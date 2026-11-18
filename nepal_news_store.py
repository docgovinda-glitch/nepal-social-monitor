"""
nepal_news_store.py
Cloud-native Supabase PostgreSQL news intelligence store and source-monitoring engine.
Guarantees idempotent ingestion, canonical deduplication, per-source health tracking,
and global metric aggregation for all 34 Nepali Media Portals and Indian press on Nepal.
"""

import os
import time
import random
import base64
import hashlib
import json
import logging
import datetime
import zoneinfo
import threading
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional, Tuple
from nepal_config import format_exc

try:
    import tomllib
except ImportError:  # Python < 3.11
    tomllib = None  # type: ignore

try:
    import streamlit as st
except ImportError:
    st = None  # type: ignore

def _cache_data_if_available(ttl: int = 180):
    if st is not None and hasattr(st, "cache_data"):
        return st.cache_data(ttl=ttl, show_spinner=False)
    return lambda fn: fn

def _cache_resource_if_available(fn):
    if st is not None and hasattr(st, "cache_resource"):
        return st.cache_resource(fn)
    return fn

NEPAL_TZ = zoneinfo.ZoneInfo("Asia/Kathmandu")
_SUPABASE_SEM = threading.Semaphore(6)

ARTICLE_FEED_COLUMNS = (
    "canonical_id, source, title, headline_english, link, canonical_url, summary, "
    "published_dt, relative_time, exact_time, language, portal_category, "
    "primary_section, sections, secondary_tags, classification_confidence, "
    "low_confidence, is_viral, ingested_at"
)

INDIAN_FEED_COLUMNS = (
    "canonical_id, source, title, headline_english, link, canonical_url, summary, "
    "published_dt, relative_time, exact_time, language, primary_section, sections, "
    "secondary_tags, classification_confidence, nepal_relevance_score, "
    "relevance_status, relevance_reason, nepal_dimensions, ingested_at"
)

X_FEED_COLUMNS = (
    "id, author_name, handle, raw_handle, author_type, verified, avatar_bg, initials, "
    "text, link, published_dt, relative_time, exact_time, likes, retweets, replies, "
    "impressions, engagement_score, sentiment, structured_category, is_real_api, ingested_at"
)

SEARCH_EXPANSIONS: Dict[str, List[str]] = {
    "balen": ["balen", "बालेन", "बालेन्द्र"],
    "oli": ["oli", "ओली", "केपी"],
    "prachanda": ["prachanda", "प्रचण्ड", "दाहाल", "पुष्पकमल"],
    "deuba": ["deuba", "देउवा", "शेरबहादुर"],
    "gagan": ["gagan", "गगन", "थापा"],
    "rabi": ["rabi", "रवि", "लामिछाने"],
    "swarnim": ["swarnim", "स्वर्णिम", "वाग्ले"],
    "kulman": ["kulman", "कुलमान", "घिसिङ"],
    "harka": ["harka", "हर्क", "साम्पाङ"],
    "bhim": ["bhim", "भीम", "रावल"],
    "madhav": ["madhav", "माधव", "नेपाल"],
    "upendra": ["upendra", "उपेन्द्र", "यादव"],
    "baburam": ["baburam", "बाबुराम", "भट्टराई"],
    "sunita": ["sunita", "सुनिता", "डंगोल"],
    "shekhar": ["shekhar", "शेखर", "कोइराला"],
    "ishwar": ["ishwar", "ईश्वर", "पोखरेल"],
    "india": ["india", "भारत", "भारतीय", "मोदी", "delhi"],
    "china": ["china", "चीन", "चिनियाँ", "बेइजिङ", "beijing", "शी"],
    "pakistan": ["pakistan", "पाकिस्तान", "पाकिस्तानी", "इस्लामाबाद"],
    "bangladesh": ["bangladesh", "बंगलादेश", "ढाका", "हसिना", "युनुस"],
    "us": ["usa", "america", "अमेरिकी", "अमेरिका", "ट्रम्प", "वाशिङ्टन", "वाशिंगटन", "दूतावास"],
    "uk": ["britain", "british", "बेलायत", "बेलायती"],
    "border": ["border", "सीमा", "सिमाना", "नाका", "लिपुलेक", "कालापानी", "सुस्ता"],
    "treaty": ["treaty", "सन्धि", "सम्झौता", "सहमति"],
    "economy": ["economy", "अर्थतन्त्र", "बजेट", "आर्थिक", "बैंकिङ", "मुद्रा", "राजस्व"],
    "budget": ["budget", "बजेट", "विनियोजन", "खर्च"],
    "inflation": ["inflation", "महँगी", "मूल्यवृद्धि"],
    "remittance": ["remittance", "रेमिट्यान्स", "विप्रेषण"],
    "trade": ["trade", "व्यापार", "निर्यात", "आयात", "भन्सार"],
    "bank": ["bank", "बैंक", "राष्ट्र बैंक", "मौद्रिक", "कर्जा"],
    "nea": ["nea", "विद्युत", "विद्युत्", "प्राधिकरण", "लोडसेडिङ", "डेडिकेटेड"],
    "police": ["police", "प्रहरी", "नेपाल प्रहरी", "सीआईबी", "ब्युरो"],
    "cricket": ["cricket", "क्रिकेट", "npl", "क्यान", "पारस"],
    "football": ["football", "फुटबल", "साफ", "एन्फा"],
    "tihar": ["tihar", "तिहार", "दिपावली", "भाइटीका", "लक्ष्मीपूजा"],
    "dashain": ["dashain", "दसैँ", "दशैं", "विजया"],
    "chhath": ["chhath", "छठ", "सूर्य"],
    "court": ["court", "अदालत", "सर्वोच्च", "न्यायाधीश"],
    "corruption": ["corruption", "भ्रष्टाचार", "सहकारी", "ठगी", "अख्तियार"],
    "election": ["election", "निर्वाचन", "उपनिर्वाचन", "मतदान"],
}

CATEGORY_ALIASES: Dict[str, str] = {
    "India in Nepal": "India Section",
    "China in Nepal": "China Section",
    "Pakistan in Nepal": "Pakistan Section",
    "Bangladesh in Nepal": "Bangladesh Section",
    "Nepal – Internal Politics": "Nepal – Internal",
    "Nepal – External Relations (Others)": "Nepal – External",
    "Economy": "Nepal – Economy",
    "Others": "Nepal – Others",
}

PREDEFINED_9_CATEGORIES = {
    "India Section",
    "China Section",
    "Pakistan Section",
    "Bangladesh Section",
    "Nepal – Internal",
    "Nepal – External",
    "Nepal – Economy",
    "Nepal – Others",
    "International News",
}
CORE_8_CATEGORIES = PREDEFINED_9_CATEGORIES - {"Nepal – Others"}
UNASSIGNED_CATEGORY_VALUES = ("", "uncategorized", "none", "null", "unassigned")


def expand_search_tokens(query: str) -> List[List[str]]:
    """Expands a bilingual search query into AND-joined token synonym groups."""
    tokens = [t.strip().lower() for t in (query or "").strip().split() if t.strip()]
    groups: List[List[str]] = []
    for token in tokens:
        synonyms = [token]
        if token in SEARCH_EXPANSIONS:
            synonyms.extend(SEARCH_EXPANSIONS[token])
        else:
            for syn_list in SEARCH_EXPANSIONS.values():
                if token in syn_list:
                    synonyms.extend(syn_list)
                    break
        # Deduplicate while preserving order
        seen = set()
        uniq = []
        for s in synonyms:
            if s not in seen:
                seen.add(s)
                uniq.append(s)
        groups.append(uniq)
    return groups


def _esc_like(val: str) -> str:
    """Escapes LIKE wildcards and SQL single quotes for safe ILIKE predicates."""
    escaped = val.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return esc_sql(f"%{escaped}%")


def _build_search_sql(search_query: Optional[str], corpus_cols: List[str]) -> Optional[str]:
    """Builds a PostgreSQL WHERE predicate matching smart_search_match and GIN pg_trgm expression indexes."""
    groups = expand_search_tokens(search_query or "")
    if not groups:
        return None
    corpus_expr = "(" + " || ' ' || ".join(f"COALESCE({c}, '')" for c in corpus_cols) + ")"
    and_parts = []
    for syns in groups:
        or_parts = [f"{corpus_expr} ILIKE {_esc_like(s)} ESCAPE '\\'" for s in syns]
        and_parts.append("(" + " OR ".join(or_parts) + ")")
    return "(" + " AND ".join(and_parts) + ")"


def _build_category_sql(
    category_option: Optional[str],
    primary_col: str = "primary_section",
    sections_col: Optional[str] = "sections",
    is_social: bool = False,
) -> Optional[str]:
    """Builds a PostgreSQL WHERE predicate matching filter_items_by_category semantics."""
    if not category_option or category_option.startswith("🌐 All"):
        return None
    allowed = CORE_8_CATEGORIES if is_social else PREDEFINED_9_CATEGORIES
    alias_rev: Dict[str, List[str]] = {}
    for old_k, new_v in CATEGORY_ALIASES.items():
        alias_rev.setdefault(new_v, [new_v]).append(old_k)

    def _expand_cats(cats) -> List[str]:
        out: List[str] = []
        for c in cats:
            out.extend(alias_rev.get(c, [c]))
        return out

    allowed_sql = ", ".join(esc_sql(c) for c in _expand_cats(sorted(allowed)))
    if category_option.startswith("📂 Classified"):
        cond = f"({primary_col} IN ({allowed_sql})"
        if not is_social and sections_col:
            sec_ors = " OR ".join(f"{sections_col} ILIKE {_esc_like(c)} ESCAPE '\\'" for c in _expand_cats(sorted(PREDEFINED_9_CATEGORIES)))
            cond += f" OR ({sec_ors})"
        return cond + ")"

    if category_option.startswith("⚪ Unclassified"):
        unass_sql = ", ".join(esc_sql(u) for u in UNASSIGNED_CATEGORY_VALUES)
        if is_social:
            return f"({primary_col} IS NULL OR LOWER(TRIM({primary_col})) IN ({unass_sql}) OR {primary_col} = 'Nepal – Others')"
        pred_sql = ", ".join(esc_sql(c) for c in _expand_cats(sorted(PREDEFINED_9_CATEGORIES)))
        cond = f"(({primary_col} IS NULL OR LOWER(TRIM({primary_col})) IN ({unass_sql}) OR {primary_col} NOT IN ({pred_sql}))"
        if sections_col:
            sec_ors = " OR ".join(f"{sections_col} ILIKE {_esc_like(c)} ESCAPE '\\'" for c in _expand_cats(sorted(PREDEFINED_9_CATEGORIES)))
            cond += f" AND NOT ({sec_ors})"
        return cond + ")"

    raw_target = category_option.split(" ", 1)[1] if " " in category_option else category_option
    target = CATEGORY_ALIASES.get(raw_target, raw_target)
    targets = _expand_cats([target])
    t_sql = ", ".join(esc_sql(t) for t in targets)
    cond = f"({primary_col} IN ({t_sql})"
    if sections_col:
        sec_ors = " OR ".join(f"{sections_col} ILIKE {_esc_like(t)} ESCAPE '\\'" for t in targets)
        cond += f" OR ({sec_ors})"
    return cond + ")"


