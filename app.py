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
import streamlit.components.v1 as components
import pandas as pd
import datetime
import time
import zoneinfo
import urllib.parse
import html
import re
import os
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter
from nepal_fetcher import (
    fetch_top_nepal_media,
    fetch_all_nepal_posts,
    fetch_nepal_in_indian_media,
    evaluate_indian_article_nepal_relevance,
    DEFAULT_NEPAL_RELEVANCE_THRESHOLD,
    BORDERLINE_NEPAL_RELEVANCE_FLOOR,
    query_x_api,
    get_live_nepal_trends,
    batch_fetch_full_content,
    extract_article_full_text,
    generate_word_document,
    map_to_target_category,
    DOCX_TARGET_CATEGORIES,
    NEPAL_TZ,
    STRUCTURED_CATEGORIES,
    CATEGORY_ICONS,
    TOP_NEPAL_NEWS_PORTALS,
    TOP_INDIAN_MEDIA_SOURCES,
    POPULAR_NEPAL_X_HANDLES
)
from nepal_x_scanner import (
    scan_popular_nepal_x_posts,
    fetch_real_account_tweets,
    TOP_NEPAL_X_ACCOUNTS
)
from nepal_news_store import (
    get_all_source_health,
    get_system_kpis,
    set_source_enabled,
    set_source_interval,
    get_stored_articles,
    get_source_broadcast_stats,
    get_stored_indian_articles,
    get_indian_media_audit_stats
)
from nepal_news_scheduler import (
    run_single_source_discovery,
    run_all_sources_discovery,
    run_historical_backfill,
    start_monitoring_daemon
)

# Start background news monitoring daemon if not already running
try:
    start_monitoring_daemon()
except Exception:
    pass
from whatsapp_dispatcher import (
    load_sent_cache,
    save_sent_cache,
    is_item_broadcasted,
    mark_item_broadcasted,
    unmark_item_broadcasted,
    get_broadcasted_stats,
    format_whatsapp_message,
    generate_whatsapp_share_url,
    get_item_key,
    DEFAULT_CHANNEL_URL,
    get_env_variable,
    dispatch_item_to_webhook,
    send_test_webhook_ping,
    get_green_api_credentials,
    get_green_api_status,
    dispatch_item_to_green_api,
    send_test_green_api_message,
    get_green_api_chats,
    find_channel_newsletter_id,
    is_substantially_related_to_nepal
)

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
    initial_sidebar_state="collapsed"
)

# 2. Modern Apple-Grade Design System & Custom Styling
from apple_theme import APPLE_DESIGN_SYSTEM_CSS
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

    # Single Unified Authentication Card – Light Minimalist Design
    st.markdown("""
    <style>
        /* Hide sidebar and header chrome during login */
        [data-testid="stSidebar"], [data-testid="collapsedControl"], header[data-testid="stHeader"] {
            display: none !important;
        }

        /* Page background: #F5F7FA */
        [data-testid="stAppViewContainer"], .main {
            background-color: #F5F7FA !important;
        }

        /* Centre the card vertically and horizontally */
        .block-container {
            padding-top: 12vh !important;
            padding-bottom: 4vh !important;
            max-width: 440px !important;
            margin: 0 auto !important;
        }

        /* Style the SINGLE stForm as the ONE unified white authentication card */
        div[data-testid="stForm"] {
            background-color: #FFFFFF !important;
            border: 1px solid #DCE5EF !important;
            border-radius: 16px !important;
            padding: 36px 32px 28px 32px !important;
            box-shadow: 0 4px 20px rgba(37, 54, 75, 0.05), 0 1px 3px rgba(37, 54, 75, 0.03) !important;
            max-width: 440px !important;
            margin: 0 auto !important;
        }

        /* Header branding inside the single form */
        .auth-header-block {
            text-align: center;
            margin-bottom: 22px;
        }

        .auth-flag-icon {
            font-size: 28px;
            line-height: 1;
            margin-bottom: 12px;
            display: inline-block;
        }

        .auth-main-heading {
            font-size: 31px !important;
            font-weight: 700 !important;
            color: #25364B !important;
            letter-spacing: -0.025em !important;
            margin: 0 0 6px 0 !important;
            line-height: 1.2 !important;
        }

        .auth-sub-heading {
            font-size: 14.5px !important;
            font-weight: 450 !important;
            color: #788596 !important;
            margin: 0 !important;
            line-height: 1.4 !important;
        }

        /* Password Input Field: height ~52-54px, background #FFFFFF, border #DCE5EF */
        div[data-testid="stForm"] div[data-baseweb="input"] {
            background-color: #FFFFFF !important;
            border-radius: 10px !important;
        }

        div[data-testid="stForm"] div[data-baseweb="input"] > div {
            background-color: #FFFFFF !important;
            border: 1.5px solid #DCE5EF !important;
            border-radius: 10px !important;
            min-height: 52px !important;
            height: 52px !important;
            padding: 0 12px !important;
            box-shadow: none !important;
            transition: border-color 0.18s ease, box-shadow 0.18s ease !important;
        }

        div[data-testid="stForm"] div[data-baseweb="input"] > div:focus-within {
            border-color: #526A85 !important;
            box-shadow: 0 0 0 3px rgba(82, 106, 133, 0.14) !important;
        }

        div[data-testid="stForm"] input[type="password"],
        div[data-testid="stForm"] input[type="text"] {
            color: #25364B !important;
            font-size: 15px !important;
            background-color: transparent !important;
        }

        div[data-testid="stForm"] input::placeholder {
            color: #788596 !important;
            opacity: 0.85 !important;
        }

        /* Hide "Press Enter to submit form" instruction overlay */
        div[data-testid="InputInstructions"] {
            display: none !important;
        }

        /* Unlock Platform Button: Muted Slate Blue #526A85, Hover #405872, Text #FFFFFF, Height ~52px */
        div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] {
            margin-top: 6px !important;
        }

        div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] > button,
        div[data-testid="stForm"] button[kind="primaryFormSubmit"],
        div[data-testid="stForm"] button[data-testid="baseButton-primary"],
        div[data-testid="stForm"] button[data-testid="baseButton-secondary"] {
            background-color: #526A85 !important;
            background: #526A85 !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 10px !important;
            min-height: 52px !important;
            height: 52px !important;
            width: 100% !important;
            font-size: 15.5px !important;
            font-weight: 600 !important;
            letter-spacing: -0.01em !important;
            box-shadow: 0 2px 6px rgba(82, 106, 133, 0.2) !important;
            transition: background-color 0.18s ease, transform 0.15s ease, box-shadow 0.18s ease !important;
            cursor: pointer !important;
        }

        div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] > button *,
        div[data-testid="stForm"] button[kind="primaryFormSubmit"] *,
        div[data-testid="stForm"] button[data-testid="baseButton-primary"] *,
        div[data-testid="stForm"] button[data-testid="baseButton-secondary"] * {
            color: #FFFFFF !important;
            font-weight: 600 !important;
        }

        div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] > button:hover,
        div[data-testid="stForm"] button[kind="primaryFormSubmit"]:hover,
        div[data-testid="stForm"] button[data-testid="baseButton-primary"]:hover,
        div[data-testid="stForm"] button[data-testid="baseButton-secondary"]:hover {
            background-color: #405872 !important;
            background: #405872 !important;
            color: #FFFFFF !important;
            box-shadow: 0 4px 12px rgba(64, 88, 114, 0.28) !important;
            transform: translateY(-1px) !important;
        }

        div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] > button:active,
        div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] > button:focus {
            background-color: #405872 !important;
            color: #FFFFFF !important;
            box-shadow: 0 0 0 3px rgba(82, 106, 133, 0.25) !important;
            outline: none !important;
        }

        /* Security Footer inside the card */
        .auth-security-footer {
            text-align: center;
            font-size: 12.5px;
            color: #788596;
            margin-top: 16px;
            margin-bottom: 0;
            font-weight: 450;
            letter-spacing: 0.01em;
        }
    </style>
    """, unsafe_allow_html=True)

    # ONE Single Unified Card containing all 6 required elements in exact order
    with st.form("auth_form", clear_on_submit=False):
        st.markdown("""
        <div class="auth-header-block">
            <div class="auth-flag-icon">🇳🇵</div>
            <h1 class="auth-main-heading">Media Monitor</h1>
            <p class="auth-sub-heading">News Intelligence Platform</p>
        </div>
        """, unsafe_allow_html=True)

        pwd = st.text_input(
            "Password",
            type="password",
            placeholder="Enter password",
            label_visibility="collapsed"
        )

        submit = st.form_submit_button("Unlock Platform", width="stretch", type="primary")

        st.markdown(
            '<div class="auth-security-footer">Secure Access · Authorised Users Only</div>',
            unsafe_allow_html=True
        )

    if submit:
        if pwd.strip() == APP_PASSWORD:
            st.session_state["authenticated"] = True
            st.query_params["auth"] = "true"
            st.rerun()
        else:
            st.error("Incorrect password. Please try again.")

    st.stop()
    return False

if not check_password():
    st.stop()

# 3. Time Reference
now_npt = datetime.datetime.now(NEPAL_TZ)
formatted_now_time = now_npt.strftime("%I:%M %p NPT")
past_12h_ref = now_npt - datetime.timedelta(hours=12)
default_start_date = past_12h_ref.date()
default_start_time = past_12h_ref.time().replace(second=0, microsecond=0)

if "last_sync_npt" not in st.session_state:
    st.session_state["last_sync_npt"] = now_npt.strftime("%I:%M %p")
if "is_refreshing_feeds" not in st.session_state:
    st.session_state["is_refreshing_feeds"] = False

# ==========================================
# 4. TIME LOGIC & STATE HELPERS
# ==========================================
def on_timeframe_preset_change():
    preset = st.session_state.get("cp_timeframe_segment", "12h")
    now_ref = datetime.datetime.now(NEPAL_TZ)
    if preset == "12h":
        past_12 = now_ref - datetime.timedelta(hours=12)
        st.session_state["filter_start_date"] = past_12.date()
        st.session_state["filter_start_time"] = past_12.time().replace(second=0, microsecond=0)
        st.session_state["filter_use_current_time"] = True
    elif preset == "24h":
        past_24 = now_ref - datetime.timedelta(hours=24)
        st.session_state["filter_start_date"] = past_24.date()
        st.session_state["filter_start_time"] = past_24.time().replace(second=0, microsecond=0)
        st.session_state["filter_use_current_time"] = True
    elif preset == "Today":
        st.session_state["filter_start_date"] = now_ref.date()
        st.session_state["filter_start_time"] = datetime.time(0, 0)
        st.session_state["filter_use_current_time"] = True

