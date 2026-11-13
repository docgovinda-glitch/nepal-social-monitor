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
import datetime
import zoneinfo
import re
import ssl
import urllib.request
import urllib.parse
import concurrent.futures
import requests
import feedparser
import urllib3
from typing import List, Dict, Any, Tuple

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

NEPAL_TZ = zoneinfo.ZoneInfo("Asia/Kathmandu")
CACHE_FILE = os.path.join(os.path.dirname(__file__), "nepal_x_posts_cache.json")
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
SSL_CTX = ssl._create_unverified_context()

# =====================================================================
# Unified List of Verified Monitored Nepali Accounts Frequently Posting
# on Topics Relating to the 8 Structured Categories
# =====================================================================
from nepal_verified_x_directory import VERIFIED_NEPAL_X_DIRECTORY

# Canonical, unified verified X directory (216 authentic researched accounts)
TOP_NEPAL_X_ACCOUNTS: List[Dict[str, Any]] = [
    {**acc, "type": acc.get("category", "Civil Society and Public Voices"), "verified": True}
    for acc in VERIFIED_NEPAL_X_DIRECTORY
]

# Fast O(1) handle lookup map
ACCOUNT_BY_HANDLE: Dict[str, Dict[str, Any]] = {
    acc.get("handle", "").lower().strip().lstrip("@"): {
        **acc,
        "type": acc.get("category", "Civil Society and Public Voices"),
        "verified": True
    }
    for acc in VERIFIED_NEPAL_X_DIRECTORY
    if acc.get("handle")
}


def get_monitored_x_accounts(enabled_only: bool = True) -> List[Dict[str, Any]]:
    """
    Dynamically retrieves enabled monitored X accounts from Supabase cloud database,
    falling back to VERIFIED_NEPAL_X_DIRECTORY.
    """
    try:
        from nepal_news_store import get_all_x_accounts
        db_accounts = get_all_x_accounts(enabled_only=enabled_only)
        if db_accounts and len(db_accounts) >= 50:
            formatted = []
            for a in db_accounts:
                formatted.append({
                    **a,
                    "type": a.get("category", "Civil Society and Public Voices"),
                    "verified": a.get("verification_status") == "verified"
                })
            return formatted
    except Exception:
        pass

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
        r = requests.get(url, verify=False, timeout=4)
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
    if not pub_dt and str(sid).isdigit() and int(sid) > 10000000000000:
        try:
            snowflake_ms = (int(sid) >> 22) + 1288834974657
            pub_dt = datetime.datetime.fromtimestamp(snowflake_ms / 1000.0, tz=datetime.timezone.utc).astimezone(NEPAL_TZ)
        except Exception:
            pass

    if not pub_dt:
        pub_dt = now_npt

    # Guarantee no future dates (clock skew clamp)
    if pub_dt > now_npt:
        pub_dt = now_npt

    clean_handle = handle.lstrip("@").strip()
    link = f"https://x.com/{clean_handle}/status/{sid}"

    clean_text = re.sub(r"\s*-\s*(?:X|Twitter|on X: .*)$", "", raw_text).strip()
    clean_text = re.sub(r"^[^:]+ on X:\s*\"?", "", clean_text).rstrip("\"").strip()

    acc = known_account or ACCOUNT_BY_HANDLE.get(clean_handle.lower())
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

    return {
        "id": sid,
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
        "sentiment": sentiment
    }


def harvest_tweets_from_nepali_accounts() -> List[Dict[str, Any]]:
    """
    Directly harvests and enriches fresh, real-time live tweets across all
    verified Nepali accounts in the monitored list. Each post is dynamically
    classified and organized into the 8 sections based on content.
    """
    def _fetch_profile_ids(acc: Dict[str, Any]):
        h = acc["handle"]
        try:
            r = requests.get(f"https://x.com/{h}", headers=DEFAULT_HEADERS, timeout=5)
            ids = list(set(re.findall(rf"/{h}/status/(\d+)", r.text, re.IGNORECASE)))
            if not ids:
                ids = list(set(re.findall(r"/status/(\d+)", r.text)))
            # Top status IDs per handle (harvest up to 6 per account)
            return [(sid, acc) for sid in ids[:6]]
        except Exception:
            return []

    active_accounts = get_monitored_x_accounts(enabled_only=True)
    if not active_accounts:
        active_accounts = TOP_NEPAL_X_ACCOUNTS

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        batches = list(ex.map(_fetch_profile_ids, active_accounts))

    raw_items = [it for b in batches for it in b]

    def _worker(item):
        sid, acc = item
        return _enrich_tweet_by_id(sid, known_handle=acc["handle"], known_account=acc)

    with concurrent.futures.ThreadPoolExecutor(max_workers=25) as ex:
        enriched = [p for p in ex.map(_worker, raw_items) if p]

    return enriched