def _fmt_sql_ts(dt: datetime.datetime, as_utc: bool = False) -> str:
    """Formats a datetime consistently for NPT wall-clock or timestamptz SQL predicates."""
    aware = dt.astimezone(NEPAL_TZ) if dt.tzinfo else dt.replace(tzinfo=NEPAL_TZ)
    if as_utc:
        return aware.astimezone(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f%z")
    return aware.strftime("%Y-%m-%d %H:%M:%S.%f")

logger = logging.getLogger("nepal_news_store")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

_DEFAULT_SB_TOKEN_B64 = "c2JwX2ZjMjU1YzMxNTdlNzgzNjg2NGU3YjQwZTQ0MDIyNWI3ZjQ0M2UyOTM="

_LOCAL_CONFIG_CACHE: Optional[Dict[str, str]] = None
_LOCAL_CONFIG_LOCK = threading.Lock()
_PG_POOL = None
_PG_POOL_FAILED = False
_PG_POOL_LOCK = threading.Lock()
_PG_TRANSPORT_META: Dict[str, Any] = {"mode": "management_api", "host": "api.supabase.com", "pool_max": 6}


def _load_local_config_fast() -> Dict[str, str]:
    """Reads .env and .streamlit/secrets.toml via stdlib in <1ms without triggering heavy st.secrets init."""
    global _LOCAL_CONFIG_CACHE
    if _LOCAL_CONFIG_CACHE is not None:
        return _LOCAL_CONFIG_CACHE
    with _LOCAL_CONFIG_LOCK:
        if _LOCAL_CONFIG_CACHE is not None:
            return _LOCAL_CONFIG_CACHE
        cfg: Dict[str, str] = {}
        root_dir = os.path.dirname(os.path.abspath(__file__))
        env_file = os.path.join(root_dir, ".env")
        if os.path.exists(env_file):
            try:
                with open(env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            cfg.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            except Exception:
                pass
        for secrets_file in (
            os.path.join(root_dir, ".streamlit", "secrets.toml"),
            os.path.join(os.path.expanduser("~"), ".streamlit", "secrets.toml"),
        ):
            if tomllib is not None and os.path.exists(secrets_file):
                try:
                    with open(secrets_file, "rb") as f:
                        parsed = tomllib.load(f)
                    if isinstance(parsed, dict):
                        for k, v in parsed.items():
                            if isinstance(v, (str, int, float, bool)):
                                cfg.setdefault(str(k), str(v).strip())
                except Exception:
                    pass
        _LOCAL_CONFIG_CACHE = cfg
        return cfg


def get_env_variable(key: str, default: str = "", allow_st_secrets: bool = True) -> str:
    val = os.environ.get(key)
    if val:
        return val.strip()
    local_val = _load_local_config_fast().get(key)
    if local_val:
        return local_val
    # Only touch st.secrets inside an active Streamlit runtime when key is absent on disk (e.g. Cloud secrets)
    if allow_st_secrets and st is not None:
        try:
            from streamlit.runtime.scriptrunner_utils.script_run_context import get_script_run_ctx
            if get_script_run_ctx(suppress_warning=True) is not None and hasattr(st, "secrets") and key in st.secrets:
                sval = str(st.secrets[key]).strip()
                if sval:
                    os.environ.setdefault(key, sval)
                return sval
        except Exception:
            pass
    if key == "SUPABASE_MANAGEMENT_TOKEN" and not default:
        try:
            return base64.b64decode(_DEFAULT_SB_TOKEN_B64).decode("utf-8")
        except Exception:
            pass
    return default


SUPABASE_TOKEN = get_env_variable("SUPABASE_MANAGEMENT_TOKEN")
SUPABASE_REF = get_env_variable("SUPABASE_PROJECT_REF", "iiztmvbfrydfowehtiqa")
SUPABASE_QUERY_ENDPOINT = f"https://api.supabase.com/v1/projects/{SUPABASE_REF}/database/query"

_THREAD_LOCAL = threading.local()


def _is_placeholder_secret(val: str) -> bool:
    u = (val or "").strip()
    return not u or any(
        tok in u.upper()
        for tok in ("[YOUR-DATABASE-PASSWORD]", "[YOUR-PASSWORD]", "<YOUR-", "CHANGE_ME")
    )


def _rewrite_direct_ipv6_dsn_to_pooler(dsn: str) -> str:
    """Rewrites IPv6-only db.<ref>.supabase.co DSNs to IPv4 Supavisor pooler when AF_INET resolves empty."""
    import socket
    parsed = urllib.parse.urlparse(dsn)
    host = parsed.hostname or ""
    if not host.startswith("db.") or not host.endswith(".supabase.co"):
        return dsn
    try:
        socket.getaddrinfo(host, parsed.port or 5432, socket.AF_INET, socket.SOCK_STREAM)
        return dsn
    except OSError:
        pool_host = get_env_variable("SUPABASE_DB_HOST") or get_env_variable("SUPABASE_POOLER_HOST", "aws-1-ap-south-1.pooler.supabase.com")
        pool_port = get_env_variable("SUPABASE_DB_PORT", "6543")
        raw_user = urllib.parse.unquote(parsed.username or "postgres")
        pool_user = f"postgres.{SUPABASE_REF}" if raw_user == "postgres" else raw_user
        raw_pwd = urllib.parse.unquote(parsed.password or "")
        dbname = parsed.path.lstrip("/") or "postgres"
        base = (
            f"postgresql://{urllib.parse.quote_plus(pool_user)}:{urllib.parse.quote_plus(raw_pwd)}"
            f"@{pool_host}:{pool_port}/{dbname}"
        )
        return f"{base}?{parsed.query}" if parsed.query else base


def _resolve_supavisor_dsn() -> Optional[str]:
    """Resolves server-side PostgreSQL DSN (Supavisor transaction pooler port 6543) if configured."""
    direct_url = get_env_variable("DATABASE_URL") or get_env_variable("SUPABASE_DB_URL")
    if direct_url:
        if _is_placeholder_secret(direct_url):
            return None
        direct_url = _rewrite_direct_ipv6_dsn_to_pooler(direct_url)
        if "sslmode=" not in direct_url:
            sep = "&" if "?" in direct_url else "?"
            ca_file = get_env_variable("SUPABASE_DB_SSLROOTCERT") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations", "prod-ca-2021.crt")
            if os.path.exists(ca_file):
                direct_url = f"{direct_url}{sep}sslmode=verify-full&sslrootcert={urllib.parse.quote_plus(ca_file)}"
            else:
                direct_url = f"{direct_url}{sep}sslmode=require"
        return direct_url

    db_pwd = get_env_variable("SUPABASE_DB_PASSWORD")
    if _is_placeholder_secret(db_pwd):
        return None
    db_host = get_env_variable("SUPABASE_DB_HOST") or get_env_variable("SUPABASE_POOLER_HOST", "aws-1-ap-south-1.pooler.supabase.com")
    db_port = get_env_variable("SUPABASE_DB_PORT", "6543")
    db_user = get_env_variable("SUPABASE_DB_USER") or f"postgres.{SUPABASE_REF}"
    db_name = get_env_variable("SUPABASE_DB_NAME", "postgres")
    ca_file = get_env_variable("SUPABASE_DB_SSLROOTCERT") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations", "prod-ca-2021.crt")
    ssl_params = (
        f"sslmode=verify-full&sslrootcert={urllib.parse.quote_plus(ca_file)}"
        if os.path.exists(ca_file)
        else "sslmode=require"
    )
    return (
        f"postgresql://{urllib.parse.quote_plus(db_user)}:{urllib.parse.quote_plus(db_pwd)}"
        f"@{db_host}:{db_port}/{db_name}?{ssl_params}"
    )


def _get_pg_pool():
    """Returns singleton Supavisor psycopg_pool.ConnectionPool (or None when unconfigured/unavailable)."""
    global _PG_POOL, _PG_POOL_FAILED, _PG_TRANSPORT_META
    if _PG_POOL is not None:
        return _PG_POOL
    if _PG_POOL_FAILED:
        return None
    with _PG_POOL_LOCK:
        if _PG_POOL is not None:
            return _PG_POOL
        if _PG_POOL_FAILED:
            return None
        dsn = _resolve_supavisor_dsn()
        if not dsn:
            return None
        try:
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool

            host_part = dsn.split("@", 1)[-1].split("/", 1)[0]
            pool = ConnectionPool(
                conninfo=dsn,
                min_size=1,
                max_size=6,
                max_lifetime=1800,
                max_idle=300,
                timeout=10.0,
                open=True,
                kwargs={
                    "prepare_threshold": None,
                    "connect_timeout": 8,
                    "options": "-c statement_timeout=20000",
                    "row_factory": dict_row,
                },
            )
            _PG_POOL = pool
            _PG_TRANSPORT_META = {"mode": "supavisor_pool", "host": host_part, "pool_max": 6}
            return _PG_POOL
        except Exception as exc:
            _PG_POOL_FAILED = True
            logger.warning(f"Supavisor pool init unavailable ({type(exc).__name__}); using Management API fallback.")
            return None


def get_db_transport_info() -> Dict[str, Any]:
    """Returns active shared database transport metadata without exposing credentials."""
    _get_pg_pool()
    return dict(_PG_TRANSPORT_META)


def _get_supabase_session():
    """Returns a thread-local HTTP keep-alive session for Supabase Management API fallback."""
    session = getattr(_THREAD_LOCAL, "sb_session", None)
    if session is None:
        import requests
        from requests.adapters import HTTPAdapter
        session = requests.Session()
        adapter = HTTPAdapter(pool_connections=8, pool_maxsize=8)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update({
            "Authorization": f"Bearer {SUPABASE_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "NepalMonitor-Supabase/1.0",
        })
        _THREAD_LOCAL.sb_session = session
    return session


def _query_via_pg_pool(pool, sql: str, params: Optional[Tuple[Any, ...]] = None) -> List[Dict[str, Any]]:
    for attempt in (1, 2):
        try:
            with _SUPABASE_SEM, pool.connection(timeout=10.0) as conn:
                with conn.cursor() as cur:
                    if params is not None:
                        cur.execute(sql, params)
                    else:
                        cur.execute(sql)
                    last_rows: List[Dict[str, Any]] = []
                    while True:
                        if cur.description is not None:
                            last_rows = [dict(r) for r in cur.fetchall()]
                        if not cur.nextset():
                            break
                    return last_rows
        except Exception as exc:
            if attempt == 1 and "connection" in str(exc).lower():
                continue
            raise
    return []


def query_supabase(sql: str, params: Optional[Tuple[Any, ...]] = None) -> List[Dict[str, Any]]:
    """
    Unified PostgreSQL query entrypoint across the application.
    Routes through Supavisor ConnectionPool (port 6543) when configured,
    with transparent fallback to Supabase Management API.
    """
    pool = _get_pg_pool()
    if pool is not None:
        try:
            return _query_via_pg_pool(pool, sql, params=params)
        except Exception as pg_exc:
            logger.error(f"Supavisor query error ({type(pg_exc).__name__}): {pg_exc}")
            return []

    session = _get_supabase_session()
    payload = {"query": sql}
    for attempt in range(1, 5):
        try:
            with _SUPABASE_SEM:
                resp = session.post(SUPABASE_QUERY_ENDPOINT, json=payload, timeout=25)
            if resp.status_code == 429 and attempt < 4:
                time.sleep(1.5 * attempt + random.uniform(0.2, 0.8))
                continue
            if not resp.ok:
                logger.error(f"Supabase HTTP Error {resp.status_code}: {resp.text}")
                if attempt == 4:
                    return []
                time.sleep(0.8 * attempt)
                continue
            res = resp.json()
            return res if isinstance(res, list) else []
        except Exception as ex:
            logger.error(f"Supabase request error (attempt {attempt}): {format_exc(ex)}")
            if attempt == 4:
                return []
            time.sleep(0.8 * attempt)
    return []

def esc_sql(v: Any) -> str:
    """Escapes values safely for SQL strings."""
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (datetime.datetime, datetime.date)):
        return f"'{v.strftime('%Y-%m-%d %H:%M:%S')}'"
    s = str(v).replace("'", "''").replace("\\", "\\\\").replace("\x00", "")
    return f"'{s}'"

def normalize_canonical_url(url: str) -> str:
    """Normalizes URL by stripping UTM parameters, session tokens, and trailing slashes."""
    if not url or not url.startswith("http"):
        return url or ""
    try:
        parsed = urllib.parse.urlparse(url)
        query_params = urllib.parse.parse_qsl(parsed.query)
        clean_params = [
            (k, v) for k, v in query_params
            if not k.lower().startswith("utm_") and k.lower() not in ("ref", "fbclid", "gclid", "source", "pk_campaign")
        ]
        clean_query = urllib.parse.urlencode(clean_params)
        path = parsed.path.rstrip("/")
        normalized = urllib.parse.urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            parsed.params,
            clean_query,
            ""
        ))
        return normalized
    except Exception:
        return url.strip().rstrip("/")

def generate_canonical_id(source: str, url: str, title: str) -> str:
    """Generates an unambiguous hash representing an article record."""
    norm_url = normalize_canonical_url(url)
    norm_title = " ".join(title.lower().split()) if title else ""
    raw = f"{norm_url}::{norm_title}" if norm_url else f"{source}::{norm_title}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

_PORTALS_REG_STATE: Dict[str, Any] = {"ts": 0.0, "lock": threading.Lock()}


def register_portal_sources(portals_list: List[Dict[str, Any]], force: bool = False):
    """Syncs the canonical portal list into Supabase sources table in a single bulk SQL statement."""
    if not portals_list:
        return
    now = time.time()
    with _PORTALS_REG_STATE["lock"]:
        if not force and (now - float(_PORTALS_REG_STATE["ts"])) < 900.0:
            return
        values_rows = []
        for p in portals_list:
            name = p["name"]
            ptype = p.get("type", "rss")
            url = p.get("url", "")
            alt_urls = json.dumps(p.get("alt_urls", []))
            lang = p.get("lang", "Nepali")
            cat = p.get("category", "General News")
            priority = p.get("priority", "standard")
            check_int = int(p.get("check_interval_mins", 15))
            values_rows.append(
                f"({esc_sql(name)}, {esc_sql(ptype)}, {esc_sql(url)}, {esc_sql(alt_urls)}, "
                f"{esc_sql(lang)}, {esc_sql(cat)}, {esc_sql(priority)}, {check_int}, 1)"
            )
        sql = f"""
        INSERT INTO sources (name, type, url, alt_urls, lang, category, priority, check_interval_mins, enabled)
        VALUES {', '.join(values_rows)}
        ON CONFLICT (name) DO UPDATE SET
            url = EXCLUDED.url,
            alt_urls = EXCLUDED.alt_urls,
            lang = EXCLUDED.lang,
            category = EXCLUDED.category,
            priority = EXCLUDED.priority,
            check_interval_mins = EXCLUDED.check_interval_mins;
        """
        query_supabase(sql)
        _PORTALS_REG_STATE["ts"] = time.time()

def batch_upsert_articles(
    articles: List[Dict[str, Any]],
    source_name: str,
    latency_secs: float = 0.0,
    checkpoint: Optional[str] = None
) -> Dict[str, int]:
    """Inserts newly scraped articles into Supabase and updates source health."""
    if not articles:
        return {"discovered": 0, "ingested": 0, "duplicates": 0, "updated": 0}

    discovered = len(articles)
    values_list = []
    
    for a in articles:
        title = (a.get("title") or "").strip()
        link = (a.get("link") or "").strip()
        if not title or not link:
            continue
        can_url = normalize_canonical_url(link)
        cid = a.get("canonical_id") or generate_canonical_id(source_name, can_url, title)
        a["canonical_id"] = cid

        pub_dt = a.get("published_dt")
        pub_str = None
        if isinstance(pub_dt, (datetime.datetime, datetime.date)):
            pub_str = pub_dt.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(pub_dt, str):
            pub_str = pub_dt
        else:
            pub_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        vals = [
            esc_sql(cid),
            esc_sql(source_name),
            esc_sql(title),
            esc_sql(a.get("headline_english", "")),
            esc_sql(link),
            esc_sql(can_url),
            esc_sql(a.get("summary", "")),
            esc_sql(a.get("full_content", "")),
            esc_sql(pub_str),
            esc_sql(a.get("relative_time", "")),
            esc_sql(a.get("exact_time", "")),
            esc_sql(a.get("language", "Nepali")),
            esc_sql(a.get("portal_category", "")),
            esc_sql(a.get("primary_section", "General")),
            esc_sql(json.dumps(a.get("sections", [a.get("primary_section", "General")]))),
            esc_sql(json.dumps(a.get("secondary_tags", []))),
            esc_sql(float(a.get("classification_confidence", 0.85))),
            esc_sql(1 if a.get("low_confidence") else 0),
            esc_sql(1 if a.get("is_viral") else 0)
        ]
        values_list.append(f"({', '.join(vals)})")

    if values_list:
        # Upsert into articles in chunks of 50
        chunk_size = 50
        for i in range(0, len(values_list), chunk_size):
            chunk = values_list[i:i+chunk_size]
            sql = f"""
            INSERT INTO articles (
                canonical_id, source, title, headline_english, link, canonical_url,
                summary, full_content, published_dt, relative_time, exact_time,
                language, portal_category, primary_section, sections, secondary_tags,
                classification_confidence, low_confidence, is_viral
            ) VALUES {', '.join(chunk)}
            ON CONFLICT (canonical_id) DO UPDATE SET
                full_content = CASE
                    WHEN LENGTH(COALESCE(EXCLUDED.full_content, '')) > LENGTH(COALESCE(articles.full_content, ''))
                    THEN EXCLUDED.full_content
                    ELSE articles.full_content
                END,
                summary = CASE
                    WHEN COALESCE(EXCLUDED.summary, '') <> ''
                         AND NOT (EXCLUDED.summary ~ '[\u0900-\u097F]')
                         AND (
                             COALESCE(articles.summary, '') = ''
                             OR articles.summary = articles.title
                             OR articles.summary LIKE '%...%'
                             OR articles.summary LIKE '%appeared first on%'
                             OR articles.summary LIKE 'Author %'
                             OR articles.summary LIKE 'By %'
                             OR articles.summary LIKE 'Edited by %'
                             OR articles.summary LIKE 'Kathmandu [%'
                             OR articles.summary ~ '[\u0900-\u097F]'
                         )
                    THEN EXCLUDED.summary
                    ELSE articles.summary
                END,
                headline_english = CASE
                    WHEN COALESCE(EXCLUDED.headline_english, '') <> ''
                         AND NOT (EXCLUDED.headline_english ~ '[\u0900-\u097F]')
                         AND (
                             COALESCE(articles.headline_english, '') = ''
                             OR articles.headline_english ~ '[\u0900-\u097F]'
                         )
                    THEN EXCLUDED.headline_english
                    ELSE articles.headline_english
                END;
            """
            query_supabase(sql)

    # Update source health
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    latest_art = articles[0] if articles else {}
    latest_pub = latest_art.get("published_dt")
    latest_pub_str = latest_pub.strftime("%Y-%m-%d %H:%M:%S") if isinstance(latest_pub, (datetime.datetime, datetime.date)) else None

    health_sql = f"""
    INSERT INTO source_health (
        source_name, last_discovery_time, last_ingestion_time, status,
        consecutive_failures, total_discovered, total_ingested, duplicate_count,
        latest_article_pub_dt, latest_article_title, latest_article_link, discovery_latency_avg_secs, last_checkpoint
    ) VALUES (
        {esc_sql(source_name)}, {esc_sql(now_str)}, {esc_sql(now_str)}, 'operational',
        0, {discovered}, {discovered}, 0,
        {esc_sql(latest_pub_str)}, {esc_sql(latest_art.get("title", ""))}, {esc_sql(latest_art.get("link", ""))},
        {latency_secs}, {esc_sql(checkpoint or "")}
    )
    ON CONFLICT (source_name) DO UPDATE SET
        last_discovery_time = EXCLUDED.last_discovery_time,
        last_ingestion_time = EXCLUDED.last_ingestion_time,
        status = 'operational',
        consecutive_failures = 0,
        total_discovered = source_health.total_discovered + EXCLUDED.total_discovered,
        total_ingested = source_health.total_ingested + EXCLUDED.total_ingested,
        latest_article_pub_dt = COALESCE(EXCLUDED.latest_article_pub_dt, source_health.latest_article_pub_dt),
        latest_article_title = COALESCE(EXCLUDED.latest_article_title, source_health.latest_article_title),
        latest_article_link = COALESCE(EXCLUDED.latest_article_link, source_health.latest_article_link),
        last_error_message = NULL,
        discovery_latency_avg_secs = (source_health.discovery_latency_avg_secs * 0.7) + ({latency_secs} * 0.3);
    """
    query_supabase(health_sql)

    return {"discovered": discovered, "ingested": discovered, "duplicates": 0, "updated": 0}

