"""
nepal_config.py
Lightweight shared constants, source registries, and zero-overhead NPT timestamp formatter.
Allows UI startup and workspaces to render without importing heavy HTML/RSS scrapers.
"""

import os
import re
import datetime
import zoneinfo
from typing import Any, Dict, List

NEPAL_TZ = zoneinfo.ZoneInfo("Asia/Kathmandu")

DEFAULT_NEPAL_RELEVANCE_THRESHOLD = float(os.getenv("INDIA_MEDIA_RELEVANCE_THRESHOLD", "0.65"))
BORDERLINE_NEPAL_RELEVANCE_FLOOR = 0.40

STRUCTURED_CATEGORIES: List[str] = [
    "India Section",
    "China Section",
    "Bangladesh Section",
    "Pakistan Section",
    "Nepal – Internal",
    "Nepal – External",
    "Nepal – Economy",
    "Nepal – Others",
    "International News",
]

CATEGORY_ICONS: Dict[str, str] = {
    "India Section": "🇮🇳",
    "China Section": "🇨🇳",
    "Bangladesh Section": "🇧🇩",
    "Pakistan Section": "🇵🇰",
    "Nepal – Internal": "🇳🇵",
    "Nepal – External": "🌐",
    "Nepal – Economy": "📈",
    "Nepal – Others": "📌",
    "International News": "🌍",
}

