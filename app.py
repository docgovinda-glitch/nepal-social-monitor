"""
app.py
Interactive Nepal Social Media, Nepali Media (Top 34 Portals), and Nepal in Indian Media Monitor.
Includes:
- Date and Time Picker Filter (From selected timestamp up to current moment in NPT)
- 8 Structured Classification Categories
- 34 Top Nepali and English News Portals
- Dedicated Nepal in Indian Media Menu
- Live X (Twitter) Feeds
- CSV / Excel Export with Timestamps and Categories
"""

import streamlit as st
import pandas as pd
import datetime
import time
import urllib.parse
import html
import re
import os
from typing import Any, Callable, Dict, List
from nepal_fetcher import (
    fetch_top_nepal_media,
    fetch_nepal_in_indian_media,
    evaluate_indian_article_nepal_relevance,
    parse_to_nepal_time,
    batch_fetch_full_content,
    DEFAULT_NEPAL_RELEVANCE_THRESHOLD,
    BORDERLINE_NEPAL_RELEVANCE_FLOOR,
    NEPAL_TZ,
    STRUCTURED_CATEGORIES,
    CATEGORY_ICONS,
    TOP_NEPAL_NEWS_PORTALS,
    TOP_INDIAN_MEDIA_SOURCES,
)
from nepal_x_scanner import scan_popular_nepal_x_posts, TOP_NEPAL_X_ACCOUNTS
from nepal_news_store import (
    get_all_source_health,
    get_system_kpis,
    set_source_enabled,
    set_source_interval,
    get_stored_articles,
    get_stored_indian_articles,
    get_indian_media_audit_stats
)
from nepal_news_scheduler import (
    run_single_source_discovery,
    run_all_sources_discovery,
    run_historical_backfill,
    start_monitoring_daemon
)
from apple_theme import APPLE_DESIGN_SYSTEM_CSS, AUTH_CSS

# Start background news monitoring daemon if not already running
try:
    start_monitoring_daemon()
except Exception:
    pass


# Load environment variables from .env if present
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip("'\""))

load_env()