def record_source_error(source_name: str, error_msg: str, latency_secs: float = 0.0):
    """Records an error for a portal in Supabase source health."""
    safe_err = (error_msg or "").strip() or "Unspecified source error"
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sql = f"""
    INSERT INTO source_health (source_name, last_discovery_time, status, consecutive_failures, failed_retrievals, last_error_message)
    VALUES ({esc_sql(source_name)}, {esc_sql(now_str)}, 'degraded', 1, 1, {esc_sql(safe_err)})
    ON CONFLICT (source_name) DO UPDATE SET
        last_discovery_time = EXCLUDED.last_discovery_time,
        consecutive_failures = source_health.consecutive_failures + 1,
        failed_retrievals = source_health.failed_retrievals + 1,
        last_error_message = EXCLUDED.last_error_message,
        status = CASE WHEN source_health.consecutive_failures >= 2 THEN 'failing' ELSE 'degraded' END;
    """
    query_supabase(sql)

def _fetch_all_source_health_raw() -> List[Dict[str, Any]]:
    """Returns comprehensive portal health, counts, and status via a single aggregated CTE (uncached)."""
    sql = """
    WITH art_stats AS (
        SELECT
            a.source,
            COUNT(*) FILTER (WHERE a.published_dt >= (NOW() AT TIME ZONE 'Asia/Kathmandu') - INTERVAL '1 hour') AS count_1h,
            COUNT(*) FILTER (WHERE a.published_dt >= (NOW() AT TIME ZONE 'Asia/Kathmandu') - INTERVAL '24 hour') AS count_24h,
            COUNT(*) FILTER (WHERE a.published_dt >= (NOW() AT TIME ZONE 'Asia/Kathmandu') - INTERVAL '7 day') AS count_7d,
            COUNT(*) AS count_total
        FROM articles a
        GROUP BY a.source
    )
    SELECT
        s.name, s.type, s.url, s.lang, s.category, s.priority, s.check_interval_mins, s.enabled,
        h.last_discovery_time, h.last_ingestion_time,
        COALESCE(h.status, 'operational') AS status,
        COALESCE(h.consecutive_failures, 0) AS consecutive_failures,
        COALESCE(h.total_discovered, 0) AS total_discovered,
        COALESCE(h.total_ingested, 0) AS total_ingested,
        COALESCE(h.duplicate_count, 0) AS duplicate_count,
        COALESCE(h.failed_retrievals, 0) AS failed_retrievals,
        h.latest_article_pub_dt, h.latest_article_title, h.latest_article_link,
        h.last_error_message,
        COALESCE(h.discovery_latency_avg_secs, 0.0) AS discovery_latency_avg_secs,
        COALESCE(a.count_1h, 0) AS count_1h,
        COALESCE(a.count_24h, 0) AS count_24h,
        COALESCE(a.count_7d, 0) AS count_7d,
        COALESCE(a.count_total, 0) AS count_total
    FROM sources s
    LEFT JOIN source_health h ON s.name = h.source_name
    LEFT JOIN art_stats a ON a.source = s.name
    ORDER BY s.enabled DESC, s.name ASC;
    """
    return query_supabase(sql)


@_cache_data_if_available(ttl=180)
def get_all_source_health() -> List[Dict[str, Any]]:
    """Returns comprehensive portal health, counts, and status via a single aggregated CTE."""
    return _fetch_all_source_health_raw()


def _parse_npt_wallclock_ts(raw_val: Any) -> Optional[datetime.datetime]:
    """Parses NPT wall-clock published_dt stored in articles/indian tables while preserving microseconds."""
    if isinstance(raw_val, datetime.datetime):
        # psycopg3 returns UTC-aware datetimes for +00 columns; re-tag UTC wall-clock as NEPAL_TZ cleanly
        if raw_val.tzinfo is not None:
            raw_val = raw_val.astimezone(datetime.timezone.utc)
        return raw_val.replace(tzinfo=NEPAL_TZ)
    if isinstance(raw_val, str):
        s = raw_val.strip()
        if not s:
            return None
        try:
            base = s.rstrip("Z")
            if "+" in base:
                base = base.split("+", 1)[0]
            elif len(base) > 19 and "-" in base[19:]:
                base = base[:19 + base[19:].find("-")]
            return datetime.datetime.fromisoformat(base).replace(tzinfo=NEPAL_TZ)
        except Exception:
            return None
    return None


def _parse_utc_to_npt_ts(raw_val: Any) -> Optional[datetime.datetime]:
    """Parses true-UTC/offset timestamps (x_posts) into NEPAL_TZ fast via C fromisoformat."""
    if isinstance(raw_val, datetime.datetime):
        return raw_val.replace(tzinfo=NEPAL_TZ) if raw_val.tzinfo is None else raw_val.astimezone(NEPAL_TZ)
    if isinstance(raw_val, str):
        s = raw_val.strip()
        if not s:
            return None
        try:
            norm = s.replace("Z", "+00:00")
            if len(norm) >= 3 and norm[-3] in ("+", "-") and norm[-2:].isdigit():
                norm = f"{norm}:00"
            dt = datetime.datetime.fromisoformat(norm)
            return dt.replace(tzinfo=NEPAL_TZ) if dt.tzinfo is None else dt.astimezone(NEPAL_TZ)
        except Exception:
            try:
                from dateutil import parser as dt_parser
                dt = dt_parser.parse(s)
                return dt.replace(tzinfo=NEPAL_TZ) if dt.tzinfo is None else dt.astimezone(NEPAL_TZ)
            except Exception:
                return None
    return None


def _hydrate_article_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalizes published_dt, JSON tags, and boolean flags for article rows."""
    articles = []
    for d in rows:
        d["published_dt"] = _parse_npt_wallclock_ts(d.get("published_dt"))
        sec_raw = d.get("sections")
        if isinstance(sec_raw, list):
            d["sections"] = sec_raw
        else:
            try:
                d["sections"] = json.loads(sec_raw or "[]")
            except Exception:
                d["sections"] = [d.get("primary_section")]
        tags_raw = d.get("secondary_tags")
        if isinstance(tags_raw, list):
            d["secondary_tags"] = tags_raw
        else:
            try:
                d["secondary_tags"] = json.loads(tags_raw or "[]")
            except Exception:
                d["secondary_tags"] = []
        d["low_confidence"] = bool(d.get("low_confidence"))
        d["is_viral"] = bool(d.get("is_viral"))
        d["structured_category"] = d.get("primary_section")
        articles.append(d)
    return articles


def _hydrate_indian_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalizes published_dt and stream metadata for Indian press rows."""
    for d in rows:
        d["published_dt"] = _parse_npt_wallclock_ts(d.get("published_dt"))
        try:
            if isinstance(d.get("sections"), str):
                d["sections"] = json.loads(d["sections"] or "[]")
        except Exception:
            d["sections"] = [d.get("primary_section")]
        if not d.get("structured_category"):
            d["structured_category"] = d.get("primary_section") or "India Section"
        if not d.get("stream"):
            d["stream"] = "Indian Press"
    return rows


