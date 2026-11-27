"""
auth_store.py
Multi-user authentication, admin approval workflow, signed session cookies,
encrypted per-user Green API credential storage, and user management helpers.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from nepal_news_store import esc_sql, get_env_variable, query_supabase

logger = logging.getLogger("auth_store")

SESSION_COOKIE_NAME = "nsm_session"
SESSION_TTL_SECONDS = 7 * 24 * 3600  # 7 days
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{3,32}$")
_MULTIUSER_TABLES_ENSURED = False


def _get_master_secret() -> bytes:
    """Derives a 32-byte master key from APP_ENCRYPTION_KEY (preferred) or APP_PASSWORD + SUPABASE_PROJECT_REF."""
    enc_key = (get_env_variable("APP_ENCRYPTION_KEY") or "").strip()
    if enc_key:
        return hashlib.sha256(f"nsm-enc-v1:{enc_key}".encode("utf-8")).digest()
    app_pwd = (get_env_variable("APP_PASSWORD") or "").strip()
    proj_ref = (get_env_variable("SUPABASE_PROJECT_REF") or "").strip()
    seed = f"nsm-fallback-v1:{app_pwd}:{proj_ref}"
    return hashlib.pbkdf2_hmac("sha256", seed.encode("utf-8"), b"nepal-social-monitor-salt", 100_000, dklen=32)


# ---------------------------------------------------------------------------
# Password hashing (salted scrypt)
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Hashes a plaintext password with a random 16-byte salt using scrypt."""
    pwd = (password or "").encode("utf-8")
    salt = os.urandom(16)
    digest = hashlib.scrypt(pwd, salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verifies a plaintext password against a stored scrypt hash."""
    if not password or not stored_hash:
        return False
    parts = stored_hash.split("$")
    if len(parts) != 3 or parts[0] != "scrypt":
        return False
    try:
        salt = bytes.fromhex(parts[1])
        expected = bytes.fromhex(parts[2])
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Authenticated encryption for Green API tokens (zero external deps)
# ---------------------------------------------------------------------------

def _derive_stream_mac_keys(master: bytes, nonce: bytes) -> Tuple[bytes, bytes]:
    enc_key = hmac.new(master, b"enc:" + nonce, hashlib.sha256).digest()
    mac_key = hmac.new(master, b"mac:" + nonce, hashlib.sha256).digest()
    return enc_key, mac_key


def _xor_keystream(data: bytes, enc_key: bytes) -> bytes:
    out = bytearray(len(data))
    counter = 0
    pos = 0
    while pos < len(data):
        block = hashlib.sha256(enc_key + counter.to_bytes(4, "big")).digest()
        take = min(len(block), len(data) - pos)
        for i in range(take):
            out[pos + i] = data[pos + i] ^ block[i]
        pos += take
        counter += 1
    return bytes(out)


def encrypt_secret(plaintext: str) -> str:
    """Encrypts a secret string with authenticated encryption (v1$<nonce>$<ct>$<mac>)."""
    clean = (plaintext or "").strip()
    if not clean:
        return ""
    master = _get_master_secret()
    nonce = os.urandom(16)
    enc_key, mac_key = _derive_stream_mac_keys(master, nonce)
    ct = _xor_keystream(clean.encode("utf-8"), enc_key)
    tag = hmac.new(mac_key, nonce + ct, hashlib.sha256).digest()
    return "v1${}${}${}".format(
        base64.urlsafe_b64encode(nonce).decode("ascii"),
        base64.urlsafe_b64encode(ct).decode("ascii"),
        base64.urlsafe_b64encode(tag).decode("ascii"),
    )


def decrypt_secret(token: str) -> str:
    """Decrypts a v1$ secret string, returning '' on empty or invalid input."""
    raw = (token or "").strip()
    if not raw:
        return ""
    parts = raw.split("$")
    if len(parts) != 4 or parts[0] != "v1":
        return ""
    try:
        nonce = base64.urlsafe_b64decode(parts[1].encode("ascii"))
        ct = base64.urlsafe_b64decode(parts[2].encode("ascii"))
        tag = base64.urlsafe_b64decode(parts[3].encode("ascii"))
        master = _get_master_secret()
        enc_key, mac_key = _derive_stream_mac_keys(master, nonce)
        expected_tag = hmac.new(mac_key, nonce + ct, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected_tag):
            return ""
        pt = _xor_keystream(ct, enc_key)
        return pt.decode("utf-8")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Signed session cookie tokens
# ---------------------------------------------------------------------------

def create_session_token(
    user_id: int,
    username: str,
    role: str,
    ttl_seconds: int = SESSION_TTL_SECONDS,
) -> str:
    """Creates an HMAC-SHA256 signed session token for browser cookie persistence."""
    payload = {
        "uid": int(user_id),
        "u": str(username),
        "r": str(role),
        "exp": int(time.time()) + int(ttl_seconds),
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    b64 = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    sig = hmac.new(_get_master_secret(), b64.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{b64}.{sig}"


def verify_session_token(token: str) -> Optional[Dict[str, Any]]:
    """Verifies signature and expiration of a session token; returns payload dict or None."""
    if not token or "." not in token:
        return None
    try:
        b64, sig = token.strip().rsplit(".", 1)
        expected_sig = hmac.new(_get_master_secret(), b64.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        padded = b64 + "=" * (-len(b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        if not payload.get("uid") or not payload.get("u"):
            return None
        return payload
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Database schema & helpers
# ---------------------------------------------------------------------------

def ensure_multiuser_tables() -> None:
    """Creates app_users and user_greenapi_configs tables if they do not exist."""
    global _MULTIUSER_TABLES_ENSURED
    if _MULTIUSER_TABLES_ENSURED:
        return
    sql = """
    CREATE TABLE IF NOT EXISTS app_users (
        id SERIAL PRIMARY KEY,
        username TEXT NOT NULL UNIQUE,
        display_name TEXT NOT NULL DEFAULT '',
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        status TEXT NOT NULL DEFAULT 'pending',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        approved_at TIMESTAMP WITH TIME ZONE,
        approved_by INTEGER
    );
    CREATE INDEX IF NOT EXISTS idx_app_users_status ON app_users (status);
    CREATE TABLE IF NOT EXISTS user_greenapi_configs (
        user_id INTEGER PRIMARY KEY REFERENCES app_users(id) ON DELETE CASCADE,
        api_url TEXT NOT NULL DEFAULT '',
        id_instance TEXT NOT NULL DEFAULT '',
        token_instance_enc TEXT NOT NULL DEFAULT '',
        sending_enabled BOOLEAN NOT NULL DEFAULT FALSE,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_by INTEGER
    );
    """
    query_supabase(sql)
    _MULTIUSER_TABLES_ENSURED = True


def _run_with_table_retry(sql: str) -> List[Dict[str, Any]]:
    ensure_multiuser_tables()
    try:
        return query_supabase(sql)
    except Exception as exc:
        msg = str(exc).lower()
        if "app_users" in msg or "user_greenapi_configs" in msg or "does not exist" in msg:
            global _MULTIUSER_TABLES_ENSURED
            _MULTIUSER_TABLES_ENSURED = False
            ensure_multiuser_tables()
            return query_supabase(sql)
        raise


def bootstrap_admin_user(app_password: str) -> Optional[Dict[str, Any]]:
    """
    Ensures at least one approved admin user exists.
    If no admin exists and app_password is provided, creates username='admin'
    with app_password and seeds its Green API config from environment if present.
    """
    if not app_password:
        return None
    rows = _run_with_table_retry(
        "SELECT id, username, display_name, role, status FROM app_users WHERE role = 'admin' LIMIT 1;"
    )
    if rows:
        return rows[0]

    pwd_hash = hash_password(app_password)
    inserted = _run_with_table_retry(
        f"""
        INSERT INTO app_users (username, display_name, password_hash, role, status, approved_at)
        VALUES ('admin', 'Administrator', {esc_sql(pwd_hash)}, 'admin', 'approved', NOW())
        ON CONFLICT (username) DO UPDATE SET
            role = 'admin',
            status = 'approved',
            updated_at = NOW()
        RETURNING id, username, display_name, role, status;
        """
    )
    admin_row = inserted[0] if inserted else None
    if admin_row:
        env_url = (get_env_variable("GREEN_API_URL") or "").strip().rstrip("/")
        env_id = (get_env_variable("GREEN_API_ID_INSTANCE") or "").strip()
        env_tok = (get_env_variable("GREEN_API_TOKEN_INSTANCE") or "").strip()
        env_enabled = (get_env_variable("GREEN_API_SENDING_ENABLED", "") or "").strip().lower() not in ("0", "false", "no")
        if env_url and env_id and env_tok:
            upsert_user_greenapi_config(
                user_id=int(admin_row["id"]),
                api_url=env_url,
                id_instance=env_id,
                token_instance=env_tok,
                sending_enabled=env_enabled,
                admin_id=int(admin_row["id"]),
            )
    return admin_row


def slugify_username_from_full_name(full_name: str) -> str:
    """Derives a clean 3-32 char username slug from a user's full name."""
    tokens = re.findall(r"[a-z0-9]+", (full_name or "").strip().lower())
    slug = ".".join(tokens)[:32].strip(".")
    if len(slug) < 3:
        slug = (slug + "user")[:32]
    return slug


def register_user(username: str, display_name: str, password: str) -> Tuple[bool, str]:
    """Registers a new user in 'pending' status awaiting admin approval."""
    dname = (display_name or "").strip() or (username or "").strip()
    uname = (username or "").strip().lower()
    if not uname and dname:
        uname = slugify_username_from_full_name(dname)
    if not dname or len(dname) < 2:
        return False, "Please enter your Full Name."
    if not _USERNAME_RE.match(uname):
        return False, "Name must contain at least 3 letters or numbers."
    if len(password or "") < 6:
        return False, "Password must be at least 6 characters."

    existing_name = _run_with_table_retry(
        f"SELECT id FROM app_users WHERE LOWER(display_name) = {esc_sql(dname.lower())} LIMIT 1;"
    )
    if existing_name:
        return False, "An account with that Full Name already exists."

    base_uname = uname
    suffix = 2
    while _run_with_table_retry(f"SELECT id FROM app_users WHERE LOWER(username) = {esc_sql(uname)} LIMIT 1;"):
        suf = str(suffix)
        uname = f"{base_uname[:32 - len(suf)]}{suf}"
        suffix += 1

    pwd_hash = hash_password(password)
    _run_with_table_retry(
        f"""
        INSERT INTO app_users (username, display_name, password_hash, role, status)
        VALUES ({esc_sql(uname)}, {esc_sql(dname[:80])}, {esc_sql(pwd_hash)}, 'user', 'pending');
        """
    )
    return True, f"Access request submitted for {dname}. Wait for an administrator to approve it."


def authenticate_user(
    username: str,
    password: str,
    fallback_admin_password: str = "",
) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Authenticates a user against app_users.
    Returns (user_dict, '') on success, or (None, error_message) on failure.
    """
    uname = (username or "").strip().lower()
    pwd = (password or "").strip()
    if not uname or not pwd:
        return None, "Please enter both username and password."

    try:
        rows = _run_with_table_retry(
            f"SELECT id, username, display_name, password_hash, role, status "
            f"FROM app_users WHERE LOWER(username) = {esc_sql(uname)} "
            f"OR LOWER(display_name) = {esc_sql(uname)} "
            f"OR LOWER(SPLIT_PART(TRIM(display_name), ' ', 1)) = {esc_sql(uname)} "
            f"LIMIT 10;"
        )
        if not rows and uname == "admin" and fallback_admin_password and hmac.compare_digest(pwd, fallback_admin_password):
            admin_row = bootstrap_admin_user(fallback_admin_password)
            if admin_row:
                return {
                    "id": int(admin_row["id"]),
                    "username": str(admin_row["username"]),
                    "display_name": str(admin_row.get("display_name") or "Administrator"),
                    "role": "admin",
                    "status": "approved",
                }, ""
        if not rows:
            return None, "Invalid first name or password."

        row = None
        for cand in rows:
            if verify_password(pwd, str(cand.get("password_hash") or "")):
                row = cand
                break
            if uname == "admin" and str(cand.get("username") or "").lower() == "admin" and fallback_admin_password and hmac.compare_digest(pwd, fallback_admin_password):
                row = cand
                break
        if row is None:
            return None, "Invalid first name or password."

        status = str(row.get("status") or "pending").lower()
        if status == "pending":
            return None, "Your account is pending administrator approval."
        if status != "approved":
            return None, "Your account has been disabled. Contact an administrator."

        return {
            "id": int(row["id"]),
            "username": str(row["username"]),
            "display_name": str(row.get("display_name") or row["username"]),
            "role": str(row.get("role") or "user"),
            "status": status,
        }, ""
    except Exception as exc:
        logger.warning(f"DB auth failed ({type(exc).__name__}); checking fallback admin.")
        if uname == "admin" and fallback_admin_password and hmac.compare_digest(pwd, fallback_admin_password):
            return {
                "id": 0,
                "username": "admin",
                "display_name": "Administrator",
                "role": "admin",
                "status": "approved",
            }, ""
        return None, "Unable to verify credentials right now. Please try again."


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Fetches an approved user by ID for session restoration."""
    try:
        rows = _run_with_table_retry(
            f"SELECT id, username, display_name, role, status "
            f"FROM app_users WHERE id = {int(user_id)} LIMIT 1;"
        )
        if not rows:
            return None
        row = rows[0]
        if str(row.get("status") or "").lower() != "approved":
            return None
        return {
            "id": int(row["id"]),
            "username": str(row["username"]),
            "display_name": str(row.get("display_name") or row["username"]),
            "role": str(row.get("role") or "user"),
            "status": "approved",
        }
    except Exception:
        return None


def list_users() -> List[Dict[str, Any]]:
    """Lists all users with their Green API assignment metadata (never returning raw tokens)."""
    sql = """
    SELECT
        u.id,
        u.username,
        u.display_name,
        u.role,
        u.status,
        u.created_at,
        u.approved_at,
        g.api_url,
        g.id_instance,
        (COALESCE(g.token_instance_enc, '') <> '') AS has_token,
        COALESCE(g.sending_enabled, FALSE) AS sending_enabled
    FROM app_users u
    LEFT JOIN user_greenapi_configs g ON g.user_id = u.id
    ORDER BY
        CASE u.status WHEN 'pending' THEN 0 WHEN 'approved' THEN 1 ELSE 2 END,
        u.created_at DESC;
    """
    return _run_with_table_retry(sql)


def update_user_status(user_id: int, status: str, admin_id: int) -> bool:
    """Approves, disables, or sets a user to pending."""
    clean_status = status if status in ("pending", "approved", "disabled") else "disabled"
    approved_sql = ", approved_at = NOW(), approved_by = " + str(int(admin_id)) if clean_status == "approved" else ""
    _run_with_table_retry(
        f"""
        UPDATE app_users
        SET status = {esc_sql(clean_status)}, updated_at = NOW(){approved_sql}
        WHERE id = {int(user_id)};
        """
    )
    return True


def update_user_role(user_id: int, role: str) -> bool:
    clean_role = role if role in ("admin", "user") else "user"
    _run_with_table_retry(
        f"UPDATE app_users SET role = {esc_sql(clean_role)}, updated_at = NOW() WHERE id = {int(user_id)};"
    )
    return True


def reset_user_password(user_id: int, new_password: str) -> Tuple[bool, str]:
    if len(new_password or "") < 6:
        return False, "Password must be at least 6 characters."
    pwd_hash = hash_password(new_password)
    _run_with_table_retry(
        f"UPDATE app_users SET password_hash = {esc_sql(pwd_hash)}, updated_at = NOW() WHERE id = {int(user_id)};"
    )
    return True, "Password updated."


def change_own_password(user_id: int, current_password: str, new_password: str) -> Tuple[bool, str]:
    """Allows a logged-in user to change their own password after verifying their current password."""
    if not user_id or int(user_id) <= 0:
        return False, "Password cannot be changed in fallback mode."
    if len(new_password or "") < 6:
        return False, "New password must be at least 6 characters."
    rows = _run_with_table_retry(
        f"SELECT password_hash FROM app_users WHERE id = {int(user_id)} LIMIT 1;"
    )
    if not rows:
        return False, "Account not found."
    if not verify_password(current_password or "", str(rows[0].get("password_hash") or "")):
        return False, "Current password is incorrect."
    pwd_hash = hash_password(new_password)
    _run_with_table_retry(
        f"UPDATE app_users SET password_hash = {esc_sql(pwd_hash)}, updated_at = NOW() WHERE id = {int(user_id)};"
    )
    return True, "Your password has been updated."


def get_user_greenapi_config(user_id: int) -> Optional[Dict[str, Any]]:
    """Returns decrypted Green API config for a user, or None if not assigned."""
    if not user_id or int(user_id) <= 0:
        return None
    try:
        rows = _run_with_table_retry(
            f"SELECT user_id, api_url, id_instance, token_instance_enc, sending_enabled "
            f"FROM user_greenapi_configs WHERE user_id = {int(user_id)} LIMIT 1;"
        )
        if not rows:
            return None
        row = rows[0]
        token_plain = decrypt_secret(str(row.get("token_instance_enc") or ""))
        return {
            "user_id": int(row["user_id"]),
            "api_url": str(row.get("api_url") or "").strip().rstrip("/"),
            "id_instance": str(row.get("id_instance") or "").strip(),
            "token_instance": token_plain,
            "sending_enabled_flag": "true" if row.get("sending_enabled") else "false",
            "sending_enabled": bool(row.get("sending_enabled")),
        }
    except Exception as exc:
        logger.warning(f"Failed to load Green API config for user {user_id}: {type(exc).__name__}")
        return None


def upsert_user_greenapi_config(
    user_id: int,
    api_url: str,
    id_instance: str,
    token_instance: str,
    sending_enabled: bool,
    admin_id: int,
) -> bool:
    """
    Assigns or updates a user's Green API credentials.
    If token_instance is empty on an existing row, preserves the existing encrypted token.
    """
    clean_url = (api_url or "").strip().rstrip("/")
    clean_id = (id_instance or "").strip()
    clean_tok = (token_instance or "").strip()
    enabled_sql = "TRUE" if sending_enabled else "FALSE"

    if clean_tok:
        tok_enc = encrypt_secret(clean_tok)
        tok_update_sql = f"token_instance_enc = {esc_sql(tok_enc)},"
    else:
        tok_enc = ""
        tok_update_sql = ""

    _run_with_table_retry(
        f"""
        INSERT INTO user_greenapi_configs (user_id, api_url, id_instance, token_instance_enc, sending_enabled, updated_at, updated_by)
        VALUES ({int(user_id)}, {esc_sql(clean_url)}, {esc_sql(clean_id)}, {esc_sql(tok_enc)}, {enabled_sql}, NOW(), {int(admin_id)})
        ON CONFLICT (user_id) DO UPDATE SET
            api_url = EXCLUDED.api_url,
            id_instance = EXCLUDED.id_instance,
            {tok_update_sql}
            sending_enabled = EXCLUDED.sending_enabled,
            updated_at = NOW(),
            updated_by = EXCLUDED.updated_by;
        """
    )
    return True