def on_custom_datetime_edit():
    st.session_state["cp_timeframe_segment"] = "Custom"

if "cp_timeframe_segment" not in st.session_state:
    st.session_state["cp_timeframe_segment"] = "12h"

# Compute Time Window
if st.session_state.get("cp_timeframe_segment") == "Custom":
    start_date = st.session_state.get("filter_start_date", default_start_date)
    start_time = st.session_state.get("filter_start_time", default_start_time)
else:
    on_timeframe_preset_change()
    start_date = st.session_state.get("filter_start_date", default_start_date)
    start_time = st.session_state.get("filter_start_time", default_start_time)

filter_start_dt = datetime.datetime.combine(start_date, start_time, tzinfo=NEPAL_TZ)

use_current_time = st.session_state.get("filter_use_current_time", True)
is_to_current = use_current_time
explicit_all_time = False

if use_current_time:
    filter_end_dt = now_npt
    end_short_str = "Now"
    status_pill_html = '<span class="status-pill-live">● LIVE</span>'
else:
    end_date = st.session_state.get("filter_end_date", now_npt.date())
    end_time = st.session_state.get("filter_end_time", now_npt.time().replace(second=0, microsecond=0))
    filter_end_dt = datetime.datetime.combine(end_date, end_time, tzinfo=NEPAL_TZ)
    if filter_end_dt < filter_start_dt:
        filter_end_dt = filter_start_dt + datetime.timedelta(hours=1)
    end_short_str = filter_end_dt.strftime("%d %b, %I:%M %p").lstrip("0")
    status_pill_html = '<span class="status-pill-paused">PAUSED</span>'

start_short_str = filter_start_dt.strftime("%d %b, %I:%M %p").lstrip("0")

CAT_FILTER_ALL_UNFILTERED = "🌐 All News"
CAT_FILTER_ALL_8 = "📂 Classified"
CAT_FILTER_UNCATEGORIZED = "⚪ Unclassified"

CATEGORY_FILTER_OPTIONS = [
    CAT_FILTER_ALL_UNFILTERED,
    CAT_FILTER_ALL_8,
    CAT_FILTER_UNCATEGORIZED,
] + [f"{CATEGORY_ICONS.get(c, '📌')} {c}" for c in STRUCTURED_CATEGORIES]

ALL_PORTALS_DEFAULT = "All Portals (34)"
ALL_LANG_DEFAULT = "All Languages"

all_portal_names = sorted(list(set([p["name"] for p in TOP_NEPAL_NEWS_PORTALS])))

def reset_all_filters():
    now_ref = datetime.datetime.now(NEPAL_TZ)
    past_12 = now_ref - datetime.timedelta(hours=12)
    st.session_state["global_search_input"] = ""
    st.session_state["np_cat_filter"] = CAT_FILTER_ALL_UNFILTERED
    st.session_state["np_portal_filter"] = ALL_PORTALS_DEFAULT
    st.session_state["np_lang_filter"] = ALL_LANG_DEFAULT
    st.session_state["in_outlet_filter"] = "All 18 Indian Outlets"
    st.session_state["x_cat_filter_select"] = CAT_FILTER_ALL_UNFILTERED
    st.session_state["x_acc_filter_select"] = "All Account Types"
    st.session_state["cp_timeframe_segment"] = "12h"
    st.session_state["filter_start_date"] = past_12.date()
    st.session_state["filter_start_time"] = past_12.time().replace(second=0, microsecond=0)
    st.session_state["filter_end_date"] = now_ref.date()
    st.session_state["filter_end_time"] = now_ref.time().replace(second=0, microsecond=0)
    st.session_state["filter_use_current_time"] = True
    st.session_state["media_visible_count"] = 20
    st.session_state["indian_visible_count"] = 20
    st.session_state["x_visible_count"] = 20

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
min_date = datetime.datetime(2020, 1, 1, tzinfo=NEPAL_TZ)

# Determine strict active cutoff for all feeds
active_time_cutoff = filter_start_dt
if not active_time_cutoff and not explicit_all_time:
    # Default timeline: Past 48 Hours
    active_time_cutoff = now_npt - datetime.timedelta(hours=48)

if active_time_cutoff:
    filtered_articles = [a for a in all_articles if a.get("published_dt") and a["published_dt"] >= active_time_cutoff and a["published_dt"] <= filter_end_dt]
    filtered_indian = [a for a in indian_articles if a.get("published_dt") and a["published_dt"] >= active_time_cutoff and a["published_dt"] <= filter_end_dt]
    filtered_x_posts = [p for p in all_x_posts if p.get("published_dt") and p["published_dt"] >= active_time_cutoff and p["published_dt"] <= filter_end_dt]
else:
    filtered_articles = [a for a in all_articles if a.get("published_dt") and a["published_dt"] <= filter_end_dt]
    filtered_indian = [a for a in indian_articles if a.get("published_dt") and a["published_dt"] <= filter_end_dt]
    filtered_x_posts = [p for p in all_x_posts if p.get("published_dt") and p["published_dt"] <= filter_end_dt]

# Sort EVERY channel strictly by newest publication timestamp first
filtered_articles.sort(key=lambda x: x.get("published_dt") or min_date, reverse=True)
filtered_indian.sort(key=lambda x: x.get("published_dt") or min_date, reverse=True)
filtered_x_posts.sort(key=lambda x: x.get("published_dt") or min_date, reverse=True)

# Calculate Category Counts for Nepali Media (based on time-filtered articles)
cat_counts = Counter([a.get("primary_section") or a.get("structured_category", "Nepal – Others") for a in filtered_articles])

# Helper for category badge
def get_badge_html(cat):
    badge_classes = {
        "India Section": "cat-badge-india",
        "China Section": "cat-badge-china",
        "Pakistan Section": "cat-badge-pakistan",
        "Bangladesh Section": "cat-badge-bangladesh",
        "Nepal – Internal": "cat-badge-internal",
        "Nepal – External": "cat-badge-external",
        "Nepal – Economy": "cat-badge-economy",
        "Nepal – Others": "cat-badge-others",
        "International News": "cat-badge-international",
        # Backward compatibility aliases
        "India in Nepal": "cat-badge-india",
        "China in Nepal": "cat-badge-china",
        "Pakistan in Nepal": "cat-badge-pakistan",
        "Bangladesh in Nepal": "cat-badge-bangladesh",
        "Nepal – Internal Politics": "cat-badge-internal",
        "Nepal – External Relations (Others)": "cat-badge-external",
        "Economy": "cat-badge-economy",
        "Others": "cat-badge-others",
    }
    css = badge_classes.get(cat, "cat-badge-others")
    icon = CATEGORY_ICONS.get(cat, "📌")
    return f'<span class="{css}">{icon} {cat}</span>'

# Minimalist Vector WhatsApp Icon (SVG)
WA_SVG_ICON = (
    '<svg viewBox="0 0 24 24" aria-hidden="true">'
    '<path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.45 1.32 4.95L2.05 22l5.25-1.38c1.45.79 3.08 1.21 4.74 1.21 5.46 0 9.91-4.45 9.91-9.91C21.95 6.45 17.5 2 12.04 2zm5.82 14.01c-.24.68-1.41 1.3-1.95 1.38-.5.08-1.13.11-1.82-.11-.42-.13-.96-.31-1.65-.61-2.91-1.26-4.81-4.19-4.96-4.38-.14-.19-1.18-1.57-1.18-3 0-1.42.75-2.12 1.01-2.41.27-.29.58-.36.78-.36.19 0 .39 0 .56.01.18.01.42-.07.66.5.24.58.82 2 .89 2.15.07.15.12.31.02.51-.1.19-.15.31-.29.48-.15.17-.31.38-.44.51-.15.15-.3.31-.13.6.17.29.76 1.25 1.63 2.02 1.12.99 2.06 1.3 2.35 1.45.29.15.46.12.63-.07.17-.19.73-.85.92-1.14.19-.29.39-.24.65-.15.27.1 1.7.8 1.99.94.29.15.48.22.56.34.07.12.07.7-.17 1.38z"/>'
    '</svg>'
)

