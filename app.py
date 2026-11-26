"""
app.py
Interactive Nepal Social Media, Nepali Media Portals, and Nepal in Indian Media Monitor.
Includes:
- Date and Time Picker Filter (From selected timestamp up to current moment in NPT)
- 8 Structured Classification Categories
- Top Nepali and English News Portals
- Dedicated Nepal in Indian Media Menu
- Live X (Twitter) Feeds
- CSV / Excel Export with Timestamps and Categories
"""

import streamlit as st
import datetime
import hashlib
import hmac
import json
import time
import urllib.parse
import html
import re
import os
import concurrent.futures
from typing import Any, Callable, Dict, List, Optional, Tuple

from apple_theme import AUTH_CSS, theme_override_css


def load_env():
    if os.environ.get("_NMM_ENV_LOADED") == "1":
        return
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip("'\""))
    os.environ["_NMM_ENV_LOADED"] = "1"


load_env()

from nepal_config import is_background_daemon_disabled


# Daemon hot-reloading is disabled in production to guarantee fast reruns and zero thread churn.
# Set DEV_HOT_RELOAD=1 in development environments if submodule reloads are explicitly desired.
if os.getenv("DEV_HOT_RELOAD") == "1":
    def _ensure_reloaded_daemon_on_code_update() -> None:
        """Automatically stops stale @st.cache_resource daemon threads and reloads submodules on hot git deploys."""
        if is_background_daemon_disabled():
            return
        import sys
        import importlib

        target_ver = "2026-11-20-v8"
        old_sched = sys.modules.get("nepal_news_scheduler")
        if old_sched is not None and getattr(old_sched, "_DAEMON_CODE_VERSION", None) != target_ver:
            try:
                old_stop = getattr(old_sched, "_STOP_EVENT", None)
                if old_stop is not None and hasattr(old_stop, "set"):
                    old_stop.set()
                old_start = getattr(old_sched, "start_monitoring_daemon", None)
                if old_start is not None and hasattr(old_start, "clear"):
                    old_start.clear()
                for mod_name in (
                    "nepal_config",
                    "nepal_verified_x_directory",
                    "nepal_news_store",
                    "nepal_summarizer",
                    "nepal_fetcher",
                    "nepal_x_scanner",
                    "nepal_news_scheduler",
                ):
                    mod = sys.modules.get(mod_name)
                    if mod is not None:
                        importlib.reload(mod)
                new_sched = sys.modules.get("nepal_news_scheduler")
                if new_sched is not None and hasattr(new_sched, "start_monitoring_daemon"):
                    new_sched.start_monitoring_daemon()
            except Exception:
                pass

    _ensure_reloaded_daemon_on_code_update()