# 1. Page Configuration
st.set_page_config(
    page_title="Nepal Media & Geo-Political Intelligence Dashboard",
    page_icon="🇳🇵",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Apple-grade design system (tokens + components live in apple_theme.py)
st.markdown(APPLE_DESIGN_SYSTEM_CSS, unsafe_allow_html=True)

# ==========================================
# AUTHENTICATION GATEWAY (PASSWORD PROTECTION)
# ==========================================
APP_PASSWORD = os.getenv("APP_PASSWORD", "PIC@55")

def check_password() -> bool:
    """Returns True if the user entered the correct password or has a persisted session cookie/token."""
    # 1. Already authenticated in active memory
    if st.session_state.get("authenticated", False):
        return True

    # 2. Check URL query params for persistent token/key
    query_auth = st.query_params.get("auth", "")
    query_key = st.query_params.get("key", "")
    if query_auth == "true" or query_key == APP_PASSWORD:
        st.session_state["authenticated"] = True
        return True

    st.markdown(AUTH_CSS, unsafe_allow_html=True)
    with st.form("auth_form", clear_on_submit=False):
        st.markdown("""
        <div class="auth-header">
            <div class="auth-header__flag">🇳🇵</div>
            <h1 class="auth-header__title">Media Monitor</h1>
            <p class="auth-header__subtitle">News Intelligence Platform</p>
        </div>
        """, unsafe_allow_html=True)
        pwd = st.text_input("Password", type="password", placeholder="Password", label_visibility="collapsed")
        submit = st.form_submit_button("Unlock", width="stretch", type="primary")
        st.markdown('<div class="auth-footer">Secure access · Authorised users only</div>', unsafe_allow_html=True)

    if submit:
        if pwd.strip() == APP_PASSWORD:
            st.session_state["authenticated"] = True
            st.query_params["auth"] = "true"
            st.rerun()
        else:
            st.error("Incorrect password. Please try again.")

    st.stop()

check_password()

# 3. Time Reference
now_npt = datetime.datetime.now(NEPAL_TZ)
formatted_now_time = now_npt.strftime("%I:%M %p NPT").lstrip("0")
past_12h_ref = now_npt - datetime.timedelta(hours=12)
default_start_date = past_12h_ref.date()
default_start_time = past_12h_ref.time().replace(second=0, microsecond=0)
st.session_state.setdefault("last_sync_npt", now_npt.strftime("%I:%M %p").lstrip("0"))
st.session_state.setdefault("cp_timeframe_segment", "12h")

# ==========================================
# 4. TIME WINDOW
# Presets (12h / 24h / Today) always run up to "now".
# "Custom" exposes start/end pickers plus an "Up to now" toggle.
# ==========================================
TIMEFRAME_PRESETS = ["12h", "24h", "Today", "Custom"]
PAGE_SIZE = 20

def _preset_start(preset: str, ref: datetime.datetime) -> datetime.datetime:
    if preset == "24h":
        return ref - datetime.timedelta(hours=24)
    if preset == "Today":
        return ref.replace(hour=0, minute=0, second=0, microsecond=0)
    return ref - datetime.timedelta(hours=12)

def on_timeframe_preset_change():
    # Segmented control can be deselected; fall back to the default preset.
    if not st.session_state.get("cp_timeframe_segment"):
        st.session_state["cp_timeframe_segment"] = "12h"
    preset = st.session_state["cp_timeframe_segment"]
    if preset != "Custom":
        start = _preset_start(preset, datetime.datetime.now(NEPAL_TZ))
        st.session_state["filter_start_date"] = start.date()
        st.session_state["filter_start_time"] = start.time().replace(second=0, microsecond=0)

active_preset = st.session_state.get("cp_timeframe_segment") or "12h"
if active_preset == "Custom":
    filter_start_dt = datetime.datetime.combine(
        st.session_state.get("filter_start_date", default_start_date),
        st.session_state.get("filter_start_time", default_start_time),
        tzinfo=NEPAL_TZ,
    )
    is_to_current = st.session_state.get("filter_use_current_time", True)
else:
    filter_start_dt = _preset_start(active_preset, now_npt)
    is_to_current = True

if is_to_current:
    filter_end_dt = now_npt
else:
    filter_end_dt = datetime.datetime.combine(
        st.session_state.get("filter_end_date", now_npt.date()),
        st.session_state.get("filter_end_time", now_npt.time().replace(second=0, microsecond=0)),
        tzinfo=NEPAL_TZ,
    )
    if filter_end_dt < filter_start_dt:
        filter_end_dt = filter_start_dt + datetime.timedelta(hours=1)

def fmt_short(dt: datetime.datetime) -> str:
    return dt.strftime("%d %b, %I:%M %p").lstrip("0")

window_label = f"{fmt_short(filter_start_dt)} → {'Now' if is_to_current else fmt_short(filter_end_dt)}"

# Filter option constants (single source of truth)
CAT_FILTER_ALL_UNFILTERED = "🌐 All News"
CAT_FILTER_ALL_8 = "📂 Classified"
CAT_FILTER_UNCATEGORIZED = "⚪ Unclassified"
CATEGORY_FILTER_OPTIONS = [
    CAT_FILTER_ALL_UNFILTERED,
    CAT_FILTER_ALL_8,
    CAT_FILTER_UNCATEGORIZED,
] + [f"{CATEGORY_ICONS.get(c, '📌')} {c}" for c in STRUCTURED_CATEGORIES]

ALL_PORTALS_DEFAULT = f"All Portals ({len(TOP_NEPAL_NEWS_PORTALS)})"
ALL_INDIAN_DEFAULT = f"All {len(TOP_INDIAN_MEDIA_SOURCES)} Indian Outlets"
ALL_LANG_DEFAULT = "All Languages"
ALL_ACC_TYPES = "All Account Types"
NEPALI_PORTAL_NAMES = sorted({p["name"] for p in TOP_NEPAL_NEWS_PORTALS})
INDIAN_OUTLET_NAMES = sorted({s["name"] for s in TOP_INDIAN_MEDIA_SOURCES})
india_rel_threshold = DEFAULT_NEPAL_RELEVANCE_THRESHOLD

def reset_all_filters():
    start = _preset_start("12h", datetime.datetime.now(NEPAL_TZ))
    st.session_state.update({
        "global_search_input": "",
        "np_cat_filter": CAT_FILTER_ALL_UNFILTERED,
        "np_portal_filter": ALL_PORTALS_DEFAULT,
        "np_lang_filter": ALL_LANG_DEFAULT,
        "in_outlet_filter": ALL_INDIAN_DEFAULT,
        "in_lang_filter": ALL_LANG_DEFAULT,
        "x_cat_filter_select": CAT_FILTER_ALL_UNFILTERED,
        "x_acc_type_select": ALL_ACC_TYPES,
        "cp_timeframe_segment": "12h",
        "filter_start_date": start.date(),
        "filter_start_time": start.time().replace(second=0, microsecond=0),
        "filter_use_current_time": True,
        "media_visible_count": PAGE_SIZE,
        "indian_visible_count": PAGE_SIZE,
        "x_visible_count": PAGE_SIZE,
    })

# Silent background credentials for Twitter API
default_bearer = os.getenv("TWITTER_BEARER_TOKEN", "")
try:
    if not default_bearer and hasattr(st, "secrets"):
        default_bearer = st.secrets.get("TWITTER_BEARER_TOKEN", "")
except Exception:
    pass
x_bearer_token = default_bearer

# 6. High-Performance Cached Data Pipeline (5-minute TTL, sub-second reload)
@st.cache_data(ttl=300, show_spinner=False)
def get_cached_nepal_media():
    """Fetches and caches Nepali media with 5-minute TTL. Instant load on filter/tab changes."""
    return fetch_top_nepal_media(max_workers=25)

@st.cache_data(ttl=300, show_spinner=False)
def get_cached_indian_media():
    """Fetches and caches Nepal-relevant Indian media with 5-minute TTL."""
    return fetch_nepal_in_indian_media(max_workers=18)

@st.cache_data(ttl=300, show_spinner=False)
def get_cached_x_posts(bearer_token: str = ""):
    """Fetches and caches X posts with 5-minute TTL."""
    return scan_popular_nepal_x_posts(force_refresh=False, x_bearer_token=bearer_token)

all_articles = get_cached_nepal_media()
indian_articles = get_cached_indian_media()

if "x_posts" not in st.session_state or not st.session_state.get("x_posts") or not any(p.get("is_real_api") for p in st.session_state.get("x_posts", [])):
    st.session_state["x_posts"] = get_cached_x_posts(x_bearer_token)
all_x_posts = st.session_state["x_posts"]

# Apply Date & Time Range Filter across ALL channels
MIN_DATE = datetime.datetime(2020, 1, 1, tzinfo=NEPAL_TZ)

def in_window(item: Dict[str, Any]) -> bool:
    pdt = item.get("published_dt")
    return isinstance(pdt, datetime.datetime) and filter_start_dt <= pdt <= filter_end_dt

def merge_stored(live_items: List[Dict[str, Any]], stored_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Reconciles live-fetched items with the persistent store so the window is complete."""
    seen = {a.get("canonical_id") or a.get("link") for a in live_items}
    for it in stored_items:
        key = it.get("canonical_id") or it.get("link")
        if key and key not in seen and in_window(it):
            _, it["relative_time"], it["exact_time"] = parse_to_nepal_time(it["published_dt"], now_npt)
            live_items.append(it)
            seen.add(key)
    return live_items

filtered_articles = [a for a in all_articles if in_window(a)]
filtered_indian = [a for a in indian_articles if in_window(a)]
filtered_x_posts = [p for p in all_x_posts if in_window(p)]

try:
    filtered_articles = merge_stored(filtered_articles, get_stored_articles(start_dt=filter_start_dt, end_dt=filter_end_dt, limit=5000))
except Exception:
    pass
try:
    filtered_indian = merge_stored(filtered_indian, get_stored_indian_articles(status_filter="substantive", limit=2000))
except Exception:
    pass

for _feed in (filtered_articles, filtered_indian, filtered_x_posts):
    _feed.sort(key=lambda x: x.get("published_dt") or MIN_DATE, reverse=True)

# ==========================================
# CATEGORY TAXONOMY (one alias map + one slug map for badges & accents)
# ==========================================
CATEGORY_ALIASES = {
    "India in Nepal": "India Section",
    "China in Nepal": "China Section",
    "Pakistan in Nepal": "Pakistan Section",
    "Bangladesh in Nepal": "Bangladesh Section",
    "Nepal – Internal Politics": "Nepal – Internal",
    "Nepal – External Relations (Others)": "Nepal – External",
    "Economy": "Nepal – Economy",
    "Others": "Nepal – Others",
}
CATEGORY_SLUGS = {
    "India Section": "india",
    "China Section": "china",
    "Pakistan Section": "pakistan",
    "Bangladesh Section": "bangladesh",
    "Nepal – Internal": "internal",
    "Nepal – External": "external",
    "Nepal – Economy": "economy",
    "Nepal – Others": "others",
    "International News": "international",
}

def canonical_category(cat: str) -> str:
    return CATEGORY_ALIASES.get(cat, cat)

def category_slug(cat: str) -> str:
    return CATEGORY_SLUGS.get(canonical_category(cat), "others")

def get_badge_html(cat: str) -> str:
    cat = canonical_category(cat)
    icon = CATEGORY_ICONS.get(cat, "📌")
    return f'<span class="cat-badge cat-badge--{category_slug(cat)}">{icon} {html.escape(cat)}</span>'

def compact_number(n: int) -> str:
    return f"{n / 1000:.1f}K" if n >= 1000 else str(n)

def time_badge_html(rel_time: str, exact_time: str) -> str:
    rel_time, exact_time = html.escape(str(rel_time or "")), html.escape(str(exact_time or ""))
    if rel_time and exact_time and rel_time not in exact_time:
        label = f"{rel_time} · {exact_time}"
    else:
        label = exact_time or rel_time or "Recent"
    return f'<span class="time-badge">{label}</span>'


# Article Card Renderer
def render_apple_article_card(item: Dict[str, Any], is_indian: bool = False) -> str:
    source_name = html.escape(item.get("source", "Unknown"))
    cat = item.get("primary_section") or item.get("structured_category", "Nepal – Others")

    if is_indian:
        accent = "indian-press"
        source_tag = f'<span class="indian-portal-tag">🇮🇳 {source_name}</span>'
        pct = int(round(float(item.get("nepal_relevance_score", 0.75)) * 100))
        reason = html.escape(str(item.get("relevance_reason", "Substantive Nepal connection")))
        if item.get("relevance_status") == "borderline_review":
            review_flag = f'<span class="conf-review-badge" title="{reason}">Borderline · {pct}% relevance</span>'
        else:
            review_flag = f'<span class="pill pill--success" title="{reason}">{pct}% Nepal relevance</span>'
    else:
        accent = category_slug(cat)
        source_tag = f'<span class="portal-tag">{source_name}</span>'
        review_flag = '<span class="conf-review-badge" title="Classification confidence below 0.60 — pending editorial verification">Needs review</span>' if item.get("low_confidence") else ""

    # Secondary tags & Nepal thematic dimensions
    sec_tags = list(item.get("secondary_tags") or [])
    if is_indian:
        sec_tags = [d for d in (item.get("nepal_dimensions") or []) if d not in sec_tags] + sec_tags
    sec_tags_html = ""
    if sec_tags:
        chips = "".join(f'<span class="sec-tag-chip">#{html.escape(str(t))}</span>' for t in sec_tags[:5])
        sec_tags_html = f'<div class="chip-row">{chips}</div>'

    lang = item.get("language", "")
    lang_badge = f'<span class="pill">{html.escape(lang)}</span>' if lang else ""

    raw_title = item.get("title", "")
    summary = (item.get("summary") or "").strip()
    summary_html = f'<p class="apple-card-summary">{html.escape(summary)}</p>' if summary and summary != raw_title.strip() else ""
    link = html.escape(item.get("link", "#"), quote=True)
    cta = "Read in Indian press ↗" if is_indian else "Read story ↗"

    return (
        f'<article class="apple-news-card accent--{accent}">'
        f'<header class="apple-card-meta">{source_tag}{get_badge_html(cat)}{review_flag}{lang_badge}'
        f'{time_badge_html(item.get("relative_time", "Recent"), item.get("exact_time", ""))}</header>'
        f'<h3 class="apple-card-title"><a href="{link}" target="_blank" rel="noopener noreferrer">{html.escape(raw_title)}</a></h3>'
        f'{summary_html}{sec_tags_html}'
        f'<footer class="apple-card-footer"><a href="{link}" target="_blank" rel="noopener noreferrer" class="apple-card-cta">{cta}</a></footer>'
        f'</article>'
    )

# X (Twitter) Post Card Renderer
def render_apple_x_post_card(p: Dict[str, Any]) -> str:
    avatar_bg = html.escape(p.get("avatar_bg", "#1D9BF0"))
    initials = html.escape(p.get("initials", "X"))
    author_name = html.escape(p.get("author_name", "Author"))
    handle = html.escape(p.get("handle", "@handle"))
    author_type = html.escape(p.get("author_type", "Public Figure"))
    verified_mark = ' <span class="x-verified-badge" title="Verified account">✓</span>' if p.get("verified") else ""

    text = html.escape(p.get("text", ""), quote=False)
    text = re.sub(r'(#[A-Za-z0-9_]+)', r'<b>\1</b>', text).replace("\n", "<br>")

    sentiment = p.get("sentiment", "Neutral")
    if "Alert" in sentiment or "Critical" in sentiment:
        senti_class = "x-sentiment-alert"
    elif "Positive" in sentiment:
        senti_class = "x-sentiment-positive"
    else:
        senti_class = ""

    raw_handle = p.get("raw_handle") or p.get("handle", "").lstrip("@").split(" ")[0].strip()
    orig_link = p.get("link", "#")
    if p.get("is_real_api") and orig_link and "/status/" in orig_link:
        link, cta_label = orig_link, "View post on X ↗"
    elif raw_handle and raw_handle not in ("LiveSearch", "Author"):
        link, cta_label = f"https://x.com/{raw_handle}", f"View @{raw_handle} on X ↗"
    else:
        link, cta_label = (orig_link if orig_link != "#" else "https://x.com"), "View on X ↗"
    link = html.escape(link, quote=True)

    metrics = "".join(
        f'<span class="x-metric-item" title="{label}">{icon} {compact_number(int(p.get(key, 0) or 0))}</span>'
        for key, icon, label in (("likes", "♥", "Likes"), ("retweets", "↻", "Reposts"), ("replies", "💬", "Replies"), ("impressions", "◉", "Views"))
    )

    return (
        f'<article class="x-post-card">'
        f'<header class="x-post-header">'
        f'<div class="x-author-box"><div class="x-avatar" style="background:{avatar_bg};">{initials}</div>'
        f'<div class="x-author-meta"><span class="x-author-name">{author_name}{verified_mark}</span>'
        f'<span class="x-author-handle">{handle} · <span class="x-type-badge">{author_type}</span></span></div></div>'
        f'<div class="x-post-header__meta">{get_badge_html(p.get("structured_category", "Others"))}'
        f'{time_badge_html(p.get("relative_time", "Recent"), p.get("exact_time", ""))}</div>'
        f'</header>'
        f'<div class="x-post-text">{text}</div>'
        f'<footer class="x-engagement-bar">'
        f'<div class="x-metrics-group">{metrics}<span class="x-sentiment-badge {senti_class}">{html.escape(sentiment)}</span></div>'
        f'<a href="{link}" target="_blank" rel="noopener noreferrer" class="x-cta-link">{cta_label}</a>'
        f'</footer>'
        f'</article>'
    )

# ==========================================
# SHARED UI COMPONENTS
# ==========================================
def render_page_header(title: str, subtitle: str = "", show_window: bool = True) -> None:
    """Large-title page header used by every workspace for a consistent hierarchy."""
    sub = f'<p class="page-header__subtitle">{subtitle}</p>' if subtitle else ""
    meta = f'<div class="page-header__meta"><span class="pill pill--tint">🕒 {html.escape(window_label)}</span></div>' if show_window else ""
    st.markdown(
        f'<div class="page-header"><div><h2 class="page-header__title">{html.escape(title)}</h2>{sub}</div>{meta}</div>',
        unsafe_allow_html=True,
    )

def render_empty_state(icon: str, title: str, body: str) -> None:
    st.markdown(
        f'<div class="empty-state"><div class="empty-state__icon">{icon}</div>'
        f'<p class="empty-state__title">{html.escape(title)}</p><p class="empty-state__body">{html.escape(body)}</p></div>',
        unsafe_allow_html=True,
    )

def sidebar_section(title: str, badge: str = "") -> None:
    badge_html = f'<span class="sb-section__badge">{html.escape(badge)}</span>' if badge else ""
    st.markdown(f'<div class="sb-section"><span class="sb-section__title">{html.escape(title)}</span>{badge_html}</div>', unsafe_allow_html=True)

def render_paginated_feed(items: List[Dict[str, Any]], state_key: str, renderer: Callable[[Dict[str, Any]], str], noun: str) -> None:
    """Renders items PAGE_SIZE at a time with a single 'Show more' control."""
    st.session_state.setdefault(state_key, PAGE_SIZE)
    limit = st.session_state[state_key]
    st.markdown("".join(renderer(it) for it in items[:limit]), unsafe_allow_html=True)

    remaining = len(items) - limit
    if remaining > 0:
        _, mid, _ = st.columns([1.5, 2, 1.5])
        with mid:
            if st.button(f"Show {min(PAGE_SIZE, remaining)} more {noun}", width="stretch", key=f"btn_more_{state_key}"):
                st.session_state[state_key] += PAGE_SIZE
                st.rerun()
            st.caption(f"Showing {limit:,} of {len(items):,} {noun}")
    elif items:
        st.caption(f"You're all caught up · {len(items):,} {noun}")

# ==========================================
# BILINGUAL & CROSS-LINGUAL SEARCH ENGINE
# ==========================================
SEARCH_EXPANSIONS = {
    # Key Political Figures & Leaders
    'balen': ['balen', 'बालेन', 'बालेन्द्र'],
    'oli': ['oli', 'ओली', 'केपी'],
    'prachanda': ['prachanda', 'प्रचण्ड', 'दाहाल', 'पुष्पकमल'],
    'deuba': ['deuba', 'देउवा', 'शेरबहादुर'],
    'gagan': ['gagan', 'गगन', 'थापा'],
    'rabi': ['rabi', 'रवि', 'लामिछाने'],
    'swarnim': ['swarnim', 'स्वर्णिम', 'वाग्ले'],
    'kulman': ['kulman', 'कुलमान', 'घिसिङ'],
    'harka': ['harka', 'हर्क', 'साम्पाङ'],
    'bhim': ['bhim', 'भीम', 'रावल'],
    'madhav': ['madhav', 'माधव', 'नेपाल'],
    'upendra': ['upendra', 'उपेन्द्र', 'यादव'],
    'baburam': ['baburam', 'बाबुराम', 'भट्टराई'],
    'sunita': ['sunita', 'सुनिता', 'डंगोल'],
    'shekhar': ['shekhar', 'शेखर', 'कोइराला'],
    'ishwar': ['ishwar', 'ईश्वर', 'पोखरेल'],
    
    # Geopolitics & Foreign Relations
    'india': ['india', 'भारत', 'भारतीय', 'मोदी', 'delhi'],
    'china': ['china', 'चीन', 'चिनियाँ', 'बेइजिङ', 'beijing', 'शी'],
    'pakistan': ['pakistan', 'पाकिस्तान', 'पाकिस्तानी', 'इस्लामाबाद'],
    'bangladesh': ['bangladesh', 'बंगलादेश', 'ढाका', 'हसिना', 'युनुस'],
    'us': ['usa', 'america', 'अमेरिकी', 'अमेरिका', 'ट्रम्प', 'वाशिङ्टन', 'वाशिंगटन', 'दूतावास'],
    'uk': ['britain', 'british', 'बेलायत', 'बेलायती'],
    'border': ['border', 'सीमा', 'सिमाना', 'नाका', 'लिपुलेक', 'कालापानी', 'सुस्ता'],
    'treaty': ['treaty', 'सन्धि', 'सम्झौता', 'सहमति'],
    
    # Economy, Finance & Infrastructure
    'economy': ['economy', 'अर्थतन्त्र', 'बजेट', 'आर्थिक', 'बैंकिङ', 'मुद्रा', 'राजस्व'],
    'budget': ['budget', 'बजेट', 'विनियोजन', 'खर्च'],
    'inflation': ['inflation', 'महँगी', 'मूल्यवृद्धि'],
    'remittance': ['remittance', 'रेमिट्यान्स', 'विप्रेषण'],
    'trade': ['trade', 'व्यापार', 'निर्यात', 'आयात', 'भन्सार'],
    'bank': ['bank', 'बैंक', 'राष्ट्र बैंक', 'मौद्रिक', 'कर्जा'],
    'nea': ['nea', 'विद्युत', 'विद्युत्', 'प्राधिकरण', 'लोडसेडिङ', 'डेडिकेटेड'],
    'police': ['police', 'प्रहरी', 'नेपाल प्रहरी', 'सीआईबी', 'ब्युरो'],
    
    # Civic, Society, Sports & Festivals
    'cricket': ['cricket', 'क्रिकेट', 'npl', 'क्यान', 'पारस'],
    'football': ['football', 'फुटबल', 'साफ', 'एन्फा'],
    'tihar': ['tihar', 'तिहार', 'दिपावली', 'भाइटीका', 'लक्ष्मीपूजा'],
    'dashain': ['dashain', 'दसैँ', 'दशैं', 'विजया'],
    'chhath': ['chhath', 'छठ', 'सूर्य'],
    'court': ['court', 'अदालत', 'सर्वोच्च', 'न्यायाधीश'],
    'corruption': ['corruption', 'भ्रष्टाचार', 'सहकारी', 'ठगी', 'अख्तियार'],
    'election': ['election', 'निर्वाचन', 'उपनिर्वाचन', 'मतदान'],
}

def smart_search_match(item: Dict[str, Any], query: str) -> bool:
    """
    High-performance bilingual, multi-token matching function.
    Searches across title, summary, full content, translated headlines,
    source outlet, author name, handle, role, hashtags, and category.
    Supports cross-lingual expansion between English and Nepali.
    """
    if not query or not query.strip():
        return True

    parts = [
        item.get("title", ""),
        item.get("headline_english", ""),
        item.get("summary", ""),
        item.get("full_content", ""),
        item.get("text", ""),
        item.get("source", ""),
        item.get("author_name", ""),
        item.get("handle", ""),
        item.get("role", ""),
        item.get("structured_category", ""),
        item.get("sentiment", ""),
        item.get("feed_type", "")
    ]
    text_corpus = " ".join(str(p) for p in parts if p).lower()

    tokens = [t.strip().lower() for t in query.strip().split() if t.strip()]
    if not tokens:
        return True

    for token in tokens:
        synonyms = [token]
        for key, syn_list in SEARCH_EXPANSIONS.items():
            if token == key or token in syn_list:
                synonyms.extend(syn_list)
        synonyms = list(set(synonyms))

        if not any(syn in text_corpus for syn in synonyms):
            return False

    return True

# ==========================================
# UNIFIED GLOBAL FILTER PIPELINE
# Seamlessly integrates across:
# 1. Nepali Media (34 Portals)
# 2. Nepal in Indian Media (18 Outlets)
# 3. Verified Live X (Twitter) Posts
# ==========================================

PREDEFINED_9_CATEGORIES = set(STRUCTURED_CATEGORIES)
CORE_8_CATEGORIES = PREDEFINED_9_CATEGORIES - {"Nepal – Others"}
UNASSIGNED_VALUES = {"", "uncategorized", "none", "null", "unassigned"}

def filter_items_by_category(items: list, selected_option: str, is_social: bool = False) -> list:
    """
    Editorial category filter shared by every feed:
      • All News      → everything, regardless of category
      • Classified    → items in any of the 9 editorial sections
      • Unclassified  → unassigned / general items
      • A section     → items whose primary OR cross-listed section matches
    """
    if not items or not selected_option or selected_option == CAT_FILTER_ALL_UNFILTERED:
        return items

    def primary_of(it):
        return canonical_category(str(it.get("primary_section") or it.get("structured_category") or it.get("category") or "").strip())

    def in_sections(it):
        return any(canonical_category(s) in PREDEFINED_9_CATEGORIES for s in it.get("sections", []))

    if selected_option == CAT_FILTER_ALL_8:
        allowed = CORE_8_CATEGORIES if is_social else PREDEFINED_9_CATEGORIES
        return [it for it in items if primary_of(it).lower() not in UNASSIGNED_VALUES
                and (primary_of(it) in allowed or (not is_social and in_sections(it)))]

    if selected_option == CAT_FILTER_UNCATEGORIZED:
        res = []
        for it in items:
            cat = primary_of(it)
            if cat.lower() in UNASSIGNED_VALUES:
                res.append(it)
            elif is_social and cat == "Nepal – Others":
                res.append(it)
            elif not is_social and cat not in PREDEFINED_9_CATEGORIES and not in_sections(it):
                res.append(it)
        return res

    target = canonical_category(selected_option.split(" ", 1)[1] if " " in selected_option else selected_option)
    return [
        it for it in items
        if primary_of(it) == target or target in {canonical_category(s) for s in (it.get("sections") or [])}
    ]

# ==========================================
# 5. APP HEADER (frosted glass)
# ==========================================
st.markdown(f"""
<div class="app-header">
    <div class="app-header__brand">
        <span class="app-header__flag">🇳🇵</span>
        <div>
            <h1 class="app-header__title">Nepal Media Monitor</h1>
            <p class="app-header__subtitle">{len(TOP_NEPAL_NEWS_PORTALS)} Nepali portals · {len(TOP_INDIAN_MEDIA_SOURCES)} Indian outlets · X</p>
        </div>
    </div>
    <div class="live-pill"><span class="live-pill__dot"></span>Live · {formatted_now_time}</div>
</div>
""", unsafe_allow_html=True)

# ==========================================
# 6. SIDEBAR · Card 1 — Timeframe & Search
# ==========================================
with st.sidebar:
    with st.container(border=True):
        sidebar_section("Timeframe & Search")
        st.segmented_control(
            "Timeframe",
            options=TIMEFRAME_PRESETS,
            key="cp_timeframe_segment",
            on_change=on_timeframe_preset_change,
            label_visibility="collapsed",
        )

        if active_preset == "Custom":
            c_dt1, c_dt2 = st.columns(2)
            with c_dt1:
                st.date_input("From", value=st.session_state.get("filter_start_date", default_start_date), max_value=now_npt.date(), key="filter_start_date")
                st.time_input("Time", value=st.session_state.get("filter_start_time", default_start_time), key="filter_start_time")
            st.toggle("Up to now", value=True, key="filter_use_current_time", help="Keep the window open-ended so new stories stream in")
            if not st.session_state.get("filter_use_current_time", True):
                with c_dt2:
                    st.date_input("To", value=st.session_state.get("filter_end_date", now_npt.date()), max_value=now_npt.date(), min_value=st.session_state.get("filter_start_date", default_start_date), key="filter_end_date")
                    st.time_input("Time ", value=st.session_state.get("filter_end_time", now_npt.time().replace(second=0, microsecond=0)), key="filter_end_time")

        search_query = st.text_input(
            "Search",
            placeholder="Search all streams",
            key="global_search_input",
            label_visibility="collapsed",
            icon=":material/search:",
        )

        sb_btn1, sb_btn2 = st.columns(2)
        with sb_btn1:
            if st.button("Sync", icon=":material/sync:", key="btn_top_sync", width="stretch", help=f"Fetch the latest stories from all {len(TOP_NEPAL_NEWS_PORTALS) + len(TOP_INDIAN_MEDIA_SOURCES)} sources"):
                with st.spinner("Syncing live feeds…"):
                    fetch_top_nepal_media(max_workers=25, force_refresh=True)
                    fetch_nepal_in_indian_media(max_workers=18, force_refresh=True)
                    st.cache_data.clear()
                    st.session_state.pop("x_posts", None)
                    st.session_state["last_sync_npt"] = datetime.datetime.now(NEPAL_TZ).strftime("%I:%M %p").lstrip("0")
                st.rerun()
        with sb_btn2:
            st.button("Reset", icon=":material/restart_alt:", key="btn_top_reset", width="stretch", on_click=reset_all_filters, help="Reset all filters")

# Global cross-channel search
if search_query and search_query.strip():
    filtered_articles = [a for a in filtered_articles if smart_search_match(a, search_query)]
    filtered_indian = [a for a in filtered_indian if smart_search_match(a, search_query)]
    filtered_x_posts = [p for p in filtered_x_posts if smart_search_match(p, search_query)]

# ==========================================
# 7. SIDEBAR · Card 2 — Workspace, Card 3 — Contextual filters
# ==========================================
NAV_ITEMS = [
    ("Nepali Media", "📰", len(filtered_articles)),
    ("Indian Press", "🇮🇳", len(filtered_indian)),
    ("X", "𝕏", len(filtered_x_posts)),
    ("Analytics & Export", "📈", None),
    ("System Health", "🩺", None),
]

def nav_label(name: str) -> str:
    icon, count = next((i, c) for n, i, c in NAV_ITEMS if n == name)
    return f"{icon}  {name}" + (f"  ·  {count:,}" if count is not None else "")

with st.sidebar:
    with st.container(border=True):
        sidebar_section("Workspace")
        selected_nav = st.selectbox(
            "Workspace",
            options=[n for n, _, _ in NAV_ITEMS],
            format_func=nav_label,
            key="app_nav_section",
            label_visibility="collapsed",
        )

    with st.container(border=True):
        if selected_nav == "Nepali Media":
            sidebar_section("Filters", f"{len(TOP_NEPAL_NEWS_PORTALS)} outlets")
            sel_np_portal = st.selectbox("News portal", [ALL_PORTALS_DEFAULT] + NEPALI_PORTAL_NAMES, key="np_portal_filter")
            sel_np_cat = st.selectbox("Category", CATEGORY_FILTER_OPTIONS, key="np_cat_filter")
            sel_np_lang = st.selectbox("Language", [ALL_LANG_DEFAULT, "Nepali Only", "English Only"], key="np_lang_filter")

        elif selected_nav == "Indian Press":
            sidebar_section("Filters", f"{len(TOP_INDIAN_MEDIA_SOURCES)} outlets")
            selected_indian_outlet = st.selectbox("News outlet", [ALL_INDIAN_DEFAULT] + INDIAN_OUTLET_NAMES, key="in_outlet_filter")
            sel_in_lang = st.selectbox("Language", [ALL_LANG_DEFAULT, "English", "Hindi"], key="in_lang_filter")

        elif selected_nav == "X":
            sidebar_section("Filters", f"{len(TOP_NEPAL_X_ACCOUNTS)} accounts")
            x_cat_filter = st.selectbox("Category", CATEGORY_FILTER_OPTIONS, key="x_cat_filter_select")
            selected_acc_type = st.selectbox(
                "Account type",
                [ALL_ACC_TYPES] + sorted({a.get("type", "") for a in TOP_NEPAL_X_ACCOUNTS if a.get("type")}),
                key="x_acc_type_select",
            )
            sort_mode = st.selectbox("Sort by", ["Newest", "Most engagement", "Most liked", "Most reposted"], key="x_sort_mode_select")
            if st.button("Rescan X", icon=":material/refresh:", width="stretch", key="btn_rescan_x_sidebar"):
                with st.spinner("Scanning verified Nepali accounts…"):
                    st.session_state["x_posts"] = scan_popular_nepal_x_posts(force_refresh=True, x_bearer_token=x_bearer_token)
                st.rerun()

        elif selected_nav == "Analytics & Export":
            sidebar_section("Export filters")
            sel_stream = st.selectbox("Stream", ["All Streams", "Nepali Media", "Indian Press", "X (Twitter)"], key="univ_stream_filter")
            all_export_cats = sorted({
                *(a.get("structured_category", "Others") for a in filtered_articles),
                *(a.get("structured_category", "India Section") for a in filtered_indian),
                *(p.get("structured_category", "Others") for p in filtered_x_posts),
            })
            sel_cat = st.selectbox("Category", ["All Categories"] + all_export_cats, key="univ_cat_filter")
            sel_lang = st.selectbox("Language", [ALL_LANG_DEFAULT, "Nepali", "English", "Nepali / English"], key="univ_lang_filter")
            kw_filter = st.text_input("Keyword", placeholder="Keyword or author", key="univ_kw_filter")

        else:
            sidebar_section("Source filters")
            admin_search_src = st.text_input("Portal name", placeholder="e.g. Setopati", key="inp_admin_src_srch")
            admin_status_filter = st.selectbox("Status", ["All Statuses", "Operational Only", "Degraded Only", "Failing Only"], key="sel_admin_status")
            admin_lang_filter = st.selectbox("Language", [ALL_LANG_DEFAULT, "Nepali Only", "English Only"], key="sel_admin_lang")
            admin_tier_filter = st.selectbox("Polling tier", ["All Tiers", "High (8m)", "Standard (18m)", "Low (40m)"], key="sel_admin_tier")

    st.markdown(
        f'<div class="sb-footer">Last synced {html.escape(st.session_state["last_sync_npt"])} NPT<br/>Nepal Social &amp; Media Monitor</div>',
        unsafe_allow_html=True,
    )

# ==========================================
# SECTION 1: Nepali Media (Top 34 Portals)
# ==========================================
if selected_nav == "Nepali Media":
    render_page_header("Nepali Media", f"{len(filtered_articles):,} stories discovered across 34 portals")

    tab_articles = filter_items_by_category(filtered_articles, sel_np_cat, is_social=False)
    if sel_np_lang == "Nepali Only":
        tab_articles = [a for a in tab_articles if a.get("language") == "Nepali"]
    elif sel_np_lang == "English Only":
        tab_articles = [a for a in tab_articles if a.get("language") == "English"]

    if sel_np_portal != ALL_PORTALS_DEFAULT:
        tab_articles = [a for a in tab_articles if a.get("source") == sel_np_portal]
        if not tab_articles:
            portal_recent = [a for a in all_articles if a.get("source") == sel_np_portal]
            if portal_recent:
                tab_articles = filter_items_by_category(portal_recent, sel_np_cat, is_social=False)
                last_dt = portal_recent[0].get("published_dt")
                last_str = last_dt.strftime("%d %b %Y, %I:%M %p NPT").lstrip("0") if last_dt else "recently"
                st.info(f"**{sel_np_portal}** has no dispatches in the active window (last story: {last_str}). Showing its {len(tab_articles)} most recent dispatches.")

    if not tab_articles:
        render_empty_state("📰", "No articles found", "Try widening the timeframe or choosing 'All Portals' / 'All News'.")
    else:
        render_paginated_feed(tab_articles, "media_visible_count", render_apple_article_card, "stories")


# ==========================================
# SECTION 2: Nepal in Indian Media
# ==========================================
elif selected_nav == "Indian Press":
    render_page_header("Indian Press", f"{len(filtered_indian):,} Nepal-focused dispatches across 18 Indian outlets")

    tab_filtered_indian = filtered_indian
    if selected_indian_outlet != ALL_INDIAN_DEFAULT:
        tab_filtered_indian = [a for a in tab_filtered_indian if a.get("source") == selected_indian_outlet]
    if sel_in_lang != ALL_LANG_DEFAULT:
        tab_filtered_indian = [a for a in tab_filtered_indian if a.get("language") == sel_in_lang]

    if not tab_filtered_indian:
        render_empty_state("🇮🇳", "No Indian media coverage found", "Try selecting 'All 18 Indian Outlets' or adjusting the timeframe.")
    else:
        render_paginated_feed(
            tab_filtered_indian,
            "indian_visible_count",
            lambda a: render_apple_article_card(a, is_indian=True),
            "stories"
        )

    # Flagged Borderline Articles for Editorial Review & Central DB Retention Audit
    try:
        ind_audit = get_indian_media_audit_stats()
        borderline_candidates = get_stored_indian_articles(status_filter=None, min_score=BORDERLINE_NEPAL_RELEVANCE_FLOOR, limit=100)
        borderline_items = []
        for bc in borderline_candidates:
            re_ev = evaluate_indian_article_nepal_relevance(
                title=bc.get("title", ""),
                summary=bc.get("summary", ""),
                full_content=bc.get("full_content", ""),
                link=bc.get("link", ""),
                source=bc.get("source", ""),
                threshold=india_rel_threshold,
            )
            if BORDERLINE_NEPAL_RELEVANCE_FLOOR <= re_ev["nepal_relevance_score"] < india_rel_threshold:
                bc["nepal_relevance_score"] = re_ev["nepal_relevance_score"]
                bc["relevance_status"] = "borderline_review"
                bc["relevance_reason"] = re_ev["relevance_reason"]
                bc["nepal_dimensions"] = re_ev["nepal_dimensions"]
                borderline_items.append(bc)
    except Exception:
        ind_audit = {"total": 0, "substantive": 0, "borderline_review": 0, "excluded": 0}
        borderline_items = []

    with st.expander(f"⚠️ Flagged Borderline Articles for Editorial Review ({len(borderline_items)})", expanded=False):
        st.caption(
            "Borderline articles (scoring between 40% and the active relevance threshold) and excluded domestic Indian articles are retained in the central database (`indian_media_articles`) without cluttering the main feed."
        )
        m_c1, m_c2, m_c3, m_c4 = st.columns(4)
        m_c1.metric("Substantive", f"{len(tab_filtered_indian):,}")
        m_c2.metric("Borderline Review", f"{len(borderline_items):,}")
        m_c3.metric("Excluded Domestic", f"{ind_audit.get('excluded', 0):,}")
        m_c4.metric("Total Stored", f"{ind_audit.get('total', 0):,}")

        if borderline_items:
            for b_art in borderline_items[:15]:
                st.markdown(render_apple_article_card(b_art, is_indian=True), unsafe_allow_html=True)
        else:
            st.success("No borderline articles currently pending editorial review.")

    with st.expander("⚡ Dedicated Nepal Desks in Indian Media", expanded=False):
        q1, q2, q3, q4 = st.columns(4)
        q1.link_button("The Indian Express ↗", "https://indianexpress.com/about/nepal/", width="stretch")
        q2.link_button("The Hindu ↗", "https://www.thehindu.com/news/international/", width="stretch")
        q3.link_button("India Today ↗", "https://www.indiatoday.in/topic/nepal", width="stretch")
        q4.link_button("Business Standard ↗", "https://www.business-standard.com/topic/nepal", width="stretch")
        q5, q6, q7, q8 = st.columns(4)
        q5.link_button("Livemint ↗", "https://www.livemint.com/topic/nepal", width="stretch")
        q6.link_button("The Tribune ↗", "https://www.tribuneindia.com/topic/nepal", width="stretch")
        q7.link_button("Amar Ujala ↗", "https://www.amarujala.com/tags/nepal", width="stretch")
        q8.link_button("Live Hindustan ↗", "https://www.livehindustan.com/tags/nepal/", width="stretch")


# ==========================================
# SECTION 3: X (Twitter) Nepal
# ==========================================
elif selected_nav == "X":
    render_page_header("X (Twitter) Nepal", f"{len(filtered_x_posts):,} posts from {len(TOP_NEPAL_X_ACCOUNTS)} verified accounts")

    with st.expander(f"🇳🇵 Verified Monitored Accounts ({len(TOP_NEPAL_X_ACCOUNTS)} Accounts)", expanded=False):
        st.caption("Directory of verified Nepali political leaders, public commentators, diplomats, and institutions:")
        a_cols = st.columns(4)
        for i, a in enumerate(TOP_NEPAL_X_ACCOUNTS):
            with a_cols[i % 4]:
                st.markdown(f"""
                <div class="acct-card">
                    <div>
                        <div class="acct-card__head">
                            <div class="x-avatar acct-card__avatar" style="background:{a['avatar_bg']};">{a['initials']}</div>
                            <div style="overflow:hidden;">
                                <div class="acct-card__name">{html.escape(a['name'])} <span style="color:#1D9BF0;">✓</span></div>
                                <div class="acct-card__handle">@{html.escape(a['handle'])} · <span class="x-type-badge">{html.escape(a.get('type', ''))}</span></div>
                            </div>
                        </div>
                        <div class="acct-card__role">{html.escape(a.get('role', ''))}</div>
                    </div>
                    <div class="acct-card__links">
                        <a href="https://x.com/{html.escape(a['handle'])}" target="_blank" rel="noopener noreferrer">Profile ↗</a>
                        <a href="https://x.com/search?q=from%3A{html.escape(a['handle'])}&f=live" target="_blank" rel="noopener noreferrer">Live Posts ↗</a>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    filtered_feed = filter_items_by_category(filtered_x_posts, x_cat_filter, is_social=True)
    if selected_acc_type != ALL_ACC_TYPES:
        filtered_feed = [p for p in filtered_feed if p.get("author_type") == selected_acc_type]

    # Apply sorting
    if sort_mode == "Newest":
        filtered_feed.sort(key=lambda x: x.get("published_dt") or MIN_DATE, reverse=True)
    elif sort_mode == "Most engagement":
        filtered_feed.sort(key=lambda x: x.get("engagement_score", 0), reverse=True)
    elif sort_mode == "Most liked":
        filtered_feed.sort(key=lambda x: x.get("likes", 0), reverse=True)
    elif sort_mode == "Most reposted":
        filtered_feed.sort(key=lambda x: x.get("retweets", 0), reverse=True)

    if not filtered_feed:
        render_empty_state("𝕏", "No X posts found", "Try selecting 'All Account Types' or choosing 'All News'.")
    else:
        render_paginated_feed(filtered_feed, "x_visible_count", render_apple_x_post_card, "posts")

    with st.expander("⚡ Live X Searches by Editorial Category", expanded=False):
        clean_q = search_query.strip() if search_query else ""
        x_cat_searches = [
            ("🇮🇳 India Section ↗", '("Nepal" OR "नेपाल" OR "India" OR "भारत") AND ("Modi" OR "border" OR "trade" OR "#NepalIndia")'),
            ("🇨🇳 China Section ↗", '("Nepal" OR "नेपाल" OR "China" OR "चीन") AND ("Beijing" OR "BRI" OR "Pokhara" OR "#NepalChina")'),
            ("🇧🇩 Bangladesh Section ↗", '("Nepal" OR "नेपाल" OR "Bangladesh" OR "बंगलादेश") AND ("Dhaka" OR "Yunus" OR "energy")'),
            ("🇵🇰 Pakistan Section ↗", '("Nepal" OR "नेपाल" OR "Pakistan" OR "पाकिस्तान") AND ("Islamabad" OR "SAARC")'),
            ("🇳🇵 Nepal – Internal ↗", '("Nepal" OR "नेपाल") AND ("politics" OR "Oli" OR "Deuba" OR "Prachanda" OR "Balen" OR "संसद्")'),
            ("🌐 Nepal – External ↗", '("Nepal" OR "नेपाल") AND ("diplomacy" OR "ambassador" OR "UN" OR "USAID" OR "MCC" OR "परराष्ट्र")'),
            ("📈 Nepal – Economy ↗", '("Nepal" OR "नेपाल") AND ("economy" OR "NRB" OR "remittance" OR "inflation" OR "budget" OR "अर्थतन्त्र")'),
            ("📌 Nepal – Others ↗", '("Nepal" OR "नेपाल") AND ("cricket" OR "cinema" OR "weather" OR "Everest" OR "संस्कृति")'),
            ("🌍 International News ↗", '("geopolitics" OR "conflict" OR "diplomacy" OR "summit" OR "Ukraine" OR "Gaza" OR "BRICS")'),
        ]
        for row_idx in range(0, len(x_cat_searches), 3):
            cols = st.columns(3)
            for col_idx, (label, query_str) in enumerate(x_cat_searches[row_idx:row_idx + 3]):
                with cols[col_idx]:
                    full_q = f"({clean_q}) AND {query_str}" if clean_q else query_str
                    x_url = f"https://x.com/search?q={urllib.parse.quote_plus(full_q)}&f=live"
                    st.link_button(label, x_url, width="stretch")


# ==========================================
# SECTION 4: Analytics & Export
# ==========================================
elif selected_nav == "Analytics & Export":
    render_page_header("Analytics & Export", "Consolidated intelligence dataset & executive document generation")

    all_unified_items = []
    for a in filtered_articles:
        all_unified_items.append({
            "stream": "Nepali Media",
            "title": (a.get("title") or "").strip(),
            "headline_en": a.get("headline_english", ""),
            "content": a.get("full_content") or a.get("summary", ""),
            "category": a.get("structured_category", "Others"),
            "source": a.get("source", "Nepali Media"),
            "language": a.get("language") or ("English" if a.get("source") in ("The Kathmandu Post", "The Himalayan Times", "Republica", "Nepal News") else "Nepali"),
            "timestamp": a.get("exact_time") or a.get("relative_time", ""),
            "published_dt": a.get("published_dt"),
            "link": a.get("link", ""),
            "raw_item": a,
        })

    for a in filtered_indian:
        all_unified_items.append({
            "stream": "Indian Press",
            "title": (a.get("title") or "").strip(),
            "headline_en": a.get("headline_english", ""),
            "content": a.get("full_content") or a.get("summary", ""),
            "category": a.get("structured_category", "India Section"),
            "source": a.get("source", "Indian Media"),
            "language": a.get("language") or "English",
            "timestamp": a.get("exact_time") or a.get("relative_time", ""),
            "published_dt": a.get("published_dt"),
            "link": a.get("link", ""),
            "raw_item": a,
        })

    for p in filtered_x_posts:
        auth_name = p.get("author_name", "")
        auth_handle = p.get("handle", "")
        all_unified_items.append({
            "stream": "X (Twitter)",
            "title": (p.get("text") or "").strip(),
            "headline_en": "",
            "content": p.get("text", ""),
            "category": p.get("structured_category", "Others"),
            "source": f"{auth_name} ({auth_handle})" if auth_handle else auth_name,
            "language": "Nepali / English",
            "timestamp": p.get("exact_time") or p.get("relative_time", ""),
            "published_dt": p.get("published_dt"),
            "link": p.get("link", ""),
            "raw_item": p,
        })

    all_unified_items.sort(key=lambda x: x.get("published_dt") or MIN_DATE, reverse=True)

    filtered_export_items = all_unified_items
    if sel_stream != "All Streams":
        filtered_export_items = [x for x in filtered_export_items if x["stream"] == sel_stream]
    if sel_cat != "All Categories":
        filtered_export_items = [x for x in filtered_export_items if x["category"] == sel_cat]
    if sel_lang != ALL_LANG_DEFAULT:
        filtered_export_items = [x for x in filtered_export_items if x["language"] == sel_lang]
    if kw_filter.strip():
        q_lower = kw_filter.strip().lower()
        filtered_export_items = [
            x for x in filtered_export_items
            if q_lower in x["title"].lower() or q_lower in x["content"].lower() or q_lower in x["source"].lower()
        ]

    rows_data = [
        {
            "Stream": it["stream"],
            "Headline / Text": it["title"],
            "English Translation": it["headline_en"],
            "Category": it["category"],
            "Source / Author": it["source"],
            "Language": it["language"],
            "Published Date & Time": it["timestamp"],
            "Link": it["link"],
            "Content": it["content"]
        }
        for it in filtered_export_items
    ]
    df_export = pd.DataFrame(rows_data)

    sum1, sum2, sum3, sum4 = st.columns(4)
    sum1.metric("Total Matches", f"{len(df_export):,}")
    sum2.metric("Nepali Media", f"{sum(1 for x in filtered_export_items if x['stream'] == 'Nepali Media'):,}")
    sum3.metric("Indian Press", f"{sum(1 for x in filtered_export_items if x['stream'] == 'Indian Press'):,}")
    sum4.metric("X Posts", f"{sum(1 for x in filtered_export_items if x['stream'] == 'X (Twitter)'):,}")

    current_filter_sig = f"{sel_stream}_{sel_cat}_{sel_lang}_{kw_filter.strip()}_{len(filtered_export_items)}"
    st.session_state.setdefault("editor_ver_univ", 0)
    if st.session_state.get("last_univ_filter_sig") != current_filter_sig or "selected_links_univ" not in st.session_state:
        st.session_state["selected_links_univ"] = {x["link"] for x in filtered_export_items}
        st.session_state["last_univ_filter_sig"] = current_filter_sig

    sc1, sc2, sc3, sc_badge = st.columns([1.3, 1.3, 1.8, 3.6])
    with sc1:
        if st.button("Select All", icon=":material/select_all:", key="btn_univ_sel_all"):
            st.session_state["selected_links_univ"] = {x["link"] for x in filtered_export_items}
            st.session_state["editor_ver_univ"] += 1
            st.rerun()
    with sc2:
        if st.button("Deselect All", icon=":material/deselect:", key="btn_univ_desel_all"):
            st.session_state["selected_links_univ"] = set()
            st.session_state["editor_ver_univ"] += 1
            st.rerun()
    with sc3:
        if st.button("Select Top 30", icon=":material/bolt:", key="btn_univ_top30"):
            st.session_state["selected_links_univ"] = {x["link"] for x in filtered_export_items[:30]}
            st.session_state["editor_ver_univ"] += 1
            st.rerun()

    selected_export_items = [x for x in filtered_export_items if x.get("link") in st.session_state["selected_links_univ"]]
    with sc_badge:
        st.markdown(
            f'<div class="counter-badge">📋 <b>{len(selected_export_items)} of {len(filtered_export_items)}</b> selected for Executive Word Document</div>',
            unsafe_allow_html=True
        )

    if not df_export.empty:
        df_for_editor = df_export[["Stream", "Headline / Text", "Category", "Source / Author", "Language", "Published Date & Time", "Link"]].copy()
        df_for_editor.insert(0, "Include?", [link in st.session_state["selected_links_univ"] for link in df_for_editor["Link"]])

        col_config_univ = {
            "Include?": st.column_config.CheckboxColumn("Include?", default=True),
            "Stream": st.column_config.TextColumn("Stream", width="small"),
            "Headline / Text": st.column_config.TextColumn("Headline / Post Text", width="large"),
            "Category": st.column_config.TextColumn("Category", width="small"),
            "Source / Author": st.column_config.TextColumn("Source / Author", width="medium"),
            "Language": st.column_config.TextColumn("Language", width="small"),
            "Published Date & Time": st.column_config.TextColumn("Date & Time Stamp", width="medium"),
            "Link": st.column_config.LinkColumn("Source Link", display_text="Open ↗", width="small")
        }

        edited_df_univ = st.data_editor(
            df_for_editor,
            column_config=col_config_univ,
            disabled=[c for c in df_for_editor.columns if c != "Include?"],
            hide_index=True,
            width="stretch",
            key=f"univ_editor_{st.session_state['editor_ver_univ']}_{len(df_for_editor)}"
        )

        for _, row in edited_df_univ.iterrows():
            link = row["Link"]
            if row["Include?"]:
                st.session_state["selected_links_univ"].add(link)
            else:
                st.session_state["selected_links_univ"].discard(link)

        selected_export_items = [x for x in filtered_export_items if x.get("link") in st.session_state["selected_links_univ"]]

        st.write("")
        c_csv, c_docx = st.columns(2)
        with c_csv:
            csv_bytes = df_export.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label=f"Download CSV ({len(df_export):,} Records)",
                icon=":material/download:",
                data=csv_bytes,
                file_name=f"nepal_intelligence_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                width="stretch"
            )

        with c_docx:
            if selected_export_items:
                raw_items_for_docx = []
                for x in selected_export_items:
                    item_copy = dict(x["raw_item"])
                    item_copy["stream"] = x.get("stream", "")
                    if not item_copy.get("structured_category") and x.get("category"):
                        item_copy["structured_category"] = x["category"]
                    raw_items_for_docx.append(item_copy)

                digest_dt = filter_end_dt if (filter_end_dt and not is_to_current) else datetime.datetime.now(NEPAL_TZ)
                day_num = digest_dt.day
                day_suffix = "th" if 11 <= day_num <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day_num % 10, "th")
                digest_filename = f"NEPAL DAILY NEWS DIGEST-{day_num}{day_suffix} {digest_dt.strftime('%B  %Y')}.docx"

                univ_hash = hash((tuple(x["link"] for x in selected_export_items), digest_dt.strftime("%Y-%m-%d")))

                if st.session_state.get("docx_ready_hash_univ") != univ_hash:
                    if st.button(f"Generate Executive Word Document ({len(selected_export_items):,} Stories)", icon=":material/description:", key="btn_prep_univ_docx", width="stretch", type="primary"):
                        with st.spinner(f"Compiling NEPAL DAILY NEWS DIGEST ({digest_dt.strftime('%B %d, %Y')}) with full body text…"):
                            from executive_docx_exporter import generate_executive_word_digest
                            enriched_docx_items = batch_fetch_full_content(raw_items_for_docx, max_workers=25)
                            st.session_state["docx_bytes_univ"] = generate_executive_word_digest(
                                articles=enriched_docx_items,
                                report_date=digest_dt,
                                enrich_missing_sections=False,
                            )
                            st.session_state["docx_ready_hash_univ"] = univ_hash
                        st.rerun()
                else:
                    st.download_button(
                        label=f"Download {digest_filename}",
                        icon=":material/download:",
                        data=st.session_state["docx_bytes_univ"],
                        file_name=digest_filename,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        width="stretch",
                        type="primary"
                    )
            else:
                st.warning("No items selected. Select items in the table above to generate the Word document.")
    else:
        render_empty_state("📊", "No export records", "Try adjusting the search keyword or selecting 'All Streams'.")


