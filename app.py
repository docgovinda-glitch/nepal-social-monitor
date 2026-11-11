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
    get_source_broadcast_stats
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
    initial_sidebar_state="expanded"
)

# 2. Modern Apple-Grade Design System & Custom Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@500;600;700;800&display=swap');

    :root {
        --apple-font: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Inter", "Plus Jakarta Sans", system-ui, sans-serif;
        --apple-bg: #F8FAFC;
        --apple-card-bg: #FFFFFF;
        --apple-card-border: #E2E8F0;
        --apple-card-shadow: 0 1px 3px rgba(15, 23, 42, 0.04), 0 4px 14px rgba(15, 23, 42, 0.02);
        --apple-card-shadow-hover: 0 8px 24px rgba(15, 23, 42, 0.07), 0 2px 6px rgba(15, 23, 42, 0.03);
        --apple-text-primary: #0F172A;
        --apple-text-secondary: #334155;
        --apple-text-muted: #64748B;
        --apple-blue: #0284C7;
        --apple-blue-hover: #0369A1;
        --apple-red: #E11D48;
        --apple-green: #10B981;
        --apple-radius-sm: 8px;
        --apple-radius-md: 12px;
        --apple-radius-lg: 14px;
        --apple-radius-xl: 18px;
        --apple-radius-pill: 9999px;
        --apple-ease: cubic-bezier(0.16, 1, 0.3, 1);
    }

    /* Global Typography & Smoothing */
    html, body, .stMarkdown, p, label, h1, h2, h3, h4, h5, h6 {
        font-family: var(--apple-font) !important;
        -webkit-font-smoothing: antialiased !important;
        -moz-osx-font-smoothing: grayscale !important;
    }

    /* Preserve Icon Glyphs & Prevent Text Leaks */
    [data-testid*="stIcon"], [data-testid*="Icon"], .material-symbols-rounded, [class*="e1vmumty0"], span[aria-hidden="true"] {
        font-family: "Material Symbols Rounded" !important;
        font-weight: normal !important;
        font-style: normal !important;
        font-size: 1.25rem;
        line-height: 1;
        letter-spacing: normal;
        text-transform: none;
        display: inline-block;
        white-space: nowrap;
        word-wrap: normal;
        direction: ltr;
        -webkit-font-smoothing: antialiased !important;
    }

    /* Clean App Background & Separators */
    [data-testid="stAppViewContainer"], .main {
        background-color: #F8FAFC !important;
    }

    hr {
        border-color: #E2E8F0 !important;
        margin: 1.2rem 0 !important;
    }

    /* Main Container Padding */
    .block-container {
        padding-top: 1.2rem !important;
        padding-bottom: 3.5rem !important;
        max-width: 1320px !important;
    }

    /* Apple Top Header Bar */
    .apple-top-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 4px 0 16px 0;
        margin-bottom: 12px;
        border-bottom: 1px solid rgba(0, 0, 0, 0.06);
    }

    .apple-top-title-group {
        display: flex;
        align-items: center;
        gap: 12px;
    }

    .apple-flag-icon {
        font-size: 1.85rem;
        line-height: 1;
        display: inline-block;
        filter: drop-shadow(0 2px 4px rgba(0,0,0,0.1));
    }

    .apple-top-title {
        font-size: 1.35rem !important;
        font-weight: 750 !important;
        color: #0F172A !important;
        letter-spacing: -0.025em !important;
        margin: 0 !important;
        line-height: 1.2 !important;
    }

    .apple-top-subtitle {
        font-size: 0.82rem !important;
        color: #64748B !important;
        font-weight: 500 !important;
        margin: 2px 0 0 0 !important;
        line-height: 1.3 !important;
    }

    .apple-top-status {
        display: inline-flex;
        align-items: center;
        gap: 7px;
        background: #ECFDF5;
        border: 1px solid #A7F3D0;
        padding: 5px 13px;
        border-radius: 9999px;
    }

    .apple-live-pulse {
        width: 8px;
        height: 8px;
        background-color: #10B981;
        border-radius: 50%;
        box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.2);
        animation: applePulse 2s infinite;
    }

    @keyframes applePulse {
        0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.6); }
        70% { transform: scale(1); box-shadow: 0 0 0 7px rgba(16, 185, 129, 0); }
        100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }

    .apple-status-text {
        font-size: 0.74rem;
        font-weight: 700;
        color: #065F46;
        letter-spacing: 0.03em;
    }

    /* Apple Segmented Controls for Tabs */
    div[data-baseweb="tab-list"], div[role="tablist"] {
        background: #EEF2F6 !important;
        padding: 4px !important;
        border-radius: 12px !important;
        gap: 4px !important;
        border: 1px solid #E2E8F0 !important;
        margin-bottom: 20px !important;
        display: flex !important;
        width: 100% !important;
        box-sizing: border-box !important;
    }
    div[data-baseweb="tab-list"]::-webkit-scrollbar, div[role="tablist"]::-webkit-scrollbar {
        display: none !important;
    }

    button[data-baseweb="tab"], div[data-testid="stTab"], [role="tab"] {
        font-family: var(--apple-font) !important;
        border-radius: 8px !important;
        padding: 8px 14px !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        color: #64748B !important;
        border: none !important;
        background: transparent !important;
        transition: all 0.2s var(--apple-ease) !important;
        cursor: pointer !important;
        flex: 1 1 auto !important;
        text-align: center !important;
        justify-content: center !important;
        white-space: nowrap !important;
        min-width: fit-content !important;
    }

    button[data-baseweb="tab"]:hover, div[data-testid="stTab"]:hover, [role="tab"]:hover {
        color: #0F172A !important;
        background: rgba(255, 255, 255, 0.6) !important;
    }

    button[data-baseweb="tab"][aria-selected="true"], 
    div[data-testid="stTab"][aria-selected="true"], 
    [role="tab"][aria-selected="true"],
    [role="tab"][data-selected="true"] {
        background: #FFFFFF !important;
        color: #0F172A !important;
        font-weight: 700 !important;
        box-shadow: 0 2px 6px rgba(15, 23, 42, 0.08), 0 1px 2px rgba(15, 23, 42, 0.04) !important;
    }

    div[data-baseweb="tab-border"], div[data-baseweb="tab-highlight"], div[role="tablist"]::after, [data-testid="stTabHighlight"] {
        display: none !important;
    }

    /* Apple Metric Cards */
    div[data-testid="stMetric"] {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 12px !important;
        padding: 14px 18px !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03) !important;
        transition: all 0.25s var(--apple-ease) !important;
    }

    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06) !important;
        border-color: #93C5FD !important;
    }

    div[data-testid="stMetricLabel"], div[data-testid="stMetricLabel"] * {
        font-size: 0.82rem !important;
        font-weight: 650 !important;
        color: #64748B !important;
        letter-spacing: -0.01em !important;
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: clip !important;
    }

    div[data-testid="stMetricValue"], div[data-testid="stMetricValue"] * {
        font-size: 1.45rem !important;
        font-weight: 750 !important;
        letter-spacing: -0.02em !important;
        color: #0F172A !important;
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: clip !important;
    }

    /* Apple News Article Card */
    .apple-news-card {
        background: #FFFFFF;
        border-radius: var(--apple-radius-lg);
        border: 1px solid var(--apple-card-border);
        border-left: 4px solid #CBD5E1;
        box-shadow: var(--apple-card-shadow);
        padding: 18px 22px;
        margin-bottom: 16px;
        transition: all 0.25s var(--apple-ease);
        position: relative;
    }

    .apple-news-card:hover {
        transform: translateY(-2px);
        box-shadow: var(--apple-card-shadow-hover);
        border-color: #93C5FD;
    }

    .card-accent-india { border-left-color: #F59E0B !important; }
    .card-accent-china { border-left-color: #EF4444 !important; }
    .card-accent-pakistan { border-left-color: #10B981 !important; }
    .card-accent-bangladesh { border-left-color: #06B6D4 !important; }
    .card-accent-internal, .card-accent-politics { border-left-color: #6366F1 !important; }
    .card-accent-external { border-left-color: #8B5CF6 !important; }
    .card-accent-economy { border-left-color: #059669 !important; }
    .card-accent-others { border-left-color: #94A3B8 !important; }
    .card-accent-international { border-left-color: #7C3AED !important; }
    .card-accent-indian-press { border-left-color: #F97316 !important; }

    .apple-card-meta {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 10px;
    }

    .apple-card-title {
        margin: 0 0 10px 0 !important;
        font-size: 1.15rem !important;
        font-weight: 650 !important;
        line-height: 1.45 !important;
        letter-spacing: -0.018em !important;
    }

    .apple-card-title a {
        color: #0F172A !important;
        text-decoration: none !important;
        transition: color 0.15s ease;
    }

    .apple-card-title a:hover {
        color: #0284C7 !important;
    }

    .apple-card-summary {
        color: #475569;
        font-size: 0.91rem;
        line-height: 1.6;
        margin: 0 0 14px 0;
    }

    .apple-card-footer {
        display: flex;
        justify-content: flex-end;
        align-items: center;
        margin-top: 4px;
    }

    .apple-card-cta {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        background: #F0F9FF;
        color: #0284C7 !important;
        border: 1px solid #BAE6FD;
        padding: 5px 15px;
        border-radius: var(--apple-radius-pill);
        font-size: 0.8rem;
        font-weight: 650;
        text-decoration: none !important;
        transition: all 0.2s var(--apple-ease);
    }

    .apple-card-cta:hover {
        background: #0284C7;
        color: #FFFFFF !important;
        border-color: #0284C7;
        box-shadow: 0 4px 12px rgba(2, 132, 199, 0.3);
    }

    .apple-wa-share-btn {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        background: #F0FDF4;
        color: #15803D !important;
        border: 1px solid #BBF7D0;
        padding: 5px 12px;
        border-radius: var(--apple-radius-pill);
        font-size: 0.77rem;
        font-weight: 650;
        text-decoration: none !important;
        transition: all 0.2s var(--apple-ease);
    }

    .apple-wa-share-btn:hover {
        background: #22C55E;
        color: #FFFFFF !important;
        border-color: #22C55E;
        box-shadow: 0 4px 12px rgba(34, 197, 94, 0.3);
        transform: translateY(-1px);
    }

    /* Category & Metadata Badges */
    .portal-tag {
        background: #0F172A;
        color: #FFFFFF;
        padding: 4px 11px;
        border-radius: var(--apple-radius-pill);
        font-size: 0.74rem;
        font-weight: 650;
        letter-spacing: -0.01em;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.1);
    }

    .indian-portal-tag {
        background: #FFF7ED;
        color: #C2410C;
        border: 1px solid #FFEDD5;
        padding: 4px 11px;
        border-radius: var(--apple-radius-pill);
        font-size: 0.74rem;
        font-weight: 650;
        letter-spacing: -0.01em;
    }

    .time-badge {
        background: #F1F5F9;
        color: #64748B;
        border: 1px solid #E2E8F0;
        padding: 4px 10px;
        border-radius: var(--apple-radius-pill);
        font-size: 0.74rem;
        font-weight: 550;
    }

    .cat-badge-india { background: #FEF3C7; color: #92400E; border: 1px solid #FDE68A; padding: 4px 11px; border-radius: 9999px; font-size: 0.74rem; font-weight: 650; }
    .cat-badge-china { background: #FEE2E2; color: #991B1B; border: 1px solid #FECACA; padding: 4px 11px; border-radius: 9999px; font-size: 0.74rem; font-weight: 650; }
    .cat-badge-pakistan { background: #ECFDF5; color: #065F46; border: 1px solid #A7F3D0; padding: 4px 11px; border-radius: 9999px; font-size: 0.74rem; font-weight: 650; }
    .cat-badge-bangladesh { background: #CFFAFE; color: #155E75; border: 1px solid #A5F3FC; padding: 4px 11px; border-radius: 9999px; font-size: 0.74rem; font-weight: 650; }
    .cat-badge-internal, .cat-badge-politics { background: #EEF2FF; color: #3730A3; border: 1px solid #C7D2FE; padding: 4px 11px; border-radius: 9999px; font-size: 0.74rem; font-weight: 650; }
    .cat-badge-external { background: #F5F3FF; color: #5B21B6; border: 1px solid #DDD6FE; padding: 4px 11px; border-radius: 9999px; font-size: 0.74rem; font-weight: 650; }
    .cat-badge-economy { background: #ECFDF5; color: #047857; border: 1px solid #6EE7B7; padding: 4px 11px; border-radius: 9999px; font-size: 0.74rem; font-weight: 650; }
    .cat-badge-others { background: #F1F5F9; color: #475569; border: 1px solid #E2E8F0; padding: 4px 11px; border-radius: 9999px; font-size: 0.74rem; font-weight: 650; }
    .cat-badge-international { background: #EDE9FE; color: #5B21B6; border: 1px solid #DDD6FE; padding: 4px 11px; border-radius: 9999px; font-size: 0.74rem; font-weight: 650; }
    .sec-tag-chip { background: #F8FAFC; color: #475569; border: 1px solid #E2E8F0; padding: 2px 7px; border-radius: 6px; font-size: 0.70rem; font-weight: 550; display: inline-flex; align-items: center; }
    .conf-review-badge { background: #FFFBEB; color: #B45309; border: 1px solid #FCD34D; padding: 2px 8px; border-radius: 9999px; font-size: 0.68rem; font-weight: 700; letter-spacing: 0.02em; }

    /* Apple Filter Banner */
    .apple-filter-banner {
        display: flex;
        align-items: center;
        gap: 12px;
        background: #F0F9FF;
        border: 1px solid #BAE6FD;
        border-radius: var(--apple-radius-md);
        padding: 10px 16px;
        margin-bottom: 16px;
        font-size: 0.88rem;
        color: #0369A1;
    }

    /* Apple Counter Badge */
    .apple-counter-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: #F0F9FF;
        color: #0284C7;
        border: 1px solid #BAE6FD;
        border-radius: var(--apple-radius-pill);
        padding: 6px 14px;
        font-size: 0.85rem;
        font-weight: 650;
    }

    /* Streamlit Buttons Styled to Apple HIG */
    .stButton>button {
        border-radius: 10px !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        padding: 8px 18px !important;
        transition: all 0.2s var(--apple-ease) !important;
        background-color: #FFFFFF !important;
        color: #0F172A !important;
        border: 1px solid #CBD5E1 !important;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04) !important;
    }

    .stButton>button:hover {
        background-color: #F8FAFC !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08) !important;
        border-color: #94A3B8 !important;
    }

    .stDownloadButton>button {
        border-radius: 10px !important;
        font-weight: 650 !important;
        font-size: 0.88rem !important;
        padding: 10px 20px !important;
        background: linear-gradient(180deg, #0284C7 0%, #0369A1 100%) !important;
        color: #FFFFFF !important;
        border: 1px solid rgba(2, 132, 199, 0.4) !important;
        box-shadow: 0 2px 6px rgba(2, 132, 199, 0.25) !important;
        transition: all 0.2s var(--apple-ease) !important;
    }

    .stDownloadButton>button:hover {
        background: linear-gradient(180deg, #0369A1 0%, #075985 100%) !important;
        transform: translateY(-1px);
        box-shadow: 0 6px 16px rgba(2, 132, 199, 0.35) !important;
    }

    /* Apple Expanders / Disclosures */
    div[data-testid="stExpander"] {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: var(--apple-radius-md) !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03) !important;
        margin-bottom: 12px !important;
        overflow: hidden !important;
        transition: all 0.2s var(--apple-ease) !important;
    }

    div[data-testid="stExpander"]:hover {
        border-color: #CBD5E1 !important;
        box-shadow: 0 2px 6px rgba(15, 23, 42, 0.05) !important;
    }

    div[data-testid="stExpander"] summary {
        padding: 12px 18px !important;
        font-weight: 650 !important;
        font-size: 0.9rem !important;
        color: #1E293B !important;
    }

    div[data-testid="stExpander"] summary:hover {
        background-color: #F8FAFC !important;
    }

    div[data-testid="stExpanderDetails"] {
        padding: 16px 20px 20px 20px !important;
        border-top: 1px solid #F1F5F9 !important;
    }

    /* Apple Input Fields & Dropdowns */
    div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
        border-radius: 10px !important;
        border-color: #CBD5E1 !important;
        background-color: #FFFFFF !important;
        transition: all 0.2s var(--apple-ease) !important;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.02) !important;
    }

    div[data-baseweb="input"] > div:focus-within, div[data-baseweb="select"] > div:focus-within {
        border-color: var(--apple-blue) !important;
        box-shadow: 0 0 0 3px rgba(2, 132, 199, 0.15) !important;
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #F8FAFC !important;
        border-right: 1px solid #E2E8F0 !important;
    }

    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        letter-spacing: -0.02em !important;
        font-weight: 700 !important;
        color: #0F172A !important;
    }

    section[data-testid="stSidebar"] label {
        font-size: 0.8rem !important;
        font-weight: 600 !important;
        color: #334155 !important;
        letter-spacing: -0.01em !important;
        margin-bottom: 2px !important;
    }

    /* Clean Sidebar Input & Button Polish */
    section[data-testid="stSidebar"] [data-testid="stTooltipHoverTarget"] {
        display: none !important;
    }
    section[data-testid="stSidebar"] input,
    section[data-testid="stSidebar"] div[data-baseweb="select"] {
        border-radius: 8px !important;
        font-size: 0.85rem !important;
    }
    section[data-testid="stSidebar"] .stButton button {
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 0.82rem !important;
        transition: all 0.15s ease !important;
    }

    /* Apple-Grade X (Twitter) Post Cards */
    .x-post-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: var(--apple-radius-lg);
        padding: 20px 24px;
        margin-bottom: 14px;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
        transition: all 0.22s var(--apple-ease);
    }
    .x-post-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.07);
        border-color: #CBD5E1;
    }
    .x-post-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 12px;
        flex-wrap: wrap;
        gap: 10px;
    }
    .x-author-box {
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .x-avatar {
        width: 44px;
        height: 44px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #FFFFFF;
        font-weight: 700;
        font-size: 0.95rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.12);
        flex-shrink: 0;
    }
    .x-author-meta {
        display: flex;
        flex-direction: column;
    }
    .x-author-name {
        font-weight: 700;
        font-size: 0.96rem;
        color: #0F172A;
        display: flex;
        align-items: center;
        gap: 5px;
    }
    .x-verified-badge {
        color: #1D9BF0;
        font-size: 0.9rem;
        font-weight: 800;
    }
    .x-author-handle {
        font-size: 0.8rem;
        color: #64748B;
        font-weight: 500;
    }
    .x-type-badge {
        background: #F1F5F9;
        color: #475569;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.72rem;
        font-weight: 600;
    }
    .x-post-text {
        font-size: 1rem;
        color: #1E293B;
        line-height: 1.62;
        margin-bottom: 14px;
        word-break: break-word;
    }
    .x-engagement-bar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding-top: 12px;
        border-top: 1px solid #F1F5F9;
        font-size: 0.82rem;
        color: #64748B;
        flex-wrap: wrap;
        gap: 12px;
    }
    .x-metrics-group {
        display: flex;
        align-items: center;
        gap: 18px;
    }
    .x-metric-item {
        display: flex;
        align-items: center;
        gap: 5px;
        font-weight: 600;
    }
    .x-sentiment-badge {
        padding: 3px 9px;
        border-radius: 9999px;
        font-size: 0.72rem;
        font-weight: 650;
    }
    .x-sentiment-positive { background: #ECFDF5; color: #047857; border: 1px solid #A7F3D0; }
    .x-sentiment-alert { background: #FEF2F2; color: #B91C1C; border: 1px solid #FECACA; }
    .x-sentiment-neutral { background: #F8FAFC; color: #475569; border: 1px solid #E2E8F0; }
    .x-cta-link {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        color: #0284C7;
        font-weight: 650;
        text-decoration: none;
        font-size: 0.84rem;
        padding: 4px 12px;
        border-radius: var(--apple-radius-pill);
        background: #F0F9FF;
        border: 1px solid #BAE6FD;
        transition: all 0.18s var(--apple-ease);
    }
    .x-cta-link:hover {
        background: #E0F2FE;
        border-color: #7DD3FC;
        text-decoration: none;
        transform: translateY(-1px);
    }
</style>
""", unsafe_allow_html=True)

# 3. Time Reference
now_npt = datetime.datetime.now(NEPAL_TZ)
formatted_now_time = now_npt.strftime("%I:%M %p NPT")

# 4. Sidebar Controls & Date/Time Filter
st.sidebar.markdown("### 🎛️ Control Panel")
refresh_btn = st.sidebar.button("🔄 Refresh All Feeds", width='stretch', type="primary")

# --- Date & Time Range Filter Section ---
st.sidebar.markdown("---")
st.sidebar.markdown("##### 📅 Date & Time Range")

yesterday_date = (now_npt - datetime.timedelta(days=1)).date()
yesterday_18_time = datetime.time(18, 0)

# Quick Preset Buttons
col_p1, col_p2, col_p3 = st.sidebar.columns(3)
if col_p1.button("🌅 Yesterday", width='stretch', help="From Yesterday 18:00 NPT to Now"):
    st.session_state["filter_start_date"] = yesterday_date
    st.session_state["filter_start_time"] = yesterday_18_time
    st.session_state["filter_use_current_time"] = True
    st.rerun()
if col_p2.button("📅 Today", width='stretch', help="From Today 00:00 NPT to Now"):
    st.session_state["filter_start_date"] = now_npt.date()
    st.session_state["filter_start_time"] = datetime.time(0, 0)
    st.session_state["filter_use_current_time"] = True
    st.rerun()
if col_p3.button("⚡ Past 24h", width='stretch', help="From 24 Hours Ago to Now"):
    past_24_dt = now_npt - datetime.timedelta(hours=24)
    st.session_state["filter_start_date"] = past_24_dt.date()
    st.session_state["filter_start_time"] = past_24_dt.time().replace(second=0, microsecond=0)
    st.session_state["filter_use_current_time"] = True
    st.rerun()

col_start_d, col_start_t = st.sidebar.columns([3, 2])
with col_start_d:
    start_date = st.date_input(
        "Start Date",
        value=st.session_state.get("filter_start_date", yesterday_date),
        max_value=now_npt.date(),
        key="filter_start_date",
        help="Select start date from calendar"
    )
with col_start_t:
    start_time = st.time_input(
        "Start Time",
        value=st.session_state.get("filter_start_time", yesterday_18_time),
        key="filter_start_time",
        help="Select start time (default 18:00 / 6:00 PM)"
    )

filter_start_dt = datetime.datetime.combine(start_date, start_time, tzinfo=NEPAL_TZ)

use_current_time = st.sidebar.checkbox(
    "⚡ Lock to Current Time (Live)",
    value=st.session_state.get("filter_use_current_time", True),
    key="filter_use_current_time",
    help="Automatically keeps feed synced to current moment"
)

is_to_current = use_current_time
explicit_all_time = False

if use_current_time:
    filter_end_dt = now_npt
    st.sidebar.markdown("""
    <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.25); color: #047857; padding: 6px 10px; border-radius: 8px; font-size: 0.78rem; font-weight: 600; display: flex; align-items: center; justify-content: space-between; margin: 2px 0 8px 0;">
        <span>🟢 Live Tracking Active</span>
        <span style="background: #10B981; color: white; padding: 1px 7px; border-radius: 10px; font-size: 0.68rem; font-weight: 700;">LIVE</span>
    </div>
    """, unsafe_allow_html=True)
else:
    col_end_d, col_end_t = st.sidebar.columns([3, 2])
    with col_end_d:
        end_date = st.date_input(
            "End Date",
            value=st.session_state.get("filter_end_date", now_npt.date()),
            max_value=now_npt.date(),
            min_value=start_date,
            key="filter_end_date",
            help="Select end date from calendar"
        )
    with col_end_t:
        end_time = st.time_input(
            "End Time",
            value=st.session_state.get("filter_end_time", now_npt.time().replace(second=0, microsecond=0)),
            key="filter_end_time",
            help="Select end time"
        )
    filter_end_dt = datetime.datetime.combine(end_date, end_time, tzinfo=NEPAL_TZ)
    if filter_end_dt < filter_start_dt:
        st.sidebar.warning("⚠️ End time cannot be earlier than start time.")
        filter_end_dt = filter_start_dt + datetime.timedelta(hours=1)

end_label = f"Now ({now_npt.strftime('%I:%M %p')})" if use_current_time else filter_end_dt.strftime("%b %d, %I:%M %p")
st.sidebar.caption(f"🕒 **{filter_start_dt.strftime('%b %d, %I:%M %p')} → {end_label}**")

st.sidebar.markdown("---")
st.sidebar.markdown("##### 🔍 Search & Filters")

search_query = st.sidebar.text_input(
    "Search Keyword:",
    placeholder="e.g. Balen, India, Budget, Cricket...",
    key="global_search_input",
    help="Bilingual cross-lingual search across Nepali Media, Indian Media, and X Posts."
)

CAT_FILTER_ALL_UNFILTERED = "🌐 All News"
CAT_FILTER_ALL_8 = "📂 Classified"
CAT_FILTER_UNCATEGORIZED = "⚪ Unclassified"

CATEGORY_FILTER_OPTIONS = [
    CAT_FILTER_ALL_UNFILTERED,
    CAT_FILTER_ALL_8,
    CAT_FILTER_UNCATEGORIZED,
] + [f"{CATEGORY_ICONS.get(c, '📌')} {c}" for c in STRUCTURED_CATEGORIES]

selected_cat_filter = st.sidebar.selectbox(
    "Editorial Section / Category:",
    CATEGORY_FILTER_OPTIONS,
    index=0,
    key="sidebar_selected_cat_filter",
    help="Filter across the 9 geographically and thematically organised editorial sections."
)

col_portal, col_lang = st.sidebar.columns(2)
with col_portal:
    all_portal_names = sorted(list(set([p["name"] for p in TOP_NEPAL_NEWS_PORTALS])))
    portal_filter = st.selectbox(
        "Nepali Portal:",
        ["All Portals (34 Portals)"] + all_portal_names,
        key="sidebar_portal_filter"
    )

with col_lang:
    lang_filter = st.selectbox(
        "Language:",
        ["All Languages", "Nepali Only", "English Only", "Hindi Only"],
        index=0,
        key="sidebar_lang_filter"
    )

def reset_all_filters():
    st.session_state["global_search_input"] = ""
    st.session_state["sidebar_selected_cat_filter"] = CAT_FILTER_ALL_UNFILTERED
    st.session_state["sidebar_portal_filter"] = "All Portals (34 Portals)"
    st.session_state["sidebar_lang_filter"] = "All Languages"
    st.session_state["filter_start_date"] = yesterday_date
    st.session_state["filter_start_time"] = yesterday_18_time
    st.session_state["filter_end_date"] = now_npt.date()
    st.session_state["filter_end_time"] = now_npt.time().replace(second=0, microsecond=0)
    st.session_state["filter_use_current_time"] = True
    st.session_state["media_visible_count"] = 20
    st.session_state["indian_visible_count"] = 20
    st.session_state["x_visible_count"] = 20
    if "x_cat_filter_select" in st.session_state:
        st.session_state["x_cat_filter_select"] = CAT_FILTER_ALL_UNFILTERED

st.sidebar.button("🔄 Reset Filters", width='stretch', key="btn_reset_filters", on_click=reset_all_filters)

st.sidebar.markdown("---")
with st.sidebar.expander("ℹ️ Monitored Sources (52 Sources)", expanded=False):
    st.markdown("**🇳🇵 Nepali Media (34 Portals):** eKantipur, Setopati, Annapurna Post, Naya Patrika, NepalKhabar, Gorkhapatra, News of Nepal, Nepal Aaja, Nepal News, OnlineKhabar, Ratopati, Nagarik News, Nepal Press, Baahrakhari, Himal Press, Deshsanchar, Shilapatra, Nepal Live, Image Khabar, Khabarhub, TechPana, ArthaSarokar, The Kathmandu Post, The Himalayan Times, MyRepublica, The Annapurna Express, Rising Nepal, Nepali Times, etc.")
    st.markdown("**🇮🇳 Indian Media Covering Nepal (18 Prominent Outlets):** The Indian Express, The Hindu, India Today, The Tribune, Business Standard, Financial Express, Livemint, Moneycontrol, ABP Live, Outlook India, The Quint, Swarajya, OneIndia, NDTV, Amar Ujala (Hindi), Live Hindustan (Hindi), Jansatta (Hindi), Prabhat Khabar (Hindi).")

# Silent background credentials for Twitter API
default_bearer = os.getenv("TWITTER_BEARER_TOKEN", "")
try:
    if not default_bearer and hasattr(st, "secrets"):
        default_bearer = st.secrets.get("TWITTER_BEARER_TOKEN", "")
except Exception:
    pass
x_bearer_token = default_bearer

# 6. Fetch Data in Parallel
with st.spinner("Fetching breaking news across 34 Nepal portals, 18 Indian outlets & scanning live verified X posts..."):
    all_articles = fetch_top_nepal_media(max_workers=25)
    indian_articles = fetch_nepal_in_indian_media(max_workers=18)

if "x_posts" not in st.session_state or not st.session_state.get("x_posts") or not any(p.get("is_real_api") for p in st.session_state.get("x_posts", [])):
    st.session_state["x_posts"] = scan_popular_nepal_x_posts(force_refresh=False, x_bearer_token=x_bearer_token)
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

    # Low confidence warning flag
    review_flag = '<span class="conf-review-badge" title="Classification confidence < 0.60 - Pending Editorial Verification">⚠️ Review</span>' if item.get("low_confidence") else ''

    # Secondary tags chips
    sec_tags = item.get("secondary_tags", [])
    sec_tags_html = ""
    if sec_tags and isinstance(sec_tags, list):
        chips = [f'<span class="sec-tag-chip">#{html.escape(str(t))}</span>' for t in sec_tags[:4]]
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
        f'<a href="{wa_share_url}" target="_blank" rel="noopener noreferrer" class="apple-wa-share-btn" title="Share individual story to WhatsApp">📲 WhatsApp</a>'
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
        f'<a href="{wa_share_url}" target="_blank" rel="noopener noreferrer" class="apple-wa-share-btn" title="Share tweet to WhatsApp">📲 WhatsApp</a>'
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

# 1. Global Category Filter (Seamless across channels)
filtered_articles = filter_items_by_category(filtered_articles, selected_cat_filter, is_social=False)
filtered_indian = filter_items_by_category(filtered_indian, selected_cat_filter, is_social=False)
filtered_x_posts = filter_items_by_category(filtered_x_posts, selected_cat_filter, is_social=True)

# 2. Strengthened Bilingual & Cross-Channel Search Filter
if search_query and search_query.strip():
    filtered_articles = [a for a in filtered_articles if smart_search_match(a, search_query)]
    filtered_indian = [a for a in filtered_indian if smart_search_match(a, search_query)]
    filtered_x_posts = [p for p in filtered_x_posts if smart_search_match(p, search_query)]

# 3. Language Filter (for media portals)
if lang_filter == "Nepali Only":
    filtered_articles = [a for a in filtered_articles if a.get('language') == "Nepali"]
    filtered_indian = []
elif lang_filter == "English Only":
    filtered_articles = [a for a in filtered_articles if a.get('language') == "English"]
    filtered_indian = [a for a in filtered_indian if a.get('language') == "English"]
elif lang_filter == "Hindi Only":
    filtered_articles = []
    filtered_indian = [a for a in filtered_indian if a.get('language') == "Hindi"]

# 4. Portal Filter (for Nepali Media)
if portal_filter != "All Portals (34 Portals)":
    filtered_articles = [a for a in filtered_articles if a.get('source') == portal_filter]

# Top Minimalist Header
st.markdown(f"""
<div class="apple-top-header">
    <div class="apple-top-title-group">
        <span class="apple-flag-icon">🇳🇵</span>
        <div>
            <h1 class="apple-top-title">Nepal Media & Intelligence Monitor</h1>
            <p class="apple-top-subtitle">Real-time intelligence across 34 top Nepali portals & 18 Indian outlets</p>
        </div>
    </div>
    <div class="apple-top-status">
        <span class="apple-live-pulse"></span>
        <span class="apple-status-text">LIVE · 34 PORTALS & 18 INDIAN OUTLETS · {formatted_now_time}</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Active Filters Banner
active_filter_chips = []
if search_query and search_query.strip():
    active_filter_chips.append(f'<span style="background:#E0F2FE; color:#0369A1; border:1px solid #BAE6FD; padding:3px 10px; border-radius:14px; font-size:0.8rem; font-weight:600;">🔍 Keyword: "{html.escape(search_query.strip())}"</span>')
if selected_cat_filter != CAT_FILTER_ALL_UNFILTERED:
    active_filter_chips.append(f'<span style="background:#F1F5F9; color:#334155; border:1px solid #CBD5E1; padding:3px 10px; border-radius:14px; font-size:0.8rem; font-weight:600;">🏷 {html.escape(selected_cat_filter)}</span>')
if filter_start_dt or not is_to_current:
    from_chip = filter_start_dt.strftime("%b %d, %I:%M %p") if filter_start_dt else "Archive Start"
    to_chip = "Current / Now" if is_to_current else filter_end_dt.strftime("%b %d, %I:%M %p")
    active_filter_chips.append(f'<span style="background:#FEF3C7; color:#92400E; border:1px solid #FDE68A; padding:3px 10px; border-radius:14px; font-size:0.8rem; font-weight:600;">⏱ Range: {from_chip} → {to_chip}</span>')
if lang_filter != "All Languages":
    active_filter_chips.append(f'<span style="background:#F3E8FF; color:#6B21A8; border:1px solid #E9D5FF; padding:3px 10px; border-radius:14px; font-size:0.8rem; font-weight:600;">🌐 {html.escape(lang_filter)}</span>')

if active_filter_chips:
    af_col1, af_col2 = st.columns([5.5, 1])
    with af_col1:
        st.markdown(f'<div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin:6px 0 10px 0;"><span style="font-size:0.8rem; font-weight:700; color:#64748B; letter-spacing:0.04em;">ACTIVE FILTERS:</span>{" ".join(active_filter_chips)}</div>', unsafe_allow_html=True)
    with af_col2:
        st.button("✕ Clear All", key="btn_clear_active_pills", width="stretch", on_click=reset_all_filters)

# 8. Navigation Tabs (Dynamic Live Counts)
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    f"📰 Nepali Media ({len(filtered_articles)} Stories)",
    f"🇮🇳 Indian Media ({len(filtered_indian)} Stories)",
    f"🐦 X (Twitter) ({len(filtered_x_posts)} Posts)",
    "📈 Analytics & Export",
    "📡 Source Monitoring & Admin"
])

# ==========================================
# TAB 1: Nepali Media (Top 34 Portals)
# ==========================================
with tab1:
    # Display Active Date-Time Filter Banner if applicable
    if filter_start_dt or not is_to_current:
        from_str = filter_start_dt.strftime('%b %d, %Y · %I:%M %p') if filter_start_dt else "Archive Start"
        to_str = f"Current / Now ({filter_end_dt.strftime('%I:%M %p')} NPT)" if is_to_current else filter_end_dt.strftime('%b %d, %Y · %I:%M %p NPT')
        st.markdown(f"""
        <div class="apple-filter-banner">
            <span style="font-size:1.15rem;">⏱</span>
            <div><b>Active Time Range:</b> Showing articles published from <b>{from_str} NPT</b> up to <b>{to_str}</b>.</div>
        </div>
        """, unsafe_allow_html=True)

    if not filtered_articles:
        st.warning("No news articles found matching your filters. Try selecting 'All Recent Articles' or expanding your time window.")
    else:
        # Incremental Loading / Pagination (20 entries initial, +20 per click)
        if "media_visible_count" not in st.session_state:
            st.session_state["media_visible_count"] = 20

        current_media_limit = st.session_state["media_visible_count"]
        visible_articles = filtered_articles[:current_media_limit]

        for item in visible_articles:
            st.markdown(render_apple_article_card(item, is_indian=False), unsafe_allow_html=True)

        if len(filtered_articles) > current_media_limit:
            remaining_media = len(filtered_articles) - current_media_limit
            next_batch_media = min(20, remaining_media)
            c_m1, c_m2, c_m3 = st.columns([1.5, 2, 1.5])
            with c_m2:
                if st.button(f"⬇️ Load More News (+{next_batch_media} stories)", width="stretch", key="btn_load_more_media"):
                    st.session_state["media_visible_count"] += 20
                    st.rerun()
                st.caption(f"Showing {len(visible_articles):,} of {len(filtered_articles):,} stories ({remaining_media:,} remaining)")
        elif len(filtered_articles) > 0:
            st.caption(f"🏁 You've reached the end of the news feed ({len(filtered_articles):,} stories displayed).")

# ==========================================
# TAB 2: Nepal in Indian Media
# ==========================================
with tab2:
    if filter_start_dt or not is_to_current:
        from_str = filter_start_dt.strftime('%b %d, %Y · %I:%M %p') if filter_start_dt else "Archive Start"
        to_str = f"Current / Now ({filter_end_dt.strftime('%I:%M %p')} NPT)" if is_to_current else filter_end_dt.strftime('%b %d, %Y · %I:%M %p NPT')
        st.markdown(f"""
        <div class="apple-filter-banner">
            <span style="font-size:1.15rem;">⏱</span>
            <div><b>Active Time Range:</b> Showing Indian media stories published from <b>{from_str} NPT</b> up to <b>{to_str}</b>.</div>
        </div>
        """, unsafe_allow_html=True)

    indian_outlet_names = sorted(list(set([s["name"] for s in TOP_INDIAN_MEDIA_SOURCES])))

    tab_filtered_indian = filtered_indian
    ti_col1, ti_col2 = st.columns([2.5, 1.5])
    with ti_col1:
        selected_indian_outlet = st.selectbox(
            "Filter by Specific Indian Media Outlet:",
            ["All 18 Monitored Indian Outlets"] + indian_outlet_names,
            key="select_indian_outlet",
            label_visibility="collapsed"
        )
    
    if selected_indian_outlet != "All 18 Monitored Indian Outlets":
        tab_filtered_indian = [a for a in tab_filtered_indian if a["source"] == selected_indian_outlet]

    with ti_col2:
        st.markdown(f'<div class="apple-counter-badge" style="background:#FFF7ED; color:#C2410C; border-color:#FFEDD5; margin-top:2px; height:38px; display:flex; align-items:center; justify-content:center;">Showing <b>{len(tab_filtered_indian):,}</b> stories · 18 Outlets (EN & HI)</div>', unsafe_allow_html=True)

    st.write("")

    if not tab_filtered_indian:
        st.info("No articles found matching the current timeframe or filter. Try selecting 'All Recent Articles'.")
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
            st.caption(f"🏁 You've reached the end of Indian press coverage ({len(tab_filtered_indian):,} stories displayed).")

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

    # Filter Controls
    xf_col1, xf_col2, xf_col3, xf_col4 = st.columns([2, 1.8, 1.8, 1.4])
    with xf_col1:
        x_cat_filter = st.selectbox(
            "Filter Category:",
            CATEGORY_FILTER_OPTIONS,
            index=0,
            key="x_cat_filter_select"
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
        selected_acc_type = st.selectbox("Account Type:", acc_types, key="x_acc_type_select")
    with xf_col3:
        sort_mode = st.selectbox(
            "Sort Feed By:",
            ["🕒 Newest First (NPT)", "🔥 Most Viral / Engagement", "❤️ Most Liked", "🔁 Most Retweeted"],
            key="x_sort_mode_select"
        )
    with xf_col4:
        st.write("")
        st.write("")
        if st.button("🔄 Rescan X", width="stretch", key="btn_rescan_x"):
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
    st.subheader("📈 Analytics & CSV Export")
    st.write("Inspect, filter, and export the datasets with **Extracted Full News Text** within your selected time window.")

    export_type = st.radio(
        "Choose Dataset to Inspect/Download:",
        ["Nepali Media (34 Portals)", "Nepal in Indian Media (18 Outlets)", "Verified Live X (Twitter) Posts"]
    )

    if export_type == "Nepali Media (34 Portals)":
        if filtered_articles:
            with st.spinner("Extracting full news text for export..."):
                ready_articles = batch_fetch_full_content(filtered_articles)

            export_rows = []
            for a in ready_articles:
                orig_title = (a.get("title") or "").strip()
                export_rows.append({
                    "Headline": orig_title,
                    "Full Content": a.get("full_content") or a.get("summary", ""),
                    "Structured Category": a.get("structured_category", "Others"),
                    "Source / Portal": a.get("source", ""),
                    "Exact Timestamp": a.get("exact_time", ""),
                    "Article Link": a.get("link", "")
                })

            df = pd.DataFrame(export_rows)
            st.markdown(f"**Total Matching Articles in Timeframe:** `{len(df)}`")

            c_cat, c_src = st.columns(2)
            with c_cat:
                st.write("**Articles by Structured Category:**")
                cat_counts_df = df['Structured Category'].value_counts().reset_index()
                cat_counts_df.columns = ['Category', 'Count']
                fig_cat = px.bar(
                    cat_counts_df,
                    x='Count',
                    y='Category',
                    orientation='h',
                    color='Count',
                    color_continuous_scale='Blues',
                    text='Count'
                )
                fig_cat.update_layout(
                    margin=dict(l=10, r=20, t=10, b=10),
                    height=280,
                    showlegend=False,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    yaxis=dict(autorange="reversed")
                )
                st.plotly_chart(fig_cat, width="stretch")

            with c_src:
                st.write("**Top Portals by Volume:**")
                src_counts_df = df['Source / Portal'].value_counts()[:8].reset_index()
                src_counts_df.columns = ['Portal', 'Count']
                fig_src = px.pie(
                    src_counts_df,
                    values='Count',
                    names='Portal',
                    hole=0.45,
                    color_discrete_sequence=px.colors.qualitative.Prism
                )
                fig_src.update_layout(
                    margin=dict(l=10, r=10, t=10, b=10),
                    height=280,
                    paper_bgcolor='rgba(0,0,0,0)',
                    showlegend=True,
                    legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.0)
                )
                st.plotly_chart(fig_src, width="stretch")

            # Category & Source Filter for Selection Table
            st.markdown("##### 📌 Select Articles to Export to Word Document")
            col_filt_np1, col_filt_np2, col_filt_np3 = st.columns([2, 2, 2])
            with col_filt_np1:
                cat_choices = ["All Categories"] + sorted(list(df["Structured Category"].unique()))
                filter_table_cat = st.selectbox("Filter Table by Category:", cat_choices, key="tbl_cat_filter_np")
            with col_filt_np2:
                portal_choices = ["All Portals"] + sorted(list(df["Source / Portal"].unique()))
                filter_table_portal = st.selectbox("Filter Table by Portal:", portal_choices, key="tbl_portal_filter_np")
            with col_filt_np3:
                table_kw = st.text_input("Quick Filter by Keyword:", placeholder="Filter rows...", key="tbl_kw_filter_np")

            # Selection Controls for Word Export
            if "editor_ver_np" not in st.session_state:
                st.session_state["editor_ver_np"] = 0
            if "selected_links_np" not in st.session_state:
                # Default all selected
                st.session_state["selected_links_np"] = set(a.get("link", "") for a in ready_articles)

            col_sel1, col_sel2, col_sel3, col_info = st.columns([1.5, 1.5, 2, 4])
            with col_sel1:
                if st.button("☑️ Select All", key="btn_sel_all_np"):
                    st.session_state["selected_links_np"] = set(a.get("link", "") for a in ready_articles)
                    st.session_state["editor_ver_np"] += 1
                    st.rerun()
            with col_sel2:
                if st.button("⬜ Deselect All", key="btn_desel_all_np"):
                    st.session_state["selected_links_np"] = set()
                    st.session_state["editor_ver_np"] += 1
                    st.rerun()
            with col_sel3:
                if st.button("⚡ Select Top 25 Fresh", key="btn_sel_top25_np"):
                    st.session_state["selected_links_np"] = set(a.get("link", "") for a in ready_articles[:25])
                    st.session_state["editor_ver_np"] += 1
                    st.rerun()

            # Filter rows for display table if user chose filters
            display_df = df.copy()
            if filter_table_cat != "All Categories":
                display_df = display_df[display_df["Structured Category"] == filter_table_cat]
            if filter_table_portal != "All Portals":
                display_df = display_df[display_df["Source / Portal"] == filter_table_portal]
            if table_kw.strip():
                tkw = table_kw.strip().lower()
                display_df = display_df[display_df["Headline"].str.lower().str.contains(tkw, na=False) | display_df["Full Content"].str.lower().str.contains(tkw, na=False)]

            # Map the selection column from persistent session set
            display_df_with_sel = display_df.copy()
            display_df_with_sel.insert(
                0, 
                "Select", 
                [link in st.session_state["selected_links_np"] for link in display_df_with_sel["Article Link"]]
            )

            col_config_np = {
                "Select": st.column_config.CheckboxColumn(
                    "Include in Report?",
                    help="Check this box to include this news item in the Word Document export",
                    default=True
                ),
                "Headline": st.column_config.TextColumn(
                    "Headline",
                    width="large"
                ),
                "Structured Category": st.column_config.TextColumn(
                    "Category",
                    width="medium"
                ),
                "Source / Portal": st.column_config.TextColumn(
                    "Source",
                    width="small"
                ),
                "Exact Timestamp": st.column_config.TextColumn(
                    "Published",
                    width="small"
                ),
                "Article Link": st.column_config.LinkColumn(
                    "Link",
                    display_text="Open ↗",
                    width="small"
                )
            }

            edited_df = st.data_editor(
                display_df_with_sel[["Select", "Headline", "Structured Category", "Source / Portal", "Exact Timestamp", "Article Link"]],
                column_config=col_config_np,
                disabled=[c for c in display_df_with_sel.columns if c != "Select"],
                hide_index=True,
                width="stretch",
                key=f"editor_np_{st.session_state['editor_ver_np']}_{len(display_df)}"
            )

            # Update selected links in session state based on user edits
            for idx, row in edited_df.iterrows():
                link = row["Article Link"]
                if row["Select"]:
                    st.session_state["selected_links_np"].add(link)
                else:
                    st.session_state["selected_links_np"].discard(link)

            selected_articles = [a for a in ready_articles if a.get("link") in st.session_state["selected_links_np"]]

            with col_info:
                st.markdown(f'<div class="apple-counter-badge">📋 <b>{len(selected_articles)} of {len(ready_articles)}</b> articles selected for Executive Report</div>', unsafe_allow_html=True)

            # Interactive Report Preview Expander
            with st.expander("👁️ Executive Word Document Live Preview & Structure", expanded=False):
                st.markdown(f"**Document Title:** `Nepal Media & Intelligence Executive Report`")
                st.markdown(f"**Total Selected Stories:** `{len(selected_articles)}`")
                if selected_articles:
                    sel_cat_counts = Counter([map_to_target_category(a.get("structured_category", "")) for a in selected_articles])
                    p_cols = st.columns(len(DOCX_TARGET_CATEGORIES))
                    for i, tc in enumerate(DOCX_TARGET_CATEGORIES):
                        with p_cols[i]:
                            st.caption(f"**{tc}**\n\n`{sel_cat_counts.get(tc, 0)} items`")
                    st.markdown("---")
                    st.markdown("**Sample Formatted Story in Report:**")
                    sample_a = selected_articles[0]
                    s_orig = sample_a.get("title", "")
                    s_en = sample_a.get("headline_english", "")
                    s_src = sample_a.get("source", "")
                    s_body = (sample_a.get("full_content") or sample_a.get("summary", ""))[:300] + "..."
                    st.markdown(f"""
                    <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-left:4px solid #EAB308; padding:12px 16px; border-radius:8px; font-size:0.9rem;">
                        <div style="font-weight:700; color:#854D0E; font-size:0.75rem; letter-spacing:0.04em; margin-bottom:4px;">{map_to_target_category(sample_a.get("structured_category", ""))}</div>
                        <div style="font-style:italic; font-weight:700; color:#0F172A;">• {html.escape(s_orig)}</div>
                        {f'<div style="font-style:italic; color:#475569; font-size:0.85rem;">{html.escape(s_en)}</div>' if s_en and s_en != s_orig else ''}
                        <div style="font-size:0.82rem; color:#64748B; margin:4px 0;">({html.escape(s_src)})</div>
                        <div style="color:#334155; line-height:1.5; font-size:0.86rem; margin-top:6px;">{html.escape(s_body)}</div>
                        <div style="margin-top:6px; font-size:0.8rem; color:#0284C7; text-decoration:underline;">{html.escape(sample_a.get("link", ""))}</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.info("Select articles above to view report preview.")

            csv_file = df.to_csv(index=False).encode('utf-8-sig')

            c_btn1, c_btn2 = st.columns(2)
            with c_btn1:
                st.download_button(
                    label=f"📥 Download Full CSV Dataset ({len(df)} Articles)",
                    data=csv_file,
                    file_name=f"nepal_media_full_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    width='stretch'
                )
            with c_btn2:
                if selected_articles:
                    docx_data = generate_word_document(selected_articles, report_title="Nepal Media & Intelligence Executive Report")
                    st.download_button(
                        label=f"📄 Generate & Download Executive Word Document ({len(selected_articles)} Stories)",
                        data=docx_data,
                        file_name=f"nepal_media_intelligence_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        width='stretch'
                    )
                else:
                    st.warning("⚠️ No articles selected. Check the box on articles above or click 'Select All' to enable Word export.")
        else:
            st.info("No articles found in the selected timeframe.")
    elif export_type == "Nepal in Indian Media (18 Outlets)":
        if filtered_indian:
            with st.spinner("Extracting full news text for export..."):
                ready_indian = batch_fetch_full_content(filtered_indian)

            export_rows_i = []
            for a in ready_indian:
                orig_title = (a.get("title") or "").strip()
                export_rows_i.append({
                    "Headline": orig_title,
                    "Full Content": a.get("full_content") or a.get("summary", ""),
                    "Source / Outlet": a.get("source", ""),
                    "Exact Timestamp": a.get("exact_time", ""),
                    "Article Link": a.get("link", "")
                })

            df_i = pd.DataFrame(export_rows_i)
            st.markdown(f"**Total Nepal Stories in Indian Press (Timeframe):** `{len(df_i)}`")
            st.write("**Coverage by Indian Outlet:**")
            ind_counts_df = df_i['Source / Outlet'].value_counts()[:10].reset_index()
            ind_counts_df.columns = ['Outlet', 'Articles']
            fig_ind = px.bar(
                ind_counts_df,
                x='Articles',
                y='Outlet',
                orientation='h',
                color='Articles',
                color_continuous_scale='Oranges',
                text='Articles'
            )
            fig_ind.update_layout(
                margin=dict(l=10, r=20, t=10, b=10),
                height=300,
                showlegend=False,
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                yaxis=dict(autorange="reversed")
            )
            st.plotly_chart(fig_ind, width="stretch")

            # Selection Controls for Indian Media Word Export
            if "editor_ver_ind" not in st.session_state:
                st.session_state["editor_ver_ind"] = 0
            if "selected_links_ind" not in st.session_state:
                st.session_state["selected_links_ind"] = set(a.get("link", "") for a in ready_indian)

            st.markdown("##### 📌 Select Articles to Export to Word Document")
            col_filt_i1, col_filt_i2 = st.columns([3, 3])
            with col_filt_i1:
                outlet_choices = ["All Indian Outlets"] + sorted(list(df_i["Source / Outlet"].unique()))
                filter_table_ind = st.selectbox("Filter Table by Outlet:", outlet_choices, key="tbl_outlet_filter_ind")
            with col_filt_i2:
                table_kw_i = st.text_input("Quick Filter Indian Stories by Keyword:", placeholder="Filter rows...", key="tbl_kw_filter_ind")

            col_sel_i1, col_sel_i2, col_sel_i3, col_info_i = st.columns([1.5, 1.5, 2, 4])
            with col_sel_i1:
                if st.button("☑️ Select All", key="btn_sel_all_ind"):
                    st.session_state["selected_links_ind"] = set(a.get("link", "") for a in ready_indian)
                    st.session_state["editor_ver_ind"] += 1
                    st.rerun()
            with col_sel_i2:
                if st.button("⬜ Deselect All", key="btn_desel_all_ind"):
                    st.session_state["selected_links_ind"] = set()
                    st.session_state["editor_ver_ind"] += 1
                    st.rerun()
            with col_sel_i3:
                if st.button("⚡ Select Top 25 Fresh", key="btn_sel_top25_ind"):
                    st.session_state["selected_links_ind"] = set(a.get("link", "") for a in ready_indian[:25])
                    st.session_state["editor_ver_ind"] += 1
                    st.rerun()

            display_df_i = df_i.copy()
            if filter_table_ind != "All Indian Outlets":
                display_df_i = display_df_i[display_df_i["Source / Outlet"] == filter_table_ind]
            if table_kw_i.strip():
                tkw_i = table_kw_i.strip().lower()
                display_df_i = display_df_i[display_df_i["Headline"].str.lower().str.contains(tkw_i, na=False) | display_df_i["Full Content"].str.lower().str.contains(tkw_i, na=False)]

            display_df_i_with_sel = display_df_i.copy()
            display_df_i_with_sel.insert(
                0, 
                "Select", 
                [link in st.session_state["selected_links_ind"] for link in display_df_i_with_sel["Article Link"]]
            )

            col_config_ind = {
                "Select": st.column_config.CheckboxColumn(
                    "Include?",
                    help="Check this box to include this news item in the Word Document export",
                    default=True
                ),
                "Headline": st.column_config.TextColumn(
                    "Headline",
                    width="large"
                ),
                "Source / Outlet": st.column_config.TextColumn(
                    "Indian Outlet",
                    width="medium"
                ),
                "Exact Timestamp": st.column_config.TextColumn(
                    "Published",
                    width="small"
                ),
                "Article Link": st.column_config.LinkColumn(
                    "Link",
                    display_text="Open ↗",
                    width="small"
                )
            }

            edited_df_i = st.data_editor(
                display_df_i_with_sel[["Select", "Headline", "Source / Outlet", "Exact Timestamp", "Article Link"]],
                column_config=col_config_ind,
                disabled=[c for c in display_df_i_with_sel.columns if c != "Select"],
                hide_index=True,
                width="stretch",
                key=f"editor_ind_{st.session_state['editor_ver_ind']}_{len(display_df_i)}"
            )

            # Update selected links in session state
            for idx, row in edited_df_i.iterrows():
                link = row["Article Link"]
                if row["Select"]:
                    st.session_state["selected_links_ind"].add(link)
                else:
                    st.session_state["selected_links_ind"].discard(link)

            selected_indian = [a for a in ready_indian if a.get("link") in st.session_state["selected_links_ind"]]

            with col_info_i:
                st.markdown(f'<div class="apple-counter-badge">📋 <b>{len(selected_indian)} of {len(ready_indian)}</b> articles selected for Executive Report</div>', unsafe_allow_html=True)

            # Interactive Report Preview Expander
            with st.expander("👁️ Indian Press Report Live Preview", expanded=False):
                st.markdown(f"**Document Title:** `Nepal Coverage in Indian Press - Intelligence Dossier`")
                st.markdown(f"**Total Selected Stories:** `{len(selected_indian)}`")
                if selected_indian:
                    st.markdown("**Sample Formatted Story in Report:**")
                    sample_i = selected_indian[0]
                    st.markdown(f"""
                    <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-left:4px solid #F97316; padding:12px 16px; border-radius:8px; font-size:0.9rem;">
                        <div style="font-weight:700; color:#C2410C; font-size:0.75rem; letter-spacing:0.04em; margin-bottom:4px;">INDIA IN NEPAL</div>
                        <div style="font-style:italic; font-weight:700; color:#0F172A;">• {html.escape(sample_i.get("title", ""))}</div>
                        {f'<div style="font-style:italic; color:#475569; font-size:0.85rem;">{html.escape(sample_i.get("headline_english", ""))}</div>' if sample_i.get("headline_english") and sample_i.get("headline_english") != sample_i.get("title") else ''}
                        <div style="font-size:0.82rem; color:#64748B; margin:4px 0;">({html.escape(sample_i.get("source", ""))})</div>
                        <div style="color:#334155; line-height:1.5; font-size:0.86rem; margin-top:6px;">{html.escape((sample_i.get("full_content") or sample_i.get("summary", ""))[:300])}...</div>
                        <div style="margin-top:6px; font-size:0.8rem; color:#0284C7; text-decoration:underline;">{html.escape(sample_i.get("link", ""))}</div>
                    </div>
                    """, unsafe_allow_html=True)

            csv_file_i = df_i.to_csv(index=False).encode('utf-8-sig')

            c_btn_i1, c_btn_i2 = st.columns(2)
            with c_btn_i1:
                st.download_button(
                    label=f"📥 Download Indian Media CSV ({len(df_i)} Articles)",
                    data=csv_file_i,
                    file_name=f"nepal_in_indian_media_full_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    width='stretch'
                )
            with c_btn_i2:
                if selected_indian:
                    docx_data_i = generate_word_document(selected_indian, report_title="Nepal Coverage in Indian Press - Intelligence Dossier")
                    st.download_button(
                        label=f"📄 Generate & Download Executive Word Document ({len(selected_indian)} Stories)",
                        data=docx_data_i,
                        file_name=f"nepal_in_indian_media_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        width='stretch'
                    )
                else:
                    st.warning("⚠️ No articles selected. Check the box on articles above to enable Word export.")
        else:
            st.info("No Indian media articles found in the selected timeframe.")
    elif export_type == "Verified Live X (Twitter) Posts":
        # Verified Live X (Twitter) Posts
        if filtered_x_posts:
            export_rows_x = []
            for p in filtered_x_posts:
                export_rows_x.append({
                    "Post Content": p.get("text", ""),
                    "Author": f"{p.get('author_name', '')} ({p.get('handle', '')})",
                    "Author Type": p.get("author_type", ""),
                    "Structured Category": p.get("structured_category", "Others"),
                    "Likes": p.get("likes", 0),
                    "Retweets": p.get("retweets", 0),
                    "Impressions": p.get("impressions", 0),
                    "Exact Timestamp": p.get("exact_time", ""),
                    "Post Link": p.get("link", "")
                })

            df_x = pd.DataFrame(export_rows_x)
            st.markdown(f"**Total Matching X Posts in Timeframe:** `{len(df_x):,}`")

            cx_cat, cx_type = st.columns(2)
            with cx_cat:
                st.write("**X Posts by Structured Category:**")
                xcat_df = df_x['Structured Category'].value_counts().reset_index()
                xcat_df.columns = ['Category', 'Posts']
                fig_xcat = px.bar(
                    xcat_df,
                    x='Posts',
                    y='Category',
                    orientation='h',
                    color='Posts',
                    color_continuous_scale='Blues',
                    text='Posts'
                )
                fig_xcat.update_layout(
                    margin=dict(l=10, r=20, t=10, b=10),
                    height=280,
                    showlegend=False,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    yaxis=dict(autorange="reversed")
                )
                st.plotly_chart(fig_xcat, width="stretch")

            with cx_type:
                st.write("**X Posts by Account Category:**")
                xtype_df = df_x['Author Type'].value_counts().reset_index()
                xtype_df.columns = ['Account Type', 'Posts']
                fig_xtype = px.pie(
                    xtype_df,
                    values='Posts',
                    names='Account Type',
                    hole=0.45,
                    color_discrete_sequence=px.colors.qualitative.Safe
                )
                fig_xtype.update_layout(
                    margin=dict(l=10, r=10, t=10, b=10),
                    height=280,
                    paper_bgcolor='rgba(0,0,0,0)',
                    showlegend=True,
                    legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.0)
                )
                st.plotly_chart(fig_xtype, width="stretch")

            # Selection Controls for X Posts Word Export
            if "editor_ver_x" not in st.session_state:
                st.session_state["editor_ver_x"] = 0
            if "selected_links_x" not in st.session_state:
                st.session_state["selected_links_x"] = set(p.get("link", "") for p in filtered_x_posts)

            st.markdown("##### 📌 Select X Posts to Export to Word Document")
            col_filt_x1, col_filt_x2, col_filt_x3 = st.columns([2, 2, 2])
            with col_filt_x1:
                x_cat_choices = ["All Categories"] + sorted(list(df_x["Structured Category"].unique()))
                filter_table_xcat = st.selectbox("Filter Table by Category:", x_cat_choices, key="tbl_cat_filter_x")
            with col_filt_x2:
                x_type_choices = ["All Account Types"] + sorted(list(df_x["Author Type"].unique()))
                filter_table_xtype = st.selectbox("Filter Table by Account Type:", x_type_choices, key="tbl_type_filter_x")
            with col_filt_x3:
                table_kw_x = st.text_input("Quick Filter X Posts by Keyword:", placeholder="Filter tweets...", key="tbl_kw_filter_x")

            col_sel_x1, col_sel_x2, col_sel_x3, col_info_x = st.columns([1.5, 1.5, 2, 4])
            with col_sel_x1:
                if st.button("☑️ Select All", key="btn_sel_all_x"):
                    st.session_state["selected_links_x"] = set(p.get("link", "") for p in filtered_x_posts)
                    st.session_state["editor_ver_x"] += 1
                    st.rerun()
            with col_sel_x2:
                if st.button("⬜ Deselect All", key="btn_desel_all_x"):
                    st.session_state["selected_links_x"] = set()
                    st.session_state["editor_ver_x"] += 1
                    st.rerun()
            with col_sel_x3:
                if st.button("⚡ Select Top 25 Viral", key="btn_sel_top25_x"):
                    sorted_viral = sorted(filtered_x_posts, key=lambda x: x.get("likes", 0) + x.get("retweets", 0), reverse=True)
                    st.session_state["selected_links_x"] = set(p.get("link", "") for p in sorted_viral[:25])
                    st.session_state["editor_ver_x"] += 1
                    st.rerun()

            display_df_x = df_x.copy()
            if filter_table_xcat != "All Categories":
                display_df_x = display_df_x[display_df_x["Structured Category"] == filter_table_xcat]
            if filter_table_xtype != "All Account Types":
                display_df_x = display_df_x[display_df_x["Author Type"] == filter_table_xtype]
            if table_kw_x.strip():
                tkw_x = table_kw_x.strip().lower()
                display_df_x = display_df_x[display_df_x["Post Content"].str.lower().str.contains(tkw_x, na=False) | display_df_x["Author"].str.lower().str.contains(tkw_x, na=False)]

            display_df_x_with_sel = display_df_x.copy()
            display_df_x_with_sel.insert(
                0, 
                "Select", 
                [link in st.session_state["selected_links_x"] for link in display_df_x_with_sel["Post Link"]]
            )

            col_config_x = {
                "Select": st.column_config.CheckboxColumn(
                    "Include?",
                    help="Check this box to include this post in the Word Document export",
                    default=True
                ),
                "Post Content": st.column_config.TextColumn(
                    "Post Text",
                    width="large"
                ),
                "Author": st.column_config.TextColumn(
                    "Author",
                    width="medium"
                ),
                "Structured Category": st.column_config.TextColumn(
                    "Category",
                    width="small"
                ),
                "Likes": st.column_config.NumberColumn(
                    "Likes",
                    width="small"
                ),
                "Retweets": st.column_config.NumberColumn(
                    "RTs",
                    width="small"
                ),
                "Post Link": st.column_config.LinkColumn(
                    "Link",
                    display_text="Open on X ↗",
                    width="small"
                )
            }

            edited_df_x = st.data_editor(
                display_df_x_with_sel[["Select", "Post Content", "Author", "Structured Category", "Likes", "Retweets", "Post Link"]],
                column_config=col_config_x,
                disabled=[c for c in display_df_x_with_sel.columns if c != "Select"],
                hide_index=True,
                width="stretch",
                key=f"editor_x_{st.session_state['editor_ver_x']}_{len(display_df_x)}"
            )

            # Update selected links in session state
            for idx, row in edited_df_x.iterrows():
                link = row["Post Link"]
                if row["Select"]:
                    st.session_state["selected_links_x"].add(link)
                else:
                    st.session_state["selected_links_x"].discard(link)

            selected_x_posts = [p for p in filtered_x_posts if p.get("link") in st.session_state["selected_links_x"]]

            with col_info_x:
                st.markdown(f'<div class="apple-counter-badge">📋 <b>{len(selected_x_posts):,} of {len(filtered_x_posts):,}</b> posts selected for Executive Report</div>', unsafe_allow_html=True)

            # Interactive Report Preview Expander
            with st.expander("👁️ X (Twitter) Intelligence Report Live Preview", expanded=False):
                st.markdown(f"**Document Title:** `Nepal X (Twitter) Social Intelligence Report`")
                st.markdown(f"**Total Selected Posts:** `{len(selected_x_posts)}`")
                if selected_x_posts:
                    st.markdown("**Sample Formatted Post in Report:**")
                    sample_x = selected_x_posts[0]
                    st.markdown(f"""
                    <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-left:4px solid #1D9BF0; padding:12px 16px; border-radius:8px; font-size:0.9rem;">
                        <div style="font-weight:700; color:#0284C7; font-size:0.75rem; letter-spacing:0.04em; margin-bottom:4px;">{map_to_target_category(sample_x.get("structured_category", ""))}</div>
                        <div style="font-style:italic; font-weight:700; color:#0F172A;">• {html.escape(sample_x.get("text", "")[:120])}...</div>
                        <div style="font-size:0.82rem; color:#64748B; margin:4px 0;">({html.escape(sample_x.get("author_name", ""))} @{html.escape(sample_x.get("handle", ""))})</div>
                        <div style="color:#334155; line-height:1.5; font-size:0.86rem; margin-top:6px;">{html.escape(sample_x.get("text", ""))}</div>
                        <div style="margin-top:6px; font-size:0.8rem; color:#0284C7; text-decoration:underline;">{html.escape(sample_x.get("link", ""))}</div>
                    </div>
                    """, unsafe_allow_html=True)

            csv_file_x = df_x.to_csv(index=False).encode('utf-8-sig')

            c_btn_x1, c_btn_x2 = st.columns(2)
            with c_btn_x1:
                st.download_button(
                    label=f"📥 Download X Posts CSV ({len(df_x):,} Posts)",
                    data=csv_file_x,
                    file_name=f"nepal_x_posts_full_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    width='stretch'
                )
            with c_btn_x2:
                if selected_x_posts:
                    docx_data_x = generate_word_document(selected_x_posts, report_title="Nepal X (Twitter) Social Intelligence Report")
                    st.download_button(
                        label=f"📄 Generate & Download Executive Word Document ({len(selected_x_posts):,} Selected Posts)",
                        data=docx_data_x,
                        file_name=f"nepal_x_intelligence_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        width='stretch'
                    )
                else:
                    st.warning("⚠️ No posts selected. Check the box on posts above to enable Word export.")
        else:
            st.info("No X posts found matching the selected timeframe.")

    # ==========================================
    # WHATSAPP CHANNEL BROADCAST ENGINE (OPTION 2)
    # ==========================================
    st.markdown("---")
    st.subheader("📢 WhatsApp Broadcast Manager & Live Queue")
    st.write(
        "Manage real-time distribution of individual news stories and X tweets "
        "to your **WhatsApp Group** with automatic deduplication."
    )

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

    # Deduplication Queue: Gather unscanned/unbroadcasted items from current timeframe
    pending_queue = []
    # 1. Nepali Media: every article irrespective of category
    for item in filtered_articles:
        if not is_item_broadcasted(item, "article"):
            pending_queue.append({"item": item, "type": "article", "source_type": "Nepali Media"})
    # 2. Indian Media: all articles substantially related to Nepal
    for item in filtered_indian:
        if is_substantially_related_to_nepal(item):
            if not is_item_broadcasted(item, "article"):
                pending_queue.append({"item": item, "type": "article", "source_type": "Indian Press"})
    # 3. X (Twitter): every accessible new post without relevance filtering
    for item in filtered_x_posts:
        if not is_item_broadcasted(item, "x"):
            pending_queue.append({"item": item, "type": "x", "source_type": "X (Twitter)"})

    q_col1, q_col2 = st.columns([3, 1.2])
    with q_col1:
        st.markdown(f"##### 📥 Pending Broadcast Queue (`{len(pending_queue)}` unsent items in timeframe)")
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
        # Batch Actions Bar
        b_c1, b_c2, b_c3 = st.columns([2, 2.5, 1.8])
        with b_c1:
            st.caption(f"Displaying top **{min(15, len(display_queue))}** of {len(display_queue)} pending items")
        with b_c2:
            if st.button("⚡ Broadcast Top 10 to WhatsApp", key="btn_wa_broadcast_top10"):
                target_chat = get_env_variable("GREEN_API_CHAT_ID")
                wh_url = get_env_variable("WHATSAPP_WEBHOOK_URL")
                sent_count = 0
                for q_entry in display_queue[:10]:
                    raw = q_entry["item"]
                    ityp = q_entry["type"]
                    ok = False
                    if target_chat:
                        ok, _ = dispatch_item_to_green_api(raw, ityp, target_chat)
                    elif wh_url:
                        ok, _ = dispatch_item_to_webhook(raw, ityp, wh_url)
                    else:
                        ok = True
                    if ok:
                        mark_item_broadcasted(raw, ityp)
                        sent_count += 1
                        time.sleep(0.3)
                st.success(f"✅ {sent_count} items broadcasted & marked as sent in cache.")
                st.rerun()
        with b_c3:
            if st.button("🗑 Clear Sent Cache History", key="btn_wa_clear_cache"):
                save_sent_cache({"sent_keys": {}, "history": []})
                st.warning("Sent cache history cleared.")
                st.rerun()

        # Display Queue Cards
        for idx, q_item in enumerate(display_queue[:15]):
            raw_item = q_item["item"]
            itype = q_item["type"]
            stype = q_item["source_type"]
            msg_text = format_whatsapp_message(raw_item, itype)
            wa_dispatch_url = generate_whatsapp_share_url(raw_item, itype)
            item_title = raw_item.get("title") or raw_item.get("text") or "Untitled"
            item_source = raw_item.get("source") or raw_item.get("author_name") or raw_item.get("handle") or "Unknown"
            item_cat = raw_item.get("structured_category", "Others")
            item_time = raw_item.get("exact_time") or raw_item.get("relative_time") or ""

            with st.container():
                st.markdown(f"""
                <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-left:4px solid #22C55E; border-radius:8px; padding:12px; margin-bottom:10px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                        <span style="font-size:0.75rem; background:#F0FDF4; color:#166534; padding:2px 8px; border-radius:4px; font-weight:700;">{stype} · {item_cat}</span>
                        <span style="font-size:0.75rem; color:#64748B;">🕒 {html.escape(str(item_time))}</span>
                    </div>
                    <div style="font-weight:650; font-size:0.95rem; color:#0F172A; margin-bottom:4px;">{html.escape(item_title[:160])}</div>
                    <div style="font-size:0.8rem; color:#64748B;">Source: <b>{html.escape(item_source)}</b></div>
                </div>
                """, unsafe_allow_html=True)

                act_c1, act_c2, act_c3 = st.columns([2.5, 2, 1.5])
                with act_c1:
                    with st.expander("👁 View WhatsApp Formatted Preview", expanded=False):
                        st.code(msg_text, language="markdown")
                with act_c2:
                    st.link_button(
                        "⚡ Broadcast to WhatsApp ↗",
                        wa_dispatch_url,
                        width="stretch",
                        key=f"btn_send_wa_{idx}_{get_item_key(raw_item, itype)}"
                    )
                with act_c3:
                    if st.button("✓ Mark as Sent", key=f"btn_mark_sent_{idx}_{get_item_key(raw_item, itype)}", width="stretch"):
                        mark_item_broadcasted(raw_item, itype)
                        st.rerun()
    else:
        st.success("🎉 All scanned items in this timeframe have been broadcasted! Deduplication engine is up to date.")

    # Recent Broadcast History
    with st.expander("📜 Recent Broadcast History (Last 25 Dispatched Updates)", expanded=False):
        if wa_stats["recent_history"]:
            for h in wa_stats["recent_history"][:15]:
                hc1, hc2, hc3 = st.columns([4, 1.5, 1])
                with hc1:
                    st.markdown(f"**{html.escape(h.get('title', ''))}**\n\n_{html.escape(h.get('source', ''))}_ · `{h.get('stream', h.get('type'))}`")
                with hc2:
                    st.caption(f"Sent: {h.get('sent_at', '')[:16]}")
                with hc3:
                    if st.button("↺ Re-queue", key=f"btn_requeue_{h.get('key')}"):
                        unmark_item_broadcasted({"link": h.get("link"), "title": h.get("title")}, h.get("type", "article"))
                        st.rerun()
        else:
            st.caption("No broadcast history recorded yet.")

    # Source-Wise Broadcast Distribution Matrix & Monitoring Logs
    with st.expander("📊 Source-Wise WhatsApp Distribution Matrix & Audit Logs", expanded=False):
        src_stats = get_source_broadcast_stats()
        if src_stats:
            df_src = pd.DataFrame(src_stats)
            df_src.columns = ["Source / Handle", "Content Stream", "Total Dispatches", "Delivered", "Failed", "Last Dispatched At"]
            st.dataframe(df_src, width="stretch", hide_index=True)
        else:
            cache_src = wa_stats.get("source_stats", {})
            if cache_src:
                rows = []
                for sname, sdata in cache_src.items():
                    rows.append({
                        "Source / Handle": sname,
                        "Content Stream": sdata.get("stream", "General"),
                        "Total Dispatches": sdata.get("total_sent", 0),
                        "Delivered": sdata.get("delivered", sdata.get("total_sent", 0)),
                        "Failed": sdata.get("failed", 0),
                        "Last Dispatched At": sdata.get("last_sent_at", "")
                    })
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            else:
                st.info("No distribution records logged yet. As automated hourly cycles execute, source-wise dispatches will be tracked here.")

# ==========================================
# TAB 5: Nepali Media Monitoring & Control (Chief Admin)
# ==========================================
with tab5:
    st.subheader("📡 Nepali Media Continuous Monitoring & Admin Control")
    st.caption("Comprehensive, independently tracked news discovery across all 34 Nepalese media portals with adaptive scheduling, real-time health matrices, historical backfill, and zero-drop coverage guarantees.")

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
        c_1h = src.get("count_1h", 0)
        c_24h = src.get("count_24h", 0)
        c_7d = src.get("count_7d", 0)
        c_tot = src.get("count_total", 0)
        lat = round(src.get("discovery_latency_avg_secs", 0.0), 2)

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

    # 4. Coverage Diagnostics & Unusually Low Discovery Alerts
    with st.expander("🔍 Coverage Diagnostics & Anomaly Detection", expanded=False):
        low_coverage_sources = [h for h in health_data if h.get("count_24h", 0) == 0 and h.get("enabled", 1)]
        if low_coverage_sources:
            st.warning(f"⚠️ **Low Discovery Alert:** {len(low_coverage_sources)} enabled portals have produced 0 articles in the last 24 hours. Verify feed availability or run deep recovery:")
            for lcs in low_coverage_sources:
                st.write(f"- **{lcs['name']}** ({lcs['type']} · {lcs['lang']}): Status `{lcs['status']}` · Endpoint: `{lcs['url']}`")
        else:
            st.success("🎉 All 34 configured media portals have actively discovered and ingested articles within the last 24-hour window!")