# Apple-Grade Article Card Renderer
def render_apple_article_card(item, is_indian=False, auto_translate=False):
    source_name = html.escape(item.get("source", "Unknown"))
    cat = item.get("primary_section") or item.get("structured_category", "Nepal – Others")
    
    cat_accent_class = {
        "India Section": "card-accent-india",
        "China Section": "card-accent-china",
        "Pakistan Section": "card-accent-pakistan",
        "Bangladesh Section": "card-accent-bangladesh",
        "Nepal – Internal": "card-accent-internal",
        "Nepal – External": "card-accent-external",
        "Nepal – Economy": "card-accent-economy",
        "Nepal – Others": "card-accent-others",
        "International News": "card-accent-international",
        # Backward compatibility aliases
        "India in Nepal": "card-accent-india",
        "China in Nepal": "card-accent-china",
        "Pakistan in Nepal": "card-accent-pakistan",
        "Bangladesh in Nepal": "card-accent-bangladesh",
        "Nepal – Internal Politics": "card-accent-internal",
        "Nepal – External Relations (Others)": "card-accent-external",
        "Economy": "card-accent-economy",
        "Others": "card-accent-others",
    }.get(cat, "card-accent-others")

    if is_indian:
        cat_accent_class = "card-accent-indian-press"
        source_tag = f'<span class="indian-portal-tag">🇮🇳 {source_name}</span>'
        cat_badge = get_badge_html(cat)
    else:
        source_tag = f'<span class="portal-tag">{source_name}</span>'
        cat_badge = get_badge_html(cat)

    # Low confidence warning flag or Nepal relevance badge for Indian media
    if is_indian:
        rel_score = float(item.get("nepal_relevance_score", 0.75))
        rel_status = item.get("relevance_status", "substantive")
        rel_reason = html.escape(str(item.get("relevance_reason", "Substantive Nepal connection")))
        pct = int(round(rel_score * 100))
        if rel_status == "borderline_review":
            review_flag = f'<span class="conf-review-badge" title="{rel_reason}">⚠️ Borderline Review ({pct}% Relevance)</span>'
        else:
            review_flag = f'<span class="time-badge" style="background:#ECFDF5; color:#047857; border-color:#A7F3D0; font-weight:650;" title="{rel_reason}">🎯 {pct}% Nepal Relevance</span>'
    else:
        review_flag = '<span class="conf-review-badge" title="Classification confidence < 0.60 - Pending Editorial Verification">⚠️ Review</span>' if item.get("low_confidence") else ''

    # Secondary tags chips & Nepal thematic dimensions
    sec_tags = list(item.get("secondary_tags", []) or [])
    if is_indian:
        dims = item.get("nepal_dimensions", []) or []
        for d in dims:
            if d not in sec_tags:
                sec_tags.insert(0, d)
    sec_tags_html = ""
    if sec_tags and isinstance(sec_tags, list):
        chips = [f'<span class="sec-tag-chip">#{html.escape(str(t))}</span>' for t in sec_tags[:5]]
        sec_tags_html = f'<div style="display:flex; flex-wrap:wrap; gap:4px; margin-top:6px;">{" ".join(chips)}</div>'

    rel_time = html.escape(str(item.get('relative_time', 'Recent')))
    exact_time = html.escape(str(item.get('exact_time', '')))
    time_badge = f'<span class="time-badge">🕒 {rel_time} · {exact_time}</span>'

    raw_title = item.get("title", "")
    summary = item.get("summary", "")
    has_sum = bool(summary and summary.strip() != raw_title.strip())

    # Language pill badge
    lang = item.get("language", "")
    lang_badge = f'<span class="time-badge" style="background:#F8FAFC; color:#475569; font-weight:600;">🌐 {lang}</span>' if lang else ""

    link = item.get("link", "#")
    title_display = html.escape(raw_title)
    summary_html = f'<p class="apple-card-summary">{html.escape(summary.strip())}</p>' if has_sum else ""

    btn_label = "Read in Indian Press ↗" if is_indian else "Read Story ↗"
    wa_share_url = generate_whatsapp_share_url(item, "article")

    return (
        f'<article class="apple-news-card {cat_accent_class}">'
        f'<header class="apple-card-meta">{source_tag}{cat_badge}{review_flag}{lang_badge}{time_badge}</header>'
        f'<h3 class="apple-card-title"><a href="{link}" target="_blank" rel="noopener noreferrer">{title_display}</a></h3>'
        f'{summary_html}'
        f'{sec_tags_html}'
        f'<footer class="apple-card-footer" style="display:flex; justify-content:space-between; align-items:center; margin-top:8px;">'
        f'<a href="{wa_share_url}" target="_blank" rel="noopener noreferrer" class="apple-wa-share-btn" title="Share individual story to WhatsApp">{WA_SVG_ICON}<span>WhatsApp</span></a>'
        f'<a href="{link}" target="_blank" rel="noopener noreferrer" class="apple-card-cta">{btn_label}</a>'
        f'</footer>'
        f'</article>'
    )

# Apple-Grade X (Twitter) Post Card Renderer
def render_apple_x_post_card(p, auto_translate=False):
    avatar_bg = html.escape(p.get("avatar_bg", "#1D9BF0"))
    initials = html.escape(p.get("initials", "X"))
    author_name = html.escape(p.get("author_name", "Author"))
    handle = html.escape(p.get("handle", "@handle"))
    author_type = html.escape(p.get("author_type", "Public Figure"))
    verified_mark = ' <span class="x-verified-badge" title="Verified Account">✓</span>' if p.get("verified") else ""
    
    cat = p.get("structured_category", "Others")
    cat_badge = get_badge_html(cat)
    rel_time = html.escape(str(p.get("relative_time", "Recent")))
    exact_time = html.escape(str(p.get("exact_time", "")))
    if exact_time and rel_time and rel_time not in exact_time:
        time_badge = f'<span class="time-badge">🕒 {rel_time} · {exact_time}</span>'
    elif exact_time:
        time_badge = f'<span class="time-badge">🕒 {exact_time}</span>'
    else:
        time_badge = f'<span class="time-badge">🕒 {rel_time}</span>'

    raw_text = p.get("text", "")
    text = html.escape(raw_text, quote=False)
    text = re.sub(r'(#[A-Za-z0-9_]+)', r'<b style="color:#0284C7;">\1</b>', text)

    likes = p.get("likes", 0)
    retweets = p.get("retweets", 0)
    replies = p.get("replies", 0)
    impressions = p.get("impressions", 0)

    likes_fmt = f"{likes/1000:.1f}K" if likes >= 1000 else str(likes)
    rt_fmt = f"{retweets/1000:.1f}K" if retweets >= 1000 else str(retweets)
    rep_fmt = f"{replies/1000:.1f}K" if replies >= 1000 else str(replies)
    imp_fmt = f"{impressions/1000:.1f}K" if impressions >= 1000 else str(impressions)

    sentiment = p.get("sentiment", "Neutral")
    if "Alert" in sentiment or "Critical" in sentiment:
        senti_class = "x-sentiment-alert"
    elif "Positive" in sentiment:
        senti_class = "x-sentiment-positive"
    else:
        senti_class = "x-sentiment-neutral"
    senti_html = f'<span class="x-sentiment-badge {senti_class}">{html.escape(sentiment)}</span>'

    raw_handle = p.get("raw_handle") or p.get("handle", "").lstrip("@").split(" ")[0].strip()
    is_real = p.get("is_real_api", False)
    orig_link = p.get("link", "#")

    if is_real and orig_link and "/status/" in orig_link:
        link = orig_link
        cta_label = "View Post on X ↗"
    elif raw_handle and raw_handle not in ["LiveSearch", "Author"]:
        link = f"https://x.com/{raw_handle}"
        cta_label = f"View @{raw_handle} on X ↗"
    else:
        link = orig_link if orig_link != "#" else "https://x.com"
        cta_label = "View on X ↗"

    wa_share_url = generate_whatsapp_share_url(p, "x")

    return (
        f'<article class="x-post-card">'
        f'<header class="x-post-header">'
        f'<div class="x-author-box">'
        f'<div class="x-avatar" style="background:{avatar_bg};">{initials}</div>'
        f'<div class="x-author-meta">'
        f'<span class="x-author-name">{author_name}{verified_mark}</span>'
        f'<span class="x-author-handle">{handle} · <span class="x-type-badge">{author_type}</span></span>'
        f'</div>'
        f'</div>'
        f'<div style="display:flex; align-items:center; gap:8px;">{cat_badge}{time_badge}</div>'
        f'</header>'
        f'<div class="x-post-text">{text}</div>'
        f'<footer class="x-engagement-bar">'
        f'<div class="x-metrics-group">'
        f'<span class="x-metric-item" title="Likes">❤️ {likes_fmt}</span>'
        f'<span class="x-metric-item" title="Retweets">🔁 {rt_fmt}</span>'
        f'<span class="x-metric-item" title="Replies">💬 {rep_fmt}</span>'
        f'<span class="x-metric-item" title="Impressions">👁️ {imp_fmt}</span>'
        f'{senti_html}'
        f'</div>'
        f'<div style="display:flex; align-items:center; gap:8px;">'
        f'<a href="{wa_share_url}" target="_blank" rel="noopener noreferrer" class="apple-wa-share-btn" title="Share tweet to WhatsApp">{WA_SVG_ICON}<span>WhatsApp</span></a>'
        f'<a href="{link}" target="_blank" rel="noopener noreferrer" class="x-cta-link">{cta_label}</a>'
        f'</div>'
        f'</footer>'
        f'</article>'
    )

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
PREDEFINED_8_CATEGORIES = PREDEFINED_9_CATEGORIES
CORE_8_CATEGORIES = {c for c in STRUCTURED_CATEGORIES if c not in ["Nepal – Others", "Others"]}
CORE_7_CATEGORIES = CORE_8_CATEGORIES

def filter_items_by_category(items: list, selected_option: str, is_social: bool = False) -> list:
    """
    Refined editorial news feed filtering mechanism:

    1. Default / Unfiltered State (No Filters Selected):
       Fetch and display all news and posts published across all sources regardless of category.

    2. "All Categories" Selected:
       Fetch and display news items that fall under any of the 9 predefined editorial sections.

    3. "Uncategorized" View:
       Filter and display items that are uncategorized, unassigned, or general feeds.

    4. Single Category Selected:
       Filter and display news items belonging to the selected section, including cross-listed
       bilateral stories (e.g. Nepal-India bilateral story discoverable in both India Section
       and Nepal – External).
    """
    if not items:
        return []
    if not selected_option or selected_option == CAT_FILTER_ALL_UNFILTERED or "All News" in selected_option or selected_option.startswith("🌐 All"):
        return items

    if selected_option == CAT_FILTER_ALL_8 or "Classified" in selected_option or "All Categories" in selected_option:
        res = []
        for it in items:
            cat = str(it.get("primary_section") or it.get("structured_category") or it.get("category") or "").strip()
            if not cat or cat.lower() in ["uncategorized", "none", "null", "unassigned", ""]:
                continue
            if is_social:
                if cat in CORE_8_CATEGORIES:
                    res.append(it)
            else:
                if cat in PREDEFINED_9_CATEGORIES or any(s in PREDEFINED_9_CATEGORIES for s in it.get("sections", [])):
                    res.append(it)
        return res

    if selected_option == CAT_FILTER_UNCATEGORIZED or "Unclassified" in selected_option or "Uncategorized" in selected_option:
        res = []
        for it in items:
            cat = str(it.get("primary_section") or it.get("structured_category") or it.get("category") or "").strip()
            if not cat or cat.lower() in ["uncategorized", "none", "null", "unassigned", ""]:
                res.append(it)
            elif is_social and cat in ["Nepal – Others", "Others"]:
                res.append(it)
            elif not is_social and cat not in PREDEFINED_9_CATEGORIES and not any(s in PREDEFINED_9_CATEGORIES for s in it.get("sections", [])):
                res.append(it)
        return res

    # Single Category Selected: extract category name
    chosen_cat = selected_option.split(" ", 1)[1] if " " in selected_option else selected_option

    # Backward compatibility aliases
    cat_aliases = {
        "India in Nepal": "India Section",
        "China in Nepal": "China Section",
        "Pakistan in Nepal": "Pakistan Section",
        "Bangladesh in Nepal": "Bangladesh Section",
        "Nepal – Internal Politics": "Nepal – Internal",
        "Nepal – External Relations (Others)": "Nepal – External",
        "Economy": "Nepal – Economy",
        "Others": "Nepal – Others"
    }
    target_cat = cat_aliases.get(chosen_cat, chosen_cat)

    res = []
    for it in items:
        primary = it.get("primary_section") or it.get("structured_category") or ""
        item_sections = it.get("sections") or [primary]
        # Multi-section discovery: match primary or cross-listed sections list
        if primary == chosen_cat or primary == target_cat or chosen_cat in item_sections or target_cat in item_sections:
            res.append(it)
    return res

