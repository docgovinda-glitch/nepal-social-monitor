"""
nepal_x_scanner.py
Comprehensive Daily X (Twitter) & Social Intelligence Scanner for Nepal.
Aggregates authentic, real-time live posts across verified Nepali political figures,
government institutions, embassies, news curators, and journalists who frequently post
on topics relating to the 8 Structured Categories:
  1. India in Nepal
  2. China in Nepal
  3. Pakistan in Nepal
  4. Bangladesh in Nepal
  5. Nepal – Internal Politics
  6. Nepal – External Relations (Others)
  7. Economy
  8. Others

Each post is dynamically analyzed and organized into one of the 8 Structured Categories during fetching.
"""

import json
import os
import time
import threading
import datetime
import zoneinfo
import re
import ssl
import urllib.request
import urllib.parse
import concurrent.futures
import requests
from requests.adapters import HTTPAdapter
import feedparser
import urllib3
from typing import List, Dict, Any, Tuple, Optional

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from nepal_config import NEPAL_TZ, DEFAULT_HEADERS, format_nepal_relative_time as format_relative_time
SSL_CTX = ssl._create_unverified_context()
_X_HTTP_LOCAL = threading.local()


def _get_x_http_session() -> requests.Session:
    """Returns a thread-local keep-alive HTTP session for X/Twitter and Bing RSS requests."""
    sess = getattr(_X_HTTP_LOCAL, "session", None)
    if sess is None:
        sess = requests.Session()
        adapter = HTTPAdapter(pool_connections=32, pool_maxsize=32)
        sess.mount("https://", adapter)
        sess.mount("http://", adapter)
        sess.headers.update(DEFAULT_HEADERS)
        _X_HTTP_LOCAL.session = sess
    return sess


def _decode_snowflake_dt(sid: str) -> Optional[datetime.datetime]:
    """Decodes an authentic Twitter/X Snowflake status ID into a Nepal-timezone datetime."""
    s = str(sid).strip()
    if s.isdigit() and int(s) > 10_000_000_000_000:
        try:
            snowflake_ms = (int(s) >> 22) + 1288834974657
            return datetime.datetime.fromtimestamp(snowflake_ms / 1000.0, tz=datetime.timezone.utc).astimezone(NEPAL_TZ)
        except Exception:
            return None
    return None

# =====================================================================
# Unified List of Verified Monitored Nepali Accounts Frequently Posting
# on Topics Relating to the 8 Structured Categories
# =====================================================================
try:
    from nepal_social_directory import VERIFIED_NEPAL_SOCIAL_DIRECTORY as _PRIMARY_SOCIAL_DIR
except Exception:
    _PRIMARY_SOCIAL_DIR = []

try:
    from nepal_verified_x_directory import VERIFIED_NEPAL_X_DIRECTORY
except Exception:
    VERIFIED_NEPAL_X_DIRECTORY = []

_BASE_X_ACCOUNTS_SOURCE: List[Dict[str, Any]] = (
    [a for a in _PRIMARY_SOCIAL_DIR if str(a.get("platform") or "x").lower() == "x"]
    if _PRIMARY_SOCIAL_DIR
    else list(VERIFIED_NEPAL_X_DIRECTORY)
)

# Canonical, unified verified X directory
TOP_NEPAL_X_ACCOUNTS: List[Dict[str, Any]] = [
    {**acc, "type": acc.get("category", "Civil Society and Public Voices"), "verified": True}
    for acc in _BASE_X_ACCOUNTS_SOURCE
]

# Fast O(1) handle lookup map (seeded from nepal_social_directory.py, with legacy fallback)
ACCOUNT_BY_HANDLE: Dict[str, Dict[str, Any]] = {
    acc.get("handle", "").lower().strip().lstrip("@"): {
        **acc,
        "type": acc.get("category", "Civil Society and Public Voices"),
        "verified": True,
    }
    for acc in _BASE_X_ACCOUNTS_SOURCE
    if acc.get("handle")
}

_ACCOUNT_MAP_CACHE: Dict[str, Any] = {"ts": 0.0, "data": None}
_PORTAL_X_HANDLE_SET_CACHE: Optional[frozenset] = None


def _get_portal_x_handle_set() -> frozenset:
    """Returns lowercase X handles configured as portal x_handle / x_boost_handle."""
    global _PORTAL_X_HANDLE_SET_CACHE
    if _PORTAL_X_HANDLE_SET_CACHE is not None:
        return _PORTAL_X_HANDLE_SET_CACHE
    try:
        from nepal_config import TOP_NEPAL_NEWS_PORTALS
        handles = set()
        for portal in TOP_NEPAL_NEWS_PORTALS:
            for field in ("x_handle", "x_boost_handle"):
                h = (portal.get(field) or "").lstrip("@").strip().lower()
                if h:
                    handles.add(h)
        _PORTAL_X_HANDLE_SET_CACHE = frozenset(handles)
    except Exception:
        _PORTAL_X_HANDLE_SET_CACHE = frozenset()
    return _PORTAL_X_HANDLE_SET_CACHE


def _get_account_by_handle_map(ttl_seconds: int = 300) -> Dict[str, Dict[str, Any]]:
    """
    Returns a handle_lower -> account dict map synced from live Supabase x_accounts (platform='x')
    and nepal_social_directory.py, falling back to nepal_verified_x_directory.py only when unavailable.
    """
    now = time.time()
    cached = _ACCOUNT_MAP_CACHE.get("data")
    if cached is not None and (now - float(_ACCOUNT_MAP_CACHE.get("ts") or 0.0)) < ttl_seconds:
        return cached

    merged: Dict[str, Dict[str, Any]] = dict(ACCOUNT_BY_HANDLE)
    try:
        from nepal_news_store import get_all_x_accounts
        db_accounts = get_all_x_accounts(enabled_only=False, platform="x")
        if db_accounts:
            for a in db_accounts:
                if str(a.get("platform") or "x").lower() != "x":
                    continue
                h = str(a.get("handle") or "").lstrip("@").strip().lower()
                if h:
                    merged[h] = {
                        **a,
                        "type": a.get("category", "Civil Society and Public Voices"),
                        "verified": a.get("verification_status", "verified") == "verified",
                    }
    except Exception:
        pass

    if not merged and VERIFIED_NEPAL_X_DIRECTORY:
        merged = {
            acc.get("handle", "").lower().strip().lstrip("@"): {
                **acc,
                "type": acc.get("category", "Civil Society and Public Voices"),
                "verified": True,
            }
            for acc in VERIFIED_NEPAL_X_DIRECTORY
            if acc.get("handle")
        }

    _ACCOUNT_MAP_CACHE["data"] = merged
    _ACCOUNT_MAP_CACHE["ts"] = now
    return merged


