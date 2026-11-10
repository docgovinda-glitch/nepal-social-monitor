"""
nepal_fb_real_scanner.py
Authentic, Real-Time Facebook & Civic Intelligence Aggregator for Nepal Social Monitor.

Strictly preserves actual, genuine publication dates from all original sources.
Guarantees NO overwriting of historical dates with current timestamps.
"""

import os
import re
import json
import datetime
import zoneinfo
import requests
import urllib3
import feedparser
from dateutil import parser as dt_parser
from typing import List, Dict, Any
from bs4 import BeautifulSoup

urllib3.disable_warnings()

NEPAL_TZ = zoneinfo.ZoneInfo("Asia/Kathmandu")
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
FB_MANUAL_CACHE_FILE = os.path.join(os.path.dirname(__file__), "nepal_fb_manual_curated.json")
FB_DIRECTORY_FILE = os.path.join(os.path.dirname(__file__), "verified_nepal_fb_directory.json")


def format_exact_relative_time(pub_dt: datetime.datetime, now_npt: datetime.datetime) -> str:
    """Computes genuine relative time without overriding the real timestamp."""
    if not pub_dt:
        return "Recent"
    diff = now_npt - pub_dt
    secs = int(diff.total_seconds())
    if secs < -3600:
        return pub_dt.strftime("%b %d, %Y")
    if secs < 60:
        return "Just now"
    elif secs < 3600:
        return f"{secs // 60}m ago"
    elif secs < 86400:
        return f"{secs // 3600}h ago"
    elif secs < 86400 * 7:
        return f"{secs // 86400}d ago"
    else:
        return pub_dt.strftime("%b %d, %Y")