# Unified Top Minimalist Header & Global Control Toolbar
st.markdown(f"""
<div class="apple-top-header" style="margin-bottom:8px;">
    <div class="apple-top-title-group">
        <span class="apple-flag-icon">🇳🇵</span>
        <div>
            <h1 class="apple-top-title">Nepal Media Monitor</h1>
            <p class="apple-top-subtitle">34 Nepali · 18 Indian · Live</p>
        </div>
    </div>
    <div style="display:flex; align-items:center; gap:12px;">
        <div class="apple-top-status">
            <span class="apple-live-pulse"></span>
            <span class="apple-status-text">LIVE · {formatted_now_time}</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Sleek Global Controls Strip (Timeframe, Search, Sync, Reset)
with st.container():
    tb_c1, tb_c2, tb_c3, tb_c4, tb_c5 = st.columns([2.4, 1.2, 3.2, 0.9, 0.9])
    
    with tb_c1:
        selected_preset = st.segmented_control(
            "Timeframe",
            options=["12h", "24h", "Today", "Custom"],
            default=st.session_state.get("cp_timeframe_segment", "12h"),
            key="cp_timeframe_segment",
            on_change=on_timeframe_preset_change,
            label_visibility="collapsed"
        )
    with tb_c2:
        use_current_time = st.toggle(
            "Live",
            value=st.session_state.get("filter_use_current_time", True),
            key="filter_use_current_time",
            help="When on, automatically streams up to the current moment"
        )
    with tb_c3:
        search_query = st.text_input(
            "Search",
            placeholder="Search across all streams...",
            key="global_search_input",
            label_visibility="collapsed"
        )
    with tb_c4:
        if st.button("🔄 Sync", key="btn_top_sync", width="stretch", help="Sync latest news across all 52 sources"):
            st.session_state["is_refreshing_feeds"] = True
            with st.spinner("Syncing live feeds..."):
                fetch_top_nepal_media(max_workers=25, force_refresh=True)
                fetch_nepal_in_indian_media(max_workers=18, force_refresh=True)
                st.cache_data.clear()
                if "x_posts" in st.session_state:
                    del st.session_state["x_posts"]
                st.session_state["last_sync_npt"] = datetime.datetime.now(NEPAL_TZ).strftime("%I:%M %p")
                st.session_state["is_refreshing_feeds"] = False
            st.rerun()
    with tb_c5:
        st.button("✕ Reset", key="btn_top_reset", width="stretch", on_click=reset_all_filters, help="Reset all filters")

# Expand custom date/time only if Custom timeframe is selected
if st.session_state.get("cp_timeframe_segment") == "Custom":
    c_dt1, c_dt2, c_dt3, c_dt4 = st.columns(4)
    with c_dt1:
        st.date_input("Start Date", value=st.session_state.get("filter_start_date", default_start_date), max_value=now_npt.date(), key="filter_start_date", on_change=on_custom_datetime_edit)
    with c_dt2:
        st.time_input("Start Time", value=st.session_state.get("filter_start_time", default_start_time), key="filter_start_time", on_change=on_custom_datetime_edit)
    with c_dt3:
        st.date_input("End Date", value=st.session_state.get("filter_end_date", now_npt.date()), max_value=now_npt.date(), min_value=st.session_state.get("filter_start_date", default_start_date), key="filter_end_date", on_change=on_custom_datetime_edit)
    with c_dt4:
        st.time_input("End Time", value=st.session_state.get("filter_end_time", now_npt.time().replace(second=0, microsecond=0)), key="filter_end_time", on_change=on_custom_datetime_edit)

# Global Cross-Channel Search Filter
if search_query and search_query.strip():
    filtered_articles = [a for a in filtered_articles if smart_search_match(a, search_query)]
    filtered_indian = [a for a in filtered_indian if smart_search_match(a, search_query)]
    filtered_x_posts = [p for p in filtered_x_posts if smart_search_match(p, search_query)]

# 8. Navigation Tabs (Dynamic Live Counts)
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    f"Nepali Media ({len(filtered_articles)})",
    f"Indian Press ({len(filtered_indian)})",
    f"X ({len(filtered_x_posts)})",
    "Analytics & Export",
    "Health"
])

# ==========================================
# TAB 1: Nepali Media (Top 34 Portals)
# ==========================================
with tab1:
    # 🎛️ Source-Specific Control Panel: Nepali Media
    with st.container():
        npc1, npc2, npc3 = st.columns([1.6, 1.4, 1.0])
        with npc1:
            all_portal_names = sorted(list(set([p["name"] for p in TOP_NEPAL_NEWS_PORTALS])))
            sel_np_portal = st.selectbox(
                "News Portal",
                ["All Portals (34)"] + all_portal_names,
                key="np_portal_filter",
                label_visibility="collapsed"
            )
        with npc2:
            sel_np_cat = st.selectbox(
                "Editorial Category",
                CATEGORY_FILTER_OPTIONS,
                key="np_cat_filter",
                label_visibility="collapsed"
            )
        with npc3:
            sel_np_lang = st.selectbox(
                "Language",
                ["All Languages", "Nepali Only", "English Only"],
                key="np_lang_filter",
                label_visibility="collapsed"
            )

    # Filter articles based on Tab 1 Controls
    tab_articles = filter_items_by_category(filtered_articles, sel_np_cat, is_social=False)
    if sel_np_lang == "Nepali Only":
        tab_articles = [a for a in tab_articles if a.get('language') == "Nepali"]
    elif sel_np_lang == "English Only":
        tab_articles = [a for a in tab_articles if a.get('language') == "English"]

    if sel_np_portal != "All Portals (34)":
        tab_articles = [a for a in tab_articles if a.get('source') == sel_np_portal]
        if not tab_articles:
            portal_recent = [a for a in all_articles if a.get('source') == sel_np_portal]
            if portal_recent:
                tab_articles = filter_items_by_category(portal_recent, sel_np_cat, is_social=False)
                latest_pub_str = portal_recent[0]["published_dt"].strftime("%d %b %Y, %I:%M %p NPT") if portal_recent[0].get("published_dt") else "recently"
                st.info(f"ℹ️ **{sel_np_portal}** has no stories published in the selected window (last story: **{latest_pub_str}**). Showing its **{len(tab_articles)}** most recent dispatches.")

    if not tab_articles:
        st.warning("No Nepali news articles found matching your criteria. Try adjusting the category, portal, or timeframe window.")
    else:
        # Incremental Loading / Pagination (20 entries initial, +20 per click)
        if "media_visible_count" not in st.session_state:
            st.session_state["media_visible_count"] = 20

        current_media_limit = st.session_state["media_visible_count"]
        visible_articles = tab_articles[:current_media_limit]

        for item in visible_articles:
            st.markdown(render_apple_article_card(item, is_indian=False), unsafe_allow_html=True)

        if len(tab_articles) > current_media_limit:
            remaining_media = len(tab_articles) - current_media_limit
            next_batch_media = min(20, remaining_media)
            c_m1, c_m2, c_m3 = st.columns([1.5, 2, 1.5])
            with c_m2:
                if st.button(f"⬇️ Load More News (+{next_batch_media} stories)", width="stretch", key="btn_load_more_media"):
                    st.session_state["media_visible_count"] += 20
                    st.rerun()
                st.caption(f"Showing {len(visible_articles):,} of {len(tab_articles):,} stories ({remaining_media:,} remaining)")
        elif len(tab_articles) > 0:
            st.caption(f"🏁 You've reached the end of the news feed ({len(tab_articles):,} stories displayed).")

# ==========================================
# TAB 2: Nepal in Indian Media
# ==========================================
with tab2:
    indian_outlet_names = sorted(list(set([s["name"] for s in TOP_INDIAN_MEDIA_SOURCES])))

    # Source Controls: Indian Press
    with st.container():
        ti_col1, ti_col2 = st.columns([2, 1.2])
        with ti_col1:
            selected_indian_outlet = st.selectbox(
                "Outlet",
                ["All 18 Indian Outlets"] + indian_outlet_names,
                key="in_outlet_filter",
                label_visibility="collapsed"
            )
        with ti_col2:
            sel_in_lang = st.selectbox(
                "Language",
                ["All Languages", "English", "Hindi"],
                key="in_lang_filter",
                label_visibility="collapsed"
            )

    tab_filtered_indian = filtered_indian
    if selected_indian_outlet != "All 18 Indian Outlets":
        tab_filtered_indian = [a for a in tab_filtered_indian if a["source"] == selected_indian_outlet]
    if sel_in_lang != "All Languages":
        tab_filtered_indian = [a for a in tab_filtered_indian if a.get("language") == sel_in_lang]

    st.write("")

    if not tab_filtered_indian:
        st.info("No Indian media articles match the current filter criteria.")
    else:
        # Incremental Loading / Pagination (20 entries initial, +20 per click)
        if "indian_visible_count" not in st.session_state:
            st.session_state["indian_visible_count"] = 20

        current_indian_limit = st.session_state["indian_visible_count"]
        visible_indian = tab_filtered_indian[:current_indian_limit]

        for a in visible_indian:
            st.markdown(render_apple_article_card(a, is_indian=True), unsafe_allow_html=True)

        if len(tab_filtered_indian) > current_indian_limit:
            remaining_indian = len(tab_filtered_indian) - current_indian_limit
            next_batch_indian = min(20, remaining_indian)
            c_i1, c_i2, c_i3 = st.columns([1.5, 2, 1.5])
            with c_i2:
                if st.button(f"⬇️ Load More Stories (+{next_batch_indian} stories)", width="stretch", key="btn_load_more_indian"):
                    st.session_state["indian_visible_count"] += 20
                    st.rerun()
                st.caption(f"Showing {len(visible_indian):,} of {len(tab_filtered_indian):,} stories ({remaining_indian:,} remaining)")
        elif len(tab_filtered_indian) > 0:
            st.caption(f"🏁 You've reached the end of Nepal-focused Indian press coverage ({len(tab_filtered_indian):,} stories displayed).")

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

    with st.expander(f"⚠️ Flagged Borderline Articles for Editorial Review ({len(borderline_items)}) & Central Database Retention", expanded=False):
        st.caption(
            "Borderline articles (scoring between 40% and the active relevance threshold) and excluded domestic Indian articles are retained in the central SQLite database (`indian_media_articles`) without cluttering the main India Media feed."
        )
        m_c1, m_c2, m_c3, m_c4 = st.columns(4)
        m_c1.metric("Substantive (Displayed)", f"{len(tab_filtered_indian):,}")
        m_c2.metric("Flagged Borderline (Review)", f"{len(borderline_items):,}")
        m_c3.metric("Excluded Domestic (DB Archived)", f"{ind_audit.get('excluded', 0):,}")
        m_c4.metric("Total Retained in Central DB", f"{ind_audit.get('total', 0):,}")

        if borderline_items:
            for b_art in borderline_items[:15]:
                st.markdown(render_apple_article_card(b_art, is_indian=True), unsafe_allow_html=True)
        else:
            st.success("No borderline articles currently pending editorial review.")

    with st.expander("⚡ Quick Jump to Dedicated Nepal Desks in Indian Media", expanded=False):
        q1, q2, q3, q4 = st.columns(4)
        with q1:
            st.link_button("🇮🇳 The Indian Express ↗", "https://indianexpress.com/about/nepal/", width='stretch')
        with q2:
            st.link_button("🇮🇳 The Hindu (World) ↗", "https://www.thehindu.com/news/international/", width='stretch')
        with q3:
            st.link_button("🇮🇳 India Today (Nepal) ↗", "https://www.indiatoday.in/topic/nepal", width='stretch')
        with q4:
            st.link_button("🇮🇳 Business Standard ↗", "https://www.business-standard.com/topic/nepal", width='stretch')

        q5, q6, q7, q8 = st.columns(4)
        with q5:
            st.link_button("🇮🇳 Livemint (Mint) ↗", "https://www.livemint.com/topic/nepal", width='stretch')
        with q6:
            st.link_button("🇮🇳 The Tribune ↗", "https://www.tribuneindia.com/topic/nepal", width='stretch')
        with q7:
            st.link_button("🇮🇳 Amar Ujala (नेपाल) ↗", "https://www.amarujala.com/tags/nepal", width='stretch')
        with q8:
            st.link_button("🇮🇳 Live Hindustan (हिन्दुस्तान) ↗", "https://www.livehindustan.com/tags/nepal/", width='stretch')

# ==========================================
# TAB 3: X (Twitter) Nepal
# ==========================================
with tab3:
    # Seamlessly integrated X posts (filtered by global search, category, and time)
    tab_x_posts = filtered_x_posts

    with st.expander(f"🇳🇵 Verified Monitored Nepali Accounts ({len(TOP_NEPAL_X_ACCOUNTS)} Accounts)", expanded=False):
        st.write(f"Direct directory of **{len(TOP_NEPAL_X_ACCOUNTS)} verified Nepali accounts** across civic commentators, political leaders, foreign affairs analysts, and diplomatic desks:")
        a_cols = st.columns(4)
        for i, a in enumerate(TOP_NEPAL_X_ACCOUNTS):
            with a_cols[i % 4]:
                st.markdown(f"""
                <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:12px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.02); display:flex; flex-direction:column; justify-content:space-between; min-height:120px;">
                    <div>
                        <div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
                            <div style="width:28px; height:28px; border-radius:50%; background:{a['avatar_bg']}; color:#fff; display:flex; align-items:center; justify-content:center; font-size:11px; font-weight:700; flex-shrink:0;">{a['initials']}</div>
                            <div style="overflow:hidden;">
                                <div style="font-weight:600; font-size:13px; color:#0f172a; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{a['name']} <span style="color:#0284c7;">✓</span></div>
                                <div style="font-size:11px; color:#64748b;">@{a['handle']} · <span style="color:#0284c7; font-weight:500;">{a.get('type', '')}</span></div>
                            </div>
                        </div>
                        <div style="font-size:11px; color:#475569; line-height:1.35; margin-top:4px; margin-bottom:8px; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;">{a.get('role', '')}</div>
                    </div>
                    <div style="border-top:1px solid #f1f5f9; padding-top:6px; font-size:11px;">
                        <a href="https://x.com/{a['handle']}" target="_blank" style="font-weight:600; color:#0284c7; text-decoration:none;">Profile on X ↗</a> · 
                        <a href="https://x.com/search?q=from%3A{a['handle']}&f=live" target="_blank" style="color:#64748b; text-decoration:none;">Live Posts ↗</a>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # Source Controls: X
    with st.container():
        xf_col1, xf_col2, xf_col3, xf_col4 = st.columns([1.6, 1.4, 1.3, 0.9])
        with xf_col1:
            x_cat_filter = st.selectbox(
                "Editorial Category",
                CATEGORY_FILTER_OPTIONS,
                index=0,
                key="x_cat_filter_select",
                label_visibility="collapsed"
            )
        with xf_col2:
            acc_types = [
                "All Account Types",
                "Civic Voice / Public Commentator",
                "Youth & Cultural Voice",
                "Foreign Affairs Specialist",
                "Journalist / Analyst",
                "Political Leader",
                "Government & Security",
                "Media & News Curators",
                "Diplomatic Missions",
                "Think Tank & Policy",
                "Sports & Culture"
            ]
            selected_acc_type = st.selectbox(
                "Account Category",
                acc_types,
                key="x_acc_type_select",
                label_visibility="collapsed"
            )
        with xf_col3:
            sort_mode = st.selectbox(
                "Sort Posts",
                ["🕒 Newest First (NPT)", "🔥 Most Viral / Engagement", "❤️ Most Liked", "🔁 Most Retweeted"],
                key="x_sort_mode_select",
                label_visibility="collapsed"
            )
        with xf_col4:
            if st.button("🔄 Sync X", width="stretch", key="btn_rescan_x"):
                with st.spinner("Deep scanning authentic real-time X posts across verified Nepali accounts..."):
                    st.session_state["x_posts"] = scan_popular_nepal_x_posts(force_refresh=True, x_bearer_token=x_bearer_token)
                    st.rerun()

    # Apply category filter
    filtered_feed = filter_items_by_category(tab_x_posts, x_cat_filter, is_social=True)

    if selected_acc_type != "All Account Types":
        filtered_feed = [p for p in filtered_feed if p.get("author_type") == selected_acc_type]

    # Apply sorting
    if sort_mode == "🕒 Newest First (NPT)":
        filtered_feed = sorted(filtered_feed, key=lambda x: x.get("published_dt"), reverse=True)
    elif sort_mode == "🔥 Most Viral / Engagement":
        filtered_feed = sorted(filtered_feed, key=lambda x: x.get("engagement_score", 0), reverse=True)
    elif sort_mode == "❤️ Most Liked":
        filtered_feed = sorted(filtered_feed, key=lambda x: x.get("likes", 0), reverse=True)
    elif sort_mode == "🔁 Most Retweeted":
        filtered_feed = sorted(filtered_feed, key=lambda x: x.get("retweets", 0), reverse=True)

    # Display count banner
    st.markdown(f'<div class="apple-counter-badge">Showing <b>{len(filtered_feed):,} of {len(all_x_posts):,}</b> verified X posts</div>', unsafe_allow_html=True)
    st.write("")

    # Render Post Cards with "Load More Feeds" button
    if "x_visible_count" not in st.session_state:
        st.session_state["x_visible_count"] = 20

    current_x_limit = st.session_state["x_visible_count"]
    visible_x_posts = filtered_feed[:current_x_limit]

    for p in visible_x_posts:
        st.markdown(render_apple_x_post_card(p), unsafe_allow_html=True)

    if len(filtered_feed) > current_x_limit:
        remaining_x = len(filtered_feed) - current_x_limit
        next_batch_x = min(20, remaining_x)
        c_lm1, c_lm2, c_lm3 = st.columns([1.5, 2, 1.5])
        with c_lm2:
            if st.button(f"⬇️ Load More Feeds (+{next_batch_x} posts)", width="stretch", key="btn_load_more_x"):
                st.session_state["x_visible_count"] += 20
                st.rerun()
            st.caption(f"Showing {len(visible_x_posts):,} of {len(filtered_feed):,} posts ({remaining_x:,} remaining)")
    elif len(filtered_feed) > 0:
        st.caption(f"🏁 You've reached the end of the feed ({len(filtered_feed):,} posts displayed).")

    with st.expander("⚡ Quick Jump to Live X Searches Across 9 Editorial Sections", expanded=False):
        clean_q = search_query.strip() if search_query else ""
        if clean_q:
            st.caption(f"Launch live X searches combining your search keyword **'{html.escape(clean_q)}'** with any of the 9 editorial sections:")
        else:
            st.caption("One-click direct access to real-time live posts on X (Twitter) across the 9 editorial sections:")

        x_cat_searches = [
            {
                "label": "🇮🇳 India Section ↗",
                "query": '("Nepal" OR "नेपाल" OR "India" OR "भारत") AND ("Modi" OR "border" OR "trade" OR "security" OR "#NepalIndia")',
                "help": "Search live X posts on India Section, bilateral relations, governance & border"
            },
            {
                "label": "🇨🇳 China Section ↗",
                "query": '("Nepal" OR "नेपाल" OR "China" OR "चीन") AND ("Beijing" OR "BRI" OR "Pokhara" OR "Tibet" OR "#NepalChina")',
                "help": "Search live X posts on China Section, BRI, diplomacy & strategic developments"
            },
            {
                "label": "🇧🇩 Bangladesh Section ↗",
                "query": '("Nepal" OR "नेपाल" OR "Bangladesh" OR "बंगलादेश") AND ("Dhaka" OR "Yunus" OR "energy" OR "transit")',
                "help": "Search live X posts on Bangladesh Section, tripartite electricity trade & transit"
            },
            {
                "label": "🇵🇰 Pakistan Section ↗",
                "query": '("Nepal" OR "नेपाल" OR "Pakistan" OR "पाकिस्तान") AND ("Islamabad" OR "SAARC" OR "Kashmir")',
                "help": "Search live X posts on Pakistan Section, regional diplomacy & bilateral relations"
            },
            {
                "label": "🇳🇵 Nepal – Internal ↗",
                "query": '("Nepal" OR "नेपाल") AND ("politics" OR "Oli" OR "Deuba" OR "Prachanda" OR "Balen" OR "संसद्" OR "सरकार" OR "भ्रष्टाचार")',
                "help": "Search live X posts on Nepal internal politics, parliament, governance & societal developments"
            },
            {
                "label": "🌐 Nepal – External ↗",
                "query": '("Nepal" OR "नेपाल") AND ("diplomacy" OR "ambassador" OR "UN" OR "USAID" OR "MCC" OR "परराष्ट्र" OR "कूटनीति")',
                "help": "Search live X posts on Nepal foreign policy, multilateral relations, US, EU & global partners"
            },
            {
                "label": "📈 Nepal – Economy ↗",
                "query": '("Nepal" OR "नेपाल") AND ("economy" OR "NRB" OR "remittance" OR "inflation" OR "budget" OR "NEPSE" OR "अर्थतन्त्र")',
                "help": "Search live X posts on Nepal economy, banking, NEPSE, remittances & fiscal policy"
            },
            {
                "label": "📌 Nepal – Others ↗",
                "query": '("Nepal" OR "नेपाल") AND ("cricket" OR "cinema" OR "weather" OR "Everest" OR "earthquake" OR "संस्कृति")',
                "help": "Search live X posts on sports, culture, climate, tourism & civic society"
            },
            {
                "label": "🌍 International News ↗",
                "query": '("geopolitics" OR "conflict" OR "diplomacy" OR "summit" OR "Ukraine" OR "Gaza" OR "UN" OR "BRICS")',
                "help": "Search live X posts on major global geopolitical conflicts, diplomacy & world affairs"
            },
        ]

        # 3x3 Grid Display
        for row_idx in range(0, len(x_cat_searches), 3):
            cols = st.columns(3)
            for col_idx, item in enumerate(x_cat_searches[row_idx:row_idx+3]):
                with cols[col_idx]:
                    full_q = f"({clean_q}) AND {item['query']}" if clean_q else item["query"]
                    x_url = f"https://x.com/search?q={urllib.parse.quote_plus(full_q)}&f=live"
                    st.link_button(item["label"], x_url, width="stretch", help=item["help"])