def get_monitored_x_accounts(enabled_only: bool = True) -> List[Dict[str, Any]]:
    """
    Dynamically retrieves enabled monitored X accounts (platform == 'x') from Supabase cloud
    database, falling back to nepal_social_directory.py (and nepal_verified_x_directory.py only
    when nepal_social_directory is unavailable).
    """
    try:
        from nepal_news_store import get_all_x_accounts
        db_accounts = get_all_x_accounts(enabled_only=enabled_only, platform="x")
        x_only = [
            a for a in (db_accounts or [])
            if str(a.get("platform") or "x").lower() == "x"
        ]
        if x_only and len(x_only) >= 50:
            return [
                {
                    **a,
                    "type": a.get("category", "Civil Society and Public Voices"),
                    "verified": a.get("verification_status") == "verified",
                }
                for a in x_only
            ]
    except Exception:
        pass

    try:
        from nepal_social_directory import VERIFIED_NEPAL_SOCIAL_DIRECTORY
        return [
            {**a, "type": a.get("category", "Civil Society and Public Voices"), "verified": True}
            for a in VERIFIED_NEPAL_SOCIAL_DIRECTORY
            if str(a.get("platform") or "x").lower() == "x"
            and (not enabled_only or a.get("enabled", 1) in (1, True, "1"))
        ]
    except Exception:
        return [
            {**a, "type": a.get("category", "Civil Society and Public Voices"), "verified": True}
            for a in VERIFIED_NEPAL_X_DIRECTORY
            if (not enabled_only or a.get("enabled", 1) in (1, True, "1"))
        ]


def classify_x_post(text: str, author_name: str = "", handle: str = "", role: str = "") -> str:
    """
    Intelligently organizes a post into one of the 9 Structured Categories based on
    its content and topics:
      1. India Section
      2. China Section
      3. Bangladesh Section
      4. Pakistan Section
      5. Nepal – Internal
      6. Nepal – External
      7. Nepal – Economy
      8. Nepal – Others
      9. International News
    """
    from nepal_fetcher import classify_article_editorial

    # 1. Primary: Classify based purely on post text with editorial engine
    res = classify_article_editorial(text, text, author_name, role)
    inferred = res["primary_section"]
    if inferred not in ("Nepal – Others", "Others"):
        return inferred

    # 2. Secondary: Handle-specific topical defaults
    h_low = handle.lower()
    t_low = text.lower()
    if any(k in h_low for k in ["prcamb", "chinainnepal", "chinese", "amish973", "contactniice", "cesifnepal", "kdbhattarai"]):
        if any(w in t_low for w in [
            "china", "chinese", "चीन", "चिनियाँ", "bri", "beijing", "tibet", "तिब्बत",
            "kerung", "केरुङ", "tatopani", "तातोपानी", "pokhara", "पोखरा", "🇨🇳", "grant",
            "loan", "debt", "humla", "हुम्ला", "railway", "रेलमार्ग", "conclave", "dialogue",
            "asia", "ambassador", "policy", "foreign", "treaty"
        ]) or any(k in h_low for k in ["prcamb"]):
            return "China Section"

    if any(k in h_low for k in ["indiainnepal", "sureshrajn", "ronin_nepal", "dilipkhadk", "th3_kmix"]):
        if any(w in t_low for w in [
            "border", "सीमा", "india", "भारत", "treaty", "सन्धि", "dhoti", "धोती", "🇮🇳",
            "dispute", "विवाद", "delhi", "army", "power", "electricity", "export",
            "trade", "व्यापार", "modi", "नाकाबन्दी", "epg", "susta", "kalapani", "lipulekh"
        ]) or any(k in h_low for k in ["indiainnepal", "sureshrajn"]):
            return "India Section"

    if any(k in h_low for k in ["pakinnepal"]):
        return "Pakistan Section"
    if any(k in h_low for k in ["cricnepal", "therhinosarmy", "ronin_nepal", "dilipkhadk", "contactniice", "saarcsec", "nepcorres"]):
        if any(w in t_low for w in [
            "pakistan", "pakistani", "पाकिस्तान", "पाकिस्तानी", "islamabad", "इस्लामाबाद",
            "babar", "🇵🇰", "shaheen", "psl", "ptap", "karachi", "lahore", "rawalpindi"
        ]):
            return "Pakistan Section"
    if any(k in h_low for k in ["bdmofa", "bangladoot", "hamrokhelkud", "nepcorres", "trailokyararyal", "kathmandupost", "the_chillax", "contactniice", "cesifnepal", "amish973", "ashokpillar", "kdbhattarai"]):
        if any(w in t_low for w in [
            "bangladesh", "bangladeshi", "ढाका", "dhaka", "हसिना", "hasina",
            "युनुस", "yunus", "बङ्गलादेश", "बंगलादेश", "saff", "साफ", "rohanpur", "रोहनपुर", "🇧🇩",
            "40 mw", "४० मेगावाट"
        ]) or any(k in h_low for k in ["bdmofa", "bangladoot"]):
            return "Bangladesh Section"
    if any(k in h_low for k in [
        "nepalrastrabank", "fncci", "mofnepal", "cninepal", "nepalipaisa", "arthasarokar",
        "bizshala", "bizpati", "bizmandu", "sejonnepal", "bull_nepse"
    ]):
        return "Nepal – Economy"
    if any(k in h_low for k in ["ukinnepal", "usembassy", "un_nepal", "euinnepal", "nepalunny", "saarcsec", "japaninnepal"]):
        return "Nepal – External"
    if any(k in h_low for k in ["gejawagle", "nepcorres", "trailokyararyal", "dipak_gyawali", "madhuramanach", "arzuranadeuba", "mofanepal", "cesifnepal", "contactniice", "iids1979", "suryaraacharya", "the_chillax", "ronin_nepal", "dilipkhadk"]):
        if any(w in t_low for w in [
            "america", "अमेरिकी", "अमेरिका", "us", "mcc", "एमसीसी", "spp", "usaid", "trump", "biden",
            "eu", "european", "युरोपेली", "uk", "british", "britain", "बेलायत", "un", "united nations",
            "राष्ट्रसंघ", "peacekeeping", "शान्ति सेना", "saarc", "सार्क", "bimstec", "बिम्सटेक",
            "ldc", "who", "wto", "embassy", "ambassador", "diplomatic", "foreign", "treaty",
            "israel", "russia", "ukraine", "gaza", "blacklist", "कालोसूची", "grant", "aid"
        ]):
            return "Nepal – External"
    if any(k in h_low for k in [
        "kpsharmaoli", "cmprachanda", "sherbdeuba", "brb1954", "gagan", "hamrorabi", "swarnim",
        "shahbalen", "rabindra", "drckraut", "bishwaprakash", "yogesbhattarai", "gokulpbaskota",
        "minendrarijal", "pradeepgyawali", "hello_sarkar", "nepalpolicehq", "milanpandey",
        "kanakmanidixit", "narayanwagle", "kpariyar12", "vijaykantkarna", "sanjib_bagale",
        "nepalicongress", "shekharnc", "nainsinghmahar", "prakashsnehi", "bimalendranidhi",
        "gururajghimire", "umlcpn", "uml_nepal", "shankarpokhrel8", "bpaudel1959",
        "bishnurimal", "bhimrawal179", "sunitadangol_", "mamaheshbasnet", "ishwarpokhrel",
        "prithvisubba", "surendra_pandey", "manishjhanepal", "dipjha", "paswanbhola",
        "mohnaansari", "upendrayadav_", "jspnepal", "madhesiyouth", "teraionline",
        "madheshvani", "surendralabh", "jitendrajha", "rajeshahiraj", "janakpurlitfest"
    ]):
        return "Nepal – Internal"

    return "Nepal – Others"