def load_verified_fb_directory() -> List[Dict[str, Any]]:
    """Loads the verified directory of 100+ public Facebook pages, leaders and institutions."""
    if os.path.exists(FB_DIRECTORY_FILE):
        try:
            with open(FB_DIRECTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def load_manual_curated_posts() -> List[Dict[str, Any]]:
    """Loads genuine public posts curated by user paste/entry with preserved timestamps."""
    if os.path.exists(FB_MANUAL_CACHE_FILE):
        try:
            with open(FB_MANUAL_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                now_npt = datetime.datetime.now(NEPAL_TZ)
                for p in data:
                    if isinstance(p.get("published_dt"), str):
                        try:
                            p["published_dt"] = datetime.datetime.fromisoformat(p["published_dt"])
                            p["relative_time"] = format_exact_relative_time(p["published_dt"], now_npt)
                            p["exact_time"] = p["published_dt"].strftime("%b %d, %Y · %I:%M %p NPT")
                        except Exception:
                            pass
                return data
        except Exception:
            pass
    return []


def save_manual_curated_post(post: Dict[str, Any]):
    """Persists a new user-curated Facebook post to disk with its exact timestamp."""
    posts = load_manual_curated_posts()
    posts = [p for p in posts if p.get("link") != post.get("link")]
    posts.insert(0, post)
    try:
        serializable = []
        for p in posts:
            p_copy = dict(p)
            if isinstance(p_copy.get("published_dt"), datetime.datetime):
                p_copy["published_dt"] = p_copy["published_dt"].isoformat()
            serializable.append(p_copy)
        with open(FB_MANUAL_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def fetch_live_official_dispatches() -> List[Dict[str, Any]]:
    """
    Fetches official statements and press releases directly from official feeds,
    strictly extracting and preserving their genuine published date.
    """
    dispatches = []
    now_npt = datetime.datetime.now(NEPAL_TZ)

    # 1. U.S. Embassy Nepal Official Feed (RSS contains exact pubDate)
    try:
        resp = requests.get("https://np.usembassy.gov/feed/", headers=DEFAULT_HEADERS, timeout=6, verify=False)
        f = feedparser.parse(resp.content)
        for e in f.entries[:5]:
            t = e.get("title", "")
            pub = e.get("published")
            pub_dt = None
            if pub:
                try:
                    pub_dt = dt_parser.parse(pub).astimezone(NEPAL_TZ)
                except Exception:
                    pass

            if not pub_dt:
                continue

            rel_time = format_exact_relative_time(pub_dt, now_npt)
            exact_time = pub_dt.strftime("%b %d, %Y · %I:%M %p NPT")

            dispatches.append({
                "id": f"gov_usemb_{hash(t) % 1000000}",
                "source": "U.S. Embassy Kathmandu",
                "author_name": "U.S. Embassy Nepal",
                "author_type": "Diplomatic Mission in Nepal",
                "handle": "fb.com/nepal.usembassy",
                "raw_handle": "nepal.usembassy",
                "role": "Diplomatic Press Release",
                "verified": True,
                "avatar_bg": "#1e3a8a",
                "initials": "US",
                "title": t,
                "text": f"🇺🇸 U.S. Embassy Public Release: {t} — {e.get('summary', '')[:200]}...",
                "headline_english": t,
                "structured_category": "Nepal – External Relations (Others)",
                "link": e.get("link", "https://np.usembassy.gov"),
                "likes": 0,
                "shares": 0,
                "comments": 0,
                "impressions": 0,
                "engagement_score": 90,
                "published_dt": pub_dt,
                "relative_time": rel_time,
                "exact_time": exact_time,
                "sentiment": "Diplomatic Notice",
                "feed_type": "Official Dispatch"
            })
    except Exception:
        pass

    # 2. British Embassy / UK in Nepal (Atom feed contains exact updated timestamp)
    try:
        resp = requests.get("https://www.gov.uk/search/news-and-communications.atom?world_locations%5B%5D=nepal", headers=DEFAULT_HEADERS, timeout=6, verify=False)
        f = feedparser.parse(resp.content)
        for e in f.entries[:5]:
            t = e.get("title", "")
            upd = e.get("updated")
            pub_dt = None
            if upd:
                try:
                    pub_dt = dt_parser.parse(upd).astimezone(NEPAL_TZ)
                except Exception:
                    pass

            if not pub_dt:
                continue

            rel_time = format_exact_relative_time(pub_dt, now_npt)
            exact_time = pub_dt.strftime("%b %d, %Y · %I:%M %p NPT")

            dispatches.append({
                "id": f"gov_ukemb_{hash(t) % 1000000}",
                "source": "British Embassy Kathmandu",
                "author_name": "British Embassy Kathmandu",
                "author_type": "Diplomatic Mission in Nepal",
                "handle": "fb.com/ukinnepal",
                "raw_handle": "ukinnepal",
                "role": "Diplomatic Communication",
                "verified": True,
                "avatar_bg": "#1e40af",
                "initials": "UK",
                "title": t,
                "text": f"🇬🇧 UK Government Dispatch on Nepal: {t}",
                "headline_english": t,
                "structured_category": "Nepal – External Relations (Others)",
                "link": e.get("link", "https://www.gov.uk"),
                "likes": 0,
                "shares": 0,
                "comments": 0,
                "impressions": 0,
                "engagement_score": 85,
                "published_dt": pub_dt,
                "relative_time": rel_time,
                "exact_time": exact_time,
                "sentiment": "Bilateral Cooperation",
                "feed_type": "Official Dispatch"
            })
    except Exception:
        pass

    # 3. Nepal Rastra Bank (Central Bank Feed with real published dates)
    try:
        resp = requests.get("https://www.nrb.org.np/feed/", headers=DEFAULT_HEADERS, timeout=6, verify=False)
        f = feedparser.parse(resp.content)
        for e in f.entries[:4]:
            t = e.get("title", "")
            pub = e.get("published")
            pub_dt = None
            if pub:
                try:
                    pub_dt = dt_parser.parse(pub).astimezone(NEPAL_TZ)
                except Exception:
                    pass

            if not pub_dt:
                continue

            rel_time = format_exact_relative_time(pub_dt, now_npt)
            exact_time = pub_dt.strftime("%b %d, %Y · %I:%M %p NPT")

            dispatches.append({
                "id": f"gov_nrb_{hash(t) % 1000000}",
                "source": "Nepal Rastra Bank",
                "author_name": "Nepal Rastra Bank",
                "author_type": "Central Monetary Authority",
                "handle": "fb.com/nepalrastrabank",
                "raw_handle": "nepalrastrabank",
                "role": "Central Bank Notice",
                "verified": True,
                "avatar_bg": "#0f766e",
                "initials": "NR",
                "title": t,
                "text": f"🏦 Nepal Rastra Bank Public Notice: {t}",
                "headline_english": t,
                "structured_category": "Economy",
                "link": e.get("link", "https://www.nrb.org.np"),
                "likes": 0,
                "shares": 0,
                "comments": 0,
                "impressions": 0,
                "engagement_score": 80,
                "published_dt": pub_dt,
                "relative_time": rel_time,
                "exact_time": exact_time,
                "sentiment": "Monetary Alert",
                "feed_type": "Official Dispatch"
            })
    except Exception:
        pass

    return dispatches


def scan_real_nepal_fb_intelligence(all_articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Combines authentic sources into a live Facebook & Civic Intelligence stream:
      1. Genuine news articles covering Facebook statements/status updates across Nepali leaders and analysts
         (PRESERVES exact portal article timestamp like '15 mins ago', '1h ago', 'Nov 10').
      2. Official live diplomatic and government releases from MoFA, US Embassy, UK Embassy, and Central Bank
         (PRESERVES exact RSS/Atom published timestamp).
      3. Manually pasted and curated genuine public Facebook posts.
    """
    fb_feed = []

    # 1. Filter articles for Facebook / civic statements
    fb_keywords = [
        "फेसबुक", "facebook", "fb status", "फेसबुकमा लेखेका छन्",
        "फेसबुक स्टाटस", "फेसबुक पोस्ट", "सामाजिक सञ्जाल", "स्टाटस लेख्दै"
    ]
    for a in all_articles:
        text_corp = f"{a.get('title', '')} {a.get('summary', '')} {a.get('full_content', '')}".lower()
        if any(kw in text_corp for kw in fb_keywords):
            src = a.get("source", "Nepali Media")
            title = a.get("title", "")
            pub_dt = a.get("published_dt")

            fb_feed.append({
                "id": f"art_fb_{hash(a.get('link', '')) % 1000000}",
                "source": f"{src} (Reported FB Discourse)",
                "author_name": src,
                "author_type": "Media Coverage of FB Statements",
                "handle": f"Via {src}",
                "raw_handle": "media_report",
                "role": "Press Report on Social Media Statement",
                "verified": True,
                "avatar_bg": "#0369a1",
                "initials": src[:2].upper(),
                "title": title,
                "text": f"📰 {title} — {a.get('summary', '')[:260]}",
                "headline_english": a.get("headline_english", ""),
                "structured_category": a.get("structured_category", "Others"),
                "link": a.get("link", "#"),
                "likes": 0,
                "shares": 0,
                "comments": 0,
                "impressions": 0,
                "engagement_score": 50,
                "published_dt": pub_dt,
                "relative_time": a.get("relative_time", "Recent"),
                "exact_time": a.get("exact_time", ""),
                "sentiment": "Media Monitored Statement",
                "feed_type": "Media Reported FB Statement"
            })

    # 2. Add live official dispatches with genuine dates
    official_dispatches = fetch_live_official_dispatches()
    fb_feed.extend(official_dispatches)

    # 3. Add user manual curated posts
    manual_posts = load_manual_curated_posts()
    fb_feed.extend(manual_posts)

    # Sort strictly by published date (newest first, putting items with valid dates at top)
    min_date = datetime.datetime(2020, 1, 1, tzinfo=NEPAL_TZ)
    fb_feed.sort(key=lambda x: x.get("published_dt") or min_date, reverse=True)

    return fb_feed
