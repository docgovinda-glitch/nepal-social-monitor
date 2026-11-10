"""
app.py
Interactive Nepal Social Media, Nepali Media (Top 34 Portals), and Nepal in Indian Media Monitor.
Includes:
- Date and Time Picker Filter (From selected timestamp up to current moment in NPT)
- 8 Structured Classification Categories
- 34 Top Nepali and English News Portals
- Dedicated Nepal in Indian Media Menu
- Live Facebook and X (Twitter) Feeds
- CSV / Excel Export with Timestamps and Categories
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import datetime
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
    POPULAR_NEPAL_FB_PAGES,
    POPULAR_NEPAL_X_HANDLES
)
from nepal_x_scanner import (
    scan_popular_nepal_x_posts,
    fetch_real_account_tweets,
    TOP_NEPAL_X_ACCOUNTS
)
from nepal_fb_real_scanner import (
    scan_real_nepal_fb_intelligence,
    load_verified_fb_directory,
    save_manual_curated_post
)
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
    get_green_api_chats
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
    .card-accent-politics { border-left-color: #6366F1 !important; }
    .card-accent-external { border-left-color: #8B5CF6 !important; }
    .card-accent-economy { border-left-color: #059669 !important; }
    .card-accent-others { border-left-color: #94A3B8 !important; }
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
    .cat-badge-politics { background: #EEF2FF; color: #3730A3; border: 1px solid #C7D2FE; padding: 4px 11px; border-radius: 9999px; font-size: 0.74rem; font-weight: 650; }
    .cat-badge-external { background: #F5F3FF; color: #5B21B6; border: 1px solid #DDD6FE; padding: 4px 11px; border-radius: 9999px; font-size: 0.74rem; font-weight: 650; }
    .cat-badge-economy { background: #ECFDF5; color: #047857; border: 1px solid #6EE7B7; padding: 4px 11px; border-radius: 9999px; font-size: 0.74rem; font-weight: 650; }
    .cat-badge-others { background: #F1F5F9; color: #475569; border: 1px solid #E2E8F0; padding: 4px 11px; border-radius: 9999px; font-size: 0.74rem; font-weight: 650; }

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
        font-size: 0.83rem !important;
        font-weight: 600 !important;
        color: #334155 !important;
        letter-spacing: -0.01em !important;
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
st.sidebar.header("🔍 Controls & Filters")
refresh_btn = st.sidebar.button("🔄 Refresh All Feeds Now", width='stretch')

# --- Date & Time Range Filter Section ---
st.sidebar.markdown("---")
st.sidebar.subheader("📅 Date & Timestamp Filter")

DEFAULT_TIME_PRESET = "🕒 Past 48 Hours (Default)"
TIME_FILTER_PRESETS = [
    DEFAULT_TIME_PRESET,
    "⚡ Past 24 Hours",
    "⏳ Past 12 Hours",
    "⏱ Past 6 Hours",
    "📅 Today (Since 00:00 NPT)",
    "📅 Past 7 Days",
    "📆 Past 30 Days",
    "🗓 Custom Date & Timestamp Range...",
    "🏛 All Time (Archive)",
]

# Ensure valid session state value across updates
if st.session_state.get("time_filter_mode_select") not in TIME_FILTER_PRESETS:
    st.session_state["time_filter_mode_select"] = DEFAULT_TIME_PRESET

time_filter_mode = st.sidebar.selectbox(
    "Date & Time Window:",
    TIME_FILTER_PRESETS,
    key="time_filter_mode_select",
    help="Filters all articles, reports, and social feeds published within the selected timeframe in Nepal Time (NPT)."
)

filter_start_dt = None
filter_end_dt = now_npt
explicit_all_time = False

if "Past 6 Hours" in time_filter_mode:
    filter_start_dt = now_npt - datetime.timedelta(hours=6)
elif "Past 12 Hours" in time_filter_mode:
    filter_start_dt = now_npt - datetime.timedelta(hours=12)
elif "Past 24 Hours" in time_filter_mode:
    filter_start_dt = now_npt - datetime.timedelta(hours=24)
elif "Past 48 Hours" in time_filter_mode:
    filter_start_dt = now_npt - datetime.timedelta(hours=48)
elif "Today" in time_filter_mode:
    filter_start_dt = datetime.datetime.combine(now_npt.date(), datetime.time(0, 0), tzinfo=NEPAL_TZ)
elif "Past 7 Days" in time_filter_mode:
    filter_start_dt = now_npt - datetime.timedelta(days=7)
elif "Past 30 Days" in time_filter_mode:
    filter_start_dt = now_npt - datetime.timedelta(days=30)
elif "All Time" in time_filter_mode:
    explicit_all_time = True
    filter_start_dt = None
    filter_end_dt = now_npt
elif "Custom" in time_filter_mode:
    col_from_d, col_from_t = st.sidebar.columns(2)
    with col_from_d:
        from_date = st.date_input(
            "From Date:",
            value=now_npt.date() - datetime.timedelta(days=1),
            max_value=now_npt.date(),
            key="custom_from_date",
            help="Starting date in Nepal Time (NPT)"
        )
    with col_from_t:
        default_from_time = (now_npt - datetime.timedelta(hours=4)).time().replace(second=0, microsecond=0)
        from_time = st.time_input(
            "From Time:",
            value=default_from_time,
            key="custom_from_time",
            help="Starting time in Nepal Time (NPT)"
        )
    filter_start_dt = datetime.datetime.combine(from_date, from_time, tzinfo=NEPAL_TZ)

    to_use_current = st.sidebar.checkbox(
        "⚡ End at Current / Now",
        value=True,
        key="custom_to_use_current",
        help="Quick-select: Automatically ends at the exact present moment (NPT)."
    )
    if to_use_current:
        filter_end_dt = now_npt
        st.sidebar.caption(f"Ending at present moment: **{now_npt.strftime('%b %d · %I:%M %p NPT')}**")
    else:
        col_to_d, col_to_t = st.sidebar.columns(2)
        with col_to_d:
            to_date = st.date_input(
                "To Date:",
                value=now_npt.date(),
                max_value=now_npt.date(),
                min_value=from_date,
                key="custom_to_date",
                help="Ending date in Nepal Time (NPT)"
            )
        with col_to_t:
            to_time = st.time_input(
                "To Time:",
                value=now_npt.time().replace(second=0, microsecond=0),
                key="custom_to_time",
                help="Ending time in Nepal Time (NPT)"
            )
        filter_end_dt = datetime.datetime.combine(to_date, to_time, tzinfo=NEPAL_TZ)
        if filter_end_dt < filter_start_dt:
            st.sidebar.warning("⚠️ 'To' timestamp is earlier than 'From'. Auto-adjusting to end at 'From'.")
            filter_end_dt = filter_start_dt + datetime.timedelta(hours=1)

is_to_current = (filter_end_dt >= now_npt - datetime.timedelta(minutes=2))
to_display_str = f"Current ({filter_end_dt.strftime('%I:%M %p NPT')})" if is_to_current else filter_end_dt.strftime("%b %d, %Y · %I:%M %p NPT")

if filter_start_dt:
    st.sidebar.caption(f"🗓 Active Window: **{filter_start_dt.strftime('%b %d, %I:%M %p')}** → **{to_display_str}**")
elif explicit_all_time:
    st.sidebar.caption(f"📚 Active Window: **Full Archive** up to **{to_display_str}**")

st.sidebar.markdown("---")
st.sidebar.subheader("🔍 Global Search & Filter System")

search_query = st.sidebar.text_input(
    "Search Global Keyword:",
    placeholder="e.g. Balen, India, Budget, Cricket...",
    key="global_search_input",
    help="Bilingual cross-lingual search across Nepali Media, Indian Media, X Posts, and Facebook."
)

CAT_FILTER_ALL_UNFILTERED = "🌐 All (No Filters / Everything)"
CAT_FILTER_ALL_8 = "📂 All Categories (8 Predefined Categories)"
CAT_FILTER_UNCATEGORIZED = "⚪ Uncategorized Feeds Only"

CATEGORY_FILTER_OPTIONS = [
    CAT_FILTER_ALL_UNFILTERED,
    CAT_FILTER_ALL_8,
    CAT_FILTER_UNCATEGORIZED,
] + [f"{CATEGORY_ICONS.get(c, '📌')} {c}" for c in STRUCTURED_CATEGORIES]

selected_cat_filter = st.sidebar.selectbox(
    "Structured Geopolitical Category:",
    CATEGORY_FILTER_OPTIONS,
    index=0,
    key="sidebar_selected_cat_filter",
    help="Default shows all news & posts unfiltered. 'All Categories' filters to the 8 predefined categories and excludes uncategorized social feeds."
)

def reset_all_filters():
    st.session_state["global_search_input"] = ""
    st.session_state["sidebar_selected_cat_filter"] = CAT_FILTER_ALL_UNFILTERED
    st.session_state["time_filter_mode_select"] = DEFAULT_TIME_PRESET
    st.session_state["media_visible_count"] = 20
    st.session_state["indian_visible_count"] = 20
    st.session_state["x_visible_count"] = 20
    st.session_state["fb_visible_count"] = 20
    if "custom_to_use_current" in st.session_state:
        st.session_state["custom_to_use_current"] = True
    if "x_cat_filter_select" in st.session_state:
        st.session_state["x_cat_filter_select"] = CAT_FILTER_ALL_UNFILTERED
    if "fb_cat_filter_select" in st.session_state:
        st.session_state["fb_cat_filter_select"] = CAT_FILTER_ALL_UNFILTERED

# Quick Filter Reset Button in Sidebar
st.sidebar.button("🔄 Reset All Filters", width='stretch', key="btn_reset_filters", on_click=reset_all_filters)

lang_filter = st.sidebar.radio("Content Language:", ["All Languages", "Nepali Only", "English Only", "Hindi Only"])

# Portal Filter Dropdown
all_portal_names = sorted(list(set([p["name"] for p in TOP_NEPAL_NEWS_PORTALS])))
portal_filter = st.sidebar.selectbox(
    "Filter Nepali Portal:",
    ["All Portals (34 Portals)"] + all_portal_names
)

# WhatsApp Channel Subscription Widget in Sidebar
st.sidebar.markdown("---")
wa_channel_url = os.getenv("WHATSAPP_CHANNEL_URL", "")
try:
    if not wa_channel_url and hasattr(st, "secrets"):
        wa_channel_url = st.secrets.get("WHATSAPP_CHANNEL_URL", "")
except Exception:
    pass

if not wa_channel_url:
    wa_channel_url = "https://whatsapp.com/channel/0029Vb92VH61iUxbhQ4HpB38"

st.sidebar.markdown(f"""
<div style="background:#F0FDF4; border:1px solid #BBF7D0; border-radius:10px; padding:12px; margin-bottom:10px;">
    <div style="display:flex; align-items:center; gap:8px;">
        <span style="font-size:1.35rem;">📢</span>
        <div>
            <div style="font-weight:700; color:#166534; font-size:0.86rem;">Official WhatsApp Channel</div>
            <div style="font-size:0.75rem; color:#15803D; line-height:1.35;">Instant alerts for each news story, X tweet & FB post.</div>
        </div>
    </div>
    <div style="margin-top:10px;">
        <a href="{wa_channel_url}" target="_blank" rel="noopener noreferrer" 
           style="display:block; text-align:center; background:#22C55E; color:#FFFFFF !important; text-decoration:none !important; font-weight:700; font-size:0.8rem; padding:7px 12px; border-radius:6px; box-shadow:0 1px 2px rgba(0,0,0,0.06);">
           📲 Follow on WhatsApp ↗
        </a>
    </div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("---")
