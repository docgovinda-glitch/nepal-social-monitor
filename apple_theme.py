"""
apple_theme.py
Single source of truth for the dashboard's visual language.

Design principles (Apple HIG inspired):
  • One tint colour, neutral greys, generous whitespace.
  • One type scale, one radius scale, one shadow scale — all exposed as CSS tokens.
  • Shared "pill" base for every chip/badge so variants only change colour.
  • Accessible by default: visible focus rings and prefers-reduced-motion support.
"""

APPLE_DESIGN_SYSTEM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* ==========================================================
       1. DESIGN TOKENS
       ========================================================== */
    :root {
        --font: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", "Segoe UI", sans-serif;

        /* Neutrals */
        --bg: #F5F5F7;
        --surface: #FFFFFF;
        --surface-muted: #F5F5F7;
        --label: #1D1D1F;
        --label-2: #6E6E73;
        --label-3: #86868B;
        --separator: rgba(0, 0, 0, 0.08);
        --separator-strong: rgba(0, 0, 0, 0.14);

        /* Single tint (matches .streamlit/config.toml primaryColor) */
        --tint: #526A85;
        --tint-hover: #405872;
        --tint-soft: rgba(82, 106, 133, 0.10);
        --link: #0066CC;

        /* Semantic */
        --green: #1E8E3E;  --green-soft: #E8F5EC;
        --amber: #B25E09;  --amber-soft: #FFF4E5;
        --red: #C9302C;    --red-soft: #FDECEC;

        /* Scales */
        --r-sm: 8px;  --r-md: 12px;  --r-lg: 16px;  --r-pill: 999px;
        --shadow-1: 0 1px 2px rgba(0, 0, 0, 0.04), 0 1px 1px rgba(0, 0, 0, 0.02);
        --shadow-2: 0 6px 20px rgba(0, 0, 0, 0.06), 0 1px 3px rgba(0, 0, 0, 0.03);
        --ease: cubic-bezier(0.16, 1, 0.3, 1);
    }

    /* ==========================================================
       2. FOUNDATION
       ========================================================== */
    html, body, .stMarkdown, p, label, h1, h2, h3, h4, h5, h6, button, input {
        font-family: var(--font) !important;
        -webkit-font-smoothing: antialiased !important;
        -moz-osx-font-smoothing: grayscale !important;
    }
    [data-testid="stAppViewContainer"], .main { background-color: var(--bg) !important; }
    .block-container { padding-top: 2rem !important; padding-bottom: 3rem !important; max-width: 1240px !important; }
    header[data-testid="stHeader"] { background: transparent !important; height: 1.5rem !important; }
    hr { border-color: var(--separator) !important; margin: 1.25rem 0 !important; }
    a { color: var(--link); }

    *:focus-visible {
        outline: 2px solid var(--tint) !important;
        outline-offset: 2px !important;
        border-radius: var(--r-sm);
    }

    /* ==========================================================
       3. APP HEADER & SIDEBAR BRAND CARD (Apple HIG)
       ========================================================== */
    .app-header {
        display: flex; justify-content: space-between; align-items: center; gap: 12px;
        padding: 14px 22px; margin-bottom: 20px;
        background: rgba(255, 255, 255, 0.72);
        backdrop-filter: blur(24px) saturate(180%);
        -webkit-backdrop-filter: blur(24px) saturate(180%);
        border: 1px solid rgba(255, 255, 255, 0.8);
        border-radius: var(--r-lg);
        box-shadow: var(--shadow-1);
    }
    .app-header__brand { display: flex; align-items: center; gap: 12px; }
    .app-header__flag { font-size: 1.7rem; line-height: 1; }
    .app-header__title { font-size: 1.22rem !important; font-weight: 700 !important; letter-spacing: -0.022em !important; margin: 0 !important; line-height: 1.15 !important; color: var(--label) !important; padding: 0 !important; }
    .app-header__subtitle { font-size: 0.78rem !important; color: var(--label-2) !important; margin: 2px 0 0 0 !important; }

    /* Sidebar Brand Card */
    .sidebar-brand-card {
        display: flex;
        flex-direction: column;
        gap: 8px;
        padding: 2px 0 8px 0;
    }
    .sidebar-brand-card.standalone {
        background: var(--surface);
        border: 1px solid var(--separator);
        border-radius: var(--r-md);
        padding: 14px 16px;
        box-shadow: var(--shadow-1);
        margin-bottom: 8px;
    }
    .sidebar-brand-card__row1 {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
    }
    .sidebar-brand-card__brand {
        display: flex;
        align-items: center;
        gap: 8px;
        min-width: 0;
    }
    .sidebar-brand-card__flag {
        font-size: 1.35rem;
        line-height: 1;
        flex-shrink: 0;
    }
    .sidebar-brand-card__title {
        font-size: 0.95rem !important;
        font-weight: 700 !important;
        letter-spacing: -0.022em !important;
        color: var(--label) !important;
        line-height: 1.2 !important;
        margin: 0 !important;
        padding: 0 !important;
        white-space: nowrap;
    }
    .sidebar-brand-card__subtitle {
        font-size: 0.72rem !important;
        color: var(--label-2) !important;
        letter-spacing: -0.01em !important;
        margin: 4px 0 0 0 !important;
        padding: 0 !important;
        line-height: 1.45 !important;
        white-space: nowrap;
        display: block !important;
    }
    .sidebar-brand-card .live-pill {
        padding: 2px 7px;
        font-size: 0.68rem;
        font-weight: 600;
        flex-shrink: 0;
        white-space: nowrap;
    }

    .live-pill {
        display: inline-flex; align-items: center; gap: 7px;
        background: var(--green-soft); color: var(--green);
        padding: 5px 12px; border-radius: var(--r-pill);
        font-size: 0.74rem; font-weight: 600; letter-spacing: 0.01em;
    }
    .live-pill__dot { width: 6px; height: 6px; border-radius: 50%; background: var(--green); animation: livePulse 2s infinite; }
    @keyframes livePulse {
        0% { box-shadow: 0 0 0 0 rgba(30, 142, 62, 0.45); }
        70% { box-shadow: 0 0 0 6px rgba(30, 142, 62, 0); }
        100% { box-shadow: 0 0 0 0 rgba(30, 142, 62, 0); }
    }

    /* ==========================================================
       4. PAGE HEADER (large title per workspace)
       ========================================================== */
    .page-header { display: flex; align-items: flex-end; justify-content: space-between; flex-wrap: wrap; gap: 10px; margin: 4px 0 16px 0; }
    .page-header__title { font-size: 1.65rem !important; font-weight: 700 !important; letter-spacing: -0.028em !important; margin: 0 !important; padding: 0 !important; color: var(--label) !important; line-height: 1.1 !important; }
    .page-header__subtitle { font-size: 0.86rem; color: var(--label-2); margin: 4px 0 0 0; }
    .page-header__meta { display: inline-flex; align-items: center; gap: 6px; flex-wrap: wrap; }

    /* ==========================================================
       5. PILLS / CHIPS / BADGES (shared base + colour variants)
       ========================================================== */
    .pill, .portal-tag, .indian-portal-tag, .time-badge, .cat-badge, .conf-review-badge,
    .x-sentiment-badge, .x-metric-item, .status-pill {
        display: inline-flex; align-items: center; gap: 4px;
        padding: 3px 9px; border-radius: var(--r-pill);
        font-size: 0.72rem; font-weight: 600; line-height: 1.35; white-space: nowrap;
        background: var(--surface-muted); color: var(--label-2);
        border: 1px solid transparent;
    }
    .portal-tag { background: var(--label); color: #FFFFFF; }
    .indian-portal-tag { background: #FFF4EA; color: #B4530D; }
    .time-badge { font-weight: 500; }
    .pill--success { background: var(--green-soft); color: var(--green); }
    .pill--warn, .conf-review-badge { background: var(--amber-soft); color: var(--amber); }
    .pill--tint { background: var(--tint-soft); color: var(--tint); }
    .sec-tag-chip { font-size: 0.7rem; font-weight: 500; color: var(--label-3); }
    .chip-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }

    .cat-badge--india { background: #FFF6E0; color: #8A5300; }
    .cat-badge--china { background: #FDECEC; color: #A61B1B; }
    .cat-badge--pakistan { background: #E8F5EC; color: #1B6B35; }
    .cat-badge--bangladesh { background: #E3F6F8; color: #106270; }
    .cat-badge--internal { background: #EEF0FF; color: #3A3FB0; }
    .cat-badge--external { background: #F4ECFF; color: #6B2BB0; }
    .cat-badge--economy { background: #E6F6EF; color: #0B6B47; }
    .cat-badge--international { background: #EFEAFD; color: #5427B5; }
    .cat-badge--others { background: var(--surface-muted); color: var(--label-2); }

    .status-pill--ok { background: var(--green-soft); color: var(--green); }
    .status-pill--warn { background: var(--amber-soft); color: var(--amber); }
    .status-pill--fail { background: var(--red-soft); color: var(--red); }

    /* ==========================================================
       6. CARDS (articles, X posts, accounts, health)
       ========================================================== */
    .apple-news-card, .x-post-card, .acct-card, .health-card {
        background: var(--surface);
        border: 1px solid var(--separator);
        border-radius: var(--r-md);
        box-shadow: var(--shadow-1);
        transition: box-shadow 0.25s var(--ease), border-color 0.25s var(--ease);
    }
    .apple-news-card:hover, .x-post-card:hover, .acct-card:hover, .health-card:hover {
        box-shadow: var(--shadow-2);
        border-color: var(--separator-strong);
    }

    /* Article card */
    .apple-news-card { position: relative; padding: 16px 20px 14px 22px; margin-bottom: 12px; overflow: hidden; }
    .apple-news-card::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--accent, #C7C7CC); }
    .accent--india { --accent: #F5A623; }
    .accent--china { --accent: #E5484D; }
    .accent--pakistan { --accent: #30A46C; }
    .accent--bangladesh { --accent: #12A5B5; }
    .accent--internal { --accent: #5B5BD6; }
    .accent--external { --accent: #8E4EC6; }
    .accent--economy { --accent: #0E9F6E; }
    .accent--international { --accent: #6E56CF; }
    .accent--others { --accent: #C7C7CC; }
    .accent--indian-press { --accent: #F76B15; }

    .apple-card-meta { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
    .apple-card-title { margin: 0 0 6px 0 !important; padding: 0 !important; font-size: 1.04rem !important; font-weight: 650 !important; line-height: 1.4 !important; letter-spacing: -0.014em !important; }
    .apple-card-title a { color: var(--label) !important; text-decoration: none !important; }
    .apple-card-title a:hover { color: var(--link) !important; }
    .apple-card-summary { color: var(--label-2); font-size: 0.88rem; line-height: 1.55; margin: 0 0 6px 0; }
    .apple-card-footer { display: flex; justify-content: flex-end; margin-top: 8px; }
    .apple-card-cta, .x-cta-link {
        display: inline-flex; align-items: center; gap: 4px;
        color: var(--link) !important; font-size: 0.78rem; font-weight: 600;
        text-decoration: none !important; padding: 4px 2px;
    }
    .apple-card-cta:hover, .x-cta-link:hover { text-decoration: underline !important; }

    /* X post card */
    .x-post-card { padding: 16px 20px; margin-bottom: 12px; }
    .x-post-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
    .x-post-header__meta { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
    .x-author-box { display: flex; align-items: center; gap: 10px; min-width: 0; }
    .x-avatar {
        width: 36px; height: 36px; min-width: 36px; border-radius: 50%;
        display: inline-flex; align-items: center; justify-content: center;
        color: #FFFFFF; font-weight: 700; font-size: 0.76rem; letter-spacing: 0.02em;
    }
    .x-author-meta { display: flex; flex-direction: column; line-height: 1.25; min-width: 0; }
    .x-author-name { font-size: 0.92rem; font-weight: 650; color: var(--label); display: inline-flex; align-items: center; gap: 4px; }
    .x-author-handle { font-size: 0.76rem; color: var(--label-2); }
    .x-type-badge { color: var(--tint); font-weight: 600; }
    .x-verified-badge {
        display: inline-flex; align-items: center; justify-content: center;
        width: 15px; height: 15px; border-radius: 50%;
        background: #1D9BF0; color: #FFFFFF; font-weight: 700; font-size: 0.6rem;
    }
    .x-post-text { font-size: 0.93rem; line-height: 1.55; color: var(--label); margin: 10px 0 12px 0; white-space: pre-wrap; word-break: break-word; }
    .x-post-text b { color: var(--link); font-weight: 600; }
    .x-engagement-bar { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; padding-top: 10px; border-top: 1px solid var(--separator); }
    .x-metrics-group { display: inline-flex; align-items: center; gap: 6px; flex-wrap: wrap; }
    .x-metric-item { font-weight: 500; }
    .x-sentiment-positive { background: var(--green-soft); color: var(--green); }
    .x-sentiment-alert { background: var(--red-soft); color: var(--red); }

    /* Account directory card */
    .acct-card { padding: 12px; margin-bottom: 12px; display: flex; flex-direction: column; justify-content: space-between; min-height: 124px; }
    .acct-card__head { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
    .acct-card__avatar { width: 28px; height: 28px; font-size: 0.66rem; min-width: 28px; }
    .acct-card__name { font-weight: 600; font-size: 0.82rem; color: var(--label); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .acct-card__handle { font-size: 0.7rem; color: var(--label-2); }
    .acct-card__role { font-size: 0.72rem; color: var(--label-2); line-height: 1.4; margin: 4px 0 8px 0; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
    .acct-card__links { border-top: 1px solid var(--separator); padding-top: 6px; font-size: 0.72rem; display: flex; gap: 10px; }
    .acct-card__links a { color: var(--link); text-decoration: none; font-weight: 600; }

    /* Enhanced Account Directory Card (200+ Verified Accounts) */
    .acct-card-rich {
        background: var(--surface);
        border: 1px solid var(--separator);
        border-radius: var(--r-md);
        box-shadow: var(--shadow-1);
        padding: 14px 16px;
        margin-bottom: 14px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        min-height: 200px;
        transition: transform 0.15s ease, box-shadow 0.2s ease, border-color 0.2s ease;
    }
    .acct-card-rich:hover {
        box-shadow: var(--shadow-2);
        border-color: var(--tint);
    }
    .acct-card-rich__head {
        display: flex;
        align-items: flex-start;
        gap: 12px;
        margin-bottom: 6px;
    }
    .acct-card-rich__avatar {
        width: 38px;
        height: 38px;
        min-width: 38px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #FFFFFF;
        font-weight: 700;
        font-size: 0.84rem;
        box-shadow: 0 2px 6px rgba(0,0,0,0.12);
        flex-shrink: 0;
    }
    .acct-card-rich__name {
        font-weight: 700;
        font-size: 0.90rem;
        color: var(--label);
        line-height: 1.25;
        display: flex;
        align-items: center;
        gap: 4px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .acct-card-rich__handle {
        font-size: 0.74rem;
        color: var(--label-2);
        margin-top: 2px;
    }
    .acct-card-rich__badges {
        display: flex;
        gap: 6px;
        flex-wrap: wrap;
        margin: 6px 0 8px 0;
    }
    .acct-badge-cat {
        font-size: 0.67rem;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: var(--r-pill);
        background: rgba(0, 113, 227, 0.08);
        color: var(--tint);
    }
    .acct-badge-subcat {
        font-size: 0.65rem;
        font-weight: 500;
        padding: 2px 7px;
        border-radius: var(--r-pill);
        background: var(--surface-muted);
        color: var(--label-2);
    }
    .acct-card-rich__role {
        font-size: 0.78rem;
        font-weight: 600;
        color: var(--label);
        line-height: 1.35;
        margin-bottom: 4px;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    .acct-card-rich__relevance {
        font-size: 0.72rem;
        color: var(--label-2);
        line-height: 1.4;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
        margin-bottom: 10px;
    }
    .acct-card-rich__footer {
        border-top: 1px solid var(--separator);
        padding-top: 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 0.72rem;
    }
    .acct-card-rich__links {
        display: flex;
        gap: 10px;
    }
    .acct-card-rich__links a {
        color: var(--link);
        text-decoration: none;
        font-weight: 600;
    }
    .acct-status-pill {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 2px 7px;
        border-radius: var(--r-pill);
        font-size: 0.67rem;
        font-weight: 600;
    }
    .acct-status-pill--active {
        background: var(--green-soft);
        color: var(--green);
    }
    .acct-status-pill--paused {
        background: var(--amber-soft);
        color: var(--amber);
    }
    .acct-status-pill--pending {
        background: rgba(142, 78, 198, 0.12);
        color: #8E4EC6;
    }

    /* Health card */
    .health-card { position: relative; padding: 14px 18px 14px 20px; margin-bottom: 10px; overflow: hidden; }
    .health-card::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; background: var(--accent, var(--green)); }
    .health-card--ok { --accent: var(--green); }
    .health-card--warn { --accent: #F5A623; }
    .health-card--fail { --accent: var(--red); }
    .health-card__head { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; }
    .health-card__title { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
    .health-card__name { font-size: 1rem; font-weight: 700; color: var(--label); }
    .health-card__meta { font-size: 0.78rem; color: var(--label-2); }
    .health-card__stats { display: flex; gap: 16px; flex-wrap: wrap; font-size: 0.82rem; color: var(--label-2); margin: 6px 0; }
    .health-card__stats b { color: var(--label); }
    .health-card__latest { background: var(--surface-muted); border-radius: var(--r-sm); padding: 8px 12px; margin-top: 6px; font-size: 0.82rem; }
    .health-card__eyebrow { color: var(--label-3); font-size: 0.68rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; margin-bottom: 2px; }
    .health-card__latest a { color: var(--label); font-weight: 600; text-decoration: none; }

    /* Empty state */
    .empty-state { text-align: center; padding: 48px 24px; background: var(--surface); border: 1px dashed var(--separator-strong); border-radius: var(--r-lg); margin: 8px 0 16px 0; }
    .empty-state__icon { font-size: 2rem; margin-bottom: 8px; }
    .empty-state__title { font-size: 1rem; font-weight: 650; color: var(--label); margin: 0 0 4px 0; }
    .empty-state__body { font-size: 0.86rem; color: var(--label-2); margin: 0; }

    /* Apple HIG KPI Card */
    .apple-kpi-card {
        background: var(--surface);
        border: 1px solid var(--separator);
        border-radius: var(--r-md);
        padding: 12px 14px;
        box-shadow: var(--shadow-1);
        display: flex;
        flex-direction: column;
        gap: 3px;
        margin-bottom: 8px;
    }
    .apple-kpi-card__label {
        font-size: 0.72rem;
        font-weight: 600;
        color: var(--label-2);
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .apple-kpi-card__value {
        font-size: 1.55rem;
        font-weight: 700;
        letter-spacing: -0.028em;
        color: var(--label);
        line-height: 1.15;
    }
    .apple-kpi-card__subtitle {
        font-size: 0.70rem;
        color: var(--label-3);
    }

    .counter-badge { display: inline-block; background: var(--surface); border: 1px solid var(--separator); border-radius: var(--r-sm); padding: 6px 12px; font-size: 0.78rem; color: var(--label-2); }
    .counter-badge b { color: var(--label); }

    /* ==========================================================
       7. NATIVE STREAMLIT WIDGETS (global)
       ========================================================== */
    div[data-testid="stMetric"] {
        background: var(--surface) !important; border: 1px solid var(--separator) !important;
        border-radius: var(--r-md) !important; padding: 14px 18px !important; box-shadow: var(--shadow-1) !important;
    }
    div[data-testid="stMetricLabel"], div[data-testid="stMetricLabel"] * {
        font-size: 0.72rem !important; font-weight: 600 !important; color: var(--label-3) !important;
        letter-spacing: 0.04em !important; text-transform: uppercase !important; white-space: normal !important;
    }
    div[data-testid="stMetricValue"], div[data-testid="stMetricValue"] * {
        font-size: 1.4rem !important; font-weight: 700 !important; letter-spacing: -0.02em !important; color: var(--label) !important;
    }

    div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
        border-radius: 10px !important; border-color: var(--separator-strong) !important; background-color: var(--surface) !important;
        transition: border-color 0.18s var(--ease), box-shadow 0.18s var(--ease) !important;
    }
    div[data-baseweb="input"] > div:focus-within, div[data-baseweb="select"] > div:focus-within {
        border-color: var(--tint) !important; box-shadow: 0 0 0 3px var(--tint-soft) !important;
    }

    .stButton > button, div[data-testid="stDownloadButton"] > button, div[data-testid="stLinkButton"] > a {
        border-radius: 10px !important; font-weight: 600 !important; font-size: 0.84rem !important;
        border: 1px solid var(--separator-strong) !important; background: var(--surface) !important; color: var(--label) !important;
        box-shadow: var(--shadow-1) !important; transition: background-color 0.18s var(--ease), border-color 0.18s var(--ease) !important;
    }
    .stButton > button:hover, div[data-testid="stDownloadButton"] > button:hover, div[data-testid="stLinkButton"] > a:hover {
        background: var(--surface-muted) !important; border-color: var(--separator-strong) !important; color: var(--label) !important;
    }
    .stButton > button[kind="primary"], div[data-testid="stDownloadButton"] > button[kind="primary"],
    button[data-testid="stBaseButton-primary"], button[data-testid="stBaseButton-primaryFormSubmit"] {
        background: var(--tint) !important; color: #FFFFFF !important; border: none !important;
    }
    .stButton > button[kind="primary"] *, div[data-testid="stDownloadButton"] > button[kind="primary"] *,
    button[data-testid="stBaseButton-primary"] *, button[data-testid="stBaseButton-primaryFormSubmit"] * { color: #FFFFFF !important; }
    .stButton > button[kind="primary"]:hover, div[data-testid="stDownloadButton"] > button[kind="primary"]:hover,
    button[data-testid="stBaseButton-primary"]:hover, button[data-testid="stBaseButton-primaryFormSubmit"]:hover {
        background: var(--tint-hover) !important;
    }

    /* ==========================================================
       7. SEGMENTED CONTROLS (macOS / Apple HIG)
       ========================================================== */
    /* Main Content Area Segmented Controls */
    [data-testid="stAppViewContainer"] .main div[data-testid="stButtonGroup"],
    .main div[data-testid="stButtonGroup"] {
        width: 100% !important;
        display: flex !important;
        justify-content: flex-start !important;
        align-items: center !important;
        margin: 4px 0 16px 0 !important;
    }
    [data-testid="stAppViewContainer"] .main div[data-testid="stButtonGroup"] > div,
    .main div[data-testid="stButtonGroup"] > div {
        display: inline-flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        width: auto !important;
        max-width: 100% !important;
        overflow-x: auto !important;
        scrollbar-width: none !important;
        -webkit-overflow-scrolling: touch !important;
        background: rgba(118, 118, 128, 0.12) !important;
        padding: 3px !important;
        border-radius: 10px !important;
        border: none !important;
        gap: 3px !important;
        box-sizing: border-box !important;
    }
    [data-testid="stAppViewContainer"] .main div[data-testid="stButtonGroup"] > div::-webkit-scrollbar,
    .main div[data-testid="stButtonGroup"] > div::-webkit-scrollbar {
        display: none !important;
    }
    [data-testid="stAppViewContainer"] .main div[data-testid="stButtonGroup"] button,
    .main div[data-testid="stButtonGroup"] button {
        flex: 0 0 auto !important;
        width: auto !important;
        min-width: max-content !important;
        height: 34px !important;
        min-height: 34px !important;
        padding: 0 18px !important;
        border-radius: 8px !important;
        border: none !important;
        background: transparent !important;
        color: var(--label-2) !important;
        box-shadow: none !important;
        font-size: 0.82rem !important;
        font-weight: 500 !important;
        letter-spacing: -0.01em !important;
        text-align: center !important;
        justify-content: center !important;
        align-items: center !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        cursor: pointer !important;
        transition: background-color 0.2s var(--ease), box-shadow 0.2s var(--ease), color 0.2s var(--ease) !important;
    }
    [data-testid="stAppViewContainer"] .main div[data-testid="stButtonGroup"] button *,
    [data-testid="stAppViewContainer"] .main div[data-testid="stButtonGroup"] button p,
    [data-testid="stAppViewContainer"] .main div[data-testid="stButtonGroup"] button div,
    [data-testid="stAppViewContainer"] .main div[data-testid="stButtonGroup"] button span,
    .main div[data-testid="stButtonGroup"] button *,
    .main div[data-testid="stButtonGroup"] button p,
    .main div[data-testid="stButtonGroup"] button div,
    .main div[data-testid="stButtonGroup"] button span {
        font-size: 0.82rem !important;
        font-weight: inherit !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        margin: 0 !important;
        padding: 0 !important;
        line-height: 34px !important;
        text-align: center !important;
    }
    [data-testid="stAppViewContainer"] .main div[data-testid="stButtonGroup"] button:hover:not([aria-checked="true"]),
    .main div[data-testid="stButtonGroup"] button:hover:not([aria-checked="true"]) {
        background: rgba(255, 255, 255, 0.45) !important;
        color: var(--label) !important;
    }
    [data-testid="stAppViewContainer"] .main div[data-testid="stButtonGroup"] button[data-selected],
    [data-testid="stAppViewContainer"] .main div[data-testid="stButtonGroup"] button[aria-checked="true"],
    .main div[data-testid="stButtonGroup"] button[data-selected],
    .main div[data-testid="stButtonGroup"] button[aria-checked="true"] {
        background: var(--surface) !important;
        font-weight: 600 !important;
        color: var(--label) !important;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.10), 0 1px 2px rgba(0, 0, 0, 0.05) !important;
    }

    /* Sidebar Segmented Controls (compact 1-row layout for timeframe presets) */
    section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] {
        width: 100% !important;
        display: flex !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] > div {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        width: 100% !important;
        background: rgba(118, 118, 128, 0.12) !important;
        padding: 2px !important;
        border-radius: 9px !important;
        border: none !important;
        gap: 0 !important;
        box-sizing: border-box !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button,
    section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button[data-variant="segmented_control"] {
        flex: 1 1 0 !important;
        width: 100% !important;
        min-width: 0 !important;
        height: 28px !important;
        min-height: 28px !important;
        padding: 0 4px !important;
        border-radius: 7px !important;
        border: none !important;
        background: transparent !important;
        color: var(--label-2) !important;
        box-shadow: none !important;
        font-size: 0.72rem !important;
        font-weight: 500 !important;
        letter-spacing: -0.01em !important;
        text-align: center !important;
        justify-content: center !important;
        align-items: center !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        transition: background-color 0.2s var(--ease), box-shadow 0.2s var(--ease) !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button *,
    section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button p,
    section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button div,
    section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button span {
        font-size: 0.72rem !important;
        font-weight: inherit !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        margin: 0 !important;
        padding: 0 !important;
        line-height: 1 !important;
        text-align: center !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button[data-selected],
    section[data-testid="stSidebar"] div[data-testid="stButtonGroup"] button[aria-checked="true"] {
        background: var(--surface) !important;
        font-weight: 600 !important;
        color: var(--label) !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12), 0 1px 1px rgba(0, 0, 0, 0.04) !important;
    }

    /* Toggle */
    label[data-baseweb="checkbox"] > div:first-child { background-color: rgba(120, 120, 128, 0.24) !important; }
    label[data-baseweb="checkbox"]:has(input:checked) > div:first-child { background-color: var(--tint) !important; }

    /* Tables */
    div[data-testid="stDataEditor"], div[data-testid="stDataFrame"] {
        border-radius: var(--r-md) !important; border: 1px solid var(--separator) !important;
        overflow: hidden !important; background: var(--surface) !important; box-shadow: var(--shadow-1) !important;
    }

    /* Expanders */
    div[data-testid="stExpander"] details {
        background: var(--surface) !important; border: 1px solid var(--separator) !important; border-radius: var(--r-md) !important;
    }
    div[data-testid="stExpander"] summary p { font-weight: 600 !important; font-size: 0.86rem !important; }

    /* ==========================================================
       8. SIDEBAR (macOS inset grouped style)
       ========================================================== */
    section[data-testid="stSidebar"] {
        background: #F2F2F7 !important; border-right: 1px solid var(--separator) !important;
        min-width: 330px !important; max-width: 375px !important;
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarContent"] { padding: 1rem 1rem 1.5rem 1rem !important; }
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 0.5rem !important; }
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] { margin-bottom: 0 !important; }
    section[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] > div,
    section[data-testid="stSidebar"] div[data-testid="stLayoutWrapper"] > div[data-testid="stVerticalBlock"] {
        background: var(--surface) !important;
        border: 1px solid var(--separator) !important;
        border-radius: var(--r-md) !important;
        padding: 13px 14px 15px 14px !important;
        box-shadow: var(--shadow-1) !important;
    }
    section[data-testid="stSidebar"] label[data-testid="stWidgetLabel"] [data-testid="stTooltipIcon"] { display: none !important; }
    section[data-testid="stSidebar"] [data-testid="stTooltipIcon"]:not(label *) {
        display: inline-flex !important;
        width: 100% !important;
    }
    section[data-testid="stSidebar"] [data-testid="stTooltipHoverTarget"] {
        width: 100% !important;
        display: flex !important;
    }
    section[data-testid="stSidebar"] .stButton {
        width: 100% !important;
    }
    section[data-testid="stSidebar"] label[data-testid="stWidgetLabel"] { min-height: 16px !important; margin-bottom: 2px !important; }
    section[data-testid="stSidebar"] label[data-testid="stWidgetLabel"] p { font-size: 0.74rem !important; font-weight: 500 !important; color: var(--label-2) !important; }
    section[data-testid="stSidebar"] div[data-baseweb="input"] > div,
    section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
        min-height: 34px !important; height: 34px !important; border-radius: var(--r-sm) !important;
        background: var(--surface-muted) !important; border: 1px solid transparent !important; font-size: 0.82rem !important;
    }
    section[data-testid="stSidebar"] div[data-baseweb="input"] > div:focus-within,
    section[data-testid="stSidebar"] div[data-baseweb="select"] > div:focus-within {
        background: var(--surface) !important; border-color: var(--tint) !important;
    }
    section[data-testid="stSidebar"] div[data-baseweb="base-input"], section[data-testid="stSidebar"] input { background: transparent !important; }
    section[data-testid="stSidebar"] div[data-baseweb="select"] span,
    section[data-testid="stSidebar"] div[data-baseweb="select"] div,
    section[data-testid="stSidebar"] input { font-size: 0.82rem !important; color: var(--label) !important; }
    section[data-testid="stSidebar"] .stButton > button { min-height: 32px !important; height: 32px !important; padding: 0 10px !important; font-size: 0.8rem !important; border-radius: var(--r-sm) !important; box-shadow: none !important; }

    .sb-section { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
    .sb-section__title { font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; color: var(--label-3); }
    .sb-section__badge { font-size: 0.68rem; font-weight: 600; color: var(--label-2); background: var(--surface-muted); padding: 2px 8px; border-radius: var(--r-pill); }
    .sb-footer { margin-top: 16px; text-align: center; font-size: 0.7rem; line-height: 1.5; color: var(--label-3); }

    /* ==========================================================
       9. RESPONSIVE + ACCESSIBILITY
       ========================================================== */
    @media (max-width: 900px) {
        .block-container { padding: 1.2rem 0.8rem 2rem 0.8rem !important; }
        .app-header { padding: 10px 14px; flex-direction: column; align-items: flex-start; }
        .page-header__title { font-size: 1.35rem !important; }
    }
    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after { animation: none !important; transition: none !important; }
    }
</style>
"""

AUTH_CSS = """
<style>
    [data-testid="stSidebar"], [data-testid="collapsedControl"], header[data-testid="stHeader"] { display: none !important; }
    .block-container { padding-top: 14vh !important; max-width: 420px !important; margin: 0 auto !important; }
    div[data-testid="stForm"] {
        background: var(--surface) !important; border: 1px solid var(--separator) !important;
        border-radius: 20px !important; padding: 36px 32px 28px 32px !important; box-shadow: var(--shadow-2) !important;
    }
    .auth-header { text-align: center; margin-bottom: 22px; }
    .auth-header__flag { font-size: 2rem; line-height: 1; margin-bottom: 12px; }
    .auth-header__title { font-size: 1.85rem !important; font-weight: 700 !important; color: var(--label) !important; letter-spacing: -0.028em !important; margin: 0 0 4px 0 !important; padding: 0 !important; }
    .auth-header__subtitle { font-size: 0.92rem; color: var(--label-2); margin: 0; }
    div[data-testid="stForm"] div[data-baseweb="input"] > div { min-height: 48px !important; border-radius: 12px !important; }
    div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button { min-height: 48px !important; width: 100% !important; border-radius: 12px !important; font-size: 0.95rem !important; }
    div[data-testid="InputInstructions"] { display: none !important; }
    .auth-footer { text-align: center; font-size: 0.76rem; color: var(--label-3); margin-top: 14px; }
</style>
"""

__all__ = ["APPLE_DESIGN_SYSTEM_CSS", "AUTH_CSS"]