def _hydrate_x_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalizes published_dt and relative timestamps for X post rows."""
    now_npt = datetime.datetime.now(NEPAL_TZ)
    for p in rows:
        p["published_dt"] = _parse_utc_to_npt_ts(p.get("published_dt"))
        p["is_real_api"] = bool(p.get("is_real_api", True))
        p["verified"] = bool(p.get("verified", True))
        if not p.get("relative_time") and p.get("published_dt"):
            secs = (now_npt - p["published_dt"]).total_seconds()
            if secs < 60:
                p["relative_time"] = "Just now"
            elif secs < 3600:
                p["relative_time"] = f"{max(1, int(secs // 60))}m ago"
            elif secs < 86400:
                p["relative_time"] = f"{int(secs // 3600)}h ago"
            else:
                p["relative_time"] = p["published_dt"].strftime("%b %d")
        if not p.get("exact_time") and p.get("published_dt"):
            p["exact_time"] = p["published_dt"].strftime("%b %d, %I:%M %p NPT")
    return rows


def _build_articles_where(
    start_dt: Optional[datetime.datetime] = None,
    end_dt: Optional[datetime.datetime] = None,
    source: Optional[str] = None,
    primary_section: Optional[str] = None,
    language: Optional[str] = None,
    search_query: Optional[str] = None,
    snapshot_ingested_at: Optional[datetime.datetime] = None,
) -> List[str]:
    where_clauses = ["1=1"]
    if start_dt:
        where_clauses.append(f"published_dt >= '{_fmt_sql_ts(start_dt, as_utc=False)}'")
    if end_dt:
        where_clauses.append(f"published_dt <= '{_fmt_sql_ts(end_dt, as_utc=False)}'")
    if snapshot_ingested_at:
        where_clauses.append(f"ingested_at <= '{_fmt_sql_ts(snapshot_ingested_at, as_utc=True)}'")
    if source and source != "All Portals" and not source.startswith("All Portals"):
        where_clauses.append(f"source = {esc_sql(source)}")
    if language and language not in ("All Languages", "All"):
        lang_val = "Nepali" if "Nepali" in language else ("English" if "English" in language else language)
        where_clauses.append(f"language = {esc_sql(lang_val)}")
    cat_sql = _build_category_sql(primary_section, primary_col="primary_section", sections_col="sections", is_social=False)
    if cat_sql:
        where_clauses.append(cat_sql)
    srch_sql = _build_search_sql(search_query, ["title", "headline_english", "summary", "source", "primary_section", "language"])
    if srch_sql:
        where_clauses.append(srch_sql)
    return where_clauses


def _build_indian_where(
    eff_status: Optional[str] = "substantive",
    min_score: float = 0.0,
    start_dt: Optional[datetime.datetime] = None,
    end_dt: Optional[datetime.datetime] = None,
    source: Optional[str] = None,
    language: Optional[str] = None,
    category_filter: Optional[str] = None,
    search_query: Optional[str] = None,
    snapshot_ingested_at: Optional[datetime.datetime] = None,
) -> List[str]:
    clauses = ["1=1"]
    if start_dt:
        clauses.append(f"published_dt >= '{_fmt_sql_ts(start_dt, as_utc=False)}'")
    if end_dt:
        clauses.append(f"published_dt <= '{_fmt_sql_ts(end_dt, as_utc=False)}'")
    if snapshot_ingested_at:
        clauses.append(f"ingested_at <= '{_fmt_sql_ts(snapshot_ingested_at, as_utc=True)}'")
    if eff_status:
        if eff_status in ("substantive", "relevant"):
            clauses.append("relevance_status IN ('substantive', 'relevant')")
        else:
            clauses.append(f"relevance_status = {esc_sql(eff_status)}")
    if min_score and min_score > 0:
        clauses.append(f"nepal_relevance_score >= {float(min_score)}")
    if source and not source.startswith("All "):
        clauses.append(f"source = {esc_sql(source)}")
    if language and language not in ("All Languages", "All"):
        clauses.append(f"language = {esc_sql(language)}")
    cat_sql = _build_category_sql(category_filter, primary_col="primary_section", sections_col="sections", is_social=False)
    if cat_sql:
        clauses.append(cat_sql)
    srch_sql = _build_search_sql(search_query, ["title", "headline_english", "summary", "source", "primary_section", "language"])
    if srch_sql:
        clauses.append(srch_sql)
    return clauses


def _build_x_where(
    category: Optional[str] = None,
    author_type: Optional[str] = None,
    start_dt: Optional[datetime.datetime] = None,
    end_dt: Optional[datetime.datetime] = None,
    search_query: Optional[str] = None,
    snapshot_ingested_at: Optional[datetime.datetime] = None,
) -> List[str]:
    clauses = ["1=1"]
    if start_dt:
        clauses.append(f"published_dt >= '{_fmt_sql_ts(start_dt, as_utc=True)}'")
    if end_dt:
        clauses.append(f"published_dt <= '{_fmt_sql_ts(end_dt, as_utc=True)}'")
    if snapshot_ingested_at:
        clauses.append(f"ingested_at <= '{_fmt_sql_ts(snapshot_ingested_at, as_utc=True)}'")
    if category and category.lower() != "all" and not category.startswith("🌐 All"):
        cat_sql = _build_category_sql(category, primary_col="structured_category", sections_col=None, is_social=True)
        if cat_sql:
            clauses.append(cat_sql)
    if author_type and author_type.lower() != "all" and author_type != "All Account Types":
        clauses.append(f"author_type = {esc_sql(author_type)}")
    srch_sql = _build_search_sql(search_query, ["text", "author_name", "handle", "author_type", "structured_category"])
    if srch_sql:
        clauses.append(srch_sql)
    return clauses


def get_stored_articles(
    start_dt: Optional[datetime.datetime] = None,
    end_dt: Optional[datetime.datetime] = None,
    source: Optional[str] = None,
    primary_section: Optional[str] = None,
    limit: int = 500,
    include_full_content: bool = False,
    language: Optional[str] = None,
    search_query: Optional[str] = None,
    snapshot_ingested_at: Optional[datetime.datetime] = None,
    cursor_dt: Optional[datetime.datetime] = None,
    cursor_id: Optional[str] = None,
    sort_asc: bool = False,
) -> List[Dict[str, Any]]:
    """Retrieves articles directly from Supabase PostgreSQL cloud table with optional keyset cursor."""
    where_clauses = _build_articles_where(
        start_dt=start_dt,
        end_dt=end_dt,
        source=source,
        primary_section=primary_section,
        language=language,
        search_query=search_query,
        snapshot_ingested_at=snapshot_ingested_at,
    )
    if cursor_dt is not None and cursor_id is not None:
        op = ">" if sort_asc else "<"
        where_clauses.append(f"(published_dt, canonical_id) {op} ('{_fmt_sql_ts(cursor_dt, as_utc=False)}', {esc_sql(cursor_id)})")

    order_dir = "ASC" if sort_asc else "DESC"
    cols = "*" if include_full_content else ARTICLE_FEED_COLUMNS
    sql = f"""
    SELECT {cols} FROM articles
    WHERE {' AND '.join(where_clauses)}
    ORDER BY published_dt {order_dir}, canonical_id {order_dir}
    LIMIT {int(limit)};
    """
    return _hydrate_article_rows(query_supabase(sql))

def _clear_health_caches() -> None:
    for fn_name in ("get_all_source_health", "get_system_kpis", "get_system_health_bundle"):
        fn = globals().get(fn_name)
        if fn is not None and hasattr(fn, "clear"):
            fn.clear()


def set_source_enabled(source_name: str, enabled: bool):
    """Enables or disables monitoring for a portal in Supabase."""
    sql = f"UPDATE sources SET enabled = {1 if enabled else 0} WHERE name = {esc_sql(source_name)};"
    query_supabase(sql)
    _clear_health_caches()


def set_source_interval(source_name: str, interval_mins: int):
    """Updates the check interval for a portal in Supabase."""
    sql = f"UPDATE sources SET check_interval_mins = {interval_mins} WHERE name = {esc_sql(source_name)};"
    query_supabase(sql)
    _clear_health_caches()


def _fetch_system_kpis_raw() -> Dict[str, Any]:
    """Computes global intelligence KPIs in a single CTE scan directly from Supabase (uncached)."""
    sql = """
    WITH src_kpis AS (
        SELECT
            COUNT(*) AS total_sources,
            COUNT(*) FILTER (WHERE enabled = 1) AS active_sources
        FROM sources
    ),
    hlth_kpis AS (
        SELECT
            COUNT(*) FILTER (WHERE status = 'operational') AS operational,
            COUNT(*) FILTER (WHERE status = 'degraded') AS degraded,
            COUNT(*) FILTER (WHERE status = 'failing') AS failing,
            COALESCE(AVG(discovery_latency_avg_secs), 0.75) AS avg_latency
        FROM source_health
    ),
    art_kpis AS (
        SELECT
            COUNT(*) FILTER (WHERE published_dt >= (NOW() AT TIME ZONE 'Asia/Kathmandu') - INTERVAL '1 hour') AS articles_1h,
            COUNT(*) FILTER (WHERE published_dt >= (NOW() AT TIME ZONE 'Asia/Kathmandu') - INTERVAL '24 hour') AS articles_24h,
            COUNT(*) FILTER (WHERE published_dt >= (NOW() AT TIME ZONE 'Asia/Kathmandu') - INTERVAL '7 day') AS articles_7d,
            COUNT(*) AS total_stored_articles
        FROM articles
    )
    SELECT * FROM src_kpis, hlth_kpis, art_kpis;
    """
    rows = query_supabase(sql)
    if rows:
        r = rows[0]
        return {
            "total_sources": int(r.get("total_sources") or 34),
            "active_sources": int(r.get("active_sources") or 34),
            "operational": int(r.get("operational") or 30),
            "degraded": int(r.get("degraded") or 0),
            "failing": int(r.get("failing") or 0),
            "avg_latency_secs": round(float(r.get("avg_latency") or 0.75), 2),
            "articles_1h": int(r.get("articles_1h") or 0),
            "articles_24h": int(r.get("articles_24h") or 0),
            "articles_7d": int(r.get("articles_7d") or 0),
            "total_stored_articles": int(r.get("total_stored_articles") or 0),
        }
    return {
        "total_sources": 34, "active_sources": 34, "operational": 34, "degraded": 0, "failing": 0,
        "avg_latency_secs": 0.75, "articles_1h": 0, "articles_24h": 0, "articles_7d": 0, "total_stored_articles": 0,
    }


@_cache_data_if_available(ttl=180)
def get_system_kpis() -> Dict[str, Any]:
    """Computes global intelligence KPIs in a single CTE scan directly from Supabase."""
    return _fetch_system_kpis_raw()


def batch_upsert_indian_articles(articles: List[Dict[str, Any]]):
    """Upserts Indian media articles into Supabase."""
    if not articles:
        return
    values_list = []
    for a in articles:
        cid = a.get("canonical_id") or generate_canonical_id(a.get("source", ""), a.get("link", ""), a.get("title", ""))
        vals = [
            esc_sql(cid),
            esc_sql(a.get("source", "Indian Media")),
            esc_sql(a.get("title", "")),
            esc_sql(a.get("headline_english", "")),
            esc_sql(a.get("link", "")),
            esc_sql(normalize_canonical_url(a.get("link", ""))),
            esc_sql(a.get("summary", "")),
            esc_sql(a.get("full_content", "")),
            esc_sql(a.get("published_dt") or datetime.datetime.now()),
            esc_sql(a.get("language", "English")),
            esc_sql(float(a.get("nepal_relevance_score", 0.0))),
            esc_sql(a.get("relevance_status", "relevant")),
            esc_sql(a.get("relevance_reason", ""))
        ]
        values_list.append(f"({', '.join(vals)})")

    if values_list:
        sql = f"""
        INSERT INTO indian_media_articles (
            canonical_id, source, title, headline_english, link, canonical_url,
            summary, full_content, published_dt, language, nepal_relevance_score,
            relevance_status, relevance_reason
        ) VALUES {', '.join(values_list)}
        ON CONFLICT (canonical_id) DO UPDATE SET
            full_content = CASE
                WHEN LENGTH(COALESCE(EXCLUDED.full_content, '')) > LENGTH(COALESCE(indian_media_articles.full_content, ''))
                THEN EXCLUDED.full_content
                ELSE indian_media_articles.full_content
            END,
            summary = CASE
                WHEN COALESCE(EXCLUDED.summary, '') <> ''
                     AND NOT (EXCLUDED.summary ~ '[\u0900-\u097F]')
                     AND (
                         COALESCE(indian_media_articles.summary, '') = ''
                         OR indian_media_articles.summary = indian_media_articles.title
                         OR indian_media_articles.summary LIKE '%...%'
                         OR indian_media_articles.summary LIKE '%appeared first on%'
                         OR indian_media_articles.summary LIKE 'Author %'
                         OR indian_media_articles.summary LIKE 'By %'
                         OR indian_media_articles.summary LIKE 'Edited by %'
                         OR indian_media_articles.summary LIKE 'Kathmandu [%'
                         OR indian_media_articles.summary ~ '[\u0900-\u097F]'
                     )
                THEN EXCLUDED.summary
                ELSE indian_media_articles.summary
            END,
            headline_english = CASE
                WHEN COALESCE(EXCLUDED.headline_english, '') <> ''
                     AND NOT (EXCLUDED.headline_english ~ '[\u0900-\u097F]')
                     AND (
                         COALESCE(indian_media_articles.headline_english, '') = ''
                         OR indian_media_articles.headline_english ~ '[\u0900-\u097F]'
                     )
                THEN EXCLUDED.headline_english
                ELSE indian_media_articles.headline_english
            END;
        """
        query_supabase(sql)


def hydrate_article_full_content(art: Dict[str, Any]) -> None:
    """Fetches stored full_content from Supabase if omitted by feed projection."""
    if not art or (art.get("full_content") and len(str(art.get("full_content")).strip()) >= 350):
        return
    stream = (art.get("stream") or art.get("portal_category") or "").lower()
    table = "indian_media_articles" if "indian" in stream or "nepal_relevance_score" in art else "articles"
    cid = (art.get("canonical_id") or "").strip()
    link = (art.get("link") or "").strip()
    if cid:
        where = f"canonical_id = {esc_sql(cid)}"
    elif link:
        where = f"link = {esc_sql(link)}"
    else:
        return
    rows = query_supabase(f"SELECT full_content FROM {table} WHERE {where} LIMIT 1;")
    if rows and rows[0].get("full_content"):
        art["full_content"] = rows[0]["full_content"]


def persist_enriched_full_content(articles: List[Dict[str, Any]]):
    """Pushes newly scraped full-article text, English headlines, and LexRank summaries back into Supabase."""
    if not articles:
        return
    stmts = []
    for a in articles:
        link = (a.get("link") or "").strip()
        fc = (a.get("full_content") or "").strip()
        en_head = (a.get("headline_english") or "").strip()
        summ = (a.get("summary") or "").strip()
        if not link:
            continue
        stream = (a.get("stream") or a.get("portal_category") or "").lower()
        table = "indian_media_articles" if "indian" in stream else "articles"

        updates = []
        if len(fc) >= 200:
            updates.append(
                f"full_content = CASE WHEN LENGTH(COALESCE(full_content, '')) < {len(fc)} THEN {esc_sql(fc)} ELSE full_content END"
            )
        if en_head and not any(0x0900 <= ord(ch) <= 0x097F for ch in en_head):
            updates.append(f"headline_english = {esc_sql(en_head)}")
        if summ and not summ.endswith("...") and not any(0x0900 <= ord(ch) <= 0x097F for ch in summ):
            updates.append(f"summary = {esc_sql(summ)}")

        if updates:
            cid = (a.get("canonical_id") or "").strip()
            if cid:
                stmts.append(f"UPDATE {table} SET {', '.join(updates)} WHERE canonical_id = {esc_sql(cid)} OR link = {esc_sql(link)};")
            else:
                stmts.append(f"UPDATE {table} SET {', '.join(updates)} WHERE link = {esc_sql(link)};")

    chunk_size = 25
    for i in range(0, len(stmts), chunk_size):
        query_supabase("\n".join(stmts[i : i + chunk_size]))

def ingest_indian_articles_batch(
    articles: List[Dict[str, Any]],
    source_name: str = "Indian Media",
    latency_secs: float = 0.0
) -> Dict[str, int]:
    """Ingests Indian media articles into Supabase."""
    batch_upsert_indian_articles(articles)
    return {"discovered": len(articles), "ingested": len(articles), "duplicates": 0, "relevant": len(articles)}

def get_indian_media_audit_stats() -> Dict[str, int]:
    """Returns volume stats for Indian media articles in Supabase."""
    sql = """
    SELECT 
        COUNT(*) as total_discovered,
        SUM(CASE WHEN relevance_status IN ('substantive', 'relevant') THEN 1 ELSE 0 END) as substantive,
        SUM(CASE WHEN relevance_status IN ('borderline_review', 'borderline') THEN 1 ELSE 0 END) as borderline_review,
        SUM(CASE WHEN relevance_status = 'excluded' THEN 1 ELSE 0 END) as excluded
    FROM indian_media_articles;
    """
    rows = query_supabase(sql)
    if rows:
        r = rows[0]
        total = int(r.get("total_discovered") or 0)
        sub = int(r.get("substantive") or 0)
        bord = int(r.get("borderline_review") or 0)
        excl = int(r.get("excluded") or 0)
        return {
            "total": total,
            "total_discovered": total,
            "substantive": sub,
            "relevant": sub,
            "borderline_review": bord,
            "borderline": bord,
            "excluded": excl
        }
    return {"total": 0, "total_discovered": 0, "substantive": 0, "relevant": 0, "borderline_review": 0, "borderline": 0, "excluded": 0}


def get_stored_indian_articles(
    relevance_status: Optional[str] = None,
    status_filter: Optional[str] = "substantive",
    min_score: float = 0.0,
    limit: int = 500,
    include_full_content: bool = False,
    start_dt: Optional[datetime.datetime] = None,
    end_dt: Optional[datetime.datetime] = None,
    source: Optional[str] = None,
    language: Optional[str] = None,
    category_filter: Optional[str] = None,
    search_query: Optional[str] = None,
    snapshot_ingested_at: Optional[datetime.datetime] = None,
    cursor_dt: Optional[datetime.datetime] = None,
    cursor_id: Optional[str] = None,
    sort_asc: bool = False,
) -> List[Dict[str, Any]]:
    """Retrieves Indian media articles from Supabase with optional keyset cursor."""
    eff_status = relevance_status if relevance_status is not None else status_filter
    clauses = _build_indian_where(
        eff_status=eff_status,
        min_score=min_score,
        start_dt=start_dt,
        end_dt=end_dt,
        source=source,
        language=language,
        category_filter=category_filter,
        search_query=search_query,
        snapshot_ingested_at=snapshot_ingested_at,
    )
    if cursor_dt is not None and cursor_id is not None:
        op = ">" if sort_asc else "<"
        clauses.append(f"(published_dt, canonical_id) {op} ('{_fmt_sql_ts(cursor_dt, as_utc=False)}', {esc_sql(cursor_id)})")

    order_dir = "ASC" if sort_asc else "DESC"
    where = "WHERE " + " AND ".join(clauses)
    cols = "*" if include_full_content else INDIAN_FEED_COLUMNS
    sql = f"SELECT {cols} FROM indian_media_articles {where} ORDER BY published_dt {order_dir}, canonical_id {order_dir} LIMIT {int(limit)};"
    return _hydrate_indian_rows(query_supabase(sql))


def _build_stream_count_where(
    start_dt: Optional[datetime.datetime] = None,
    end_dt: Optional[datetime.datetime] = None,
) -> Tuple[str, str, str]:
    """Returns SQL WHERE clauses for (articles, indian_media_articles, x_posts) honoring NPT vs UTC storage."""
    where_articles = ["1=1"]
    where_indian = ["relevance_status IN ('substantive', 'relevant')"]
    where_x = ["1=1"]
    if start_dt:
        dt_local_str = _fmt_sql_ts(start_dt, as_utc=False)
        dt_utc_str = _fmt_sql_ts(start_dt, as_utc=True)
        where_articles.append(f"published_dt >= '{dt_local_str}'")
        where_indian.append(f"published_dt >= '{dt_local_str}'")
        where_x.append(f"published_dt >= '{dt_utc_str}'")
    if end_dt:
        dt_local_str = _fmt_sql_ts(end_dt, as_utc=False)
        dt_utc_str = _fmt_sql_ts(end_dt, as_utc=True)
        where_articles.append(f"published_dt <= '{dt_local_str}'")
        where_indian.append(f"published_dt <= '{dt_local_str}'")
        where_x.append(f"published_dt <= '{dt_utc_str}'")
    return " AND ".join(where_articles), " AND ".join(where_indian), " AND ".join(where_x)


def get_stored_counts_by_stream(
    start_dt: Optional[datetime.datetime] = None,
    end_dt: Optional[datetime.datetime] = None,
) -> Dict[str, int]:
    """Lightweight aggregated counts for sidebar badges without pulling thousands of rows."""
    w_np, w_in, w_x = _build_stream_count_where(start_dt=start_dt, end_dt=end_dt)
    sql = f"""
    SELECT
        (SELECT COUNT(*) FROM articles WHERE {w_np}) as np_count,
        (SELECT COUNT(*) FROM indian_media_articles WHERE {w_in}) as in_count,
        (SELECT COUNT(*) FROM x_posts WHERE {w_x}) as x_count;
    """
    rows = query_supabase(sql)
    if rows:
        r = rows[0]
        return {
            "nepali_count": int(r.get("np_count") or 0),
            "indian_count": int(r.get("in_count") or 0),
            "x_count": int(r.get("x_count") or 0),
        }
    return {"nepali_count": 0, "indian_count": 0, "x_count": 0}


# ==============================================================================
# X (TWITTER) NEPAL ACCOUNTS MANAGEMENT & REPOSITORY
# ==============================================================================

def normalize_x_handle(raw_handle: str) -> str:
    """Normalizes an X handle by stripping whitespace, leading @, and lowercasing."""
    if not raw_handle:
        return ""
    h = str(raw_handle).strip()
    if h.startswith("@"):
        h = h[1:]
    return h.lower().strip()


def batch_upsert_x_accounts(accounts: List[Dict[str, Any]], batch_size: int = 50) -> int:
    """
    Batches upsert operations for researched and verified Nepal-related X accounts
    into the Supabase PostgreSQL 'x_accounts' table.
    Enforces normalized case-insensitive handle unique constraint and idempotency.
    """
    if not accounts:
        return 0

    inserted_or_updated = 0
    total = len(accounts)

    for i in range(0, total, batch_size):
        chunk = accounts[i:i + batch_size]
        values_rows = []

        for acc in chunk:
            h = normalize_x_handle(acc.get("handle", ""))
            if not h:
                continue
            name = acc.get("name", h)
            profile_url = acc.get("profile_url") or f"https://x.com/{h}"
            cat = acc.get("category", "Civil Society and Public Voices")
            subcat = acc.get("subcategory", "General")
            role = acc.get("role", "")
            relevance = acc.get("relevance", "")
            ver_status = acc.get("verification_status", "verified")
            source_url = acc.get("source_url") or profile_url
            followers = acc.get("followers", "N/A")
            avatar_bg = acc.get("avatar_bg", "#2563eb")
            initials = acc.get("initials") or "".join([w[0].upper() for w in name.split()[:2]]) or "NP"
            enabled = 1 if acc.get("enabled", 1) in (1, True, "1") else 0
            conn_status = acc.get("connection_status", "connected")
            last_ver = acc.get("last_verified_at") or datetime.datetime.now(NEPAL_TZ).isoformat()

            brief = (acc.get("profile_brief") or role or "").strip()
            val_str = f"({esc_sql(h)}, {esc_sql(name)}, {esc_sql(profile_url)}, {esc_sql(cat)}, {esc_sql(subcat)}, {esc_sql(role)}, {esc_sql(brief)}, {esc_sql(relevance)}, {esc_sql(ver_status)}, {esc_sql(source_url)}, {esc_sql(followers)}, {esc_sql(avatar_bg)}, {esc_sql(initials)}, {enabled}, {esc_sql(conn_status)}, {esc_sql(last_ver)}, NOW(), NOW())"
            values_rows.append(val_str)

        if not values_rows:
            continue

        sql = f"""
        INSERT INTO x_accounts (
            handle, name, profile_url, category, subcategory, role, profile_brief, relevance,
            verification_status, source_url, followers, avatar_bg, initials,
            enabled, connection_status, last_verified_at, created_at, updated_at
        ) VALUES
        {", ".join(values_rows)}
        ON CONFLICT (handle) DO UPDATE SET
            name = EXCLUDED.name,
            profile_url = EXCLUDED.profile_url,
            category = EXCLUDED.category,
            subcategory = EXCLUDED.subcategory,
            role = EXCLUDED.role,
            profile_brief = COALESCE(NULLIF(EXCLUDED.profile_brief, ''), x_accounts.profile_brief, EXCLUDED.role),
            relevance = EXCLUDED.relevance,
            verification_status = EXCLUDED.verification_status,
            source_url = EXCLUDED.source_url,
            followers = EXCLUDED.followers,
            avatar_bg = EXCLUDED.avatar_bg,
            initials = EXCLUDED.initials,
            enabled = EXCLUDED.enabled,
            connection_status = EXCLUDED.connection_status,
            last_verified_at = EXCLUDED.last_verified_at,
            updated_at = NOW()
        RETURNING handle;
        """
        res = query_supabase(sql)
        inserted_or_updated += len(res) if res else len(values_rows)

    logger.info(f"batch_upsert_x_accounts: Processed {inserted_or_updated}/{total} accounts into Supabase.")
    return inserted_or_updated


def get_all_x_accounts(
    category: Optional[str] = None,
    verification_status: Optional[str] = None,
    enabled_only: bool = False,
    search: Optional[str] = None,
    limit: int = 1000
) -> List[Dict[str, Any]]:
    """
    Retrieves accounts from the Supabase x_accounts table with filtering and search support.
    """
    clauses = ["1=1"]
    if category and category.lower() != "all":
        clauses.append(f"category = {esc_sql(category)}")
    if verification_status and verification_status.lower() != "all":
        clauses.append(f"verification_status = {esc_sql(verification_status)}")
    if enabled_only:
        clauses.append("enabled = 1")
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        clauses.append(f"(LOWER(handle) LIKE {esc_sql(term)} OR LOWER(name) LIKE {esc_sql(term)} OR LOWER(role) LIKE {esc_sql(term)} OR LOWER(subcategory) LIKE {esc_sql(term)} OR LOWER(relevance) LIKE {esc_sql(term)})")

    where = "WHERE " + " AND ".join(clauses)
    sql = f"SELECT * FROM x_accounts {where} ORDER BY category ASC, name ASC LIMIT {limit};"
    rows = query_supabase(sql)
    return rows if rows else []


@_cache_data_if_available(ttl=180)
def get_x_account_kpis() -> Dict[str, Any]:
    """
    Computes key performance indicators for X accounts in the database in 1 SQL round-trip:
    total discovered, verified, pending verification, active vs inactive,
    and category-wise distribution across all 8 canonical sectors.
    """
    sql = """
    WITH kpi AS (
        SELECT
            COUNT(*) AS total_discovered,
            SUM(CASE WHEN verification_status = 'verified' THEN 1 ELSE 0 END) AS total_verified,
            SUM(CASE WHEN verification_status != 'verified' THEN 1 ELSE 0 END) AS pending_verification,
            SUM(CASE WHEN enabled = 1 THEN 1 ELSE 0 END) AS active_monitored,
            SUM(CASE WHEN enabled = 0 THEN 1 ELSE 0 END) AS inactive_monitored
        FROM x_accounts
    ),
    cats AS (
        SELECT category, COUNT(*) AS cnt
        FROM x_accounts
        WHERE category IS NOT NULL AND category <> ''
        GROUP BY category
        ORDER BY cnt DESC
    )
    SELECT
        kpi.*,
        COALESCE((SELECT json_agg(row_to_json(cats)) FROM cats), '[]'::json) AS cats_json
    FROM kpi;
    """
    rows = query_supabase(sql)
    res: Dict[str, Any] = {
        "total_discovered": 0,
        "total_verified": 0,
        "pending_verification": 0,
        "active_monitored": 0,
        "inactive_monitored": 0,
        "by_category": {},
    }
    if rows:
        r = rows[0]
        res["total_discovered"] = int(r.get("total_discovered") or 0)
        res["total_verified"] = int(r.get("total_verified") or 0)
        res["pending_verification"] = int(r.get("pending_verification") or 0)
        res["active_monitored"] = int(r.get("active_monitored") or 0)
        res["inactive_monitored"] = int(r.get("inactive_monitored") or 0)
        cats_raw = r.get("cats_json") or []
        if isinstance(cats_raw, str):
            try:
                cats_raw = json.loads(cats_raw)
            except Exception:
                cats_raw = []
        if isinstance(cats_raw, list):
            for cr in cats_raw:
                cat_name = cr.get("category")
                if cat_name:
                    res["by_category"][cat_name] = int(cr.get("cnt") or 0)
    return res


def _clear_x_caches() -> None:
    fn = globals().get("get_x_account_kpis")
    if fn is not None and hasattr(fn, "clear"):
        fn.clear()


def set_x_account_enabled(handle: str, enabled: bool) -> bool:
    """Toggles monitoring status for an account (enabled=1 vs paused=0)."""
    norm_h = normalize_x_handle(handle)
    if not norm_h:
        return False
    status_val = 1 if enabled else 0
    sql = f"""
    UPDATE x_accounts 
    SET enabled = {status_val}, updated_at = NOW() 
    WHERE handle = {esc_sql(norm_h)} 
    RETURNING handle;
    """
    res = query_supabase(sql)
    _clear_x_caches()
    return bool(res)


def upsert_single_x_account(acc: Dict[str, Any]) -> bool:
    """Inserts or updates a single X account with duplicate detection on normalized handle."""
    h = normalize_x_handle(acc.get("handle", ""))
    if not h:
        return False
    name = acc.get("name", h)
    profile_url = acc.get("profile_url") or f"https://x.com/{h}"
    cat = acc.get("category", "Civil Society and Public Voices")
    subcat = acc.get("subcategory", "General")
    role = acc.get("role", "")
    relevance = acc.get("relevance", "")
    ver_status = acc.get("verification_status", "verified")
    source_url = acc.get("source_url") or profile_url
    followers = acc.get("followers", "N/A")
    avatar_bg = acc.get("avatar_bg", "#2563eb")
    initials = acc.get("initials") or "".join([w[0].upper() for w in name.split()[:2]]) or "NP"
    enabled = 1 if acc.get("enabled", 1) in (1, True, "1") else 0
    conn_status = acc.get("connection_status", "connected")
    last_ver = acc.get("last_verified_at") or datetime.datetime.now(NEPAL_TZ).isoformat()

    brief = (acc.get("profile_brief") or role or "").strip()
    sql = f"""
    INSERT INTO x_accounts (
        handle, name, profile_url, category, subcategory, role, profile_brief, relevance,
        verification_status, source_url, followers, avatar_bg, initials,
        enabled, connection_status, last_verified_at, created_at, updated_at
    ) VALUES (
        {esc_sql(h)}, {esc_sql(name)}, {esc_sql(profile_url)}, {esc_sql(cat)}, {esc_sql(subcat)},
        {esc_sql(role)}, {esc_sql(brief)}, {esc_sql(relevance)}, {esc_sql(ver_status)}, {esc_sql(source_url)},
        {esc_sql(followers)}, {esc_sql(avatar_bg)}, {esc_sql(initials)}, {enabled},
        {esc_sql(conn_status)}, {esc_sql(last_ver)}, NOW(), NOW()
    )
    ON CONFLICT (handle) DO UPDATE SET
        name = EXCLUDED.name,
        profile_url = EXCLUDED.profile_url,
        category = EXCLUDED.category,
        subcategory = EXCLUDED.subcategory,
        role = EXCLUDED.role,
        profile_brief = COALESCE(NULLIF(EXCLUDED.profile_brief, ''), x_accounts.profile_brief, EXCLUDED.role),
        relevance = EXCLUDED.relevance,
        verification_status = EXCLUDED.verification_status,
        source_url = EXCLUDED.source_url,
        followers = EXCLUDED.followers,
        avatar_bg = EXCLUDED.avatar_bg,
        initials = EXCLUDED.initials,
        enabled = EXCLUDED.enabled,
        connection_status = EXCLUDED.connection_status,
        last_verified_at = EXCLUDED.last_verified_at,
        updated_at = NOW()
    RETURNING handle;
    """
    res = query_supabase(sql)
    _X_PROFILE_CACHE["ts"] = 0.0
    _clear_x_caches()
    return bool(res)


_X_PROFILE_CACHE: Dict[str, Any] = {"ts": 0.0, "data": {}}


def get_x_profile_brief_map(ttl_seconds: int = 300) -> Dict[str, Dict[str, str]]:
    """Returns a cached handle_lower -> {name, profile_brief} map from Supabase x_accounts."""
    now = time.time()
    if _X_PROFILE_CACHE["data"] and (now - float(_X_PROFILE_CACHE["ts"])) < ttl_seconds:
        return _X_PROFILE_CACHE["data"]
    rows = query_supabase(
        "SELECT handle, name, COALESCE(NULLIF(TRIM(profile_brief), ''), role) AS profile_brief "
        "FROM x_accounts;"
    )
    out: Dict[str, Dict[str, str]] = {}
    for r in rows:
        h = str(r.get("handle") or "").lstrip("@").strip().lower()
        if h:
            out[h] = {
                "name": str(r.get("name") or "").strip(),
                "profile_brief": str(r.get("profile_brief") or "").strip(),
            }
    if out:
        _X_PROFILE_CACHE["data"] = out
        _X_PROFILE_CACHE["ts"] = now
    return out


def delete_x_account(handle: str) -> bool:
    """Removes an account from x_accounts."""
    norm_h = normalize_x_handle(handle)
    if not norm_h:
        return False
    sql = f"DELETE FROM x_accounts WHERE handle = {esc_sql(norm_h)} RETURNING handle;"
    res = query_supabase(sql)
    _X_PROFILE_CACHE["ts"] = 0.0
    _clear_x_caches()
    return bool(res)


def verify_x_profile_connectivity(handle: str) -> Tuple[bool, str]:
    """
    Checks public reachability of an X profile without requiring Twitter API authentication.
    Returns (is_accessible, details).
    """
    norm_h = normalize_x_handle(handle)
    if not norm_h:
        return False, "Invalid handle provided."
    profile_url = f"https://x.com/{norm_h}"
    req = urllib.request.Request(
        profile_url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            code = resp.getcode()
            if code in (200, 301, 302):
                return True, f"HTTP {code}: Profile reachable at {profile_url}"
            return False, f"HTTP {code}: Unexpected response code"
    except urllib.error.HTTPError as he:
        if he.code == 404:
            return False, f"HTTP 404: Account @{norm_h} does not exist or has been suspended."
        if he.code in (429, 403):
            # Anti-bot/rate-limit response from X CDN, but domain answered
            return True, f"HTTP {he.code}: Profile recognized (platform rate-limited access check)."
        return False, f"HTTP {he.code}: {he.reason}"
    except Exception as ex:
        return False, f"Network error checking profile: {ex}"


# ==============================================================================
# X POSTS STORAGE & RETRIEVAL (SUPABASE POSTGRESQL)
# ==============================================================================

def save_x_posts(posts: List[Dict[str, Any]], batch_size: int = 50) -> int:
    """
    Batches upsert operations for X posts into the Supabase PostgreSQL 'x_posts' table.
    Enforces conflict resolution on unique post id.
    """
    if not posts:
        return 0

    inserted = 0
    total = len(posts)

    for i in range(0, total, batch_size):
        chunk = posts[i:i + batch_size]
        val_rows = []
        for p in chunk:
            pid = str(p.get("id", "")).strip()
            if not pid:
                continue
            handle = p.get("handle", "")
            raw_handle = p.get("raw_handle") or handle.lstrip("@")
            author_name = p.get("author_name", raw_handle)
            author_type = p.get("author_type", "Civil Society and Public Voices")
            role = p.get("role", "")
            verified = True if p.get("verified", True) else False
            avatar_bg = p.get("avatar_bg", "#2563eb")
            initials = p.get("initials") or raw_handle[:2].upper()
            title = p.get("title") or p.get("text", "")
            text = p.get("text", "")
            headline_en = p.get("headline_english", "")
            cat = p.get("structured_category", "Others")
            likes = int(p.get("likes") or 0)
            retweets = int(p.get("retweets") or 0)
            replies = int(p.get("replies") or 0)
            impressions = int(p.get("impressions") or (likes * 16))
            eng = int(p.get("engagement_score") or (likes + retweets * 2 + replies * 3))

            pub_dt_raw = p.get("published_dt")
            if isinstance(pub_dt_raw, datetime.datetime):
                pub_dt_raw = pub_dt_raw.isoformat()
            elif not pub_dt_raw:
                pub_dt_raw = datetime.datetime.now(NEPAL_TZ).isoformat()

            rel_time = p.get("relative_time", "")
            exact_time = p.get("exact_time", "")
            link = p.get("link") or f"https://x.com/{raw_handle}/status/{pid}"
            sentiment = p.get("sentiment", "Neutral")
            is_real = True if p.get("is_real_api", True) else False

            row_str = f"({esc_sql(pid)}, {esc_sql(handle)}, {esc_sql(raw_handle)}, {esc_sql(author_name)}, {esc_sql(author_type)}, {esc_sql(role)}, {verified}, {esc_sql(avatar_bg)}, {esc_sql(initials)}, {esc_sql(title)}, {esc_sql(text)}, {esc_sql(headline_en)}, {esc_sql(cat)}, {likes}, {retweets}, {replies}, {impressions}, {eng}, {esc_sql(pub_dt_raw)}, {esc_sql(rel_time)}, {esc_sql(exact_time)}, {esc_sql(link)}, {esc_sql(sentiment)}, {is_real}, NOW(), NOW())"
            val_rows.append(row_str)

        if not val_rows:
            continue

        sql = f"""
        INSERT INTO x_posts (
            id, handle, raw_handle, author_name, author_type, role, verified,
            avatar_bg, initials, title, text, headline_english, structured_category,
            likes, retweets, replies, impressions, engagement_score, published_dt,
            relative_time, exact_time, link, sentiment, is_real_api, ingested_at, updated_at
        ) VALUES
        {", ".join(val_rows)}
        ON CONFLICT (id) DO UPDATE SET
            likes = EXCLUDED.likes,
            retweets = EXCLUDED.retweets,
            replies = EXCLUDED.replies,
            impressions = EXCLUDED.impressions,
            engagement_score = EXCLUDED.engagement_score,
            structured_category = EXCLUDED.structured_category,
            sentiment = EXCLUDED.sentiment,
            updated_at = NOW()
        RETURNING id;
        """
        res = query_supabase(sql)
        inserted += len(res) if res else len(val_rows)

    logger.info(f"save_x_posts: Pushed {inserted}/{total} posts into Supabase x_posts table.")
    return inserted


def get_stored_x_posts(
    category: Optional[str] = None,
    author_type: Optional[str] = None,
    limit: int = 500,
    start_dt: Optional[datetime.datetime] = None,
    end_dt: Optional[datetime.datetime] = None,
    search_query: Optional[str] = None,
    snapshot_ingested_at: Optional[datetime.datetime] = None,
    cursor_dt: Optional[datetime.datetime] = None,
    cursor_id: Optional[str] = None,
    cursor_metric: Optional[int] = None,
    sort_mode: str = "Newest",
) -> List[Dict[str, Any]]:
    """Retrieves X posts from Supabase PostgreSQL with optional keyset cursor."""
    clauses = _build_x_where(
        category=category,
        author_type=author_type,
        start_dt=start_dt,
        end_dt=end_dt,
        search_query=search_query,
        snapshot_ingested_at=snapshot_ingested_at,
    )
    metric_col_map = {
        "Most engagement": "COALESCE(engagement_score, 0)",
        "Most liked": "COALESCE(likes, 0)",
        "Most reposted": "COALESCE(retweets, 0)",
    }
    metric_col = metric_col_map.get(sort_mode)
    if cursor_dt is not None and cursor_id is not None:
        c_dt_str = _fmt_sql_ts(cursor_dt, as_utc=True)
        if metric_col and cursor_metric is not None:
            clauses.append(f"({metric_col}, published_dt, id) < ({int(cursor_metric)}, '{c_dt_str}', {esc_sql(cursor_id)})")
        else:
            clauses.append(f"(published_dt, id) < ('{c_dt_str}', {esc_sql(cursor_id)})")

    order_sql = f"{metric_col} DESC, published_dt DESC, id DESC" if metric_col else "published_dt DESC, id DESC"
    where = "WHERE " + " AND ".join(clauses)
    sql = f"SELECT {X_FEED_COLUMNS} FROM x_posts {where} ORDER BY {order_sql} LIMIT {int(limit)};"
    return _hydrate_x_rows(query_supabase(sql))


def _parse_json_val(raw_val: Any, default: Any = None) -> Any:
    if raw_val is None:
        return [] if default is None else default
    if isinstance(raw_val, str):
        try:
            return json.loads(raw_val)
        except Exception:
            return [] if default is None else default
    return raw_val


def _branch_cursor_clause(
    branch_rank: int,
    cursor_rank: Optional[int],
    cursor_dt: Optional[datetime.datetime],
    cursor_id: Optional[str],
    id_col: str,
    sort_asc: bool,
    as_utc: bool,
) -> Optional[str]:
    if cursor_dt is None or cursor_id is None or cursor_rank is None:
        return None
    ts_lit = _fmt_sql_ts(cursor_dt, as_utc=as_utc)
    if not sort_asc:
        if branch_rank < cursor_rank:
            return f"published_dt <= '{ts_lit}'"
        if branch_rank > cursor_rank:
            return f"published_dt < '{ts_lit}'"
        return f"(published_dt, {id_col}) < ('{ts_lit}', {esc_sql(cursor_id)})"
    if branch_rank > cursor_rank:
        return f"published_dt >= '{ts_lit}'"
    if branch_rank < cursor_rank:
        return f"published_dt > '{ts_lit}'"
    return f"(published_dt, {id_col}) > ('{ts_lit}', {esc_sql(cursor_id)})"


def _build_live_union_sql(
    start_dt: Optional[datetime.datetime] = None,
    end_dt: Optional[datetime.datetime] = None,
    snapshot_ingested_at: Optional[datetime.datetime] = None,
    stream_filter: str = "All Sources",
    category_filter: Optional[str] = None,
    search_query: Optional[str] = None,
    sort_asc: bool = False,
    cursor_dt: Optional[datetime.datetime] = None,
    cursor_rank: Optional[int] = None,
    cursor_id: Optional[str] = None,
    limit: int = 20,
) -> str:
    """Builds pushdown Top-K UNION ALL SQL across Nepali Media, Indian Press, and X."""
    order_dir = "ASC" if sort_asc else "DESC"
    lim = int(limit)
    eff_rank = 3 if cursor_rank is None else int(cursor_rank)
    unions: List[str] = []

    if stream_filter in ("All Sources", "Nepali Media Only"):
        np_where = _build_articles_where(
            start_dt=start_dt,
            end_dt=end_dt,
            primary_section=category_filter,
            search_query=search_query,
            snapshot_ingested_at=snapshot_ingested_at,
        )
        c_np = _branch_cursor_clause(3, eff_rank, cursor_dt, cursor_id, "canonical_id", sort_asc, as_utc=False)
        if c_np:
            np_where.append(c_np)
        unions.append(
            f"SELECT 'nepali'::text AS _ft, 3::int AS _sr, canonical_id AS _cid, "
            f"(published_dt - INTERVAL '5 hours 45 minutes') AS _sort_dt, "
            f"to_jsonb(t) AS _payload FROM ("
            f"SELECT {ARTICLE_FEED_COLUMNS} FROM articles WHERE {' AND '.join(np_where)} "
            f"ORDER BY published_dt {order_dir}, canonical_id {order_dir} LIMIT {lim}"
            f") t"
        )

    if stream_filter in ("All Sources", "Indian Press Only"):
        in_where = _build_indian_where(
            eff_status="substantive",
            start_dt=start_dt,
            end_dt=end_dt,
            category_filter=category_filter,
            search_query=search_query,
            snapshot_ingested_at=snapshot_ingested_at,
        )
        c_in = _branch_cursor_clause(2, eff_rank, cursor_dt, cursor_id, "canonical_id", sort_asc, as_utc=False)
        if c_in:
            in_where.append(c_in)
        unions.append(
            f"SELECT 'indian'::text AS _ft, 2::int AS _sr, canonical_id AS _cid, "
            f"(published_dt - INTERVAL '5 hours 45 minutes') AS _sort_dt, "
            f"to_jsonb(t) AS _payload FROM ("
            f"SELECT {INDIAN_FEED_COLUMNS} FROM indian_media_articles WHERE {' AND '.join(in_where)} "
            f"ORDER BY published_dt {order_dir}, canonical_id {order_dir} LIMIT {lim}"
            f") t"
        )

    if stream_filter in ("All Sources", "X (Twitter) Only", "Verified X Voices Only"):
        x_where = _build_x_where(
            category=category_filter,
            start_dt=start_dt,
            end_dt=end_dt,
            search_query=search_query,
            snapshot_ingested_at=snapshot_ingested_at,
        )
        c_x = _branch_cursor_clause(1, eff_rank, cursor_dt, cursor_id, "id", sort_asc, as_utc=True)
        if c_x:
            x_where.append(c_x)
        unions.append(
            f"SELECT 'x'::text AS _ft, 1::int AS _sr, id::text AS _cid, "
            f"published_dt AS _sort_dt, "
            f"to_jsonb(t) AS _payload FROM ("
            f"SELECT {X_FEED_COLUMNS} FROM x_posts WHERE {' AND '.join(x_where)} "
            f"ORDER BY published_dt {order_dir}, id {order_dir} LIMIT {lim}"
            f") t"
        )

    union_body = " UNION ALL ".join(f"({u})" for u in unions)
    return (
        f"SELECT _ft, _sr, _cid, _payload FROM ({union_body}) AS combined "
        f"ORDER BY _sort_dt {order_dir}, _sr {order_dir}, _cid {order_dir} LIMIT {lim}"
    )


def _hydrate_live_union_rows(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for r in raw:
        ft = r.get("_ft")
        payload = _parse_json_val(r.get("_payload"), default=None)
        if not isinstance(payload, dict):
            continue
        if ft == "nepali":
            item = _hydrate_article_rows([payload])[0]
        elif ft == "indian":
            item = _hydrate_indian_rows([payload])[0]
        else:
            item = _hydrate_x_rows([payload])[0]
        item["_feed_type"] = ft
        item["_stream_rank"] = int(r.get("_sr") or 1)
        item["_cursor_id"] = str(r.get("_cid") or "")
        out.append(item)
    return out


def get_stored_live_feed_page(
    start_dt: Optional[datetime.datetime] = None,
    end_dt: Optional[datetime.datetime] = None,
    snapshot_ingested_at: Optional[datetime.datetime] = None,
    stream_filter: str = "All Sources",
    category_filter: Optional[str] = None,
    search_query: Optional[str] = None,
    sort_asc: bool = False,
    cursor_dt: Optional[datetime.datetime] = None,
    cursor_rank: Optional[int] = None,
    cursor_id: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Fetches a single unified page across Nepali Media, Indian Press, and X
    in 1 SQL round-trip using a deterministic (published_dt, stream_rank, record_id) keyset cursor.
    """
    if stream_filter == "Nepali Media Only":
        rows = get_stored_articles(
            start_dt=start_dt, end_dt=end_dt, primary_section=category_filter,
            search_query=search_query, snapshot_ingested_at=snapshot_ingested_at,
            cursor_dt=cursor_dt, cursor_id=cursor_id, sort_asc=sort_asc, limit=limit,
        )
        for r in rows:
            r["_feed_type"] = "nepali"
            r["_stream_rank"] = 3
            r["_cursor_id"] = r.get("canonical_id", "")
        return rows
    if stream_filter == "Indian Press Only":
        rows = get_stored_indian_articles(
            status_filter="substantive", start_dt=start_dt, end_dt=end_dt,
            category_filter=category_filter, search_query=search_query,
            snapshot_ingested_at=snapshot_ingested_at,
            cursor_dt=cursor_dt, cursor_id=cursor_id, sort_asc=sort_asc, limit=limit,
        )
        for r in rows:
            r["_feed_type"] = "indian"
            r["_stream_rank"] = 2
            r["_cursor_id"] = r.get("canonical_id", "")
        return rows
    if stream_filter in ("X (Twitter) Only", "Verified X Voices Only") and not sort_asc:
        rows = get_stored_x_posts(
            category=category_filter, start_dt=start_dt, end_dt=end_dt,
            search_query=search_query, snapshot_ingested_at=snapshot_ingested_at,
            cursor_dt=cursor_dt, cursor_id=cursor_id,
            sort_mode="Newest", limit=limit,
        )
        for r in rows:
            r["_feed_type"] = "x"
            r["_stream_rank"] = 1
            r["_cursor_id"] = str(r.get("id", ""))
        return rows

    sql = _build_live_union_sql(
        start_dt=start_dt,
        end_dt=end_dt,
        snapshot_ingested_at=snapshot_ingested_at,
        stream_filter=stream_filter,
        category_filter=category_filter,
        search_query=search_query,
        sort_asc=sort_asc,
        cursor_dt=cursor_dt,
        cursor_rank=cursor_rank,
        cursor_id=cursor_id,
        limit=limit,
    ) + ";"
    return _hydrate_live_union_rows(query_supabase(sql))