with st.sidebar.expander("ℹ️ Monitored Sources Summary"):
    st.markdown("**🇳🇵 Nepali Media (34 Portals):** eKantipur, Setopati, Annapurna Post, Naya Patrika, NepalKhabar, Gorkhapatra, News of Nepal, Nepal Aaja, Nepal News, OnlineKhabar, Ratopati, Nagarik News, Nepal Press, Baahrakhari, Himal Press, Deshsanchar, Shilapatra, Nepal Live, Image Khabar, Khabarhub, TechPana, ArthaSarokar, The Kathmandu Post, The Himalayan Times, MyRepublica, The Annapurna Express, Rising Nepal, Nepali Times, etc.")
    st.markdown("**🇮🇳 Indian Media Covering Nepal (18 Prominent Outlets):** The Indian Express, The Hindu, India Today, The Tribune, Business Standard, Financial Express, Livemint, Moneycontrol, ABP Live, Outlook India, The Quint, Swarajya, OneIndia, NDTV, Amar Ujala (Hindi), Live Hindustan (Hindi), Jansatta (Hindi), Prabhat Khabar (Hindi).")

default_bearer = os.getenv("TWITTER_BEARER_TOKEN", "")
try:
    if not default_bearer and hasattr(st, "secrets"):
        default_bearer = st.secrets.get("TWITTER_BEARER_TOKEN", "")
except Exception:
    pass

with st.sidebar.expander("🔑 X (Twitter) Developer API", expanded=False):
    if default_bearer:
        st.success("✅ Credentials active (.env / secrets)")
    st.caption("Paste custom X Bearer Token to override:")
    x_bearer_token = st.text_input("Twitter Bearer Token", value=default_bearer, type="password")

# 6. Fetch Data in Parallel
with st.spinner("Fetching breaking news across 34 Nepal portals, 18 Indian outlets & scanning live verified X posts..."):
    all_articles = fetch_top_nepal_media(max_workers=25)
    indian_articles = fetch_nepal_in_indian_media(max_workers=18)

if "x_posts" not in st.session_state or not st.session_state.get("x_posts") or not any(p.get("is_real_api") for p in st.session_state.get("x_posts", [])):
    st.session_state["x_posts"] = scan_popular_nepal_x_posts(force_refresh=False, x_bearer_token=x_bearer_token)
all_x_posts = st.session_state["x_posts"]

if "fb_directory" not in st.session_state:
    st.session_state["fb_directory"] = load_verified_fb_directory()
verified_fb_directory = st.session_state["fb_directory"]

if "fb_posts" not in st.session_state or not st.session_state.get("fb_posts"):
    st.session_state["fb_posts"] = scan_real_nepal_fb_intelligence(all_articles)
all_fb_posts = st.session_state["fb_posts"]

# Apply Date & Time Range Filter across ALL 4 channels
min_date = datetime.datetime(2020, 1, 1, tzinfo=NEPAL_TZ)

# Determine strict active cutoff for all feeds
active_time_cutoff = filter_start_dt
if not active_time_cutoff and not explicit_all_time:
    # Default timeline across ALL 4 sections: Past 48 Hours
    active_time_cutoff = now_npt - datetime.timedelta(hours=48)

if active_time_cutoff:
    filtered_articles = [a for a in all_articles if a.get("published_dt") and a["published_dt"] >= active_time_cutoff and a["published_dt"] <= filter_end_dt]
    filtered_indian = [a for a in indian_articles if a.get("published_dt") and a["published_dt"] >= active_time_cutoff and a["published_dt"] <= filter_end_dt]
    filtered_x_posts = [p for p in all_x_posts if p.get("published_dt") and p["published_dt"] >= active_time_cutoff and p["published_dt"] <= filter_end_dt]
    filtered_fb_posts = [p for p in all_fb_posts if p.get("published_dt") and p["published_dt"] >= active_time_cutoff and p["published_dt"] <= filter_end_dt]
else:
    filtered_articles = [a for a in all_articles if a.get("published_dt") and a["published_dt"] <= filter_end_dt]
    filtered_indian = [a for a in indian_articles if a.get("published_dt") and a["published_dt"] <= filter_end_dt]
    filtered_x_posts = [p for p in all_x_posts if p.get("published_dt") and p["published_dt"] <= filter_end_dt]
    filtered_fb_posts = [p for p in all_fb_posts if p.get("published_dt") and p["published_dt"] <= filter_end_dt]

