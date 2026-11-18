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
       3. SIDEBAR BRAND CARD (Apple HIG)
       ========================================================== */
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
    .live-status-inline {
        display: inline-flex; align-items: center; gap: 6px;
        font-size: 0.7rem; font-weight: 700; letter-spacing: 0.08em;
        color: var(--green); text-transform: uppercase;
    }
    .live-pill__dot { display: inline-block; flex-shrink: 0; width: 7px; height: 7px; border-radius: 50%; background: var(--green); animation: livePulse 2s infinite; }
    @keyframes livePulse {
        0% { box-shadow: 0 0 0 0 rgba(30, 142, 62, 0.45); }
        70% { box-shadow: 0 0 0 6px rgba(30, 142, 62, 0); }
        100% { box-shadow: 0 0 0 0 rgba(30, 142, 62, 0); }
    }

    /* ==========================================================
       4. PAGE HEADER (large title per workspace)
       ========================================================== */
    .page-header { display: flex; align-items: flex-end; justify-content: space-between; flex-wrap: wrap; gap: 10px; margin: 2px 0 10px 0; }
    .page-header__title { font-size: 1.9rem !important; font-weight: 700 !important; letter-spacing: -0.03em !important; margin: 0 !important; padding: 0 !important; color: var(--label) !important; line-height: 1.12 !important; }
    .page-header [data-testid="stHeaderActionElements"], .page-header__title a { display: none !important; }
    .page-header__subtitle { font-size: 0.88rem; color: var(--label-2); margin: 4px 0 0 0; }
    .page-header__meta { display: inline-flex; align-items: center; gap: 6px; flex-wrap: wrap; }
    .newsroom-stat-line {
        display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap;
        margin: 2px 0 10px 0;
    }
    .newsroom-stat-total {
        font-size: 1.35rem; font-weight: 700; letter-spacing: -0.02em; color: var(--label);
    }
    .newsroom-stat-label {
        font-size: 0.9rem; font-weight: 500; color: var(--label-2);
    }
    .news-stream-bar {
        display: flex; align-items: center; justify-content: space-between;
        padding: 8px 2px 6px 2px; margin-top: 4px;
        border-bottom: 1px solid rgba(0, 0, 0, 0.06);
        font-size: 0.72rem; font-weight: 700; letter-spacing: 0.08em;
        color: var(--label-3); text-transform: uppercase;
    }
    .news-stream-bar__right {
        font-weight: 500; letter-spacing: 0.01em; text-transform: none; font-size: 0.78rem;
    }

    /* ==========================================================
       5. PILLS / CHIPS / BADGES (shared base + colour variants)
       ========================================================== */
    .pill, .portal-tag, .indian-portal-tag, .cat-badge, .conf-review-badge,
    .x-sentiment-badge, .x-metric-item, .status-pill {
        display: inline-flex; align-items: center; gap: 4px;
        padding: 3px 9px; border-radius: 7px;
        font-size: 0.73rem; font-weight: 600; line-height: 1.35; white-space: nowrap;
        background: var(--surface-muted); color: var(--label-2);
        border: 1px solid rgba(0, 0, 0, 0.06);
    }
    .portal-tag { background: #F2F4F7; color: var(--label); border-color: rgba(0, 0, 0, 0.09); font-weight: 650; }
    .indian-portal-tag { background: #FFF4EA; color: #B4530D; border-color: rgba(180, 83, 13, 0.15); }
    .lang-label {
        font-size: 0.73rem;
        font-weight: 500;
        color: var(--label-2);
        white-space: nowrap;
        padding: 0 2px;
    }
    .time-badge {
        margin-left: auto;
        font-size: 0.75rem;
        font-weight: 500;
        color: var(--label-3);
        white-space: nowrap;
        line-height: 1.35;
    }
    .pill--success { background: var(--green-soft); color: var(--green); }
    .pill--warn, .conf-review-badge { background: var(--amber-soft); color: var(--amber); }
    .pill--tint { background: var(--tint-soft); color: var(--tint); }
    .sec-tag-chip {
        display: inline-flex;
        align-items: center;
        padding: 2px 8px;
        border-radius: 6px;
        background: #F5F6F8;
        border: 1px solid rgba(0, 0, 0, 0.06);
        font-size: 0.72rem;
        font-weight: 500;
        color: var(--label-2);
        line-height: 1.35;
    }
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
    .apple-news-card, .x-post-card, .health-card {
        background: var(--surface);
        border: 1px solid var(--separator);
        border-radius: var(--r-md);
        box-shadow: var(--shadow-1);
        transition: box-shadow 0.25s var(--ease), border-color 0.25s var(--ease);
    }
    .apple-news-card:hover, .x-post-card:hover, .health-card:hover {
        box-shadow: var(--shadow-2);
        border-color: var(--separator-strong);
    }

    /* Article card (lives inside consolidated st.container(border=True) card) */
    .apple-news-card { position: relative; padding: 0 0 4px 0; margin: 0; background: transparent; border: none; box-shadow: none; overflow: hidden; }
    .apple-news-card:hover { box-shadow: none; border: none; }
    .apple-news-card::before { display: none; }
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

    .apple-card-meta { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; width: 100%; }
    .apple-card-title { margin: 0 0 6px 0 !important; padding: 0 !important; font-size: 1.06rem !important; font-weight: 700 !important; line-height: 1.38 !important; letter-spacing: -0.015em !important; }
    .apple-card-title a { color: var(--label) !important; text-decoration: none !important; }
    .apple-card-title a:hover { color: var(--link) !important; }
    .apple-card-native-title { font-size: 0.78rem; color: var(--label-3); margin: -2px 0 6px 0; line-height: 1.35; }
    .apple-card-summary {
        color: #48484A;
        font-size: 0.885rem;
        line-height: 1.54;
        margin: 0 0 2px 0;
        display: -webkit-box;
        -webkit-line-clamp: 3;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    .apple-summary-badge {
        display: inline-block; padding: 1px 6px; margin-right: 6px; border-radius: 5px;
        background: var(--tint-soft); color: var(--tint); font-size: 0.65rem; font-weight: 700;
        letter-spacing: 0.04em; vertical-align: 1px;
    }

    /* X post card (lives inside consolidated st.container(border=True) card) */
    .x-post-card { padding: 2px 2px 8px 2px; margin: 0; background: transparent; border: none; box-shadow: none; }
    .x-post-card:hover { box-shadow: none; border: none; }
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

    /* Consolidated Feed Card Container */
    .feed-card-anchor { display: none; }
    :is(.main, [data-testid="stMain"]) div[data-testid="stVerticalBlockBorderWrapper"]:has(.feed-card-anchor),
    :is(.main, [data-testid="stMain"]) div[data-testid="stLayoutWrapper"]:has(.feed-card-anchor) > div[data-testid="stVerticalBlock"] {
        background: var(--surface) !important;
        border: 1px solid rgba(0, 0, 0, 0.08) !important;
        border-radius: 14px !important;
        padding: 16px 18px 14px 18px !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04) !important;
        margin-bottom: 12px !important;
        transition: box-shadow 0.22s var(--ease), border-color 0.22s var(--ease) !important;
    }
    :is(.main, [data-testid="stMain"]) div[data-testid="stVerticalBlockBorderWrapper"]:has(.feed-card-anchor):hover,
    :is(.main, [data-testid="stMain"]) div[data-testid="stLayoutWrapper"]:has(.feed-card-anchor) > div[data-testid="stVerticalBlock"]:hover {
        box-shadow: var(--shadow-2) !important;
        border-color: var(--separator-strong) !important;
    }

    /* Unified Copyable Brief / Translation Inset Panel */
    .unified-brief-box {
        background: #F4F6F9;
        border: 1px solid rgba(82, 106, 133, 0.16);
        border-left: 3px solid var(--tint);
        border-radius: 10px;
        padding: 12px 15px;
        margin: 6px 0 8px 0;
    }
    .unified-brief-box__eyebrow {
        font-size: 0.67rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--tint);
        margin-bottom: 6px;
    }
    .unified-brief-box__body {
        font-size: 0.89rem;
        line-height: 1.56;
        color: var(--label);
        white-space: pre-wrap;
        word-break: break-word;
        margin-bottom: 8px;
        user-select: all;
    }
    .unified-brief-box__profile {
        font-size: 0.8rem;
        font-style: italic;
        line-height: 1.45;
        color: #526A85;
        padding-top: 8px;
        margin-bottom: 8px;
        border-top: 1px solid rgba(0, 0, 0, 0.07);
    }
    .unified-brief-box__source {
        font-size: 0.77rem;
        line-height: 1.4;
        color: var(--label-2);
        padding-top: 7px;
        border-top: 1px solid rgba(0, 0, 0, 0.07);
        word-break: break-all;
    }
    .unified-brief-box__source a {
        color: var(--link) !important;
        text-decoration: none !important;
        font-weight: 500;
    }
    .unified-brief-box__source a:hover {
        text-decoration: underline !important;
    }
    .feed-action-divider {
        height: 1px;
        background: var(--separator);
        margin: 2px 0 8px 0;
    }
    .wa-already-sent-notice {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 7px 12px;
        margin: 6px 0 6px 0;
        border-radius: var(--r-md, 10px);
        background: rgba(30, 142, 62, 0.08);
        color: #136b2c;
        font-size: 0.8rem;
        font-weight: 600;
        border: 1px solid rgba(30, 142, 62, 0.25);
    }
    :is(.main, [data-testid="stMain"]) div[data-testid="stVerticalBlock"]:has(.feed-card-anchor) div[data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-wrap: wrap !important;
        gap: 10px !important;
        align-items: center !important;
        justify-content: flex-start !important;
    }
    :is(.main, [data-testid="stMain"]) div[data-testid="stVerticalBlock"]:has(.feed-card-anchor) div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
        flex: 0 0 auto !important;
        width: auto !important;
        min-width: max-content !important;
        max-width: none !important;
    }
    :is(.main, [data-testid="stMain"]) div[data-testid="stVerticalBlock"]:has(.feed-card-anchor) .stButton,
    :is(.main, [data-testid="stMain"]) div[data-testid="stVerticalBlock"]:has(.feed-card-anchor) .stButton > button,
    :is(.main, [data-testid="stMain"]) div[data-testid="stVerticalBlock"]:has(.feed-card-anchor) .stButton > button *,
    :is(.main, [data-testid="stMain"]) div[data-testid="stVerticalBlock"]:has(.feed-card-anchor) div[data-testid="stLinkButton"],
    :is(.main, [data-testid="stMain"]) div[data-testid="stVerticalBlock"]:has(.feed-card-anchor) div[data-testid="stLinkButton"] > a,
    :is(.main, [data-testid="stMain"]) div[data-testid="stVerticalBlock"]:has(.feed-card-anchor) div[data-testid="stLinkButton"] > a * {
        white-space: nowrap !important;
        overflow: visible !important;
        text-overflow: unset !important;
        width: auto !important;
        max-width: none !important;
    }
    :is(.main, [data-testid="stMain"]) div[data-testid="stVerticalBlock"]:has(.feed-card-anchor) .stButton > button,
    :is(.main, [data-testid="stMain"]) div[data-testid="stVerticalBlock"]:has(.feed-card-anchor) div[data-testid="stLinkButton"] > a {
        padding: 0 16px !important;
        height: 36px !important;
        min-height: 36px !important;
        border-radius: 10px !important;
        font-size: 0.84rem !important;
        font-weight: 600 !important;
        display: inline-flex !important;
        align-items: center !important;
        gap: 6px !important;
    }
    :is(.main, [data-testid="stMain"]) div[data-testid="stVerticalBlock"]:has(.feed-card-anchor) .stButton > button[kind="secondary"],
    :is(.main, [data-testid="stMain"]) div[data-testid="stVerticalBlock"]:has(.feed-card-anchor) div[data-testid="stLinkButton"] > a {
        background: var(--surface) !important;
        color: var(--label) !important;
        border: 1px solid rgba(0, 0, 0, 0.12) !important;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03) !important;
        text-decoration: none !important;
    }
    :is(.main, [data-testid="stMain"]) div[data-testid="stVerticalBlock"]:has(.feed-card-anchor) .stButton > button[kind="secondary"]:hover,
    :is(.main, [data-testid="stMain"]) div[data-testid="stVerticalBlock"]:has(.feed-card-anchor) div[data-testid="stLinkButton"] > a:hover {
        background: var(--surface-muted) !important;
        border-color: rgba(0, 0, 0, 0.2) !important;
    }
    :is(.main, [data-testid="stMain"]) div[data-testid="stVerticalBlock"]:has(.feed-card-anchor) .stButton > button[kind="primary"] {
        background: #0066CC !important;
        color: #FFFFFF !important;
        border: 1px solid #0066CC !important;
        box-shadow: 0 1px 2px rgba(0, 102, 204, 0.18) !important;
    }
    :is(.main, [data-testid="stMain"]) div[data-testid="stVerticalBlock"]:has(.feed-card-anchor) .stButton > button[kind="primary"]:hover {
        background: #0052A3 !important;
        border-color: #0052A3 !important;
    }
    @media (max-width: 640px) {
        .apple-card-meta .time-badge { margin-left: 0; }
        :is(.main, [data-testid="stMain"]) div[data-testid="stVerticalBlock"]:has(.feed-card-anchor) div[data-testid="stHorizontalBlock"] {
            gap: 8px !important;
        }
    }
    .fulltext-reader-box {
        background: #FAFAFC;
        border: 1px solid var(--separator-strong);
        border-radius: 10px;
        padding: 14px 16px;
        margin: 6px 0 8px 0;
    }
    .fulltext-reader-box__header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 6px;
    }
    .fulltext-reader-box__title {
        font-size: 1rem;
        font-weight: 700;
        color: var(--label);
        line-height: 1.38;
        margin: 0 0 4px 0;
    }
    .fulltext-reader-box__meta {
        font-size: 0.74rem;
        color: var(--label-2);
        margin-bottom: 10px;
        padding-bottom: 8px;
        border-bottom: 1px solid var(--separator);
    }
    .extraction-badge {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 2px 8px;
        border-radius: var(--r-pill);
        font-size: 0.68rem;
        font-weight: 600;
    }
    .extraction-badge--full { background: var(--green-soft); color: var(--green); }
    .extraction-badge--partial { background: var(--amber-soft); color: var(--amber); }

    /* Minimalist Share Modal */
    .share-modal-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 6px;
    }
    .share-modal-type {
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--label-2);
    }
    .share-modal-pills {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        flex-wrap: wrap;
    }
    .share-draft-pill {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 2px 9px;
        border-radius: var(--r-pill);
        font-size: 0.7rem;
        font-weight: 600;
    }
    .share-draft-pill--saved { background: var(--surface-muted); color: var(--label-2); }
    .share-draft-pill--unsaved { background: var(--amber-soft); color: var(--amber); }
    .share-draft-pill--sent { background: var(--green-soft); color: var(--green); }
    div[data-testid="stDialog"] div[data-testid="stVerticalBlock"]:has(.share-modal-anchor, .read-modal-anchor) div[data-testid="stHorizontalBlock"] {
        display: flex !important;
        flex-wrap: wrap !important;
        gap: 10px !important;
        align-items: center !important;
        justify-content: flex-start !important;
    }
    div[data-testid="stDialog"] div[data-testid="stVerticalBlock"]:has(.share-modal-anchor, .read-modal-anchor) div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
        flex: 0 0 auto !important;
        width: auto !important;
        min-width: max-content !important;
    }
    div[data-testid="stDialog"] div[data-testid="stVerticalBlock"]:has(.share-modal-anchor, .read-modal-anchor) div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:last-child {
        margin-left: auto !important;
    }
    div[data-testid="stDialog"] div[data-testid="stVerticalBlock"]:has(.share-modal-anchor, .read-modal-anchor) .stButton > button {
        height: 36px !important;
        min-height: 36px !important;
        border-radius: 10px !important;
        padding: 0 14px !important;
        font-size: 0.83rem !important;
        font-weight: 600 !important;
    }
    div[data-testid="stDialog"] div[data-testid="stVerticalBlock"]:has(.share-modal-anchor, .read-modal-anchor) .stButton > button[kind="primary"] {
        background: #0066CC !important;
        color: #FFFFFF !important;
        border-color: #0066CC !important;
        padding: 0 16px !important;
    }
    div[data-testid="stDialog"] div[data-testid="stVerticalBlock"]:has(.share-modal-anchor, .read-modal-anchor) .stButton > button[kind="primary"]:hover {
        background: #0052A3 !important;
        border-color: #0052A3 !important;
    }
    .fulltext-reader-box__body {
        font-size: 0.95rem;
        line-height: 1.72;
        color: var(--label);
        word-break: break-word;
        max-height: 54vh;
        overflow-y: auto;
        padding-right: 6px;
        margin-bottom: 10px;
    }
    .reader-para {
        margin: 0 0 12px 0;
        max-width: 68ch;
    }
    .reader-para:last-child {
        margin-bottom: 0;
    }

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

    [data-testid="stAppDeployButton"], .stAppDeployButton, #MainMenu { display: none !important; }

    /* Streamlit 1.67 React Aria Selectbox & BaseWeb inputs — Unified 34px Pill Chips */
    div[data-testid="stSelectbox"] div:has(> input),
    div[data-baseweb="input"] > div:first-child,
    div[data-baseweb="select"] > div:first-child {
        border-radius: 999px !important;
        border: 1px solid rgba(15, 23, 42, 0.13) !important;
        background-color: #FFFFFF !important;
        min-height: 34px !important;
        height: 34px !important;
        max-height: 34px !important;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03) !important;
        font-size: 0.8rem !important;
        transition: border-color 0.16s var(--ease), box-shadow 0.16s var(--ease), background-color 0.16s var(--ease) !important;
    }
    div[data-testid="stSelectbox"] div:has(> input):hover,
    div[data-baseweb="select"] > div:first-child:hover {
        border-color: rgba(15, 23, 42, 0.24) !important;
        background-color: #FAFBFD !important;
    }
    div[data-testid="stSelectbox"] input {
        padding: 0 2px 0 12px !important;
        font-size: 0.8rem !important;
        font-weight: 550 !important;
        color: var(--label) !important;
        caret-color: transparent !important;
        cursor: pointer !important;
        line-height: 32px !important;
    }
    div[data-testid="stSelectbox"] button[aria-label="Open"] {
        padding-right: 10px !important;
        padding-left: 2px !important;
        color: var(--label-2) !important;
    }
    div[data-baseweb="select"] > div:first-child {
        padding-left: 6px !important;
        cursor: pointer !important;
    }
    div[data-baseweb="select"] > div > div {
        border: none !important;
        box-shadow: none !important;
        background: transparent !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }
    div[data-baseweb="select"] input {
        caret-color: transparent !important;
        cursor: pointer !important;
    }
    div[data-testid="stSelectbox"] div:has(> input)[data-focus-within],
    div[data-testid="stSelectbox"] div:has(> input):focus-within,
    div[data-baseweb="input"] > div:first-child:focus-within,
    div[data-baseweb="select"] > div:first-child:focus-within {
        border-color: #0066CC !important;
        box-shadow: 0 0 0 3px rgba(0, 102, 204, 0.12) !important;
    }

    /* Editorial Top Navbar (Row 1) & Filter Bar (Row 2) */
    div[data-testid="stHorizontalBlock"]:has(.editorial-brand-anchor) {
        align-items: center !important;
        border-bottom: 1px solid rgba(15, 23, 42, 0.09) !important;
        padding: 0 !important;
        margin-bottom: -4px !important;
        min-height: 38px !important;
    }
    div[data-testid="stElementContainer"]:has(.editorial-brand-anchor),
    div[data-testid="stMarkdownContainer"]:has(.editorial-brand-anchor) {
        margin: 0 !important;
        padding: 0 !important;
    }

    /* Unified 34px Pill Buttons & Popovers (matches Selectbox pills) */
    [data-testid="stPopover"] > button,
    [data-testid="stPopover"] > div > button,
    .stButton > button,
    div[data-testid="stDownloadButton"] > button,
    div[data-testid="stLinkButton"] > a {
        min-height: 34px !important;
        height: 34px !important;
        padding: 0 11px !important;
        border-radius: 999px !important;
        font-weight: 600 !important;
        font-size: 0.79rem !important;
        border: 1px solid rgba(15, 23, 42, 0.13) !important;
        background: #FFFFFF !important;
        color: var(--label) !important;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03) !important;
        white-space: nowrap !important;
        transition: background-color 0.16s var(--ease), border-color 0.16s var(--ease), box-shadow 0.16s var(--ease) !important;
    }
    [data-testid="stPopover"] button div,
    [data-testid="stPopover"] button p,
    [data-testid="stPopover"] button span {
        overflow: visible !important;
        text-overflow: clip !important;
        white-space: nowrap !important;
    }
    [data-testid="stPopover"] > button:hover,
    [data-testid="stPopover"] > div > button:hover,
    .stButton > button:hover,
    div[data-testid="stDownloadButton"] > button:hover,
    div[data-testid="stLinkButton"] > a:hover {
        background: #FAFBFD !important;
        border-color: rgba(15, 23, 42, 0.24) !important;
        color: var(--label) !important;
    }
    .stButton > button[kind="primary"], div[data-testid="stDownloadButton"] > button[kind="primary"],
    button[data-testid="stBaseButton-primary"], button[data-testid="stBaseButton-primaryFormSubmit"] {
        background: #0066CC !important; color: #FFFFFF !important; border: none !important;
    }
    .stButton > button[kind="primary"] *, div[data-testid="stDownloadButton"] > button[kind="primary"] *,
    button[data-testid="stBaseButton-primary"] *, button[data-testid="stBaseButton-primaryFormSubmit"] * { color: #FFFFFF !important; }
    .stButton > button[kind="primary"]:hover, div[data-testid="stDownloadButton"] > button[kind="primary"]:hover,
    button[data-testid="stBaseButton-primary"]:hover, button[data-testid="stBaseButton-primaryFormSubmit"]:hover {
        background: #0052A3 !important;
    }

    /* macOS / Linear-style borderless left-aligned popover menu items (must override .stButton) */
    div[data-baseweb="popover"] .stButton > button,
    [data-testid="stPopoverBody"] .stButton > button {
        justify-content: flex-start !important;
        text-align: left !important;
        border: 1px solid transparent !important;
        background: transparent !important;
        box-shadow: none !important;
        font-weight: 500 !important;
        padding: 6px 10px !important;
        min-height: 34px !important;
        border-radius: 8px !important;
        color: var(--label) !important;
    }
    div[data-baseweb="popover"] .stButton > button:hover,
    [data-testid="stPopoverBody"] .stButton > button:hover {
        background: rgba(0, 0, 0, 0.045) !important;
        border-color: transparent !important;
    }
    div[data-baseweb="popover"] .stButton > button[kind="primary"],
    [data-testid="stPopoverBody"] .stButton > button[kind="primary"] {
        background: var(--tint-soft) !important;
        color: #0066CC !important;
        font-weight: 600 !important;
        border-color: transparent !important;
    }
    div[data-baseweb="popover"] .stButton > button[kind="primary"] *,
    [data-testid="stPopoverBody"] .stButton > button[kind="primary"] * {
        color: #0066CC !important;
    }

    /* ==========================================================
       7. EDITORIAL UNDERLINE TABS (Concept C — Feedly / FT style)
       ========================================================== */
    div[data-testid="stButtonGroup"] {
        width: 100% !important;
        display: flex !important;
        justify-content: flex-end !important;
        align-items: center !important;
        margin: 0 !important;
    }
    div[data-testid="stButtonGroup"] > div,
    div[data-baseweb="button-group"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        width: 100% !important;
        max-width: 100% !important;
        justify-content: flex-end !important;
        overflow-x: visible !important;
        mask-image: none !important;
        -webkit-mask-image: none !important;
        background: transparent !important;
        border: none !important;
        border-radius: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
        column-gap: 2px !important;
        box-shadow: none !important;
    }
    div[data-testid="stButtonGroup"] > div::-webkit-scrollbar {
        display: none !important;
    }
    div[data-testid="stButtonGroup"] button,
    div[data-testid="stButtonGroup"] button[data-variant="segmented_control"],
    div[data-baseweb="button-group"] button {
        flex: 0 1 auto !important;
        width: auto !important;
        min-width: max-content !important;
        height: 36px !important;
        min-height: 36px !important;
        margin: 0 !important;
        padding: 0 9px 4px 9px !important;
        border: none !important;
        border-bottom: 2px solid transparent !important;
        border-radius: 0 !important;
        background: transparent !important;
        box-shadow: none !important;
        outline: none !important;
        color: #64748B !important;
        font-size: 0.79rem !important;
        font-weight: 500 !important;
        letter-spacing: -0.01em !important;
        text-align: center !important;
        justify-content: center !important;
        align-items: center !important;
        white-space: nowrap !important;
        cursor: pointer !important;
        transition: color 0.15s var(--ease), border-color 0.15s var(--ease), background-color 0.15s var(--ease) !important;
    }
    div[data-testid="stButtonGroup"] button *,
    div[data-testid="stButtonGroup"] button[data-variant="segmented_control"] * {
        font-size: 0.79rem !important;
        font-weight: inherit !important;
        color: inherit !important;
        white-space: nowrap !important;
        overflow: visible !important;
        text-overflow: clip !important;
        margin: 0 !important;
        padding: 0 !important;
        line-height: 32px !important;
    }
    div[data-testid="stButtonGroup"] button:hover:not([data-selected]),
    div[data-testid="stButtonGroup"] button[data-variant="segmented_control"]:hover:not([data-selected]),
    div[data-baseweb="button-group"] button:hover {
        background: rgba(15, 23, 42, 0.035) !important;
        color: #0F172A !important;
        border: none !important;
        border-bottom: 2px solid rgba(15, 23, 42, 0.2) !important;
        border-top-left-radius: 6px !important;
        border-top-right-radius: 6px !important;
        box-shadow: none !important;
    }
    div[data-testid="stButtonGroup"] button[data-focus-visible],
    div[data-testid="stButtonGroup"] button:focus,
    div[data-testid="stButtonGroup"] button:focus-visible {
        box-shadow: none !important;
        outline: none !important;
    }
    div[data-testid="stButtonGroup"] button[data-selected],
    div[data-testid="stButtonGroup"] button[data-variant="segmented_control"][data-selected],
    div[data-testid="stButtonGroup"] button[aria-checked="true"],
    div[data-testid="stButtonGroup"] button[data-testid*="Active"],
    div[data-testid="stButtonGroup"] button[kind*="Active"],
    div[data-baseweb="button-group"] button[aria-checked="true"],
    div[data-baseweb="button-group"] button[data-testid*="Active"] {
        background: transparent !important;
        font-weight: 650 !important;
        color: #0066CC !important;
        border: none !important;
        border-bottom: 2px solid #0066CC !important;
        border-radius: 0 !important;
        box-shadow: none !important;
        outline: none !important;
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