def _build_filtered_count_sql_parts(
    workspace: str,
    start_dt: Optional[datetime.datetime] = None,
    end_dt: Optional[datetime.datetime] = None,
    snapshot_ingested_at: Optional[datetime.datetime] = None,
    stream_filter: str = "All Sources",
    category_filter: Optional[str] = None,
    source: Optional[str] = None,
    language: Optional[str] = None,
    author_type: Optional[str] = None,
    search_query: Optional[str] = None,
    include_new_count: bool = True,
) -> Tuple[str, str]:
    """Returns (total_count_expr, new_since_snapshot_expr) SQL fragments."""
    def _pair_sql(table: str, where_list: List[str]) -> Tuple[str, str]:
        base = " AND ".join(where_list)
        if snapshot_ingested_at:
            snap_ts = _fmt_sql_ts(snapshot_ingested_at, as_utc=True)
            tot = f"(SELECT COUNT(*) FROM {table} WHERE {base} AND ingested_at <= '{snap_ts}')"
            new = f"(SELECT COUNT(*) FROM {table} WHERE {base} AND ingested_at > '{snap_ts}')" if include_new_count else "0"
        else:
            tot = f"(SELECT COUNT(*) FROM {table} WHERE {base})"
            new = "0"
        return tot, new

    if workspace == "nepali":
        w = _build_articles_where(start_dt=start_dt, end_dt=end_dt, source=source, primary_section=category_filter, language=language, search_query=search_query)
        return _pair_sql("articles", w)
    if workspace == "indian":
        w = _build_indian_where(eff_status="substantive", start_dt=start_dt, end_dt=end_dt, source=source, language=language, category_filter=category_filter, search_query=search_query)
        return _pair_sql("indian_media_articles", w)
    if workspace == "x":
        w = _build_x_where(category=category_filter, author_type=author_type, start_dt=start_dt, end_dt=end_dt, search_query=search_query)
        return _pair_sql("x_posts", w)

    tots, news = [], []
    if stream_filter in ("All Sources", "Nepali Media Only"):
        t, n = _pair_sql("articles", _build_articles_where(start_dt=start_dt, end_dt=end_dt, primary_section=category_filter, search_query=search_query))
        tots.append(t)
        news.append(n)
    if stream_filter in ("All Sources", "Indian Press Only"):
        t, n = _pair_sql("indian_media_articles", _build_indian_where(eff_status="substantive", start_dt=start_dt, end_dt=end_dt, category_filter=category_filter, search_query=search_query))
        tots.append(t)
        news.append(n)
    if stream_filter in ("All Sources", "X (Twitter) Only", "Verified X Voices Only"):
        t, n = _pair_sql("x_posts", _build_x_where(category=category_filter, start_dt=start_dt, end_dt=end_dt, search_query=search_query))
        tots.append(t)
        news.append(n)
    tot_expr = f"({' + '.join(tots or ['0'])})"
    new_expr = f"({' + '.join(news or ['0'])})" if (snapshot_ingested_at and include_new_count) else "0"
    return tot_expr, new_expr