# Sort EVERY channel strictly by newest publication timestamp first
filtered_articles.sort(key=lambda x: x.get("published_dt") or min_date, reverse=True)
filtered_indian.sort(key=lambda x: x.get("published_dt") or min_date, reverse=True)
filtered_x_posts.sort(key=lambda x: x.get("published_dt") or min_date, reverse=True)
filtered_fb_posts.sort(key=lambda x: x.get("published_dt") or min_date, reverse=True)

# Calculate Category Counts for Nepali Media (based on time-filtered articles)
cat_counts = Counter([a["structured_category"] for a in filtered_articles])

# Helper for category badge
def get_badge_html(cat):
    badge_classes = {
        "India in Nepal": "cat-badge-india",
        "China in Nepal": "cat-badge-china",
        "Pakistan in Nepal": "cat-badge-pakistan",
        "Bangladesh in Nepal": "cat-badge-bangladesh",
        "Nepal – Internal Politics": "cat-badge-politics",
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
    cat = item.get("structured_category", "Others")
    
    cat_accent_class = {
        "India in Nepal": "card-accent-india",
        "China in Nepal": "card-accent-china",
        "Pakistan in Nepal": "card-accent-pakistan",
        "Bangladesh in Nepal": "card-accent-bangladesh",
        "Nepal – Internal Politics": "card-accent-politics",
        "Nepal – External Relations (Others)": "card-accent-external",
        "Economy": "card-accent-economy",
        "Others": "card-accent-others",
    }.get(cat, "card-accent-others")

    if is_indian:
        cat_accent_class = "card-accent-indian-press"
        source_tag = f'<span class="indian-portal-tag">{source_name}</span>'
        cat_badge = f'<span class="indian-portal-tag">🇮🇳 Indian Press ({html.escape(item.get("language", "English"))})</span>'
    else:
        source_tag = f'<span class="portal-tag">{source_name}</span>'
        cat_badge = get_badge_html(cat)

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
        f'<header class="apple-card-meta">{source_tag}{cat_badge}{lang_badge}{time_badge}</header>'
        f'<h3 class="apple-card-title"><a href="{link}" target="_blank" rel="noopener noreferrer">{title_display}</a></h3>'
        f'{summary_html}'
        f'<footer class="apple-card-footer" style="display:flex; justify-content:space-between; align-items:center;">'
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

# Apple-Grade Facebook Post Card Renderer
def render_apple_fb_post_card(p, auto_translate=False):
    avatar_bg = html.escape(p.get("avatar_bg", "#1877F2"))
    initials = html.escape(p.get("initials", "FB"))
    author_name = html.escape(p.get("author_name", "Author"))
    handle = html.escape(p.get("handle", "fb.com/page"))
    author_type = html.escape(p.get("author_type", "Public Figure"))
    verified_mark = ' <span style="color:#1877F2; font-size:0.92rem; font-weight:800;" title="Verified Page">✓</span>' if p.get("verified") else ""
    
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
    text = re.sub(r'(#[A-Za-z0-9_]+)', r'<b style="color:#1877F2;">\1</b>', text)

    feed_type = p.get("feed_type", "Facebook & Civic Intelligence")
    feed_badge = f'<span style="background:#F1F5F9; color:#475569; padding:2px 8px; border-radius:4px; font-size:0.7rem; font-weight:600;">{html.escape(feed_type)}</span>'

    sentiment = p.get("sentiment", "Neutral")
    if "Alert" in sentiment or "Critical" in sentiment:
        senti_class = "x-sentiment-alert"
    elif "Positive" in sentiment or "Cooperation" in sentiment:
        senti_class = "x-sentiment-positive"
    else:
        senti_class = "x-sentiment-neutral"
    senti_html = f'<span class="x-sentiment-badge {senti_class}">{html.escape(sentiment)}</span>'

    # Determine authentic Facebook link (guaranteeing it points to Facebook)
    fb_link = p.get("fb_link") or p.get("link", "")
    slug = p.get("raw_handle", "")
    
    # If fb_link is not an actual FB domain, use official slug or FB fallback
    is_fb_url = any(dom in fb_link for dom in ["facebook.com", "fb.com", "fb.watch", "fb.me"])
    if not is_fb_url:
        if slug and slug != "media_report":
            fb_link = f"https://www.facebook.com/{slug}"
        else:
            fb_link = "https://www.facebook.com"

    # Contextual CTA label for real post / page
    if "/posts/" in fb_link or "permalink.php" in fb_link or "/share/" in fb_link or "fb.watch" in fb_link or p.get("has_direct_post"):
        cta_label = "View Real Post on Facebook ↗"
    elif slug and slug != "media_report":
        cta_label = f"View {author_name}'s Facebook ↗"
    elif "search/posts" in fb_link:
        cta_label = "Search Post on Facebook ↗"
    else:
        cta_label = "View on Facebook ↗"

    # Optional secondary link to the news coverage if available and distinct
    article_link = p.get("article_link", "")
    source_btn_html = ""
    if article_link and article_link != fb_link and article_link.startswith("http"):
        source_raw = p.get("source", "Media Desk")
        if "via" in source_raw.lower():
            desk_label = source_raw.split("via")[-1].replace(")", "").strip()
        elif "(" in source_raw:
            desk_label = source_raw.split("(")[0].strip()
        else:
            desk_label = source_raw[:24]
        source_btn_html = (
            f'<a href="{html.escape(article_link)}" target="_blank" rel="noopener noreferrer" '
            f'style="font-size:0.75rem; color:#475569; text-decoration:none; padding:4px 9px; '
            f'border-radius:6px; background:#F8FAFC; border:1px solid #CBD5E1; display:inline-flex; '
            f'align-items:center; gap:4px; font-weight:500;" '
            f'title="Read media coverage report on {html.escape(desk_label)}">🗞 {html.escape(desk_label)} Report ↗</a>'
        )

    wa_share_url = generate_whatsapp_share_url(p, "fb")

    return (
        f'<article class="x-post-card" style="border-left: 3px solid #1877F2;">'
        f'<header class="x-post-header">'
        f'<div class="x-author-box">'
        f'<div class="x-avatar" style="background:{avatar_bg};">{initials}</div>'
        f'<div class="x-author-meta">'
        f'<span class="x-author-name">{author_name}{verified_mark}</span>'
        f'<span class="x-author-handle">{handle} · <span class="x-type-badge" style="background:#EBF5FF; color:#1877F2;">{author_type}</span></span>'
        f'</div>'
        f'</div>'
        f'<div style="display:flex; align-items:center; gap:8px;">{feed_badge}{cat_badge}{time_badge}</div>'
        f'</header>'
        f'<div class="x-post-text">{text}</div>'
        f'<footer class="x-engagement-bar">'
        f'<div class="x-metrics-group">'
        f'{senti_html}'
        f'<span style="font-size:0.75rem; color:#64748B;">Authentic Facebook Stream</span>'
        f'</div>'
        f'<div style="display:flex; align-items:center; gap:8px;">'
        f'{source_btn_html}'
        f'<a href="{wa_share_url}" target="_blank" rel="noopener noreferrer" class="apple-wa-share-btn" title="Share Facebook update to WhatsApp">📲 WhatsApp</a>'
        f'<a href="{html.escape(fb_link)}" target="_blank" rel="noopener noreferrer" class="x-cta-link" style="color:#1877F2; background:#EBF5FF; border-color:#BFDBFE; font-weight:600;">{cta_label}</a>'
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
# 4. Monitored Facebook Posts & Insights
# ==========================================

PREDEFINED_8_CATEGORIES = set(STRUCTURED_CATEGORIES)
CORE_7_CATEGORIES = {c for c in STRUCTURED_CATEGORIES if c != "Others"}

def filter_items_by_category(items: list, selected_option: str, is_social: bool = False) -> list:
    """
    Refined news feed filtering mechanism according to user requirements:

    1. Default / Unfiltered State (No Filters Selected):
       Fetch and display all news and posts published by the listed Nepali media outlets across
       all sources—including RSS feeds, X (formerly Twitter), and Facebook—regardless of whether
       they are assigned a category.

    2. "All Categories" Selected:
       Fetch and display news items that fall under any of the 8 predefined categories.
       (Exclude uncategorized posts/social feeds).

    3. "Uncategorized" View:
       Filter and display items that are uncategorized, unassigned, or general feeds.

    4. Single Category Selected:
       Filter and display news items exclusively belonging to the selected category.
    """
    if not items:
        return []
    if not selected_option or selected_option == CAT_FILTER_ALL_UNFILTERED or selected_option.startswith("🌐 All"):
        return items

    if selected_option == CAT_FILTER_ALL_8 or "All Categories" in selected_option:
        res = []
        for it in items:
            cat = str(it.get("structured_category") or it.get("category") or "").strip()
            if not cat or cat.lower() in ["uncategorized", "none", "null", "unassigned", ""]:
                continue
            if is_social:
                # For social feeds (X, Facebook): exclude uncategorized/general social feeds (must belong to core categories)
                if cat in CORE_7_CATEGORIES:
                    res.append(it)
            else:
                # For media articles: must fall under any of the 8 predefined categories
                if cat in PREDEFINED_8_CATEGORIES:
                    res.append(it)
        return res

    if selected_option == CAT_FILTER_UNCATEGORIZED or "Uncategorized" in selected_option:
        res = []
        for it in items:
            cat = str(it.get("structured_category") or it.get("category") or "").strip()
            if not cat or cat.lower() in ["uncategorized", "none", "null", "unassigned", ""]:
                res.append(it)
            elif is_social and cat == "Others":
                res.append(it)
            elif not is_social and cat not in PREDEFINED_8_CATEGORIES:
                res.append(it)
        return res

    # Single Category Selected: extract category name
    chosen_cat = selected_option.split(" ", 1)[1] if " " in selected_option else selected_option
    return [it for it in items if it.get("structured_category") == chosen_cat]

# 1. Global Category Filter (Seamless across all 4 channels)
filtered_articles = filter_items_by_category(filtered_articles, selected_cat_filter, is_social=False)
filtered_indian = filter_items_by_category(filtered_indian, selected_cat_filter, is_social=False)
filtered_x_posts = filter_items_by_category(filtered_x_posts, selected_cat_filter, is_social=True)
filtered_fb_posts = filter_items_by_category(filtered_fb_posts, selected_cat_filter, is_social=True)

# 2. Strengthened Bilingual & Cross-Channel Search Filter
if search_query and search_query.strip():
    filtered_articles = [a for a in filtered_articles if smart_search_match(a, search_query)]
    filtered_indian = [a for a in filtered_indian if smart_search_match(a, search_query)]
    filtered_x_posts = [p for p in filtered_x_posts if smart_search_match(p, search_query)]
    filtered_fb_posts = [p for p in filtered_fb_posts if smart_search_match(p, search_query)]

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
    f"📰 Nepali Media ({len(filtered_articles)})",
    f"🇮🇳 Indian Media ({len(filtered_indian)})",
    f"🐦 X (Twitter) ({len(filtered_x_posts)})",
    f"📘 Facebook ({len(filtered_fb_posts)})",
    "📈 Analytics & Export"
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

    with st.expander("⚡ Quick Jump to Live X Searches Across 8 Predefined Categories", expanded=False):
        clean_q = search_query.strip() if search_query else ""
        if clean_q:
            st.caption(f"Launch live X searches combining your search keyword **'{html.escape(clean_q)}'** with any of the 8 predefined categories:")
        else:
            st.caption("One-click direct access to real-time live posts on X (Twitter) across the 8 predefined strategic categories:")

        x_cat_searches = [
            {
                "label": "🇮🇳 India in Nepal ↗",
                "query": '("Nepal" OR "नेपाल") AND ("India" OR "Modi" OR "भारत" OR "#NepalIndia")',
                "help": "Search live X posts on India-Nepal bilateral relations, border & treaties"
            },
            {
                "label": "🇨🇳 China in Nepal ↗",
                "query": '("Nepal" OR "नेपाल") AND ("China" OR "Beijing" OR "BRI" OR "चीन" OR "#NepalChina")',
                "help": "Search live X posts on China-Nepal relations, BRI, and border crossings"
            },
            {
                "label": "🇵🇰 Pakistan in Nepal ↗",
                "query": '("Nepal" OR "नेपाल") AND ("Pakistan" OR "Islamabad" OR "पाकिस्तान" OR "#NepalPakistan")',
                "help": "Search live X posts on Pakistan-Nepal engagements and SAARC"
            },
            {
                "label": "🇧🇩 Bangladesh in Nepal ↗",
                "query": '("Nepal" OR "नेपाल") AND ("Bangladesh" OR "Dhaka" OR "बंगलादेश" OR "#NepalBangladesh")',
                "help": "Search live X posts on Bangladesh-Nepal energy trade and transit"
            },
            {
                "label": "🏛 Internal Politics ↗",
                "query": '("Nepal" OR "नेपाल") AND ("politics" OR "Oli" OR "Deuba" OR "Prachanda" OR "Balen" OR "संसद्" OR "राजनीति")',
                "help": "Search live X posts on Nepal internal politics, parliament, and leaders"
            },
            {
                "label": "🌐 External Relations ↗",
                "query": '("Nepal" OR "नेपाल") AND ("foreign" OR "diplomacy" OR "ambassador" OR "USAID" OR "MCC" OR "परराष्ट्र" OR "कूटनीति")',
                "help": "Search live X posts on Nepal multilateral relations, US, EU, and foreign affairs"
            },
            {
                "label": "💰 Economy ↗",
                "query": '("Nepal" OR "नेपाल") AND ("economy" OR "NRB" OR "remittance" OR "inflation" OR "budget" OR "अर्थतन्त्र" OR "बजेट")',
                "help": "Search live X posts on Nepal economy, remittance, inflation, and NRB policy"
            },
            {
                "label": "📌 Others (Civic) ↗",
                "query": '("Nepal" OR "नेपाल") AND ("society" OR "civic" OR "governance" OR "जनता" OR "#Nepal")',
                "help": "Search live X posts on broader Nepali civic, social, and governance topics"
            },
        ]

        # Row 1: Regional Bilateral Relations (India, China, Pakistan, Bangladesh)
        r1_cols = st.columns(4)
        for i, item in enumerate(x_cat_searches[:4]):
            with r1_cols[i]:
                full_q = f"({clean_q}) AND {item['query']}" if clean_q else item["query"]
                x_url = f"https://x.com/search?q={urllib.parse.quote_plus(full_q)}&f=live"
                st.link_button(item["label"], x_url, width="stretch", help=item["help"])

        # Row 2: Domestic & Global Themes (Politics, Foreign Relations, Economy, Others)
        r2_cols = st.columns(4)
        for i, item in enumerate(x_cat_searches[4:]):
            with r2_cols[i]:
                full_q = f"({clean_q}) AND {item['query']}" if clean_q else item["query"]
                x_url = f"https://x.com/search?q={urllib.parse.quote_plus(full_q)}&f=live"
                st.link_button(item["label"], x_url, width="stretch", help=item["help"])

# ==========================================
# TAB 4: Facebook Trends Nepal
# ==========================================
with tab4:
    # Seamlessly integrated FB posts (filtered by global search, category, and 48h default)
    tab_fb_posts = filtered_fb_posts

    # Monitored Profiles Directory (100+ Curated Profiles)
    with st.expander(f"🇳🇵 Monitored Directory of 100+ Facebook Personalities, Institutions & Embassies", expanded=False):
        st.write(f"Direct verified directory of **{len(verified_fb_directory)} Facebook public pages, senior journalists, analysts, and state institutions** with one-click links to their live pages:")
        
        dir_cat_choice = st.selectbox(
            "Filter Directory by Sector:",
            ["All Sectors"] + sorted(list(set(p.get("type", "General") for p in verified_fb_directory))),
            key="fb_dir_sector_filter"
        )
        filtered_dir = verified_fb_directory
        if dir_cat_choice != "All Sectors":
            filtered_dir = [p for p in filtered_dir if p.get("type") == dir_cat_choice]

        fba_cols = st.columns(3)
        for i, a in enumerate(filtered_dir):
            with fba_cols[i % 3]:
                st.markdown(f"""
                <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:10px; padding:12px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.02); display:flex; flex-direction:column; justify-content:space-between; min-height:130px;">
                    <div>
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                            <span style="font-size:10.5px; background:#f1f5f9; color:#475569; padding:2px 7px; border-radius:4px; font-weight:600;">{a.get('category', 'Others')}</span>
                            <span style="font-size:11px; color:#1877f2; font-weight:600;">{a.get('type', '')}</span>
                        </div>
                        <div style="display:flex; align-items:center; gap:8px; margin-top:4px;">
                            <div style="width:30px; height:30px; border-radius:50%; background:{a.get('avatar_bg', '#1877f2')}; color:#fff; display:flex; align-items:center; justify-content:center; font-size:11px; font-weight:700; flex-shrink:0;">{a.get('initials', 'FB')}</div>
                            <div style="overflow:hidden;">
                                <div style="font-weight:600; font-size:13px; color:#0f172a; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{a['name']}</div>
                                <div style="font-size:11px; color:#64748b;">fb.com/{a['slug']}</div>
                            </div>
                        </div>
                        <div style="font-size:11px; color:#475569; line-height:1.35; margin-top:6px; margin-bottom:8px; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;">{a.get('desc', '')}</div>
                    </div>
                    <div style="border-top:1px solid #f1f5f9; padding-top:6px; font-size:11px; display:flex; justify-content:space-between;">
                        <a href="https://facebook.com/{a['slug']}" target="_blank" style="font-weight:600; color:#1877f2; text-decoration:none;">Open Page on FB ↗</a>
                        {f'<a href="https://x.com/{a.get("x_handle")}" target="_blank" style="color:#0284c7; text-decoration:none;">@{a.get("x_handle")} on X ↗</a>' if a.get("x_handle") else ''}
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # Interactive User Post Curation Tool
    with st.expander("➕ Curate / Add Any Specific Public Facebook Post to Executive Report", expanded=False):
        st.write("Found an important public Facebook post from a leader or journalist? Paste its URL below to add it to the live stream and include it in your Word document and CSV export.")
        c_p1, c_p2 = st.columns([3, 1])
        with c_p1:
            custom_post_url = st.text_input("Facebook Post URL:", placeholder="https://www.facebook.com/.../posts/...", key="input_custom_fb_post_url")
            custom_post_text = st.text_area("Post Summary / Excerpt:", placeholder="Brief excerpt or key takeaway from this post...", key="input_custom_fb_post_text", height=80)
        with c_p2:
            custom_post_author = st.text_input("Author / Page Name:", placeholder="e.g. Balen Shah", key="input_custom_fb_post_author")
            custom_post_cat = st.selectbox("Category:", STRUCTURED_CATEGORIES, key="input_custom_fb_post_cat")
            st.write("")
            if st.button("📌 Add Post to Stream", width="stretch", key="btn_add_custom_fb_post"):
                if custom_post_url.strip() and custom_post_author.strip():
                    new_post_entry = {
                        "id": f"custom_fb_{hash(custom_post_url) % 1000000}",
                        "source": "User Curated Public Post",
                        "author_name": custom_post_author.strip(),
                        "author_type": "Curated Public Figure",
                        "handle": f"fb.com/post",
                        "raw_handle": "curated_post",
                        "role": "Curated Facebook Post",
                        "verified": True,
                        "avatar_bg": "#1877f2",
                        "initials": custom_post_author.strip()[:2].upper(),
                        "title": custom_post_text.strip()[:90] if custom_post_text.strip() else f"Post by {custom_post_author.strip()}",
                        "text": custom_post_text.strip() if custom_post_text.strip() else f"Direct Facebook Post by {custom_post_author.strip()}",
                        "headline_english": "",
                        "structured_category": custom_post_cat,
                        "link": custom_post_url.strip(),
                        "likes": 0,
                        "shares": 0,
                        "comments": 0,
                        "impressions": 0,
                        "engagement_score": 100,
                        "published_dt": datetime.datetime.now(NEPAL_TZ),
                        "relative_time": "Just now",
                        "exact_time": datetime.datetime.now(NEPAL_TZ).strftime("%b %d, %I:%M %p NPT"),
                        "sentiment": "Civic Discourse",
                        "feed_type": "Curated Post"
                    }
                    save_manual_curated_post(new_post_entry)
                    st.session_state["fb_posts"] = scan_real_nepal_fb_intelligence(all_articles)
                    st.success("✅ Post successfully added to live feed and report export!")
                    st.rerun()
                else:
                    st.warning("Please provide at least the post URL and Author/Page name.")

    st.markdown("---")

    # Feed Filter & Sorting Controls
    fbf_col1, fbf_col2, fbf_col3, fbf_col4, fbf_col5 = st.columns([1.8, 1.6, 1.6, 1.6, 1.2])
    with fbf_col1:
        fb_cat_filter = st.selectbox(
            "Filter Category:",
            CATEGORY_FILTER_OPTIONS,
            index=0,
            key="fb_cat_filter_select"
        )
    with fbf_col2:
        feed_types = [
            "All Stream Sources",
            "Monitored Page Statements & Reports",
            "Media Reported FB Statements",
            "Monitored News Platform Posts",
            "Official Dispatches",
            "Curated Posts"
        ]
        selected_feed_type = st.selectbox("Intelligence Type:", feed_types, key="fb_feed_type_select")
    with fbf_col3:
        fb_time_scope = st.selectbox(
            "Time Horizon:",
            [
                "🕒 Last 48 Hours (Default)",
                "⚡ Past 24 Hours",
                "⏳ Past 12 Hours",
                "📅 Past 7 Days",
                "🏛 All Time / Full Archive"
            ],
            key="fb_time_scope_select"
        )
    with fbf_col4:
        fb_sort_mode = st.selectbox(
            "Sort Feed By:",
            ["🕒 Newest First (NPT)", "📌 High Priority Dispatches First"],
            key="fb_sort_mode_select"
        )
    with fbf_col5:
        st.write("")
        st.write("")
        if st.button("🔄 Rescan", width="stretch", key="btn_rescan_fb"):
            with st.spinner("Re-aggregating real-time media statements and official diplomatic dispatches..."):
                st.session_state["fb_posts"] = scan_real_nepal_fb_intelligence(all_articles)
                st.rerun()

    # Inherit from filtered_fb_posts (which strictly adheres to user-specified timeline, search & category)
    filtered_fb_feed = list(filtered_fb_posts)

    # 1. Apply in-tab tighter time scope refinement if chosen
    if fb_time_scope == "⚡ Past 24 Hours":
        cutoff_24 = now_npt - datetime.timedelta(hours=24)
        filtered_fb_feed = [p for p in filtered_fb_feed if p.get("published_dt") and p["published_dt"] >= cutoff_24]
    elif fb_time_scope == "⏳ Past 12 Hours":
        cutoff_12 = now_npt - datetime.timedelta(hours=12)
        filtered_fb_feed = [p for p in filtered_fb_feed if p.get("published_dt") and p["published_dt"] >= cutoff_12]

    # 2. Apply in-tab category filter if selected
    filtered_fb_feed = filter_items_by_category(filtered_fb_feed, fb_cat_filter, is_social=True)

    # 4. Apply intelligence type filter
    if selected_feed_type != "All Stream Sources":
        if selected_feed_type == "Monitored Page Statements & Reports":
            filtered_fb_feed = [p for p in filtered_fb_feed if "Page Statement" in p.get("feed_type", "")]
        elif selected_feed_type == "Media Reported FB Statements":
            filtered_fb_feed = [p for p in filtered_fb_feed if "Media Reported" in p.get("feed_type", "")]
        elif selected_feed_type == "Monitored News Platform Posts":
            filtered_fb_feed = [p for p in filtered_fb_feed if "Platform Post" in p.get("feed_type", "")]
        elif selected_feed_type == "Official Dispatches":
            filtered_fb_feed = [p for p in filtered_fb_feed if p.get("feed_type") == "Official Dispatch"]
        elif selected_feed_type == "Curated Posts":
            filtered_fb_feed = [p for p in filtered_fb_feed if p.get("feed_type") == "Curated Post"]

    # 5. Apply sorting
    if fb_sort_mode == "🕒 Newest First (NPT)":
        min_date = datetime.datetime(2020, 1, 1, tzinfo=NEPAL_TZ)
        filtered_fb_feed = sorted(filtered_fb_feed, key=lambda x: x.get("published_dt") or min_date, reverse=True)
    elif fb_sort_mode == "📌 High Priority Dispatches First":
        filtered_fb_feed = sorted(filtered_fb_feed, key=lambda x: x.get("engagement_score", 0), reverse=True)

    # Display count banner
    time_badge_label = "Last 48 Hours → Current (Default)"
    if filter_start_dt or not is_to_current:
        from_fb_lbl = filter_start_dt.strftime('%b %d, %I:%M %p') if filter_start_dt else "Start"
        to_fb_lbl = "Current / Now" if is_to_current else filter_end_dt.strftime('%b %d, %I:%M %p')
        time_badge_label = f"Range: {from_fb_lbl} → {to_fb_lbl}"
    elif fb_time_scope != "🕒 Last 48 Hours (Default)":
        time_badge_label = fb_time_scope.split(" ", 1)[1] if " " in fb_time_scope else fb_time_scope

    st.markdown(f'<div class="apple-counter-badge" style="background:#EBF5FF; color:#1877F2; border-color:#BFDBFE;">Showing <b>{len(filtered_fb_feed):,} of {len(all_fb_posts):,}</b> authentic intelligence items · Horizon: <b>{time_badge_label}</b></div>', unsafe_allow_html=True)
    st.write("")

    # Render Post Cards with "Load More Feeds" button
    if "fb_visible_count" not in st.session_state:
        st.session_state["fb_visible_count"] = 20

    current_fb_limit = st.session_state["fb_visible_count"]
    visible_fb_posts = filtered_fb_feed[:current_fb_limit]

    for p in visible_fb_posts:
        st.markdown(render_apple_fb_post_card(p), unsafe_allow_html=True)

    if len(filtered_fb_feed) > current_fb_limit:
        remaining_fb = len(filtered_fb_feed) - current_fb_limit
        next_batch_fb = min(20, remaining_fb)
        c_lmf1, c_lmf2, c_lmf3 = st.columns([1.5, 2, 1.5])
        with c_lmf2:
            if st.button(f"⬇️ Load More Feeds (+{next_batch_fb} items)", width="stretch", key="btn_load_more_fb"):
                st.session_state["fb_visible_count"] += 20
                st.rerun()
            st.caption(f"Showing {len(visible_fb_posts):,} of {len(filtered_fb_feed):,} items ({remaining_fb:,} remaining)")
    elif len(filtered_fb_feed) > 0:
        st.caption(f"🏁 You've reached the end of the stream ({len(filtered_fb_feed):,} items displayed).")

    st.markdown("---")

    with st.expander("⚡ Quick Jump to Live Facebook Searches & Discussions in Nepal", expanded=False):
        q_fb = urllib.parse.quote_plus(search_query if search_query else "Nepal viral")
        fcol1, fcol2, fcol3, fcol4 = st.columns(4)
        with fcol1:
            st.link_button("🔍 Search Keyword on FB ↗", f"https://www.facebook.com/search/posts/?q={q_fb}", width='stretch')
        with fcol2:
            st.link_button("📺 Watch Trending Videos ↗", "https://www.facebook.com/watch/search/?q=nepal+trending", width='stretch')
        with fcol3:
            st.link_button("🔥 #Nepal Viral Tag ↗", "https://www.facebook.com/hashtag/nepal", width='stretch')
        with fcol4:
            st.link_button("🏛 #BalenShah on FB ↗", "https://www.facebook.com/hashtag/balenshah", width='stretch')

# ==========================================
# TAB 5: Analytics & Export
# ==========================================
with tab5:
    st.subheader("📈 Analytics & CSV Export")
    st.write("Inspect, filter, and export the datasets with **Extracted Full News Text** within your selected time window.")

    export_type = st.radio(
        "Choose Dataset to Inspect/Download:",
        ["Nepali Media (34 Portals)", "Nepal in Indian Media (18 Outlets)", "Verified Live X (Twitter) Posts", "Monitored Facebook Posts & Insights"]
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
                st.plotly_chart(fig_cat, use_container_width=True)

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
                st.plotly_chart(fig_src, use_container_width=True)

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
            st.plotly_chart(fig_ind, use_container_width=True)

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
                st.plotly_chart(fig_xcat, use_container_width=True)

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
                st.plotly_chart(fig_xtype, use_container_width=True)

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
    elif export_type == "Monitored Facebook Posts & Insights":
        # Monitored Facebook Posts
        if filtered_fb_posts:
            export_rows_fb = []
            for p in filtered_fb_posts:
                export_rows_fb.append({
                    "Post Content": p.get("text", ""),
                    "Page / Author": f"{p.get('author_name', '')} ({p.get('handle', '')})",
                    "Profile Role": p.get("author_type", ""),
                    "Structured Category": p.get("structured_category", "Others"),
                    "Likes / Reactions": p.get("likes", 0),
                    "Shares": p.get("shares", 0),
                    "Comments": p.get("comments", 0),
                    "Estimated Reach": p.get("impressions", 0),
                    "Exact Timestamp": p.get("exact_time", ""),
                    "Post Link": p.get("link", "")
                })

            df_fb = pd.DataFrame(export_rows_fb)
            st.markdown(f"**Total Matching Facebook Posts in Timeframe:** `{len(df_fb):,}`")

            cfb_cat, cfb_type = st.columns(2)
            with cfb_cat:
                st.write("**Facebook Posts by Structured Category:**")
                fbcat_df = df_fb['Structured Category'].value_counts().reset_index()
                fbcat_df.columns = ['Category', 'Posts']
                fig_fbcat = px.bar(
                    fbcat_df,
                    x='Posts',
                    y='Category',
                    orientation='h',
                    color='Posts',
                    color_continuous_scale='Blues',
                    text='Posts'
                )
                fig_fbcat.update_layout(
                    margin=dict(l=10, r=20, t=10, b=10),
                    height=280,
                    showlegend=False,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    yaxis=dict(autorange="reversed")
                )
                st.plotly_chart(fig_fbcat, use_container_width=True)

            with cfb_type:
                st.write("**Facebook Posts by Profile Sector:**")
                fbtype_df = df_fb['Profile Role'].value_counts()[:8].reset_index()
                fbtype_df.columns = ['Profile Sector', 'Posts']
                fig_fbtype = px.pie(
                    fbtype_df,
                    values='Posts',
                    names='Profile Sector',
                    hole=0.45,
                    color_discrete_sequence=px.colors.qualitative.Prism
                )
                fig_fbtype.update_layout(
                    margin=dict(l=10, r=10, t=10, b=10),
                    height=280,
                    paper_bgcolor='rgba(0,0,0,0)',
                    showlegend=True,
                    legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.0)
                )
                st.plotly_chart(fig_fbtype, use_container_width=True)

            # Selection Controls for Facebook Posts Word Export
            if "editor_ver_fb" not in st.session_state:
                st.session_state["editor_ver_fb"] = 0
            if "selected_links_fb" not in st.session_state:
                st.session_state["selected_links_fb"] = set(p.get("link", "") for p in filtered_fb_posts)

            st.markdown("##### 📌 Select Facebook Posts to Export to Word Document")
            col_filt_fb1, col_filt_fb2, col_filt_fb3 = st.columns([2, 2, 2])
            with col_filt_fb1:
                fb_cat_choices = ["All Categories"] + sorted(list(df_fb["Structured Category"].unique()))
                filter_table_fbcat = st.selectbox("Filter Table by Category:", fb_cat_choices, key="tbl_cat_filter_fb")
            with col_filt_fb2:
                fb_type_choices = ["All Profile Types"] + sorted(list(df_fb["Profile Role"].unique()))
                filter_table_fbtype = st.selectbox("Filter Table by Profile Type:", fb_type_choices, key="tbl_type_filter_fb")
            with col_filt_fb3:
                table_kw_fb = st.text_input("Quick Filter FB Posts by Keyword:", placeholder="Filter posts...", key="tbl_kw_filter_fb")

            col_sel_fb1, col_sel_fb2, col_sel_fb3, col_info_fb = st.columns([1.5, 1.5, 2, 4])
            with col_sel_fb1:
                if st.button("☑️ Select All", key="btn_sel_all_fb"):
                    st.session_state["selected_links_fb"] = set(p.get("link", "") for p in filtered_fb_posts)
                    st.session_state["editor_ver_fb"] += 1
                    st.rerun()
            with col_sel_fb2:
                if st.button("⬜ Deselect All", key="btn_desel_all_fb"):
                    st.session_state["selected_links_fb"] = set()
                    st.session_state["editor_ver_fb"] += 1
                    st.rerun()
            with col_sel_fb3:
                if st.button("⚡ Select Top Viral", key="btn_sel_top_fb"):
                    sorted_viral_fb = sorted(filtered_fb_posts, key=lambda x: x.get("likes", 0) + (x.get("shares", 0) * 3), reverse=True)
                    st.session_state["selected_links_fb"] = set(p.get("link", "") for p in sorted_viral_fb[:15])
                    st.session_state["editor_ver_fb"] += 1
                    st.rerun()

            display_df_fb = df_fb.copy()
            if filter_table_fbcat != "All Categories":
                display_df_fb = display_df_fb[display_df_fb["Structured Category"] == filter_table_fbcat]
            if filter_table_fbtype != "All Profile Types":
                display_df_fb = display_df_fb[display_df_fb["Profile Role"] == filter_table_fbtype]
            if table_kw_fb.strip():
                tkw_fb = table_kw_fb.strip().lower()
                display_df_fb = display_df_fb[display_df_fb.apply(lambda r: tkw_fb in str(r["Post Content"]).lower() or tkw_fb in str(r["Page / Author"]).lower(), axis=1)]

            display_df_fb.insert(0, "Select", display_df_fb["Post Link"].apply(lambda l: l in st.session_state["selected_links_fb"]))

            edited_df_fb = st.data_editor(
                display_df_fb,
                column_config={
                    "Select": st.column_config.CheckboxColumn(
                        "Include in Report",
                        help="Check to include in Executive Word Document",
                        default=True,
                    ),
                    "Post Content": st.column_config.TextColumn("Post Content", width="large"),
                    "Page / Author": st.column_config.TextColumn("Page / Author", width="medium"),
                    "Profile Role": st.column_config.TextColumn("Role / Sector", width="medium"),
                    "Structured Category": st.column_config.TextColumn("Category", width="small"),
                    "Likes / Reactions": st.column_config.NumberColumn("Reactions", format="%d"),
                    "Shares": st.column_config.NumberColumn("Shares", format="%d"),
                    "Estimated Reach": st.column_config.NumberColumn("Reach", format="%d"),
                    "Exact Timestamp": st.column_config.TextColumn("Timestamp", width="small"),
                    "Post Link": st.column_config.LinkColumn("Link", width="small")
                },
                disabled=["Post Content", "Page / Author", "Profile Role", "Structured Category", "Likes / Reactions", "Shares", "Comments", "Estimated Reach", "Exact Timestamp", "Post Link"],
                hide_index=True,
                use_container_width=True,
                key=f"fb_editor_{st.session_state['editor_ver_fb']}"
            )

            for idx, row in edited_df_fb.iterrows():
                link = row["Post Link"]
                if row["Select"]:
                    st.session_state["selected_links_fb"].add(link)
                else:
                    st.session_state["selected_links_fb"].discard(link)

            selected_fb_posts = [p for p in filtered_fb_posts if p.get("link") in st.session_state["selected_links_fb"]]

            with col_info_fb:
                st.markdown(f'<div class="apple-counter-badge">📋 <b>{len(selected_fb_posts):,} of {len(filtered_fb_posts):,}</b> posts selected for Executive Report</div>', unsafe_allow_html=True)

            csv_file_fb = df_fb.to_csv(index=False).encode('utf-8-sig')

            c_btn_fb1, c_btn_fb2 = st.columns(2)
            with c_btn_fb1:
                st.download_button(
                    label=f"📥 Download Facebook Posts CSV ({len(df_fb):,} Posts)",
                    data=csv_file_fb,
                    file_name=f"nepal_facebook_posts_full_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    width='stretch'
                )
            with c_btn_fb2:
                if selected_fb_posts:
                    docx_data_fb = generate_word_document(selected_fb_posts, report_title="Nepal Facebook Social Intelligence Report")
                    st.download_button(
                        label=f"📄 Generate & Download Executive Word Document ({len(selected_fb_posts):,} Selected Posts)",
                        data=docx_data_fb,
                        file_name=f"nepal_facebook_intelligence_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        width='stretch'
                    )
                else:
                    st.warning("⚠️ No posts selected. Check the box on posts above to enable Word export.")
        else:
            st.info("No Facebook posts found matching the selected timeframe.")

    # ==========================================
    # WHATSAPP CHANNEL BROADCAST ENGINE (OPTION 2)
    # ==========================================
    st.markdown("---")
    st.subheader("📢 WhatsApp Channel Broadcast Manager & Live Queue")
    st.write(
        "Manage real-time distribution of individual news stories, X tweets, and Facebook intelligence "
        "to your **Official WhatsApp Channel subscribers** with automatic deduplication."
    )

    wa_stats = get_broadcasted_stats()

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total Broadcasted", f"{wa_stats['total_broadcasted']:,}")
    with m2:
        st.metric("📰 News Stories", f"{wa_stats['by_type']['article']:,}")
    with m3:
        st.metric("🐦 X (Twitter)", f"{wa_stats['by_type']['x']:,}")
    with m4:
        st.metric("📘 Facebook", f"{wa_stats['by_type']['fb']:,}")

    # Deduplication Queue: Gather unscanned/unbroadcasted items from current timeframe
    pending_queue = []
    for item in filtered_articles:
        if not is_item_broadcasted(item, "article"):
            pending_queue.append({"item": item, "type": "article", "source_type": "Nepali Media"})
    for item in filtered_indian:
        if not is_item_broadcasted(item, "article"):
            pending_queue.append({"item": item, "type": "article", "source_type": "Indian Press"})
    for item in filtered_x_posts:
        if not is_item_broadcasted(item, "x"):
            pending_queue.append({"item": item, "type": "x", "source_type": "X (Twitter)"})
    for item in filtered_fb_posts:
        if not is_item_broadcasted(item, "fb"):
            pending_queue.append({"item": item, "type": "fb", "source_type": "Facebook"})

    # Webhook & Automation Status Bar
    wh_url = get_env_variable("WHATSAPP_WEBHOOK_URL")
    _, green_id, _ = get_green_api_credentials()
    green_state, green_qr = get_green_api_status() if green_id else ("notConfigured", "")

    st.markdown("""
    <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:10px; padding:12px 16px; margin: 12px 0 14px 0;">
        <span style="font-size:0.75rem; font-weight:700; color:#475569; text-transform:uppercase; letter-spacing:0.04em;">AUTOMATION DISPATCH ENGINE</span>
        <div style="font-size:0.92rem; font-weight:600; color:#0F172A; margin-top:2px;">
    """ + (
        f"🟢 Webhook Dispatcher Connected & Ready · <code style='font-size:0.8rem; background:#E2E8F0; padding:2px 6px; border-radius:4px;'>{wh_url[:28]}...{wh_url[-10:] if len(wh_url)>38 else ''}</code>"
        if wh_url else
        "⚪ 1-Click Broadcast Mode Active · <span style='font-weight:400; color:#64748B;'>Set <code>WHATSAPP_WEBHOOK_URL</code> in <code>.env</code> for 100% automated background posting</span>"
    ) + f"""
        </div>
        <div style="font-size:0.82rem; color:{'#166534' if green_state == 'authorized' else '#B45309'}; margin-top:4px;">
            {'🟢 GREEN-API Instance Connected & Authorized' if green_state == 'authorized' else f'🟡 GREEN-API Instance {green_id}: {green_state} (Needs QR Scan below)' if green_id else '⚪ GREEN-API not configured'}
        </div>
    </div>
    """, unsafe_allow_html=True)

    if green_id and green_state != "authorized" and green_qr:
        with st.expander("📲 Scan QR Code to Authorize Green-API WhatsApp Instance", expanded=True):
            qr_c1, qr_c2 = st.columns([1.5, 3])
            with qr_c1:
                try:
                    import base64
                    st.image(base64.b64decode(green_qr), caption="Scan with WhatsApp (Linked Devices)", width=200)
                except Exception:
                    st.caption("QR Code rendering unavailable.")
            with qr_c2:
                st.markdown("""
                **Quick 5-Second Setup:**
                1. Open **WhatsApp** on your mobile phone.
                2. Tap **Settings** (or 3 dots on Android) > **Linked Devices**.
                3. Tap **Link a Device** and point your camera at this QR code.
                4. Once scanned, your instance status will instantly change to **Authorized**!
                """)
                if st.button("🔄 Refresh Status After Scanning", key="btn_refresh_green_status"):
                    st.rerun()

    wb_col1, wb_col2, wb_col3 = st.columns([2, 2.5, 3.5])
    with wb_col1:
        if st.button("🧪 Test Webhook Ping", key="btn_wa_ping_webhook", disabled=not bool(wh_url)):
            with st.spinner("Pinging webhook endpoint..."):
                ok, msg = send_test_webhook_ping(wh_url)
                if ok:
                    st.success(f"✅ Webhook ping successful! ({msg})")
                else:
                    st.error(f"❌ Webhook ping failed: {msg}")
    with wb_col2:
        if st.button("⚡ Dispatch Top 5 Unsent via Webhook", key="btn_wa_dispatch_webhook", disabled=not bool(wh_url)):
            if not pending_queue:
                st.info("No unsent items in pending queue.")
            else:
                success_count = 0
                for q_item in pending_queue[:5]:
                    ok, _ = dispatch_item_to_webhook(q_item["item"], q_item["type"], wh_url)
                    if ok:
                        mark_item_broadcasted(q_item["item"], q_item["type"])
                        success_count += 1
                        time.sleep(0.5)
                st.success(f"✅ Dispatched {success_count} item(s) to webhook successfully.")
                st.rerun()
    with wb_col3:
        with st.expander("📘 How to connect free Webhook (Make.com / n8n)", expanded=False):
            st.markdown("""
            **100% Free Webhook Setup:**
            1. **Make.com (Free 1,000 runs/mo)**:
               - Create a scenario with trigger **Webhooks > Custom webhook**.
               - Copy the generated Webhook URL.
            2. **Configure your project**:
               - Add `WHATSAPP_WEBHOOK_URL=https://hook.make.com/...` in your `.env` or `.streamlit/secrets.toml`.
            3. **Done!** Every new scanned news, X tweet, and FB update will be automatically dispatched.
            """)

    # Direct Green-API Broadcast Gateway Controls
    if green_id:
        with st.container():
            st.markdown("##### 🚀 Direct Green-API Broadcast (Bypasses Make.com completely)")
            g_c1, g_c2, g_c3 = st.columns([3, 2, 2.5])
            with g_c1:
                default_target = get_env_variable("GREEN_API_CHAT_ID", "")
                green_target_input = st.text_input(
                    "WhatsApp Recipient (Phone / Group / Channel):",
                    value=default_target,
                    placeholder="e.g. 9779812345678@c.us",
                    key="input_green_target_chat"
                )
            with g_c2:
                st.write("")
                st.write("")
                if st.button("🧪 Send Test WhatsApp Message", key="btn_green_test_msg", disabled=(green_state != "authorized" or not green_target_input.strip())):
                    with st.spinner("Sending test message via Green-API..."):
                        ok, res = send_test_green_api_message(green_target_input.strip())
                        if ok:
                            st.success(f"✅ WhatsApp message delivered! (Message ID: {res})")
                        else:
                            st.error(f"❌ Failed to send: {res}")
            with g_c3:
                st.write("")
                st.write("")
                if st.button("⚡ Dispatch Top 5 via Green-API", key="btn_green_dispatch_top5", disabled=(green_state != "authorized" or not green_target_input.strip())):
                    if not pending_queue:
                        st.info("No unsent items in pending queue.")
                    else:
                        g_success = 0
                        for q_item in pending_queue[:5]:
                            ok, _ = dispatch_item_to_green_api(q_item["item"], q_item["type"], green_target_input.strip())
                            if ok:
                                mark_item_broadcasted(q_item["item"], q_item["type"])
                                g_success += 1
                                time.sleep(1)
                        st.success(f"✅ Delivered {g_success} story updates directly to WhatsApp!")
                        st.rerun()

    q_col1, q_col2 = st.columns([3, 1.2])
    with q_col1:
        st.markdown(f"##### 📥 Pending Broadcast Queue (`{len(pending_queue)}` unsent items in timeframe)")
    with q_col2:
        queue_filter = st.selectbox(
            "Filter Queue Source:",
            ["All Sources", "Nepali Media", "Indian Press", "X (Twitter)", "Facebook"],
            key="wa_queue_source_filter"
        )

    if queue_filter != "All Sources":
        display_queue = [q for q in pending_queue if q["source_type"] == queue_filter]
    else:
        display_queue = pending_queue

    if display_queue:
        # Batch Actions Bar
        b_c1, b_c2, b_c3 = st.columns([2, 2, 2])
        with b_c1:
            st.caption(f"Displaying top **{min(15, len(display_queue))}** of {len(display_queue)} pending items")
        with b_c2:
            if st.button("⚡ Mark Top 10 as Broadcasted", key="btn_wa_mark_top10"):
                for q_entry in display_queue[:10]:
                    mark_item_broadcasted(q_entry["item"], q_entry["type"])
                st.success("✅ Top 10 items marked as sent in deduplication cache.")
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
    with st.expander("📜 Recent Broadcast History (Last 15 Dispatched Updates)", expanded=False):
        if wa_stats["recent_history"]:
            for h in wa_stats["recent_history"]:
                hc1, hc2, hc3 = st.columns([4, 1.5, 1])
                with hc1:
                    st.markdown(f"**{html.escape(h.get('title', ''))}**\n\n_{html.escape(h.get('source', ''))}_ · `{h.get('type')}`")
                with hc2:
                    st.caption(f"Sent: {h.get('sent_at', '')[:16]}")
                with hc3:
                    if st.button("↺ Re-queue", key=f"btn_requeue_{h.get('key')}"):
                        unmark_item_broadcasted({"link": h.get("link"), "title": h.get("title")}, h.get("type", "article"))
                        st.rerun()
        else:
            st.caption("No broadcast history recorded yet.")