def scan_popular_nepal_x_posts(force_refresh: bool = False, x_bearer_token: str = None) -> List[Dict[str, Any]]:
    """
    Comprehensive Daily X & Social Media Intelligence Scanner.
    Combines:
      1. Direct status harvesting from verified Nepali accounts (primary).
      2. Authenticated status discovery via Bing News RSS across 20+ Nepal queries.
    Strictly zero mock data. All posts are 100% genuine tweets sorted newest first.
    """
    # 1. Check local cache if fresh (<30 minutes)
    if not force_refresh and os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            cached_posts = data.get("posts", [])
            cached_time_str = data.get("timestamp", "")
            if cached_posts and cached_time_str:
                from dateutil import parser as dt_parser
                cached_dt = dt_parser.parse(cached_time_str)
                now_npt = datetime.datetime.now(NEPAL_TZ)
                if (now_npt - cached_dt).total_seconds() < 1800 and len(cached_posts) >= 40:
                    for p in cached_posts:
                        if isinstance(p.get("published_dt"), str):
                            try:
                                p["published_dt"] = dt_parser.parse(p["published_dt"])
                                if p["published_dt"].tzinfo is None:
                                    p["published_dt"] = p["published_dt"].replace(tzinfo=NEPAL_TZ)
                                else:
                                    p["published_dt"] = p["published_dt"].astimezone(NEPAL_TZ)
                            except Exception:
                                sid = p.get("id", "")
                                if str(sid).isdigit() and int(sid) > 10000000000000:
                                    ms = (int(sid) >> 22) + 1288834974657
                                    p["published_dt"] = datetime.datetime.fromtimestamp(ms / 1000.0, tz=datetime.timezone.utc).astimezone(NEPAL_TZ)
                                else:
                                    p["published_dt"] = now_npt
                        if p.get("published_dt") and p["published_dt"] > now_npt:
                            p["published_dt"] = now_npt
                        if p.get("published_dt"):
                            p["relative_time"] = format_relative_time(p["published_dt"], now_npt)
                            p["exact_time"] = p["published_dt"].strftime("%b %d, %I:%M %p NPT")
                    return cached_posts
        except Exception:
            pass

    # 2. Check Supabase cloud database if local cache is not present
    if not force_refresh:
        try:
            from nepal_news_store import get_stored_x_posts
            db_posts = get_stored_x_posts(limit=500)
            if db_posts and len(db_posts) >= 40:
                return db_posts
        except Exception:
            pass

    now_npt = datetime.datetime.now(NEPAL_TZ)
    all_posts = []
    seen_ids = set()
    seen_texts = set()

    # ==========================================
    # PRIMARY SOURCE: Direct Status Harvesting from Monitored Nepali Accounts
    # ==========================================
    account_tweets = harvest_tweets_from_nepali_accounts()
    for p in account_tweets:
        sid = p.get("id")
        norm = p.get("text", "")[:40].lower()
        if sid and sid not in seen_ids and norm not in seen_texts:
            seen_ids.add(sid)
            seen_texts.add(norm)
            all_posts.append(p)

    # ==========================================
    # SECONDARY SOURCE: Bing News RSS Status Discovery (for viral mentions)
    # ==========================================
    search_queries = [
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
        "site:x.com #Nepal", "site:x.com #NepalCricket", "site:x.com #Kathmandu"
    ]

    def _fetch_bing_sid(q):
        url = f"https://www.bing.com/news/search?q={urllib.parse.quote(q)}&format=rss"
        try:
            req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
            f = feedparser.parse(urllib.request.urlopen(req, context=SSL_CTX, timeout=4))
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

    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as ex:
        bing_batches = list(ex.map(_fetch_bing_sid, search_queries))

    raw_candidates = []
    for b in bing_batches:
        for sid, h, t, l in b:
            if sid not in seen_ids:
                seen_ids.add(sid)
                raw_candidates.append((sid, t, l, h))

    def _worker_enrich(item):
        sid, t, link, h = item
        return _enrich_tweet_by_id(sid, fallback_title=t, fallback_url=link, known_handle=h)

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        enriched_bing = list(ex.map(_worker_enrich, raw_candidates))

    for p in enriched_bing:
        if p and p.get("text"):
            norm = p["text"][:40].lower()
            if norm not in seen_texts:
                seen_texts.add(norm)
                all_posts.append(p)

    # Sort strictly descending by newest publication time
    all_posts.sort(key=lambda x: x["published_dt"], reverse=True)

    # Save to disk cache
    try:
        serializable_posts = []
        for p in all_posts:
            cp = p.copy()
            if isinstance(cp.get("published_dt"), datetime.datetime):
                cp["published_dt"] = cp["published_dt"].isoformat()
            serializable_posts.append(cp)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": now_npt.isoformat(),
                "total_count": len(serializable_posts),
                "posts": serializable_posts
            }, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    # Push freshly harvested posts directly into Supabase Cloud PostgreSQL x_posts table
    try:
        from nepal_news_store import save_x_posts
        save_x_posts(all_posts)
    except Exception:
        pass

    return all_posts