# 1. Page Configuration
_PAGE_ICON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "icon-192.png")
st.set_page_config(
    page_title="Monitor & Analytics",
    page_icon=_PAGE_ICON if os.path.exists(_PAGE_ICON) else "📰",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown(
    """<style>
    [data-testid='stSidebar'], [data-testid='stSidebarCollapsedControl'] { display: none !important; }
    .block-container { max-width: 960px !important; padding-top: 1.25rem !important; margin: 0 auto !important; }
    </style>""",
    unsafe_allow_html=True,
)

# ==========================================
# AUTHENTICATION GATEWAY (PASSWORD PROTECTION)
# ==========================================
def _get_app_password() -> str:
    if "APP_PASSWORD" in os.environ:
        val = (os.environ.get("APP_PASSWORD") or "").strip()
        if val or os.environ.get("APP_PASSWORD") == "":
            return val
    try:
        if hasattr(st, "secrets") and "APP_PASSWORD" in st.secrets:
            s_val = str(st.secrets.get("APP_PASSWORD", "")).strip()
            if s_val:
                return s_val
    except Exception:
        pass
    try:
        from nepal_news_store import _load_local_config_fast
        cfg_val = (_load_local_config_fast().get("APP_PASSWORD") or "").strip()
        if cfg_val:
            return cfg_val
    except Exception:
        pass
    return ""

APP_PASSWORD = _get_app_password()


_THEME_MODE = st.query_params.get("theme", "auto")
if _THEME_MODE not in ("auto", "light", "dark"):
    _THEME_MODE = "auto"


@st.cache_data(ttl=300, show_spinner=False)
def _source_counts() -> Tuple[int, int, int]:
    """Live source counts: Nepali portals and Indian outlets from configured lists, social media from the database/directory."""
    from nepal_config import TOP_NEPAL_NEWS_PORTALS as _np, TOP_INDIAN_MEDIA_SOURCES as _ind
    x_n = 0
    try:
        from nepal_news_store import count_enabled_x_accounts
        x_n = count_enabled_x_accounts()
    except Exception:
        x_n = 0
    if x_n <= 0:
        try:
            from nepal_social_directory import VERIFIED_NEPAL_SOCIAL_DIRECTORY as _x
            x_n = len(_x)
        except Exception:
            try:
                from nepal_verified_x_directory import VERIFIED_NEPAL_X_DIRECTORY as _x
                x_n = len(_x)
            except Exception:
                x_n = 0
    return len(_np), len(_ind), x_n


def _auth_stats_html() -> str:
    """Live source coverage rows in the login left pane."""
    try:
        n1, n2, n3 = _source_counts()
    except Exception:
        return ""
    return (
        '<div class="auth-coverage">'
        f'<div class="auth-cov-row"><span class="auth-cov-label">🇳🇵 Nepali Press</span><span class="auth-cov-val">{n1} portals</span></div>'
        f'<div class="auth-cov-row"><span class="auth-cov-label">🇮🇳 Indian Press</span><span class="auth-cov-val">{n2} outlets</span></div>'
        f'<div class="auth-cov-row"><span class="auth-cov-label">💬 Social Media</span><span class="auth-cov-val">{n3:,} voices</span></div>'
        '</div>'
    )


def check_password() -> bool:
    """Returns True if the user entered the correct password or has a persisted session cookie/token."""
    if st.session_state.get("authenticated", False):
        return True

    app_pwd = _get_app_password()
    if not app_pwd:
        st.markdown(AUTH_CSS + theme_override_css(_THEME_MODE), unsafe_allow_html=True)
        st.error(
            "⚠️ **Authentication Configuration Error**: `APP_PASSWORD` is not configured in the environment "
            "or Streamlit secrets. Administrative access is locked to protect intelligence feeds."
        )
        st.stop()

    query_key = st.query_params.get("key", "")
    if query_key and hmac.compare_digest(query_key, app_pwd):
        st.session_state["authenticated"] = True
        return True

    auth_slot = st.empty()
    with auth_slot.container():
        st.markdown(AUTH_CSS + theme_override_css(_THEME_MODE), unsafe_allow_html=True)
        with st.form("auth_form", clear_on_submit=False):
            c_left, c_right = st.columns([1.08, 1], gap=None)
            with c_left:
                st.markdown(f"""
                <div class="auth-split-left">
                    <div class="auth-split-top">
                        <div class="auth-live-pill"><span class="auth-live-dot"></span> LIVE MONITORING · NPT</div>
                        <div class="auth-header__title">Monitor &amp; Analytics</div>
                        <div class="auth-header__subtitle">Unified intelligence across Nepali newsrooms, Indian press, and verified social voices.</div>
                    </div>
                    {_auth_stats_html()}
                </div>
                """, unsafe_allow_html=True)
            with c_right:
                st.markdown("""
                <div class="auth-split-right-head">
                    <div class="auth-header__icon-ring">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg">
                            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
                        </svg>
                    </div>
                    <div class="auth-right-title">Workspace Access</div>
                    <div class="auth-right-sub">Enter passcode to continue</div>
                </div>
                """, unsafe_allow_html=True)
                pwd = st.text_input("Password", type="password", placeholder="Enter password", label_visibility="collapsed")
                submit = st.form_submit_button("Unlock Workspace", icon=":material/arrow_forward:", width="stretch", type="primary")
                st.markdown(
                    '<div class="auth-footer">'
                    '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                    'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
                    '<rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>'
                    '<path d="M7 11V7a5 5 0 0 1 10 0v4"/>'
                    '</svg>'
                    'Secure access · Authorised users only'
                    '</div>',
                    unsafe_allow_html=True,
                )

        if submit:
            if pwd and hmac.compare_digest(pwd.strip(), app_pwd):
                st.session_state["authenticated"] = True
                auth_slot.empty()
                return True
            else:
                st.error("Incorrect password. Please try again.")

    st.stop()


check_password()

# Deferred UI & fast DB store imports (scrapers/translators/GreenAPI stay lazy-loaded until needed)
import streamlit.components.v1 as components
from apple_theme import APPLE_DESIGN_SYSTEM_CSS, FEED_CARD_CSS

st.markdown(APPLE_DESIGN_SYSTEM_CSS + theme_override_css(_THEME_MODE), unsafe_allow_html=True)

# Home-screen install hints: icon, full-screen mode and status-bar colour (injected into the parent page head)
components.html(
    """<script>(function(){try{
var d=window.parent.document,h=d.head,m="__MODE__";
function put(tag,attrs){var id="nmm-"+tag+"-"+(attrs.name||attrs.rel||"x")+(attrs.media?"-"+attrs.media.replace(/[^a-z0-9]/gi,""):"");
var e=d.getElementById(id);if(e)e.remove();e=d.createElement(tag);e.id=id;for(var k in attrs)e.setAttribute(k,attrs[k]);h.appendChild(e);}
put("link",{rel:"apple-touch-icon",href:"/app/static/apple-touch-icon.png"});
put("link",{rel:"manifest",href:"/app/static/manifest.json"});
put("meta",{name:"apple-mobile-web-app-capable",content:"yes"});
put("meta",{name:"mobile-web-app-capable",content:"yes"});
put("meta",{name:"apple-mobile-web-app-title",content:"Monitor & Analytics"});
put("meta",{name:"apple-mobile-web-app-status-bar-style",content:"default"});
d.querySelectorAll('meta[name="theme-color"]').forEach(function(x){if(x.id.indexOf("nmm-")===0)x.remove();});
if(m==="dark"){put("meta",{name:"theme-color",content:"#000000"});}
else if(m==="light"){put("meta",{name:"theme-color",content:"#F5F5F7"});}
else{var a=d.createElement("meta");a.id="nmm-meta-theme-color-l";a.name="theme-color";a.content="#F5F5F7";a.media="(prefers-color-scheme: light)";h.appendChild(a);
var b=d.createElement("meta");b.id="nmm-meta-theme-color-d";b.name="theme-color";b.content="#000000";b.media="(prefers-color-scheme: dark)";h.appendChild(b);}
}catch(e){}})();</script>""".replace("__MODE__", _THEME_MODE),
    height=0,
)

_ICON_PATHS = {
    "search": '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "bolt": '<path d="M13 2 3 14h9l-1 8 10-12h-9z"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
    "news": '<path d="M5 4h11a1 1 0 0 1 1 1v15H6a2 2 0 0 1-2-2V5a1 1 0 0 1 1-1z"/><path d="M17 9h3v9a2 2 0 0 1-2 2M8 8h6M8 12h6M8 16h3"/>',
    "rss": '<path d="M4 11a9 9 0 0 1 9 9M4 4a16 16 0 0 1 16 16"/><circle cx="5" cy="19" r="1"/>',
    "list": '<path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4.5" cy="6" r="1"/><circle cx="4.5" cy="12" r="1"/><circle cx="4.5" cy="18" r="1"/>',
    "chart": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "alert": '<path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>',
    "tag": '<path d="M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8z"/><circle cx="7.5" cy="7.5" r="1"/>',
}
_WA_SVG = (
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/></svg>'
)
_EMOJI_TO_ICON = {"📰": "news", "🌐": "globe", "🔍": "search", "📊": "chart", "📋": "list", "🕒": "clock", "⚡": "bolt", "📡": "rss"}


def _ico(name: str, size: int = 13) -> str:
    path = _ICON_PATHS.get(name, "")
    return (
        f'<svg class="ico" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{path}</svg>'
    )

from nepal_config import (
    NEPAL_TZ,
    DEFAULT_NEPAL_RELEVANCE_THRESHOLD,
    BORDERLINE_NEPAL_RELEVANCE_FLOOR,
    STRUCTURED_CATEGORIES,
    CATEGORY_ICONS,
    TOP_NEPAL_NEWS_PORTALS,
    TOP_INDIAN_MEDIA_SOURCES,
    ENGLISH_NEPAL_PORTAL_NAMES,
    _has_devanagari,
    parse_to_nepal_time,
)
try:
    from nepal_social_directory import (
        CANONICAL_SOCIAL_CATEGORIES as CANONICAL_X_CATEGORIES,
        VERIFIED_NEPAL_SOCIAL_DIRECTORY,
        VERIFIED_NEPAL_SOCIAL_DIRECTORY as VERIFIED_NEPAL_X_DIRECTORY,
    )
except Exception:
    from nepal_verified_x_directory import CANONICAL_X_CATEGORIES, VERIFIED_NEPAL_X_DIRECTORY
    VERIFIED_NEPAL_SOCIAL_DIRECTORY = VERIFIED_NEPAL_X_DIRECTORY
from nepal_news_store import (
    register_portal_sources,
    get_all_source_health,
    get_all_indian_source_health,
    get_system_kpis,
    get_system_health_bundle,
    get_db_transport_info,
    is_portal_stale,
    set_source_enabled,
    set_source_interval,
    get_stored_articles,
    get_stored_indian_articles,
    get_stored_counts_by_stream,
    get_indian_media_audit_stats,
    get_indian_borderline_bundle,
    get_login_bootstrap_bundle,
    get_indian_workspace_bootstrap,
    get_x_workspace_bootstrap,
    batch_upsert_x_accounts,
    get_all_x_accounts,
    get_x_account_kpis,
    set_x_account_enabled,
    upsert_single_x_account,
    promote_pending_x_account,
    delete_x_account,
    verify_x_profile_connectivity,
    normalize_x_handle,
    save_x_posts,
    get_stored_x_posts,
    get_stored_live_feed_page,
    get_filtered_feed_count,
    get_feed_page_with_count,
    get_dashboard_header_state,
    fetch_analytics_export_bundle,
    SEARCH_EXPANSIONS,
    expand_search_tokens,
    CATEGORY_ALIASES,
    PREDEFINED_9_CATEGORIES,
    CORE_8_CATEGORIES,
    record_whatsapp_sent,
    get_whatsapp_sent_map,
)
from components.infinite_feed import render_infinite_feed_component
from media_logos import get_source_logo_html, get_x_author_avatar_html, resolve_media_domain
from nepal_news_scheduler import (
    start_monitoring_daemon,
    trigger_manual_sync_async,
    get_manual_sync_status,
)

# Start background news monitoring daemon only if not disabled for split deployment
if not is_background_daemon_disabled():
    try:
        start_monitoring_daemon()
    except Exception:
        pass

# 3. Time Reference (single session-pinned timeframe clock shared strictly across sidebar, header, feeds, and export)
_wall_now_npt = datetime.datetime.now(NEPAL_TZ)
st.session_state.setdefault("last_sync_npt", _wall_now_npt.strftime("%I:%M %p").lstrip("0"))
st.session_state.setdefault("auto_sync_enabled", True)
st.session_state.setdefault("cp_timeframe_segment", "12h")
st.session_state.setdefault("tf_epoch", 1)
st.session_state.setdefault("stream_versions", {"nepali": 0, "indian": 0, "x": 0})
_tf_anchor_state = st.session_state.get("_tf_anchor_state")
_cur_tf_ep_top = int(st.session_state.get("tf_epoch", 1))
_cur_dv_top = int(st.session_state.get("data_version", 0))
if (
    not isinstance(_tf_anchor_state, dict)
    or not isinstance(_tf_anchor_state.get("dt"), datetime.datetime)
    or int(_tf_anchor_state.get("epoch", -1)) != _cur_tf_ep_top
    or int(_tf_anchor_state.get("data_ver", -1)) != _cur_dv_top
    or (time.time() - float(_tf_anchor_state.get("ts") or 0.0)) >= 60.0
):
    _tf_anchor_state = {
        "epoch": _cur_tf_ep_top,
        "data_ver": _cur_dv_top,
        "ts": time.time(),
        "dt": _wall_now_npt,
    }
    st.session_state["_tf_anchor_state"] = _tf_anchor_state
actual_now_npt = _tf_anchor_state["dt"]
now_npt = actual_now_npt.replace(minute=(actual_now_npt.minute // 3) * 3, second=0, microsecond=0)
formatted_now_time = actual_now_npt.strftime("%I:%M %p NPT").lstrip("0")
past_12h_ref = actual_now_npt - datetime.timedelta(hours=12)
default_start_date = past_12h_ref.date()
default_start_time = past_12h_ref.time().replace(second=0, microsecond=0)

# ==========================================
# 4. TIME WINDOW
# Presets (2h / 6h / 12h / 24h / Today) always run up to "now".
# "Custom" exposes start/end pickers plus an "Up to now" toggle.
# ==========================================
TIMEFRAME_PRESETS = ["2h", "6h", "12h", "24h", "Today", "Custom"]
QUICK_TIME_PRESETS = ["6h", "12h", "24h", "Today"]
PAGE_SIZE = 20

def _preset_start(preset: str, ref: datetime.datetime) -> datetime.datetime:
    if preset == "2h":
        return ref - datetime.timedelta(hours=2)
    if preset == "6h":
        return ref - datetime.timedelta(hours=6)
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
    now_curr = datetime.datetime.now(NEPAL_TZ)
    if preset != "Custom":
        start = _preset_start(preset, now_curr)
        st.session_state["filter_start_date"] = start.date()
        st.session_state["filter_start_time"] = start.time().replace(second=0, microsecond=0)
    new_ep = int(st.session_state.get("tf_epoch", 1)) + 1
    st.session_state["tf_epoch"] = new_ep
    st.session_state["_tf_anchor_state"] = {
        "epoch": new_ep,
        "data_ver": int(st.session_state.get("data_version", 0)),
        "ts": time.time(),
        "dt": now_curr,
    }
    st.session_state.pop("_hdr_state_cache", None)
    st.session_state["_pending_tf_rerun"] = True

active_preset = st.session_state.get("cp_timeframe_segment") or "12h"
if active_preset == "Custom":
    st.session_state.setdefault("filter_start_date", default_start_date)
    st.session_state.setdefault("filter_start_time", default_start_time)
    st.session_state.setdefault("filter_use_current_time", True)
    filter_start_dt = datetime.datetime.combine(
        st.session_state.get("filter_start_date", default_start_date),
        st.session_state.get("filter_start_time", default_start_time),
        tzinfo=NEPAL_TZ,
    )
    is_to_current = bool(st.session_state.get("filter_use_current_time", True))
else:
    filter_start_dt = _preset_start(active_preset, actual_now_npt)
    is_to_current = True

if is_to_current:
    filter_end_dt = actual_now_npt
else:
    st.session_state.setdefault("filter_end_date", actual_now_npt.date())
    st.session_state.setdefault("filter_end_time", actual_now_npt.time().replace(second=0, microsecond=0))
    filter_end_dt = datetime.datetime.combine(
        st.session_state.get("filter_end_date", actual_now_npt.date()),
        st.session_state.get("filter_end_time", actual_now_npt.time().replace(second=0, microsecond=0)),
        tzinfo=NEPAL_TZ,
    )
    if filter_end_dt < filter_start_dt:
        filter_end_dt = filter_start_dt + datetime.timedelta(hours=1)
cache_start_dt = filter_start_dt
cache_end_dt = filter_end_dt

if active_preset == "Custom":
    _custom_key = (
        str(st.session_state.get("filter_start_date", "")),
        str(st.session_state.get("filter_start_time", "")),
        bool(is_to_current),
        "" if is_to_current else str(st.session_state.get("filter_end_date", "")),
        "" if is_to_current else str(st.session_state.get("filter_end_time", "")),
    )
    if st.session_state.get("_prev_custom_tf") != _custom_key:
        if "_prev_custom_tf" in st.session_state:
            st.session_state["tf_epoch"] = int(st.session_state.get("tf_epoch", 1)) + 1
            st.session_state.pop("_hdr_state_cache", None)
        st.session_state["_prev_custom_tf"] = _custom_key

_tf_epoch = int(st.session_state.get("tf_epoch", 1))


def _tf_state_sig() -> Tuple[Any, ...]:
    p = st.session_state.get("cp_timeframe_segment") or "12h"
    ep = int(st.session_state.get("tf_epoch", 1))
    if p != "Custom":
        return (p, ep)
    use_now = bool(st.session_state.get("filter_use_current_time", True))
    return (
        p,
        ep,
        str(st.session_state.get("filter_start_date", default_start_date)),
        str(st.session_state.get("filter_start_time", default_start_time)),
        use_now,
        "" if use_now else str(st.session_state.get("filter_end_date", actual_now_npt.date())),
        "" if use_now else str(st.session_state.get("filter_end_time", actual_now_npt.time().replace(second=0, microsecond=0))),
    )


_TOP_LEVEL_TF_SIG = _tf_state_sig()
_stream_vers = st.session_state.get("stream_versions", {"nepali": 0, "indian": 0, "x": 0})
_v_np = int(_stream_vers.get("nepali", 0))
_v_in = int(_stream_vers.get("indian", 0))
_v_x = int(_stream_vers.get("x", 0))
_v_live = _v_np + _v_in + _v_x

def fmt_short(dt: datetime.datetime) -> str:
    return dt.strftime("%d %b, %I:%M %p").lstrip("0")

window_label = f"{fmt_short(filter_start_dt)} → {'Now' if is_to_current else fmt_short(filter_end_dt)}"

# Filter option constants (single source of truth)
CAT_FILTER_ALL_UNFILTERED = "🌐 All Topics"
CAT_FILTER_ALL_8 = "📂 Classified Only"
CAT_FILTER_UNCATEGORIZED = "⚪ Unclassified Only"
CATEGORY_FILTER_OPTIONS = (
    [CAT_FILTER_ALL_UNFILTERED]
    + [f"{CATEGORY_ICONS.get(c, '📌')} {c}" for c in STRUCTURED_CATEGORIES]
    + [CAT_FILTER_ALL_8, CAT_FILTER_UNCATEGORIZED]
)

ALL_PORTALS_DEFAULT = f"All Portals ({len(TOP_NEPAL_NEWS_PORTALS)})"
ALL_INDIAN_DEFAULT = f"All {len(TOP_INDIAN_MEDIA_SOURCES)} Indian Outlets"
ALL_LANG_DEFAULT = "All Languages"
ALL_ACC_TYPES = "All Account Types"
NEPALI_PORTAL_NAMES = sorted({p["name"] for p in TOP_NEPAL_NEWS_PORTALS})
INDIAN_OUTLET_NAMES = sorted({s["name"] for s in TOP_INDIAN_MEDIA_SOURCES})
india_rel_threshold = DEFAULT_NEPAL_RELEVANCE_THRESHOLD

def reset_all_filters():
    now_curr = datetime.datetime.now(NEPAL_TZ)
    start = _preset_start("12h", now_curr)
    new_ep = int(st.session_state.get("tf_epoch", 1)) + 1
    st.session_state.update({
        "global_search_input": "",
        "committed_search_query": "",
        "np_cat_filter": CAT_FILTER_ALL_UNFILTERED,
        "np_portal_filter": ALL_PORTALS_DEFAULT,
        "np_lang_filter": ALL_LANG_DEFAULT,
        "in_outlet_filter": ALL_INDIAN_DEFAULT,
        "in_lang_filter": ALL_LANG_DEFAULT,
        "x_cat_filter_select": CAT_FILTER_ALL_UNFILTERED,
        "x_acc_type_select": ALL_ACC_TYPES,
        "x_sort_mode_select": "Newest",
        "comb_stream_key": "All",
        "comb_cat_filter": CAT_FILTER_ALL_UNFILTERED,
        "comb_sort_mode": "Newest First",
        "cp_timeframe_segment": "12h",
        "filter_start_date": start.date(),
        "filter_start_time": start.time().replace(second=0, microsecond=0),
        "filter_use_current_time": True,
        "media_visible_count": PAGE_SIZE,
        "indian_visible_count": PAGE_SIZE,
        "x_visible_count": PAGE_SIZE,
        "combined_visible_count": PAGE_SIZE,
        "np_fetch_limit": 500,
        "in_fetch_limit": 500,
        "x_fetch_limit": 500,
        "tf_epoch": new_ep,
        "_tf_anchor_state": {
            "epoch": new_ep,
            "data_ver": int(st.session_state.get("data_version", 0)),
            "ts": time.time(),
            "dt": now_curr,
        },
        "_pending_tf_rerun": True,
    })
    st.session_state.pop("_hdr_state_cache", None)
    st.session_state.pop("feed_sessions", None)


def _clear_workspace_filters(defaults: Dict[str, Any], workspace_key: str) -> None:
    """Clears only the active workspace's contextual filters without touching timeframe or search."""
    for k, v in defaults.items():
        st.session_state[k] = v
    sessions = st.session_state.get("feed_sessions")
    if isinstance(sessions, dict):
        sessions.pop(workspace_key, None)


def _render_active_search_chip() -> None:
    """Renders the active search query pill below the header with a one-click clear button."""
    if not _active_sq:
        return
    _sq_c1, _sq_c2 = st.columns([5.0, 1.0], gap="small")
    with _sq_c1:
        st.markdown(
            f'<div style="padding:2px 0;"><span class="pill pill--tint">{_ico("search", 12)} {html.escape(_active_sq)}</span></div>',
            unsafe_allow_html=True,
        )
    with _sq_c2:
        if st.button("Clear search", icon=":material/close:", key="btn_clr_top_search", width="stretch"):
            st.session_state["committed_search_query"] = ""
            st.rerun()


def _render_active_filters_bar(active_labels: List[str], defaults: Dict[str, Any], workspace_key: str) -> None:
    """Shows active contextual filter pills and a one-click Clear button when non-default filters are applied."""
    _render_active_search_chip()
    if not active_labels:
        return
    pills_html = "".join(
        f'<span class="pill pill--tint" style="margin-right:6px;">{html.escape(lbl)}</span>'
        for lbl in active_labels
    )
    c1, c2 = st.columns([4.0, 1.5], gap="small")
    with c1:
        st.markdown(f'<div style="display:flex;align-items:center;flex-wrap:wrap;gap:6px;padding:6px 0;">{pills_html}</div>', unsafe_allow_html=True)
    with c2:
        st.button(
            "Clear",
            icon=":material/close:",
            key=f"btn_clr_ws_{workspace_key}",
            width="stretch",
            on_click=_clear_workspace_filters,
            args=(defaults, workspace_key),
        )

# 6. High-Performance Cached Data Pipeline (Lazy-loaded, feed-projected)
MIN_DATE = datetime.datetime(2020, 1, 1, tzinfo=NEPAL_TZ)

def in_window(item: Dict[str, Any], start_dt: datetime.datetime = None, end_dt: datetime.datetime = None) -> bool:
    pdt = item.get("published_dt")
    if not isinstance(pdt, datetime.datetime):
        return False
    pdt_npt = pdt.astimezone(NEPAL_TZ) if pdt.tzinfo else pdt.replace(tzinfo=NEPAL_TZ)
    s = start_dt if start_dt is not None else filter_start_dt
    e = end_dt if end_dt is not None else (datetime.datetime.now(NEPAL_TZ) if is_to_current else filter_end_dt)
    return s <= pdt_npt <= e

@st.cache_data(ttl=120, show_spinner=False)
def get_cached_header_bundle(start_dt: datetime.datetime, end_dt: datetime.datetime = None, data_version: int = 0) -> Dict[str, Any]:
    """Retrieves stream counts and WhatsApp sent map in ONE SQL round-trip."""
    eff_end = end_dt if end_dt is not None else datetime.datetime.now(NEPAL_TZ)
    try:
        return get_dashboard_header_state(start_dt=start_dt, end_dt=eff_end, include_wa_sent=True)
    except Exception:
        return {"counts": {"nepali_count": 0, "indian_count": 0, "x_count": 0}, "wa_sent_map": {}}


@st.cache_data(ttl=120, show_spinner=False)
def get_cached_login_bootstrap(
    start_iso: str,
    end_iso: str,
    live_start_iso: str,
    live_end_iso: str,
    live_stream: str,
    live_cat: str,
    live_sort: str,
    search_query: str,
    data_version: int = 0,
) -> Dict[str, Any]:
    """
    Executes cold-login header state (counts + WA sent map) AND initial Live Feed page + count
    in ONE single SQL CTE round-trip.
    """
    h_start = datetime.datetime.fromisoformat(start_iso)
    h_end = datetime.datetime.fromisoformat(end_iso) if end_iso else datetime.datetime.now(NEPAL_TZ)
    l_start = datetime.datetime.fromisoformat(live_start_iso) if live_start_iso else h_start
    l_end = datetime.datetime.fromisoformat(live_end_iso) if live_end_iso else h_end
    try:
        boot = get_login_bootstrap_bundle(
            header_start_dt=h_start,
            header_end_dt=h_end,
            live_start_dt=l_start,
            live_end_dt=l_end,
            stream_filter=live_stream,
            category_filter=live_cat,
            search_query=search_query,
            sort_asc=(live_sort == "Oldest First"),
            limit=PAGE_SIZE,
        )
        lp = boot.get("live_page") or {"rows": [], "total_count": 0}
        now_curr = datetime.datetime.now(NEPAL_TZ)
        for r in lp.get("rows", []):
            pdt = r.get("published_dt")
            if isinstance(pdt, datetime.datetime):
                _, r["relative_time"], r["exact_time"] = parse_to_nepal_time(pdt, now_curr)
        lp["rows"] = [r for r in lp.get("rows", []) if in_window(r, l_start, l_end)]
        lp["snapshot_start_dt"] = l_start
        lp["snapshot_end_dt"] = l_end
        lp["snapshot_ingested_at"] = l_end
        return {"header": boot.get("header"), "live_page": lp}
    except Exception:
        return {
            "header": {"counts": {"nepali_count": 0, "indian_count": 0, "x_count": 0}, "wa_sent_map": {}},
            "live_page": None,
        }


@st.cache_data(ttl=60, show_spinner=False)
def _get_cached_indian_source_health() -> List[Dict[str, Any]]:
    try:
        return get_all_indian_source_health() or []
    except Exception:
        return []


@st.cache_data(ttl=120, show_spinner=False)
def _get_cached_indian_workspace_bootstrap(
    start_iso: str,
    end_iso: str,
    snap_iso: str,
    source: str,
    language: str,
    search_query: str,
    threshold_val: float,
    data_version: int = 0,
) -> Dict[str, Any]:
    """Single SQL round-trip bootstrap for Indian Press workspace (page + count + audit + borderline)."""
    s_dt = datetime.datetime.fromisoformat(start_iso)
    e_dt = datetime.datetime.fromisoformat(end_iso) if end_iso else datetime.datetime.now(NEPAL_TZ)
    sn_dt = datetime.datetime.fromisoformat(snap_iso) if snap_iso else e_dt
    try:
        res = get_indian_workspace_bootstrap(
            start_dt=s_dt,
            end_dt=e_dt,
            snapshot_ingested_at=sn_dt,
            source=(None if not source or source == ALL_INDIAN_DEFAULT else source),
            language=(None if not language or language == ALL_LANG_DEFAULT else language),
            search_query=search_query or None,
            limit=PAGE_SIZE,
            relevance_threshold=threshold_val,
            borderline_floor=BORDERLINE_NEPAL_RELEVANCE_FLOOR,
            borderline_limit=15,
        )
        now_curr = datetime.datetime.now(NEPAL_TZ)
        cleaned = []
        for r in res.get("rows", []):
            pdt = r.get("published_dt")
            if isinstance(pdt, datetime.datetime):
                _, r["relative_time"], r["exact_time"] = parse_to_nepal_time(pdt, now_curr)
            if in_window(r, s_dt, e_dt):
                cleaned.append(r)
        for b in res.get("borderline_items", []):
            pdt = b.get("published_dt")
            if isinstance(pdt, datetime.datetime):
                _, b["relative_time"], b["exact_time"] = parse_to_nepal_time(pdt, now_curr)
        res["rows"] = cleaned
        res["snapshot_start_dt"] = s_dt
        res["snapshot_end_dt"] = e_dt
        res["snapshot_ingested_at"] = sn_dt
        return res
    except Exception:
        return {
            "rows": [],
            "total_count": 0,
            "audit": {"total": 0, "total_discovered": 0, "substantive": 0, "relevant": 0, "borderline_review": 0, "borderline": 0, "excluded": 0},
            "borderline_items": [],
        }


@st.cache_data(ttl=120, show_spinner=False)
def _get_cached_x_workspace_bootstrap(
    start_iso: str,
    end_iso: str,
    snap_iso: str,
    category_filter: str,
    author_type: str,
    search_query: str,
    sort_mode: str,
    platform: str = "All Platforms",
    data_version: int = 0,
) -> Dict[str, Any]:
    """Single SQL round-trip bootstrap for X workspace (KPIs + page + count)."""
    s_dt = datetime.datetime.fromisoformat(start_iso)
    e_dt = datetime.datetime.fromisoformat(end_iso) if end_iso else datetime.datetime.now(NEPAL_TZ)
    sn_dt = datetime.datetime.fromisoformat(snap_iso) if snap_iso else e_dt
    plat_val = None
    if platform and platform.lower() not in ("all", "all platforms"):
        plat_val = "facebook" if "facebook" in platform.lower() else "x"
    try:
        res = get_x_workspace_bootstrap(
            start_dt=s_dt,
            end_dt=e_dt,
            snapshot_ingested_at=sn_dt,
            category_filter=category_filter,
            author_type=author_type,
            search_query=search_query or None,
            sort_mode=sort_mode,
            limit=PAGE_SIZE,
            platform=plat_val,
        )
        now_curr = datetime.datetime.now(NEPAL_TZ)
        cleaned = []
        for r in res.get("rows", []):
            pdt = r.get("published_dt")
            if isinstance(pdt, datetime.datetime):
                _, r["relative_time"], r["exact_time"] = parse_to_nepal_time(pdt, now_curr)
            if in_window(r, s_dt, e_dt):
                cleaned.append(r)
        res["rows"] = cleaned
        res["snapshot_start_dt"] = s_dt
        res["snapshot_end_dt"] = e_dt
        res["snapshot_ingested_at"] = sn_dt
        return res
    except Exception:
        return {
            "kpis": {"total_discovered": 0, "total_verified": 0, "pending_verification": 0, "active_monitored": 0, "inactive_monitored": 0, "by_category": {}},
            "rows": [],
            "total_count": 0,
        }


def get_cached_stream_counts(start_dt: datetime.datetime, end_dt: datetime.datetime = None) -> Dict[str, int]:
    """Retrieves fast aggregated counts across streams via unified header bundle."""
    return get_cached_header_bundle(start_dt=start_dt, end_dt=end_dt, data_version=st.session_state.get("data_version", 0)).get("counts", {"nepali_count": 0, "indian_count": 0, "x_count": 0})


@st.cache_data(ttl=120, show_spinner=False)
def get_cached_analytics_bundle(start_iso: str, end_iso: str, limit: int = 500, data_version: int = 0) -> Dict[str, List[Dict[str, Any]]]:
    """Concurrently fetches Nepali, Indian, and X datasets for Analytics & Export."""
    s_dt = datetime.datetime.fromisoformat(start_iso) if start_iso else None
    e_dt = datetime.datetime.fromisoformat(end_iso) if end_iso else datetime.datetime.now(NEPAL_TZ)
    try:
        bundle = fetch_analytics_export_bundle(start_dt=s_dt, end_dt=e_dt, limit=int(limit))
    except Exception:
        bundle = {"nepali": [], "indian": [], "x": []}
    now_curr = datetime.datetime.now(NEPAL_TZ)
    for k in ("nepali", "indian"):
        cleaned = []
        for sa in bundle.get(k, []):
            pdt = sa.get("published_dt")
            if isinstance(pdt, datetime.datetime):
                _, sa["relative_time"], sa["exact_time"] = parse_to_nepal_time(pdt, now_curr)
            if in_window(sa, s_dt, e_dt):
                cleaned.append(sa)
        cleaned.sort(key=lambda x: x.get("published_dt") or MIN_DATE, reverse=True)
        bundle[k] = cleaned
    if s_dt is not None:
        bundle["x"] = [p for p in bundle.get("x", []) if in_window(p, s_dt, e_dt)]
    return bundle


@st.cache_data(ttl=180, show_spinner=False)
def get_active_nepal_articles(start_dt: datetime.datetime, end_dt: datetime.datetime = None, limit: int = 500) -> List[Dict[str, Any]]:
    """Loads Nepali media for the active window directly from Supabase with feed projection."""
    now_curr = datetime.datetime.now(NEPAL_TZ)
    eff_end = end_dt if end_dt is not None else now_curr
    try:
        stored = get_stored_articles(start_dt=start_dt, end_dt=eff_end, limit=int(limit), include_full_content=False)
    except Exception:
        stored = []
    for sa in stored:
        pdt = sa.get("published_dt")
        if isinstance(pdt, datetime.datetime):
            _, sa["relative_time"], sa["exact_time"] = parse_to_nepal_time(pdt, now_curr)
    stored = [sa for sa in stored if in_window(sa, start_dt, eff_end)]
    stored.sort(key=lambda x: x.get("published_dt") or MIN_DATE, reverse=True)
    return stored

@st.cache_data(ttl=180, show_spinner=False)
def get_active_indian_articles(start_dt: datetime.datetime, end_dt: datetime.datetime = None, limit: int = 500) -> List[Dict[str, Any]]:
    """Loads Indian press articles covering Nepal from Supabase strictly within the active timeframe window."""
    now_curr = datetime.datetime.now(NEPAL_TZ)
    eff_end = end_dt if end_dt is not None else now_curr
    try:
        stored = get_stored_indian_articles(
            status_filter="substantive",
            start_dt=start_dt,
            end_dt=eff_end,
            limit=int(limit),
            include_full_content=False,
        )
    except Exception:
        stored = []
    for sa in stored:
        pdt = sa.get("published_dt")
        if isinstance(pdt, datetime.datetime):
            _, sa["relative_time"], sa["exact_time"] = parse_to_nepal_time(pdt, now_curr)
    stored = [sa for sa in stored if in_window(sa, start_dt, eff_end)]
    stored.sort(key=lambda x: x.get("published_dt") or MIN_DATE, reverse=True)
    return stored

@st.cache_data(ttl=180, show_spinner=False)
def get_active_x_posts(start_dt: datetime.datetime = None, end_dt: datetime.datetime = None, limit: int = 500) -> List[Dict[str, Any]]:
    """Loads monitored X posts from Supabase store for the active timeframe window."""
    now_curr = datetime.datetime.now(NEPAL_TZ)
    eff_end = end_dt if end_dt is not None else now_curr
    try:
        posts = get_stored_x_posts(start_dt=start_dt, end_dt=eff_end, exclude_media_houses=True, limit=int(limit))
    except Exception:
        return []
    if start_dt is not None:
        posts = [p for p in posts if in_window(p, start_dt, eff_end)]
    return posts

# ==========================================
# CATEGORY TAXONOMY (imported from nepal_news_store + slug map for badges & accents)
# ==========================================
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
    return f'<span class="cat-badge cat-badge--{category_slug(cat)}"><span class="cat-ico">{icon}</span> {html.escape(cat)}</span>'

def compact_number(n: int) -> str:
    return f"{n / 1000:.1f}K" if n >= 1000 else str(n)

def _source_initials(name: str) -> str:
    parts = re.findall(r"[A-Za-z0-9\u0900-\u097F]+", name or "")
    if not parts:
        return "•"
    if len(parts) == 1:
        return parts[0][:2]
    return (parts[0][0] + parts[1][0])


_HL_ALERT_SVG = '<svg class="ico" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/></svg>'
_HL_CHECK_SVG = '<svg class="ico" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>'


def render_headline_card(item: Dict[str, Any], is_indian: bool = False, sent_title: str = "") -> str:
    """Headline-first card: one meta line, the headline, nothing else (actions live in the feed footer)."""
    source_name = (item.get("source") or "Unknown").strip()
    cat = item.get("primary_section") or item.get("structured_category", "Nepal – Others")
    raw_title = (item.get("title") or "").strip()
    headline_en = (item.get("headline_english") or "").strip()
    display_title = headline_en if (headline_en and not _has_devanagari(headline_en)) else raw_title
    raw_link = (item.get("link") or "").strip()
    link = html.escape(raw_link or "#", quote=True)
    rel = html.escape(str(item.get("relative_time") or "Recent"))
    exact = html.escape(str(item.get("exact_time") or ""), quote=True)

    chips = ""
    if is_indian:
        pct = int(round(float(item.get("nepal_relevance_score", 0.75)) * 100))
        reason = html.escape(str(item.get("relevance_reason", "Substantive Nepal connection")), quote=True)
        if item.get("relevance_status") == "borderline_review":
            chips += f'<span class="hl-chip hl-chip--warn" title="Borderline · Nepal relevance {pct}% · {reason}">{_HL_ALERT_SVG}{pct}%</span>'
        else:
            chips += f'<span class="hl-chip" title="Nepal relevance {pct}% · {reason}">{pct}%</span>'
    elif item.get("low_confidence"):
        chips += f'<span class="hl-chip hl-chip--warn" title="Needs review: classification confidence below 0.60">{_HL_ALERT_SVG}</span>'
    if sent_title:
        chips += f'<span class="hl-chip hl-chip--ok" title="{html.escape(sent_title, quote=True)}">{_HL_CHECK_SVG}</span>'
    else:
        chips += "<!--sent-->"

    logo_html = get_source_logo_html(source_name, link=raw_link, is_indian=is_indian)

    return (
        f'<article class="hl-card" title="{html.escape(str(cat), quote=True)}">'
        f'<header class="hl-meta">{logo_html}'
        f'<b class="hl-src">{html.escape(source_name)}</b><span class="hl-dot">·</span>'
        f'<time class="hl-time" title="{exact}">{rel}</time><span class="hl-sp"></span>{chips}</header>'
        f'<h3 class="hl-title"><a href="{link}" target="_blank" rel="noopener noreferrer">{html.escape(display_title)}</a></h3>'
        f'</article>'
    )


def time_badge_html(rel_time: str, exact_time: str) -> str:
    rel_time, exact_time = html.escape(str(rel_time or "")), html.escape(str(exact_time or ""))
    label = rel_time or exact_time or "Recent"
    title_attr = f' title="{exact_time}"' if exact_time else ""
    return f'<span class="time-badge"{title_attr}>{label}</span>'


# Article Card Renderer
def _render_article_tags_html(item: Dict[str, Any], is_indian: bool = False) -> str:
    sec_tags = list(item.get("secondary_tags") or [])
    if is_indian:
        sec_tags = [d for d in (item.get("nepal_dimensions") or []) if d not in sec_tags] + sec_tags
    if not sec_tags:
        return ""
    shown = sec_tags[:3]
    chips = "".join(f'<span class="sec-tag-chip">#{html.escape(str(t))}</span>' for t in shown)
    if len(shown) > 1:
        hidden = ", ".join(f"#{html.escape(str(t))}" for t in shown[1:])
        chips += f'<span class="sec-tag-chip sec-tag-more" title="{hidden}">+{len(shown) - 1}</span>'
    return f'<div class="chip-row">{chips}</div>'


def _translation_engine_badge_html(item: Dict[str, Any]) -> str:
    """Renders a subtle non-intrusive badge when an item was translated via Google Translate, IndicTrans2, or NLLB-200."""
    eng = str((item or {}).get("translation_engine") or "").strip()
    if not eng:
        return ""
    esc = html.escape(eng)
    return f'<span class="lang-label" title="Translated via {esc}">Translated via {esc}</span>'


def render_apple_article_card(item: Dict[str, Any], is_indian: bool = False, show_tags: bool = True) -> str:
    raw_source = (item.get("source") or "Unknown").strip()
    source_name = html.escape(raw_source)
    cat = item.get("primary_section") or item.get("structured_category", "Nepal – Others")
    raw_link = (item.get("link") or "").strip()

    if is_indian:
        accent = "indian-press"
        logo_html = get_source_logo_html(raw_source, link=raw_link, is_indian=True, extra_class="hl-av--tag")
        source_tag = f'<span class="indian-portal-tag">{logo_html}<span>🇮🇳 {source_name}</span></span>'
        pct = int(round(float(item.get("nepal_relevance_score", 0.75)) * 100))
        reason = html.escape(str(item.get("relevance_reason", "Substantive Nepal connection")))
        if item.get("relevance_status") == "borderline_review":
            review_flag = f'<span class="conf-review-badge" title="Nepal relevance {pct}% · {reason}">⚠ {pct}%</span>'
        else:
            review_flag = f'<span class="pill pill--success" title="Nepal relevance · {reason}">{pct}%</span>'
    else:
        accent = category_slug(cat)
        logo_html = get_source_logo_html(raw_source, link=raw_link, is_indian=False, extra_class="hl-av--tag")
        source_tag = f'<span class="portal-tag">{logo_html}<span>{source_name}</span></span>'
        review_flag = '<span class="conf-review-badge" title="Needs review — classification confidence below 0.60, pending editorial verification">⚠<span class="rv-word"> Review</span></span>' if item.get("low_confidence") else ""

    sec_tags_html = _render_article_tags_html(item, is_indian=is_indian) if show_tags else ""

    lang = item.get("language", "")
    lang_badge = f'<span class="lang-label">{html.escape(lang)}</span>' if lang else ""

    raw_title = (item.get("title") or "").strip()
    headline_en = (item.get("headline_english") or "").strip()
    summary = (item.get("summary") or "").strip()

    display_title = headline_en if (headline_en and not _has_devanagari(headline_en)) else raw_title
    native_title_html = (
        f'<div class="apple-card-native-title">{html.escape(raw_title)}</div>'
        if raw_title and display_title and raw_title != display_title
        else ""
    )

    if summary and summary != display_title and summary != raw_title:
        summary_html = f'<p class="apple-card-summary">{html.escape(summary)}</p>'
    else:
        summary_html = ""

    raw_link = (item.get("link") or "").strip()
    link = html.escape(raw_link or "#", quote=True)

    # PHASE 1: Add card type color stripe
    stripe_class = "feed-card-stripe--india" if is_indian else "feed-card-stripe--nepal"

    tr_badge_html = _translation_engine_badge_html(item)
    return (
        f'<div class="feed-card-inner">'
        f'<div class="feed-card-stripe {stripe_class}"></div>'
        f'<article class="apple-news-card accent--{accent}">'
        f'<header class="apple-card-meta">{source_tag}{get_badge_html(cat)}{review_flag}'
        f'{time_badge_html(item.get("relative_time", "Recent"), item.get("exact_time", ""))}{tr_badge_html}</header>'
        f'<h3 class="apple-card-title"><a href="{link}" target="_blank" rel="noopener noreferrer">{html.escape(display_title)}</a></h3>'
        f'{native_title_html}'
        f'{summary_html}{sec_tags_html}'
        f'</article>'
        f'</div>'
    )

def _render_x_metrics_html(p: Dict[str, Any]) -> str:
    sentiment = p.get("sentiment", "Neutral")
    if "Alert" in sentiment or "Critical" in sentiment:
        senti_class = "x-sentiment-alert"
    elif "Positive" in sentiment:
        senti_class = "x-sentiment-positive"
    else:
        senti_class = ""
    likes = int(p.get("likes", 0) or 0)
    retweets = int(p.get("retweets", 0) or 0)
    replies = int(p.get("replies", 0) or 0)
    if not p.get("is_real_api", True) and likes == 0 and retweets == 0 and replies == 0:
        metrics = '<span class="x-metric-item" title="Syndicated RSS post; engagement metrics unavailable">RSS / Metrics N/A</span>'
    else:
        metrics = "".join(
            f'<span class="x-metric-item" title="{label}">{icon} {compact_number(int(p.get(key, 0) or 0))}</span>'
            for key, icon, label in (("likes", "♥", "Likes"), ("retweets", "↻", "Reposts"), ("replies", "💬", "Replies"), ("impressions", "◉", "Views"))
        )
    return f'<div class="x-metrics-group">{metrics}<span class="x-sentiment-badge {senti_class}">{html.escape(sentiment)}</span></div>'


# X (Twitter) Post Card Renderer
def render_apple_x_post_card(p: Dict[str, Any], show_footer: bool = True, sent_title: str = "") -> str:
    author_name = html.escape(p.get("author_name", "Author"))
    handle = html.escape(p.get("handle", "@handle"))
    author_type = html.escape(p.get("author_type", "Public Figure"))
    verified_mark = ' <span class="x-verified-badge" title="Verified account">✓</span>' if p.get("verified") else ""

    plat = str(p.get("platform") or ("facebook" if "facebook.com" in str(p.get("link", "")).lower() else "x")).lower()
    stripe_cls = "feed-card-stripe--fb" if plat == "facebook" else "feed-card-stripe--x"
    plat_badge = (
        '<span style="background:#1877F2; color:#fff; font-size:0.65rem; font-weight:700; padding:1px 5px; border-radius:3px; margin-right:4px;">FB</span>'
        if plat == "facebook"
        else '<span style="background:#0f172a; color:#fff; font-size:0.65rem; font-weight:700; padding:1px 5px; border-radius:3px; margin-right:4px;">𝕏</span>'
    )

    text = html.escape(p.get("text", ""), quote=False)
    text = re.sub(r'(#[A-Za-z0-9_]+)', r'<b>\1</b>', text).replace("\n", "<br>")

    footer_html = f'<footer class="x-engagement-bar">{_render_x_metrics_html(p)}</footer>' if show_footer else ""
    avatar_html = get_x_author_avatar_html(p)

    return (
        f'<div class="feed-card-inner">'
        f'<div class="feed-card-stripe {stripe_cls}"></div>'
        f'<article class="x-post-card">'
        f'<header class="x-post-header">'
        f'<div class="x-author-box">{avatar_html}'
        f'<div class="x-author-meta"><span class="x-author-name">{author_name}{verified_mark}</span>'
        f'<span class="x-author-handle">{plat_badge}{handle} · <span class="x-type-badge">{author_type}</span></span></div></div>'
        f'<div class="x-post-header__meta">{get_badge_html(p.get("structured_category", "Others"))}'
        f'{time_badge_html(p.get("relative_time", "Recent"), p.get("exact_time", ""))}'
        f'{_translation_engine_badge_html(p)}'
        + (f'<span class="hl-chip hl-chip--ok" title="{html.escape(sent_title, quote=True)}">{_HL_CHECK_SVG}</span>' if sent_title else "<!--sent-->")
        + f'</div>'
        f'</header>'
        f'<div class="x-post-text">{text}</div>'
        f'{footer_html}'
        f'</article>'
        f'</div>'
    )

def render_apple_combined_item_card(item: Dict[str, Any]) -> str:
    """Dispatches item rendering based on source type (Nepali Media, Indian Press, or X Post)."""
    item_type = item.get("_feed_type") or item.get("stream")
    if item_type == "x" or "raw_handle" in item or "handle" in item:
        return render_apple_x_post_card(item)
    elif item_type == "indian" or item.get("stream") == "Indian Press" or "nepal_relevance_score" in item:
        return render_apple_article_card(item, is_indian=True)
    else:
        return render_apple_article_card(item, is_indian=False)

# ==========================================
# SHARED UI COMPONENTS
# ==========================================
def render_page_header(title: str, subtitle: str = "", show_window: bool = False) -> None:
    """Large-title page header used by every workspace for a consistent hierarchy."""
    sub = f'<p class="page-header__subtitle">{subtitle}</p>' if subtitle else ""
    meta = f'<div class="page-header__meta"><span class="pill pill--tint">{_ico("clock", 12)} {html.escape(window_label)}</span></div>' if show_window else ""
    st.markdown(
        f'<div class="page-header"><div><h2 class="page-header__title">{html.escape(title)}</h2>{sub}</div>{meta}</div>',
        unsafe_allow_html=True,
    )

def render_empty_state(icon: str, title: str, body: str) -> None:
    glyph = _ico(_EMOJI_TO_ICON[icon], 26) if icon in _EMOJI_TO_ICON else icon
    st.markdown(
        f'<div class="empty-state"><div class="empty-state__icon">{glyph}</div>'
        f'<p class="empty-state__title">{html.escape(title)}</p><p class="empty-state__body">{html.escape(body)}</p></div>',
        unsafe_allow_html=True,
    )

def sidebar_section(title: str, badge: str = "") -> None:
    badge_html = f'<span class="sb-section__badge">{html.escape(badge)}</span>' if badge else ""
    st.markdown(f'<div class="sb-section"><span class="sb-section__title">{html.escape(title)}</span>{badge_html}</div>', unsafe_allow_html=True)

def _render_copy_button(text_to_copy: str, uid: str, icon_only: bool = False) -> None:
    """Renders a single-click browser clipboard button matching the Apple HIG button style."""
    js_payload = json.dumps(text_to_copy)
    btn_id = f"cp_{uid}"
    svg_icon = (
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>'
        '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>'
    )
    _cp_dark = (
        ".cp-btn { background: #3A3A3C; color: #F5F5F7; border-color: transparent; box-shadow: none; } "
        ".cp-btn:hover { background: #48484A; } .cp-btn.copied { background: rgba(50,215,75,.2); color: #6BE585; }"
    )
    if _THEME_MODE == "dark":
        _cp_dark_css = _cp_dark
    elif _THEME_MODE == "auto":
        _cp_dark_css = ".dk " + _cp_dark.replace("} .", "} .dk .")
    else:
        _cp_dark_css = ""
    default_html = svg_icon if icon_only else f'{svg_icon}<span>Copy</span>'
    copied_html = "✓" if icon_only else "<span>✓ Copied</span>"
    btn_height = 36
    components.html(
        f"""
        <!DOCTYPE html>
        <html>
        <head>
        <style>
            html, body {{ margin: 0; padding: 0; background: transparent; overflow: hidden; font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", system-ui, sans-serif; }}
            .cp-btn {{
                width: 100%;
                height: {btn_height}px;
                border-radius: 8px;
                border: none;
                background: rgba(0, 0, 0, 0.05);
                color: #1D1D1F;
                font-size: 13px;
                font-weight: 600;
                cursor: pointer;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                gap: 6px;
                box-shadow: none;
                transition: background-color 0.15s ease, color 0.15s ease;
                box-sizing: border-box;
            }}
            .cp-btn:hover {{ background: rgba(0, 0, 0, 0.08); }}
            {_cp_dark_css}
            @media (max-width: 110px) {{ .cp-btn span {{ display: none; }} }}
            .cp-btn.copied {{
                background: #DCFCE7;
                color: #15803D;
                border-color: rgba(21, 128, 61, 0.32);
            }}
        </style>
        </head>
        <body>
            <button id="{btn_id}" class="cp-btn" type="button" title="Copy content and source" aria-label="Copy content and source" onclick="copyUnified()">{default_html}</button>
            <script>
            try {{ if (window.parent.matchMedia("(prefers-color-scheme: dark)").matches) document.documentElement.classList.add("dk"); }} catch (e) {{}}
            const TEXT = {js_payload};
            const DEFAULT_HTML = {json.dumps(default_html)};
            const COPIED_HTML = {json.dumps(copied_html)};
            function copyUnified() {{
                const btn = document.getElementById("{btn_id}");
                const markCopied = () => {{
                    btn.innerHTML = COPIED_HTML;
                    btn.classList.add("copied");
                    setTimeout(() => {{
                        btn.innerHTML = DEFAULT_HTML;
                        btn.classList.remove("copied");
                    }}, 2000);
                }};
                if (navigator.clipboard && window.isSecureContext) {{
                    navigator.clipboard.writeText(TEXT).then(markCopied).catch(() => fallbackCopy(markCopied));
                }} else {{
                    fallbackCopy(markCopied);
                }}
            }}
            function fallbackCopy(onDone) {{
                const ta = document.createElement("textarea");
                ta.value = TEXT;
                ta.style.position = "fixed";
                ta.style.opacity = "0";
                document.body.appendChild(ta);
                ta.focus();
                ta.select();
                try {{
                    document.execCommand("copy");
                    onDone();
                }} catch (e) {{
                    console.error("Copy failed", e);
                }}
                document.body.removeChild(ta);
            }}
            </script>
        </body>
        </html>
        """,
        height=btn_height,
    )


_BUSY_VERBS = {
    "read": ["Unfolding", "Fetching", "Skimming", "Gathering", "Opening up"],
    "translate": ["Translating", "Decoding", "Weaving words", "Untangling", "Rephrasing"],
    "send": ["Sending", "Dispatching", "Beaming", "Delivering", "Launching"],
    "prepare": ["Preparing", "Composing", "Polishing", "Drafting", "Shaping"],
    "feed": ["Gathering", "Scouting", "Collecting", "Sifting", "Tuning in"],
}


def _busy(kind: str = "feed", detail: str = "") -> str:
    """Playful progress label (e.g. 'Untangling…') so no wait is ever silent."""
    import random
    v = random.choice(_BUSY_VERBS.get(kind, _BUSY_VERBS["feed"]))
    return f"{v}… {detail}".strip() if detail else f"{v}…"


def _set_pending_dest(kind: str, cache_id: str, idx: int) -> None:
    st.session_state[f"pending_{kind}_send"] = cache_id
    st.session_state[f"pending_{kind}_dest"] = idx


def _remember_wa_group(key: str) -> None:
    st.session_state["wa_last_group"] = st.session_state.get(key)


def _wa_dest_from_state(targets: List[Dict[str, Any]], key: str) -> str:
    names = [t["name"] for t in targets]
    cur = st.session_state.get(key)
    if cur in names:
        return cur
    return names[0]


def _render_wa_group_chip(targets: List[Dict[str, Any]], key: str, uid: str) -> None:
    """Compact WhatsApp group picker: a short-name chip that opens a list of groups."""
    names = [t["name"] for t in targets]
    cur = _wa_dest_from_state(targets, key)
    if st.session_state.get(key) != cur:
        st.session_state[key] = cur
    _w = cur.split()
    short = " ".join(_w[:2]) if len(" ".join(_w[:2])) <= 12 else _w[0]
    with st.popover(f":material/chat: {short}", help=cur, key=f"wa_pop_{uid}", width="stretch"):
        st.radio("WhatsApp group", names, key=key, label_visibility="collapsed", on_change=_remember_wa_group, args=(key,))


def _compute_item_uid(item: Dict[str, Any], prefix: str) -> str:
    raw_key = f"{prefix}|{item.get('canonical_id') or item.get('id') or item.get('link') or item.get('title') or ''}"
    return hashlib.md5(raw_key.encode("utf-8", errors="ignore")).hexdigest()[:12]


def _resolve_item_flags(item: Dict[str, Any], renderer: Callable[[Dict[str, Any]], str]) -> tuple:
    feed_type = item.get("_feed_type") or item.get("stream") or ""
    if renderer is render_apple_x_post_card or feed_type == "x" or "raw_handle" in item or "handle" in item:
        return (False, True)
    if feed_type == "indian" or feed_type == "Indian Press" or "nepal_relevance_score" in item:
        return (True, False)
    return (False, False)


def _generate_unified_item_content(
    item: Dict[str, Any],
    is_x: bool,
    on_progress: Optional[Callable[[str, float], None]] = None,
) -> Dict[str, Any]:
    from nepal_summarizer import generate_on_demand_news_brief, generate_on_demand_x_content
    if is_x:
        return generate_on_demand_x_content(item, on_progress=on_progress)
    return generate_on_demand_news_brief(item, on_progress=on_progress)


@st.cache_data(ttl=300, show_spinner=False)
def _get_cached_wa_dest() -> Dict[str, Any]:
    from whatsapp_greenapi import get_destination_group as get_wa_destination_group
    return get_wa_destination_group()


@st.cache_data(ttl=120, show_spinner=False)
def _get_wa_sent_map() -> Dict[str, Dict[str, Any]]:
    try:
        return get_whatsapp_sent_map()
    except Exception:
        return {}


def _format_wa_sent_time(sent_at_val: Any) -> str:
    if not sent_at_val:
        return ""
    try:
        from dateutil import parser as dt_parser
        dt = sent_at_val if isinstance(sent_at_val, datetime.datetime) else dt_parser.parse(str(sent_at_val))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(NEPAL_TZ).strftime("%b %d, %I:%M %p NPT")
    except Exception:
        return ""


def _clear_active_modal() -> None:
    st.session_state["active_modal"] = None
    st.session_state["_active_modal_opened"] = False


def _render_source_link_html(url: str, inline: bool = False) -> str:
    """Renders a secondary clickable Source URL block shared by Read in App and Share modals."""
    clean = (url or "").strip()
    if not clean:
        return ""
    from urllib.parse import urlparse
    parsed = urlparse(clean)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    domain_label = host or clean
    esc_url = html.escape(clean, quote=True)
    esc_dom = html.escape(domain_label)
    style = ' style="border-top:none;padding-top:2px;margin-bottom:8px;"' if inline else ""
    return (
        f'<div class="unified-brief-box__source"{style}>'
        f'<span class="source-lbl">Source:</span> '
        f'<a href="{esc_url}" target="_blank" rel="noopener noreferrer" class="source-link-chip" title="Open original article in new tab">'
        f'<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><line x1="2" y1="12" x2="22" y2="12"></line><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path></svg>'
        f'<span>{esc_dom}</span>'
        f'<span class="source-link-arrow">↗</span>'
        f'</a></div>'
    )


def _commit_share_draft(draft: Dict[str, Any], new_text: str, new_headline: Optional[str] = None) -> None:
    """Commits edited headline/body text to the versioned Share draft without altering original AI output or sending."""
    clean = (new_text or "").strip()
    old_body = (draft.get("saved_content") or "").strip()
    old_hl = (draft.get("saved_headline") or "").strip()
    clean_hl = (new_headline if new_headline is not None else old_hl).strip()
    changed = (clean and clean != old_body) or (new_headline is not None and clean_hl != old_hl)
    if changed:
        if clean:
            draft["saved_content"] = clean
        if new_headline is not None:
            draft["saved_headline"] = clean_hl
        draft["version"] = int(draft.get("version") or 1) + 1
        draft["saved_at"] = datetime.datetime.now(NEPAL_TZ).strftime("%I:%M %p NPT")
        draft["_just_saved"] = f"Saved draft v{draft['version']}"
    draft["draft_content"] = draft.get("saved_content") or ""
    if "saved_headline" in draft:
        draft["draft_headline"] = draft.get("saved_headline") or ""
    draft["is_editing"] = False
    draft["unsaved_send_warn"] = False
    draft["close_guard"] = False


def _commit_read_draft(draft: Dict[str, Any], new_body: str, new_headline: Optional[str] = None) -> None:
    """Commits edited headline/body text to the versioned Read Translation draft."""
    clean = (new_body or "").strip()
    old_body = (draft.get("saved_body") or "").strip()
    old_hl = (draft.get("saved_headline") or "").strip()
    clean_hl = (new_headline if new_headline is not None else old_hl).strip()
    changed = (clean and clean != old_body) or (new_headline is not None and clean_hl != old_hl)
    if changed:
        if clean:
            draft["saved_body"] = clean
        if new_headline is not None:
            draft["saved_headline"] = clean_hl
        draft["version"] = int(draft.get("version") or 1) + 1
        draft["saved_at"] = datetime.datetime.now(NEPAL_TZ).strftime("%I:%M %p NPT")
        draft["_just_saved"] = f"Saved translation draft v{draft['version']}"
    draft["draft_body"] = draft.get("saved_body") or ""
    draft["draft_headline"] = draft.get("saved_headline") or ""
    draft["is_editing"] = False
    draft["unsaved_send_warn"] = False
    draft["close_guard"] = False


def _on_read_enter_edit(cache_id: str) -> None:
    d = st.session_state.get("read_translation_drafts", {}).get(cache_id)
    if d:
        d["is_editing"] = True
        d["close_guard"] = False
        d["unsaved_send_warn"] = False


def _on_read_cancel_edit(cache_id: str) -> None:
    d = st.session_state.get("read_translation_drafts", {}).get(cache_id)
    if d:
        d["draft_body"] = d.get("saved_body") or ""
        d["draft_headline"] = d.get("saved_headline") or ""
        d["is_editing"] = False
        d["unsaved_send_warn"] = False


def _on_read_save(cache_id: str, ta_key: str = "", hl_key: str = "") -> None:
    d = st.session_state.get("read_translation_drafts", {}).get(cache_id)
    if not d:
        return
    txt = str(st.session_state[ta_key]) if (ta_key and ta_key in st.session_state) else (d.get("draft_body") or "")
    hl_val: Optional[str] = None
    if hl_key and hl_key in st.session_state:
        hl_val = str(st.session_state[hl_key])
    elif "draft_headline" in d:
        hl_val = str(d.get("draft_headline") or "")
    _commit_read_draft(d, txt, new_headline=hl_val)


def _on_read_discard_unsaved(cache_id: str) -> None:
    d = st.session_state.get("read_translation_drafts", {}).get(cache_id)
    if d:
        d["draft_body"] = d.get("saved_body") or ""
        d["draft_headline"] = d.get("saved_headline") or ""
        d["unsaved_send_warn"] = False


def _on_read_req_send(cache_id: str) -> None:
    st.session_state["pending_read_send"] = cache_id


def _on_read_req_close_guard(cache_id: str) -> None:
    d = st.session_state.get("read_translation_drafts", {}).get(cache_id)
    if d:
        d["close_guard"] = True


def _on_req_read_translate(cache_id: str) -> None:
    st.session_state["pending_read_translate"] = cache_id


def _on_toggle_read_view(cache_id: str) -> None:
    cur = st.session_state.get("ondemand_fulltext_view", {}).get(cache_id, "orig")
    st.session_state.setdefault("ondemand_fulltext_view", {})[cache_id] = "orig" if cur == "en" else "en"


def _render_read_send_fragment(
    cache_id: str,
    item_uid: str,
    dest_name: str,
    selected_gid: str,
    item_link: str,
    has_unsaved: bool,
    ver: int,
    saved_headline: str,
    saved_body: str,
    ft_src: str,
    targets: Any = None,
) -> None:
    sent_ids = st.session_state.setdefault("whatsapp_sent_ids", set())
    persisted_sent = _get_wa_sent_map().get(cache_id)
    is_sent = cache_id in sent_ids or bool(persisted_sent)

    btn_label = "Sent" if is_sent else "Send"
    btn_icon = ":material/check:" if is_sent else ":material/send:"
    btn_help = f"Already sent to {dest_name}" if is_sent else f"Send to {dest_name}: latest saved translation (v{ver}) to {dest_name}"

    _tg = targets if (targets and len(targets) > 1) else [{"name": dest_name, "id": selected_gid}]
    _multi = len(_tg) > 1
    _bcols = st.columns(len(_tg), gap="small") if _multi else [st.container()]
    _clicked = None
    for _i, _t in enumerate(_tg):
        _short = " ".join(_t["name"].split()[:2]) if _multi else btn_label
        with _bcols[_i]:
            if st.button(
                "Sent" if is_sent else _short,
                icon=btn_icon,
                type="secondary" if is_sent else "primary",
                key=f"dlg_rd_conf_{item_uid}" + (f"_{_i}" if _multi else ""),
                disabled=is_sent,
                help=("Already sent" if is_sent else f"Send to {_t['name']}"),
                on_click=_set_pending_dest,
                args=("read", cache_id, _i),
                width="stretch",
            ):
                _clicked = _i
    if _clicked is None and st.session_state.get("pending_read_send") == cache_id:
        _clicked = st.session_state.pop("pending_read_dest", 0)
    st.session_state.pop("pending_read_send", None)
    if _clicked is not None and _multi:
        dest_name, selected_gid = _tg[_clicked]["name"], _tg[_clicked]["id"]
    send_clicked = _clicked is not None
    should_send = send_clicked and not is_sent
    if should_send:
        read_draft = st.session_state.get("read_translation_drafts", {}).get(cache_id, {})
        if has_unsaved:
            read_draft["unsaved_send_warn"] = True
            st.warning("Please save changes before sending.")
        else:
            with st.spinner(_busy("send", dest_name)):
                from whatsapp_greenapi import send_group_message as send_wa_group_message
                from nepal_summarizer import format_reader_copy_payload
                wa_payload = format_reader_copy_payload(
                    headline=saved_headline,
                    full_body=saved_body,
                    source_url=ft_src,
                    whatsapp_bold=True,
                )
                wa_res = send_wa_group_message(
                    chat_id=selected_gid,
                    message=wa_payload,
                    session_approved=True,
                    sent_registry=st.session_state.setdefault("wa_sent_registry", set()),
                )
                wa_res["group_name"] = dest_name
                st.session_state.setdefault("wa_item_status", {})[cache_id] = wa_res
                if wa_res.get("ok") and wa_res.get("accepted"):
                    try:
                        record_whatsapp_sent(
                            item_key=cache_id,
                            group_id=selected_gid,
                            group_name=dest_name,
                            id_message=str(wa_res.get("id_message") or ""),
                            item_link=item_link,
                        )
                        _get_wa_sent_map.clear()
                    except Exception as log_exc:
                        wa_res["log_warning"] = f"Sent, but failed to update history log: {type(log_exc).__name__}"
                    sent_ids.add(cache_id)
                    _mark_feed_card_sent(cache_id, dest_name)
                    st.session_state["active_modal"] = None
                    st.rerun()
                else:
                    st.error(wa_res.get("error") or "Failed to send WhatsApp message.")

    wa_status = st.session_state.get("wa_item_status", {}).get(cache_id)
    if wa_status:
        st_code = wa_status.get("status")
        if wa_status.get("ok") and wa_status.get("accepted"):
            gname = html.escape(wa_status.get("group_name") or dest_name)
            msg_id = html.escape(str(wa_status.get("id_message") or ""))
            st.success(f"✓ Accepted by Green API for {gname} · ID: {msg_id}")
        elif st_code == "inactive":
            st.info(wa_status.get("error"))
        elif st_code == "duplicate_prevented":
            st.warning(wa_status.get("error"))
        elif not wa_status.get("ok"):
            st.error(f"{wa_status.get('error') or 'Failed to send WhatsApp message.'} Your draft is preserved — click Confirm to Send to retry.")


@st.dialog("Read in App", width="large", icon=":material/menu_book:", on_dismiss=_clear_active_modal)
def _show_read_in_app_dialog() -> None:
    ctx = st.session_state.get("active_modal") or {}
    item = ctx.get("item") or {}
    cache_id = ctx.get("cache_id") or ""
    item_uid = ctx.get("item_uid") or cache_id
    item_link = (ctx.get("item_link") or item.get("link") or "").strip()

    if "news.google.com" in item_link.lower():
        try:
            from nepal_fetcher import resolve_google_news_url
            res_link = resolve_google_news_url(item_link)
            if res_link and "news.google.com" not in res_link.lower():
                item_link = res_link
                item["link"] = res_link
                ctx["item_link"] = res_link
                try:
                    from nepal_news_store import update_article_link
                    update_article_link(
                        old_link=ctx.get("item_link") or item.get("link") or "",
                        new_link=res_link,
                        canonical_id=cache_id,
                    )
                except Exception:
                    pass
        except Exception:
            pass

    st.session_state.setdefault("ondemand_fulltext", {})
    st.session_state.setdefault("ondemand_fulltext_view", {})
    st.session_state.setdefault("read_translation_drafts", {})
    st.session_state.setdefault("wa_sent_registry", set())
    st.session_state.setdefault("wa_item_status", {})

    if st.session_state.pop("pending_read_translate", None) == cache_id:
        from nepal_summarizer import extract_on_demand_full_article
        with st.container(key="busy_pill"):
            _tr_ph = st.empty()
        _tr_failed = False
        with _tr_ph.status(_busy("translate"), expanded=True) as tr_status:
            def _tr_prog(msg: str, pct: float) -> None:
                tr_status.update(label=f"{_busy('translate')} {int(pct * 100)}%")
            ft_tr = extract_on_demand_full_article(item, translate_to_english=True, on_progress=_tr_prog)
            st.session_state["ondemand_fulltext"][cache_id] = ft_tr
            if ft_tr.get("translated_text") or ft_tr.get("translated_title"):
                st.session_state["ondemand_fulltext_view"][cache_id] = "en"
                tr_status.update(label="English translation ready", state="complete", expanded=False)
                st.toast("Headline & full article translated to English", icon=":material/translate:")
                tr_t = (ft_tr.get("translated_title") or "").strip()
                tr_b = (ft_tr.get("translated_text") or "").strip()
                rd = st.session_state["read_translation_drafts"].get(cache_id)
                if rd:
                    if rd.get("version", 1) == 1 and not rd.get("is_editing"):
                        if tr_t:
                            rd["original_headline"] = tr_t
                            rd["saved_headline"] = tr_t
                            rd["draft_headline"] = tr_t
                        if tr_b:
                            rd["original_body"] = tr_b
                            rd["saved_body"] = tr_b
                            rd["draft_body"] = tr_b
                else:
                    st.session_state["read_translation_drafts"][cache_id] = {
                        "original_headline": tr_t,
                        "saved_headline": tr_t,
                        "draft_headline": tr_t,
                        "original_body": tr_b,
                        "saved_body": tr_b,
                        "draft_body": tr_b,
                        "source_url": ft_tr.get("source_url") or item_link,
                        "version": 1,
                        "saved_at": "",
                        "is_editing": False,
                        "close_guard": False,
                        "unsaved_send_warn": False,
                    }
            else:
                tr_status.update(label="Translation unavailable", state="error", expanded=False)
                _tr_failed = True
        if not _tr_failed:
            _tr_ph.empty()

    fulltext_data = st.session_state["ondemand_fulltext"].get(cache_id)
    if not fulltext_data:
        from nepal_summarizer import extract_on_demand_full_article
        with st.container(key="busy_pill"):
            _op_ph = st.empty()
        with _op_ph.status(_busy("read"), expanded=True) as status:
            def _read_prog(msg: str, pct: float) -> None:
                status.update(label=f"{_busy('read')} {int(pct * 100)}%")
            fulltext_data = extract_on_demand_full_article(item, translate_to_english=False, on_progress=_read_prog)
            status.update(label="Article ready", state="complete", expanded=False)
            st.session_state["ondemand_fulltext"][cache_id] = fulltext_data
            st.session_state["ondemand_fulltext_view"][cache_id] = "orig"
        _op_ph.empty()

    if fulltext_data and fulltext_data.get("ok"):
        from nepal_summarizer import format_reader_copy_payload
        ft_lang = fulltext_data.get("lang", "en")
        lang_names = {"ne": "Nepali", "hi": "Hindi", "en": "English"}
        lang_lbl = lang_names.get(ft_lang, "Original")
        has_tr = bool(fulltext_data.get("translated_text") or fulltext_data.get("translated_title"))
        view_mode = st.session_state["ondemand_fulltext_view"].get(cache_id, "en" if has_tr else "orig")
        is_en_view = bool(view_mode == "en" and has_tr)
        is_english_mode = is_en_view or (ft_lang == "en")

        raw_title = (fulltext_data.get("original_title") or item.get("title") or "").strip()
        tr_title = (fulltext_data.get("translated_title") or "").strip()
        base_shown_title = tr_title if (is_en_view and tr_title) else raw_title
        base_shown_text = (
            fulltext_data["translated_text"]
            if (is_en_view and fulltext_data.get("translated_text"))
            else fulltext_data["original_text"]
        )
        ft_src = (fulltext_data.get("source_url") or item_link or "").strip()

        dkey = cache_id if is_english_mode else f"{cache_id}::orig"
        read_draft = st.session_state["read_translation_drafts"].get(dkey)
        if True:
            if not read_draft:
                read_draft = {
                    "original_headline": base_shown_title,
                    "saved_headline": base_shown_title,
                    "draft_headline": base_shown_title,
                    "original_body": base_shown_text,
                    "saved_body": base_shown_text,
                    "draft_body": base_shown_text,
                    "source_url": ft_src,
                    "version": 1,
                    "saved_at": "",
                    "is_editing": False,
                    "close_guard": False,
                    "unsaved_send_warn": False,
                }
                st.session_state["read_translation_drafts"][dkey] = read_draft
            if read_draft.get("_just_saved"):
                st.toast(read_draft.pop("_just_saved"), icon=":material/bookmark_added:")

        hl_key = f"dlg_rd_hl_{item_uid}"
        ta_key = f"dlg_rd_ta_{item_uid}"
        if read_draft and read_draft.get("is_editing"):
            if hl_key in st.session_state:
                read_draft["draft_headline"] = str(st.session_state[hl_key] or "")
            if ta_key in st.session_state:
                read_draft["draft_body"] = str(st.session_state[ta_key] or "")

        saved_headline = (read_draft.get("saved_headline") if read_draft else base_shown_title) or ""
        current_draft_headline = (read_draft.get("draft_headline") if read_draft else base_shown_title) or ""
        saved_body = (read_draft.get("saved_body") if read_draft else base_shown_text) or ""
        current_draft_body = (read_draft.get("draft_body") if read_draft else base_shown_text) or ""

        has_unsaved = bool(read_draft and (
            (current_draft_body.strip() != saved_body.strip()) or
            (current_draft_headline.strip() != saved_headline.strip())
        ))
        active_headline = current_draft_headline if (has_unsaved and current_draft_headline != saved_headline) else saved_headline
        active_body = current_draft_body if (has_unsaved and current_draft_body != saved_body) else saved_body

        shown_title = active_headline
        shown_text = active_body

        from whatsapp_greenapi import get_share_targets
        _wa_targets = get_share_targets(is_x_post=False)
        _wa_grp_key = f"dlg_rd_wa_grp_{item_uid}"
        if len(_wa_targets) == 1:
            selected_gid = _wa_targets[0]["id"]
            dest_name = _wa_targets[0]["name"]
        else:
            _target_by_name = {t["name"]: t["id"] for t in _wa_targets}
            _default_grp = st.session_state.get(_wa_grp_key)
            if _default_grp not in _target_by_name:
                _default_grp = _wa_targets[0]["name"]
            dest_name = _default_grp
            selected_gid = _target_by_name[dest_name]

        ft_eyebrow = "English Translation" if is_en_view else ("English Article" if ft_lang == "en" else lang_lbl)
        is_complete = bool(fulltext_data.get("is_complete", True))
        ext_badge = (
            '<span class="extraction-badge extraction-badge--full">✓ Full Article</span>'
            if is_complete
            else '<span class="extraction-badge extraction-badge--partial">⚠ Partial Extraction</span>'
        )

        persisted_sent = _get_wa_sent_map().get(cache_id)
        ver = int(read_draft.get("version") or 1) if read_draft else 1
        saved_at = read_draft.get("saved_at") or "" if read_draft else ""

        status_pill = ""
        if read_draft:
            status_pill = (
                '<span class="share-draft-pill share-draft-pill--unsaved">● Unsaved</span>'
                if has_unsaved
                else (
                    f'<span class="share-draft-pill share-draft-pill--saved">✓ Saved v{ver} · {html.escape(saved_at)}</span>'
                    if saved_at
                    else f'<span class="share-draft-pill share-draft-pill--saved">Draft v{ver}</span>'
                )
            )

        sent_pill = ""
        if persisted_sent:
            gname_esc = html.escape(str(persisted_sent.get("group_name") or "WhatsApp"))
            ts_str = _format_wa_sent_time(persisted_sent.get("sent_at"))
            msg_id_esc = html.escape(str(persisted_sent.get("id_message") or ""))
            ts_txt = f" · {html.escape(ts_str)}" if ts_str else ""
            sent_pill = f'<span class="share-draft-pill share-draft-pill--sent" title="Message ID: {msg_id_esc}">✓ Sent to {gname_esc}{ts_txt}</span>'

        st.markdown('<div class="read-modal-anchor"></div>', unsafe_allow_html=True)
        _rd_eng = str(fulltext_data.get("translation_engine") or "").strip()
        if is_en_view and _rd_eng:
            st.markdown(
                f'<div class="share-modal-head"><span class="share-modal-pills">'
                f'<span class="lang-label" title="Translated via {html.escape(_rd_eng, quote=True)}">Translated via {html.escape(_rd_eng)}</span>'
                f'</span></div>',
                unsafe_allow_html=True,
            )

        if read_draft and read_draft.get("is_editing"):
            st.markdown(
                f'<div class="share-modal-head">'
                f'<span class="share-modal-pills">{"<span class=share-draft-pill>●</span>" if has_unsaved else ""}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div class="editorial-edit-banner">'
                '<div class="editorial-edit-banner__tag">'
                '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-1px;margin-right:5px;"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>'
                'EDITORIAL STUDIO'
                '</div>'
                '<div class="editorial-edit-banner__hint">Tap any field to refine before sending. Changes save to session draft.</div>'
                '</div>',
                unsafe_allow_html=True,
            )
            edited_hl = st.text_input(
                f"Headline ({lang_lbl if not is_english_mode else 'English'})",
                value=read_draft.get("draft_headline") or "",
                key=hl_key,
            )
            read_draft["draft_headline"] = edited_hl or ""
            current_draft_headline = read_draft["draft_headline"].strip()

            edited_body = st.text_area(
                f"Article Body ({lang_lbl if not is_english_mode else 'English'})",
                value=read_draft.get("draft_body") or "",
                height=260,
                key=ta_key,
            )
            read_draft["draft_body"] = edited_body or ""
            current_draft_body = read_draft["draft_body"].strip()
            has_unsaved = (current_draft_body != saved_body) or (current_draft_headline != saved_headline)

            if ft_src:
                st.markdown(_render_source_link_html(ft_src, inline=True), unsafe_allow_html=True)
            st.markdown('<div class="editorial-edit-actions-anchor"></div>', unsafe_allow_html=True)
            ec1, ec2 = st.columns([1.2, 1], gap="small")
            with ec1:
                st.button(
                    "Save Draft",
                    icon=":material/save:",
                    type="primary",
                    key=f"dlg_rd_save_{item_uid}",
                    help="Save draft without sending",
                    on_click=_on_read_save,
                    args=(dkey, ta_key, hl_key),
                    use_container_width=True,
                )
            with ec2:
                st.button(
                    "Discard Edits",
                    icon=":material/close:",
                    key=f"dlg_rd_cancel_{item_uid}",
                    help="Discard unsaved edits",
                    on_click=_on_read_cancel_edit,
                    args=(dkey,),
                    use_container_width=True,
                )
            return

        reader_title = html.escape(shown_title)
        reader_src = html.escape((item.get("source") or "").strip())
        reader_time = html.escape((item.get("exact_time") or item.get("relative_time") or "").strip())
        meta_parts = [p for p in (reader_src, reader_time) if p]
        reader_meta_html = f'<div class="fulltext-reader-box__meta">{" · ".join(meta_parts)}</div>' if meta_parts else ""

        body_paras = [p.strip() for p in re.split(r"\n\s*\n", (shown_text or "").strip()) if p.strip()]
        if body_paras and len(body_paras) > 1 and body_paras[0] in (raw_title, shown_title, base_shown_title):
            body_paras = body_paras[1:]
        body_html = "".join(f'<p class="reader-para">{html.escape(p)}</p>' for p in body_paras)
        ft_src_html = _render_source_link_html(ft_src)

        _partial_chip = '' if is_complete else '<span class="extraction-badge extraction-badge--partial" title="Partial extraction">⚠</span>'
        _rd_unsaved = '<span class="share-draft-pill share-draft-pill--unsaved" title="Unsaved changes">●</span>' if (read_draft and has_unsaved) else ''
        _rd_sent = f'<span class="share-draft-pill share-draft-pill--sent" title="Already sent to WhatsApp">✓ Sent</span>' if persisted_sent else ''
        header_pills = f'{_partial_chip}{_rd_unsaved}{_rd_sent}'
        st.markdown(
            f'<div class="fulltext-reader-box">'
            f'{"<div class=fulltext-reader-box__header>" + header_pills + "</div>" if header_pills else ""}'
            f'<div class="fulltext-reader-box__title">{reader_title}</div>'
            f'{reader_meta_html}'
            f'<div class="fulltext-reader-box__body">{body_html}</div>'
            f'{ft_src_html}'
            f'</div>',
            unsafe_allow_html=True,
        )
        if fulltext_data.get("error"):
            st.warning(fulltext_data["error"])

        if read_draft:
            if read_draft.get("close_guard") and has_unsaved:
                st.warning("Save changes before closing?")
                g1, g2, g3 = st.columns(3, gap="small")
                with g1:
                    if st.button("Save & Close", icon=":material/save:", type="primary", key=f"dlg_rd_sc_{item_uid}"):
                        _commit_read_draft(read_draft, current_draft_body, new_headline=current_draft_headline)
                        st.session_state["active_modal"] = None
                        st.rerun()
                with g2:
                    if st.button("Discard", icon=":material/delete_outline:", key=f"dlg_rd_dc_{item_uid}"):
                        read_draft["draft_body"] = read_draft["saved_body"]
                        read_draft["draft_headline"] = read_draft.get("saved_headline") or ""
                        read_draft["close_guard"] = False
                        st.session_state["active_modal"] = None
                        st.rerun()
                with g3:
                    st.button(
                        "Keep Editing",
                        icon=":material/edit:",
                        key=f"dlg_rd_ke_{item_uid}",
                        on_click=_on_read_enter_edit,
                        args=(dkey,),
                    )
                return

            if read_draft.get("unsaved_send_warn") and has_unsaved:
                st.warning("Unsaved edits exist. Save or discard them before sending.")
                u1, u2 = st.columns(2, gap="small")
                with u1:
                    st.button(
                        "Save Draft",
                        icon=":material/save:",
                        type="primary",
                        key=f"dlg_rd_sd_{item_uid}",
                        on_click=_on_read_save,
                        args=(dkey, "", ""),
                    )
                with u2:
                    st.button(
                        "Discard Edits",
                        icon=":material/undo:",
                        key=f"dlg_rd_dd_{item_uid}",
                        on_click=_on_read_cancel_edit,
                        args=(dkey,),
                    )

        needs_tr = (ft_lang != "en") or _has_devanagari(raw_title) or _has_devanagari(fulltext_data.get("original_text", ""))
        has_tr_btn = needs_tr or has_tr

        if len(_wa_targets) > 1:
            dest_name = _wa_dest_from_state(_wa_targets, _wa_grp_key)
            selected_gid = _target_by_name[dest_name]

        copy_body = "\n\n".join(body_paras) if body_paras else (shown_text or "").strip()
        ft_copy_payload = format_reader_copy_payload(
            headline=shown_title,
            full_body=copy_body,
            source_url=ft_src,
            whatsapp_bold=False,
        )

        if True:
            _multi_wa = len(_wa_targets) > 1
            _spec = ([1.25] if has_tr_btn else []) + [0.8, 0.95, 1.1] + ([1.1] if has_unsaved else [])
            with st.container(key=f"wa_actions_{item_uid}"):
                cols = st.columns(_spec, vertical_alignment="center", gap="small")
                ci = 0
                if has_tr_btn:
                    with cols[ci]:
                        if needs_tr and not has_tr:
                            st.button("Translate", help="Translate to English", icon=":material/translate:", type="primary",
                                      key=f"dlg_ft_tr_{item_uid}", on_click=_on_req_read_translate, args=(cache_id,), width="stretch")
                        else:
                            st.button("Original" if is_english_mode else "English", help="Switch between original and English",
                                      icon=":material/swap_horiz:", type="secondary", key=f"dlg_ft_tog_{item_uid}",
                                      on_click=_on_toggle_read_view, args=(cache_id,), width="stretch")
                    ci += 1
                with cols[ci]:
                    _render_copy_button(ft_copy_payload, uid=f"dlg_ft_{item_uid}", icon_only=False)
                with cols[ci + 1]:
                    st.button(
                        "Edit",
                        icon=":material/edit:",
                        key=f"dlg_rd_edit_{item_uid}",
                        help="Edit",
                        on_click=_on_read_enter_edit,
                        args=(dkey,),
                        width="stretch",
                    )
                with cols[ci + 2]:
                    st.button(
                        "Save",
                        icon=":material/save:",
                        key=f"dlg_rd_save_bar_{item_uid}",
                        disabled=not has_unsaved,
                        help="Save draft without sending" if has_unsaved else "All changes saved",
                        on_click=_on_read_save,
                        args=(dkey, "", ""),
                        width="stretch",
                    )
                ci += 3
                if has_unsaved:
                    with cols[ci]:
                        st.button(
                            "Close",
                            icon=":material/close:",
                            key=f"dlg_ft_cls_{item_uid}",
                            help="Close",
                            on_click=_on_read_req_close_guard,
                            args=(dkey,),
                            width="stretch",
                        )
                    ci += 1
                _render_read_send_fragment(
                    cache_id=cache_id,
                    item_uid=item_uid,
                    dest_name=dest_name,
                    selected_gid=selected_gid,
                    item_link=item_link,
                    has_unsaved=has_unsaved,
                    ver=ver,
                    saved_headline=saved_headline,
                    saved_body=saved_body,
                    ft_src=ft_src,
                    targets=_wa_targets if _multi_wa else None,
                )
    else:
        st.warning("Full article could not be extracted (the publisher may block scraping or require a subscription). Use View Original to read on the publisher's site.")
        c1, c2 = st.columns(2, gap="small")
        if item_link.startswith("http"):
            with c1:
                st.link_button("View Original", item_link, icon=":material/open_in_new:")
        with c2:
            if st.button("Close", icon=":material/close:", key=f"dlg_ft_err_cls_{item_uid}"):
                st.session_state["active_modal"] = None
                st.rerun()


def _on_share_enter_edit(cache_id: str) -> None:
    d = st.session_state.get("share_drafts", {}).get(cache_id)
    if d:
        d["is_editing"] = True
        d["close_guard"] = False
        d["unsaved_send_warn"] = False


def _on_share_cancel_edit(cache_id: str) -> None:
    d = st.session_state.get("share_drafts", {}).get(cache_id)
    if d:
        d["draft_content"] = d.get("saved_content") or ""
        if "saved_headline" in d:
            d["draft_headline"] = d.get("saved_headline") or ""
        d["is_editing"] = False
        d["unsaved_send_warn"] = False


def _on_share_save(cache_id: str, ta_key: str = "", hl_key: str = "") -> None:
    d = st.session_state.get("share_drafts", {}).get(cache_id)
    if not d:
        return
    txt = str(st.session_state[ta_key]) if (ta_key and ta_key in st.session_state) else (d.get("draft_content") or "")
    hl_val: Optional[str] = None
    if hl_key and hl_key in st.session_state:
        hl_val = str(st.session_state[hl_key])
    elif "draft_headline" in d:
        hl_val = str(d.get("draft_headline") or "")
    _commit_share_draft(d, txt, new_headline=hl_val)


def _on_share_discard_unsaved(cache_id: str) -> None:
    d = st.session_state.get("share_drafts", {}).get(cache_id)
    if d:
        d["draft_content"] = d.get("saved_content") or ""
        if "saved_headline" in d:
            d["draft_headline"] = d.get("saved_headline") or ""
        d["unsaved_send_warn"] = False


def _on_share_req_send(cache_id: str) -> None:
    st.session_state["pending_share_send"] = cache_id


def _on_share_req_close_guard(cache_id: str) -> None:
    d = st.session_state.get("share_drafts", {}).get(cache_id)
    if d:
        d["close_guard"] = True


def _render_share_send_fragment(
    cache_id: str,
    item_uid: str,
    dest_name: str,
    selected_gid: str,
    item_link: str,
    has_unsaved: bool,
    ver: int,
    saved_formatted: str,
    targets: Any = None,
) -> None:
    draft = st.session_state.get("share_drafts", {}).get(cache_id, {})
    sent_ids = st.session_state.setdefault("whatsapp_sent_ids", set())
    persisted_sent = _get_wa_sent_map().get(cache_id)
    is_sent = cache_id in sent_ids or bool(persisted_sent)

    btn_label = "Sent" if is_sent else "Send"
    btn_icon = ":material/check:" if is_sent else ":material/send:"
    btn_help = f"Already sent to {dest_name}" if is_sent else f"Send to {dest_name}: latest saved draft (v{ver}) to {dest_name}"

    _tg = targets if (targets and len(targets) > 1) else [{"name": dest_name, "id": selected_gid}]
    _multi = len(_tg) > 1
    _bcols = st.columns(len(_tg), gap="small") if _multi else [st.container()]
    _clicked = None
    for _i, _t in enumerate(_tg):
        _short = " ".join(_t["name"].split()[:2]) if _multi else btn_label
        with _bcols[_i]:
            if st.button(
                "Sent" if is_sent else _short,
                icon=btn_icon,
                type="secondary" if is_sent else "primary",
                key=f"dlg_conf_{item_uid}" + (f"_{_i}" if _multi else ""),
                disabled=is_sent,
                help=("Already sent" if is_sent else f"Send to {_t['name']}"),
                on_click=_set_pending_dest,
                args=("share", cache_id, _i),
                width="stretch",
            ):
                _clicked = _i
    if _clicked is None and st.session_state.get("pending_share_send") == cache_id:
        _clicked = st.session_state.pop("pending_share_dest", 0)
    st.session_state.pop("pending_share_send", None)
    if _clicked is not None and _multi:
        dest_name, selected_gid = _tg[_clicked]["name"], _tg[_clicked]["id"]
    send_clicked = _clicked is not None
    should_send = send_clicked and not is_sent
    if should_send:
        if has_unsaved:
            draft["unsaved_send_warn"] = True
            st.warning("Please save changes before sending.")
        else:
            with st.spinner(_busy("send", dest_name)):
                from whatsapp_greenapi import send_group_message as send_wa_group_message
                wa_res = send_wa_group_message(
                    chat_id=selected_gid,
                    message=saved_formatted,
                    session_approved=True,
                    sent_registry=st.session_state.setdefault("wa_sent_registry", set()),
                )
                wa_res["group_name"] = dest_name
                st.session_state.setdefault("wa_item_status", {})[cache_id] = wa_res
                if wa_res.get("ok") and wa_res.get("accepted"):
                    try:
                        record_whatsapp_sent(
                            item_key=cache_id,
                            group_id=selected_gid,
                            group_name=dest_name,
                            id_message=str(wa_res.get("id_message") or ""),
                            item_link=item_link,
                        )
                        _get_wa_sent_map.clear()
                    except Exception as log_exc:
                        wa_res["log_warning"] = f"Sent, but failed to update history log: {type(log_exc).__name__}"
                    sent_ids.add(cache_id)
                    _mark_feed_card_sent(cache_id, dest_name)
                    st.session_state["active_modal"] = None
                    st.rerun()
                else:
                    st.error(wa_res.get("error") or "Failed to send WhatsApp message.")

    wa_status = st.session_state.get("wa_item_status", {}).get(cache_id)
    if wa_status:
        st_code = wa_status.get("status")
        if wa_status.get("ok") and wa_status.get("accepted"):
            gname = html.escape(wa_status.get("group_name") or dest_name)
            msg_id = html.escape(str(wa_status.get("id_message") or ""))
            st.success(f"✓ Accepted by Green API for {gname} · ID: {msg_id}")
        elif st_code == "inactive":
            st.info(wa_status.get("error"))
        elif st_code == "duplicate_prevented":
            st.warning(wa_status.get("error"))
        elif not wa_status.get("ok"):
            st.error(f"{wa_status.get('error') or 'Failed to send WhatsApp message.'} Your draft is preserved — click Confirm to Send to retry.")


@st.dialog("WhatsApp", width="medium", icon=":material/chat:", on_dismiss=_clear_active_modal)
def _show_share_dialog() -> None:
    ctx = st.session_state.get("active_modal") or {}
    item = ctx.get("item") or {}
    is_x = bool(ctx.get("is_x", False))
    cache_id = ctx.get("cache_id") or ""
    item_uid = ctx.get("item_uid") or cache_id
    item_link = (ctx.get("item_link") or item.get("link") or "").strip()

    if not is_x and "news.google.com" in item_link.lower():
        try:
            from nepal_fetcher import resolve_google_news_url
            res_link = resolve_google_news_url(item_link)
            if res_link and "news.google.com" not in res_link.lower():
                item_link = res_link
                item["link"] = res_link
                ctx["item_link"] = res_link
                try:
                    from nepal_news_store import update_article_link
                    update_article_link(
                        old_link=ctx.get("item_link") or item.get("link") or "",
                        new_link=res_link,
                        canonical_id=cache_id,
                    )
                except Exception:
                    pass
        except Exception:
            pass

    st.session_state.setdefault("ondemand_generated", {})
    st.session_state.setdefault("share_drafts", {})
    st.session_state.setdefault("wa_sent_registry", set())
    st.session_state.setdefault("wa_item_status", {})

    if is_x:
        from nepal_summarizer import detect_text_language
        raw_x_txt = (item.get("text") or item.get("title") or "").strip()
        x_lang = detect_text_language(raw_x_txt)
        content_type_lbl = "Complete X Post" if x_lang == "en" else "X Translation"
    else:
        content_type_lbl = "English Brief"

    generated = st.session_state["ondemand_generated"].get(cache_id)
    if not generated:
        with st.container(key="busy_pill"):
            _pr_ph = st.empty()
        with _pr_ph.status(_busy("prepare"), expanded=True) as status:
            def _gen_prog(msg: str, pct: float) -> None:
                status.update(label=f"{_busy('read')} {int(pct * 100)}%")
            generated = _generate_unified_item_content(item, is_x=is_x, on_progress=_gen_prog)
            status.update(label=f"{content_type_lbl} ready", state="complete", expanded=False)
            st.session_state["ondemand_generated"][cache_id] = generated
        _pr_ph.empty()

    if not generated or not generated.get("ok"):
        st.error((generated or {}).get("error") or "Could not generate English output for this item.")
        if st.button("", icon=":material/close:", key=f"dlg_sh_err_cls_{item_uid}", help="Close"):
            st.session_state["active_modal"] = None
            st.rerun()
        return

    src_url = generated.get("source_url", "") or item_link
    if not is_x and "news.google.com" in (src_url or "").lower():
        src_url = item_link
    profile_line = (generated.get("profile_line") or "").strip()
    gen_headline = "" if is_x else (generated.get("headline_english") or item.get("headline_english") or item.get("title") or "").strip()
    draft = st.session_state["share_drafts"].get(cache_id)
    if not draft:
        init_text = (generated.get("content") or "").strip()
        draft = {
            "original_headline": gen_headline,
            "saved_headline": gen_headline,
            "draft_headline": gen_headline,
            "original_content": init_text,
            "saved_content": init_text,
            "draft_content": init_text,
            "profile_line": profile_line,
            "source_url": src_url,
            "version": 1,
            "saved_at": "",
            "is_editing": False,
            "close_guard": False,
            "unsaved_send_warn": False,
        }
        st.session_state["share_drafts"][cache_id] = draft
    else:
        if not is_x and "saved_headline" not in draft:
            draft["original_headline"] = gen_headline
            draft["saved_headline"] = gen_headline
            draft["draft_headline"] = gen_headline
        if not is_x and "news.google.com" in (draft.get("source_url") or "").lower():
            draft["source_url"] = src_url

    if draft and draft.get("_just_saved"):
        st.toast(draft.pop("_just_saved"), icon=":material/bookmark_added:")

    ta_key = f"dlg_ta_edit_{item_uid}"
    hl_key = f"dlg_hl_edit_{item_uid}"
    if draft.get("is_editing"):
        if ta_key in st.session_state:
            draft["draft_content"] = str(st.session_state[ta_key] or "")
        if not is_x and hl_key in st.session_state:
            draft["draft_headline"] = str(st.session_state[hl_key] or "")

    saved_headline = "" if is_x else (draft.get("saved_headline") or "").strip()
    current_draft_headline = "" if is_x else (draft.get("draft_headline") or "").strip()
    saved_text = (draft.get("saved_content") or "").strip()
    current_draft_text = (draft.get("draft_content") or "").strip()
    has_unsaved = (current_draft_text != saved_text) or (not is_x and current_draft_headline != saved_headline)
    active_headline = current_draft_headline if (not is_x and current_draft_headline != saved_headline) else saved_headline
    active_text = current_draft_text if current_draft_text != saved_text else saved_text
    eff_profile = (draft.get("profile_line") or profile_line or "").strip()

    from nepal_summarizer import format_english_brief_payload

    def _fmt_payload(hl_txt: str, body_txt: str) -> str:
        if not is_x:
            return format_english_brief_payload(
                headline=hl_txt,
                brief=body_txt,
                source_url=src_url,
                whatsapp_bold=True,
            )
        pts = [body_txt] if body_txt else []
        if eff_profile:
            pts.append(f"_{eff_profile}_")
        if src_url:
            pts.append(f"Read Original Source: {src_url}")
        return "\n\n".join(pts)

    saved_formatted = _fmt_payload(saved_headline, saved_text)
    current_formatted = _fmt_payload(active_headline, active_text)

    from whatsapp_greenapi import get_share_targets
    _wa_targets = get_share_targets(is_x_post=is_x)
    _wa_grp_key = f"dlg_wa_grp_{item_uid}"
    if len(_wa_targets) == 1:
        selected_gid = _wa_targets[0]["id"]
        dest_name = _wa_targets[0]["name"]
    else:
        _target_by_name = {t["name"]: t["id"] for t in _wa_targets}
        _default_grp = st.session_state.get(_wa_grp_key)
        if _default_grp not in _target_by_name:
            _default_grp = _wa_targets[0]["name"]
        dest_name = _default_grp
        selected_gid = _target_by_name[dest_name]

    persisted_sent = _get_wa_sent_map().get(cache_id)
    ver = int(draft.get("version") or 1)
    saved_at = draft.get("saved_at") or ""

    status_pill = (
        '<span class="share-draft-pill share-draft-pill--unsaved">● Unsaved</span>'
        if has_unsaved
        else (
            f'<span class="share-draft-pill share-draft-pill--saved">✓ Saved v{ver} · {html.escape(saved_at)}</span>'
            if saved_at
            else f'<span class="share-draft-pill share-draft-pill--saved">Draft v{ver}</span>'
        )
    )
    sent_pill = ""
    if persisted_sent:
        gname_esc = html.escape(str(persisted_sent.get("group_name") or "WhatsApp"))
        ts_str = _format_wa_sent_time(persisted_sent.get("sent_at"))
        msg_id_esc = html.escape(str(persisted_sent.get("id_message") or ""))
        ts_txt = f" · {html.escape(ts_str)}" if ts_str else ""
        sent_pill = f'<span class="share-draft-pill share-draft-pill--sent" title="Message ID: {msg_id_esc}">✓ Sent to {gname_esc}{ts_txt}</span>'

    st.markdown('<div class="share-modal-anchor"></div>', unsafe_allow_html=True)
    _sh_eng = str(generated.get("translation_engine") or "").strip()
    _min_chips = (
        ('<span class="share-draft-pill share-draft-pill--unsaved" title="Unsaved changes">●</span>' if has_unsaved else "")
        + (
            f'<span class="share-draft-pill share-draft-pill--sent" title="Sent to {html.escape(str(persisted_sent.get("group_name") or "WhatsApp"), quote=True)} {html.escape(_format_wa_sent_time(persisted_sent.get("sent_at")) or "", quote=True)}">✓ Sent</span>'
            if persisted_sent else ""
        )
        + (
            f'<span class="lang-label" title="Translated via {html.escape(_sh_eng, quote=True)}">Translated via {html.escape(_sh_eng)}</span>'
            if _sh_eng else ""
        )
    )
    if _min_chips:
        st.markdown(f'<div class="share-modal-head"><span class="share-modal-pills">{_min_chips}</span></div>', unsafe_allow_html=True)

    if draft.get("is_editing"):
        if not is_x:
            edited_hl = st.text_input(
                "Headline (English)",
                value=draft.get("draft_headline") or "",
                key=hl_key,
            )
            draft["draft_headline"] = edited_hl or ""
            current_draft_headline = draft["draft_headline"].strip()
        edited_val = st.text_area(
            "Brief (English)" if not is_x else f"Edit {content_type_lbl}",
            value=draft["draft_content"],
            height=160,
            key=ta_key,
            label_visibility="visible" if not is_x else "collapsed",
        )
        draft["draft_content"] = edited_val or ""
        current_draft_text = draft["draft_content"].strip()
        has_unsaved = (current_draft_text != saved_text) or (not is_x and current_draft_headline != saved_headline)
        if src_url:
            st.markdown(_render_source_link_html(src_url, inline=True), unsafe_allow_html=True)
        st.markdown('<div class="editorial-edit-actions-anchor"></div>', unsafe_allow_html=True)
        ec1, ec2 = st.columns([1.2, 1], gap="small")
        with ec1:
            st.button(
                "Save Draft",
                icon=":material/save:",
                type="primary",
                key=f"dlg_save_edit_{item_uid}",
                help="Save draft without sending",
                on_click=_on_share_save,
                args=(cache_id, ta_key, "" if is_x else hl_key),
                use_container_width=True,
            )
        with ec2:
            st.button(
                "Discard Edits",
                icon=":material/close:",
                key=f"dlg_cancel_edit_{item_uid}",
                help="Discard unsaved edits",
                on_click=_on_share_cancel_edit,
                args=(cache_id,),
                use_container_width=True,
            )
        return

    headline_html = (
        f'<div class="unified-brief-box__headline">{html.escape(active_headline)}</div>'
        if (not is_x and active_headline)
        else ""
    )
    profile_html = f'<div class="unified-brief-box__profile">{html.escape(eff_profile)}</div>' if eff_profile else ""
    src_html = _render_source_link_html(src_url)
    st.markdown(
        f'<div class="unified-brief-box">'
        f'{headline_html}'
        f'<div class="unified-brief-box__body">{html.escape(active_text)}</div>'
        f'{profile_html}'
        f'{src_html}'
        f'</div>',
        unsafe_allow_html=True,
    )

    if draft.get("close_guard") and has_unsaved:
        st.warning("Save changes before closing?")
        g1, g2, g3 = st.columns(3, gap="small")
        with g1:
            if st.button("Save & Close", icon=":material/save:", type="primary", key=f"dlg_sc_{item_uid}"):
                _commit_share_draft(draft, current_draft_text, new_headline=(None if is_x else current_draft_headline))
                st.session_state["active_modal"] = None
                st.rerun()
        with g2:
            if st.button("Discard", icon=":material/delete_outline:", key=f"dlg_dc_{item_uid}"):
                draft["draft_content"] = draft["saved_content"]
                if not is_x:
                    draft["draft_headline"] = draft.get("saved_headline") or ""
                draft["close_guard"] = False
                st.session_state["active_modal"] = None
                st.rerun()
        with g3:
            st.button(
                "Keep Editing",
                icon=":material/edit:",
                key=f"dlg_ke_{item_uid}",
                on_click=_on_share_enter_edit,
                args=(cache_id,),
            )
        return

    if draft.get("unsaved_send_warn") and has_unsaved:
        st.warning("Unsaved edits exist. Save or discard them before sending.")
        u1, u2 = st.columns(2, gap="small")
        with u1:
            st.button(
                "Save Draft",
                icon=":material/save:",
                type="primary",
                key=f"dlg_sd_{item_uid}",
                on_click=_on_share_save,
                args=(cache_id, ""),
            )
        with u2:
            st.button(
                "Discard Edits",
                icon=":material/undo:",
                key=f"dlg_dd_{item_uid}",
                on_click=_on_share_discard_unsaved,
                args=(cache_id,),
            )

    _multi_wa = len(_wa_targets) > 1
    if _multi_wa:
        dest_name = _wa_dest_from_state(_wa_targets, _wa_grp_key)
        selected_gid = _target_by_name[dest_name]

    with st.container(key=f"wa_actions_{item_uid}"):
        _spec = [1, 1, 1] + ([1] if has_unsaved else [])
        _cols = st.columns(_spec, vertical_alignment="center", gap="small")
        with _cols[0]:
            _render_copy_button(current_formatted, uid=f"dlg_{item_uid}", icon_only=False)
        with _cols[1]:
            st.button(
                "Edit",
                icon=":material/edit:",
                key=f"dlg_edit_{item_uid}",
                help="Edit draft",
                on_click=_on_share_enter_edit,
                args=(cache_id,),
                width="stretch",
            )
        with _cols[2]:
            st.button(
                "Save",
                icon=":material/save:",
                key=f"dlg_save_bar_{item_uid}",
                disabled=not has_unsaved,
                help="Save current draft without sending" if has_unsaved else "All changes saved",
                on_click=_on_share_save,
                args=(cache_id, ""),
                width="stretch",
            )
        _ci = 3
        if has_unsaved:
            with _cols[_ci]:
                st.button(
                    "Close",
                    icon=":material/close:",
                    key=f"dlg_sh_cls_{item_uid}",
                    help="Close",
                    on_click=_on_share_req_close_guard,
                    args=(cache_id,),
                    width="stretch",
                )
            _ci += 1
        _render_share_send_fragment(
            cache_id=cache_id,
            item_uid=item_uid,
            dest_name=dest_name,
            selected_gid=selected_gid,
            item_link=item_link,
            has_unsaved=has_unsaved,
            ver=ver,
            saved_formatted=saved_formatted,
            targets=_wa_targets if _multi_wa else None,
        )


def render_feed_item_with_actions(
    item: Dict[str, Any],
    renderer: Callable[[Dict[str, Any]], str],
    state_key: str,
    item_uid: str,
) -> None:
    """Renders a compact, uniform feed card with three primary actions (Read in App, View Original, Share)."""
    st.session_state.setdefault("active_modal", None)
    st.session_state.setdefault("ondemand_generated", {})
    st.session_state.setdefault("ondemand_fulltext", {})

    is_indian, is_x = _resolve_item_flags(item, renderer)
    cache_id = _compute_item_uid(item, "global")

    item_link = (item.get("link") or "").strip()
    if is_x and not item_link:
        rh = (item.get("raw_handle") or item.get("handle") or "").lstrip("@").strip()
        sid = str(item.get("id") or "").strip()
        if rh and sid:
            item_link = f"https://x.com/{rh}/status/{sid}"

    with st.container(border=True):
        st.markdown('<div class="feed-card-anchor"></div>', unsafe_allow_html=True)
        if is_x:
            st.markdown(renderer(item), unsafe_allow_html=True)
        else:
            st.markdown(render_apple_article_card(item, is_indian=is_indian, show_tags=True), unsafe_allow_html=True)

        persisted_sent = _get_wa_sent_map().get(cache_id)
        if persisted_sent:
            sent_gname = html.escape(str(persisted_sent.get("group_name") or "WhatsApp"))
            sent_ts = _format_wa_sent_time(persisted_sent.get("sent_at"))
            sent_id = html.escape(str(persisted_sent.get("id_message") or ""))
            ts_part = f" · {html.escape(sent_ts)}" if sent_ts else ""
            st.markdown(
                f'<div class="wa-already-sent-notice" title="Green API Message ID: {sent_id}">'
                f'✓ Notice: Already sent to <strong>{sent_gname}</strong>{ts_part}'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.markdown('<div class="feed-action-divider"></div>', unsafe_allow_html=True)

        has_link = bool(item_link and item_link.startswith("http"))
        n_cols = (1 if not is_x else 0) + (1 if has_link else 0) + 1
        cols = st.columns(n_cols, gap="small")
        ci = 0
        if not is_x:
            with cols[ci]:
                if st.button(
                    "Read in App",
                    icon=":material/menu_book:",
                    key=f"btn_ft_{item_uid}",
                    help="Read complete article in a focused modal with optional English translation",
                ):
                    st.session_state["active_modal"] = {
                        "mode": "read",
                        "item": item,
                        "is_x": False,
                        "is_indian": is_indian,
                        "cache_id": cache_id,
                        "item_uid": item_uid,
                        "item_link": item_link,
                    }
                    _show_read_in_app_dialog()
            ci += 1
        if has_link:
            with cols[ci]:
                st.link_button("View Original", item_link, icon=":material/open_in_new:")
            ci += 1
        with cols[ci]:
            if st.button(
                "",
                icon=":material/share:",
                type="primary",
                key=f"btn_gen_{item_uid}",
                help="Share to WhatsApp: English brief to review, copy or send",
                width="stretch",
            ):
                st.session_state["active_modal"] = {
                    "mode": "share",
                    "item": item,
                    "is_x": is_x,
                    "is_indian": is_indian,
                    "cache_id": cache_id,
                    "item_uid": item_uid,
                    "item_link": item_link,
                }
                _show_share_dialog()


def _on_show_more_feed(state_key: str) -> None:
    st.session_state[state_key] = st.session_state.get(state_key, PAGE_SIZE) + PAGE_SIZE


def _on_load_more_db(fetch_limit_key: str, state_key: str) -> None:
    st.session_state[fetch_limit_key] = st.session_state.get(fetch_limit_key, 500) + 500
    st.session_state[state_key] = st.session_state.get(state_key, PAGE_SIZE) + PAGE_SIZE


def render_paginated_feed(
    items: List[Dict[str, Any]],
    state_key: str,
    renderer: Callable[[Dict[str, Any]], str],
    noun: str,
    total_db_count: int = None,
    loaded_count: int = None,
    fetch_limit_key: str = None,
) -> None:
    """Renders items PAGE_SIZE at a time with on-demand action controls and DB batch expansion."""
    st.session_state.setdefault(state_key, PAGE_SIZE)
    limit = st.session_state[state_key]
    seen_uids: Dict[str, int] = {}
    for it in items[:limit]:
        base_uid = _compute_item_uid(it, state_key)
        occ = seen_uids.get(base_uid, 0)
        seen_uids[base_uid] = occ + 1
        uid = base_uid if occ == 0 else f"{base_uid}_{occ}"
        render_feed_item_with_actions(it, renderer=renderer, state_key=state_key, item_uid=uid)

    remaining = len(items) - limit
    eff_loaded = loaded_count if loaded_count is not None else len(items)
    has_more_in_db = (
        total_db_count is not None
        and total_db_count > eff_loaded
        and bool(fetch_limit_key)
    )
    if remaining > 0:
        _, mid, _ = st.columns([1.5, 2, 1.5])
        with mid:
            st.button(
                f"Show {min(PAGE_SIZE, remaining)} more {noun}",
                width="stretch",
                key=f"btn_more_{state_key}",
                on_click=_on_show_more_feed,
                args=(state_key,),
            )
            if has_more_in_db:
                st.caption(f"Showing {limit:,} of {len(items):,} loaded {noun} ({total_db_count:,} total in window)")
            else:
                st.caption(f"Showing {limit:,} of {len(items):,} {noun}")
    elif has_more_in_db:
        _, mid, _ = st.columns([1.5, 2, 1.5])
        with mid:
            st.button(
                f"Load 500 more {noun} from database",
                width="stretch",
                key=f"btn_db_more_{state_key}",
                on_click=_on_load_more_db,
                args=(fetch_limit_key, state_key),
            )
            st.caption(f"Loaded {eff_loaded:,} of {total_db_count:,} total {noun} in window")
    elif items:
        st.caption(f"You're all caught up · {len(items):,} {noun}")


def _safe_http_url(raw_url: str) -> str:
    """Validates URL scheme to prevent unsafe javascript:/data: links."""
    u = (raw_url or "").strip()
    if not u:
        return ""
    try:
        parsed = urllib.parse.urlparse(u)
        if parsed.scheme.lower() in ("http", "https") and parsed.netloc:
            return u
    except Exception:
        pass
    return ""


def _mark_feed_card_sent(cache_id: str, group_name: str) -> None:
    """Shows the sent tick on the card right away by patching the stored feed HTML and forcing a full re-send."""
    chip = (
        f'<span class="hl-chip hl-chip--ok" title="Sent to {html.escape(group_name or "WhatsApp", quote=True)}">{_HL_CHECK_SVG}</span>'
    )
    for sess in (st.session_state.get("feed_sessions") or {}).values():
        if not isinstance(sess, dict):
            continue
        changed = False
        for uid, row in (sess.get("items_by_uid") or {}).items():
            if _compute_item_uid(row, "global") != cache_id:
                continue
            marker = f'data-uid="{uid}"'
            for b in sess.get("batches", []):
                h = b.get("html", "")
                i = h.find(marker)
                if i < 0:
                    continue
                j = h.find("<!--sent-->", i)
                nxt = h.find('class="feed-card-wrap"', i + len(marker))
                if j >= 0 and (nxt < 0 or j < nxt):
                    b["html"] = h[:j] + chip + h[j + len("<!--sent-->"):]
                    b["rev"] = int(b.get("rev", 0)) + 1
                    changed = True
        if changed:
            sess["_mounted_nav_seq"] = -1


def _build_card_wrapper_html(
    item: Dict[str, Any],
    renderer: Callable[[Dict[str, Any]], str],
    item_uid: str,
    wa_sent_map: Dict[str, Dict[str, Any]],
) -> str:
    """Builds a single sanitized card HTML block reusing existing card renderers."""
    is_indian, is_x = _resolve_item_flags(item, renderer)
    cache_id = _compute_item_uid(item, "global")
    if is_x:
        _x_sent = wa_sent_map.get(cache_id)
        _x_sent_title = ""
        if _x_sent:
            _xg = str(_x_sent.get("group_name") or "WhatsApp")
            _xt = _format_wa_sent_time(_x_sent.get("sent_at"))
            _x_sent_title = f"Sent to {_xg}" + (f" · {_xt}" if _xt else "")
        card_html = render_apple_x_post_card(item, show_footer=False, sent_title=_x_sent_title)
        tags_html = _render_x_metrics_html(item)
    else:
        persisted_for_chip = wa_sent_map.get(cache_id)
        sent_title = ""
        if persisted_for_chip:
            _g = str(persisted_for_chip.get("group_name") or "WhatsApp")
            _t = _format_wa_sent_time(persisted_for_chip.get("sent_at"))
            sent_title = f"Sent to {_g}" + (f" · {_t}" if _t else "")
        card_html = render_headline_card(item, is_indian=is_indian, sent_title=sent_title)
        tags_html = ""

    wa_html = ""
    persisted_sent = None
    if persisted_sent:
        sent_gname = html.escape(str(persisted_sent.get("group_name") or "WhatsApp"))
        sent_ts = _format_wa_sent_time(persisted_sent.get("sent_at"))
        sent_id = html.escape(str(persisted_sent.get("id_message") or ""))
        ts_part = f" · {html.escape(sent_ts)}" if sent_ts else ""
        wa_html = (
            f'<div class="wa-already-sent-notice" title="Green API Message ID: {sent_id}">'
            f'✓ Sent to <strong>{sent_gname}</strong>{ts_part}'
            f'</div>'
        )

    item_link = _safe_http_url(item.get("link") or "")
    if is_x and not item_link:
        rh = (item.get("raw_handle") or item.get("handle") or "").lstrip("@").strip()
        sid = str(item.get("id") or "").strip()
        if rh and sid:
            item_link = _safe_http_url(f"https://x.com/{rh}/status/{sid}")

    btns: List[str] = []
    if not is_x:
        btns.append(
            f'<button type="button" class="feed-btn" data-action="read" data-uid="{html.escape(item_uid, quote=True)}" '
            f'aria-label="Read in App" title="Read the full article, with optional English translation">'
            f'<span class="ico-swap" aria-hidden="true"><svg class="ico-read" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 5.5A1.5 1.5 0 0 1 3.5 4H10a2 2 0 0 1 2 2v14a2 2 0 0 0-2-2H3.5A1.5 1.5 0 0 1 2 16.5z"/><path d="M22 5.5A1.5 1.5 0 0 0 20.5 4H14a2 2 0 0 0-2 2v14a2 2 0 0 1 2-2h6.5a1.5 1.5 0 0 0 1.5-1.5z"/></svg><svg class="ico-translate" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 8 6 6"/><path d="m4 14 6-6 2-3"/><path d="M2 5h12"/><path d="M7 2h1"/><path d="m22 22-5-10-5 10"/><path d="M14 18h6"/></svg></span></button>'
        )
    if item_link:
        btns.append(
            f'<a class="feed-btn" href="{html.escape(item_link, quote=True)}" target="_blank" rel="noopener noreferrer" '
            f'aria-label="Open original source" title="Open original publisher article">'
            f'<svg width="16" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 17 17 7M8 7h9v9"/></svg></a>'
        )
    btns.append(
        f'<button type="button" class="feed-btn feed-btn--wa" data-action="share" data-uid="{html.escape(item_uid, quote=True)}" '
        f'aria-label="Share to WhatsApp" title="Share to WhatsApp: English brief to review, copy or send">'
        f'{_WA_SVG}</button>'
    )
    return (
        f'<div class="feed-card-wrap" data-uid="{html.escape(item_uid, quote=True)}">'
        f'{card_html}{wa_html}'
        f'<footer class="feed-card-footer" role="toolbar" aria-label="Story actions">'
        f'{tags_html}'
        f'<div class="feed-card-actions">{"".join(btns)}</div>'
        f'</footer>'
        f'</div>'
    )


@st.cache_data(ttl=90, show_spinner=False)
def _get_cached_feed_page_with_count(
    workspace: str,
    start_iso: str,
    end_iso: str,
    snap_iso: str,
    stream_filter: str,
    category_filter: str,
    source: str,
    language: str,
    author_type: str,
    search_query: str,
    sort_mode: str,
    limit: int = PAGE_SIZE,
    platform: str = "",
    data_version: int = 0,
) -> Dict[str, Any]:
    """Cached 90s initial page + exact filtered total count in ONE SQL round-trip."""
    s_dt = datetime.datetime.fromisoformat(start_iso) if start_iso else None
    e_dt = datetime.datetime.fromisoformat(end_iso) if end_iso else None
    sn_dt = datetime.datetime.fromisoformat(snap_iso) if snap_iso else None
    plat_val = None
    if platform and platform.lower() not in ("all", "all platforms"):
        plat_val = "facebook" if "facebook" in platform.lower() else "x"
    res = get_feed_page_with_count(
        workspace=workspace,
        start_dt=s_dt,
        end_dt=e_dt,
        snapshot_ingested_at=sn_dt,
        stream_filter=stream_filter,
        category_filter=category_filter,
        source=(None if not source or source in (ALL_PORTALS_DEFAULT, ALL_INDIAN_DEFAULT) else source),
        language=(None if not language or language == ALL_LANG_DEFAULT else language),
        author_type=author_type,
        search_query=search_query,
        sort_asc=(sort_mode == "Oldest First"),
        sort_mode=sort_mode,
        limit=limit,
        include_count=True,
        include_new_count=False,
        platform=plat_val,
    )
    now_curr = datetime.datetime.now(NEPAL_TZ)
    cleaned: List[Dict[str, Any]] = []
    for r in res.get("rows", []):
        pdt = r.get("published_dt")
        if isinstance(pdt, datetime.datetime):
            _, r["relative_time"], r["exact_time"] = parse_to_nepal_time(pdt, now_curr)
        if in_window(r, s_dt, e_dt):
            cleaned.append(r)
    res["rows"] = cleaned
    return res


@st.cache_data(ttl=60, show_spinner=False)
def _get_cached_filtered_count(
    workspace: str,
    start_iso: str,
    end_iso: str,
    snap_iso: str,
    stream_filter: str,
    category_filter: str,
    source: str,
    language: str,
    author_type: str,
    search_query: str,
    data_version: int = 0,
) -> Dict[str, int]:
    """Cached 60s filtered total + new-since-snapshot delta count."""
    s_dt = datetime.datetime.fromisoformat(start_iso) if start_iso else None
    e_dt = datetime.datetime.fromisoformat(end_iso) if end_iso else None
    sn_dt = datetime.datetime.fromisoformat(snap_iso) if snap_iso else None
    return get_filtered_feed_count(
        workspace=workspace,
        start_dt=s_dt,
        end_dt=e_dt,
        snapshot_ingested_at=sn_dt,
        stream_filter=stream_filter,
        category_filter=category_filter,
        source=(None if not source or source in (ALL_PORTALS_DEFAULT, ALL_INDIAN_DEFAULT) else source),
        language=(None if not language or language == ALL_LANG_DEFAULT else language),
        author_type=author_type,
        search_query=search_query,
    )


def _fetch_workspace_keyset_page(
    workspace: str,
    start_dt: datetime.datetime,
    end_dt: datetime.datetime,
    snapshot_ingested_at: datetime.datetime,
    cursor: Any,
    stream_filter: str = "All Sources",
    category_filter: str = CAT_FILTER_ALL_UNFILTERED,
    source: str = "",
    language: str = "",
    author_type: str = "",
    search_query: str = "",
    sort_mode: str = "Newest First",
    limit: int = PAGE_SIZE,
    platform: str = "",
) -> List[Dict[str, Any]]:
    """Fetches a single 20-item keyset page from Supabase for the given workspace."""
    now_curr = datetime.datetime.now(NEPAL_TZ)
    c_dt = None
    c_rank = None
    c_id = None
    c_metric = None
    if workspace == "live":
        c_dt, c_rank, c_id = cursor if cursor else (None, None, None)
    elif workspace == "x":
        c_metric, c_dt, c_id = cursor if cursor else (None, None, None)
    else:
        c_dt, c_id = cursor if cursor else (None, None)

    plat_val = None
    if platform and platform.lower() not in ("all", "all platforms"):
        plat_val = "facebook" if "facebook" in platform.lower() else "x"

    res = get_feed_page_with_count(
        workspace=workspace,
        start_dt=start_dt,
        end_dt=end_dt,
        snapshot_ingested_at=snapshot_ingested_at,
        stream_filter=stream_filter,
        category_filter=category_filter,
        source=(None if not source or source in (ALL_PORTALS_DEFAULT, ALL_INDIAN_DEFAULT) else source),
        language=(None if not language or language == ALL_LANG_DEFAULT else language),
        author_type=author_type,
        search_query=search_query,
        sort_asc=(sort_mode == "Oldest First"),
        sort_mode=sort_mode,
        cursor_dt=c_dt,
        cursor_rank=c_rank,
        cursor_id=c_id,
        cursor_metric=c_metric,
        limit=limit,
        include_count=False,
        include_new_count=False,
        platform=plat_val,
    )
    rows = res.get("rows", [])
    for r in rows:
        pdt = r.get("published_dt")
        if isinstance(pdt, datetime.datetime):
            _, r["relative_time"], r["exact_time"] = parse_to_nepal_time(pdt, now_curr)
    return [r for r in rows if in_window(r, start_dt, end_dt)]


def _extract_next_cursor(workspace: str, rows: List[Dict[str, Any]], sort_mode: str) -> Any:
    if not rows:
        return None
    last = rows[-1]
    pdt = last.get("published_dt")
    if workspace == "live":
        return (pdt, last.get("_stream_rank", 1), str(last.get("_cursor_id") or last.get("canonical_id") or last.get("id") or ""))
    if workspace == "x":
        m_key = {"Most engagement": "engagement_score", "Most liked": "likes", "Most reposted": "retweets"}.get(sort_mode)
        if m_key:
            m_val = int(last.get(m_key, 0) or 0) if last.get("is_real_api", True) else -1
        else:
            m_val = None
        return (m_val, pdt, str(last.get("id") or ""))
    return (pdt, str(last.get("canonical_id") or ""))


def _safe_fragment_rerun() -> None:
    """Reruns the current fragment when inside a fragment rerun, falling back to a full rerun during full script runs."""
    try:
        from streamlit.errors import StreamlitInvalidLayoutContextError
        st.rerun(scope="fragment")
    except StreamlitInvalidLayoutContextError:
        st.rerun()


def _floor_60s(dt: datetime.datetime) -> datetime.datetime:
    return dt.replace(second=0, microsecond=0)


def render_infinite_workspace_feed(
    workspace: str,
    renderer: Callable[[Dict[str, Any]], str],
    noun: str,
    filter_sig: str,
    stream_filter: str = "All Sources",
    category_filter: str = CAT_FILTER_ALL_UNFILTERED,
    source: str = "",
    language: str = "",
    author_type: str = "",
    search_query: str = "",
    sort_mode: str = "Newest First",
    empty_icon: str = "📰",
    empty_title: str = "No items found",
    empty_body: str = "Try widening the timeframe or adjusting filters.",
    on_fetch_now: Optional[Callable[[], None]] = None,
    wa_sent_map: Optional[Dict[str, Dict[str, Any]]] = None,
    prefetched_init: Optional[Dict[str, Any]] = None,
    platform: str = "",
) -> Dict[str, int]:
    """
    Shared incremental infinite-scroll feed engine across Live Feed, Nepali Media, Indian Press, and X.
    Single-pass keyset pagination, incremental delta payloads, and strict timeframe snapshot pinning.
    """
    data_ver = int(st.session_state.get("data_version", 0))
    sessions = st.session_state.setdefault("feed_sessions", {})
    sess = sessions.get(workspace)

    current_nav_seq = int(st.session_state.get("_nav_visit_seq", 1))
    need_full_payload = False
    just_appended_batch: Optional[Dict[str, Any]] = None

    if not sess or sess.get("filter_sig") != filter_sig:
        if prefetched_init and prefetched_init.get("snapshot_end_dt"):
            snap_start = prefetched_init.get("snapshot_start_dt") or filter_start_dt
            snap_end = prefetched_init["snapshot_end_dt"]
            snap_ing = prefetched_init.get("snapshot_ingested_at") or snap_end
        else:
            snap_start = filter_start_dt
            snap_end = filter_end_dt
            snap_ing = datetime.datetime.now(NEPAL_TZ)
        sess = {
            "filter_sig": filter_sig,
            "session_key": f"{workspace}_{filter_sig}_{int(snap_ing.timestamp() * 1000)}",
            "snapshot_start_dt": snap_start,
            "snapshot_end_dt": snap_end,
            "snapshot_ingested_at": snap_ing,
            "cursor": None,
            "batches": [],
            "items_by_uid": {},
            "seen_keys": set(),
            "total_count": 0,
            "has_more": False,
            "error_msg": "",
            "last_event_ts": 0,
            "_mounted_nav_seq": -1,
        }
        sessions[workspace] = sess
        need_full_payload = True

    if sess.get("_mounted_nav_seq") != current_nav_seq:
        need_full_payload = True

    eff_wa_map = wa_sent_map if wa_sent_map is not None else _get_wa_sent_map()

    def _append_batch(rows: List[Dict[str, Any]], seq_idx: int) -> Dict[str, Any]:
        html_parts: List[str] = []
        for r in rows:
            dedup_key = (
                r.get("_feed_type", workspace),
                str(r.get("canonical_id") or r.get("id") or r.get("link") or ""),
            )
            if dedup_key in sess["seen_keys"]:
                continue
            sess["seen_keys"].add(dedup_key)
            uid = f"{workspace}_{seq_idx}_{len(sess['items_by_uid'])}"
            sess["items_by_uid"][uid] = r
            html_parts.append(_build_card_wrapper_html(r, renderer=renderer, item_uid=uid, wa_sent_map=eff_wa_map))
        batch_obj = {"seq": seq_idx, "html": "".join(html_parts)}
        sess["batches"].append(batch_obj)
        return batch_obj

    # Initial 20-item + exact filtered count fetch in 1 SQL round-trip
    if not sess["batches"] and not sess["error_msg"]:
        try:
            if prefetched_init is not None:
                init_res = prefetched_init
            else:
              with st.spinner(_busy("feed", noun)):
                init_res = _get_cached_feed_page_with_count(
                    workspace=workspace,
                    start_iso=sess["snapshot_start_dt"].isoformat(),
                    end_iso=sess["snapshot_end_dt"].isoformat(),
                    snap_iso=sess["snapshot_ingested_at"].isoformat(),
                    stream_filter=stream_filter,
                    category_filter=category_filter,
                    source=source,
                    language=language,
                    author_type=author_type,
                    search_query=search_query or "",
                    sort_mode=sort_mode,
                    limit=PAGE_SIZE,
                    platform=platform,
                    data_version=data_ver,
                )
            first_rows = init_res.get("rows", [])
            tot_cnt = init_res.get("total_count")
            sess["total_count"] = int(tot_cnt) if tot_cnt is not None else len(first_rows)
            if first_rows:
                _append_batch(first_rows, 0)
                sess["cursor"] = _extract_next_cursor(workspace, first_rows, sort_mode)
                sess["has_more"] = len(first_rows) == PAGE_SIZE and len(sess["items_by_uid"]) < max(sess["total_count"], len(first_rows))
            else:
                sess["has_more"] = False
            need_full_payload = True
        except Exception as exc:
            sess["error_msg"] = f"Failed to load {noun}: {type(exc).__name__}"

    # Read component widget event BEFORE rendering component -> single-pass load_more & action handling!
    _last_ts_map = st.session_state.setdefault("inf_feed_last_ts", {})
    _last_ts = int(_last_ts_map.get(workspace) or 0)
    pre_ev = st.session_state.get(f"inf_feed_{workspace}")
    handled_ev_type = None
    modal_action_requested: Optional[Dict[str, Any]] = None

    def _process_component_event(ev_obj: Any, is_pre_pass: bool) -> None:
        nonlocal need_full_payload, just_appended_batch, handled_ev_type, modal_action_requested, _last_ts
        if not isinstance(ev_obj, dict):
            return
        ev_ts = int(ev_obj.get("ts") or 0)
        if ev_ts <= _last_ts:
            return
        _last_ts_map[workspace] = ev_ts
        _last_ts = ev_ts
        sess["last_event_ts"] = ev_ts
        ev_type = ev_obj.get("event")
        handled_ev_type = ev_type

        if ev_type == "sync_all":
            need_full_payload = True
            if not is_pre_pass:
                _safe_fragment_rerun()
        elif ev_type in ("load_more", "retry") and sess["has_more"]:
            next_seq = len(sess["batches"])
            if int(ev_obj.get("next_seq", -1)) == next_seq:
                try:
                    more_rows = _fetch_workspace_keyset_page(
                        workspace=workspace,
                        start_dt=sess["snapshot_start_dt"],
                        end_dt=sess["snapshot_end_dt"],
                        snapshot_ingested_at=sess["snapshot_ingested_at"],
                        cursor=sess["cursor"],
                        stream_filter=stream_filter,
                        category_filter=category_filter,
                        source=source,
                        language=language,
                        author_type=author_type,
                        search_query=search_query,
                        sort_mode=sort_mode,
                        limit=PAGE_SIZE,
                        platform=platform,
                    )
                    sess["error_msg"] = ""
                    if more_rows:
                        new_batch = _append_batch(more_rows, next_seq)
                        just_appended_batch = new_batch
                        sess["cursor"] = _extract_next_cursor(workspace, more_rows, sort_mode)
                        sess["has_more"] = len(more_rows) == PAGE_SIZE and len(sess["items_by_uid"]) < max(sess["total_count"], len(sess["items_by_uid"]))
                    else:
                        sess["has_more"] = False
                except Exception as exc:
                    sess["error_msg"] = f"Could not load next {noun} ({type(exc).__name__})."
                if not is_pre_pass:
                    _safe_fragment_rerun()
        elif ev_type == "action":
            uid = str(ev_obj.get("item_uid") or "")
            target_item = sess["items_by_uid"].get(uid)
            if target_item:
                is_indian, is_x = _resolve_item_flags(target_item, renderer)
                cache_id = _compute_item_uid(target_item, "global")
                item_link = _safe_http_url(target_item.get("link") or "")
                st.session_state["active_modal"] = {
                    "mode": ev_obj.get("action"),
                    "item": target_item,
                    "is_x": is_x,
                    "is_indian": is_indian,
                    "cache_id": cache_id,
                    "item_uid": uid,
                    "item_link": item_link,
                }
                st.session_state["_active_modal_opened"] = False
                modal_action_requested = {"action": ev_obj.get("action"), "is_x": is_x}

    _process_component_event(pre_ev, is_pre_pass=True)

    # Check for newly ingested stories since snapshot (throttled to 60s cache buckets, skipped during active scroll/action)
    new_since_snap = 0
    _snap_age_secs = (datetime.datetime.now(NEPAL_TZ) - sess["snapshot_ingested_at"]).total_seconds()
    if is_to_current and sess["batches"] and _snap_age_secs >= 8 and handled_ev_type not in ("load_more", "retry", "action", "sync_all"):
        try:
            delta_now_bucket = _floor_60s(datetime.datetime.now(NEPAL_TZ))
            delta_info = _get_cached_filtered_count(
                workspace=workspace,
                start_iso=sess["snapshot_start_dt"].isoformat(),
                end_iso=delta_now_bucket.isoformat(),
                snap_iso=sess["snapshot_ingested_at"].isoformat(),
                stream_filter=stream_filter,
                category_filter=category_filter,
                source=source,
                language=language,
                author_type=author_type,
                search_query=search_query or "",
                data_version=data_ver,
            )
            new_since_snap = int(delta_info.get("new_since_snapshot", 0) or 0)
        except Exception:
            new_since_snap = 0

    if new_since_snap > 0:
        with st.container(key="new_stories_pill"):
            _new_clicked = st.button(f"{new_since_snap:,} new", icon=":material/arrow_upward:", key=f"btn_new_stories_{workspace}", help=f"{new_since_snap:,} new {noun}")
        if _new_clicked:
            st.session_state["_scroll_top_once"] = True
            sessions.pop(workspace, None)
            _get_cached_feed_page_with_count.clear()
            _get_cached_filtered_count.clear()
            get_cached_header_bundle.clear()
            get_cached_login_bootstrap.clear()
            _get_cached_indian_workspace_bootstrap.clear()
            _get_cached_x_workspace_bootstrap.clear()
            st.session_state.pop("_hdr_state_cache", None)
            sv = st.session_state.setdefault("stream_versions", {"nepali": 0, "indian": 0, "x": 0})
            for sk in (("nepali", "indian", "x") if workspace == "live" else (workspace,)):
                if sk in sv:
                    sv[sk] = int(sv.get(sk, 0)) + 1
            st.session_state["data_version"] = data_ver + 1
            st.rerun()


    if st.session_state.pop("_scroll_top_once", False):
        components.html(
            "<script>try{const d=window.parent.document;const m=d.querySelector('[data-testid=\"stMain\"]')||d.scrollingElement;m.scrollTo({top:0,behavior:'smooth'});}catch(e){}</script>",
            height=0,
        )

    if not sess["batches"] and not sess["error_msg"]:
        render_empty_state(empty_icon, empty_title, empty_body)
        if on_fetch_now is not None:
            _, mid_col, _ = st.columns([1.5, 2, 1.5])
            with mid_col:
                if st.button("Fetch Now", icon=":material/sync:", key=f"btn_fetch_now_{workspace}", width="stretch"):
                    on_fetch_now()
                    sessions.pop(workspace, None)
                    _get_cached_feed_page_with_count.clear()
                    _get_cached_filtered_count.clear()
                    get_cached_header_bundle.clear()
                    get_cached_login_bootstrap.clear()
                    _get_cached_indian_workspace_bootstrap.clear()
                    _get_cached_x_workspace_bootstrap.clear()
                    st.session_state.pop("_hdr_state_cache", None)
                    sv = st.session_state.setdefault("stream_versions", {"nepali": 0, "indian": 0, "x": 0})
                    for sk in (("nepali", "indian", "x") if workspace == "live" else (workspace,)):
                        if sk in sv:
                            sv[sk] = int(sv.get(sk, 0)) + 1
                    st.session_state["data_version"] = data_ver + 1
                    st.rerun()
        return {"total_count": 0, "loaded_count": 0, "new_since_snapshot": 0}

    loaded_count = len(sess["items_by_uid"])
    if need_full_payload:
        batches_to_send = sess["batches"]
        theme_css_to_send = FEED_CARD_CSS + theme_override_css(_THEME_MODE)
        sess["_mounted_nav_seq"] = current_nav_seq
    elif just_appended_batch is not None:
        batches_to_send = [just_appended_batch]
        theme_css_to_send = ""
    else:
        batches_to_send = []
        theme_css_to_send = ""

    if sess.get("error_msg"):
        st.warning(f"⚠️ {sess['error_msg']}. Showing cached data or retry shortly.", icon=":material/wifi_off:")

    ev = render_infinite_feed_component(
        session_key=sess["session_key"],
        batches=batches_to_send,
        has_more=sess["has_more"],
        total_count=max(sess["total_count"], loaded_count),
        loaded_count=loaded_count,
        noun=noun,
        theme_css=theme_css_to_send,
        error_msg=sess["error_msg"],
        key=f"inf_feed_{workspace}",
    )

    if modal_action_requested is None:
        _process_component_event(ev, is_pre_pass=False)

    active_m = st.session_state.get("active_modal")
    if active_m and not st.session_state.get("_active_modal_opened"):
        st.session_state["_active_modal_opened"] = True
        m_mode = active_m.get("mode")
        m_is_x = bool(active_m.get("is_x", False))
        if m_mode == "read" and not m_is_x:
            _show_read_in_app_dialog()
        elif m_mode == "share":
            _show_share_dialog()

    return {
        "total_count": max(sess["total_count"], loaded_count),
        "loaded_count": loaded_count,
        "new_since_snapshot": new_since_snap,
    }

# ==========================================
# BILINGUAL & CROSS-LINGUAL SEARCH ENGINE (uses shared SEARCH_EXPANSIONS from nepal_news_store)
# ==========================================
def smart_search_match(item: Dict[str, Any], query: str) -> bool:
    """
    High-performance bilingual, multi-token matching function.
    Searches across title, summary, translated headlines, source outlet,
    author name, handle, role, category, and sentiment.
    """
    groups = expand_search_tokens(query or "")
    if not groups:
        return True

    parts = [
        item.get("title", ""),
        item.get("headline_english", ""),
        item.get("summary", ""),
        item.get("text", ""),
        item.get("source", ""),
        item.get("author_name", ""),
        item.get("handle", ""),
        item.get("role", ""),
        item.get("structured_category", ""),
        item.get("language", ""),
    ]
    text_corpus = " ".join(str(p) for p in parts if p).lower()
    return all(any(syn in text_corpus for syn in synonyms) for synonyms in groups)

# ==========================================
# UNIFIED GLOBAL FILTER PIPELINE
# ==========================================
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
# 5. NAVIGATION & TOP BAR (Zero-Sidebar Gemini-Style Main Canvas)
# ==========================================
NAV_ITEMS = [
    ("Live Feed", "🌐"),
    ("Nepali Media", "📰"),
    ("Indian Press", "🇮🇳"),
    ("Social Media", "💬"),
    ("Analytics & Export", "📈"),
    ("System Health", "🩺"),
]
_NAV_ICON_MAP = dict(NAV_ITEMS)
_NAV_ICON_MAP["X"] = "💬"


def nav_label(name: str) -> str:
    return f"{_NAV_ICON_MAP.get(name, '')}  {name}"


def _resolve_nav_from_query_param() -> str:
    param_nav = str(st.query_params.get("nav", "") or "").strip().lower()
    if not param_nav:
        return "Live Feed"
    if param_nav in ("x", "twitter", "social", "social media"):
        return "Social Media"
    for n, _ in NAV_ITEMS:
        if n.lower() == param_nav or (param_nav == "x" and n == "X") or (param_nav in ("live", "feed", "unified", "combined") and "Live" in n):
            return n
    return "Live Feed"


def _select_workspace(name: str) -> None:
    st.session_state["app_nav_section"] = name
    st.query_params["nav"] = name


if "app_nav_section" not in st.session_state:
    st.session_state["app_nav_section"] = _resolve_nav_from_query_param()
selected_nav = st.session_state["app_nav_section"]
if st.query_params.get("nav") != selected_nav:
    st.query_params["nav"] = selected_nav

st.session_state.setdefault("data_version", 0)
if st.session_state.get("_last_rendered_nav") != selected_nav:
    st.session_state["_nav_visit_seq"] = int(st.session_state.get("_nav_visit_seq", 0)) + 1
    st.session_state["_last_rendered_nav"] = selected_nav

st.session_state.setdefault("committed_search_query", "")
_active_sq = st.session_state.get("committed_search_query", "")
_data_ver = int(st.session_state.get("data_version", 0))

# Check per-stream incremental sync completion & invalidate ONLY completed stream(s)
_sync_snap = get_manual_sync_status()
_seen_stream_seqs = st.session_state.setdefault("_seen_stream_seqs", {"nepali": 0, "indian": 0, "x": 0})
_snap_stream_seqs = _sync_snap.get("stream_seqs") or {}
_changed_streams = [
    s_name for s_name in ("nepali", "indian", "x")
    if int(_snap_stream_seqs.get(s_name, 0)) > int(_seen_stream_seqs.get(s_name, 0))
]
if _changed_streams:
    _sess_map = st.session_state.get("feed_sessions")
    for s_name in _changed_streams:
        # Do NOT bump _stream_vers here: it is part of each feed's filter signature and would reset the user's scroll.
        # New stories surface through the floating "N new" pill instead.
        _seen_stream_seqs[s_name] = int(_snap_stream_seqs.get(s_name, 0))
    _v_np = int(_stream_vers.get("nepali", 0))
    _v_in = int(_stream_vers.get("indian", 0))
    _v_x = int(_stream_vers.get("x", 0))
    _v_live = _v_np + _v_in + _v_x
    _data_ver += 1
    st.session_state["data_version"] = _data_ver
    st.session_state["last_sync_npt"] = datetime.datetime.now(NEPAL_TZ).strftime("%I:%M %p").lstrip("0")
    st.session_state.pop("_hdr_state_cache", None)
    get_cached_header_bundle.clear()
    get_cached_login_bootstrap.clear()
    _get_cached_feed_page_with_count.clear()
    _get_cached_filtered_count.clear()
    if "nepali" in _changed_streams:
        get_active_nepal_articles.clear()
    if "indian" in _changed_streams:
        get_active_indian_articles.clear()
        _get_cached_indian_workspace_bootstrap.clear()
        _get_cached_indian_source_health.clear()
    if "x" in _changed_streams:
        st.session_state.pop("x_posts", None)
        get_active_x_posts.clear()
        _get_cached_x_workspace_bootstrap.clear()
    get_cached_analytics_bundle.clear()

_seen_sync_seq = int(st.session_state.get("_seen_sync_seq", 0))
if not _sync_snap.get("running") and int(_sync_snap.get("completed_seq", 0)) > _seen_sync_seq:
    st.session_state["_seen_sync_seq"] = int(_sync_snap["completed_seq"])
    pass

# Cold login 1-query bootstrap when Live Feed needs initial load; cached header otherwise
_prefetched_live_init = None
_prefetched_live_sig = None
_hdr_cache_key = (active_preset, _tf_epoch, filter_start_dt.isoformat(), filter_end_dt.isoformat(), _data_ver)
_hdr_cached_entry = st.session_state.get("_hdr_state_cache")
_live_sess_existing = st.session_state.get("feed_sessions", {}).get("live")
if selected_nav == "Live Feed" and not _live_sess_existing:
    _boot_cat = st.session_state.get("comb_cat_filter", CAT_FILTER_ALL_UNFILTERED)
    _boot_sort = st.session_state.get("comb_sort_mode", "Newest First")
    _boot = get_cached_login_bootstrap(
        start_iso=cache_start_dt.isoformat(),
        end_iso=cache_end_dt.isoformat() if cache_end_dt else "",
        live_start_iso=filter_start_dt.isoformat(),
        live_end_iso=filter_end_dt.isoformat(),
        live_stream="All Sources",
        live_cat=_boot_cat,
        live_sort=_boot_sort,
        search_query=_active_sq or "",
        data_version=_data_ver,
    )
    _hdr_bundle = _boot.get("header") or {"counts": {"nepali_count": 0, "indian_count": 0, "x_count": 0}, "wa_sent_map": {}}
    st.session_state["_hdr_state_cache"] = {"key": _hdr_cache_key, "ts": time.time(), "data": _hdr_bundle}
    _prefetched_live_init = _boot.get("live_page")
    _prefetched_live_sig = f"live|{active_preset}|tf{_tf_epoch}|v{_v_live}|All Sources|{_boot_cat}|{_boot_sort}|{_active_sq or ''}"
elif (
    isinstance(_hdr_cached_entry, dict)
    and _hdr_cached_entry.get("key") == _hdr_cache_key
    and (time.time() - float(_hdr_cached_entry.get("ts") or 0.0)) < 120.0
):
    _hdr_bundle = _hdr_cached_entry["data"]
else:
    _hdr_bundle = get_cached_header_bundle(start_dt=cache_start_dt, end_dt=cache_end_dt, data_version=_data_ver)
    st.session_state["_hdr_state_cache"] = {"key": _hdr_cache_key, "ts": time.time(), "data": _hdr_bundle}

stream_counts = _hdr_bundle.get("counts", {"nepali_count": 0, "indian_count": 0, "x_count": 0})
_shared_wa_sent_map = _hdr_bundle.get("wa_sent_map")
total_combined_count = (
    stream_counts.get("nepali_count", 0) +
    stream_counts.get("indian_count", 0) +
    stream_counts.get("x_count", 0)
)


@st.dialog("Search", width="small", icon=":material/search:")
def _show_search_dialog() -> None:
    with st.form("dialog_search_form", border=False):
        q_val = st.text_input(
            "Search",
            value=st.session_state.get("committed_search_query", ""),
            placeholder="Type keywords, leaders, topics and press Enter…",
            label_visibility="collapsed",
            icon=":material/search:",
        )
        sc1, sc2 = st.columns([3, 1], gap="small")
        with sc1:
            submitted = st.form_submit_button("Search", icon=":material/search:", type="primary", width="stretch")
        with sc2:
            cleared = st.form_submit_button("Clear", width="stretch")
        if submitted:
            st.session_state["committed_search_query"] = (q_val or "").strip()
            st.rerun()
        if cleared:
            st.session_state["committed_search_query"] = ""
            st.rerun()

# ==========================================
# EDITORIAL UNDERLINE TOP NAVBAR (Concept C)
# ==========================================
_ws_counts = {
    "Live Feed": total_combined_count,
    "Nepali Media": stream_counts.get("nepali_count", 0),
    "Indian Press": stream_counts.get("indian_count", 0),
    "Social Media": stream_counts.get("x_count", 0),
    "X": stream_counts.get("x_count", 0),
}

_WS_TAB_META = {
    "Live Feed": (":material/newspaper:", "Stream"),
    "Nepali Media": (":material/landscape:", "Portals"),
    "Indian Press": (":material/public:", "Outlets"),
    "Social Media": (":material/forum:", "Social"),
    "X": (":material/forum:", "Social"),
    "Analytics & Export": (":material/ios_share:", "Export"),
    "System Health": (":material/monitor_heart:", "Health"),
}


def _ws_seg_label(name: str) -> str:
    icon, short = _WS_TAB_META.get(name, (_NAV_ICON_MAP.get(name, ""), name))
    return f"{icon} {short}" if short else icon


def _on_ws_seg_change() -> None:
    chosen = st.session_state.get("app_nav_seg") or "Live Feed"
    _select_workspace(chosen)


st.session_state["app_nav_seg"] = selected_nav

_RAIL_TOGGLE_JS = """
<script>
(function () {
  try {
    var d = window.parent.document;
    if (d.getElementById('rail-toggle')) return;
    var b = d.createElement('button');
    b.id = 'rail-toggle'; b.type = 'button';
    b.setAttribute('aria-label', 'Hide sidebar'); b.title = 'Hide sidebar';
    b.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="3"/><line x1="9" y1="4" x2="9" y2="20"/><path class="rt-arr" d="M16 9.5L13.5 12l2.5 2.5"/></svg>';
    b.addEventListener('click', function () {
      var h = d.documentElement, collapsed = h.getAttribute('data-rail') === 'collapsed';
      if (collapsed) { h.removeAttribute('data-rail'); } else { h.setAttribute('data-rail', 'collapsed'); }
      var label = collapsed ? 'Hide sidebar' : 'Show sidebar';
      b.setAttribute('aria-label', label); b.title = label;
    });
    d.body.appendChild(b);
  } catch (e) {}
})();
</script>
<script>
(function () {
  try {
    var w = window.parent, d = w.document;
    if (w.__nmSelectFix) return;
    w.__nmSelectFix = true;
    // Phones/tablets: tapping a filter opens its option list directly; the search box inside must not pull up the keyboard.
    var coarse = (w.matchMedia && w.matchMedia('(pointer: coarse)').matches) || w.innerWidth <= 820;
    if (!coarse) return;
    function fix(root) {
      root.querySelectorAll('[data-testid="stSelectbox"] input, [data-testid="stMultiSelect"] input').forEach(function (i) {
        if (i.getAttribute('data-nm-nokb')) return;
        i.setAttribute('data-nm-nokb', '1'); i.setAttribute('inputmode', 'none'); i.setAttribute('readonly', 'readonly'); i.setAttribute('autocomplete', 'off');
      });
    }
    fix(d);
    new MutationObserver(function () { fix(d); }).observe(d.body, { childList: true, subtree: true });
  } catch (e) {}
})();
</script>
<script>
(function () {
  try {
    var w = window.parent, d = w.document;
    if (w.__nmCmdK) return;
    w.__nmCmdK = true;
    d.addEventListener('keydown', function (e) {
      if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
        var el = d.activeElement, tag = (el && el.tagName || '').toLowerCase();
        if (tag === 'input' || tag === 'textarea' || (el && el.isContentEditable)) return;
        var btn = d.querySelector('[class*="st-key-btn_srch_"] button');
        if (btn) { e.preventDefault(); btn.click(); }
      }
    });
  } catch (e) {}
})();
</script>
"""

_nav_tabs = st.container(key="rail_host")
with _nav_tabs:
    components.html(_RAIL_TOGGLE_JS, height=0)
@st.cache_data(ttl=60, show_spinner=False)
def _latest_ingest_epoch() -> float:
    """Newest source poll time recorded in Supabase (written by GitHub Actions or the in-app daemon)."""
    best = 0.0
    try:
        rows = get_all_source_health() or []
    except Exception:
        return 0.0
    now = time.time()
    for row in rows:
        raw = row.get("last_discovery_time")
        ts = 0.0
        try:
            if isinstance(raw, datetime.datetime):
                dt = raw if raw.tzinfo else raw.replace(tzinfo=datetime.timezone.utc)
                ts = dt.timestamp()
            elif isinstance(raw, str) and raw.strip():
                dt = datetime.datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
                dt = dt if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc)
                ts = dt.timestamp()
        except Exception:
            continue
        if ts <= now + 60:
            best = max(best, ts)
    return best


@st.cache_data(ttl=20, show_spinner=False)
def _stream_freshness() -> Dict[str, float]:
    """Per-stream newest poll time, cached briefly (not stacked on top of other caches)."""
    try:
        from nepal_news_store import get_stream_freshness
        return get_stream_freshness()
    except Exception:
        return {"nepali": 0.0, "indian": 0.0, "x": 0.0}


def _sync_age_label(epoch: float) -> Tuple[str, str]:
    """('Updated 2m ago', colour) from the newest successful ingest; colour reflects freshness."""
    if not epoch:
        return "Not synced yet", "#8E8E93"
    mins = max(0, int((time.time() - epoch) // 60))
    if mins < 1:
        txt = "Updated just now"
    elif mins < 60:
        txt = f"Updated {mins}m ago"
    elif mins < 1440:
        txt = f"Updated {mins // 60}h ago"
    else:
        txt = f"Updated {mins // 1440}d ago"
    col = "#15803D" if mins < 20 else ("#B45309" if mins < 60 else "#B91C1C")
    return txt, col


_SOCIAL_SVG = ('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px">'
               '<path d="M5 4h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-7l-5 4v-4H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z"/><path d="M12 13.2l-2.6-2.5a1.7 1.7 0 0 1 2.6-2.1 1.7 1.7 0 0 1 2.6 2.1z"/></svg>')

_NAV_STREAMS = {"Live Feed": ("nepali", "indian", "x"), "Nepali Media": ("nepali",), "Indian Press": ("indian",), "Social Media": ("x",), "X": ("x",)}


def _sync_inline_html(pipes: Dict[str, Dict[str, Any]], final: bool = False) -> str:
    icons = {"nepali": "🇳🇵", "indian": "🇮🇳", "x": _SOCIAL_SVG}
    out = []
    total = 0
    for k in _NAV_STREAMS.get(selected_nav, ("nepali", "indian", "x")):
        p = pipes.get(k) or {}
        stt = p.get("status", "idle")
        if stt == "running":
            _rn = int(p.get("count", 0))
            body = '<span class="sp-spin"></span>' + (f'<b>+{_rn}</b>' if _rn > 0 else '')
        elif stt == "done":
            n = int(p.get("count", 0)); total += n
            body = f'<b>+{n}</b>' if n else '<span class="sp-ok">✓</span>'
        elif stt in ("error", "timeout"):
            body = '<span class="sp-err">!</span>'
        else:
            body = '<span class="sp-wait">·</span>'
        out.append(f'<span class="sp-chip">{icons[k]}{body}</span>')
    return "".join(out)


@st.fragment(run_every=2)
def _render_brand_sync() -> None:
    # Pause background polling while any modal dialog is active to avoid visual flickering
    if st.session_state.get("active_modal"):
        return
    snap = get_manual_sync_status()
    running = bool(snap.get("running"))
    fin = float(snap.get("finished_at") or 0)
    _fresh = _stream_freshness()
    _scope = _NAV_STREAMS.get(selected_nav, ("nepali", "indian", "x"))
    # Freshness comes from each stream's own newest poll in the database (no cross-stream guessing).
    epoch = max([float(_fresh.get(k) or 0.0) for k in _scope] or [0.0])
    label, col = _sync_age_label(epoch)
    _names = {"nepali": "Nepali", "indian": "Indian", "x": "Social"}
    _per = " · ".join(f"{_names[k]} {_sync_age_label(float(_fresh.get(k) or 0.0))[0].replace('Updated ', '')}" for k in ("nepali", "indian", "x"))
    tip = _per
    is_syncing = running or (fin and time.time() - fin < 8)
    try:
        _n_np, _n_in, _n_x = _source_counts()
        _src_labels = {
            "Live Feed": f"{_n_np + _n_in + _n_x:,} sources",
            "Nepali Media": f"{_n_np} portals",
            "Indian Press": f"{_n_in} outlets",
            "Social Media": f"{_n_x:,} voices",
            "X": f"{_n_x:,} voices",
            "Analytics & Export": f"{_n_np + _n_in + _n_x:,} sources",
            "System Health": f"{_n_np + _n_in} portals",
        }
        _src_txt = _src_labels.get(selected_nav, "")
    except Exception:
        _src_txt = ""
    if is_syncing:
        dot_col = "#0071E3"
        meta_inner = _sync_inline_html(snap.get("pipelines") or {}, final=not running)
        tip = "Syncing…" if running else "Sync finished"
    else:
        is_fresh = col == "#15803D"
        dot_col = "#34C759" if is_fresh else col
        parts = [f'<span class="sync-dot{" sync-dot--live" if is_fresh else ""}"></span>']
        if is_fresh:
            parts.append('<span class="hdr-live-word">Live</span><span class="hdr-sep">·</span>')
        parts.append(f'<span>{html.escape(label)}</span>')
        if _src_txt:
            parts.append(f'<span class="hdr-sep hdr-sources">·</span><span class="hdr-sources">{html.escape(_src_txt)}</span>')
        meta_inner = "".join(parts)
    _titles = {
        "Live Feed": "Unified Stream",
        "Nepali Media": "National Portals",
        "Indian Press": "Indian Outlets",
        "Social Media": "Social Media",
        "X": "Social Media",
        "Analytics & Export": "Analytics & Export",
        "System Health": "System Health",
    }
    _ws_counts_map = {
        "Live Feed": total_combined_count,
        "Nepali Media": stream_counts.get("nepali_count", 0),
        "Indian Press": stream_counts.get("indian_count", 0),
        "Social Media": stream_counts.get("x_count", 0),
        "X": stream_counts.get("x_count", 0),
    }
    _title = _titles.get(selected_nav, "Monitor & Analytics")
    _item_n = _ws_counts_map.get(selected_nav)
    _count_html = f'<span class="hdr-count">({int(_item_n):,})</span>' if _item_n is not None else ""
    st.markdown(
        f'<div class="editorial-brand-anchor hdr-title-wrap">'
        f'<div class="hdr-title-row"><div class="hdr-title">{html.escape(_title)}</div>{_count_html}</div>'
        f'<div class="hdr-meta"><span class="live-status-inline sync-inline" style="--dot:{dot_col}" '
        f'title="{html.escape(tip)}">{meta_inner}</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _on_theme_change() -> None:
    chosen = st.session_state.get("theme_seg") or "auto"
    st.query_params["theme"] = chosen
    st.session_state.pop("feed_sessions", None)


def _cycle_theme() -> None:
    """One button: auto -> light -> dark -> auto."""
    order = ["auto", "light", "dark"]
    cur = st.query_params.get("theme", "auto")
    nxt = order[(order.index(cur) + 1) % 3] if cur in order else "light"
    st.query_params["theme"] = nxt
    st.session_state.pop("feed_sessions", None)


def _render_theme_button(ws_suffix: str) -> None:
    mode = _THEME_MODE if _THEME_MODE in ("auto", "light", "dark") else "auto"
    icon = {"auto": ":material/brightness_auto:", "light": ":material/light_mode:", "dark": ":material/dark_mode:"}[mode]
    if st.button("", icon=icon, key=f"btn_theme_{ws_suffix}", width="content",
                 help=f"Appearance · {mode.capitalize()}"):
        _cycle_theme()
        st.rerun()  # full-app rerun: this button lives inside a fragment, and the theme CSS is applied at the top of the script


def _fmt_rail_badge(count: Any) -> str:
    try:
        n = max(0, int(count or 0))
    except (TypeError, ValueError):
        return "0"
    if n < 1000:
        return str(n)
    if n < 10000:
        return f"{n / 1000:.1f}k".replace(".0k", "k")
    return f"{n // 1000}k"


def _rail_health_dot_color() -> str:
    try:
        if (_sync_snap or {}).get("errors"):
            return "#FF9F0A"
        fresh = _stream_freshness() or {}
        newest = max([float(v or 0.0) for v in fresh.values()] or [0.0])
        if newest > 0:
            mins = max(0, int((time.time() - newest) // 60))
            if mins < 20:
                return "#34C759"
            if mins < 60:
                return "#FF9F0A"
            return "#FF453A"
    except Exception:
        pass
    return "#34C759" if total_combined_count > 0 else "#8E8E93"


with _nav_tabs:
    st.markdown(
        f'<style>:root{{'
        f'--rail-c1:"{_fmt_rail_badge(total_combined_count)}";'
        f'--rail-c2:"{_fmt_rail_badge(stream_counts.get("nepali_count", 0))}";'
        f'--rail-c3:"{_fmt_rail_badge(stream_counts.get("indian_count", 0))}";'
        f'--rail-c4:"{_fmt_rail_badge(stream_counts.get("x_count", 0))}";'
        f'--rail-health-dot:{_rail_health_dot_color()};'
        f'}}</style>',
        unsafe_allow_html=True,
    )
    st.segmented_control(
        "Workspace",
        options=[n for n, _ in NAV_ITEMS],
        format_func=_ws_seg_label,
        key="app_nav_seg",
        on_change=_on_ws_seg_change,
        label_visibility="collapsed",
        width="stretch",
    )


def _format_sync_age(finished_at: float) -> str:
    age = max(0, int(time.time() - finished_at))
    if age < 45:
        return "just now"
    if age < 3600:
        return f"{max(1, age // 60)}m ago"
    if age < 86400:
        return f"{age // 3600}h ago"
    return f"{age // 86400}d ago"


@st.fragment(run_every=2)
def _render_sync_status_bar() -> None:
    """Inline sync status bar: per-stream pills plus a data-freshness chip."""
    snap = get_manual_sync_status()
    pipes = snap.get("pipelines") or {}
    running = bool(snap.get("running"))
    finished_at = max(float(snap.get("finished_at") or 0), _latest_ingest_epoch())

    just_finished = bool(float(snap.get("finished_at") or 0)) and (time.time() - float(snap.get("finished_at") or 0)) <= 180
    needs_detail = running or any((pipes.get(k) or {}).get("status") in ("error", "timeout") for k in ("nepali", "indian", "x")) or just_finished
    if not needs_detail and finished_at:
        return

    pills_html = []
    for key, label, emoji in [("nepali", "Nepali", "🇳🇵"), ("indian", "Indian", "🇮🇳"), ("x", "Social", "💬")]:
        pipe = pipes.get(key) or {}
        status = pipe.get("status", "idle")
        if status == "running":
            cls, content = "sync-status-pill--running", '<span class="sync-spinner"></span> Syncing…'
        elif status == "done":
            cls, content = "sync-status-pill--done", f'✓ {int(pipe.get("count", 0))}'
        elif status in ("error", "timeout"):
            cls, content = "sync-status-pill--error", f"⚠️ {html.escape(str(status))}"
        elif running:
            cls, content = "sync-status-pill--waiting", "Queued"
        elif finished_at:
            cls, content = "sync-status-pill--idle", "✓ Ready"
        else:
            cls, content = "sync-status-pill--idle", "Idle"
        pills_html.append(f'<div class="sync-status-pill {cls}" title="{label}">{emoji}<span class="sp-name">{label}:</span> {content}</div>')

    if running:
        fresh = '<span class="fresh-long">Refreshing live feeds…</span><span class="fresh-short">Syncing</span>'
    elif finished_at:
        age = _format_sync_age(finished_at)
        fresh = f'<span class="fresh-long">Updated {age}</span><span class="fresh-short">{age}</span>'
    else:
        fresh = "Freshness unknown"
    pills_html.append(f'<div class="sync-fresh-chip">{_ico("clock", 12)} {fresh}</div>')

    st.markdown(f'<div class="sync-status-bar">{"".join(pills_html)}</div>', unsafe_allow_html=True)




def _apply_fresh_data_refresh(epoch: float) -> None:
    """Drops cached feed data and per-session feed pages so the next rerun loads newly ingested rows."""
    st.session_state["_seen_ingest_epoch"] = epoch
    for fn in (
        get_all_source_health, _latest_ingest_epoch, get_cached_header_bundle, get_cached_login_bootstrap,
        _get_cached_feed_page_with_count, _get_cached_filtered_count, get_active_nepal_articles,
        get_active_indian_articles, get_active_x_posts, _get_cached_indian_workspace_bootstrap,
        _get_cached_x_workspace_bootstrap, _get_cached_indian_source_health, get_cached_analytics_bundle,
    ):
        try:
            fn.clear()
        except Exception:
            pass
    st.session_state.pop("_hdr_state_cache", None)
    st.session_state.pop("x_posts", None)
    sessions = st.session_state.get("feed_sessions")
    if isinstance(sessions, dict):
        sessions.clear()
    vers = st.session_state.get("stream_versions")
    if isinstance(vers, dict):
        for k in ("nepali", "indian", "x"):
            vers[k] = int(vers.get(k, 0)) + 1
    st.session_state["data_version"] = int(st.session_state.get("data_version", 0)) + 1
    st.session_state["last_sync_npt"] = datetime.datetime.now(NEPAL_TZ).strftime("%I:%M %p").lstrip("0")


@st.fragment(run_every=60)
def _render_new_data_banner() -> None:
    """Polls Supabase freshness once a minute and offers a one-tap reload when newer data has landed."""
    epoch = _latest_ingest_epoch()
    seen = float(st.session_state.setdefault("_seen_ingest_epoch", epoch))
    if epoch <= seen + 1:
        return
    if st.button("New stories", icon=":material/arrow_upward:", key="btn_load_new_data", type="primary", width="stretch", help=f"Updated {_format_sync_age(epoch)}"):
        _apply_fresh_data_refresh(epoch)
        st.rerun()


@st.fragment
def _render_phase2_search_sidebar() -> None:
    """PHASE 2: Persistent search sidebar with active filter pills."""
    _active_sq = st.session_state.get("committed_search_query", "")
    _active_filters = st.session_state.get("active_filters", {})

    if not _active_sq and not _active_filters:
        return

    # Build filter pills HTML
    filter_pills_html = []

    # Search query pill
    if _active_sq:
        filter_pills_html.append(
            f'<div class="filter-pill-removable">'
            f'{_ico("search", 12)} {html.escape(_active_sq[:30])}'
            f'<button onclick="window.location.search = \'query=\';" title="Clear search">×</button>'
            f'</div>'
        )

    # Category filter pill
    if _active_filters.get("category") and _active_filters["category"] != "All":
        cat = html.escape(str(_active_filters["category"]))
        filter_pills_html.append(
            f'<div class="filter-pill-removable">'
            f'{cat}'
            f'<button title="Clear category filter">×</button>'
            f'</div>'
        )

    if filter_pills_html:
        st.markdown(
            f'<div class="search-sidebar">'
            f'<div class="search-sidebar__label">Active Filters</div>'
            f'<div class="search-sidebar__filters">{"".join(filter_pills_html)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


# Search query pills are rendered cleanly inside _render_active_filters_bar below the sticky header.


@st.fragment
def _render_phase2_skeleton_cards(count: int = 3) -> None:
    """PHASE 2: Show loading skeleton placeholders while fetching articles."""
    for _ in range(count):
        st.markdown(
            f'<div class="skeleton-card">'
            f'<div class="skeleton-line skeleton-line--title"></div>'
            f'<div style="margin-top: 10px;"></div>'
            f'<div class="skeleton-line skeleton-line--text"></div>'
            f'<div class="skeleton-line skeleton-line--text" style="width: 95%;"></div>'
            f'<div class="skeleton-line skeleton-line--text" style="width: 80%;"></div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def _render_phase3_help_icon(tooltip_text: str, icon: str = "?") -> str:
    """PHASE 3: Render contextual help tooltip icon."""
    return (
        f'<span class="help-tooltip" title="{html.escape(tooltip_text)}">'
        f'{html.escape(icon)}'
        f'</span>'
    )


def _render_phase3_activity_log(items: List[Dict[str, Any]], max_items: int = 5) -> None:
    """PHASE 3: Render recent activity log."""
    if not items:
        st.info("No recent activity")
        return

    activity_html = '<div class="activity-log">'
    for item in items[:max_items]:
        icon = item.get("icon", "📝")
        title = html.escape(str(item.get("title", "Activity")))
        time_str = html.escape(str(item.get("time", "Just now")))

        activity_html += (
            f'<div class="activity-item">'
            f'<div class="activity-item__icon">{icon}</div>'
            f'<div class="activity-item__content">'
            f'<div class="activity-item__title">{title}</div>'
            f'<div class="activity-item__time">{time_str}</div>'
            f'</div>'
            f'</div>'
        )

    activity_html += '</div>'
    st.markdown(activity_html, unsafe_allow_html=True)


def _render_phase3_health_metrics(metrics: Dict[str, Any]) -> None:
    """PHASE 3: Render health dashboard metrics."""
    cols = st.columns(len(metrics) or 3)

    for col, (label, value) in zip(cols, metrics.items()):
        with col:
            st.markdown(
                f'<div class="health-metric-card">'
                f'<div class="health-metric-value">{html.escape(str(value))}</div>'
                f'<div class="health-metric-label">{html.escape(str(label))}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


def _render_phase3_onboarding_card() -> None:
    """PHASE 3: Show first-time user onboarding card."""
    if st.session_state.get("dismiss_onboarding"):
        return

    col_content, col_close = st.columns([4, 0.3])

    with col_content:
        st.markdown(
            f'<div class="onboarding-card">'
            f'<div class="onboarding-card__content">'
            f'<div class="onboarding-card__title">Welcome</div>'
            f'<div class="onboarding-card__steps">'
            f'Browse · Search · Share'
            f'</div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with col_close:
        if st.button("×", key="dismiss_onboard", help="Dismiss"):
            st.session_state["dismiss_onboarding"] = True
            st.rerun()


def _sync_tf_from_widget(seg_key: str) -> None:
    chosen = st.session_state.get(seg_key)
    if not chosen:
        cur = st.session_state.get("cp_timeframe_segment") or "12h"
        chosen = cur if cur in QUICK_TIME_PRESETS else "12h"
        st.session_state[seg_key] = chosen
    st.session_state["cp_timeframe_segment"] = chosen
    on_timeframe_preset_change()


def _sync_pop_tf_from_widget(seg_key: str) -> None:
    chosen = st.session_state.get(seg_key) or "12h"
    st.session_state["cp_timeframe_segment"] = chosen
    on_timeframe_preset_change()


def _render_time_capsule(ws_suffix: str) -> None:
    """Renders the unified Apple segmented time capsule: [ 6h | 12h | 24h | Today | 📅▾ ]."""
    # Timeframe lives inside workspace @st.fragment blocks; rerun the full app whenever
    # a preset, popover range, custom picker, or reset changes so sidebar badges, header
    # counts, and every workspace stay strictly aligned to the chosen window.
    if st.session_state.pop("_pending_tf_rerun", False) or _tf_state_sig() != _TOP_LEVEL_TF_SIG:
        st.session_state.pop("_hdr_state_cache", None)
        st.rerun(scope="app")

    cur_preset = st.session_state.get("cp_timeframe_segment") or "12h"
    quick_key = f"cp_tf_quick_{ws_suffix}"
    pop_seg_key = f"cp_tf_seg_{ws_suffix}"
    is_extra_tf = cur_preset not in QUICK_TIME_PRESETS
    st.session_state[quick_key] = cur_preset if not is_extra_tf else None
    st.session_state[pop_seg_key] = cur_preset

    cap_key = f"hdr_time_custom_{ws_suffix}" if is_extra_tf else f"hdr_time_{ws_suffix}"
    with st.container(key=cap_key, horizontal=True, horizontal_alignment="left", vertical_alignment="center", gap=None, wrap=False, width="content"):
        st.segmented_control(
            "Timeframe",
            options=QUICK_TIME_PRESETS,
            key=quick_key,
            on_change=_sync_tf_from_widget,
            args=(quick_key,),
            label_visibility="collapsed",
            width="content",
        )
        pop_label = cur_preset
        pop_icon = ":material/schedule:" if cur_preset == "2h" else ":material/date_range:"
        with st.popover(pop_label, icon=pop_icon, key=f"pop_time_{ws_suffix}", help=f"{window_label} · Custom range & reset", width="content"):
            st.segmented_control(
                "All timeframes",
                options=TIMEFRAME_PRESETS,
                key=pop_seg_key,
                on_change=_sync_pop_tf_from_widget,
                args=(pop_seg_key,),
                label_visibility="collapsed",
                width="stretch",
            )
            if cur_preset == "Custom":
                c_dt1, c_dt2 = st.columns(2)
                with c_dt1:
                    st.date_input("From", value=st.session_state.get("filter_start_date", default_start_date), max_value=now_npt.date(), key="filter_start_date")
                    st.time_input("Time", value=st.session_state.get("filter_start_time", default_start_time), key="filter_start_time")
                st.toggle("Up to now", value=True, key="filter_use_current_time", help="Keep the window open-ended so new stories stream in")
                if not st.session_state.get("filter_use_current_time", True):
                    with c_dt2:
                        st.date_input("To", value=st.session_state.get("filter_end_date", now_npt.date()), max_value=now_npt.date(), min_value=st.session_state.get("filter_start_date", default_start_date), key="filter_end_date")
                        st.time_input("Time ", value=st.session_state.get("filter_end_time", now_npt.time().replace(second=0, microsecond=0)), key="filter_end_time")
            st.caption(f"{window_label} · Synced {st.session_state['last_sync_npt']} NPT")
            st.button("Reset All Filters", icon=":material/restart_alt:", key=f"btn_rst_{ws_suffix}", width="stretch", on_click=reset_all_filters)


def _format_sync_pipeline_pills(pipes: Dict[str, Dict[str, Any]]) -> str:
    labels = {"nepali": "🇳🇵 Nepali", "indian": "🇮🇳 Indian", "x": "💬 Social"}
    parts = []
    for k in ("nepali", "indian", "x"):
        p = pipes.get(k) or {}
        st_name = p.get("status", "idle")
        if st_name == "running":
            parts.append(f"{labels[k]}: syncing…")
        elif st_name == "done":
            parts.append(f"{labels[k]}: ✓ {int(p.get('count', 0))} ({p.get('elapsed_secs', 0)}s)")
        elif st_name in ("error", "timeout"):
            parts.append(f"{labels[k]}: ⚠️ {st_name}")
    return " · ".join(parts)


def _render_telemetry_hud_html(elapsed: int, pipes: Dict[str, Dict[str, Any]]) -> str:
    labels = {
        "nepali": ("🇳🇵", "Nepali Media"),
        "indian": ("🇮🇳", "Indian Press"),
        "x": ("💬", "Social Media"),
    }
    pill_htmls = []
    for k in ("nepali", "indian", "x"):
        flag, name = labels[k]
        p = pipes.get(k) or {}
        st_name = p.get("status", "idle")
        if st_name == "running":
            cls = "telemetry-stream--running"
            metric = '<span class="telemetry-spinner"></span> Syncing…'
        elif st_name == "done":
            cls = "telemetry-stream--done"
            c = int(p.get("count", 0))
            el = p.get("elapsed_secs", 0)
            metric = f"✓ {c} ({el}s)"
        elif st_name in ("error", "timeout"):
            cls = "telemetry-stream--error"
            metric = f"⚠️ {st_name}"
        else:
            cls = "telemetry-stream--idle"
            metric = "Pending"
        pill_htmls.append(
            f'<div class="telemetry-stream-pill {cls}">'
            f'<span class="telemetry-flag">{flag}</span>'
            f'<span class="telemetry-name">{name}</span>'
            f'<span class="telemetry-metric">{metric}</span>'
            f'</div>'
        )

    return (
        f'<div class="apple-telemetry-hud">'
        f'<div class="telemetry-hud-lead">'
        f'<span class="telemetry-pulse-dot"></span>'
        f'<span class="telemetry-hud-title">LIVE SYNC</span>'
        f'<span class="telemetry-hud-elapsed">{elapsed}s</span>'
        f'</div>'
        f'<div class="telemetry-hud-streams">{"".join(pill_htmls)}</div>'
        f'</div>'
    )


@st.fragment(run_every=1.5)
def _render_active_sync_monitor() -> None:
    snap = get_manual_sync_status()
    pipes = snap.get("pipelines") or {}
    snap_seqs = snap.get("stream_seqs") or {}
    started = float(snap.get("started_at") or 0)
    if st.session_state.get("_sync_verb_for") != started:
        st.session_state["_sync_verb_for"] = started
        st.session_state["_sync_verb"] = _busy("feed").rstrip("…")
    seen_seqs = st.session_state.get("_seen_stream_seqs", {"nepali": 0, "indian": 0, "x": 0})
    has_new_stream = any(int(snap_seqs.get(k, 0)) > int(seen_seqs.get(k, 0)) for k in ("nepali", "indian", "x"))
    if has_new_stream:
        st.rerun()
    if not snap.get("running") and int(snap.get("completed_seq", 0)) > int(st.session_state.get("_seen_sync_seq", 0)):
        st.rerun()


if get_manual_sync_status().get("running"):
    _render_active_sync_monitor()
elif _sync_snap.get("errors"):
    _failed_streams = [k for k in ("nepali", "indian", "x") if k in (_sync_snap.get("errors") or {})]
    if _failed_streams:
        _sc1, _sc2 = st.columns([4.2, 1.3], vertical_alignment="center", gap="small")
        with _sc1:
            st.markdown(
                f'<div class="telemetry-error-bar">'
                f'<span class="telemetry-warn-dot">⚠️</span>'
                f'<span class="telemetry-error-text">Sync finished with partial errors: <b>{html.escape(_format_sync_pipeline_pills(_sync_snap.get("pipelines") or {}))}</b></span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with _sc2:
            if st.button("Retry Failed", icon=":material/refresh:", key="btn_retry_failed_sync", width="stretch"):
                started, _ = trigger_manual_sync_async(targets=_failed_streams)
                if started:
                    st.toast(f"Retrying {', '.join(_failed_streams)}…", icon=":material/refresh:")
                st.rerun()

search_query = st.session_state.get("committed_search_query", "")

# ==========================================
# SECTION 0: Live Feed (Nepali Media, Indian Press, X Posts)
# ==========================================
def _toolbar_columns(ws_suffix: str, defaults: Dict[str, Any], only_theme: bool = False, admin: bool = False, show_timeframe: bool = False) -> Any:
    """Sticky Apple-grade header: large title + live status on the left; unified capsule controls on the right.
    Returns the filters popover for the caller to fill."""
    with st.container(key=f"hdr_shell_{ws_suffix}", width="stretch"):
        with st.container(
            key=f"hdr_bar_{ws_suffix}",
            horizontal=True,
            horizontal_alignment="distribute",
            vertical_alignment="center",
            gap="small",
            wrap=True,
            width="stretch",
        ):
            with st.container(key=f"hdr_left_{ws_suffix}", width="content"):
                _render_brand_sync()
            with st.container(
                key=f"hdr_tools_{ws_suffix}",
                horizontal=True,
                horizontal_alignment="right",
                vertical_alignment="center",
                gap="xsmall",
                wrap=True,
                width="content",
            ):
                if only_theme:
                    if show_timeframe:
                        _render_time_capsule(ws_suffix)
                    _render_theme_button(ws_suffix)
                    return None
                _srch_btn_type = "primary" if _active_sq else "secondary"
                _srch_help = f"“{_active_sq}” · tap to edit (⌘K)" if _active_sq else "Search (⌘K)"
                _srch_lbl = (f"“{_active_sq[:12]}…”" if len(_active_sq) > 12 else f"“{_active_sq}”") if _active_sq else "Search"
                if st.button(_srch_lbl, icon=":material/search:", key=f"btn_srch_{ws_suffix}", type=_srch_btn_type, width="content", help=_srch_help):
                    _show_search_dialog()
                _render_time_capsule(ws_suffix)
                n_active = sum(1 for k, d in defaults.items() if st.session_state.get(k, d) != d)
                _flt_key = f"pop_flt_on_{ws_suffix}" if n_active else f"pop_flt_{ws_suffix}"
                _flt_lbl = f"Filter · {n_active}" if n_active else "Filter"
                pop = st.popover(_flt_lbl, icon=":material/tune:", key=_flt_key, help="Filters", width="content")
                _sync_now = get_manual_sync_status()
                _is_syncing_now = bool(_sync_now.get("running"))
                if st.button(
                    "",
                    icon=":material/sync:",
                    key=(f"btn_sync_run_{ws_suffix}" if _is_syncing_now else f"btn_sync_{ws_suffix}"),
                    width="content",
                    disabled=_is_syncing_now,
                    help=("Syncing…" if _is_syncing_now else "Refresh feeds"),
                ):
                    trigger_manual_sync_async(targets={"np": ["nepali"], "in": ["indian"], "x": ["x"]}.get(ws_suffix))
                    st.rerun()
                _render_theme_button(ws_suffix)
                if admin:
                    st.button(
                        "",
                        icon=":material/admin_panel_settings:",
                        key="btn_x_admin",
                        help="Directory & Admin",
                        width="content",
                        on_click=lambda: st.session_state.update({"x_subview_active_tab": "Admin"}),
                    )
                return pop


@st.fragment
def render_live_feed_section() -> None:
    st.session_state.setdefault("comb_cat_filter", CAT_FILTER_ALL_UNFILTERED)
    st.session_state.setdefault("comb_sort_mode", "Newest First")
    sel_comb_stream = "All Sources"

    _lf_pop = _toolbar_columns("lf", {"comb_cat_filter": CAT_FILTER_ALL_UNFILTERED, "comb_sort_mode": "Newest First"})
    with _lf_pop:
        sel_comb_cat = st.selectbox("Topic", CATEGORY_FILTER_OPTIONS, key="comb_cat_filter")
        comb_sort_mode = st.selectbox(
            "Sort",
            ["Newest First", "Oldest First"],
            format_func=lambda s: f"⇅ {s}",
            key="comb_sort_mode",
        )

    _live_active = []
    if sel_comb_cat != CAT_FILTER_ALL_UNFILTERED:
        _live_active.append(sel_comb_cat)
    if comb_sort_mode != "Newest First":
        _live_active.append(comb_sort_mode)
    _render_active_filters_bar(
        _live_active,
        {"comb_cat_filter": CAT_FILTER_ALL_UNFILTERED, "comb_sort_mode": "Newest First"},
        "live",
    )

    _sig = f"live|{active_preset}|tf{_tf_epoch}|v{_v_live}|{sel_comb_stream}|{sel_comb_cat}|{comb_sort_mode}|{search_query or ''}"

    def _fetch_all_now():
        with st.spinner(_busy("feed", "all streams")):
            from nepal_news_scheduler import _run_concurrent_ingest_pipelines
            _run_concurrent_ingest_pipelines(include_nepali=True, include_indian=True, include_x=True, nepali_workers=12, indian_workers=8)

    render_infinite_workspace_feed(
        workspace="live",
        renderer=render_apple_combined_item_card,
        noun="items",
        filter_sig=_sig,
        stream_filter=sel_comb_stream,
        category_filter=sel_comb_cat,
        search_query=search_query or "",
        sort_mode=comb_sort_mode,
        empty_icon="🌐",
        empty_title="No combined stories found",
        empty_body="Try widening the timeframe preset or clearing active filters.",
        on_fetch_now=_fetch_all_now,
        wa_sent_map=_shared_wa_sent_map,
        prefetched_init=(_prefetched_live_init if _sig == _prefetched_live_sig else None),
    )


if selected_nav == "Live Feed":
    render_live_feed_section()


# ==========================================
# SECTION 1: Nepali Media (Monitored Portals)
# ==========================================
@st.fragment
def render_nepali_media_section() -> None:
    _np_pop = _toolbar_columns("np", {"np_portal_filter": ALL_PORTALS_DEFAULT, "np_cat_filter": CAT_FILTER_ALL_UNFILTERED, "np_lang_filter": ALL_LANG_DEFAULT})
    with _np_pop:
        sel_np_portal = st.selectbox("Portal", [ALL_PORTALS_DEFAULT] + NEPALI_PORTAL_NAMES, key="np_portal_filter")
        sel_np_cat = st.selectbox("Topic", CATEGORY_FILTER_OPTIONS, key="np_cat_filter")
        sel_np_lang = st.selectbox("Language", [ALL_LANG_DEFAULT, "Nepali Only", "English Only"], key="np_lang_filter")

    _np_active = []
    if sel_np_portal != ALL_PORTALS_DEFAULT:
        _np_active.append(sel_np_portal)
    if sel_np_cat != CAT_FILTER_ALL_UNFILTERED:
        _np_active.append(sel_np_cat)
    if sel_np_lang != ALL_LANG_DEFAULT:
        _np_active.append(sel_np_lang)
    _render_active_filters_bar(
        _np_active,
        {"np_portal_filter": ALL_PORTALS_DEFAULT, "np_cat_filter": CAT_FILTER_ALL_UNFILTERED, "np_lang_filter": ALL_LANG_DEFAULT},
        "nepali",
    )

    _sig = f"nepali|{active_preset}|tf{_tf_epoch}|v{_v_np}|{sel_np_portal}|{sel_np_cat}|{sel_np_lang}|{search_query or ''}"

    def _fetch_np_now():
        with st.spinner(_busy("feed", "Nepali portals")):
            from nepal_fetcher import fetch_top_nepal_media
            fetch_top_nepal_media(max_workers=15, force_refresh=True, return_all_stored=False)

    render_infinite_workspace_feed(
        workspace="nepali",
        renderer=render_apple_article_card,
        noun="stories",
        filter_sig=_sig,
        category_filter=sel_np_cat,
        source=sel_np_portal,
        language=sel_np_lang,
        search_query=search_query or "",
        empty_icon="📰",
        empty_title="No articles found",
        empty_body="Try widening the timeframe or clearing active filters.",
        on_fetch_now=_fetch_np_now,
        wa_sent_map=_shared_wa_sent_map,
    )


if selected_nav == "Nepali Media":
    render_nepali_media_section()


# ==========================================
# SECTION 2: Nepal in Indian Media
# ==========================================
@st.fragment
def render_indian_press_section() -> None:
    _in_pop = _toolbar_columns("in", {"in_outlet_filter": ALL_INDIAN_DEFAULT, "in_lang_filter": ALL_LANG_DEFAULT})
    with _in_pop:
        selected_indian_outlet = st.selectbox("Outlet", [ALL_INDIAN_DEFAULT] + INDIAN_OUTLET_NAMES, key="in_outlet_filter")
        sel_in_lang = st.selectbox("Language", [ALL_LANG_DEFAULT, "English", "Hindi"], key="in_lang_filter")

    _in_active = []
    if selected_indian_outlet != ALL_INDIAN_DEFAULT:
        _in_active.append(selected_indian_outlet)
    if sel_in_lang != ALL_LANG_DEFAULT:
        _in_active.append(sel_in_lang)
    _render_active_filters_bar(
        _in_active,
        {"in_outlet_filter": ALL_INDIAN_DEFAULT, "in_lang_filter": ALL_LANG_DEFAULT},
        "indian",
    )

    _sig = f"indian|{active_preset}|tf{_tf_epoch}|v{_v_in}|{selected_indian_outlet}|{sel_in_lang}|{search_query or ''}"

    _ind_boot = _get_cached_indian_workspace_bootstrap(
        start_iso=filter_start_dt.isoformat(),
        end_iso=filter_end_dt.isoformat(),
        snap_iso=filter_end_dt.isoformat(),
        source=selected_indian_outlet,
        language=sel_in_lang,
        search_query=search_query or "",
        threshold_val=india_rel_threshold,
        data_version=_v_in,
    )
    _existing_ind = st.session_state.get("feed_sessions", {}).get("indian")
    _ind_prefetched = _ind_boot if (not _existing_ind or _existing_ind.get("filter_sig") != _sig) else None

    def _fetch_in_now():
        with st.spinner(_busy("feed", "Indian press")):
            from nepal_fetcher import fetch_nepal_in_indian_media
            fetch_nepal_in_indian_media(max_workers=12, force_refresh=True, return_all_stored=False)

    feed_stats = render_infinite_workspace_feed(
        workspace="indian",
        renderer=lambda a: render_apple_article_card(a, is_indian=True),
        noun="stories",
        filter_sig=_sig,
        source=selected_indian_outlet,
        language=sel_in_lang,
        search_query=search_query or "",
        empty_icon="🇮🇳",
        empty_title="No Indian media coverage found",
        empty_body=f"Try selecting '{ALL_INDIAN_DEFAULT}' or adjusting the timeframe.",
        on_fetch_now=_fetch_in_now,
        wa_sent_map=_shared_wa_sent_map,
        prefetched_init=_ind_prefetched,
    )

    # Flagged Borderline Articles for Editorial Review & Central DB Retention Audit (populated from same 1-query bundle)
    ind_audit = _ind_boot.get("audit") or {"total": 0, "substantive": 0, "borderline_review": 0, "excluded": 0}
    borderline_items = _ind_boot.get("borderline_items") or []

    with st.expander(f":material/flag: Review queue · {len(borderline_items)}", expanded=False):
        st.caption(
            "Borderline articles (scoring between 40% and the active relevance threshold) and excluded domestic Indian articles are retained in the central database (`indian_media_articles`) without cluttering the main feed."
        )
        m_c1, m_c2, m_c3, m_c4 = st.columns(4)
        m_c1.metric("Substantive", f"{feed_stats.get('total_count', 0):,}")
        m_c2.metric("Borderline Review", f"{len(borderline_items):,}")
        m_c3.metric("Excluded Domestic", f"{ind_audit.get('excluded', 0):,}")
        m_c4.metric("Total Stored", f"{ind_audit.get('total', 0):,}")

        if borderline_items:
            for b_art in borderline_items[:15]:
                st.markdown(render_apple_article_card(b_art, is_indian=True), unsafe_allow_html=True)
        else:
            st.success("No borderline articles currently pending editorial review.")

    with st.expander(":material/bolt: Nepal desks", expanded=False):
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


if selected_nav == "Indian Press":
    render_indian_press_section()


# ==========================================
# SECTION 3: X (Twitter) Nepal
# ==========================================
@st.fragment
def render_x_section() -> None:
    st.session_state.setdefault("x_plat_filter_select", "All Platforms")
    st.session_state.setdefault("x_cat_filter_select", CAT_FILTER_ALL_UNFILTERED)
    st.session_state.setdefault("x_acc_type_select", ALL_ACC_TYPES)
    st.session_state.setdefault("x_sort_mode_select", "Newest")

    x_plat_filter = st.session_state.get("x_plat_filter_select", "All Platforms")
    x_cat_filter = st.session_state.get("x_cat_filter_select", CAT_FILTER_ALL_UNFILTERED)
    selected_acc_type = st.session_state.get("x_acc_type_select", ALL_ACC_TYPES)
    sort_mode = st.session_state.get("x_sort_mode_select", "Newest")

    _x_sig = f"x|{active_preset}|tf{_tf_epoch}|v{_v_x}|{x_plat_filter}|{x_cat_filter}|{selected_acc_type}|{sort_mode}|{search_query or ''}"
    _existing_x = st.session_state.get("feed_sessions", {}).get("x")
    _need_x_boot = (not _existing_x or _existing_x.get("filter_sig") != _x_sig)
    _x_boot = None
    if _need_x_boot:
        _x_boot = _get_cached_x_workspace_bootstrap(
            start_iso=filter_start_dt.isoformat(),
            end_iso=filter_end_dt.isoformat(),
            snap_iso=filter_end_dt.isoformat(),
            category_filter=x_cat_filter,
            author_type=selected_acc_type,
            search_query=search_query or "",
            sort_mode=sort_mode,
            platform=x_plat_filter,
            data_version=_v_x,
        )
        x_kpis = _x_boot.get("kpis") or get_x_account_kpis()
    else:
        x_kpis = get_x_account_kpis()
    total_acc_count = x_kpis.get("total_discovered", len(VERIFIED_NEPAL_X_DIRECTORY))
    verified_acc_count = x_kpis.get("total_verified", len(VERIFIED_NEPAL_X_DIRECTORY))
    active_acc_count = x_kpis.get("active_monitored", len(VERIFIED_NEPAL_X_DIRECTORY))
    pending_acc_count = x_kpis.get("pending_verification", 0)

    _xs = st.session_state.get("x_subview_active_tab", "Live Feed")
    x_subview = "Directory" if str(_xs).startswith("Directory") else (_xs if _xs in ("Live Feed", "Admin") else "Live Feed")
    st.session_state["x_subview_active_tab"] = x_subview

    def _x_go(view: str) -> None:
        st.session_state["x_subview_active_tab"] = view

    if x_subview != "Live Feed":
        _bk, _sg = st.columns([1, 5], gap="small", vertical_alignment="center")
        with _bk:
            st.button("", icon=":material/arrow_back:", key="btn_x_back", help="Back to feed", on_click=_x_go, args=("Live Feed",), width="stretch")
        with _sg:
            st.segmented_control(
                "Social Media admin",
                options=["Directory", "Admin"],
                format_func=lambda o: ":material/groups: Directory" if o == "Directory" else ":material/admin_panel_settings: Admin",
                default=x_subview,
                key="x_admin_seg",
                on_change=lambda: _x_go(st.session_state.get("x_admin_seg") or "Directory"),
                label_visibility="collapsed",
            )

    # -------------------------------------------------------------
    # SUBVIEW 1: LIVE FEED
    # -------------------------------------------------------------
    if x_subview == "Live Feed":
        x_acc_types = [ALL_ACC_TYPES] + [
            c for c in CANONICAL_X_CATEGORIES
            if c not in ("Media Houses and News Outlets", "Media Houses & News Outlets")
        ]
        _x_pop = _toolbar_columns("x", {"x_plat_filter_select": "All Platforms", "x_cat_filter_select": CAT_FILTER_ALL_UNFILTERED, "x_acc_type_select": ALL_ACC_TYPES, "x_sort_mode_select": "Newest"}, admin=True)
        with _x_pop:
            x_plat_filter = st.selectbox("Platform", ["All Platforms", "X (Twitter)", "Facebook"], key="x_plat_filter_select")
            x_cat_filter = st.selectbox("Topic", CATEGORY_FILTER_OPTIONS, key="x_cat_filter_select")
            selected_acc_type = st.selectbox("Account type", x_acc_types, key="x_acc_type_select")
            sort_mode = st.selectbox("Sort", ["Newest", "Most engagement", "Most liked", "Most reposted"], key="x_sort_mode_select")

        _x_active = []
        if x_plat_filter != "All Platforms":
            _x_active.append(x_plat_filter)
        if x_cat_filter != CAT_FILTER_ALL_UNFILTERED:
            _x_active.append(x_cat_filter)
        if selected_acc_type != ALL_ACC_TYPES:
            _x_active.append(selected_acc_type)
        if sort_mode != "Newest":
            _x_active.append(sort_mode)
        _render_active_filters_bar(
            _x_active,
            {"x_plat_filter_select": "All Platforms", "x_cat_filter_select": CAT_FILTER_ALL_UNFILTERED, "x_acc_type_select": ALL_ACC_TYPES, "x_sort_mode_select": "Newest"},
            "x",
        )

        _sig = f"x|{active_preset}|tf{_tf_epoch}|v{_v_x}|{x_plat_filter}|{x_cat_filter}|{selected_acc_type}|{sort_mode}|{search_query or ''}"
        if _sig != _x_sig:
            _x_boot = _get_cached_x_workspace_bootstrap(
                start_iso=filter_start_dt.isoformat(),
                end_iso=filter_end_dt.isoformat(),
                snap_iso=filter_end_dt.isoformat(),
                category_filter=x_cat_filter,
                author_type=selected_acc_type,
                search_query=search_query or "",
                sort_mode=sort_mode,
                platform=x_plat_filter,
                data_version=_v_x,
            )

        def _fetch_x_now():
            with st.spinner(_busy("feed", "Social Media accounts")):
                try:
                    from nepal_social_scanner import scan_popular_nepal_social_posts
                    scan_popular_nepal_social_posts(force_refresh=True)
                except Exception:
                    pass

        render_infinite_workspace_feed(
            workspace="x",
            renderer=render_apple_x_post_card,
            noun="posts",
            filter_sig=_sig,
            category_filter=x_cat_filter,
            author_type=selected_acc_type,
            search_query=search_query or "",
            sort_mode=sort_mode,
            empty_icon="💬",
            empty_title="No social media posts found",
            empty_body="Try selecting 'All Platforms' or 'All Account Types' or choosing 'All News'.",
            on_fetch_now=_fetch_x_now,
            wa_sent_map=_shared_wa_sent_map,
            prefetched_init=_x_boot,
            platform=x_plat_filter,
        )

        with st.expander(":material/search: Live X searches", expanded=False):
            clean_q = search_query.strip() if search_query else ""
            x_cat_searches = [
                ("India", "🇮🇳", '("Nepal" OR "नेपाल" OR "India" OR "भारत") AND ("Modi" OR "border" OR "trade" OR "#NepalIndia")'),
                ("China", "🇨🇳", '("Nepal" OR "नेपाल" OR "China" OR "चीन") AND ("Beijing" OR "BRI" OR "Pokhara" OR "#NepalChina")'),
                ("Bangladesh", "🇧🇩", '("Nepal" OR "नेपाल" OR "Bangladesh" OR "बंगलादेश") AND ("Dhaka" OR "Yunus" OR "energy")'),
                ("Pakistan", "🇵🇰", '("Nepal" OR "नेपाल" OR "Pakistan" OR "पाकिस्तान") AND ("Islamabad" OR "SAARC")'),
                ("Internal", "🇳🇵", '("Nepal" OR "नेपाल") AND ("politics" OR "Oli" OR "Deuba" OR "Prachanda" OR "Balen" OR "संसद्")'),
                ("External", ":material/public:", '("Nepal" OR "नेपाल") AND ("diplomacy" OR "ambassador" OR "UN" OR "USAID" OR "MCC" OR "परराष्ट्र")'),
                ("Economy", ":material/trending_up:", '("Nepal" OR "नेपाल") AND ("economy" OR "NRB" OR "remittance" OR "inflation" OR "budget" OR "अर्थतन्त्र")'),
                ("Others", ":material/push_pin:", '("Nepal" OR "नेपाल") AND ("cricket" OR "cinema" OR "weather" OR "Everest" OR "संस्कृति")'),
                ("International", ":material/language:", '("geopolitics" OR "conflict" OR "diplomacy" OR "summit" OR "Ukraine" OR "Gaza" OR "BRICS")'),
            ]
            for row_idx in range(0, len(x_cat_searches), 3):
                cols = st.columns(3)
                for col_idx, (label, label_icon, query_str) in enumerate(x_cat_searches[row_idx:row_idx + 3]):
                    with cols[col_idx]:
                        full_q = f"({clean_q}) AND {query_str}" if clean_q else query_str
                        x_url = f"https://x.com/search?q={urllib.parse.quote_plus(full_q)}&f=live"
                        st.link_button(label, x_url, icon=label_icon, width="stretch")

    # -------------------------------------------------------------
    # SUBVIEW 2: MONITORED DIRECTORY (200+ ACCOUNTS)
    # -------------------------------------------------------------
    elif x_subview == "Directory":
        # Top KPI Metrics Cards Row (Apple HIG cards)
        kc1, kc2, kc3, kc4, kc5 = st.columns(5)
        with kc1:
            st.markdown(f"""
            <div class="apple-kpi-card">
                <div class="apple-kpi-card__label">Total Discovered</div>
                <div class="apple-kpi-card__value">{total_acc_count}</div>
                <div class="apple-kpi-card__subtitle">Researched network</div>
            </div>
            """, unsafe_allow_html=True)
        with kc2:
            st.markdown(f"""
            <div class="apple-kpi-card">
                <div class="apple-kpi-card__label">Verified Authentic</div>
                <div class="apple-kpi-card__value" style="color:var(--tint);">{verified_acc_count}</div>
                <div class="apple-kpi-card__subtitle">Zero mock accounts</div>
            </div>
            """, unsafe_allow_html=True)
        with kc3:
            st.markdown(f"""
            <div class="apple-kpi-card">
                <div class="apple-kpi-card__label">Active Monitored</div>
                <div class="apple-kpi-card__value" style="color:var(--green);">{active_acc_count}</div>
                <div class="apple-kpi-card__subtitle">Ingestion active</div>
            </div>
            """, unsafe_allow_html=True)
        with kc4:
            st.markdown(f"""
            <div class="apple-kpi-card">
                <div class="apple-kpi-card__label">Pending Review</div>
                <div class="apple-kpi-card__value" style="color:var(--amber);">{pending_acc_count}</div>
                <div class="apple-kpi-card__subtitle">Candidates queue</div>
            </div>
            """, unsafe_allow_html=True)
        with kc5:
            st.markdown(f"""
            <div class="apple-kpi-card">
                <div class="apple-kpi-card__label">Canonical Sectors</div>
                <div class="apple-kpi-card__value">{len(CANONICAL_X_CATEGORIES)}</div>
                <div class="apple-kpi-card__subtitle">Balanced coverage</div>
            </div>
            """, unsafe_allow_html=True)

        # Category Breakdown Badges Row
        cat_counts = x_kpis.get("by_category", {})
        badge_html = " ".join([
            f'<span class="acct-badge-cat" style="font-size:0.72rem; padding:4px 10px;">{cat}: <b>{cat_counts.get(cat, 0)}</b></span>'
            for cat in CANONICAL_X_CATEGORIES
        ])
        st.markdown(f'<div style="margin: 6px 0 16px 0; display:flex; flex-wrap:wrap; gap:6px;">{badge_html}</div>', unsafe_allow_html=True)

        # Filters Row
        flt_c1, flt_c2, flt_c3, flt_c4 = st.columns([2.2, 1.8, 1.3, 1.2])
        with flt_c1:
            dir_search = st.text_input("Search directory", placeholder="Search by name, handle (@...), role, or keywords…", label_visibility="collapsed", key="dir_search_input")
        with flt_c2:
            dir_cat = st.selectbox("Canonical Sector", [f"All Sectors ({len(CANONICAL_X_CATEGORIES)})"] + CANONICAL_X_CATEGORIES, label_visibility="collapsed", key="dir_cat_select")
        with flt_c3:
            dir_plat = st.selectbox("Platform", ["All Platforms", "X Only", "Facebook Only"], label_visibility="collapsed", key="dir_plat_select")
        with flt_c4:
            dir_status = st.selectbox("Status Filter", ["All Statuses", "Verified Only", "Active Monitored", "Paused Only", "Pending Review"], label_visibility="collapsed", key="dir_status_select")

        # Query Accounts from DB (or fallback)
        dir_filter_cat = None if dir_cat.startswith("All Sectors") else dir_cat
        sel_ver_status = None
        enabled_only = False
        if dir_status == "Verified Only":
            sel_ver_status = "verified"
        elif dir_status == "Active Monitored":
            enabled_only = True
        elif dir_status == "Pending Review":
            sel_ver_status = "pending_verification"

        sel_plat = None
        if dir_plat == "X Only":
            sel_plat = "x"
        elif dir_plat == "Facebook Only":
            sel_plat = "facebook"

        all_dir_accounts = get_all_x_accounts(
            category=dir_filter_cat,
            verification_status=sel_ver_status,
            enabled_only=enabled_only,
            search=dir_search,
            platform=sel_plat,
            limit=2000
        )
        if not all_dir_accounts:
            # Fallback to local verified directory
            all_dir_accounts = [
                a for a in VERIFIED_NEPAL_SOCIAL_DIRECTORY
                if (not dir_filter_cat or a.get("category") == dir_filter_cat)
                and (not sel_plat or str(a.get("platform", "x")).lower() == sel_plat.lower())
                and (not dir_search or dir_search.lower() in (a.get("name","")+a.get("handle","")+a.get("role","")+a.get("relevance","")).lower())
            ]

        if dir_plat == "X Only":
            all_dir_accounts = [a for a in all_dir_accounts if str(a.get("platform", "x")).lower() == "x"]
        elif dir_plat == "Facebook Only":
            all_dir_accounts = [a for a in all_dir_accounts if str(a.get("platform")).lower() == "facebook"]

        if dir_status == "Paused Only":
            all_dir_accounts = [a for a in all_dir_accounts if int(a.get("enabled", 1)) == 0]

        # Top Action Bar: Count + Export
        act_c1, act_c2 = st.columns([3, 1.2])
        with act_c1:
            st.caption(f"Showing **{len(all_dir_accounts)}** of {total_acc_count} researched accounts:")
        with act_c2:
            import pandas as pd
            export_df = pd.DataFrame([
                {
                    "platform": a.get("platform", "x"),
                    "handle": a.get("handle"),
                    "name": a.get("name"),
                    "category": a.get("category"),
                    "subcategory": a.get("subcategory"),
                    "profile": a.get("role") or a.get("profile_brief"),
                    "profile_url": a.get("profile_url"),
                    "enabled": "Active" if int(a.get("enabled", 1)) == 1 else "Paused",
                    "connection_status": a.get("connection_status"),
                    "last_verified_at": a.get("last_verified_at")
                }
                for a in all_dir_accounts
            ])
            csv_bytes = export_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "CSV",
                icon=":material/download:",
                help="Export directory as CSV",
                data=csv_bytes,
                file_name=f"nepal_social_monitored_accounts_{datetime.datetime.now(NEPAL_TZ).strftime('%Y%m%d')}.csv",
                mime="text/csv",
                width="stretch"
            )

        # Accounts Grid (3 Columns)
        if not all_dir_accounts:
            render_empty_state("🔍", "No matching accounts found", "Try clearing the search term or resetting the sector filter.")
        else:
            cols = st.columns(3)
            for idx, a in enumerate(all_dir_accounts):
                with cols[idx % 3]:
                    h = a.get("handle", "")
                    name = a.get("name", h)
                    plat = str(a.get("platform") or ("facebook" if "facebook.com" in str(a.get("profile_url","")) else "x")).lower()
                    plat_pill = '<span style="background:#1877F2; color:#fff; font-size:0.65rem; font-weight:700; padding:1px 5px; border-radius:3px; margin-right:4px;">FB</span>' if plat == "facebook" else '<span style="background:#0f172a; color:#fff; font-size:0.65rem; font-weight:700; padding:1px 5px; border-radius:3px; margin-right:4px;">𝕏</span>'
                    profile_url = a.get("profile_url") or (f"https://www.facebook.com/{h}" if plat == "facebook" else f"https://x.com/{h}")
                    cat = a.get("category", "Civil Society and Public Voices")
                    subcat = a.get("subcategory", "")
                    role = a.get("role") or a.get("profile_brief") or ""
                    avatar_bg = a.get("avatar_bg") or ("#1877f2" if plat == "facebook" else "#2563eb")
                    initials = a.get("initials") or (name[:2].upper() if name else "NP")
                    is_enabled = bool(int(a.get("enabled", 1)) == 1)

                    status_pill = '<span class="acct-status-pill acct-status-pill--active">● Active</span>' if is_enabled else '<span class="acct-status-pill acct-status-pill--paused">○ Paused</span>'

                    prefix = "fb/" if plat == "facebook" else "@"
                    st.markdown(f"""
                    <div class="acct-card-rich">
                        <div>
                            <div class="acct-card-rich__head">
                                {get_x_author_avatar_html(a, is_acct_card=True)}
                                <div style="overflow:hidden; flex:1;">
                                    <div class="acct-card-rich__name">{plat_pill}{html.escape(name)} <span style="color:#1D9BF0; font-size:0.82rem;">✓</span></div>
                                    <div class="acct-card-rich__handle">{prefix}{html.escape(h)}</div>
                                </div>
                            </div>
                            <div class="acct-card-rich__badges">
                                <span class="acct-badge-cat">{html.escape(cat)}</span>
                                {f'<span class="acct-badge-subcat">{html.escape(subcat)}</span>' if subcat else ''}
                            </div>
                            <div class="acct-card-rich__role" style="margin-top:6px; line-height:1.35; font-size:0.82rem; color:var(--label);"><b style="color:var(--label-2); font-weight:600;">Profile:</b> {html.escape(role or "Monitored critical voice")}</div>
                        </div>
                        <div class="acct-card-rich__footer">
                            <div class="acct-card-rich__links">
                                <a href="{html.escape(profile_url)}" target="_blank" rel="noopener noreferrer">Profile ↗</a>
                            </div>
                            <div style="display:flex; gap:6px; align-items:center;">
                                {status_pill}
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # Account controls: Monitor (On/Off) & Remove
                    ctrl_c1, ctrl_c2 = st.columns([1.6, 1], vertical_alignment="center")
                    with ctrl_c1:
                        t_val = st.toggle("Monitor", value=is_enabled, key=f"tgl_dir_{plat}_{h}_{idx}")
                        if t_val != is_enabled:
                            set_x_account_enabled(h, t_val, platform=plat)
                            st.session_state["data_version"] = int(st.session_state.get("data_version", 0)) + 1
                            _get_cached_x_workspace_bootstrap.clear()
                            get_cached_header_bundle.clear()
                            get_cached_login_bootstrap.clear()
                            st.toast(f"{prefix}{h} monitoring {'activated' if t_val else 'paused'}!", icon=":material/check_circle:")
                            st.rerun()
                    with ctrl_c2:
                        if st.button("Remove", key=f"btn_rm_dir_{plat}_{h}_{idx}", icon=":material/delete:", help=f"Remove {prefix}{h} from database & directory", width="stretch"):
                            delete_x_account(h, platform=plat)
                            st.session_state["data_version"] = int(st.session_state.get("data_version", 0)) + 1
                            _get_cached_x_workspace_bootstrap.clear()
                            get_cached_header_bundle.clear()
                            get_cached_login_bootstrap.clear()
                            st.toast(f"Removed {prefix}{h} from database & directory!", icon=":material/delete:")
                            st.rerun()

    # -------------------------------------------------------------
    # SUBVIEW 3: DISCOVERY & ACCOUNT ADMIN (CHIEF ADMIN)
    # -------------------------------------------------------------
    elif x_subview == "Admin":
        st.markdown("""
        <div style="background:var(--surface); border:1px solid var(--separator); border-radius:var(--r-md); padding:16px 20px; margin-bottom:18px;">
            <h3 style="margin:0 0 6px 0; font-size:1.1rem; font-weight:700;">Account Discovery & Verification Console</h3>
            <p style="margin:0; font-size:0.84rem; color:var(--label-2);">
                Continuous intelligence expansion pipeline for the Chief Admin. Rigorously research, verify, test reachability,
                and onboard new authentic Nepal-related voices across Facebook & X.
            </p>
        </div>
        """, unsafe_allow_html=True)

        admin_tab1, admin_tab2, admin_tab3 = st.tabs([
            ":material/person_add: Onboard",
            f":material/hourglass_top: Pending · {pending_acc_count}",
            ":material/shield: Audit"
        ])

        with admin_tab1:
            st.subheader("Add Nepal Social Media Account (Facebook & X)")
            with st.form("form_add_x_account", clear_on_submit=False):
                af_c1, af_c2 = st.columns(2)
                with af_c1:
                    new_platform = st.selectbox("Platform*", ["Facebook", "X (Twitter)"], key="onboard_platform_select")
                    new_handle = st.text_input("Handle or Page Slug (without @ or URL)*", placeholder="e.g. onlinekhabar or BasantaBasnet")
                    new_cat = st.selectbox("Canonical Monitoring Sector*", CANONICAL_X_CATEGORIES)
                with af_c2:
                    new_name = st.text_input("Full Display Name*", placeholder="e.g. Basanta Basnet")
                    new_role = st.text_input("Profile*", placeholder="e.g. Editor, OnlineKhabar (onlinekhabar.com)")
                    new_subcat = st.text_input("Subcategory", placeholder="e.g. Journalists & Commentators / Digital Media")

                btn_add_acc = st.form_submit_button("Save & Integrate Account into Monitoring Network", type="primary", width="stretch")

                if btn_add_acc:
                    norm_h = normalize_x_handle(new_handle)
                    if not norm_h or not new_name.strip() or not new_role.strip():
                        st.error("Please fill in all required fields (Platform, Handle/Slug, Display Name, and Profile).")
                    else:
                        plat_code = "facebook" if "facebook" in new_platform.lower() else "x"
                        profile_url = f"https://www.facebook.com/{norm_h}" if plat_code == "facebook" else f"https://x.com/{norm_h}"

                        # Check duplicate
                        existing_accs = get_all_x_accounts(search=norm_h, platform=plat_code)
                        duplicate = any(normalize_x_handle(ex.get("handle","")) == norm_h for ex in existing_accs)
                        if duplicate:
                            st.info(f"Account {norm_h} ({plat_code.title()}) already exists in the database. Updating profile...")

                        # Reachability
                        is_ok, reach_msg = True, "Reachable"
                        if plat_code == "x":
                            is_ok, reach_msg = verify_x_profile_connectivity(norm_h)

                        acc_payload = {
                            "platform": plat_code,
                            "handle": norm_h,
                            "name": new_name.strip(),
                            "profile_url": profile_url,
                            "category": new_cat,
                            "subcategory": new_subcat.strip() or "General",
                            "role": new_role.strip(),
                            "profile_brief": new_role.strip(),
                            "relevance": f"Monitored {plat_code.title()} voice: {new_name.strip()} ({new_role.strip()})",
                            "verification_status": "verified",
                            "source_url": profile_url,
                            "followers": "N/A",
                            "avatar_bg": "#1877f2" if plat_code == "facebook" else "#0f172a",
                            "initials": "".join([w[0].upper() for w in new_name.split()[:2]]) or "NP",
                            "enabled": 1,
                            "connection_status": "connected" if is_ok else "unreachable",
                            "last_verified_at": datetime.datetime.now(NEPAL_TZ).isoformat()
                        }
                        saved = upsert_single_x_account(acc_payload)
                        if saved:
                            st.success(f"Successfully integrated {new_name.strip()} ({plat_code.title()}) into monitoring! Status: {reach_msg}")
                            st.rerun()
                        else:
                            st.error(f"Failed to save account {norm_h} into database.")

        with admin_tab2:
            st.subheader("Review Pending Verification Candidates")
            pending_accounts = get_all_x_accounts(verification_status="pending_verification")
            if not pending_accounts:
                st.info("No accounts currently pending verification. All monitored accounts are verified!")
            else:
                for pa in pending_accounts:
                    ph = pa.get("handle")
                    pa_plat = pa.get("platform", "x")
                    with st.container(border=True):
                        pc1, pc2, pc3 = st.columns([3, 1, 1])
                        with pc1:
                            st.markdown(f"**{pa.get('name')}** (`{ph}`) · *{pa.get('category')}* · `{pa_plat.title()}`")
                            st.caption(f"Profile: {pa.get('role') or pa.get('profile_brief')}")
                        with pc2:
                            if st.button("Promote to Verified", key=f"btn_promote_{pa_plat}_{ph}", width="stretch"):
                                ok_prom, prom_msg = promote_pending_x_account(ph, platform=pa_plat)
                                if ok_prom:
                                    st.toast(f"Promoted {ph} to Verified!", icon=":material/verified:")
                                    st.rerun()
                                else:
                                    st.warning(prom_msg)
                        with pc3:
                            if st.button("Remove", key=f"btn_remove_{pa_plat}_{ph}", width="stretch", type="secondary"):
                                delete_x_account(ph, platform=pa_plat)
                                st.toast(f"Removed candidate {ph}", icon=":material/delete:")
                                st.rerun()

        with admin_tab3:
            st.subheader("Batch Network Reachability Audit")
            st.caption("Checks live reachability across monitored social media handles to detect suspended, renamed, or inaccessible profiles.")
            audit_sector = st.selectbox("Select Sector to Audit", ["All Sectors"] + CANONICAL_X_CATEGORIES, key="audit_sector_select")
            if st.button("Run Reachability Audit", icon=":material/speed:", type="primary"):
                with st.spinner("Pinging social media profile endpoints..."):
                    target_audit = get_all_x_accounts(category=(None if audit_sector == "All Sectors" else audit_sector), limit=30)
                    audit_results = []
                    for ta in target_audit:
                        t_handle = ta.get("handle")
                        t_plat = ta.get("platform", "x")
                        ok, msg = True, "Reachable"
                        if t_plat == "x":
                            ok, msg = verify_x_profile_connectivity(t_handle)
                        audit_results.append({
                            "Platform": t_plat.title(),
                            "Handle": f"@{t_handle}" if t_plat == "x" else f"fb/{t_handle}",
                            "Name": ta.get("name"),
                            "Sector": ta.get("category"),
                            "Accessible": "✅ Reachable" if ok else "❌ Unreachable",
                            "Details": msg
                        })
                    import pandas as pd
                    st.dataframe(pd.DataFrame(audit_results), use_container_width=True)
                    st.success(f"Audit completed for {len(audit_results)} profiles!")


# ==========================================
# SECTION 4: Analytics & Export
# ==========================================
@st.fragment
def render_export_analytics_section() -> None:
    _toolbar_columns("ex", {}, only_theme=True, show_timeframe=True)
    _render_active_search_chip()

    ex_c1, ex_c2, ex_c3, ex_c4 = st.columns([1.2, 1.3, 1.1, 1.4], gap="small")
    with ex_c1:
        sel_stream = st.selectbox("Feed Source", ["All Streams", "Nepali Media", "Indian Press", "Social Media"], key="univ_stream_filter", label_visibility="collapsed")
    with ex_c2:
        sel_cat = st.selectbox("News Category", ["All Categories"] + STRUCTURED_CATEGORIES, key="univ_cat_filter", label_visibility="collapsed")
    with ex_c3:
        sel_lang = st.selectbox("News Language", [ALL_LANG_DEFAULT, "Nepali", "English", "Nepali / English"], key="univ_lang_filter", label_visibility="collapsed")
    with ex_c4:
        kw_filter = st.text_input("Search Keyword", placeholder="Keyword or @handle", key="univ_kw_filter", icon=":material/search:", label_visibility="collapsed")

    _ana_bundle = get_cached_analytics_bundle(
        start_iso=cache_start_dt.isoformat() if cache_start_dt else "",
        end_iso=cache_end_dt.isoformat() if cache_end_dt else "",
        limit=500,
        data_version=_data_ver,
    )
    articles_src = _ana_bundle.get("nepali", [])
    indian_src = _ana_bundle.get("indian", [])
    x_src = _ana_bundle.get("x", [])

    if search_query and search_query.strip():
        filtered_articles = [a for a in articles_src if smart_search_match(a, search_query)]
        filtered_indian = [a for a in indian_src if smart_search_match(a, search_query)]
        filtered_x_posts = [p for p in x_src if smart_search_match(p, search_query)]
    else:
        filtered_articles = articles_src
        filtered_indian = indian_src
        filtered_x_posts = x_src

    all_unified_items = []
    for a in filtered_articles:
        all_unified_items.append({
            "stream": "Nepali Media",
            "title": (a.get("title") or "").strip(),
            "headline_en": a.get("headline_english", ""),
            "content": a.get("full_content") or a.get("summary", ""),
            "category": a.get("structured_category", "Others"),
            "source": a.get("source", "Nepali Media"),
            "language": a.get("language") or ("English" if a.get("source") in ENGLISH_NEPAL_PORTAL_NAMES else "Nepali"),
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
            "stream": "Social Media",
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
    import pandas as pd
    df_export = pd.DataFrame(rows_data)

    sum1, sum2, sum3, sum4 = st.columns(4)
    sum1.metric("Matches", f"{len(df_export):,}")
    sum2.metric("Nepal", f"{sum(1 for x in filtered_export_items if x['stream'] == 'Nepali Media'):,}")
    sum3.metric("India", f"{sum(1 for x in filtered_export_items if x['stream'] == 'Indian Press'):,}")
    sum4.metric("Social Media", f"{sum(1 for x in filtered_export_items if x['stream'] == 'Social Media'):,}")

    current_filter_sig = f"{sel_stream}_{sel_cat}_{sel_lang}_{kw_filter.strip()}_{len(filtered_export_items)}"
    st.session_state.setdefault("editor_ver_univ", 0)
    if st.session_state.get("last_univ_filter_sig") != current_filter_sig or "selected_links_univ" not in st.session_state:
        st.session_state["selected_links_univ"] = {x["link"] for x in filtered_export_items}
        st.session_state["last_univ_filter_sig"] = current_filter_sig

    selected_export_items = [x for x in filtered_export_items if x.get("link") in st.session_state["selected_links_univ"]]
    st.markdown(
        f'<div class="counter-badge" style="margin-bottom:8px;">{_ico("list", 13)} <b>{len(selected_export_items)} / {len(filtered_export_items)}</b> selected</div>',
        unsafe_allow_html=True,
    )

    if not df_export.empty:
        df_for_editor = df_export[["Stream", "Headline / Text", "Category", "Source / Author", "Language", "Published Date & Time", "Link"]].copy()
        df_for_editor.insert(0, "Include?", [link in st.session_state["selected_links_univ"] for link in df_for_editor["Link"]])

        col_config_univ = {
            "Include?": st.column_config.CheckboxColumn("✓", default=True, width="small"),
            "Stream": st.column_config.TextColumn("Stream", width="small"),
            "Headline / Text": st.column_config.TextColumn("Headline", width="large"),
            "Category": st.column_config.TextColumn("Category", width="small"),
            "Source / Author": st.column_config.TextColumn("Source", width="medium"),
            "Language": st.column_config.TextColumn("Language", width="small"),
            "Published Date & Time": st.column_config.TextColumn("Time", width="medium"),
            "Link": st.column_config.LinkColumn("Source Link", display_text="Open", width="small")
        }

        edited_df_univ = st.data_editor(
            df_for_editor,
            column_config=col_config_univ,
            disabled=[c for c in df_for_editor.columns if c != "Include?"],
            hide_index=True,
            width="stretch",
            key=f"univ_editor_{st.session_state['editor_ver_univ']}_{len(df_for_editor)}"
        )

        sel_links = st.session_state["selected_links_univ"]
        for link, inc in zip(edited_df_univ["Link"], edited_df_univ["Include?"]):
            if inc:
                sel_links.add(link)
            else:
                sel_links.discard(link)

        selected_export_items = [x for x in filtered_export_items if x.get("link") in st.session_state["selected_links_univ"]]

        st.write("")
        c_csv, c_docx = st.columns(2)
        with c_csv:
            csv_bytes = df_export.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label=f"CSV · {len(df_export):,}",
                help="Download all records as CSV",
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
                    if st.button(f"Word digest · {len(selected_export_items):,}", help="Build the executive Word document", icon=":material/description:", key="btn_prep_univ_docx", width="stretch", type="primary"):
                        with st.spinner(f"Compiling NEPAL DAILY NEWS DIGEST ({digest_dt.strftime('%B %d, %Y')}) with full body text…"):
                            from executive_docx_exporter import generate_executive_word_digest
                            from nepal_fetcher import batch_fetch_full_content
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
                        label="Word digest",
                        help=digest_filename,
                        icon=":material/download:",
                        data=st.session_state["docx_bytes_univ"],
                        file_name=digest_filename,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        width="stretch",
                        type="primary"
                    )
            else:
                st.caption(":material/info: Select rows to build the Word digest.")
    else:
        render_empty_state("📊", "No export records", "Try adjusting the search keyword or selecting 'All Streams'.")


if selected_nav in ("Social Media", "X"):
    render_x_section()
elif selected_nav == "Analytics & Export":
    render_export_analytics_section()


# ==========================================
# SECTION 5: Health & Diagnostics
# ==========================================
def _invalidate_ui_caches_after_indian_ingest() -> None:
    """Clears Indian Press health, feed, and session snapshot caches after manual Indian Press sync."""
    for fn in (
        _get_cached_indian_source_health,
        _get_cached_indian_workspace_bootstrap,
        get_active_indian_articles,
        _get_cached_feed_page_with_count,
        _get_cached_filtered_count,
        get_cached_header_bundle,
        get_cached_login_bootstrap,
        get_cached_analytics_bundle,
    ):
        if hasattr(fn, "clear"):
            fn.clear()
    st.session_state.pop("_hdr_state_cache", None)
    sess_map = st.session_state.get("feed_sessions")
    if isinstance(sess_map, dict):
        sess_map.pop("indian", None)
        sess_map.pop("live", None)
    sv = st.session_state.setdefault("stream_versions", {"nepali": 0, "indian": 0, "x": 0})
    sv["indian"] = int(sv.get("indian", 0)) + 1
    st.session_state["data_version"] = int(st.session_state.get("data_version", 0)) + 1
    st.session_state["last_sync_npt"] = datetime.datetime.now(NEPAL_TZ).strftime("%I:%M %p").lstrip("0")


def _invalidate_ui_caches_after_nepali_ingest() -> None:
    """Clears health, feed, and session snapshot caches after manual System Health ingestion/backfill."""
    for fn in (
        get_system_health_bundle,
        get_all_source_health,
        get_system_kpis,
        _get_cached_feed_page_with_count,
        _get_cached_filtered_count,
        get_cached_header_bundle,
        get_cached_login_bootstrap,
        get_cached_analytics_bundle,
        get_active_nepal_articles,
    ):
        if hasattr(fn, "clear"):
            fn.clear()
    st.session_state.pop("_hdr_state_cache", None)
    sess_map = st.session_state.get("feed_sessions")
    if isinstance(sess_map, dict):
        sess_map.pop("nepali", None)
        sess_map.pop("live", None)
    sv = st.session_state.setdefault("stream_versions", {"nepali": 0, "indian": 0, "x": 0})
    sv["nepali"] = int(sv.get("nepali", 0)) + 1
    st.session_state["data_version"] = int(st.session_state.get("data_version", 0)) + 1
    st.session_state["last_sync_npt"] = datetime.datetime.now(NEPAL_TZ).strftime("%I:%M %p").lstrip("0")


@st.fragment
def render_system_health_section() -> None:
    _tr = get_db_transport_info()
    _tr_label = "Supavisor Transaction Pool (port 6543)" if _tr.get("mode") == "supavisor_pool" else "Supabase Management API (fallback)"
    st.caption(_tr_label)

    try:
        register_portal_sources(TOP_NEPAL_NEWS_PORTALS)
        _sys_bundle = get_system_health_bundle()
        kpis = _sys_bundle.get("kpis") or get_system_kpis()
        health_data = _sys_bundle.get("health") or []
    except Exception:
        kpis = {
            "total_sources": len(TOP_NEPAL_NEWS_PORTALS),
            "active_sources": len(TOP_NEPAL_NEWS_PORTALS),
            "operational": len(TOP_NEPAL_NEWS_PORTALS),
            "stale": 0,
            "degraded": 0,
            "failing": 0,
            "avg_latency_secs": 0.75,
            "articles_1h": 0,
            "articles_24h": 0,
            "articles_7d": 0,
            "total_stored_articles": 0,
        }
        health_data = []

    stale_portals = []
    for _h in health_data:
        if "is_stale" not in _h:
            _h["is_stale"] = is_portal_stale(_h)
        if _h["is_stale"] and (_h.get("status") or "operational") == "operational":
            _h["status"] = "stale"
        if _h["is_stale"] or _h.get("status") == "stale":
            stale_portals.append(_h)

    _failing_cnt = int(kpis.get("failing") or 0)
    _stale_cnt = len(stale_portals) if health_data else int(kpis.get("stale") or 0)
    if _failing_cnt > 0:
        _op_delta = f"-{_failing_cnt} failing"
    elif _stale_cnt > 0:
        _op_delta = f"{_stale_cnt} stale (>24h)"
    else:
        _op_delta = "Healthy"

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Portals", f"{kpis['total_sources']}")
    k2.metric("Online", f"{kpis['operational']}", delta=_op_delta)
    k3.metric("1h", f"{kpis['articles_1h']:,}")
    k4.metric("24h", f"{kpis['articles_24h']:,}")
    k5.metric("Stored", f"{kpis['total_stored_articles']:,}")
    k6.metric("Latency", f"{kpis['avg_latency_secs']}s")

    if stale_portals:
        _stale_names = ", ".join(
            f"{sp['name']} ({str(sp.get('latest_article_pub_dt') or '')[:16]})"
            for sp in stale_portals[:5]
        )
        st.warning(
            f"{len(stale_portals)} enabled high/standard portal(s) returned HTTP 200 OK but have no fresh articles in the last 24h (possible silent CMS redesign): {_stale_names}",
            icon=":material/warning:",
            title="Stale 200 OK portal alert",
        )

    st.write("")

    ctrl_col1, ctrl_col2 = st.columns([1.8, 2.2])
    _n_portals = len(TOP_NEPAL_NEWS_PORTALS)
    _all_portals_lbl = f"All {_n_portals} Portals"
    with ctrl_col1:
        st.markdown("##### Ingestion")
        if st.button(f"Ingest all · {_n_portals}", icon=":material/refresh:", width="stretch", key="btn_trigger_all_ingest"):
            with st.spinner(f"Executing parallel discovery across all {_n_portals} Nepali news portals…"):
                from nepal_news_scheduler import run_all_sources_discovery
                sync_res = run_all_sources_discovery(parallel_workers=20, force_all=True)
                _invalidate_ui_caches_after_nepali_ingest()
                st.success(f"✓ Checked {sync_res['total_checked']} portals · Ingested {sync_res['total_ingested']} fresh articles.")
                time.sleep(1)
                st.rerun()
        st.caption("Auto-polled by tier.")

    with ctrl_col2:
        st.markdown("##### Backfill")
        with st.expander(":material/history: Backfill", expanded=False):
            st.caption("Inspect past days' archives, category pagination, and XML sitemaps:")
            bf_days = st.select_slider("Backfill Time Horizon:", options=[1, 3, 5, 7, 14], value=3, format_func=lambda x: f"Past {x} Days")
            portal_options = [_all_portals_lbl] + NEPALI_PORTAL_NAMES
            bf_targets = st.multiselect("Select Target Portals:", portal_options, default=[_all_portals_lbl])

            if st.button("Start", icon=":material/history:", width="stretch", key="btn_exec_backfill"):
                targets = None if _all_portals_lbl in bf_targets else bf_targets
                with st.spinner(f"Initiating deep backfill for {len(targets) if targets else _n_portals} portals across the past {bf_days} days…"):
                    from nepal_news_scheduler import run_historical_backfill
                    bf_res = run_historical_backfill(source_names=targets, days_back=bf_days, parallel_workers=10)
                    _invalidate_ui_caches_after_nepali_ingest()
                    st.success(f"✓ Backfill Complete! Ingested {bf_res['total_ingested']} historical articles from {bf_res['sources_backfilled']} outlets.")
                    time.sleep(1)
                    st.rerun()

    st.write("")
    st.markdown(f"##### Indian press · {len(TOP_INDIAN_MEDIA_SOURCES)} outlets")
    ind_health_rows = _get_cached_indian_source_health()
    ind_by_name = {r.get("source_name"): r for r in ind_health_rows if r.get("source_name")}
    ind_merged = []
    for scfg in TOP_INDIAN_MEDIA_SOURCES:
        sname = scfg["name"]
        rec = ind_by_name.get(sname) or {}
        st_val = rec.get("status") or "pending"
        last_disc_raw = rec.get("last_discovery_time")
        last_disc_str = ""
        if isinstance(last_disc_raw, datetime.datetime):
            dt_npt = last_disc_raw.astimezone(NEPAL_TZ) if last_disc_raw.tzinfo else last_disc_raw.replace(tzinfo=datetime.timezone.utc).astimezone(NEPAL_TZ)
            last_disc_str = dt_npt.strftime("%b %d, %I:%M %p")
        elif last_disc_raw:
            last_disc_str = str(last_disc_raw)[:19]
        latest_pub_raw = rec.get("latest_article_pub_dt")
        latest_pub_str = str(latest_pub_raw)[:16] if latest_pub_raw else "—"
        status_icon = {"operational": "🟢 Operational", "degraded": "🟡 Degraded", "failing": "🔴 Failing"}.get(st_val, "⚪ Pending")
        ind_merged.append({
            "Outlet": sname,
            "Status": status_icon,
            "_status": st_val,
            "Type": str(rec.get("source_type") or scfg.get("type", "search_rss")).upper(),
            "Language": scfg.get("lang", "English"),
            "24h": int(rec.get("rel_24h") or 0),
            "7d": int(rec.get("rel_7d") or 0),
            "Last Run": f"{int(rec.get('substantive_count') or 0)}/{int(rec.get('discovered_count') or 0)}",
            "Latency (s)": round(float(rec.get("latency_secs") or 0.0), 2),
            "Latest Story": latest_pub_str,
            "Last Polled (NPT)": last_disc_str or "Pending",
            "Error": (rec.get("last_error_message") or "")[:90],
        })

    ind_op = sum(1 for r in ind_merged if r["_status"] == "operational")
    ind_fail = sum(1 for r in ind_merged if r["_status"] == "failing")
    ind_24h_tot = sum(r["24h"] for r in ind_merged)
    ind_7d_tot = sum(r["7d"] for r in ind_merged)

    ik1, ik2, ik3, ik4, ik_btn = st.columns([1, 1.1, 1, 1, 1.4], gap="small")
    ik1.metric("Outlets", f"{len(ind_merged)}")
    ik2.metric("Online", f"{ind_op}", delta="All Healthy" if ind_fail == 0 and ind_op > 0 else (f"-{ind_fail} failing" if ind_fail else "Pending"))
    ik3.metric("24h", f"{ind_24h_tot}")
    ik4.metric("7d", f"{ind_7d_tot}")
    with ik_btn:
        st.write("")
        if st.button("Refresh", icon=":material/refresh:", help=f"Re-scan {len(TOP_INDIAN_MEDIA_SOURCES)} Indian outlets", width="stretch", key="btn_trigger_indian_health"):
            with st.spinner(f"Running precision discovery across {len(TOP_INDIAN_MEDIA_SOURCES)} Indian outlets…"):
                from nepal_fetcher import fetch_nepal_in_indian_media
                ind_cands = fetch_nepal_in_indian_media(max_workers=16, force_refresh=True, return_all_stored=False)
                _invalidate_ui_caches_after_indian_ingest()
                subst_cnt = sum(1 for c in (ind_cands or []) if c.get("relevance_status") == "substantive")
                st.success(f"✓ Scanned {len(TOP_INDIAN_MEDIA_SOURCES)} Indian outlets · {subst_cnt} substantive stories.")
                time.sleep(0.8)
                st.rerun()

    ih_c1, ih_c2, ih_c3 = st.columns([1.6, 1.2, 1.2], gap="small")
    with ih_c1:
        ind_srch = st.text_input("Filter Indian outlet", placeholder="Filter Indian outlet…", key="inp_ind_health_srch", label_visibility="collapsed")
    with ih_c2:
        ind_st_f = st.selectbox("Indian Status", ["All Statuses", "Operational Only", "Degraded Only", "Failing Only"], key="sel_ind_health_st", label_visibility="collapsed")
    with ih_c3:
        ind_lang_f = st.selectbox("Indian Language", [ALL_LANG_DEFAULT, "English Only", "Hindi Only"], key="sel_ind_health_lang", label_visibility="collapsed")

    ind_view = ind_merged
    if ind_srch and ind_srch.strip():
        qs = ind_srch.strip().lower()
        ind_view = [r for r in ind_view if qs in r["Outlet"].lower()]
    if ind_st_f == "Operational Only":
        ind_view = [r for r in ind_view if r["_status"] == "operational"]
    elif ind_st_f == "Degraded Only":
        ind_view = [r for r in ind_view if r["_status"] == "degraded"]
    elif ind_st_f == "Failing Only":
        ind_view = [r for r in ind_view if r["_status"] == "failing"]
    if ind_lang_f == "English Only":
        ind_view = [r for r in ind_view if r["Language"] == "English"]
    elif ind_lang_f == "Hindi Only":
        ind_view = [r for r in ind_view if r["Language"] == "Hindi"]

    ind_view_sorted = sorted(ind_view, key=lambda r: (0 if r["_status"] == "failing" else (1 if r["_status"] == "degraded" else 2), -r["7d"], -r["24h"], r["Outlet"]))
    ind_table_rows = [{k: v for k, v in r.items() if not k.startswith("_")} for r in ind_view_sorted]
    st.dataframe(
        ind_table_rows,
        width="stretch",
        hide_index=True,
        height=320,
        alt="Indian press source health table",
    )

    st.write("")
    st.markdown("##### Nepali sources")

    sh_c1, sh_c2, sh_c3, sh_c4 = st.columns([1.4, 1.2, 1.1, 1.1], gap="small")
    with sh_c1:
        admin_search_src = st.text_input("Source Name", placeholder="Filter by source name…", key="inp_admin_src_srch", label_visibility="collapsed")
    with sh_c2:
        admin_status_filter = st.selectbox("Status Filter", ["All Statuses", "Operational Only", "Stale Only", "Degraded Only", "Failing Only"], key="sel_admin_status", label_visibility="collapsed")
    with sh_c3:
        admin_lang_filter = st.selectbox("Source Language", [ALL_LANG_DEFAULT, "Nepali Only", "English Only"], key="sel_admin_lang", label_visibility="collapsed")
    with sh_c4:
        admin_tier_filter = st.selectbox("Check Interval", ["All Tiers", "High (8m)", "Standard (18m)", "Low (40m)"], key="sel_admin_tier", label_visibility="collapsed")

    filtered_health = health_data
    if admin_search_src and admin_search_src.strip():
        q_src = admin_search_src.strip().lower()
        filtered_health = [h for h in filtered_health if q_src in h["name"].lower()]
    if admin_status_filter == "Operational Only":
        filtered_health = [h for h in filtered_health if h.get("status") == "operational"]
    elif admin_status_filter == "Stale Only":
        filtered_health = [h for h in filtered_health if h.get("status") == "stale" or h.get("is_stale")]
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

    _boost_handle_by_portal = {
        p["name"]: p["x_boost_handle"]
        for p in TOP_NEPAL_NEWS_PORTALS
        if p.get("x_boost_handle")
    }

    for s_idx, src in enumerate(filtered_health):
        s_name = src["name"]
        s_status = src.get("status", "operational")
        s_lang = src.get("lang", "Nepali")
        s_type = src.get("type", "rss").upper()
        s_priority = src.get("priority", "standard").capitalize()
        s_interval = src.get("check_interval_mins", 15)
        s_enabled = bool(src.get("enabled", 1))
        s_boost_h = _boost_handle_by_portal.get(s_name, "")

        if s_status == "operational":
            status_cls, status_txt = "status-pill--ok", "Operational"
            card_accent = "health-card--ok"
        elif s_status == "stale" or src.get("is_stale"):
            status_cls, status_txt = "status-pill--warn", "Stale (>24h)"
            card_accent = "health-card--warn"
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
        boost_pill_html = f'<span class="pill">{_ico("bolt", 11)} @{html.escape(s_boost_h)}</span>' if s_boost_h else ""

        _hc_url = html.escape(src.get("url", ""), quote=True)
        st.markdown(f"""
        <div class="health-card {card_accent}">
            <div class="health-card__head">
                <div class="health-card__title">
                    <span class="health-card__name">{html.escape(s_name)}</span>
                    <span class="status-pill {status_cls}">● {status_txt}</span>
                    <span class="pill">{_ico("clock", 11)} {s_interval}m · {s_priority}</span>
                    <span class="pill">{_ico("rss", 11)} {s_type}</span>
                    {boost_pill_html}
                    <span class="pill">{_ico("globe", 11)} {s_lang}</span>
                </div>
                <div class="health-card__meta" title="Last polled · latency">{_ico("clock", 11)} {html.escape(str(last_disc)[:16])} · {lat}s</div>
            </div>
            <div class="health-card__stats"><b>{c_1h}</b> 1h · <b>{c_24h}</b> 24h · <b>{c_7d}</b> 7d · <b>{c_tot:,}</b> stored</div>
            <div class="health-card__latest">
                <a href="{html.escape(latest_link)}" target="_blank" rel="noopener noreferrer" title="{html.escape(str(latest_pub)[:19])}">{html.escape(latest_title[:110])}</a>
                <a class="hc-link" href="{_hc_url}" target="_blank" rel="noopener noreferrer" title="Open source endpoint" aria-label="Open source endpoint"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 17 17 7M8 7h9v9"/></svg></a>
            </div>
        </div>
        """, unsafe_allow_html=True)

        sc1, sc2, sc3, sc4 = st.columns([1.5, 1.5, 1.5, 1.5])
        with sc1:
            st.markdown('<div class="hc-actions-anchor"></div>', unsafe_allow_html=True)
            if st.button("Refresh", icon=":material/refresh:", help=f"Refresh {s_name}", key=f"btn_ref_src_{s_name}_{s_idx}", width="stretch"):
                with st.spinner(f"Ingesting latest feeds from {s_name}…"):
                    from nepal_news_scheduler import run_single_source_discovery
                    portal_cfg = next((p for p in TOP_NEPAL_NEWS_PORTALS if p["name"] == s_name), None)
                    if portal_cfg:
                        run_single_source_discovery(portal_cfg, max_articles=40)
                        _invalidate_ui_caches_after_nepali_ingest()
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
            toggle_label = "Disable" if s_enabled else "Enable"
            toggle_icon = ":material/cancel:" if s_enabled else ":material/check_circle:"
            if st.button(toggle_label, icon=toggle_icon, key=f"btn_tog_en_{s_name}_{s_idx}", width="stretch"):
                set_source_enabled(s_name, not s_enabled)
                st.rerun()
        with sc4:
            if src.get("last_error_message"):
                with st.expander(":material/error: Log", expanded=False):
                    st.error(src.get("last_error_message"))
            else:
                st.caption(":material/check_circle: No errors")

    with st.expander(":material/troubleshoot: Diagnostics", expanded=False):
        low_coverage_sources = [
            h for h in health_data 
            if h.get("count_24h", 0) == 0 and h.get("enabled", 1) and (h.get("count_7d", 0) == 0 or h.get("status") in ["failing", "degraded"])
        ]
        stale_diag_sources = [
            h for h in health_data
            if h.get("enabled", 1) and (h.get("status") == "stale" or h.get("is_stale"))
        ]
        quiet_sources = [
            h for h in health_data 
            if h.get("count_24h", 0) == 0 and h.get("enabled", 1) and h.get("count_7d", 0) > 0 and h.get("status") not in ["failing", "degraded", "stale"]
        ]
        if stale_diag_sources:
            st.warning(f"**Stale:** {len(stale_diag_sources)} enabled high/standard portal(s) have `latest_article_pub_dt` older than 24h:")
            for sds in stale_diag_sources:
                st.write(f"- **{sds['name']}** ({sds['priority']} · {sds['type']}): Latest `{str(sds.get('latest_article_pub_dt') or '—')[:19]}` · Endpoint: `{sds['url']}`")
        if low_coverage_sources:
            st.warning(f"**Low discovery:** {len(low_coverage_sources)} enabled portals have produced 0 articles and require endpoint review:")
            for lcs in low_coverage_sources:
                st.write(f"- **{lcs['name']}** ({lcs['type']} · {lcs['lang']}): Status `{lcs['status']}` · Endpoint: `{lcs['url']}`")
        if not low_coverage_sources and not stale_diag_sources:
            st.success("All feeds healthy.", icon=":material/check_circle:")

        if quiet_sources:
            st.info(f"**Quiet:** {len(quiet_sources)} portals (e.g. {', '.join([q['name'] for q in quiet_sources[:3]])}) publish on a weekly or holiday schedule. Their scrapers are operational and will automatically ingest stories when published.")


if selected_nav == "System Health":
    _toolbar_columns("hl", {}, only_theme=True)
    render_system_health_section()