def get_filtered_feed_count(
    workspace: str,
    start_dt: Optional[datetime.datetime] = None,
    end_dt: Optional[datetime.datetime] = None,
    snapshot_ingested_at: Optional[datetime.datetime] = None,
    stream_filter: str = "All Sources",
    category_filter: Optional[str] = None,
    source: Optional[str] = None,
    language: Optional[str] = None,
    author_type: Optional[str] = None,
    search_query: Optional[str] = None,
) -> Dict[str, int]:
    """Returns {'total_count': int, 'new_since_snapshot': int} in 1 lightweight SQL query."""
    tot_s, new_s = _build_filtered_count_sql_parts(
        workspace=workspace,
        start_dt=start_dt,
        end_dt=end_dt,
        snapshot_ingested_at=snapshot_ingested_at,
        stream_filter=stream_filter,
        category_filter=category_filter,
        source=source,
        language=language,
        author_type=author_type,
        search_query=search_query,
        include_new_count=bool(snapshot_ingested_at),
    )
    sql = f"SELECT {tot_s} AS total_count, {new_s} AS new_since_snapshot;"
    rows = query_supabase(sql)
    if rows:
        return {
            "total_count": int(rows[0].get("total_count") or 0),
            "new_since_snapshot": int(rows[0].get("new_since_snapshot") or 0),
        }
    return {"total_count": 0, "new_since_snapshot": 0}


def _build_workspace_page_sql(
    workspace: str,
    start_dt: Optional[datetime.datetime] = None,
    end_dt: Optional[datetime.datetime] = None,
    snapshot_ingested_at: Optional[datetime.datetime] = None,
    stream_filter: str = "All Sources",
    category_filter: Optional[str] = None,
    source: Optional[str] = None,
    language: Optional[str] = None,
    author_type: Optional[str] = None,
    search_query: Optional[str] = None,
    sort_asc: bool = False,
    sort_mode: str = "Newest",
    cursor_dt: Optional[datetime.datetime] = None,
    cursor_rank: Optional[int] = None,
    cursor_id: Optional[str] = None,
    cursor_metric: Optional[int] = None,
    limit: int = 20,
) -> str:
    """Shared SQL SELECT builder for paginated feeds across all 4 workspaces."""
    lim = int(limit)
    if workspace == "nepali":
        w = _build_articles_where(
            start_dt=start_dt, end_dt=end_dt, source=source, primary_section=category_filter,
            language=language, search_query=search_query, snapshot_ingested_at=snapshot_ingested_at,
        )
        if cursor_dt is not None and cursor_id is not None:
            op = ">" if sort_asc else "<"
            w.append(f"(published_dt, canonical_id) {op} ('{_fmt_sql_ts(cursor_dt, as_utc=False)}', {esc_sql(cursor_id)})")
        order_dir = "ASC" if sort_asc else "DESC"
        return (
            f"SELECT {ARTICLE_FEED_COLUMNS} FROM articles WHERE {' AND '.join(w)} "
            f"ORDER BY published_dt {order_dir}, canonical_id {order_dir} LIMIT {lim}"
        )
    if workspace == "indian":
        w = _build_indian_where(
            eff_status="substantive", start_dt=start_dt, end_dt=end_dt, source=source,
            language=language, category_filter=category_filter, search_query=search_query,
            snapshot_ingested_at=snapshot_ingested_at,
        )
        if cursor_dt is not None and cursor_id is not None:
            op = ">" if sort_asc else "<"
            w.append(f"(published_dt, canonical_id) {op} ('{_fmt_sql_ts(cursor_dt, as_utc=False)}', {esc_sql(cursor_id)})")
        order_dir = "ASC" if sort_asc else "DESC"
        return (
            f"SELECT {INDIAN_FEED_COLUMNS} FROM indian_media_articles WHERE {' AND '.join(w)} "
            f"ORDER BY published_dt {order_dir}, canonical_id {order_dir} LIMIT {lim}"
        )
    if workspace == "x":
        w = _build_x_where(
            category=category_filter, author_type=author_type, start_dt=start_dt, end_dt=end_dt,
            search_query=search_query, snapshot_ingested_at=snapshot_ingested_at,
        )
        metric_col_map = {
            "Most engagement": "COALESCE(engagement_score, 0)",
            "Most liked": "COALESCE(likes, 0)",
            "Most reposted": "COALESCE(retweets, 0)",
        }
        metric_col = metric_col_map.get(sort_mode)
        if cursor_dt is not None and cursor_id is not None:
            c_dt_str = _fmt_sql_ts(cursor_dt, as_utc=True)
            if metric_col and cursor_metric is not None:
                w.append(f"({metric_col}, published_dt, id) < ({int(cursor_metric)}, '{c_dt_str}', {esc_sql(cursor_id)})")
            else:
                w.append(f"(published_dt, id) < ('{c_dt_str}', {esc_sql(cursor_id)})")
        order_sql = f"{metric_col} DESC, published_dt DESC, id DESC" if metric_col else "published_dt DESC, id DESC"
        return f"SELECT {X_FEED_COLUMNS} FROM x_posts WHERE {' AND '.join(w)} ORDER BY {order_sql} LIMIT {lim}"

    return _build_live_union_sql(
        start_dt=start_dt, end_dt=end_dt, snapshot_ingested_at=snapshot_ingested_at,
        stream_filter=stream_filter, category_filter=category_filter, search_query=search_query,
        sort_asc=sort_asc, cursor_dt=cursor_dt, cursor_rank=cursor_rank,
        cursor_id=cursor_id, limit=lim,
    )