def format_relative_time(pub_dt: datetime.datetime, now_npt: datetime.datetime) -> str:
    diff = now_npt - pub_dt
    secs = diff.total_seconds()
    if secs < 0 or secs < 60:
        return "Just now"
    if secs < 3600:
        mins = max(1, int(secs // 60))
        return f"{mins}m ago"
    elif secs < 86400:
        hours = int(secs // 3600)
        return f"{hours}h ago"
    elif secs < 86400 * 7:
        days = int(secs // 86400)
        return f"{days}d ago"
    else:
        return pub_dt.strftime("%b %d")


_NEPAL_X_RELEVANCE_RE = re.compile(
    r"(\bnepal\b|\bnepali\b|\bnepalese\b|\bkathmandu\b|\bpokhara\b|\bmadhesh\b|\bterai\b|"
    r"\bkalapani\b|\blipulekh\b|\bsusta\b|\bkerung\b|\btatopani\b|\bsaarc\b|\bbimstec\b|"
    r"\bhumla\b|\blumbini\b|\bjanakpur\b|\bbirgunj\b|\bbiratnagar\b|\bsingha durbar\b|"
    r"\bbaluwatar\b|\bsheetal niwas\b|\boli\b|\bprachanda\b|\bdeuba\b|\bbalen\b|\bgagan\b|"
    r"\brabi lamichhane\b|\bswarnim\b|\bck raut\b|\bkulman\b|\bharka\b|\bnrb\b|\bnepse\b|"
    r"[\u0900-\u097F])",
    re.IGNORECASE,
)


def _is_substantive_unmapped_x_post(clean_text: str) -> bool:
    """
    Filters noise from unmapped 'Public X Voice' tweets: requires minimum non-URL/mention/hashtag
    substance, explicit Nepal/regional relevance, and news/policy relevance via is_news_post().
    """
    stripped = re.sub(r"https?://\S+", " ", clean_text or "")
    stripped = re.sub(r"[@#][A-Za-z0-9_]+", " ", stripped)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    if len(stripped) < 25 or len(stripped.split()) < 6:
        return False

    if not _NEPAL_X_RELEVANCE_RE.search(clean_text or ""):
        return False

    try:
        from nepal_social_scanner import is_news_post
        is_news, _, _ = is_news_post("", clean_text)
        return bool(is_news)
    except Exception:
        return True


def _enrich_tweet_by_id(
    sid: str,
    fallback_title: str = "",
    fallback_url: str = "",
    fallback_dt: str = "",
    known_handle: str = None,
    known_account: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Fetches real tweet JSON via Twitter syndication CDN endpoint and dynamically classifies it."""
    now_npt = datetime.datetime.now(NEPAL_TZ)
    
    tweet_json = None
    url = f"https://cdn.syndication.twimg.com/tweet-result?id={sid}&token=4"
    try:
        r = _get_x_http_session().get(url, verify=False, timeout=(2.5, 4.0))
        if r.status_code == 200:
            tweet_json = r.json()
    except Exception:
        pass

    # STRICT AUTHENTICITY: If Twitter CDN does not return genuine tweet, reject completely
    if not tweet_json or not tweet_json.get("text"):
        return None

    raw_text = tweet_json.get("text", "").strip()

    # Extract long-form X note_tweet (X Premium / unconstrained tweets)
    note = tweet_json.get("note_tweet")
    if isinstance(note, dict):
        long_text = (
            note.get("note_tweet_results", {}).get("result", {}).get("text")
            or note.get("text")
        )
        if long_text and len(long_text) > len(raw_text):
            raw_text = long_text.strip()

    # Extract quoted tweet text
    quoted = tweet_json.get("quoted_tweet")
    if isinstance(quoted, dict) and quoted.get("text"):
        q_user = quoted.get("user", {})
        q_author = q_user.get("name") or q_user.get("screen_name") or "Quoted"
        q_text = quoted.get("text", "").strip()
        raw_text += f"\n\n💬 Quoting @{q_author}:\n{q_text}"
    if not raw_text or len(raw_text) < 5:
        return None

    # Filter out vulgar/toxic words to keep feed clean & professional
    lower_raw = raw_text.lower()
    toxic_words = [
        "asshole", "gandu", "shitholes", "fuck", "bitch", "bastard", "chutiya",
        "madarchod", "bhenchod", "beggars", "piss", "porn"
    ]
    if any(w in lower_raw for w in toxic_words):
        return None

    # Filter out empty/trivial replies or grok mentions
    if "@grok" in lower_raw and len(raw_text) < 70:
        return None
    if raw_text.startswith("@"):
        substantive_body = re.sub(r"@[A-Za-z0-9_]+", "", raw_text).strip()
        if len(substantive_body) < 35 or len(substantive_body.split()) < 6:
            return None

    u = tweet_json.get("user", {})
    handle = u.get("screen_name") or known_handle or (known_account.get("handle") if known_account else "X_Nepal")
    name = u.get("name") or handle
    likes = tweet_json.get("favorite_count", 0)
    retweets = tweet_json.get("retweet_count", 0)
    replies = tweet_json.get("reply_count", 0)
    views_dict = tweet_json.get("views", {})
    impressions = int(views_dict.get("count", 0)) if isinstance(views_dict, dict) and views_dict.get("count") else (likes * 16)
    
    created_at_str = tweet_json.get("created_at", "")
    pub_dt = None
    if created_at_str:
        try:
            from dateutil import parser as dt_parser
            pub_dt = dt_parser.parse(created_at_str).astimezone(NEPAL_TZ)
        except Exception:
            pass

    # If created_at is missing, decode the tweet Snowflake ID for authentic creation timestamp
    if not pub_dt:
        pub_dt = _decode_snowflake_dt(sid)

    if not pub_dt:
        pub_dt = now_npt

    # Guarantee no future dates (clock skew clamp)
    if pub_dt > now_npt:
        pub_dt = now_npt

    clean_handle = handle.lstrip("@").strip()
    link = f"https://x.com/{clean_handle}/status/{sid}"

    clean_text = re.sub(r"\s*-\s*(?:X|Twitter|on X: .*)$", "", raw_text).strip()
    clean_text = re.sub(r"^[^:]+ on X:\s*\"?", "", clean_text).rstrip("\"").strip()

    acc_map = _get_account_by_handle_map()
    acc = (
        known_account
        if known_account and clean_handle.lower() == known_account.get("handle", "").lower().lstrip("@")
        else acc_map.get(clean_handle.lower())
    )
    is_portal_bridge = clean_handle.lower() in _get_portal_x_handle_set()
    is_protected_account = bool(acc) or is_portal_bridge
    if not is_protected_account and not _is_substantive_unmapped_x_post(clean_text):
        return None
    if is_protected_account and not is_portal_bridge:
        stripped = re.sub(r"https?://\S+", " ", clean_text or "")
        stripped = re.sub(r"[@#][A-Za-z0-9_]+", " ", stripped)
        stripped = re.sub(r"\s+", " ", stripped).strip()
        if len(stripped) < 15:
            return None
        if len(clean_text) < 120:
            try:
                from nepal_social_scanner import _GREETING_PATTERNS, _NEWS_KEYWORDS_DEV, _NEWS_KEYWORDS_EN
                has_greeting = any(re.search(pat, clean_text, re.IGNORECASE) for pat in _GREETING_PATTERNS)
                if has_greeting:
                    text_low = clean_text.lower()
                    has_news_kw = (
                        any(kw != "नेपाल" and kw in clean_text for kw in _NEWS_KEYWORDS_DEV)
                        or any(kw != "nepal" and kw in text_low for kw in _NEWS_KEYWORDS_EN)
                    )
                    if not has_news_kw:
                        return None
            except Exception:
                pass

    if acc:
        author_name = acc["name"]
        author_type = acc.get("type", "Verified Voice")
        role = acc["role"]
        verified = True
        avatar_bg = acc["avatar_bg"]
        initials = acc["initials"]
        disp_handle = f"@{acc['handle']}"
    else:
        author_name = name
        author_type = "Public X Voice"
        role = "Nepal Live Voice"
        verified = bool(u.get("is_blue_verified") or u.get("verified"))
        avatar_bg = "#1d9bf0"
        initials = clean_handle[:2].upper()
        disp_handle = f"@{clean_handle}"

    # Organize the post into the 8 sections dynamically while fetching:
    cat_name = classify_x_post(clean_text, author_name, clean_handle, role)

    # Sentiment determination:
    lower_t = clean_text.lower()
    if any(w in lower_t for w in [
        "flood", "warning", "dead", "death", "crash", "arrest", "earthquake", "landslide", "scam",
        "हत्या", "मृत्यु", "दुर्घटना", "विपद्", "dispute", "occupation", "rogue", "terrorist",
        "encroachment", "blockade", "threat", "bully", "protest", "debt trap", "coward", "wimp",
        "नाकाबन्दी", "सीमा विवाद", "मिचाहा", "हस्तक्षेप", "दमन", "धम्की", "विरोध", "अतिक्रमण",
        "शत्रु", "अन्याय", "बहिष्कार", "झुठ", "धोती", "🖕", "fraud", "corrupt", "भ्रष्टाचार",
        "ऋणको पासो", "investigation", "छानबिन", "cyber scam", "हथियार", "delay", "अवरोध",
        "terrorism", "आतङ्कवाद", "paralysis", "stalemate", "deadlock",
        "violence", "unrest", "protest", "coup", "toppled", "ouster", "riot", "curfew", "कर्फ्यू", "हिंसा", "अवरोध", "प्रदर्शन",
        "mcc", "एमसीसी", "spp", "एसपीपी", "blacklist", "कालोसूची", "air safety ban", "हवाई प्रतिबन्ध", "sanctions", "प्रतिबन्ध",
        "airstrike", "drone strike", "escalation", "drone attack", "hostage", "हमास", "विपिन जोशी", "bipin joshi",
        "घूस", "अनियमितता", "अपचलन", "सहकारी ठगी", "सहकारी प्रकरण", "दुरुपयोग", "लापरबाही", "पक्राउ", "हिरासत",
        "घेराउ", "असफल", "निकम्मा", "जालसाजी", "ललिता निवास", "भुटानी शरणार्थी", "काण्ड", "बर्खास्ती",
        "दण्डहीनता", "सिन्डिकेट", "bribe", "detained", "custody", "embezzlement", "negligence", "impunity",
        "गिरावट", "ओरालो", "घाटा", "महँगो", "महँगियो", "मूल्यवृद्धि", "ऋणको भार", "तरलता अभाव", "कर्जा जोखिम",
        "डुब्यो", "डुबायो", "ब्याज वृद्धि", "व्यापार घाटा", "राजस्व घाटा", "bearish", "crash", "inflation",
        "price hike", "liquidity crunch", "default", "debt burden",
        "गुटबन्दी", "झडप", "क्रियाशील सदस्यता विवाद", "असन्तुष्ट", "पार्टी कब्जा", "विद्रोह", "धोका", "अन्तर्घात", "factionalism", "infighting",
        "अहंकार", "कारबाही", "निष्कासन", "तानाशाही", "प्रतिगमन", "लम्पसारवादी", "authoritarian", "regression", "विभाजन", "आन्तरिक कलह", "अधिनायकवाद",
        "निरंकुश", "धरपकड", "उल्लङ्घन", "उपहास", "विकृति", "अध्यादेश", "षड्यन्त्र", "अपराधी छुटाउन",
        "भेदभाव", "उखु किसान", "मलको हाहाकार", "नागरिकताबाट वञ्चित", "बाढीको कहर", "डुबान", "साम्प्रदायिक तनाव", "कुटपिट", "झडप", "दङ्गा", "विभेद", "शोषण", "discrimination", "marginalized", "flood crisis"
    ]):
        sentiment = "Alert / Critical"
    elif any(w in lower_t for w in [
        "win", "victory", "champion", "profit", "export", "celebrates", "celebrate", "record",
        "congratulations", "century", "masterclass", "cooperation", "partnership", "friendship",
        "gratitude", "grateful", "harmony", "paradise", "brotherhood", "welcome", "compassion",
        "शुभकामना", "शुभ", "बधाई", "उल्लास", "सद्भाव", "सहकार्य", "मित्रता", "विद्युत् निर्यात",
        "सांस्कृतिक", "तीर्थ", "धार्मिक", "गौरव", "सम्मान", "प्रफुल्लित", "सफलता",
        "grant", "अनुदान", "connectivity", "सम्पर्क सञ्जाल", "reopen", "सञ्चालन",
        "scholarship", "छात्रवृत्ति", "mbbs", "bds", "fellowship", "ptap",
        "power export", "विद्युत् व्यापार", "४० मेगावाट", "40 mw", "electricity export", "saff", "sportsmanship", "friendly match", "tripartite", "ऐतिहासिक सम्झौता",
        "peacekeeping", "शान्ति सेना", "ldc graduation", "clean energy grant", "humanitarian", "राहत", "उद्धार", "consular", "visa waiver", "द्विपक्षीय", "accord", "सम्झौता", "सराहनीय", "climate finance",
        "सुशासन", "पारदर्शिता", "छिटोछरितो", "डिजिटलाइजेसन", "नागरिक एप", "राहत वितरण", "श्रमदान", "सहमति", "विकास", "सुधार", "सफाई", "सुविधा", "नियन्त्रण", "good governance", "reform", "transparency", "public service", "digital nepal",
        "उछाल", "वृद्धि", "बढ्यो", "नाफा", "फाइदा", "लाभांश", "बोनस", "हरियाली", "बुल", "रेकर्ड", "उच्चतम",
        "विप्रेषण वृद्धि", "राजस्व संकलन", "विदेशी मुद्रा सञ्चिति", "सबल", "bullish", "surge", "dividend",
        "all-time high", "remittance inflow", "green candle", "gain", "rally",
        "एकता", "प्रजातान्त्रिक", "लोकतान्त्रिक समाजवाद", "महाधिवेशन", "समुन्नत नेपाल", "सबल कांग्रेस", "solidarity",
        "समृद्ध नेपाल सुखी नेपाली", "जबज", "जनताको बहुदलीय जनवाद", "सूर्य", "सफल नेतृत्व", "विकास नायक", "अडिग", "राष्ट्रवाद", "जनपक्षीय", "कम्युनिस्ट आन्दोलन", "कम्युनिष्ट एकता",
        "छठ पर्व", "मिथिला कला", "जानकी मन्दिर", "साहित्य महोत्सव", "तराई विकास", "कृषि अनुदान", "सद्भाव", "भ्रातृत्व", "सशक्तिकरण", "महिलाक महिमा", "मिथिला संस्कृति", "mithila art", "empowerment"
    ]):
        sentiment = "Positive"
    else:
        sentiment = "Neutral"

    rel_time = format_relative_time(pub_dt, now_npt)
    exact_time = pub_dt.strftime("%b %d, %I:%M %p NPT")

    expanded_urls: List[str] = []
    entities = tweet_json.get("entities") if isinstance(tweet_json.get("entities"), dict) else {}
    for u_obj in (entities.get("urls") or []):
        if isinstance(u_obj, dict):
            eu = (u_obj.get("expanded_url") or u_obj.get("url") or "").strip()
            if eu and eu not in expanded_urls:
                expanded_urls.append(eu)
    card = tweet_json.get("card") if isinstance(tweet_json.get("card"), dict) else {}
    bv = card.get("binding_values") if isinstance(card.get("binding_values"), dict) else {}
    card_title = str((bv.get("title") or {}).get("string_value") or "").strip()
    card_description = str((bv.get("description") or {}).get("string_value") or "").strip()
    card_url = str((bv.get("card_url") or {}).get("string_value") or "").strip()
    if card_url and card_url not in expanded_urls:
        expanded_urls.append(card_url)

    discovery_signals: List[Dict[str, Any]] = []
    if acc:
        src_low = clean_handle.lower()
        seen_cands = set()
        acc_created_raw = None
        if isinstance(quoted, dict):
            qu = quoted.get("user") or {}
            qh = str(qu.get("screen_name") or "").lstrip("@").strip()
            qh_low = qh.lower()
            if qh_low and qh_low != src_low and qh_low not in acc_map and qh_low not in _get_portal_x_handle_set():
                seen_cands.add(qh_low)
                discovery_signals.append({
                    "platform": "x",
                    "handle": qh,
                    "candidate_name": qu.get("name") or qh,
                    "signal_type": "co_mention",
                    "source_handle": src_low,
                    "post_id": str(sid),
                    "engagement": likes + (retweets * 2),
                    "followers_count": int(qu.get("followers_count") or 0),
                    "is_blue_verified": bool(qu.get("is_blue_verified") or qu.get("verified")),
                    "account_created_at": qu.get("created_at") or acc_created_raw,
                    "nepal_relevant": bool(_NEPAL_X_RELEVANCE_RE.search(clean_text)),
                })
        for m_obj in (entities.get("user_mentions") or []):
            if not isinstance(m_obj, dict):
                continue
            mh = str(m_obj.get("screen_name") or "").lstrip("@").strip()
            mh_low = mh.lower()
            if not mh_low or mh_low in seen_cands or mh_low == src_low:
                continue
            if mh_low in acc_map or mh_low in _get_portal_x_handle_set():
                continue
            seen_cands.add(mh_low)
            discovery_signals.append({
                "platform": "x",
                "handle": mh,
                "candidate_name": m_obj.get("name") or mh,
                "signal_type": "co_mention",
                "source_handle": src_low,
                "post_id": str(sid),
                "engagement": likes + (retweets * 2),
                "followers_count": 0,
                "is_blue_verified": False,
                "account_created_at": None,
                "nepal_relevant": bool(_NEPAL_X_RELEVANCE_RE.search(clean_text)),
            })

    clean_sid = str(sid).strip()
    canon_id = clean_sid if clean_sid.startswith("x_") else f"x_{clean_sid}"
    return {
        "id": canon_id,
        "is_real_api": True,
        "author_name": author_name,
        "handle": disp_handle,
        "raw_handle": clean_handle,
        "author_type": author_type,
        "role": role,
        "verified": verified,
        "avatar_bg": avatar_bg,
        "initials": initials,
        "title": clean_text[:90],
        "text": clean_text,
        "headline_english": clean_text[:90],
        "structured_category": cat_name,
        "likes": likes,
        "retweets": retweets,
        "replies": replies,
        "impressions": impressions,
        "engagement_score": likes + (retweets * 2),
        "published_dt": pub_dt,
        "relative_time": rel_time,
        "exact_time": exact_time,
        "link": link,
        "sentiment": sentiment,
        "expanded_urls": expanded_urls,
        "card_title": card_title,
        "card_description": card_description,
        "_discovery_signals": discovery_signals,
    }


_BING_SEARCH_QUERIES: List[str] = [
    "site:x.com Nepal", "site:x.com Nepali", "site:x.com Kathmandu", "site:x.com Pokhara",
    "site:x.com Biratnagar", "site:x.com Lalitpur", "site:x.com Bhaktapur",
    'site:x.com "Nepal Cricket"', 'site:x.com "Nepal Police"',
    'site:x.com "Balen Shah"', 'site:x.com "KP Oli"', 'site:x.com "Prachanda"',
    'site:x.com "Rabi Lamichhane"', 'site:x.com "Nepal Rastra Bank"',
    'site:x.com "India Nepal"', 'site:x.com "China Nepal"',
    'site:x.com "Bangladesh Nepal"', 'site:x.com "Pakistan Nepal"',
    'site:x.com "Nepal" "India"', 'site:x.com "Nepal" "India" border',
    'site:x.com "Nepal" "India" electricity', 'site:x.com "Nepal" "India" cricket',
    'site:x.com "Nepal" "Modi"', 'site:x.com "Nepal" "Kalapani"',
    'site:x.com "Nepal" "Lipulekh"', 'site:x.com "Nepal" "Susta"',
    'site:x.com "नेपाल" "भारत"', 'site:x.com "कालापानी"',
    'site:x.com "लिपुलेक"', 'site:x.com "नाकाबन्दी"', 'site:x.com "नेपाल-भारत"',
    'site:x.com "Nepal" "China"', 'site:x.com "Nepal" "China" BRI',
    'site:x.com "Nepal" "China" border', 'site:x.com "Nepal" "China" Pokhara',
    'site:x.com "Nepal" "China" railway', 'site:x.com "Nepal" "Kerung"',
    'site:x.com "Nepal" "Tatopani"', 'site:x.com "Nepal" "China" loan',
    'site:x.com "Nepal" "China" grant', 'site:x.com "नेपाल" "चीन"',
    'site:x.com "नेपाल" "बिआरआई"', 'site:x.com "केरुङ नाका"',
    'site:x.com "तातोपानी नाका"', 'site:x.com "पोखरा विमानस्थल" चीन',
    'site:x.com "Nepal" "Pakistan"', 'site:x.com "Nepal" "Pakistan" cricket',
    'site:x.com "Nepal" "Pakistan" SAARC', 'site:x.com "Nepal" "Pakistan" scholarship',
    'site:x.com "नेपाल" "पाकिस्तान"', 'site:x.com "नेपाल-पाकिस्तान"',
    'site:x.com "सार्क" "पाकिस्तान"',
    'site:x.com "Nepal" "Bangladesh"', 'site:x.com "Nepal" "Bangladesh" electricity',
    'site:x.com "Nepal" "Bangladesh" power', 'site:x.com "Nepal" "Bangladesh" Hasina',
    'site:x.com "Nepal" "Bangladesh" Yunus', 'site:x.com "Nepal" "Bangladesh" SAFF',
    'site:x.com "Nepal" "Bangladesh" football', 'site:x.com "नेपाल" "बंगलादेश"',
    'site:x.com "नेपाल" "बङ्गलादेश"', 'site:x.com "बंगलादेश" "बिजुली"',
    'site:x.com "बंगलादेश" "विद्यार्थी"', 'site:x.com "हसिना" "नेपाल"',
    'site:x.com "युनुस" "नेपाल"',
    'site:x.com "Nepal" "United States"', 'site:x.com "Nepal" "MCC"', 'site:x.com "Nepal" "USAID"',
    'site:x.com "Nepal" "US Embassy"', 'site:x.com "Nepal" "EU"', 'site:x.com "Nepal" "European Union"',
    'site:x.com "Nepal" "EU blacklist"', 'site:x.com "Nepal" "UK"', 'site:x.com "Nepal" "British Embassy"',
    'site:x.com "Nepal" "United Nations"', 'site:x.com "Nepal" "peacekeeping"', 'site:x.com "Nepal" "UNGA"',
    'site:x.com "Nepal" "SAARC"', 'site:x.com "Nepal" "BIMSTEC"', 'site:x.com "नेपाल" "सार्क"',
    'site:x.com "नेपाल" "बिम्सटेक"', 'site:x.com "नेपाल" "एमसीसी"', 'site:x.com "नेपाल" "शान्ति सेना"',
    'site:x.com "हवाई कालोसूची"',
    'site:x.com "CPN UML"', 'site:x.com "नेकपा एमाले"', 'site:x.com "एमाले"',
    'site:x.com "Bhim Rawal"', 'site:x.com "Shankar Pokhrel"', 'site:x.com "जबज"',
    'site:x.com "अनेरास्ववियु"', 'site:x.com "युवा संघ"',
    'site:x.com "Madhesh"', 'site:x.com "मधेश"', 'site:x.com "मधेस"',
    'site:x.com "Janakpur"', 'site:x.com "Birgunj"', 'site:x.com "उखु किसान"',
    'site:x.com "जसपा"', 'site:x.com "जनमत पार्टी"',
    "site:x.com #Nepal", "site:x.com #NepalCricket", "site:x.com #Kathmandu",
]


def _run_pool_bounded(fn, items, max_workers: int, timeout_secs: float = 20.0, on_item=None) -> List[Any]:
    """Runs fn over items concurrently under a hard wall-clock budget."""
    results: List[Any] = []
    if not items:
        return results
    ex = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
    try:
        futs = [ex.submit(fn, it) for it in items]
        try:
            for fut in concurrent.futures.as_completed(futs, timeout=timeout_secs):
                try:
                    val = fut.result()
                    if val is not None:
                        results.append(val)
                        if on_item is not None:
                            try:
                                on_item(len(results))
                            except Exception:
                                pass
                except Exception:
                    pass
        except concurrent.futures.TimeoutError:
            pass
    finally:
        ex.shutdown(wait=False, cancel_futures=True)
    return results


def _discover_profile_tweet_candidates(
    active_accounts: List[Dict[str, Any]],
    timeout_secs: float = 16.0,
) -> Dict[str, Dict[str, Any]]:
    """Scrapes recent tweet IDs from verified Nepali account profiles via keep-alive HTTP."""
    active_by_handle = {
        a["handle"].lower().lstrip("@"): a
        for a in active_accounts
        if a.get("handle")
    }
    acc_map = _get_account_by_handle_map()

    def _fetch_profile_ids(acc: Dict[str, Any]):
        h = acc["handle"].lstrip("@")
        h_low = h.lower()
        sess = _get_x_http_session()
        for attempt in range(2):
            try:
                r = sess.get(f"https://x.com/{h}", timeout=(3.0, 5.0))
                own_ids = re.findall(rf"/{re.escape(h)}/status/(\d{{18,20}})", r.text, re.IGNORECASE)
                pairs = re.findall(r"([A-Za-z0-9_]+)/status/(\d{18,20})", r.text)

                by_sid: Dict[str, Dict[str, Any]] = {}
                for sid in own_ids:
                    by_sid[sid] = acc
                for author_h, sid in pairs:
                    alow = author_h.lower()
                    if alow == h_low:
                        by_sid[sid] = acc
                    elif alow in active_by_handle or alow in acc_map:
                        by_sid.setdefault(sid, active_by_handle.get(alow) or acc_map[alow])

                if not by_sid and len(r.text) < 100000 and attempt == 0:
                    time.sleep(0.25)
                    continue

                sorted_items = sorted(by_sid.items(), key=lambda kv: int(kv[0]), reverse=True)
                return sorted_items[:12]
            except Exception:
                if attempt == 0:
                    time.sleep(0.25)
                    continue
                return []
        return []

    batches = _run_pool_bounded(_fetch_profile_ids, active_accounts, max_workers=20, timeout_secs=timeout_secs)
    dedup_items: Dict[str, Dict[str, Any]] = {}
    for batch in batches:
        for sid, target_acc in batch:
            if sid not in dedup_items:
                dedup_items[sid] = target_acc
    return dedup_items


def _discover_bing_tweet_candidates(timeout_secs: float = 12.0) -> List[Tuple[str, str, str, str]]:
    """Discovers viral Nepal X status IDs via Bing News RSS using keep-alive connections."""
    def _fetch_bing_sid(q: str):
        url = f"https://www.bing.com/news/search?q={urllib.parse.quote(q)}&format=rss"
        try:
            resp = _get_x_http_session().get(url, verify=False, timeout=(3.0, 4.0))
            if resp.status_code != 200:
                return []
            f = feedparser.parse(resp.content)
            res = []
            for it in f.entries:
                link = it.link
                if "url=" in link:
                    qs = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
                    if "url" in qs:
                        link = qs["url"][0]
                m = re.search(r"(?:x|twitter)\.com/([^/]+)/status/(\d+)", link)
                if m:
                    res.append((m.group(2), m.group(1), it.title, link))
            return res
        except Exception:
            return []

    batches = _run_pool_bounded(_fetch_bing_sid, _BING_SEARCH_QUERIES, max_workers=20, timeout_secs=timeout_secs)
    out: List[Tuple[str, str, str, str]] = []
    for b in batches:
        if b:
            out.extend(b)
    return out


def _select_tweet_ids_to_enrich(
    candidate_sids: List[str],
    existing_map: Optional[Dict[str, Any]] = None,
    now_npt: Optional[datetime.datetime] = None,
    refresh_window_hours: float = 48.0,
    min_recheck_secs: float = 300.0,
    active_topup_hours: float = 24.0,
    active_topup_cap: int = 60,
    max_enrich: int = 350,
) -> List[str]:
    """
    Sorts candidate tweet IDs newest-first via Snowflake ID and skips >48h already-stored
    or freshly-synced tweets so syndication enrichment stays fast and prioritizes breaking posts.
    """
    if not candidate_sids:
        return []

    ref_now = now_npt or datetime.datetime.now(NEPAL_TZ)
    known = existing_map or {}

    unique_sids = sorted(
        {str(s).strip() for s in candidate_sids if str(s).strip()},
        key=lambda s: int(s) if s.isdigit() else 0,
        reverse=True,
    )

    brand_new: List[str] = []
    stale_recent: List[str] = []
    active_topup: List[str] = []
    old_new: List[str] = []

    for sid in unique_sids:
        sf_dt = _decode_snowflake_dt(sid)
        age_hours = max(0.0, (ref_now - sf_dt).total_seconds() / 3600.0) if sf_dt else 0.0

        if sid not in known:
            if sf_dt and age_hours > 336.0:
                old_new.append(sid)
            else:
                brand_new.append(sid)
            continue

        if age_hours > refresh_window_hours:
            continue

        upd_raw = known.get(sid)
        upd_dt: Optional[datetime.datetime] = None
        if isinstance(upd_raw, datetime.datetime):
            upd_dt = upd_raw.replace(tzinfo=datetime.timezone.utc) if upd_raw.tzinfo is None else upd_raw
            upd_dt = upd_dt.astimezone(NEPAL_TZ)
        elif isinstance(upd_raw, str) and upd_raw.strip():
            try:
                from dateutil import parser as dt_parser
                parsed = dt_parser.parse(upd_raw)
                upd_dt = (parsed.replace(tzinfo=datetime.timezone.utc) if parsed.tzinfo is None else parsed).astimezone(NEPAL_TZ)
            except Exception:
                upd_dt = None

        upd_age_secs = (ref_now - upd_dt).total_seconds() if upd_dt else float("inf")
        if upd_age_secs >= min_recheck_secs:
            stale_recent.append(sid)
        elif age_hours <= active_topup_hours:
            active_topup.append(sid)

    selected = brand_new + stale_recent
    if len(selected) < 40 and active_topup:
        needed = max(0, min(active_topup_cap, 60) - len(selected))
        selected.extend(active_topup[:needed])
    if len(selected) < 60 and old_new:
        selected.extend(old_new[: max(0, 60 - len(selected))])

    return selected[:max_enrich]


def _load_existing_x_refresh_map(candidate_sids: List[str]) -> Dict[str, Optional[datetime.datetime]]:
    try:
        from nepal_news_store import get_x_post_refresh_map
        return get_x_post_refresh_map(candidate_sids)
    except Exception:
        return {}


def _get_portal_x_accounts() -> List[Dict[str, Any]]:
    """
    Builds X discovery account entries for all x_handle / x_boost_handle portals in
    TOP_NEPAL_NEWS_PORTALS so portal X bridges and boosts keep ingesting even when a
    portal's X handle is excluded from the curated social directory.
    """
    from nepal_config import TOP_NEPAL_NEWS_PORTALS

    portal_accounts: List[Dict[str, Any]] = []
    seen = set()
    for portal in TOP_NEPAL_NEWS_PORTALS:
        for field in ("x_handle", "x_boost_handle"):
            raw_h = (portal.get(field) or "").lstrip("@").strip()
            if not raw_h:
                continue
            h_low = raw_h.lower()
            if h_low in seen:
                continue
            seen.add(h_low)
            existing = ACCOUNT_BY_HANDLE.get(h_low)
            if existing:
                portal_accounts.append(existing)
            else:
                name = portal.get("name") or raw_h
                portal_accounts.append({
                    "handle": raw_h,
                    "name": name,
                    "category": "Media Houses and News Outlets",
                    "type": "Media Houses and News Outlets",
                    "role": portal.get("category", "News Outlet"),
                    "avatar_bg": "#b91c1c",
                    "initials": "".join(w[0].upper() for w in name.split()[:2]) or raw_h[:2].upper(),
                    "platform": "x",
                    "enabled": 1,
                    "verified": True,
                })
    return portal_accounts


def _with_portal_x_accounts(accounts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Returns `accounts` augmented with any portal X bridge/boost handles not already present."""
    merged = list(accounts)
    seen = {
        str(a.get("handle") or "").lstrip("@").strip().lower()
        for a in merged
        if a.get("handle") and str(a.get("platform") or "x").lower() == "x"
    }
    for p_acc in _get_portal_x_accounts():
        h_low = str(p_acc.get("handle") or "").lstrip("@").strip().lower()
        if h_low and h_low not in seen:
            merged.append(p_acc)
            seen.add(h_low)
    return merged


def harvest_tweets_from_nepali_accounts() -> List[Dict[str, Any]]:
    """
    Directly harvests and enriches fresh, real-time live tweets across all
    verified Nepali accounts in the monitored list. Each post is dynamically
    classified and organized into the 8 sections based on content.
    """
    active_accounts = get_monitored_x_accounts(enabled_only=True)
    if not active_accounts:
        active_accounts = TOP_NEPAL_X_ACCOUNTS

    dedup_items = _discover_profile_tweet_candidates(_with_portal_x_accounts(active_accounts), timeout_secs=16.0)
    if not dedup_items:
        return []

    now_npt = datetime.datetime.now(NEPAL_TZ)
    existing_map = _load_existing_x_refresh_map(list(dedup_items.keys()))
    target_sids = _select_tweet_ids_to_enrich(list(dedup_items.keys()), existing_map=existing_map, now_npt=now_npt)
    raw_items = [(sid, dedup_items[sid]) for sid in target_sids if sid in dedup_items]

    def _worker(item):
        sid, acc = item
        return _enrich_tweet_by_id(sid, known_handle=acc["handle"], known_account=acc)

    return _run_pool_bounded(_worker, raw_items, max_workers=24, timeout_secs=20.0)


def scan_popular_nepal_x_posts(force_refresh: bool = False, on_progress=None) -> List[Dict[str, Any]]:
    """
    Comprehensive Daily X & Social Media Intelligence Scanner.
    Combines:
      1. Direct status harvesting from verified Nepali accounts (primary).
      2. Authenticated status discovery via Bing News RSS across Nepal queries (concurrent).
    Strictly zero mock data. All posts are 100% genuine tweets sorted newest first.
    """
    # 1. Check Supabase cloud database if not explicit force refresh
    if not force_refresh:
        try:
            from nepal_news_store import get_stored_x_posts
            db_posts = get_stored_x_posts(limit=1500)
            if db_posts and len(db_posts) >= 40:
                return db_posts
        except Exception:
            pass

    now_npt = datetime.datetime.now(NEPAL_TZ)
    active_accounts = get_monitored_x_accounts(enabled_only=True)
    if not active_accounts:
        active_accounts = TOP_NEPAL_X_ACCOUNTS
    discovery_accounts = _with_portal_x_accounts(active_accounts)

    # Run account profile harvesting and Bing RSS discovery concurrently
    profile_candidates: Dict[str, Dict[str, Any]] = {}
    bing_candidates: List[Tuple[str, str, str, str]] = []
    disc_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)
    try:
        f_profiles = disc_pool.submit(_discover_profile_tweet_candidates, discovery_accounts, 18.0)
        f_bing = disc_pool.submit(_discover_bing_tweet_candidates, 12.0)
        try:
            profile_candidates = f_profiles.result(timeout=26.0) or {}
        except Exception:
            profile_candidates = {}
        try:
            bing_candidates = f_bing.result(timeout=20.0) or []
        except Exception:
            bing_candidates = []
    finally:
        disc_pool.shutdown(wait=False, cancel_futures=True)

    # Merge candidates with monitored account metadata taking precedence over Bing fallback
    merged_meta: Dict[str, Dict[str, Any]] = {}
    for sid, acc in profile_candidates.items():
        merged_meta[sid] = {
            "sid": sid,
            "known_handle": acc["handle"],
            "known_account": acc,
            "fallback_title": "",
            "fallback_url": "",
        }
    for sid, h, title, link in bing_candidates:
        if sid not in merged_meta:
            merged_meta[sid] = {
                "sid": sid,
                "known_handle": h,
                "known_account": None,
                "fallback_title": title,
                "fallback_url": link,
            }

    if not merged_meta:
        return []

    existing_map = _load_existing_x_refresh_map(list(merged_meta.keys()))
    target_sids = _select_tweet_ids_to_enrich(list(merged_meta.keys()), existing_map=existing_map, now_npt=now_npt)
    enrich_items = [merged_meta[sid] for sid in target_sids if sid in merged_meta]

    def _worker_enrich(meta: Dict[str, Any]):
        return _enrich_tweet_by_id(
            meta["sid"],
            fallback_title=meta["fallback_title"],
            fallback_url=meta["fallback_url"],
            known_handle=meta["known_handle"],
            known_account=meta["known_account"],
        )

    enriched = _run_pool_bounded(_worker_enrich, enrich_items, max_workers=24, timeout_secs=20.0, on_item=on_progress)

    all_posts: List[Dict[str, Any]] = []
    batch_signals: List[Dict[str, Any]] = []
    seen_ids = set()
    seen_texts = set()
    for p in enriched:
        if not p or not p.get("text"):
            continue
        sigs = p.pop("_discovery_signals", None)
        if sigs:
            batch_signals.extend(sigs)
        sid = p.get("id")
        norm = p["text"][:40].lower()
        if sid and sid not in seen_ids and norm not in seen_texts:
            seen_ids.add(sid)
            seen_texts.add(norm)
            all_posts.append(p)

    if batch_signals:
        try:
            from nepal_news_store import record_discovery_signals
            record_discovery_signals(batch_signals)
        except Exception:
            pass

    # Advance the unified circular social loop (Facebook + X news posts)
    try:
        from nepal_social_scanner import scan_social_batch
        social_posts, _ = scan_social_batch(batch_size=25)
        for sp in (social_posts or []):
            sid = sp.get("id")
            norm = sp.get("text", "")[:40].lower()
            if sid and sid not in seen_ids and norm not in seen_texts:
                seen_ids.add(sid)
                seen_texts.add(norm)
                all_posts.append(sp)
    except Exception:
        pass

    # Sort strictly descending by newest publication time
    all_posts.sort(key=lambda x: x["published_dt"], reverse=True)

    # Push freshly harvested posts directly into Supabase Cloud PostgreSQL x_posts table
    if all_posts:
        try:
            from nepal_news_store import save_x_posts
            save_x_posts(all_posts, batch_size=250)
        except Exception:
            pass
        # Bridge official X-sourced media accounts (e.g. @Annapurna_Post) into main articles table
        try:
            from nepal_fetcher import bridge_x_portals_to_articles
            bridge_x_portals_to_articles(x_posts=all_posts)
        except Exception:
            pass

    return all_posts