# ==========================================
# SECTION 5: Health & Diagnostics
# ==========================================
elif selected_nav == "System Health":
    render_page_header("System Health & Diagnostics", "Portal telemetry, discovery latency, and background worker status", show_window=False)

    try:
        kpis = get_system_kpis()
    except Exception:
        kpis = {
            "total_sources": len(TOP_NEPAL_NEWS_PORTALS),
            "active_sources": len(TOP_NEPAL_NEWS_PORTALS),
            "operational": len(TOP_NEPAL_NEWS_PORTALS),
            "degraded": 0,
            "failing": 0,
            "avg_latency_secs": 0.75,
            "articles_1h": len(filtered_articles),
            "articles_24h": len(filtered_articles),
            "articles_7d": len(filtered_articles),
            "total_stored_articles": len(filtered_articles)
        }

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Total Portals", f"{kpis['total_sources']}")
    k2.metric("Operational", f"{kpis['operational']}", delta="100% Healthy" if kpis["failing"] == 0 else f"-{kpis['failing']} failing")
    k3.metric("Last 1 Hour", f"{kpis['articles_1h']:,}")
    k4.metric("Last 24 Hours", f"{kpis['articles_24h']:,}")
    k5.metric("Total Stored", f"{kpis['total_stored_articles']:,}")
    k6.metric("Avg Latency", f"{kpis['avg_latency_secs']}s")

    st.write("")

    ctrl_col1, ctrl_col2 = st.columns([1.8, 2.2])
    with ctrl_col1:
        st.markdown("##### ⚡ Live Ingestion Controls")
        if st.button("Trigger Ingestion (All 34 Portals)", icon=":material/refresh:", width="stretch", key="btn_trigger_all_ingest"):
            with st.spinner("Executing parallel discovery across all 34 Nepali news portals…"):
                sync_res = run_all_sources_discovery(parallel_workers=20, force_all=True)
                st.success(f"✓ Checked {sync_res['total_checked']} portals · Ingested {sync_res['total_ingested']} fresh articles.")
                time.sleep(1)
                st.rerun()
        st.caption("Background daemon continuously polls portals based on configured tiers.")

    with ctrl_col2:
        st.markdown("##### ⏪ Historical Backfill & Archive Recovery")
        with st.expander("Configure Historical Backfill", expanded=False):
            st.caption("Inspect past days' archives, category pagination, and XML sitemaps:")
            bf_days = st.select_slider("Backfill Time Horizon:", options=[1, 3, 5, 7, 14], value=3, format_func=lambda x: f"Past {x} Days")
            portal_options = ["All 34 Portals"] + NEPALI_PORTAL_NAMES
            bf_targets = st.multiselect("Select Target Portals:", portal_options, default=["All 34 Portals"])

            if st.button("Start Historical Backfill", icon=":material/history:", width="stretch", key="btn_exec_backfill"):
                targets = None if "All 34 Portals" in bf_targets else bf_targets
                with st.spinner(f"Initiating deep backfill for {len(targets) if targets else 34} portals across the past {bf_days} days…"):
                    bf_res = run_historical_backfill(source_names=targets, days_back=bf_days, parallel_workers=10)
                    st.success(f"✓ Backfill Complete! Ingested {bf_res['total_ingested']} historical articles from {bf_res['sources_backfilled']} outlets.")
                    time.sleep(1)
                    st.rerun()

    st.write("")
    st.markdown("##### 📋 Monitored Media Source Registry")

    try:
        health_data = get_all_source_health()
    except Exception:
        health_data = []

    filtered_health = health_data
    if admin_search_src and admin_search_src.strip():
        q_src = admin_search_src.strip().lower()
        filtered_health = [h for h in filtered_health if q_src in h["name"].lower()]
    if admin_status_filter == "Operational Only":
        filtered_health = [h for h in filtered_health if h.get("status") == "operational"]
    elif admin_status_filter == "Degraded Only":
        filtered_health = [h for h in filtered_health if h.get("status") == "degraded"]
    elif admin_status_filter == "Failing Only":
        filtered_health = [h for h in filtered_health if h.get("status") == "failing"]

    if admin_lang_filter == "Nepali Only":
        filtered_health = [h for h in filtered_health if h.get("lang") == "Nepali"]
    elif admin_lang_filter == "English Only":
        filtered_health = [h for h in filtered_health if h.get("lang") == "English"]

    if admin_tier_filter == "High (8m)":
        filtered_health = [h for h in filtered_health if h.get("priority") == "high"]
    elif admin_tier_filter == "Standard (18m)":
        filtered_health = [h for h in filtered_health if h.get("priority") == "standard"]
    elif admin_tier_filter == "Low (40m)":
        filtered_health = [h for h in filtered_health if h.get("priority") == "low"]

    st.markdown(f'<div class="counter-badge">Displaying <b>{len(filtered_health)} of {len(health_data)}</b> monitored media sources</div>', unsafe_allow_html=True)
    st.write("")

    for s_idx, src in enumerate(filtered_health):
        s_name = src["name"]
        s_status = src.get("status", "operational")
        s_lang = src.get("lang", "Nepali")
        s_type = src.get("type", "rss").upper()
        s_priority = src.get("priority", "standard").capitalize()
        s_interval = src.get("check_interval_mins", 15)
        s_enabled = bool(src.get("enabled", 1))

        if s_status == "operational":
            status_cls, status_txt = "status-pill--ok", "Operational"
            card_accent = "health-card--ok"
        elif s_status == "degraded":
            status_cls, status_txt = "status-pill--warn", "Degraded"
            card_accent = "health-card--warn"
        else:
            status_cls, status_txt = "status-pill--fail", "Failing"
            card_accent = "health-card--fail"

        c_1h = src.get("count_1h") or 0
        c_24h = src.get("count_24h") or 0
        c_7d = src.get("count_7d") or 0
        c_tot = src.get("count_total") or 0
        raw_lat = src.get("discovery_latency_avg_secs")
        lat = round(float(raw_lat), 2) if raw_lat is not None else 0.0

        last_disc = src.get("last_discovery_time") or "Pending first cycle"
        latest_title = src.get("latest_article_title") or "No article recorded yet"
        latest_link = src.get("latest_article_link") or src.get("url") or "#"
        latest_pub = src.get("latest_article_pub_dt") or ""

        st.markdown(f"""
        <div class="health-card {card_accent}">
            <div class="health-card__head">
                <div class="health-card__title">
                    <span class="health-card__name">{html.escape(s_name)}</span>
                    <span class="status-pill {status_cls}">● {status_txt}</span>
                    <span class="pill">⏱ Every {s_interval}m ({s_priority})</span>
                    <span class="pill">📡 {s_type}</span>
                    <span class="pill">🌐 {s_lang}</span>
                </div>
                <div class="health-card__meta">
                    Last Polled: <b>{html.escape(str(last_disc)[:19])}</b> · Latency: <b>{lat}s</b>
                </div>
            </div>
            <div class="health-card__stats">
                <div>Discovered: <b>{c_1h}</b> in 1h · <b>{c_24h}</b> in 24h · <b>{c_7d}</b> in 7d (<b>{c_tot:,}</b> Total Stored)</div>
                <div>Endpoint: <a href="{html.escape(src.get('url', ''))}" target="_blank" rel="noopener noreferrer">{html.escape(src.get('url', ''))[:45]}… ↗</a></div>
            </div>
            <div class="health-card__latest">
                <div class="health-card__eyebrow">Latest Discovered Story ({html.escape(str(latest_pub)[:19])}):</div>
                <div><a href="{html.escape(latest_link)}" target="_blank" rel="noopener noreferrer">• {html.escape(latest_title[:110])} ↗</a></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        sc1, sc2, sc3, sc4 = st.columns([1.5, 1.5, 1.5, 1.5])
        with sc1:
            if st.button(f"Refresh {s_name}", icon=":material/refresh:", key=f"btn_ref_src_{s_name}_{s_idx}", width="stretch"):
                with st.spinner(f"Ingesting latest feeds from {s_name}…"):
                    portal_cfg = next((p for p in TOP_NEPAL_NEWS_PORTALS if p["name"] == s_name), None)
                    if portal_cfg:
                        run_single_source_discovery(portal_cfg, max_articles=40)
                        st.success(f"✓ Refreshed {s_name}!")
                        time.sleep(0.5)
                        st.rerun()
        with sc2:
            new_int = st.selectbox(
                f"Interval ({s_name}):",
                [5, 8, 15, 18, 30, 40, 60],
                index=[5, 8, 15, 18, 30, 40, 60].index(s_interval) if s_interval in [5, 8, 15, 18, 30, 40, 60] else 3,
                key=f"sel_int_{s_name}_{s_idx}",
                label_visibility="collapsed"
            )
            if new_int != s_interval:
                set_source_interval(s_name, new_int)
                st.rerun()
        with sc3:
            toggle_label = "Disable Source" if s_enabled else "Enable Source"
            toggle_icon = ":material/cancel:" if s_enabled else ":material/check_circle:"
            if st.button(toggle_label, icon=toggle_icon, key=f"btn_tog_en_{s_name}_{s_idx}", width="stretch"):
                set_source_enabled(s_name, not s_enabled)
                st.rerun()
        with sc4:
            if src.get("last_error_message"):
                with st.expander("View Error Log", expanded=False):
                    st.error(src.get("last_error_message"))
            else:
                st.caption("✓ Zero active errors")

    with st.expander("🔍 Coverage Diagnostics & Anomaly Detection", expanded=False):
        low_coverage_sources = [
            h for h in health_data 
            if h.get("count_24h", 0) == 0 and h.get("enabled", 1) and (h.get("count_7d", 0) == 0 or h.get("status") in ["failing", "degraded"])
        ]
        quiet_sources = [
            h for h in health_data 
            if h.get("count_24h", 0) == 0 and h.get("enabled", 1) and h.get("count_7d", 0) > 0 and h.get("status") not in ["failing", "degraded"]
        ]
        if low_coverage_sources:
            st.warning(f"⚠️ **Low Discovery Alert:** {len(low_coverage_sources)} enabled portals have produced 0 articles and require endpoint review:")
            for lcs in low_coverage_sources:
                st.write(f"- **{lcs['name']}** ({lcs['type']} · {lcs['lang']}): Status `{lcs['status']}` · Endpoint: `{lcs['url']}`")
        else:
            st.success("🎉 All active media portal feeds and web scrapers are healthy with zero degraded endpoints!")

        if quiet_sources:
            st.info(f"ℹ️ **Quiet / Periodic Portals:** {len(quiet_sources)} portals (e.g. {', '.join([q['name'] for q in quiet_sources[:3]])}) publish on a weekly or holiday schedule. Their scrapers are operational and will automatically ingest stories when published.")