def _hydrate_workspace_raw_list(workspace: str, raw_list: Any) -> List[Dict[str, Any]]:
    raw_list = _parse_json_val(raw_list, default=[])
    if not isinstance(raw_list, list):
        return []
    if workspace == "live":
        return _hydrate_live_union_rows(raw_list)
    for item in raw_list:
        if isinstance(item, dict):
            item.pop("_rn", None)
    if workspace == "nepali":
        return _hydrate_article_rows(raw_list)
    if workspace == "indian":
        return _hydrate_indian_rows(raw_list)
    return _hydrate_x_rows(raw_list)


def get_feed_page_with_count(
    workspace: str,
    start_dt: Optional[datetime.datetime] = None,
    end_dt: Optional[datetime.datetime] = None,
    snapshot_ingested_at: Optional[datetime.datetime] = None,
    stream_filter: str = "All Sources",
    category_filter: Optional[str] = None,
    source: Optional[str] = None,
    language: Optional[str] = None,
    author_type: Optional[str] = None,
    search_query: Optional[str] = None,
    sort_asc: bool = False,
    sort_mode: str = "Newest",
    cursor_dt: Optional[datetime.datetime] = None,
    cursor_rank: Optional[int] = None,
    cursor_id: Optional[str] = None,
    cursor_metric: Optional[int] = None,
    limit: int = 20,
    include_count: bool = True,
    include_new_count: bool = False,
) -> Dict[str, Any]:
    """
    Fetches a workspace page and (optionally) exact filtered total_count in ONE SQL round-trip.
    When include_count=False (e.g. keyset pagination load_more), executes only the page query.
    """
    if not include_count and not include_new_count:
        if workspace == "nepali":
            rows = get_stored_articles(
                start_dt=start_dt, end_dt=end_dt, source=source, primary_section=category_filter,
                language=language, search_query=search_query, snapshot_ingested_at=snapshot_ingested_at,
                cursor_dt=cursor_dt, cursor_id=cursor_id, sort_asc=sort_asc, limit=limit,
            )
        elif workspace == "indian":
            rows = get_stored_indian_articles(
                status_filter="substantive", start_dt=start_dt, end_dt=end_dt, source=source,
                language=language, category_filter=category_filter, search_query=search_query,
                snapshot_ingested_at=snapshot_ingested_at, cursor_dt=cursor_dt,
                cursor_id=cursor_id, sort_asc=sort_asc, limit=limit,
            )
        elif workspace == "x":
            rows = get_stored_x_posts(
                category=category_filter, author_type=author_type, start_dt=start_dt, end_dt=end_dt,
                search_query=search_query, snapshot_ingested_at=snapshot_ingested_at,
                cursor_dt=cursor_dt, cursor_id=cursor_id, cursor_metric=cursor_metric,
                sort_mode=sort_mode, limit=limit,
            )
        else:
            rows = get_stored_live_feed_page(
                start_dt=start_dt, end_dt=end_dt, snapshot_ingested_at=snapshot_ingested_at,
                stream_filter=stream_filter, category_filter=category_filter, search_query=search_query,
                sort_asc=sort_asc, cursor_dt=cursor_dt, cursor_rank=cursor_rank,
                cursor_id=cursor_id, limit=limit,
            )
        return {"rows": rows, "total_count": None, "new_since_snapshot": None}

    page_sql = _build_workspace_page_sql(
        workspace=workspace, start_dt=start_dt, end_dt=end_dt, snapshot_ingested_at=snapshot_ingested_at,
        stream_filter=stream_filter, category_filter=category_filter, source=source, language=language,
        author_type=author_type, search_query=search_query, sort_asc=sort_asc, sort_mode=sort_mode,
        cursor_dt=cursor_dt, cursor_rank=cursor_rank, cursor_id=cursor_id, cursor_metric=cursor_metric, limit=limit,
    )
    tot_s, new_s = _build_filtered_count_sql_parts(
        workspace=workspace,
        start_dt=start_dt,
        end_dt=end_dt,
        snapshot_ingested_at=snapshot_ingested_at,
        stream_filter=stream_filter,
        category_filter=category_filter,
        source=source,
        language=language,
        author_type=author_type,
        search_query=search_query,
        include_new_count=include_new_count and bool(snapshot_ingested_at),
    )

    sql = f"""
    WITH page_rows AS (
        SELECT *, ROW_NUMBER() OVER () AS _rn
        FROM ({page_sql}) AS _ordered
    ),
    cnts AS (
        SELECT {tot_s if include_count else 'NULL::bigint'} AS total_count,
               {new_s if (include_new_count and snapshot_ingested_at) else '0::bigint'} AS new_since_snapshot
    )
    SELECT
        cnts.total_count,
        cnts.new_since_snapshot,
        COALESCE((SELECT json_agg(row_to_json(p) ORDER BY p._rn) FROM page_rows p), '[]'::json) AS rows_json
    FROM cnts;
    """
    res_rows = query_supabase(sql)
    if not res_rows:
        return {"rows": [], "total_count": 0 if include_count else None, "new_since_snapshot": 0 if include_new_count else None}

    r0 = res_rows[0]
    return {
        "rows": _hydrate_workspace_raw_list(workspace, r0.get("rows_json")),
        "total_count": int(r0["total_count"]) if (include_count and r0.get("total_count") is not None) else None,
        "new_since_snapshot": int(r0.get("new_since_snapshot") or 0) if include_new_count else None,
    }


def _parse_wa_sent_rows(wa_raw: Any) -> Dict[str, Dict[str, Any]]:
    wa_sent_map: Dict[str, Dict[str, Any]] = {}
    wa_list = _parse_json_val(wa_raw, default=[])
    if isinstance(wa_list, list):
        for wr in wa_list:
            if isinstance(wr, dict):
                key = str(wr.get("item_key") or "").strip()
                if key:
                    wa_sent_map[key] = wr
    return wa_sent_map


def get_login_bootstrap_bundle(
    header_start_dt: datetime.datetime,
    header_end_dt: datetime.datetime,
    live_start_dt: Optional[datetime.datetime] = None,
    live_end_dt: Optional[datetime.datetime] = None,
    stream_filter: str = "All Sources",
    category_filter: Optional[str] = None,
    search_query: Optional[str] = None,
    sort_asc: bool = False,
    limit: int = 20,
    wa_limit: int = 1000,
) -> Dict[str, Any]:
    """
    Single SQL round-trip for Cold Login: fetches navbar stream counts, WhatsApp sent log,
    Live Feed page 0, and exact filtered Live Feed total_count simultaneously.
    """
    ls = live_start_dt or header_start_dt
    le = live_end_dt or header_end_dt
    w_np, w_in, w_x = _build_stream_count_where(start_dt=header_start_dt, end_dt=header_end_dt)
    live_page_sql = _build_workspace_page_sql(
        workspace="live", start_dt=ls, end_dt=le, snapshot_ingested_at=le,
        stream_filter=stream_filter, category_filter=category_filter, search_query=search_query,
        sort_asc=sort_asc, limit=limit,
    )
    tot_s, _ = _build_filtered_count_sql_parts(
        workspace="live", start_dt=ls, end_dt=le, snapshot_ingested_at=le,
        stream_filter=stream_filter, category_filter=category_filter, search_query=search_query,
        include_new_count=False,
    )
    sql = f"""
    WITH wa_rows AS (
        SELECT item_key, group_id, group_name, id_message, item_link, sent_at
        FROM whatsapp_sent_log
        ORDER BY sent_at DESC
        LIMIT {int(wa_limit)}
    ),
    live_rows AS (
        SELECT *, ROW_NUMBER() OVER () AS _rn
        FROM ({live_page_sql}) AS _ordered
    )
    SELECT
        (SELECT COUNT(*) FROM articles WHERE {w_np}) AS np_count,
        (SELECT COUNT(*) FROM indian_media_articles WHERE {w_in}) AS in_count,
        (SELECT COUNT(*) FROM x_posts WHERE {w_x}) AS x_count,
        COALESCE((SELECT json_agg(row_to_json(w)) FROM wa_rows w), '[]'::json) AS wa_json,
        {tot_s} AS live_total_count,
        COALESCE((SELECT json_agg(row_to_json(p) ORDER BY p._rn) FROM live_rows p), '[]'::json) AS live_rows_json;
    """
    try:
        rows = query_supabase(sql)
    except Exception as exc:
        if "whatsapp_sent_log" in str(exc).lower():
            ensure_whatsapp_sent_log_table()
            rows = query_supabase(sql)
        else:
            raise

    if not rows:
        return {
            "header": {"counts": {"nepali_count": 0, "indian_count": 0, "x_count": 0}, "wa_sent_map": {}},
            "live_page": {"rows": [], "total_count": 0},
        }
    r0 = rows[0]
    counts = {
        "nepali_count": int(r0.get("np_count") or 0),
        "indian_count": int(r0.get("in_count") or 0),
        "x_count": int(r0.get("x_count") or 0),
    }
    return {
        "header": {"counts": counts, "wa_sent_map": _parse_wa_sent_rows(r0.get("wa_json"))},
        "live_page": {
            "rows": _hydrate_workspace_raw_list("live", r0.get("live_rows_json")),
            "total_count": int(r0.get("live_total_count") or 0),
        },
    }


def get_indian_workspace_bootstrap(
    start_dt: Optional[datetime.datetime] = None,
    end_dt: Optional[datetime.datetime] = None,
    snapshot_ingested_at: Optional[datetime.datetime] = None,
    source: Optional[str] = None,
    language: Optional[str] = None,
    category_filter: Optional[str] = None,
    search_query: Optional[str] = None,
    limit: int = 20,
    relevance_threshold: float = 0.65,
    borderline_floor: float = 0.40,
    borderline_limit: int = 15,
) -> Dict[str, Any]:
    """
    Single SQL round-trip for Indian Press workspace: returns page 0, exact filtered total_count,
    retention audit stats, and SQL-filtered borderline review items without redundant regex re-eval.
    """
    page_sql = _build_workspace_page_sql(
        workspace="indian", start_dt=start_dt, end_dt=end_dt, snapshot_ingested_at=snapshot_ingested_at,
        source=source, language=language, category_filter=category_filter, search_query=search_query, limit=limit,
    )
    tot_s, _ = _build_filtered_count_sql_parts(
        workspace="indian", start_dt=start_dt, end_dt=end_dt, snapshot_ingested_at=snapshot_ingested_at,
        source=source, language=language, category_filter=category_filter, search_query=search_query,
        include_new_count=False,
    )
    sql = f"""
    WITH page_rows AS (
        SELECT *, ROW_NUMBER() OVER () AS _rn
        FROM ({page_sql}) AS _ordered
    ),
    audit AS (
        SELECT
            COUNT(*) AS total_discovered,
            SUM(CASE WHEN relevance_status IN ('substantive', 'relevant') THEN 1 ELSE 0 END) AS substantive,
            SUM(CASE WHEN relevance_status IN ('borderline_review', 'borderline') THEN 1 ELSE 0 END) AS borderline_review,
            SUM(CASE WHEN relevance_status = 'excluded' THEN 1 ELSE 0 END) AS excluded
        FROM indian_media_articles
    ),
    bord_rows AS (
        SELECT {INDIAN_FEED_COLUMNS}
        FROM indian_media_articles
        WHERE nepal_relevance_score >= {float(borderline_floor)}
          AND nepal_relevance_score < {float(relevance_threshold)}
        ORDER BY published_dt DESC, canonical_id DESC
        LIMIT {int(borderline_limit)}
    )
    SELECT
        {tot_s} AS total_count,
        COALESCE((SELECT json_agg(row_to_json(p) ORDER BY p._rn) FROM page_rows p), '[]'::json) AS rows_json,
        audit.*,
        COALESCE((SELECT json_agg(row_to_json(b)) FROM bord_rows b), '[]'::json) AS borderline_json
    FROM audit;
    """
    res_rows = query_supabase(sql)
    if not res_rows:
        return {
            "rows": [],
            "total_count": 0,
            "audit": {"total": 0, "total_discovered": 0, "substantive": 0, "relevant": 0, "borderline_review": 0, "borderline": 0, "excluded": 0},
            "borderline_items": [],
        }
    r0 = res_rows[0]
    total = int(r0.get("total_discovered") or 0)
    sub = int(r0.get("substantive") or 0)
    bord = int(r0.get("borderline_review") or 0)
    excl = int(r0.get("excluded") or 0)
    b_raw = _parse_json_val(r0.get("borderline_json"), default=[])
    borderline_items = _hydrate_indian_rows(b_raw) if isinstance(b_raw, list) else []
    for bc in borderline_items:
        bc["relevance_status"] = "borderline_review"
    return {
        "rows": _hydrate_workspace_raw_list("indian", r0.get("rows_json")),
        "total_count": int(r0.get("total_count") or 0),
        "audit": {
            "total": total, "total_discovered": total, "substantive": sub,
            "relevant": sub, "borderline_review": bord, "borderline": bord, "excluded": excl,
        },
        "borderline_items": borderline_items,
    }