TOP_NEPAL_NEWS_PORTALS: List[Dict[str, Any]] = [
    {"name": "eKantipur", "type": "html", "url": "https://ekantipur.com/", "alt_urls": ["https://ekantipur.com/news", "https://ekantipur.com/national", "https://ekantipur.com/business"], "x_boost_handle": "ekantipur_com", "lang": "Nepali", "category": "National Daily", "priority": "high", "check_interval_mins": 8},
    {"name": "OnlineKhabar (NP)", "type": "rss", "url": "https://www.onlinekhabar.com/feed", "alt_urls": ["https://www.onlinekhabar.com/content/news/feed"], "x_boost_handle": "Online_khabar", "lang": "Nepali", "category": "General News", "priority": "high", "check_interval_mins": 8},
    {"name": "Setopati", "type": "rss", "url": "https://www.setopati.com/feed", "alt_urls": ["https://www.setopati.com/politics/feed"], "x_boost_handle": "Setopati", "lang": "Nepali", "category": "National", "priority": "high", "check_interval_mins": 8},
    {"name": "Ratopati", "type": "rss", "url": "https://www.ratopati.com/feed", "alt_urls": ["https://www.ratopati.com/category/politics/feed"], "x_boost_handle": "Rato_pati", "lang": "Nepali", "category": "Breaking News", "priority": "high", "check_interval_mins": 8},
    {"name": "Annapurna Post", "type": "x_bridge", "x_handle": "Annapurna_Post", "target_domain": "annapurnapost.com", "url": "https://x.com/Annapurna_Post", "alt_urls": ["https://www.bing.com/news/search?q=site:annapurnapost.com&format=rss&qft=sortbydate%3d%221%22"], "lang": "Nepali", "category": "National Daily", "priority": "high", "check_interval_mins": 8},
    {"name": "Nagarik News", "type": "rss", "url": "https://nagariknews.nagariknetwork.com/feed", "alt_urls": [], "x_boost_handle": "nagarik_news", "lang": "Nepali", "category": "National Daily", "priority": "high", "check_interval_mins": 8},
    {"name": "Naya Patrika", "type": "x_bridge", "x_handle": "NAYA_PATRIKA", "target_domain": "nayapatrikadaily.com", "url": "https://x.com/NAYA_PATRIKA", "alt_urls": ["https://www.bing.com/news/search?q=site:nayapatrikadaily.com&format=rss&qft=sortbydate%3d%221%22"], "lang": "Nepali", "category": "National Daily", "priority": "high", "check_interval_mins": 8},
    {"name": "NepalKhabar", "type": "rss", "url": "https://nepalkhabar.com/feed", "alt_urls": [], "lang": "Nepali", "category": "Digital Daily", "priority": "high", "check_interval_mins": 8},
    {"name": "Gorkhapatra Online", "type": "rss", "url": "https://gorkhapatraonline.com/rss", "alt_urls": [], "lang": "Nepali", "category": "National / State", "priority": "standard", "check_interval_mins": 18},
    {"name": "News of Nepal", "type": "rss", "url": "https://newsofnepal.com/feed", "alt_urls": [], "lang": "Nepali", "category": "National Daily", "priority": "standard", "check_interval_mins": 18},
    {"name": "Nepal Press", "type": "rss", "url": "https://www.nepalpress.com/feed/", "alt_urls": [], "lang": "Nepali", "category": "Digital News", "priority": "standard", "check_interval_mins": 18},
    {"name": "Baahrakhari", "type": "rss", "url": "https://baahrakhari.com/feed", "alt_urls": [], "lang": "Nepali", "category": "National", "priority": "standard", "check_interval_mins": 18},
    {"name": "Himal Press", "type": "rss", "url": "https://himalpress.com/feed", "alt_urls": [], "lang": "Nepali", "category": "Politics & In-depth", "priority": "standard", "check_interval_mins": 18},
    {"name": "Deshsanchar", "type": "rss", "url": "https://deshsanchar.com/feed", "alt_urls": [], "lang": "Nepali", "category": "Current Affairs", "priority": "standard", "check_interval_mins": 18},
    {"name": "Shilapatra", "type": "rss", "url": "https://shilapatra.com/feed", "alt_urls": [], "lang": "Nepali", "category": "Opinion & Society", "priority": "standard", "check_interval_mins": 18},
    {"name": "Nepal Live", "type": "rss", "url": "https://nepallive.com/feed", "alt_urls": [], "lang": "Nepali", "category": "Politics", "priority": "standard", "check_interval_mins": 18},
    {"name": "Nepal Aaja", "type": "html", "url": "https://nepalaaja.com/", "alt_urls": [], "lang": "Nepali", "category": "Digital Media", "priority": "standard", "check_interval_mins": 18},
    {"name": "Nepal News", "type": "rss", "url": "https://nepalnews.com/feed", "alt_urls": [], "lang": "Nepali", "category": "Digital Daily", "priority": "standard", "check_interval_mins": 18},
    {"name": "Image Khabar", "type": "rss", "url": "https://imagekhabar.com/feed", "alt_urls": [], "lang": "Nepali", "category": "Digital Media", "priority": "standard", "check_interval_mins": 18},
    {"name": "Khabarhub (NP)", "type": "rss", "url": "https://khabarhub.com/feed/", "alt_urls": [], "lang": "Nepali", "category": "Current Affairs", "priority": "standard", "check_interval_mins": 18},
    {"name": "TechPana", "type": "rss", "url": "https://techpana.com/feed", "alt_urls": ["https://x.com/TechPanaNP", "https://www.bing.com/news/search?q=site:techpana.com&format=rss&qft=sortbydate%3d%221%22"], "x_boost_handle": "TechPanaNP", "lang": "Nepali", "category": "Tech & Innovation", "priority": "standard", "check_interval_mins": 18},
    {"name": "ArthaSarokar", "type": "rss", "url": "https://arthasarokar.com/feed", "alt_urls": [], "lang": "Nepali", "category": "Economy & Banking", "priority": "low", "check_interval_mins": 40},
    {"name": "The Kathmandu Post", "type": "rss", "url": "https://kathmandupost.com/rss", "alt_urls": ["https://kathmandupost.com/national", "https://kathmandupost.com/politics", "https://kathmandupost.com/money", "https://kathmandupost.com/valley"], "x_boost_handle": "kathmandupost", "lang": "English", "category": "National Daily", "priority": "high", "check_interval_mins": 8},
    {"name": "The Himalayan Times", "type": "x_bridge", "x_handle": "TheHimalayan", "target_domain": "thehimalayantimes.com", "url": "https://x.com/TheHimalayan", "alt_urls": ["https://thehimalayantimes.com/nepal"], "lang": "English", "category": "National Daily", "priority": "high", "check_interval_mins": 10},
    {"name": "MyRepublica", "type": "rss", "url": "https://myrepublica.nagariknetwork.com/feeds", "alt_urls": [], "lang": "English", "category": "National Daily", "priority": "standard", "check_interval_mins": 18},
    {"name": "OnlineKhabar (EN)", "type": "rss", "url": "https://english.onlinekhabar.com/feed", "alt_urls": [], "lang": "English", "category": "National", "priority": "standard", "check_interval_mins": 18},
    {"name": "The Annapurna Express", "type": "rss", "url": "https://theannapurnaexpress.com/rss", "alt_urls": [], "lang": "English", "category": "Weekly In-depth", "priority": "low", "check_interval_mins": 40},
    {"name": "Setopati (EN)", "type": "html", "url": "https://en.setopati.com/", "alt_urls": [], "lang": "English", "category": "National", "priority": "standard", "check_interval_mins": 18},
    {"name": "Rising Nepal Daily", "type": "rss", "url": "https://risingnepaldaily.com/rss", "alt_urls": [], "lang": "English", "category": "National Daily", "priority": "standard", "check_interval_mins": 18},
    {"name": "NepalKhabar (EN)", "type": "html", "url": "https://en.nepalkhabar.com/", "alt_urls": ["https://en.nepalkhabar.com/rss"], "lang": "English", "category": "Digital Daily", "priority": "standard", "check_interval_mins": 18},
    {"name": "Ratopati (EN)", "type": "rss", "url": "https://english.ratopati.com/feed", "alt_urls": [], "lang": "English", "category": "Current Affairs", "priority": "standard", "check_interval_mins": 18},
    {"name": "Khabarhub (EN)", "type": "rss", "url": "https://english.khabarhub.com/feed/", "alt_urls": [], "lang": "English", "category": "National", "priority": "standard", "check_interval_mins": 18},
    {"name": "Nepal News (EN)", "type": "rss", "url": "https://english.nepalnews.com/feed", "alt_urls": [], "lang": "English", "category": "Digital Daily", "priority": "standard", "check_interval_mins": 18},
]

