"""
whatsapp_greenapi.py
Server-side Green API integration for WhatsApp group discovery and message sharing.
All credentials remain strictly server-side via environment / Streamlit secrets.
Actual group messaging remains inactive until Green API setup is confirmed and approved.
"""

import os
import hashlib
import logging
import requests
from typing import Dict, Any, List, Optional, Set

from nepal_news_store import get_env_variable

logger = logging.getLogger("whatsapp_greenapi")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def _get_green_config() -> Dict[str, str]:
    """Loads Green API configuration strictly server-side."""
    return {
        "api_url": (get_env_variable("GREEN_API_URL") or "").rstrip("/"),
        "id_instance": get_env_variable("GREEN_API_ID_INSTANCE") or "",
        "token_instance": get_env_variable("GREEN_API_TOKEN_INSTANCE") or "",
        "env_chat_id": get_env_variable("GREEN_API_CHAT_ID") or "",
        "sending_enabled_flag": get_env_variable("GREEN_API_SENDING_ENABLED", "").lower(),
    }


def _resolve_green_config(config: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """Resolves a Green API config dict, falling back to server environment if omitted."""
    if config is not None:
        flag = config.get("sending_enabled_flag")
        if flag is None and "sending_enabled" in config:
            flag = "true" if config.get("sending_enabled") else "false"
        return {
            "api_url": str(config.get("api_url") or "").strip().rstrip("/"),
            "id_instance": str(config.get("id_instance") or "").strip(),
            "token_instance": str(config.get("token_instance") or "").strip(),
            "env_chat_id": str(config.get("env_chat_id") or "").strip(),
            "sending_enabled_flag": str(flag or "").strip().lower(),
        }
    return _get_green_config()


def is_configured(config: Optional[Dict[str, Any]] = None) -> bool:
    """Returns True if Green API URL, instance ID, and token are present."""
    cfg = _resolve_green_config(config)
    return bool(cfg["api_url"] and cfg["id_instance"] and cfg["token_instance"])


def get_env_suggested_chat_id() -> str:
    """Returns the configured GREEN_API_CHAT_ID from environment, if present, without forcing selection."""
    return _get_green_config().get("env_chat_id", "")


def is_sending_active(session_approved: bool = True, config: Optional[Dict[str, Any]] = None) -> bool:
    """
    Returns True when Green API credentials are configured and sending is approved
    (unless explicitly disabled via sending_enabled_flag='false' / GREEN_API_SENDING_ENABLED=false).
    """
    cfg = _resolve_green_config(config)
    if cfg["sending_enabled_flag"] in ("0", "false", "no"):
        return False
    return bool(session_approved and bool(cfg["api_url"] and cfg["id_instance"] and cfg["token_instance"]))


def _get_whatsapp_group_id(env_var: str, default: str) -> str:
    """Retrieves group ID from environment variable or st.secrets, with fallback."""
    val = (os.getenv(env_var) or "").strip()
    if val:
        return val
    try:
        import streamlit as st
        val = str(st.secrets.get(env_var, "")).strip()
        if val:
            return val
    except Exception:
        pass
    if not os.getenv(env_var):
        logger.debug(f"{env_var} not configured in environment or secrets; using default ID.")
    return default


SOCIAL_MEDIA_GROUP: Dict[str, str] = {
    "id": _get_whatsapp_group_id("WHATSAPP_SOCIAL_MEDIA_GROUP_ID", "120363412139269937@g.us"),
    "name": "Social Media Monitoring",
}

NEWS_SHARE_GROUPS: List[Dict[str, str]] = [
    {
        "id": _get_whatsapp_group_id("WHATSAPP_PRIMARY_GROUP_ID", "120363428884458826@g.us"),
        "name": "India Related News in Nepali Media",
    },
    {
        "id": _get_whatsapp_group_id("WHATSAPP_SECONDARY_GROUP_ID", "9779823609230-1539002455@g.us"),
        "name": "Core group of PIC Wing",
    },
]


def get_share_targets(is_x_post: bool = False) -> List[Dict[str, str]]:
    """Returns the allowed WhatsApp destination group(s) for X posts vs news items."""
    return [dict(SOCIAL_MEDIA_GROUP)] if is_x_post else [dict(g) for g in NEWS_SHARE_GROUPS]


def get_destination_group(timeout: int = 10, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Resolves the configured destination WhatsApp group from GREEN_API_CHAT_ID
    and retrieves its live group name via Green API getChats.
    """
    env_cid = get_env_suggested_chat_id().strip()
    if not env_cid:
        return {"ok": True, **NEWS_SHARE_GROUPS[0], "error": ""}
    grps = list_whatsapp_groups(timeout=timeout, config=config)
    if grps.get("ok"):
        for g in grps.get("groups", []):
            if g["id"] == env_cid:
                return {"ok": True, "id": g["id"], "name": g["name"], "error": ""}
    return {"ok": True, "id": env_cid, "name": NEWS_SHARE_GROUPS[0]["name"], "error": ""}


def get_instance_status(timeout: int = 8, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Checks Green API instance authorization state without exposing credentials."""
    cfg = _resolve_green_config(config)
    if not (cfg["api_url"] and cfg["id_instance"] and cfg["token_instance"]):
        return {
            "configured": False,
            "authorized": False,
            "state": "not_configured",
            "error": "Green API credentials are not configured.",
        }
    endpoint = f"{cfg['api_url']}/waInstance{cfg['id_instance']}/getStateInstance/{cfg['token_instance']}"
    try:
        resp = requests.get(endpoint, timeout=timeout)
        if resp.status_code != 200:
            return {
                "configured": True,
                "authorized": False,
                "state": f"http_{resp.status_code}",
                "error": f"Green API returned HTTP {resp.status_code} while checking instance state.",
            }
        data = resp.json()
        state = str(data.get("stateInstance") or "unknown")
        return {
            "configured": True,
            "authorized": state == "authorized",
            "state": state,
            "error": "" if state == "authorized" else f"Instance state is '{state}'.",
        }
    except Exception as exc:
        logger.warning(f"Green API state check failed: {type(exc).__name__}")
        return {
            "configured": True,
            "authorized": False,
            "state": "unreachable",
            "error": "Unable to reach Green API instance. Check network or instance URL.",
        }


def list_whatsapp_groups(timeout: int = 10, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Retrieves available WhatsApp groups (@g.us) from the connected Green API instance."""
    cfg = _resolve_green_config(config)
    if not (cfg["api_url"] and cfg["id_instance"] and cfg["token_instance"]):
        return {"ok": False, "groups": [], "error": "Green API credentials are not configured."}

    endpoint = f"{cfg['api_url']}/waInstance{cfg['id_instance']}/getChats/{cfg['token_instance']}"
    try:
        resp = requests.get(endpoint, timeout=timeout)
        if resp.status_code != 200:
            return {
                "ok": False,
                "groups": [],
                "error": f"Green API getChats returned HTTP {resp.status_code}.",
            }
        raw_chats = resp.json()
        if not isinstance(raw_chats, list):
            return {"ok": False, "groups": [], "error": "Unexpected response format from Green API getChats."}

        seen: Set[str] = set()
        groups: List[Dict[str, str]] = []
        for ch in raw_chats:
            cid = str(ch.get("id") or "").strip()
            if not cid.endswith("@g.us") or cid in seen:
                continue
            seen.add(cid)
            name = str(ch.get("name") or "").strip() or cid
            groups.append({"id": cid, "name": name})

        groups.sort(key=lambda g: g["name"].lower())
        return {"ok": True, "groups": groups, "error": ""}
    except Exception as exc:
        logger.warning(f"Green API getChats failed: {type(exc).__name__}")
        return {"ok": False, "groups": [], "error": "Failed to retrieve WhatsApp groups from Green API."}


def verify_fixed_group_membership(timeout: int = 10, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Checks whether the Green API instance is a member of the fixed News and Social Media groups."""
    res = list_whatsapp_groups(timeout=timeout, config=config)
    fixed_targets = list(NEWS_SHARE_GROUPS) + [SOCIAL_MEDIA_GROUP]
    if not res.get("ok"):
        return {
            "ok": False,
            "error": res.get("error") or "Failed to fetch groups.",
            "present": [],
            "missing": [dict(t) for t in fixed_targets],
        }
    member_ids = {g["id"] for g in res.get("groups", [])}
    present = [dict(t) for t in fixed_targets if t["id"] in member_ids]
    missing = [dict(t) for t in fixed_targets if t["id"] not in member_ids]
    return {"ok": True, "error": "", "present": present, "missing": missing}


def build_send_dedup_key(chat_id: str, message: str) -> str:
    """Creates a deterministic key to prevent duplicate sends of the same content to the same group."""
    digest = hashlib.sha256(f"{chat_id}||{message}".encode("utf-8")).hexdigest()[:20]
    return digest


def send_group_message(
    chat_id: str,
    message: str,
    session_approved: bool = False,
    sent_registry: Optional[Set[str]] = None,
    timeout: Any = (3, 8),
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Sends a single text message to a selected WhatsApp group via Green API.
    Remains strictly inactive unless is_sending_active(session_approved, config=config) is True.
    Distinguishes Green API queue acceptance (idMessage) from confirmed delivery.
    """
    if not is_sending_active(session_approved=session_approved, config=config):
        return {
            "ok": False,
            "accepted": False,
            "status": "inactive",
            "id_message": "",
            "error": "WhatsApp group messaging is not active or not assigned for your account.",
        }

    target_chat = (chat_id or "").strip()
    body = (message or "").strip()

    if body and "news.google.com" in body.lower():
        try:
            import re
            from nepal_fetcher import resolve_google_news_url
            gnews_matches = re.findall(r"https://news\.google\.com/[^\s)\"'>]+", body)
            for gm in set(gnews_matches):
                orig = resolve_google_news_url(gm)
                if orig and orig != gm and "news.google.com" not in orig.lower():
                    body = body.replace(gm, orig)
        except Exception as res_exc:
            logger.debug(f"Google News URL resolution in send_group_message failed: {res_exc}")
    if not target_chat or not target_chat.endswith("@g.us"):
        return {
            "ok": False,
            "accepted": False,
            "status": "invalid_group",
            "id_message": "",
            "error": "Please select a valid destination WhatsApp group first.",
        }
    if not body:
        return {
            "ok": False,
            "accepted": False,
            "status": "empty_message",
            "id_message": "",
            "error": "Message content is empty.",
        }

    dedup_key = build_send_dedup_key(target_chat, body)
    if sent_registry is not None and dedup_key in sent_registry:
        return {
            "ok": False,
            "accepted": False,
            "status": "duplicate_prevented",
            "id_message": "",
            "error": "This exact content was already sent to the selected group.",
        }

    cfg = _resolve_green_config(config)
    endpoint = f"{cfg['api_url']}/waInstance{cfg['id_instance']}/sendMessage/{cfg['token_instance']}"
    payload = {
        "chatId": target_chat,
        "message": body,
        "linkPreview": True,
    }
    try:
        resp = requests.post(endpoint, json=payload, timeout=timeout)
        if resp.status_code != 200:
            return {
                "ok": False,
                "accepted": False,
                "status": "api_error",
                "id_message": "",
                "error": f"Green API rejected message with HTTP {resp.status_code}.",
            }
        data = resp.json()
        id_msg = str(data.get("idMessage") or "").strip()
        if not id_msg:
            return {
                "ok": False,
                "accepted": False,
                "status": "no_message_id",
                "id_message": "",
                "error": "Green API did not return an acceptance idMessage.",
            }
        if sent_registry is not None:
            sent_registry.add(dedup_key)
        return {
            "ok": True,
            "accepted": True,
            "status": "accepted_by_api",
            "id_message": id_msg,
            "error": "",
        }
    except Exception as exc:
        logger.warning(f"Green API sendMessage failed: {type(exc).__name__}")
        return {
            "ok": False,
            "accepted": False,
            "status": "network_error",
            "id_message": "",
            "error": "Network error while sending to Green API.",
        }