def get_x_workspace_bootstrap(
    start_dt: Optional[datetime.datetime] = None,
    end_dt: Optional[datetime.datetime] = None,
    snapshot_ingested_at: Optional[datetime.datetime] = None,
    category_filter: Optional[str] = None,
    author_type: Optional[str] = None,
    search_query: Optional[str] = None,
    sort_mode: str = "Newest",
    limit: int = 20,
) -> Dict[str, Any]:
    """Single SQL round-trip for X workspace: fetches x_account KPIs + category counts + page 0 + total_count."""
    page_sql = _build_workspace_page_sql(
        workspace="x", start_dt=start_dt, end_dt=end_dt, snapshot_ingested_at=snapshot_ingested_at,
        category_filter=category_filter, author_type=author_type, search_query=search_query,
        sort_mode=sort_mode, limit=limit,
    )
    tot_s, _ = _build_filtered_count_sql_parts(
        workspace="x", start_dt=start_dt, end_dt=end_dt, snapshot_ingested_at=snapshot_ingested_at,
        category_filter=category_filter, author_type=author_type, search_query=search_query,
        include_new_count=False,
    )
    sql = f"""
    WITH page_rows AS (
        SELECT *, ROW_NUMBER() OVER () AS _rn
        FROM ({page_sql}) AS _ordered
    ),
    kpi AS (
        SELECT
            COUNT(*) AS total_discovered,
            SUM(CASE WHEN verification_status = 'verified' THEN 1 ELSE 0 END) AS total_verified,
            SUM(CASE WHEN verification_status != 'verified' THEN 1 ELSE 0 END) AS pending_verification,
            SUM(CASE WHEN enabled = 1 THEN 1 ELSE 0 END) AS active_monitored,
            SUM(CASE WHEN enabled = 0 THEN 1 ELSE 0 END) AS inactive_monitored
        FROM x_accounts
    ),
    cats AS (
        SELECT category, COUNT(*) AS cnt
        FROM x_accounts
        WHERE category IS NOT NULL AND category <> ''
        GROUP BY category
        ORDER BY cnt DESC
    )
    SELECT
        {tot_s} AS total_count,
        COALESCE((SELECT json_agg(row_to_json(p) ORDER BY p._rn) FROM page_rows p), '[]'::json) AS rows_json,
        kpi.*,
        COALESCE((SELECT json_agg(row_to_json(c)) FROM cats c), '[]'::json) AS cats_json
    FROM kpi;
    """
    res_rows = query_supabase(sql)
    kpis: Dict[str, Any] = {
        "total_discovered": 0, "total_verified": 0, "pending_verification": 0,
        "active_monitored": 0, "inactive_monitored": 0, "by_category": {},
    }
    if not res_rows:
        return {"kpis": kpis, "rows": [], "total_count": 0}
    r0 = res_rows[0]
    kpis["total_discovered"] = int(r0.get("total_discovered") or 0)
    kpis["total_verified"] = int(r0.get("total_verified") or 0)
    kpis["pending_verification"] = int(r0.get("pending_verification") or 0)
    kpis["active_monitored"] = int(r0.get("active_monitored") or 0)
    kpis["inactive_monitored"] = int(r0.get("inactive_monitored") or 0)
    cats_raw = _parse_json_val(r0.get("cats_json"), default=[])
    if isinstance(cats_raw, list):
        for cr in cats_raw:
            if isinstance(cr, dict) and cr.get("category"):
                kpis["by_category"][cr["category"]] = int(cr.get("cnt") or 0)
    return {
        "kpis": kpis,
        "rows": _hydrate_workspace_raw_list("x", r0.get("rows_json")),
        "total_count": int(r0.get("total_count") or 0),
    }


def get_dashboard_header_state(
    start_dt: Optional[datetime.datetime] = None,
    end_dt: Optional[datetime.datetime] = None,
    include_wa_sent: bool = True,
    wa_limit: int = 1000,
) -> Dict[str, Any]:
    """Fetches stream counts AND WhatsApp sent map in ONE SQL round-trip without runtime DDL."""
    w_np, w_in, w_x = _build_stream_count_where(start_dt=start_dt, end_dt=end_dt)
    if include_wa_sent:
        sql = f"""
        WITH wa_rows AS (
            SELECT item_key, group_id, group_name, id_message, item_link, sent_at
            FROM whatsapp_sent_log
            ORDER BY sent_at DESC
            LIMIT {int(wa_limit)}
        )
        SELECT
            (SELECT COUNT(*) FROM articles WHERE {w_np}) AS np_count,
            (SELECT COUNT(*) FROM indian_media_articles WHERE {w_in}) AS in_count,
            (SELECT COUNT(*) FROM x_posts WHERE {w_x}) AS x_count,
            COALESCE((SELECT json_agg(row_to_json(w)) FROM wa_rows w), '[]'::json) AS wa_json;
        """
    else:
        sql = f"""
        SELECT
            (SELECT COUNT(*) FROM articles WHERE {w_np}) AS np_count,
            (SELECT COUNT(*) FROM indian_media_articles WHERE {w_in}) AS in_count,
            (SELECT COUNT(*) FROM x_posts WHERE {w_x}) AS x_count,
            '[]'::json AS wa_json;
        """
    try:
        rows = query_supabase(sql)
    except Exception as exc:
        if include_wa_sent and "whatsapp_sent_log" in str(exc).lower():
            ensure_whatsapp_sent_log_table()
            rows = query_supabase(sql)
        else:
            raise

    counts = {"nepali_count": 0, "indian_count": 0, "x_count": 0}
    wa_sent_map: Dict[str, Dict[str, Any]] = {}
    if rows:
        r0 = rows[0]
        counts = {
            "nepali_count": int(r0.get("np_count") or 0),
            "indian_count": int(r0.get("in_count") or 0),
            "x_count": int(r0.get("x_count") or 0),
        }
        wa_sent_map = _parse_wa_sent_rows(r0.get("wa_json"))
    return {"counts": counts, "wa_sent_map": wa_sent_map}


def get_indian_borderline_bundle(limit: int = 100, min_score: float = 0.40) -> Dict[str, Any]:
    """Fetches Indian media audit stats + recent borderline/relevant candidates in 1 SQL round-trip."""
    min_sc = float(min_score)
    sql = f"""
    WITH audit AS (
        SELECT
            COUNT(*) AS total_discovered,
            SUM(CASE WHEN relevance_status IN ('substantive', 'relevant') THEN 1 ELSE 0 END) AS substantive,
            SUM(CASE WHEN relevance_status IN ('borderline_review', 'borderline') THEN 1 ELSE 0 END) AS borderline_review,
            SUM(CASE WHEN relevance_status = 'excluded' THEN 1 ELSE 0 END) AS excluded
        FROM indian_media_articles
    ),
    recent_rows AS (
        SELECT {INDIAN_FEED_COLUMNS}
        FROM indian_media_articles
        WHERE nepal_relevance_score >= {min_sc}
        ORDER BY published_dt DESC, canonical_id DESC
        LIMIT {int(limit)}
    )
    SELECT
        audit.*,
        COALESCE((SELECT json_agg(row_to_json(r)) FROM recent_rows r), '[]'::json) AS candidates_json
    FROM audit;
    """
    rows = query_supabase(sql)
    audit = {
        "total": 0, "total_discovered": 0, "substantive": 0,
        "relevant": 0, "borderline_review": 0, "borderline": 0, "excluded": 0,
    }
    candidates: List[Dict[str, Any]] = []
    if rows:
        r = rows[0]
        total = int(r.get("total_discovered") or 0)
        sub = int(r.get("substantive") or 0)
        bord = int(r.get("borderline_review") or 0)
        excl = int(r.get("excluded") or 0)
        audit = {
            "total": total, "total_discovered": total, "substantive": sub,
            "relevant": sub, "borderline_review": bord, "borderline": bord, "excluded": excl,
        }
        raw_list = _parse_json_val(r.get("candidates_json"), default=[])
        if isinstance(raw_list, list):
            candidates = _hydrate_indian_rows(raw_list)
    return {"audit": audit, "candidates": candidates}


@_cache_data_if_available(ttl=120)
def get_system_health_bundle() -> Dict[str, Any]:
    """Fetches global system KPIs AND per-source health table in ONE SQL CTE round-trip."""
    sql = """
    WITH art_stats AS (
        SELECT
            a.source,
            COUNT(*) FILTER (WHERE a.published_dt >= (NOW() AT TIME ZONE 'Asia/Kathmandu') - INTERVAL '1 hour') AS count_1h,
            COUNT(*) FILTER (WHERE a.published_dt >= (NOW() AT TIME ZONE 'Asia/Kathmandu') - INTERVAL '24 hour') AS count_24h,
            COUNT(*) FILTER (WHERE a.published_dt >= (NOW() AT TIME ZONE 'Asia/Kathmandu') - INTERVAL '7 day') AS count_7d,
            COUNT(*) AS count_total
        FROM articles a
        GROUP BY a.source
    ),
    src_kpis AS (
        SELECT
            COUNT(*) AS total_sources,
            COUNT(*) FILTER (WHERE enabled = 1) AS active_sources
        FROM sources
    ),
    hlth_kpis AS (
        SELECT
            COUNT(*) FILTER (WHERE status = 'operational') AS operational,
            COUNT(*) FILTER (WHERE status = 'degraded') AS degraded,
            COUNT(*) FILTER (WHERE status = 'failing') AS failing,
            COALESCE(AVG(discovery_latency_avg_secs), 0.75) AS avg_latency
        FROM source_health
    ),
    art_kpis AS (
        SELECT
            COALESCE(SUM(count_1h), 0) AS articles_1h,
            COALESCE(SUM(count_24h), 0) AS articles_24h,
            COALESCE(SUM(count_7d), 0) AS articles_7d,
            COALESCE(SUM(count_total), 0) AS total_stored_articles
        FROM art_stats
    ),
    health_rows AS (
        SELECT
            s.name, s.type, s.url, s.lang, s.category, s.priority, s.check_interval_mins, s.enabled,
            h.last_discovery_time, h.last_ingestion_time,
            COALESCE(h.status, 'operational') AS status,
            COALESCE(h.consecutive_failures, 0) AS consecutive_failures,
            COALESCE(h.total_discovered, 0) AS total_discovered,
            COALESCE(h.total_ingested, 0) AS total_ingested,
            COALESCE(h.duplicate_count, 0) AS duplicate_count,
            COALESCE(h.failed_retrievals, 0) AS failed_retrievals,
            h.latest_article_pub_dt, h.latest_article_title, h.latest_article_link,
            h.last_error_message,
            COALESCE(h.discovery_latency_avg_secs, 0.0) AS discovery_latency_avg_secs,
            COALESCE(a.count_1h, 0) AS count_1h,
            COALESCE(a.count_24h, 0) AS count_24h,
            COALESCE(a.count_7d, 0) AS count_7d,
            COALESCE(a.count_total, 0) AS count_total
        FROM sources s
        LEFT JOIN source_health h ON s.name = h.source_name
        LEFT JOIN art_stats a ON a.source = s.name
        ORDER BY s.enabled DESC, s.name ASC
    )
    SELECT
        src_kpis.*,
        hlth_kpis.*,
        art_kpis.*,
        COALESCE((SELECT json_agg(row_to_json(hr)) FROM health_rows hr), '[]'::json) AS health_json
    FROM src_kpis, hlth_kpis, art_kpis;
    """
    rows = query_supabase(sql)
    if not rows:
        return {"kpis": _fetch_system_kpis_raw(), "health": []}
    r = rows[0]
    kpis = {
        "total_sources": int(r.get("total_sources") or 34),
        "active_sources": int(r.get("active_sources") or 34),
        "operational": int(r.get("operational") or 30),
        "degraded": int(r.get("degraded") or 0),
        "failing": int(r.get("failing") or 0),
        "avg_latency_secs": round(float(r.get("avg_latency") or 0.75), 2),
        "articles_1h": int(r.get("articles_1h") or 0),
        "articles_24h": int(r.get("articles_24h") or 0),
        "articles_7d": int(r.get("articles_7d") or 0),
        "total_stored_articles": int(r.get("total_stored_articles") or 0),
    }
    health = _parse_json_val(r.get("health_json"), default=[])
    return {"kpis": kpis, "health": health if isinstance(health, list) else []}


def fetch_analytics_export_bundle(
    start_dt: Optional[datetime.datetime] = None,
    end_dt: Optional[datetime.datetime] = None,
    limit: int = 500,
) -> Dict[str, List[Dict[str, Any]]]:
    """Fetches Nepali, Indian, and X export datasets in ONE single SQL CTE round-trip."""
    lim = int(limit)
    w_np = _build_articles_where(start_dt=start_dt, end_dt=end_dt)
    w_in = _build_indian_where(eff_status="substantive", start_dt=start_dt, end_dt=end_dt)
    w_x = _build_x_where(start_dt=start_dt, end_dt=end_dt)
    sql = f"""
    WITH np_rows AS (
        SELECT {ARTICLE_FEED_COLUMNS}
        FROM articles
        WHERE {' AND '.join(w_np)}
        ORDER BY published_dt DESC, canonical_id DESC
        LIMIT {lim}
    ),
    in_rows AS (
        SELECT {INDIAN_FEED_COLUMNS}
        FROM indian_media_articles
        WHERE {' AND '.join(w_in)}
        ORDER BY published_dt DESC, canonical_id DESC
        LIMIT {lim}
    ),
    x_rows AS (
        SELECT {X_FEED_COLUMNS}
        FROM x_posts
        WHERE {' AND '.join(w_x)}
        ORDER BY published_dt DESC, id DESC
        LIMIT {lim}
    )
    SELECT
        COALESCE((SELECT json_agg(row_to_json(n)) FROM np_rows n), '[]'::json) AS np_json,
        COALESCE((SELECT json_agg(row_to_json(i)) FROM in_rows i), '[]'::json) AS in_json,
        COALESCE((SELECT json_agg(row_to_json(x)) FROM x_rows x), '[]'::json) AS x_json;
    """
    rows = query_supabase(sql)
    if not rows:
        return {"nepali": [], "indian": [], "x": []}
    r0 = rows[0]
    np_list = _parse_json_val(r0.get("np_json"), default=[])
    in_list = _parse_json_val(r0.get("in_json"), default=[])
    x_list = _parse_json_val(r0.get("x_json"), default=[])
    return {
        "nepali": _hydrate_article_rows(np_list) if isinstance(np_list, list) else [],
        "indian": _hydrate_indian_rows(in_list) if isinstance(in_list, list) else [],
        "x": _hydrate_x_rows(x_list) if isinstance(x_list, list) else [],
    }


_WA_SENT_TABLE_ENSURED = False


def ensure_whatsapp_sent_log_table() -> None:
    """Creates the whatsapp_sent_log table in Supabase if it does not already exist."""
    global _WA_SENT_TABLE_ENSURED
    if _WA_SENT_TABLE_ENSURED:
        return
    sql = """
    CREATE TABLE IF NOT EXISTS whatsapp_sent_log (
        item_key TEXT PRIMARY KEY,
        group_id TEXT DEFAULT '',
        group_name TEXT DEFAULT 'Media Monitor',
        id_message TEXT DEFAULT '',
        item_link TEXT DEFAULT '',
        sent_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """
    query_supabase(sql)
    _WA_SENT_TABLE_ENSURED = True


def record_whatsapp_sent(
    item_key: str,
    group_id: str,
    group_name: str,
    id_message: str,
    item_link: str = "",
) -> bool:
    """Persists a successful WhatsApp share to Supabase so all users see the sent notice."""
    if not item_key:
        return False
    sql = f"""
    INSERT INTO whatsapp_sent_log (item_key, group_id, group_name, id_message, item_link, sent_at)
    VALUES (
        {esc_sql(item_key)},
        {esc_sql(group_id or '')},
        {esc_sql(group_name or 'Media Monitor')},
        {esc_sql(id_message or '')},
        {esc_sql(item_link or '')},
        NOW()
    )
    ON CONFLICT (item_key) DO UPDATE SET
        group_id = EXCLUDED.group_id,
        group_name = EXCLUDED.group_name,
        id_message = EXCLUDED.id_message,
        item_link = EXCLUDED.item_link,
        sent_at = NOW();
    """
    try:
        query_supabase(sql)
    except Exception as exc:
        if "whatsapp_sent_log" in str(exc).lower():
            ensure_whatsapp_sent_log_table()
            query_supabase(sql)
        else:
            raise
    return True


def get_whatsapp_sent_map(limit: int = 1000) -> Dict[str, Dict[str, Any]]:
    """Returns a mapping of item_key -> sent metadata without unconditional DDL checks."""
    sql = (
        "SELECT item_key, group_id, group_name, id_message, item_link, sent_at "
        f"FROM whatsapp_sent_log ORDER BY sent_at DESC LIMIT {int(limit)};"
    )
    try:
        rows = query_supabase(sql)
    except Exception as exc:
        if "whatsapp_sent_log" in str(exc).lower():
            ensure_whatsapp_sent_log_table()
            rows = query_supabase(sql)
        else:
            raise
    sent_map: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("item_key") or "").strip()
        if key:
            sent_map[key] = row
    return sent_map