ENGLISH_NEPAL_PORTAL_NAMES = frozenset(
    p["name"] for p in TOP_NEPAL_NEWS_PORTALS if p.get("lang") == "English"
) | {"Republica", "My Republica", "The Rising Nepal", "Nepal News"}

TOP_INDIAN_MEDIA_SOURCES: List[Dict[str, Any]] = [
    {"name": "The Indian Express", "type": "topic_html", "domain": "indianexpress.com", "url": "https://indianexpress.com/about/nepal/", "lang": "English", "desc": "Premier investigative & political national daily"},
    {"name": "The Hindu", "type": "search_rss", "domain": "thehindu.com", "url": "https://www.thehindu.com/news/international/", "lang": "English", "desc": "Premier broadsheet for diplomacy & foreign affairs"},
    {"name": "Hindustan Times", "type": "search_rss", "domain": "hindustantimes.com", "url": "https://www.hindustantimes.com/topic/nepal", "lang": "English", "desc": "Major national English daily covering South Asia & bilateral diplomacy"},
    {"name": "The Times of India", "type": "search_rss", "domain": "timesofindia.indiatimes.com", "url": "https://timesofindia.indiatimes.com/topic/nepal", "lang": "English", "desc": "Largest-circulation Indian English daily covering India-Nepal ties"},
    {"name": "The Economic Times", "type": "search_rss", "domain": "economictimes.indiatimes.com", "url": "https://economictimes.indiatimes.com/topic/nepal", "lang": "English", "desc": "Premier business daily covering power trade, treaties & bilateral economy"},
    {"name": "The Tribune", "type": "topic_html", "domain": "tribuneindia.com", "url": "https://www.tribuneindia.com/topic/nepal", "lang": "English", "desc": "Northern national daily covering Gorkha regiments & Himalayan borders"},
    {"name": "India Today", "type": "search_rss", "domain": "indiatoday.in", "url": "https://www.indiatoday.in/topic/nepal", "lang": "English", "desc": "Premier national broadcast & digital newsroom"},
    {"name": "ABP Live", "type": "topic_html", "domain": "abplive.com", "url": "https://news.abplive.com/topic/nepal", "lang": "English", "desc": "Major national broadcast network covering South Asian politics"},
    {"name": "NDTV", "type": "search_rss", "domain": "ndtv.com", "url": "https://www.ndtv.com/topic/nepal", "lang": "English", "desc": "Leading national broadcast & digital news network"},
    {"name": "Livemint", "type": "search_rss", "domain": "livemint.com", "url": "https://www.livemint.com/topic/nepal", "lang": "English", "desc": "Premier business daily covering bilateral trade & energy"},
    {"name": "Business Standard", "type": "topic_html", "domain": "business-standard.com", "url": "https://www.business-standard.com/topic/nepal", "lang": "English", "desc": "Leading financial daily covering treaties & hydropower"},
    {"name": "Financial Express", "type": "topic_html", "domain": "financialexpress.com", "url": "https://www.financialexpress.com/about/nepal/", "lang": "English", "desc": "Leading financial daily covering bilateral investment & infrastructure"},
    {"name": "Moneycontrol", "type": "topic_html", "domain": "moneycontrol.com", "url": "https://www.moneycontrol.com/news/tags/nepal.html", "lang": "English", "desc": "Network18 premier financial portal covering cross-border markets"},
    {"name": "Outlook India", "type": "topic_html", "domain": "outlookindia.com", "url": "https://www.outlookindia.com/topic/nepal", "lang": "English", "desc": "Premier current affairs & political analysis journal"},
    {"name": "Deccan Chronicle", "type": "search_rss", "domain": "deccanchronicle.com", "url": "https://www.deccanchronicle.com/", "lang": "English", "desc": "National daily covering foreign policy and regional developments"},
    {"name": "The Quint", "type": "search_rss", "domain": "thequint.com", "url": "https://www.thequint.com/topic/nepal", "lang": "English", "desc": "Independent digital journalism & South Asia fact-checking"},
    {"name": "Swarajya", "type": "topic_html", "domain": "swarajyamag.com", "url": "https://swarajyamag.com/topic/nepal", "lang": "English", "desc": "Strategic affairs, defense & Himalayan geopolitics analysis"},
    {"name": "OneIndia", "type": "search_rss", "domain": "oneindia.com", "url": "https://www.oneindia.com/topic/nepal", "lang": "English", "desc": "Major digital news network covering regional developments"},
    {"name": "ANI News", "type": "search_rss", "domain": "aninews.in", "url": "https://www.aninews.in/topic/nepal/", "lang": "English", "desc": "Premier South Asian multimedia news wire covering India-Nepal diplomacy & security"},
    {"name": "PTI", "type": "search_rss", "domain": "ptinews.com", "url": "https://www.ptinews.com/", "lang": "English", "desc": "Press Trust of India national wire agency covering bilateral policy & border affairs"},
    {"name": "The Print", "type": "search_rss", "domain": "theprint.in", "url": "https://theprint.in/tag/nepal/", "lang": "English", "desc": "National policy, diplomacy & defense digital publication"},
    {"name": "The Wire", "type": "search_rss", "domain": "thewire.in", "url": "https://thewire.in/tag/nepal", "lang": "English", "desc": "Independent South Asia foreign affairs & political analysis"},
    {"name": "WION", "type": "search_rss", "domain": "wionews.com", "url": "https://www.wionews.com/south-asia", "lang": "English", "desc": "Global broadcast network tracking South Asian geopolitics"},
    {"name": "Firstpost", "type": "search_rss", "domain": "firstpost.com", "url": "https://www.firstpost.com/tag/nepal", "lang": "English", "desc": "Digital news & geopolitics platform covering Himalayan affairs"},
    {"name": "Deccan Herald", "type": "search_rss", "domain": "deccanherald.com", "url": "https://www.deccanherald.com/tags/nepal", "lang": "English", "desc": "Major national daily covering South Asia & bilateral diplomacy"},
    {"name": "News18", "type": "search_rss", "domain": "news18.com", "url": "https://www.news18.com/topics/nepal/", "lang": "English", "desc": "Network18 national broadcast & digital newsroom"},
    {"name": "Amar Ujala", "type": "topic_html", "domain": "amarujala.com", "url": "https://www.amarujala.com/tags/nepal", "lang": "Hindi", "desc": "Leading Hindi daily covering UP/Uttarakhand-Nepal border"},
    {"name": "Live Hindustan", "type": "topic_html", "domain": "livehindustan.com", "url": "https://www.livehindustan.com/tags/nepal/", "lang": "Hindi", "desc": "Hindustan Times Media premier Hindi daily"},
    {"name": "Dainik Jagran", "type": "search_rss", "domain": "jagran.com", "url": "https://www.jagran.com/topics/nepal", "lang": "Hindi", "desc": "Largest Hindi daily covering Bihar/UP-Nepal border & diplomacy"},
    {"name": "Navbharat Times", "type": "search_rss", "domain": "navbharattimes.indiatimes.com", "url": "https://navbharattimes.indiatimes.com/topics.cms?query=nepal", "lang": "Hindi", "desc": "Times Group premier Hindi daily covering Himalayan & bilateral affairs"},
    {"name": "Jansatta", "type": "search_rss", "domain": "jansatta.com", "url": "https://www.jansatta.com/about/nepal/", "lang": "Hindi", "desc": "Indian Express Group leading Hindi national daily"},
    {"name": "Prabhat Khabar", "type": "topic_html", "domain": "prabhatkhabar.com", "url": "https://www.prabhatkhabar.com/topic/nepal", "lang": "Hindi", "desc": "Leading Hindi daily covering Bihar-Nepal border region"},
    {"name": "Aaj Tak", "type": "search_rss", "domain": "aajtak.in", "url": "https://www.aajtak.in/topic/nepal", "lang": "Hindi", "desc": "India Today Group flagship Hindi broadcast & digital newsroom"},
    {"name": "Dainik Bhaskar", "type": "search_rss", "domain": "bhaskar.com", "url": "https://www.bhaskar.com/", "lang": "Hindi", "desc": "Largest-circulation Hindi daily covering national & border developments"},
]

_DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")


def _has_devanagari(text: str) -> bool:
    return bool(text and _DEVANAGARI_RE.search(text))


def parse_to_nepal_time(raw_date_val: Any, now_npt: datetime.datetime):
    """Fast timestamp converter to Nepal Standard Time (avoids heavy parser imports on datetime objects)."""
    if not raw_date_val:
        fallback_dt = now_npt - datetime.timedelta(days=7)
        return fallback_dt, "Date unlisted", "Archived"

    try:
        if isinstance(raw_date_val, datetime.datetime):
            dt = raw_date_val
        else:
            from dateutil import parser as dt_parser
            clean_str = re.sub(r"\[IST\]|IST", "+0530", str(raw_date_val))
            clean_str = re.sub(r"Updated\s*:\s*|Updated On\s*:\s*|Published\s*:\s*|By[^\d]+", "", clean_str)
            clean_str = clean_str.replace("|", " ")
            dt = dt_parser.parse(clean_str, fuzzy=True)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=NEPAL_TZ)
        else:
            dt = dt.astimezone(NEPAL_TZ)

        seconds = (now_npt - dt).total_seconds()
        if seconds < -86400:
            # Reject clearly far-future dates (>1 day ahead of now_npt)
            dt = now_npt
            seconds = 0
            rel_time = "Just now"
        elif seconds < 120:
            rel_time = "Just now"
        elif seconds < 3600:
            rel_time = f"{int(seconds / 60)} mins ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            mins = int((seconds % 3600) / 60)
            rel_time = f"{hours}h {mins}m ago" if mins > 0 else f"{hours}h ago"
        else:
            rel_time = f"{int(seconds / 86400)}d ago"

        return dt, rel_time, dt.strftime("%b %d, %I:%M %p NPT")
    except Exception:
        fallback_dt = now_npt - datetime.timedelta(days=7)
        return fallback_dt, "Date unlisted", "Archived"


def format_exc(exc: BaseException, limit: int = 300) -> str:
    """Formats an exception consistently so TimeoutError and message-less errors are never blank."""
    msg = str(exc).strip()
    cls = type(exc).__name__
    text = f"{cls}: {msg}" if msg else cls
    return text[:limit] if limit and len(text) > limit else text