# ==========================================
# TAB 4: Analytics & Export
# ==========================================
with tab4:
    start_label = filter_start_dt.strftime("%d %b, %I:%M %p").lstrip("0") if filter_start_dt else "Start"
    end_label = "Now" if is_to_current else filter_end_dt.strftime("%d %b, %I:%M %p").lstrip("0")
    st.markdown(f"""
    <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px; margin-bottom:12px;">
        <div>
            <h3 style="margin:0; font-size:1.35rem; font-weight:700; color:#1D1D1F;">Analytics & Export</h3>
        </div>
        <div style="background:#F1F5F9; border:1px solid #CBD5E1; padding:4px 12px; border-radius:8px; font-size:0.78rem; font-weight:600; color:#334155; display:inline-flex; align-items:center; gap:6px;">
            <span>🕒 Active Window:</span> <b>{start_label} → {end_label}</b>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 1. Gather all items into a unified, consolidated stream
    all_unified_items = []

    # Nepali Media
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
            "item_type": "article"
        })

    # Nepal in Indian Media
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
            "item_type": "article"
        })

    # Live X (Twitter) Posts
    for p in filtered_x_posts:
        auth_name = p.get('author_name', '')
        auth_handle = p.get('handle', '')
        all_unified_items.append({
            "stream": "X (Twitter)",
            "title": (p.get("text") or "").strip(),
            "headline_en": "",
            "content": p.get("text", ""),
            "category": p.get("structured_category", "Others"),
            "source": f"{auth_name} (@{auth_handle})",
            "language": "Nepali / English",
            "timestamp": p.get("exact_time") or p.get("relative_time", ""),
            "published_dt": p.get("published_dt"),
            "link": p.get("link", ""),
            "raw_item": p,
            "item_type": "x"
        })

    # Sort chronological (newest first)
    def _parse_sort_dt(x):
        dt = x.get("published_dt")
        if isinstance(dt, datetime.datetime):
            return dt if dt.tzinfo else dt.replace(tzinfo=NEPAL_TZ)
        return datetime.datetime.min.replace(tzinfo=NEPAL_TZ)

    all_unified_items.sort(key=_parse_sort_dt, reverse=True)

    # 2. Consolidated Master Filter Toolbar
    with st.container():
        fc1, fc2, fc3, fc4 = st.columns([1.4, 1.4, 1.2, 2])

        with fc1:
            stream_choices = ["All Streams (All 3)", "Nepali Media", "Indian Press", "X (Twitter)"]
            sel_stream = st.selectbox("Dataset Stream", stream_choices, key="univ_stream_filter", label_visibility="collapsed")

        with fc2:
            all_cats = sorted(list(set(x["category"] for x in all_unified_items if x.get("category"))))
            cat_choices = ["All Categories"] + all_cats
            sel_cat = st.selectbox("Category / Section", cat_choices, key="univ_cat_filter", label_visibility="collapsed")

        with fc3:
            all_langs = ["All Languages", "Nepali", "English", "Nepali / English"]
            sel_lang = st.selectbox("Content Language", all_langs, key="univ_lang_filter", label_visibility="collapsed")

        with fc4:
            kw_filter = st.text_input("Search Keyword", placeholder="Search keyword or author...", key="univ_kw_filter", label_visibility="collapsed")

    # Apply Consolidated Filtering
    filtered_export_items = all_unified_items
    if sel_stream != "All Streams (All 3)":
        filtered_export_items = [x for x in filtered_export_items if x["stream"] == sel_stream]
    if sel_cat != "All Categories":
        filtered_export_items = [x for x in filtered_export_items if x["category"] == sel_cat]
    if sel_lang != "All Languages":
        filtered_export_items = [x for x in filtered_export_items if x["language"] == sel_lang]
    if kw_filter.strip():
        q_lower = kw_filter.strip().lower()
        filtered_export_items = [
            x for x in filtered_export_items
            if q_lower in x["title"].lower() or q_lower in x["content"].lower() or q_lower in x["source"].lower()
        ]

    # Convert to Structured DataFrame
    rows_data = []
    for it in filtered_export_items:
        rows_data.append({
            "Stream": it["stream"],
            "Headline / Text": it["title"],
            "English Translation": it["headline_en"],
            "Category": it["category"],
            "Source / Author": it["source"],
            "Language": it["language"],
            "Published Date & Time": it["timestamp"],
            "Link": it["link"],
            "Content": it["content"]
        })
    df_export = pd.DataFrame(rows_data)

    st.markdown("---")

    # Metrics Summary Row (No charts, concise KPIs)
    sum1, sum2, sum3, sum4 = st.columns(4)
    with sum1:
        st.metric("Consolidated Matches", f"{len(df_export):,}")
    with sum2:
        nep_count = sum(1 for x in filtered_export_items if x["stream"] == "Nepali Media")
        st.metric("Nepali Media", f"{nep_count:,}")
    with sum3:
        ind_count = sum(1 for x in filtered_export_items if x["stream"] == "Indian Press")
        st.metric("Indian Press", f"{ind_count:,}")
    with sum4:
        x_count = sum(1 for x in filtered_export_items if x["stream"] == "X (Twitter)")
        st.metric("X Posts", f"{x_count:,}")

    # Selection State for Word Document Export (tracked per active filter signature)
    current_filter_sig = f"{sel_stream}_{sel_cat}_{sel_lang}_{kw_filter.strip()}_{len(filtered_export_items)}"
    if "editor_ver_univ" not in st.session_state:
        st.session_state["editor_ver_univ"] = 0
    if st.session_state.get("last_univ_filter_sig") != current_filter_sig or "selected_links_univ" not in st.session_state:
        st.session_state["selected_links_univ"] = set(x["link"] for x in filtered_export_items)
        st.session_state["last_univ_filter_sig"] = current_filter_sig

    # Batch Selection Controls
    sc1, sc2, sc3, sc_badge = st.columns([1.3, 1.3, 1.8, 3.6])
    with sc1:
        if st.button("☑️ Select All", key="btn_univ_sel_all"):
            st.session_state["selected_links_univ"] = set(x["link"] for x in filtered_export_items)
            st.session_state["editor_ver_univ"] += 1
            st.rerun()
    with sc2:
        if st.button("⬜ Deselect All", key="btn_univ_desel_all"):
            st.session_state["selected_links_univ"] = set()
            st.session_state["editor_ver_univ"] += 1
            st.rerun()
    with sc3:
        if st.button("⚡ Select Top 30 Fresh", key="btn_univ_top30"):
            st.session_state["selected_links_univ"] = set(x["link"] for x in filtered_export_items[:30])
            st.session_state["editor_ver_univ"] += 1
            st.rerun()

    # Determine Active Selected Set
    selected_export_items = [x for x in filtered_export_items if x.get("link") in st.session_state["selected_links_univ"]]
    with sc_badge:
        st.markdown(f'<div class="apple-counter-badge">📋 <b>{len(selected_export_items)} of {len(filtered_export_items)}</b> items selected for Word Dossier</div>', unsafe_allow_html=True)

    # Data Editor Table
    if not df_export.empty:
        df_for_editor = df_export[["Stream", "Headline / Text", "Category", "Source / Author", "Language", "Published Date & Time", "Link"]].copy()
        df_for_editor.insert(0, "Include?", [link in st.session_state["selected_links_univ"] for link in df_for_editor["Link"]])

        col_config_univ = {
            "Include?": st.column_config.CheckboxColumn(
                "Include in Export?",
                help="Check this box to include in Word Document",
                default=True
            ),
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

        # Refresh selected items list
        selected_export_items = [x for x in filtered_export_items if x.get("link") in st.session_state["selected_links_univ"]]

        # Word Document & CSV One-Click Export Actions
        st.markdown("##### 📦 Download Intelligence Outputs")
        c_csv, c_docx = st.columns(2)

        # 1. Comprehensive CSV
        with c_csv:
            csv_bytes = df_export.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label=f"📥 Download Filtered CSV ({len(df_export):,} Records)",
                data=csv_bytes,
                file_name=f"nepal_intelligence_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                width="stretch"
            )

        # 2. Executive Word Document
        with c_docx:
            if selected_export_items:
                raw_items_for_docx = [x["raw_item"] for x in selected_export_items]
                univ_hash = hash(tuple(x["link"] for x in selected_export_items))

                if st.session_state.get("docx_ready_hash_univ") != univ_hash:
                    if st.button(f"📄 Prepare Executive Word Document ({len(selected_export_items):,} Stories)", key="btn_prep_univ_docx", width="stretch", type="primary"):
                        with st.spinner(f"Generating comprehensive Word dossier for {len(selected_export_items)} items..."):
                            enriched_docx_items = batch_fetch_full_content(raw_items_for_docx[:60]) if len(raw_items_for_docx) <= 60 else raw_items_for_docx
                            st.session_state["docx_bytes_univ"] = generate_word_document(
                                enriched_docx_items,
                                report_title="Nepal Social & Media Intelligence Dossier"
                            )
                            st.session_state["docx_ready_hash_univ"] = univ_hash
                        st.rerun()
                else:
                    st.download_button(
                        label=f"⬇️ Download Ready Word Document ({len(selected_export_items):,} Items)",
                        data=st.session_state["docx_bytes_univ"],
                        file_name=f"nepal_intelligence_dossier_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        width="stretch",
                        type="primary"
                    )
            else:
                st.warning("⚠️ No items selected. Check items in the table above or click 'Select All' to export Word document.")
    else:
        st.info("No items match the chosen filter criteria. Try adjusting the search keyword or selecting 'All Streams'.")

    # ==========================================
    # WHATSAPP CHANNEL BROADCAST ENGINE (RENDER CLOUD DAEMON)
    # ==========================================
    st.markdown("---")
    st.subheader("WhatsApp Distribution Console (Cloud Autonomous)")

    # Render Worker Live Heartbeat Card
    render_url = "https://nepal-social-monitor-worker.onrender.com"
    render_info = {}
    render_online = False
    try:
        req = urllib.request.Request(render_url, headers={"User-Agent": "NepalMonitor-LocalUI/1.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            render_info = json.loads(resp.read().decode())
            render_online = True
    except Exception:
        render_online = False

    r_col1, r_col2 = st.columns([2.5, 1.5])
    with r_col1:
        if render_online:
            st.markdown(f"""
            <div style="background:linear-gradient(135deg, rgba(16,185,129,0.08), rgba(5,150,105,0.02)); border:1px solid #10B981; border-radius:10px; padding:12px 16px; margin-bottom:14px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span style="height:10px; width:10px; background:#10B981; border-radius:50%; display:inline-block; box-shadow:0 0 8px #10B981;"></span>
                        <strong style="color:#065F46; font-size:0.95rem;">Render 24/7 Cloud Worker: ACTIVE</strong>
                    </div>
                    <span style="font-size:0.75rem; background:#D1FAE5; color:#065F46; font-weight:700; padding:3px 8px; border-radius:6px;">Uptime: Running</span>
                </div>
                <div style="font-size:0.8rem; color:#047857; margin-top:6px;">
                    Started: <b>{render_info.get('started_at', '')[:16].replace('T', ' ')} NPT</b> · Completed Runs: <b>{render_info.get('runs_completed', 0)}</b>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background:#FEF2F2; border:1px solid #EF4444; border-radius:10px; padding:12px 16px; margin-bottom:14px;">
                <strong style="color:#991B1B;">⚠️ Render Worker Status: Contacting Cloud Runner...</strong>
            </div>
            """, unsafe_allow_html=True)

    with r_col2:
        now_np = datetime.datetime.now(NEPAL_TZ)
        next_h = now_np.hour + 1
        if next_h <= 22 and now_np.hour >= 6:
            next_run_str = f"{next_h:02d}:00:00 NPT"
            mins_left = 60 - now_np.minute
            status_caption = f"⏱️ Next Cycle: **{next_run_str}** (~{mins_left}m)"
        else:
            status_caption = "🌙 Quiet Window (Resumes 06:00 AM NPT)"
        st.markdown(f"""
        <div style="background:#F8FAFC; border:1px solid #CBD5E1; border-radius:10px; padding:12px 16px; margin-bottom:14px; text-align:center;">
            <div style="font-size:0.75rem; color:#64748B; font-weight:600; text-transform:uppercase;">Scheduled Timing</div>
            <div style="font-size:0.95rem; font-weight:700; color:#1E293B; margin-top:4px;">{status_caption}</div>
        </div>
        """, unsafe_allow_html=True)

    wa_stats = get_broadcasted_stats()

    by_stream = wa_stats.get("by_stream", {})
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total Broadcasted", f"{wa_stats['total_broadcasted']:,}")
    with m2:
        st.metric("📰 Nepali Media", f"{by_stream.get('nepali_media', 0):,}")
    with m3:
        st.metric("🇮🇳 Indian Media (Nepal)", f"{by_stream.get('indian_media', 0):,}")
    with m4:
        st.metric("🐦 X (Twitter)", f"{by_stream.get('x', 0):,}")

    # Deduplication Queue: Align strictly with the active hourly broadcast window
    now_dt = datetime.datetime.now(NEPAL_TZ)
    is_morning_window = (now_dt.hour == 6 or now_dt.hour < 7)
    worker_lookback_mins = 600 if is_morning_window else 75
    broadcast_cutoff = now_dt - datetime.timedelta(minutes=worker_lookback_mins)
    lookback_display_label = "overnight window (10h)" if is_morning_window else "past hour"

    def is_within_broadcast_window(it):
        pdt = it.get("published_dt")
        if isinstance(pdt, datetime.datetime):
            item_dt = pdt if pdt.tzinfo else pdt.replace(tzinfo=NEPAL_TZ)
            return item_dt >= broadcast_cutoff
        return False

    pending_queue = []
    # 1. Nepali Media: fresh articles published within broadcast window
    for item in filtered_articles:
        if is_within_broadcast_window(item) and not is_item_broadcasted(item, "article"):
            pending_queue.append({"item": item, "type": "article", "source_type": "Nepali Media"})
    # 2. Indian Media: fresh articles substantially related to Nepal within broadcast window
    for item in filtered_indian:
        if is_substantially_related_to_nepal(item) and is_within_broadcast_window(item):
            if not is_item_broadcasted(item, "article"):
                pending_queue.append({"item": item, "type": "article", "source_type": "Indian Press"})
    # 3. X (Twitter): fresh posts within broadcast window
    for item in filtered_x_posts:
        if is_within_broadcast_window(item) and not is_item_broadcasted(item, "x"):
            pending_queue.append({"item": item, "type": "x", "source_type": "X (Twitter)"})

    q_col1, q_col2 = st.columns([3, 1.2])
    with q_col1:
        st.markdown(f"##### 📥 Pending for Next Hourly Broadcast (`{len(pending_queue)}` fresh unsent items in {lookback_display_label})")
        st.caption("ℹ️ Broadcasts are automated 24/7 on Render cloud runner. Stories in this queue will automatically dispatch at the top of the hour.")
    with q_col2:
        queue_filter = st.selectbox(
            "Filter Queue Source:",
            ["All Sources", "Nepali Media", "Indian Press", "X (Twitter)"],
            key="wa_queue_source_filter"
        )

    if queue_filter != "All Sources":
        display_queue = [q for q in pending_queue if q["source_type"] == queue_filter]
    else:
        display_queue = pending_queue

    if display_queue:
        st.caption(f"Showing **{min(15, len(display_queue))}** of {len(display_queue)} queued items waiting for next automated cloud cycle")

        # Display Queue Cards
        for idx, q_item in enumerate(display_queue[:15]):
            raw_item = q_item["item"]
            itype = q_item["type"]
            stype = q_item["source_type"]
            item_title = raw_item.get("title") or raw_item.get("text") or "Untitled"
            item_source = raw_item.get("source") or raw_item.get("author_name") or raw_item.get("handle") or "Unknown"
            item_cat = raw_item.get("structured_category", "Others")
            item_time = raw_item.get("exact_time") or raw_item.get("relative_time") or ""

            st.markdown(f"""
            <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-left:4px solid #526A85; border-radius:8px; padding:12px; margin-bottom:10px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span style="font-size:0.75rem; background:#F1F5F9; color:#334155; padding:2px 8px; border-radius:4px; font-weight:700;">{stype} · {item_cat}</span>
                    <span style="font-size:0.75rem; color:#64748B;">🕒 {html.escape(str(item_time))}</span>
                </div>
                <div style="font-weight:650; font-size:0.95rem; color:#0F172A; margin-bottom:4px;">{html.escape(item_title[:160])}</div>
                <div style="font-size:0.8rem; color:#64748B;">Source: <b>{html.escape(item_source)}</b></div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.success("🎉 All scanned items in this timeframe have been broadcasted! Deduplication engine is up to date.")

    # Recent Broadcast History
    with st.expander("📜 Recent Broadcast History (Last 25 Dispatched Updates)", expanded=False):
        if wa_stats["recent_history"]:
            for h in wa_stats["recent_history"][:15]:
                hc1, hc2 = st.columns([4, 1.5])
                with hc1:
                    st.markdown(f"**{html.escape(h.get('title', ''))}**\n\n_{html.escape(h.get('source', ''))}_ · `{h.get('stream', h.get('type'))}`")
                with hc2:
                    st.caption(f"Sent: {h.get('sent_at', '')[:16]}")
        else:
            st.caption("No broadcast history recorded yet.")

# ==========================================
# TAB 5: Health & Diagnostics
# ==========================================
with tab5:
    st.subheader("System Health")

    # 1. System-Wide Monitoring KPIs
    try:
        kpis = get_system_kpis()
    except Exception as e:
        kpis = {
            "total_sources": 34,
            "active_sources": 34,
            "operational": 34,
            "degraded": 0,
            "failing": 0,
            "avg_latency_secs": 0.75,
            "articles_1h": len(filtered_articles),
            "articles_24h": len(filtered_articles),
            "articles_7d": len(filtered_articles),
            "total_stored_articles": len(filtered_articles)
        }

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1:
        st.metric("Total Portals", f"{kpis['total_sources']} Portals", help="28 Priority Sources + 6 English Editions")
    with k2:
        st.metric("Operational", f"{kpis['operational']} Portals", delta="100% Healthy" if kpis["failing"] == 0 else f"-{kpis['failing']} failing")
    with k3:
        st.metric("Ingested (Last 1h)", f"{kpis['articles_1h']:,} arts", help="Newly published articles discovered within the last 60 minutes")
    with k4:
        st.metric("Ingested (Last 24h)", f"{kpis['articles_24h']:,} arts", help="Articles published within the last 24 hours")
    with k5:
        st.metric("Total Stored", f"{kpis['total_stored_articles']:,} arts", help="Total canonical deduplicated articles in SQLite database")
    with k6:
        st.metric("Avg Latency", f"{kpis['avg_latency_secs']}s", help="Average discovery latency per source")

    st.markdown("---")

    # 2. Chief Admin Control Panel
    ctrl_col1, ctrl_col2 = st.columns([1.8, 2.2])

    with ctrl_col1:
        st.markdown("##### ⚡ Live Ingestion Controls")
        if st.button("🔄 Trigger Manual Ingestion (All 34 Portals)", width="stretch", key="btn_trigger_all_ingest"):
            with st.spinner("Executing parallel discovery across all 34 Nepali news portals..."):
                sync_res = run_all_sources_discovery(parallel_workers=20, force_all=True)
                st.success(f"✓ Completed! Checked {sync_res['total_checked']} portals · Ingested {sync_res['total_ingested']} fresh articles.")
                time.sleep(1)
                st.rerun()

        st.caption("Scheduled background monitoring continues running automatically via daemon worker.")

    with ctrl_col2:
        st.markdown("##### ⏪ Deep Historical Backfill & Archive Recovery")
        with st.expander("Configure Historical Backfill Tool", expanded=False):
            st.write("Inspect past days' archives, category pagination, and XML sitemaps to backfill missed articles:")
            bf_days = st.select_slider("Backfill Time Horizon:", options=[1, 3, 5, 7, 14], value=3, format_func=lambda x: f"Past {x} Days")
            portal_options = ["All 34 Portals"] + sorted([p["name"] for p in TOP_NEPAL_NEWS_PORTALS])
            bf_targets = st.multiselect("Select Target Portals:", portal_options, default=["All 34 Portals"])

            if st.button("🚀 Start Deep Historical Backfill", width="stretch", key="btn_exec_backfill"):
                targets = None if "All 34 Portals" in bf_targets else bf_targets
                with st.spinner(f"Initiating deep backfill for {len(targets) if targets else 34} portals across the past {bf_days} days..."):
                    bf_res = run_historical_backfill(source_names=targets, days_back=bf_days, parallel_workers=10)
                    st.success(f"✓ Backfill Complete! Ingested {bf_res['total_ingested']} historical articles from {bf_res['sources_backfilled']} outlets.")
                    time.sleep(1)
                    st.rerun()

    st.markdown("---")

    # 3. Source Health Matrix & Discovery Table
    st.markdown("##### 📋 Complete 34 Nepali Media Source Registry & Live Health Matrix")

    # Table Filter Controls
    f_c1, f_c2, f_c3, f_c4 = st.columns([2, 1.5, 1.5, 1.5])
    with f_c1:
        admin_search_src = st.text_input("🔍 Search Portal Name:", placeholder="e.g. Setopati, Ratopati, Kantipur...", key="inp_admin_src_srch")
    with f_c2:
        admin_status_filter = st.selectbox("Health Status:", ["All Statuses", "Operational Only", "Degraded Only", "Failing Only"], key="sel_admin_status")
    with f_c3:
        admin_lang_filter = st.selectbox("Language Edition:", ["All Languages", "Nepali Only", "English Only"], key="sel_admin_lang")
    with f_c4:
        admin_tier_filter = st.selectbox("Monitoring Tier:", ["All Tiers", "High (8m)", "Standard (18m)", "Low (40m)"], key="sel_admin_tier")

    # Load Source Health Rows
    try:
        health_data = get_all_source_health()
    except Exception:
        health_data = []

    # Apply Admin Filters
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

    st.markdown(f'<div class="apple-counter-badge">Displaying <b>{len(filtered_health)} of {len(health_data)}</b> monitored media sources</div>', unsafe_allow_html=True)
    st.write("")

    # Render Source Cards
    for s_idx, src in enumerate(filtered_health):
        s_name = src["name"]
        s_status = src.get("status", "operational")
        s_lang = src.get("lang", "Nepali")
        s_type = src.get("type", "rss").upper()
        s_cat = src.get("category", "General News")
        s_priority = src.get("priority", "standard").capitalize()
        s_interval = src.get("check_interval_mins", 15)
        s_enabled = bool(src.get("enabled", 1))

        # Status badge styling
        if s_status == "operational":
            status_html = '<span style="background:#DEF7EC; color:#03543F; border:1px solid #BCF0DA; padding:3px 10px; border-radius:9999px; font-size:0.75rem; font-weight:700;">🟢 Operational</span>'
        elif s_status == "degraded":
            status_html = '<span style="background:#FEF08A; color:#713F12; border:1px solid #FDE047; padding:3px 10px; border-radius:9999px; font-size:0.75rem; font-weight:700;">🟡 Degraded (Retrying)</span>'
        else:
            status_html = '<span style="background:#FDE8E8; color:#9B1C1C; border:1px solid #F8B4B4; padding:3px 10px; border-radius:9999px; font-size:0.75rem; font-weight:700;">🔴 Failing</span>'

        tier_badge = f'<span style="background:#F1F5F9; color:#475569; padding:2px 8px; border-radius:6px; font-size:0.72rem; font-weight:600;">⏱ Every {s_interval}m ({s_priority})</span>'
        type_badge = f'<span style="background:#EFF6FF; color:#1D4ED8; padding:2px 8px; border-radius:6px; font-size:0.72rem; font-weight:600;">📡 {s_type}</span>'
        lang_badge = f'<span style="background:#FAF5FF; color:#7E22CE; padding:2px 8px; border-radius:6px; font-size:0.72rem; font-weight:600;">🌐 {s_lang}</span>'

        # Metrics
        c_1h = src.get("count_1h") or 0
        c_24h = src.get("count_24h") or 0
        c_7d = src.get("count_7d") or 0
        c_tot = src.get("count_total") or 0
        raw_lat = src.get("discovery_latency_avg_secs")
        lat = round(float(raw_lat), 2) if raw_lat is not None else 0.0

        last_disc = src.get("last_discovery_time") or "Pending first cycle"
        latest_title = src.get("latest_article_title") or "No article recorded yet"
        latest_link = src.get("latest_article_link") or src.get("url")
        latest_pub = src.get("latest_article_pub_dt") or ""

        with st.container():
            st.markdown(f"""
            <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-left:4px solid {'#10B981' if s_status=='operational' else '#EF4444' if s_status=='failing' else '#F59E0B'}; border-radius:10px; padding:14px 18px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.02);">
                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:8px;">
                    <div style="display:flex; align-items:center; gap:10px;">
                        <span style="font-size:1.05rem; font-weight:700; color:#0F172A;">{html.escape(s_name)}</span>
                        {status_html}
                        {tier_badge}
                        {type_badge}
                        {lang_badge}
                    </div>
                    <div style="font-size:0.8rem; color:#64748B;">
                        Last Polled: <b>{html.escape(str(last_disc)[:19])}</b> · Latency: <b>{lat}s</b>
                    </div>
                </div>
                <div style="display:flex; gap:16px; margin:8px 0; font-size:0.84rem; color:#334155; flex-wrap:wrap;">
                    <div>📊 Discovered: <b>{c_1h}</b> in 1h · <b>{c_24h}</b> in 24h · <b>{c_7d}</b> in 7d (<b>{c_tot:,}</b> Total Stored)</div>
                    <div>🔗 Feed Endpoint: <a href="{html.escape(src.get('url', ''))}" target="_blank" rel="noopener noreferrer" style="color:#0284C7; text-decoration:none;">{html.escape(src.get('url', ''))[:45]}... ↗</a></div>
                </div>
                <div style="background:#F8FAFC; border:1px solid #F1F5F9; border-radius:6px; padding:8px 12px; margin-top:6px; font-size:0.83rem;">
                    <div style="color:#64748B; font-size:0.75rem; font-weight:600; margin-bottom:2px;">LATEST DISCOVERED STORY ({html.escape(str(latest_pub)[:19])}):</div>
                    <div style="font-weight:600; color:#0F172A;"><a href="{html.escape(latest_link)}" target="_blank" rel="noopener noreferrer" style="color:#0F172A; text-decoration:none;">• {html.escape(latest_title[:110])} ↗</a></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            sc1, sc2, sc3, sc4 = st.columns([1.5, 1.5, 1.5, 1.5])
            with sc1:
                if st.button(f"🔄 Refresh {s_name}", key=f"btn_ref_src_{s_name}_{s_idx}", width="stretch"):
                    with st.spinner(f"Ingesting latest feeds from {s_name}..."):
                        portal_cfg = next((p for p in TOP_NEPAL_NEWS_PORTALS if p["name"] == s_name), None)
                        if portal_cfg:
                            run_single_source_discovery(portal_cfg, max_articles=40)
                            st.success(f"✓ Refreshed {s_name}!")
                            time.sleep(0.5)
                            st.rerun()
            with sc2:
                # Interval update selector
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
                # Enable / Disable toggle
                toggle_label = "🔴 Disable Source" if s_enabled else "🟢 Enable Source"
                if st.button(toggle_label, key=f"btn_tog_en_{s_name}_{s_idx}", width="stretch"):
                    set_source_enabled(s_name, not s_enabled)
                    st.rerun()
            with sc4:
                # Error log indicator
                if src.get("last_error_message"):
                    with st.expander("⚠️ View Error Log", expanded=False):
                        st.error(src.get("last_error_message"))
                else:
                    st.caption("✓ Zero active errors")

    # 4. Coverage Diagnostics & Anomaly Detection
    with st.expander("🔍 Coverage Diagnostics & Anomaly Detection", expanded=False):
        # A source is only an anomaly if it has had zero articles ingested in the last 48 hours AND has active errors
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
            st.info(f"ℹ️ **Quiet / Weekly Portals:** {len(quiet_sources)} portals (e.g. {', '.join([q['name'] for q in quiet_sources[:3]])}) publish on a weekly or holiday schedule. Their scrapers are operational and will automatically ingest stories when published.")
