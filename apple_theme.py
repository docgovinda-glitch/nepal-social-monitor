"""
apple_theme.py
Single source of truth for the dashboard's visual language.

Design principles (Apple HIG inspired):
  • One tint colour, neutral greys, generous whitespace.
  • One type scale, one radius scale, one shadow scale — all exposed as CSS tokens.
  • Shared "pill" base for every chip/badge so variants only change colour.
  • Accessible by default: visible focus rings and prefers-reduced-motion support.
"""

_DESIGN_TOKENS_CSS = """
    /* ==========================================================
       1. DESIGN TOKENS
       ========================================================== */
    :root {
        --font: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", system-ui, sans-serif;

        /* Neutrals */
        --bg: #F8FAFC;
        --surface: #FFFFFF;
        --surface-muted: #F1F5F9;
        --label: #0F172A;
        --label-2: #334155;
        --label-3: #475569;
        --separator: rgba(15, 23, 42, 0.08);
        --separator-strong: rgba(15, 23, 42, 0.14);

        /* Unified Editorial Cobalt Tint (matches .streamlit/config.toml primaryColor) */
        --tint: #0066CC;
        --tint-hover: #0052A3;
        --tint-soft: rgba(0, 102, 204, 0.09);
        --link: #0066CC;

        /* Harmonized Semantic Palette */
        --green: #15803D;  --green-soft: #DCFCE7;
        --amber: #B45309;  --amber-soft: #FEF3C7;
        --red: #B91C1C;    --red-soft: #FEE2E2;

        /* Scales */
        --r-sm: 8px;  --r-md: 12px;  --r-lg: 16px;  --r-pill: 999px;
        --shadow-1: 0 1px 2px rgba(15, 23, 42, 0.04), 0 1px 1px rgba(15, 23, 42, 0.02);
        --shadow-2: 0 6px 20px rgba(15, 23, 42, 0.06), 0 1px 3px rgba(15, 23, 42, 0.03);
        --ease: cubic-bezier(0.16, 1, 0.3, 1);
    }
"""

_PHASE2_ENHANCEMENTS_CSS = """
    /* ═══════════════════════════════════════════════════════════
       PHASE 2: SEARCH SIDEBAR, DRAWERS, SKELETONS, DARK MODE
       ═══════════════════════════════════════════════════════════ */

    /* 2.1: Persistent Search Sidebar */
    .search-sidebar {
        display: flex; flex-direction: column; gap: 12px;
        padding: 14px; margin-bottom: 16px;
        background: linear-gradient(180deg, #FAFBFD 0%, #F5F7FA 100%);
        border: 1px solid rgba(0, 102, 204, 0.08);
        border-radius: 14px;
        animation: slide-down 0.3s var(--ease) forwards;
    }
    @keyframes slide-down {
        from { opacity: 0; transform: translateY(-8px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .search-sidebar__label {
        font-size: 0.72rem; font-weight: 700;
        text-transform: uppercase; letter-spacing: 0.06em;
        color: var(--label-3); margin-bottom: 4px;
    }
    .search-sidebar__filters {
        display: flex; flex-wrap: wrap; gap: 6px;
    }
    .filter-pill-removable {
        display: inline-flex; align-items: center; gap: 6px;
        padding: 6px 10px; border-radius: 20px;
        background: var(--tint-soft); color: var(--tint);
        font-size: 0.72rem; font-weight: 600;
        border: 1px solid rgba(0, 102, 204, 0.2);
    }
    .filter-pill-removable button {
        background: none; border: none; color: var(--tint);
        cursor: pointer; padding: 0; font-size: 1rem;
        line-height: 1; opacity: 0.7; transition: opacity 0.15s ease;
    }
    .filter-pill-removable button:hover {
        opacity: 1;
    }

    /* 2.2: Right-Side Modal Drawer (> 768px) */
    @media (min-width: 1024px) {
        .modal-drawer {
            position: fixed; right: 0; top: 60px; bottom: 0;
            width: 720px; background: var(--surface);
            border-left: 1px solid var(--separator);
            box-shadow: -4px 0 12px rgba(0, 0, 0, 0.08);
            z-index: 999; overflow-y: auto;
            animation: drawer-enter 0.3s var(--ease) forwards;
        }
        @keyframes drawer-enter {
            from { transform: translateX(100%); }
            to { transform: translateX(0); }
        }
        .modal-drawer__header {
            position: sticky; top: 0; z-index: 10;
            padding: 16px 20px; border-bottom: 1px solid var(--separator);
            background: var(--surface); display: flex;
            align-items: center; justify-content: space-between;
            gap: 10px;
        }
        .modal-drawer__title {
            font-size: 1rem; font-weight: 700; color: var(--label);
        }
        .modal-drawer__close {
            width: 32px; height: 32px; border: none;
            background: var(--surface-muted); border-radius: 8px;
            cursor: pointer; color: var(--label-2);
            font-size: 1.1rem; transition: all 0.15s ease;
        }
        .modal-drawer__close:hover {
            background: var(--tint-soft); color: var(--tint);
        }
        .modal-drawer__content {
            padding: 20px;
        }
    }

    /* 2.3: Loading Skeleton Animation */
    @keyframes shimmer {
        0% { background-position: -1000px 0; }
        100% { background-position: 1000px 0; }
    }
    .skeleton {
        background: linear-gradient(
            90deg,
            var(--surface-muted) 25%,
            #FFFFFF 50%,
            var(--surface-muted) 75%
        );
        background-size: 1000px 100%;
        animation: shimmer 2s infinite;
        border-radius: 8px;
    }
    .skeleton-card {
        background: var(--surface);
        border: 1px solid var(--separator);
        border-radius: 14px;
        padding: 16px; margin-bottom: 12px;
    }
    .skeleton-line {
        height: 12px; border-radius: 6px; margin-bottom: 10px;
        background: linear-gradient(90deg, var(--surface-muted) 25%, #FFFFFF 50%, var(--surface-muted) 75%);
        background-size: 1000px 100%;
        animation: shimmer 2s infinite;
    }
    .skeleton-line:last-child {
        margin-bottom: 0;
    }
    .skeleton-line--title {
        height: 18px; width: 85%;
    }
    .skeleton-line--text {
        height: 12px; width: 100%;
    }
    .skeleton-line--text:last-of-type {
        width: 90%;
    }

    /* 2.4: Dark Mode Support */
    @media (prefers-color-scheme: dark) {
        :root {
            --bg: #0F172A;
            --surface: #1A202C;
            --surface-muted: #2D3748;
            --label: #F7FAFC;
            --label-2: #CBD5E0;
            --label-3: #A0AEC0;
            --separator: rgba(255, 255, 255, 0.08);
            --separator-strong: rgba(255, 255, 255, 0.14);
            --tint-soft: rgba(99, 179, 237, 0.15);
        }
    }
    body[data-theme="dark"] {
        --bg: #0F172A;
        --surface: #1A202C;
        --surface-muted: #2D3748;
        --label: #F7FAFC;
        --label-2: #CBD5E0;
        --label-3: #A0AEC0;
        --separator: rgba(255, 255, 255, 0.08);
        --separator-strong: rgba(255, 255, 255, 0.14);
        --tint-soft: rgba(99, 179, 237, 0.15);
    }
    body[data-theme="light"] {
        --bg: #F8FAFC;
        --surface: #FFFFFF;
        --surface-muted: #F1F5F9;
        --label: #0F172A;
        --label-2: #334155;
        --label-3: #475569;
        --separator: rgba(15, 23, 42, 0.08);
        --separator-strong: rgba(15, 23, 42, 0.14);
    }

    /* 2.5: Export Preview Card */
    .export-preview-card {
        background: var(--surface);
        border: 1px solid var(--separator);
        border-radius: 14px;
        padding: 18px 20px;
        margin: 12px 0;
    }
    .export-preview-row {
        display: flex; justify-content: space-between;
        align-items: center; gap: 12px;
        padding: 10px 0; border-bottom: 1px solid var(--separator);
    }
    .export-preview-row:last-child {
        border-bottom: none;
    }
    .export-preview-label {
        font-size: 0.84rem; font-weight: 500; color: var(--label-2);
    }
    .export-preview-value {
        font-size: 0.95rem; font-weight: 650; color: var(--label);
    }
"""

_PHASE1_ENHANCEMENTS_CSS = """
    /* ═══════════════════════════════════════════════════════════
       PHASE 1: TAB STYLING, SYNC STATUS, CARD STRIPES, MOBILE NAV
       ═══════════════════════════════════════════════════════════ */

    /* 1.1: Enhanced Active Tab State — Segmented Control */
    div[data-testid="stSegmentedControl"] {
        background: transparent !important;
        gap: 6px !important;
    }
    div[data-testid="stSegmentedControl"] > div[role="button"] {
        border-radius: 10px !important;
        padding: 10px 16px !important;
        font-weight: 550 !important;
        border: 1px solid rgba(15, 23, 42, 0.08) !important;
        background: rgba(15, 23, 42, 0.02) !important;
        transition: all 0.2s var(--ease) !important;
    }
    div[data-testid="stSegmentedControl"] > div[role="button"][aria-selected="true"] {
        background: var(--tint-soft) !important;
        border-color: var(--tint) !important;
        border-left: 3px solid var(--tint) !important;
        padding-left: 14px !important;
        color: var(--tint) !important;
        font-weight: 650 !important;
        box-shadow: 0 1px 3px rgba(0, 102, 204, 0.12) !important;
    }
    div[data-testid="stSegmentedControl"] > div[role="button"]:hover {
        background: rgba(15, 23, 42, 0.05) !important;
        border-color: rgba(15, 23, 42, 0.16) !important;
    }

    /* 1.2: Inline Sync Status Bar */
    .sync-status-bar {
        display: flex; align-items: center; justify-content: space-between;
        gap: 12px; flex-wrap: wrap;
        padding: 10px 14px; margin: 8px 0 12px 0;
        background: linear-gradient(90deg, #F0F9FF 0%, #F5F3FF 100%);
        border: 1px solid rgba(0, 102, 204, 0.12);
        border-radius: 12px;
        font-size: 0.75rem; font-weight: 600; color: var(--label-2);
    }
    .sync-status-pill {
        display: inline-flex; align-items: center; gap: 7px; padding: 5px 10px;
        border-radius: 20px; font-size: 0.72rem; font-weight: 600;
        white-space: nowrap;
    }
    .sync-status-pill--idle {
        background: #F1F5F9; color: #64748B;
    }
    .sync-status-pill--running {
        background: #FEF3C7; color: #B45309;
        animation: pulse-bg 1.5s ease-in-out infinite;
    }
    @keyframes pulse-bg {
        0%, 100% { background: #FEF3C7; }
        50% { background: #FCD34D; }
    }
    .sync-status-pill--done {
        background: #DCFCE7; color: #15803D;
    }
    .sync-status-pill--error {
        background: #FEE2E2; color: #B91C1C;
    }
    .sync-spinner {
        display: inline-block; width: 12px; height: 12px;
        border: 2px solid rgba(180, 83, 9, 0.2); border-top: 2px solid #B45309;
        border-radius: 50%; animation: spin 0.8s linear infinite;
    }
    @keyframes spin {
        to { transform: rotate(360deg); }
    }

    /* 1.3: Card Type Color Stripes */
    .feed-card-stripe {
        position: absolute; left: 0; top: 0; bottom: 0;
        width: 4px; border-radius: 14px 0 0 14px;
    }
    .feed-card-stripe--nepal {
        background: linear-gradient(180deg, #15803D 0%, #059669 100%);
    }
    .feed-card-stripe--india {
        background: linear-gradient(180deg, #F76B15 0%, #EA580C 100%);
    }
    .feed-card-stripe--x {
        background: linear-gradient(180deg, #1D9BF0 0%, #1A8CD8 100%);
    }
    :is(.main, [data-testid="stMain"]) div[data-testid="stVerticalBlockBorderWrapper"]:has(.feed-card-anchor) {
        position: relative !important;
    }

    /* 1.4: Mobile Navigation Improvements */
    @media (max-width: 768px) {
        div[data-testid="stSegmentedControl"] > div[role="button"] {
            padding: 8px 12px !important;
            font-size: 0.78rem !important;
        }
        div[data-testid="stSegmentedControl"] > div[role="button"][aria-selected="true"] {
            padding-left: 11px !important;
        }
        .nav-label-text { display: none; }
        .nav-label-icon { font-size: 1.1rem; }
    }

    /* 1.5: Modal Focus Trap & Accessibility */
    div[data-testid="stDialog"] {
        outline: 2px solid var(--tint) !important;
        outline-offset: -1px !important;
    }
    div[data-testid="stDialog"] [role="button"]:last-of-type {
        margin-right: 8px !important;
    }
"""

_PILL_AND_FEED_CARD_CSS = """
    .pill, .portal-tag, .indian-portal-tag, .cat-badge, .conf-review-badge,
    .x-sentiment-badge, .x-metric-item, .status-pill {
        display: inline-flex; align-items: center; gap: 4px;
        padding: 3px 9px; border-radius: 7px;
        font-size: 0.73rem; font-weight: 600; line-height: 1.35; white-space: nowrap;
        background: var(--surface-muted); color: var(--label-2);
        border: 1px solid rgba(0, 0, 0, 0.06);
    }
    .portal-tag { background: #F1F5F9; color: #0F172A; border-color: rgba(15, 23, 42, 0.10); font-weight: 650; }
    .indian-portal-tag { background: #FFF7ED; color: #C2410C; border-color: rgba(194, 65, 12, 0.18); font-weight: 650; }
    .lang-label { font-size: 0.73rem; font-weight: 500; color: var(--label-2); white-space: nowrap; padding: 0 2px; }
    .time-badge { margin-left: auto; font-size: 0.75rem; font-weight: 500; color: var(--label-3); white-space: nowrap; line-height: 1.35; }
    .pill--success { background: var(--green-soft); color: var(--green); }
    .pill--warn, .conf-review-badge { background: var(--amber-soft); color: var(--amber); }
    .pill--tint { background: var(--tint-soft); color: var(--tint); }
    .sec-tag-chip {
        display: inline-flex; align-items: center; padding: 2px 8px; border-radius: 6px;
        background: #F8FAFC; border: 1px solid rgba(15, 23, 42, 0.08);
        font-size: 0.72rem; font-weight: 500; color: var(--label-2); line-height: 1.35;
    }
    .chip-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
    .cat-badge--india { background: #FFFBEB; color: #B45309; border-color: rgba(180, 83, 9, 0.16); }
    .cat-badge--china { background: #FEF2F2; color: #B91C1C; border-color: rgba(185, 28, 28, 0.16); }
    .cat-badge--pakistan { background: #F0FDF4; color: #15803D; border-color: rgba(21, 128, 61, 0.16); }
    .cat-badge--bangladesh { background: #ECFEFF; color: #0E7490; border-color: rgba(14, 116, 144, 0.16); }
    .cat-badge--internal { background: #EEF2FF; color: #4338CA; border-color: rgba(67, 56, 202, 0.16); }
    .cat-badge--external { background: #FAF5FF; color: #7E22CE; border-color: rgba(126, 34, 206, 0.16); }
    .cat-badge--economy { background: #ECFDF5; color: #047857; border-color: rgba(4, 120, 87, 0.16); }
    .cat-badge--international { background: #F5F3FF; color: #6D28D9; border-color: rgba(109, 40, 217, 0.16); }
    .cat-badge--others { background: #F1F5F9; color: #475569; border-color: rgba(71, 85, 105, 0.14); }
    .status-pill--ok { background: var(--green-soft); color: var(--green); }
    .status-pill--warn { background: var(--amber-soft); color: var(--amber); }
    .status-pill--fail { background: var(--red-soft); color: var(--red); }

    .feed-item-card {
        content-visibility: auto;
        contain-intrinsic-size: auto 185px;
        contain: layout style;
    }
    .apple-news-card { position: relative; padding: 0 0 4px 0; margin: 0; background: transparent; border: none; box-shadow: none; overflow: hidden; }
    .apple-news-card:hover { box-shadow: none; border: none; }
    .apple-news-card::before { display: none; }
    .apple-card-meta { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; width: 100%; }
    .apple-card-title { margin: 0 0 6px 0 !important; padding: 0 !important; font-size: 1.06rem !important; font-weight: 700 !important; line-height: 1.38 !important; letter-spacing: -0.015em !important; }
    .apple-card-title a { color: var(--label) !important; text-decoration: none !important; }
    .apple-card-title a:hover { color: var(--link) !important; }
    .apple-card-native-title { font-size: 0.78rem; color: var(--label-3); margin: -2px 0 6px 0; line-height: 1.35; }
    .apple-card-summary {
        color: #334155; font-size: 0.885rem; line-height: 1.54; margin: 0 0 2px 0;
        display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
    }

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

    .wa-already-sent-notice {
        display: flex; align-items: center; gap: 8px; padding: 7px 12px; margin: 6px 0 6px 0;
        border-radius: var(--r-md, 10px); background: rgba(30, 142, 62, 0.08);
        color: #136b2c; font-size: 0.8rem; font-weight: 600; border: 1px solid rgba(30, 142, 62, 0.25);
    }

    @media (max-width: 768px) {
        .apple-card-title { font-size: 0.98rem !important; line-height: 1.36 !important; }
        .apple-card-summary, .x-post-text { font-size: 0.86rem !important; line-height: 1.50 !important; }
        .pill, .portal-tag, .indian-portal-tag, .cat-badge, .conf-review-badge, .x-metric-item {
            font-size: 0.72rem !important; padding: 3px 8px !important;
        }
        .sec-tag-chip { font-size: 0.70rem !important; padding: 3px 7px !important; }
        .time-badge { margin-left: auto !important; font-size: 0.73rem !important; }
    }
"""

FEED_CARD_CSS = f"<style>\n{_DESIGN_TOKENS_CSS}\n{_PHASE1_ENHANCEMENTS_CSS}\n{_PHASE2_ENHANCEMENTS_CSS}\n{_PILL_AND_FEED_CARD_CSS}\n</style>"

APPLE_DESIGN_SYSTEM_CSS = "<style>\n" + _DESIGN_TOKENS_CSS + _PHASE1_ENHANCEMENTS_CSS + _PHASE2_ENHANCEMENTS_CSS + """

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
       5. PILLS / CHIPS / BADGES & 6. CARDS (single-source-of-truth shared block)
       ========================================================== */
""" + _PILL_AND_FEED_CARD_CSS + """
    .health-card {
        background: var(--surface);
        border: 1px solid var(--separator);
        border-radius: var(--r-md);
        box-shadow: var(--shadow-1);
        transition: box-shadow 0.25s var(--ease), border-color 0.25s var(--ease);
    }
    .health-card:hover {
        box-shadow: var(--shadow-2);
        border-color: var(--separator-strong);
    }
    .accent--india { --accent: #F5A623; }
    .accent--china { --accent: #E5484D; }
    .accent--pakistan { --accent: #30A46C; }
    .accent--bangladesh { --accent: #12A5B5; }
    .accent--internal { --accent: #5B5BD6; }
    .accent--external { --accent: #8E4EC6; }
    .accent--economy { --accent: #0E9F6E; }
    .accent--international { --accent: #6E56CF; }
    .accent--others { --accent: #94A3B8; }
    .accent--indian-press { --accent: #F76B15; }
    .apple-summary-badge {
        display: inline-block; padding: 1px 6px; margin-right: 6px; border-radius: 5px;
        background: var(--tint-soft); color: var(--tint); font-size: 0.65rem; font-weight: 700;
        letter-spacing: 0.04em; vertical-align: 1px;
    }

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
        background: #F8FAFC;
        border: 1px solid rgba(15, 23, 42, 0.09);
        border-radius: 14px;
        padding: 18px 20px;
        margin: 8px 0 12px 0;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
    }
    .unified-brief-box__eyebrow {
        font-size: 0.72rem;
        font-weight: 750;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #0066CC;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .unified-brief-box__headline {
        font-size: 1.10rem;
        font-weight: 700;
        line-height: 1.42;
        color: #0F172A;
        letter-spacing: -0.015em;
        padding-bottom: 10px;
        margin-bottom: 10px;
        border-bottom: 1px solid rgba(15, 23, 42, 0.07);
        word-break: break-word;
    }
    .unified-brief-box__body {
        font-size: 0.93rem;
        line-height: 1.66;
        color: #334155;
        white-space: pre-wrap;
        word-break: break-word;
        margin-bottom: 12px;
        user-select: all;
    }
    .unified-brief-box__profile {
        font-size: 0.82rem;
        font-style: italic;
        line-height: 1.48;
        color: #64748B;
        padding-top: 8px;
        margin-bottom: 10px;
        border-top: 1px solid rgba(15, 23, 42, 0.07);
    }
    .unified-brief-box__source {
        font-size: 0.78rem;
        line-height: 1.4;
        color: #64748B;
        padding-top: 10px;
        border-top: 1px solid rgba(15, 23, 42, 0.07);
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
    }
    .source-lbl {
        font-weight: 600;
        color: #64748B;
        font-size: 0.76rem;
    }
    .source-link-chip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        border-radius: 6px;
        background: #F1F5F9;
        border: 1px solid rgba(15, 23, 42, 0.10);
        color: #0066CC !important;
        font-size: 0.77rem;
        font-weight: 600;
        text-decoration: none !important;
        transition: all 0.15s ease;
    }
    .source-link-chip:hover {
        background: #E2E8F0;
        border-color: rgba(0, 102, 204, 0.28);
        color: #0052A3 !important;
        text-decoration: none !important;
    }
    .source-link-arrow {
        font-size: 0.85rem;
        line-height: 1;
        color: #64748B;
        transition: transform 0.15s ease;
    }
    .source-link-chip:hover .source-link-arrow {
        transform: translate(1px, -1px);
        color: #0066CC;
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
        .apple-card-meta .time-badge { margin-left: auto !important; }
        :is(.main, [data-testid="stMain"]) div[data-testid="stVerticalBlock"]:has(.feed-card-anchor) div[data-testid="stHorizontalBlock"] {
            gap: 8px !important;
        }
    }
    .fulltext-reader-box {
        background: #F8FAFC;
        border: 1px solid rgba(15, 23, 42, 0.09);
        border-radius: 14px;
        padding: 20px 22px;
        margin: 8px 0 12px 0;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
    }
    .fulltext-reader-box__header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 8px;
    }
    .fulltext-reader-box__title {
        font-size: 1.18rem;
        font-weight: 750;
        color: #0F172A;
        line-height: 1.40;
        letter-spacing: -0.015em;
        margin: 0 0 6px 0;
    }
    .fulltext-reader-box__meta {
        font-size: 0.76rem;
        color: #64748B;
        margin-bottom: 12px;
        padding-bottom: 10px;
        border-bottom: 1px solid rgba(15, 23, 42, 0.07);
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

    /* Minimalist Share & Read Modals */
    .share-modal-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 8px;
    }
    .share-modal-type {
        font-size: 0.74rem;
        font-weight: 750;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #0066CC;
        background: rgba(0, 102, 204, 0.08);
        padding: 3px 10px;
        border-radius: 6px;
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
        padding: 3px 10px;
        border-radius: var(--r-pill);
        font-size: 0.72rem;
        font-weight: 600;
    }
    .share-draft-pill--saved { background: #F1F5F9; color: #334155; border: 1px solid rgba(15, 23, 42, 0.08); }
    .share-draft-pill--unsaved { background: #FEF3C7; color: #B45309; border: 1px solid rgba(180, 83, 9, 0.2); }
    .share-draft-pill--sent { background: #DCFCE7; color: #15803D; border: 1px solid rgba(21, 128, 61, 0.2); }

    /* Dialog Container & Backdrop */
    div[data-testid="stDialog"] {
        border-radius: 16px !important;
    }
    div[data-testid="stDialog"] [data-testid="stDialogContent"] {
        border-radius: 16px !important;
        box-shadow: 0 20px 48px rgba(15, 23, 42, 0.16) !important;
        border: 1px solid rgba(15, 23, 42, 0.08) !important;
        padding: 24px !important;
    }

    /* Status Widget inside Modals */
    div[data-testid="stStatusWidget"] {
        border: 1px solid rgba(21, 128, 61, 0.22) !important;
        background: #F0FDF4 !important;
        border-radius: 9px !important;
        padding: 6px 12px !important;
        margin-bottom: 10px !important;
        font-size: 0.78rem !important;
        font-weight: 600 !important;
        color: #15803D !important;
    }
    div[data-testid="stStatusWidget"] summary, div[data-testid="stStatusWidget"] summary * {
        font-size: 0.78rem !important;
        font-weight: 600 !important;
        color: #15803D !important;
    }

    /* WhatsApp Destination Segmented Control in Modals */
    .wa-dest-label {
        font-size: 0.8rem;
        font-weight: 650;
        color: #475569;
        letter-spacing: -0.01em;
        margin: 12px 0 6px 0;
    }
    .wa-dest-val {
        color: #0F172A;
        font-weight: 700;
    }
    div[data-testid="stDialog"] div[data-testid="stSegmentedControl"] {
        background: #F1F5F9 !important;
        border-radius: 9px !important;
        padding: 3px !important;
        margin-bottom: 12px !important;
        border: 1px solid rgba(15, 23, 42, 0.08) !important;
    }

    /* Dialog Modal Action Toolbar Buttons */
    div[data-testid="stDialog"] .stButton > button {
        height: 36px !important;
        min-height: 36px !important;
        border-radius: 8px !important;
        padding: 0 14px !important;
        font-size: 0.83rem !important;
        font-weight: 600 !important;
        border: 1px solid rgba(15, 23, 42, 0.12) !important;
        background: #FFFFFF !important;
        color: #0F172A !important;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04) !important;
        transition: all 0.15s ease !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 6px !important;
        white-space: nowrap !important;
    }
    div[data-testid="stDialog"] .stButton > button:hover {
        background: #F8FAFC !important;
        border-color: rgba(15, 23, 42, 0.24) !important;
        color: #0F172A !important;
    }
    div[data-testid="stDialog"] .stButton > button[kind="primary"] {
        background: #0066CC !important;
        color: #FFFFFF !important;
        border-color: #0066CC !important;
        padding: 0 18px !important;
        font-weight: 650 !important;
        box-shadow: 0 2px 8px rgba(0, 102, 204, 0.22) !important;
    }
    div[data-testid="stDialog"] .stButton > button[kind="primary"]:hover {
        background: #0052A3 !important;
        border-color: #0052A3 !important;
        box-shadow: 0 4px 14px rgba(0, 102, 204, 0.32) !important;
    }
    div[data-testid="stDialog"] .stButton > button[disabled] {
        opacity: 0.55 !important;
        cursor: not-allowed !important;
    }

    /* =========================================================================
       EDITORIAL STUDIO: DIALOG INPUTS, TEXTAREAS & MOBILE EDITING CANVAS
       ========================================================================= */
    .editorial-edit-banner {
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 6px;
        background: linear-gradient(135deg, rgba(0, 102, 204, 0.05), rgba(0, 102, 204, 0.09));
        border: 1px solid rgba(0, 102, 204, 0.16);
        border-radius: 11px;
        padding: 8px 12px;
        margin: 6px 0 12px 0;
    }
    .editorial-edit-banner__tag {
        display: inline-flex;
        align-items: center;
        font-size: 0.72rem;
        font-weight: 750;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: #0066CC;
    }
    .editorial-edit-banner__hint {
        font-size: 0.74rem;
        font-weight: 500;
        color: #64748B;
    }

    /* Dialog Headline Editor (stTextInput) - Override 34px pill chip constraint */
    div[data-testid="stDialog"] div[data-testid="stTextInput"] div[data-baseweb="input"],
    div[data-testid="stDialog"] div[data-testid="stTextInput"] div[data-baseweb="base-input"] {
        border-radius: 11px !important;
        min-height: 44px !important;
        height: auto !important;
        max-height: none !important;
        background-color: #FFFFFF !important;
        border: 1.5px solid rgba(15, 23, 42, 0.14) !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04) !important;
        padding: 2px 8px !important;
        transition: border-color 0.18s var(--ease), box-shadow 0.18s var(--ease) !important;
    }
    div[data-testid="stDialog"] div[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within {
        border-color: #0066CC !important;
        box-shadow: 0 0 0 3.5px rgba(0, 102, 204, 0.16) !important;
        background-color: #FFFFFF !important;
    }
    div[data-testid="stDialog"] div[data-testid="stTextInput"] input {
        font-family: var(--font) !important;
        font-size: 1.04rem !important;
        font-weight: 650 !important;
        color: #0F172A !important;
        line-height: 1.4 !important;
        padding: 8px 6px !important;
    }

    /* Dialog Article Body & Brief Canvas (stTextArea) */
    div[data-testid="stDialog"] div[data-testid="stTextArea"] div[data-baseweb="textarea"] {
        border-radius: 13px !important;
        border: 1.5px solid rgba(15, 23, 42, 0.14) !important;
        background-color: #FFFFFF !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03) !important;
        transition: border-color 0.18s var(--ease), box-shadow 0.18s var(--ease) !important;
        overflow: hidden !important;
    }
    div[data-testid="stDialog"] div[data-testid="stTextArea"] div[data-baseweb="textarea"]:focus-within {
        border-color: #0066CC !important;
        box-shadow: 0 0 0 3.5px rgba(0, 102, 204, 0.16) !important;
    }
    div[data-testid="stDialog"] div[data-testid="stTextArea"] textarea {
        font-family: var(--font) !important;
        font-size: 0.95rem !important;
        line-height: 1.68 !important;
        color: #1E293B !important;
        padding: 12px 14px !important;
        background-color: transparent !important;
        resize: vertical !important;
    }

    /* Input & Textarea Micro-Labels */
    div[data-testid="stDialog"] div[data-testid="stTextInput"] label,
    div[data-testid="stDialog"] div[data-testid="stTextArea"] label {
        font-size: 0.72rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.06em !important;
        text-transform: uppercase !important;
        color: #64748B !important;
        margin-bottom: 5px !important;
    }

    /* Edit Mode Actions Container & Balanced Button Toolbar */
    div[data-testid="stDialog"] div[data-testid="stHorizontalBlock"]:has(.editorial-edit-actions-anchor) {
        margin-top: 14px !important;
        padding-top: 12px !important;
        border-top: 1px solid rgba(15, 23, 42, 0.08) !important;
        align-items: center !important;
    }
    div[data-testid="stDialog"] div[data-testid="stHorizontalBlock"]:has(.editorial-edit-actions-anchor) .stButton > button {
        height: 42px !important;
        min-height: 42px !important;
        border-radius: 10px !important;
        font-size: 0.88rem !important;
        font-weight: 650 !important;
        width: 100% !important;
        justify-content: center !important;
    }

    /* Live Telemetry HUD Bar (Apple Inspired) */
    .apple-telemetry-hud {
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 12px;
        background: #FFFFFF;
        border: 1px solid rgba(0, 102, 204, 0.16);
        box-shadow: 0 4px 16px rgba(15, 23, 42, 0.04);
        border-radius: 12px;
        padding: 9px 16px;
        margin-bottom: 14px;
    }
    .telemetry-hud-lead {
        display: inline-flex;
        align-items: center;
        gap: 8px;
    }
    .telemetry-pulse-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #0066CC;
        box-shadow: 0 0 0 0 rgba(0, 102, 204, 0.7);
        animation: radar-pulse 1.8s infinite;
    }
    @keyframes radar-pulse {
        0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 102, 204, 0.7); }
        70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(0, 102, 204, 0); }
        100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 102, 204, 0); }
    }
    .telemetry-hud-title {
        font-size: 0.74rem;
        font-weight: 750;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #0066CC;
    }
    .telemetry-hud-elapsed {
        font-size: 0.72rem;
        font-weight: 600;
        color: #64748B;
        background: #F1F5F9;
        padding: 2px 7px;
        border-radius: 999px;
    }
    .telemetry-hud-streams {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: wrap;
    }
    .telemetry-stream-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 3px 10px;
        border-radius: 7px;
        font-size: 0.76rem;
        font-weight: 600;
        background: #F8FAFC;
        border: 1px solid rgba(15, 23, 42, 0.08);
        color: #334155;
    }
    .telemetry-stream--done {
        background: #F0FDF4;
        border-color: rgba(21, 128, 61, 0.22);
        color: #15803D;
    }
    .telemetry-stream--running {
        background: #EFF6FF;
        border-color: rgba(0, 102, 204, 0.24);
        color: #0066CC;
    }
    .telemetry-stream--error {
        background: #FEF2F2;
        border-color: rgba(185, 28, 28, 0.22);
        color: #B91C1C;
    }
    .telemetry-stream--idle {
        background: #F8FAFC;
        color: #64748B;
    }
    .telemetry-error-bar {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 14px;
        border-radius: 10px;
        background: #FFFBEB;
        border: 1px solid rgba(180, 83, 9, 0.2);
        color: #92400E;
        font-size: 0.82rem;
    }

    /* Floating New Stories Pill Bar */
    .apple-new-stories-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: #EFF6FF;
        border: 1px solid rgba(0, 102, 204, 0.20);
        border-radius: 999px;
        padding: 7px 16px;
        box-shadow: 0 2px 8px rgba(0, 102, 204, 0.06);
        width: 100%;
        box-sizing: border-box;
    }
    .new-stories-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: #0066CC;
        box-shadow: 0 0 0 0 rgba(0, 102, 204, 0.7);
        animation: radar-pulse 1.8s infinite;
    }
    .new-stories-msg {
        font-size: 0.82rem;
        font-weight: 500;
        color: #0066CC;
    }
    .new-stories-msg b {
        font-weight: 750;
    }
    div[data-testid="stColumn"]:has(button[key^="btn_new_stories_"]) .stButton > button {
        height: 36px !important;
        border-radius: 999px !important;
        background: #0066CC !important;
        color: #FFFFFF !important;
        border-color: #0066CC !important;
        font-weight: 650 !important;
        font-size: 0.82rem !important;
        box-shadow: 0 2px 8px rgba(0, 102, 204, 0.22) !important;
        transition: all 0.15s ease !important;
    }
    div[data-testid="stColumn"]:has(button[key^="btn_new_stories_"]) .stButton > button:hover {
        background: #0052A3 !important;
        border-color: #0052A3 !important;
        box-shadow: 0 4px 12px rgba(0, 102, 204, 0.32) !important;
    }

    .fulltext-reader-box__body {
        font-size: 0.95rem;
        line-height: 1.74;
        color: var(--label);
        word-break: break-word;
        max-height: 54vh;
        overflow-y: auto;
        padding-right: 6px;
        margin-bottom: 12px;
    }
    .reader-para {
        margin: 0 0 12px 0;
        max-width: 68ch;
    }
    .reader-para:last-child {
        margin-bottom: 0;
    }

    /* ==========================================================
       APPLE HIG / LINEAR EXECUTIVE TOAST NOTIFICATIONS & TOOLTIPS
       ========================================================== */
    div[data-testid="stToastContainer"],
    section[data-testid="stToastContainer"] {
        bottom: 24px !important;
        right: 24px !important;
        gap: 10px !important;
        z-index: 999999 !important;
    }

    div[data-testid="stToast"] {
        background: rgba(255, 255, 255, 0.94) !important;
        backdrop-filter: blur(28px) saturate(200%) !important;
        -webkit-backdrop-filter: blur(28px) saturate(200%) !important;
        border: 1px solid rgba(15, 23, 42, 0.09) !important;
        border-radius: 14px !important;
        box-shadow: 0 16px 36px -4px rgba(15, 23, 42, 0.12), 0 4px 12px -2px rgba(15, 23, 42, 0.04) !important;
        padding: 10px 16px !important;
        min-height: 48px !important;
        display: flex !important;
        align-items: center !important;
        gap: 12px !important;
        color: #0F172A !important;
        transition: all 0.22s cubic-bezier(0.16, 1, 0.3, 1) !important;
        animation: toast-slide-in 0.26s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }

    @keyframes toast-slide-in {
        0% { transform: translateY(14px) scale(0.96); opacity: 0; }
        100% { transform: translateY(0) scale(1); opacity: 1; }
    }

    /* Toast Typography */
    div[data-testid="stToast"] div[data-testid="stMarkdownContainer"] {
        margin: 0 !important;
        padding: 0 !important;
    }

    div[data-testid="stToast"] div[data-testid="stMarkdownContainer"] p {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", sans-serif !important;
        font-size: 0.86rem !important;
        font-weight: 550 !important;
        line-height: 1.4 !important;
        color: #0F172A !important;
        letter-spacing: -0.012em !important;
        margin: 0 !important;
    }

    /* Toast Icon: Apple Micro-Badge */
    div[data-testid="stToast"] [data-testid="stIconMaterial"],
    div[data-testid="stToast"] > span:first-child,
    div[data-testid="stToast"] div:first-child > span:first-child {
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: 28px !important;
        height: 28px !important;
        min-width: 28px !important;
        min-height: 28px !important;
        border-radius: 8px !important;
        background: rgba(0, 102, 204, 0.08) !important;
        color: #0066CC !important;
        font-size: 1.1rem !important;
        border: 1px solid rgba(0, 102, 204, 0.16) !important;
    }

    /* Toast Close Button */
    div[data-testid="stToast"] button {
        border: none !important;
        background: transparent !important;
        color: #64748B !important;
        border-radius: 6px !important;
        width: 24px !important;
        height: 24px !important;
        padding: 0 !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        cursor: pointer !important;
        opacity: 0.6 !important;
        transition: all 0.15s ease !important;
    }

    div[data-testid="stToast"] button:hover {
        background: rgba(15, 23, 42, 0.06) !important;
        color: #0F172A !important;
        opacity: 1 !important;
    }

    /* Apple HIG Frosted Tooltips */
    div[data-baseweb="tooltip"],
    div[role="tooltip"],
    div[data-testid="stTooltipContent"] {
        border-radius: 9px !important;
        box-shadow: 0 10px 26px -2px rgba(15, 23, 42, 0.12), 0 2px 6px -1px rgba(15, 23, 42, 0.05) !important;
        background: rgba(255, 255, 255, 0.95) !important;
        backdrop-filter: blur(20px) saturate(180%) !important;
        -webkit-backdrop-filter: blur(20px) saturate(180%) !important;
        border: 1px solid rgba(15, 23, 42, 0.09) !important;
        padding: 6px 12px !important;
        color: #0F172A !important;
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", sans-serif !important;
        font-size: 0.78rem !important;
        font-weight: 550 !important;
        letter-spacing: -0.01em !important;
        line-height: 1.36 !important;
    }

    div[data-baseweb="tooltip"] > div,
    div[role="tooltip"] > div,
    div[data-testid="stTooltipContent"] > div {
        background: transparent !important;
        color: #0F172A !important;
        font-size: 0.78rem !important;
        font-weight: 550 !important;
        padding: 0 !important;
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
    div[data-testid="stTextInput"]:not(div[data-testid="stForm"] *) div[data-baseweb="input"],
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
    div[data-testid="stTextInput"]:not(div[data-testid="stForm"] *) div[data-baseweb="base-input"],
    div[data-testid="stTextInput"]:not(div[data-testid="stForm"] *) div[data-baseweb="base-input"]:focus-within {
        border: none !important;
        box-shadow: none !important;
        background: transparent !important;
        min-height: 32px !important;
        height: 32px !important;
        padding: 0 10px !important;
    }
    div[data-testid="stTextInput"]:not(div[data-testid="stForm"] *) input {
        font-size: 0.8rem !important;
        color: var(--label) !important;
        padding: 0 4px !important;
    }
    div[data-testid="stSelectbox"] div:has(> input):hover,
    div[data-testid="stTextInput"]:not(div[data-testid="stForm"] *) div[data-baseweb="input"]:hover,
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
    div[data-testid="stTextInput"]:not(div[data-testid="stForm"] *) div[data-baseweb="input"]:focus-within,
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
        justify-content: flex-start !important;
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
        justify-content: flex-start !important;
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
    div[data-testid="stHorizontalBlock"]:has(.editorial-brand-anchor) div[data-testid="stButtonGroup"],
    div[data-testid="stHorizontalBlock"]:has(.editorial-brand-anchor) div[data-testid="stButtonGroup"] > div {
        justify-content: flex-end !important;
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
       9. RESPONSIVE (DESKTOP / TABLET / MOBILE) + ACCESSIBILITY
       ========================================================== */
    @media (max-width: 1024px) {
        .block-container { padding: 0.9rem 0.9rem 2rem 0.9rem !important; }
        .page-header__title { font-size: 1.5rem !important; }

        /* Fit editorial navbar tabs comfortably on tablet widths (769px-1024px) */
        div[data-testid="stHorizontalBlock"]:has(.editorial-brand-anchor) div[data-testid="stButtonGroup"] button,
        div[data-testid="stHorizontalBlock"]:has(.editorial-brand-anchor) div[data-testid="stButtonGroup"] button[data-variant="segmented_control"] {
            padding: 0 7px 4px 7px !important;
            font-size: 0.76rem !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.editorial-brand-anchor) div[data-testid="stButtonGroup"] button *,
        div[data-testid="stHorizontalBlock"]:has(.editorial-brand-anchor) div[data-testid="stButtonGroup"] button[data-variant="segmented_control"] * {
            font-size: 0.76rem !important;
        }

        /* Tablet 3-column grid for 5/6-column KPI & Metric rows */
        div[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]),
        div[data-testid="stHorizontalBlock"]:has(.apple-kpi-card) {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: wrap !important;
            gap: 10px !important;
        }
        div[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > div[data-testid="stColumn"],
        div[data-testid="stHorizontalBlock"]:has(.apple-kpi-card) > div[data-testid="stColumn"] {
            flex: 1 1 calc(33.33% - 10px) !important;
            min-width: 170px !important;
            width: auto !important;
        }

        /* Tablet 2-column grid for 3-column Account Directory cards */
        div[data-testid="stHorizontalBlock"]:has(.acct-card-rich) {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: wrap !important;
            gap: 10px !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.acct-card-rich) > div[data-testid="stColumn"] {
            flex: 1 1 calc(50% - 10px) !important;
            min-width: 240px !important;
            width: auto !important;
        }
    }

    @media (max-width: 900px) {
        .block-container { padding: 0.75rem 0.75rem 2rem 0.75rem !important; }
        .page-header__title { font-size: 1.35rem !important; }
    }

    @media (max-width: 768px) {
        header[data-testid="stHeader"] { height: 0.25rem !important; min-height: 0 !important; }
        .block-container {
            padding: 0.45rem 0.6rem 2rem 0.6rem !important;
            max-width: 100% !important;
        }

        /* Row 1: Compact stacked Brand + Horizontally Swipeable Editorial Tabs */
        div[data-testid="stHorizontalBlock"]:has(.editorial-brand-anchor) {
            flex-direction: column !important;
            align-items: stretch !important;
            gap: 2px !important;
            padding: 0 !important;
            margin-bottom: -4px !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.editorial-brand-anchor) > div[data-testid="stColumn"] {
            width: 100% !important;
            min-width: 100% !important;
            flex: 1 1 100% !important;
        }
        .editorial-brand-anchor {
            height: 30px !important;
            justify-content: space-between !important;
            width: 100% !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.editorial-brand-anchor) div[data-testid="stButtonGroup"],
        div[data-testid="stHorizontalBlock"]:has(.editorial-brand-anchor) div[data-testid="stButtonGroup"] > div,
        div[data-testid="stButtonGroup"],
        div[data-testid="stButtonGroup"] > div,
        div[data-baseweb="button-group"] {
            justify-content: flex-start !important;
            overflow-x: auto !important;
            -webkit-overflow-scrolling: touch !important;
            scrollbar-width: none !important;
            column-gap: 2px !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.editorial-brand-anchor) div[data-testid="stButtonGroup"] button,
        div[data-testid="stHorizontalBlock"]:has(.editorial-brand-anchor) div[data-testid="stButtonGroup"] button[data-variant="segmented_control"],
        div[data-testid="stButtonGroup"] button,
        div[data-testid="stButtonGroup"] button[data-variant="segmented_control"] {
            height: 32px !important;
            min-height: 32px !important;
            padding: 0 8px 3px 8px !important;
            font-size: 0.76rem !important;
            flex: 0 0 auto !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.editorial-brand-anchor) div[data-testid="stButtonGroup"] button *,
        div[data-testid="stHorizontalBlock"]:has(.editorial-brand-anchor) div[data-testid="stButtonGroup"] button[data-variant="segmented_control"] *,
        div[data-testid="stButtonGroup"] button *,
        div[data-testid="stButtonGroup"] button[data-variant="segmented_control"] * {
            font-size: 0.76rem !important;
            line-height: 28px !important;
        }

        /* Row 2: Keep Filter Pills & Utility Controls in strictly 2 full-width rows on mobile */
        div[data-testid="stHorizontalBlock"]:has([data-testid="stPopover"]) {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: wrap !important;
            gap: 5px !important;
            align-items: center !important;
            width: 100% !important;
        }
        /* Ensure popover and buttons stretch to 100% of their mobile flex column */
        div[data-testid="stHorizontalBlock"]:has([data-testid="stPopover"]) [data-testid="stPopover"],
        div[data-testid="stHorizontalBlock"]:has([data-testid="stPopover"]) [data-testid="stPopover"] > div,
        div[data-testid="stHorizontalBlock"]:has([data-testid="stPopover"]) [data-testid="stPopover"] button,
        div[data-testid="stHorizontalBlock"]:has([data-testid="stPopover"]) .stButton,
        div[data-testid="stHorizontalBlock"]:has([data-testid="stPopover"]) .stButton > button {
            width: 100% !important;
        }
        /* First 2 filter selectboxes sit side-by-side on Line 1 (50% / 50%) */
        div[data-testid="stHorizontalBlock"]:has([data-testid="stPopover"]) > div[data-testid="stColumn"]:has([data-testid="stSelectbox"]) {
            flex: 1 1 calc(50% - 5px) !important;
            min-width: 130px !important;
            width: auto !important;
        }
        /* Default (2-selectbox workspaces: Live Feed & Indian Press):
           Line 2 fills 100% equally — [🕒 12h ▾ (50%)] + [🔍 (25%)] + [🔄 (25%)] */
        div[data-testid="stHorizontalBlock"]:has([data-testid="stPopover"]) > div[data-testid="stColumn"]:has([data-testid="stPopover"]) {
            display: flex !important;
            flex: 1 1 calc(50% - 5px) !important;
            min-width: 110px !important;
            width: auto !important;
        }
        div[data-testid="stHorizontalBlock"]:has([data-testid="stPopover"]) > div[data-testid="stColumn"]:has(.stButton):not(:has([data-testid="stPopover"])) {
            flex: 1 1 calc(25% - 5px) !important;
            min-width: 48px !important;
            max-width: none !important;
            width: auto !important;
        }
        /* 3-selectbox workspaces (Nepali Media & X):
           Line 2 has [3rd Selectbox] + [🕒 12h ▾] + [🔍] + [🔄] filling 100% on one line */
        div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-of-type(3) [data-testid="stSelectbox"]) > div[data-testid="stColumn"]:has([data-testid="stSelectbox"]):nth-of-type(3) {
            flex: 1 1 105px !important;
            min-width: 96px !important;
            width: auto !important;
        }
        div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-of-type(3) [data-testid="stSelectbox"]) > div[data-testid="stColumn"]:has([data-testid="stPopover"]) {
            flex: 0.85 1 78px !important;
            min-width: 76px !important;
            width: auto !important;
        }
        div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-of-type(3) [data-testid="stSelectbox"]) > div[data-testid="stColumn"]:has(.stButton):not(:has([data-testid="stPopover"])) {
            flex: 0 0 38px !important;
            min-width: 38px !important;
            max-width: 40px !important;
            width: 38px !important;
        }
        div[data-testid="stHorizontalBlock"]:has([data-testid="stPopover"]) > div[data-testid="stColumn"]:has(.stButton):not(:has([data-testid="stPopover"])) button {
            padding: 0 !important;
        }

        /* Secondary multi-column filter bars (Analytics & Export, System Health, X Directory) in a compact 2-col grid */
        div[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]):not(:has([data-testid="stPopover"])):not(div[data-testid="stForm"] *) {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: wrap !important;
            gap: 6px !important;
            align-items: center !important;
            width: 100% !important;
        }
        div[data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]):not(:has([data-testid="stPopover"])):not(div[data-testid="stForm"] *) > div[data-testid="stColumn"] {
            flex: 1 1 calc(50% - 6px) !important;
            min-width: 135px !important;
            width: auto !important;
        }

        /* 2x2 grid for KPI Metric rows on mobile */
        div[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]),
        div[data-testid="stHorizontalBlock"]:has(.apple-kpi-card) {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: wrap !important;
            gap: 8px !important;
        }
        div[data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > div[data-testid="stColumn"],
        div[data-testid="stHorizontalBlock"]:has(.apple-kpi-card) > div[data-testid="stColumn"] {
            flex: 1 1 calc(50% - 8px) !important;
            min-width: 135px !important;
            width: auto !important;
        }
        div[data-testid="stMetric"] {
            padding: 10px 12px !important;
        }
        div[data-testid="stMetricValue"], div[data-testid="stMetricValue"] * {
            font-size: 1.15rem !important;
        }
        .apple-kpi-card {
            padding: 10px 12px !important;
        }
        .apple-kpi-card__value {
            font-size: 1.25rem !important;
        }

        /* Mobile typography & card spacing */
        .apple-card-title {
            font-size: 0.97rem !important;
            line-height: 1.35 !important;
        }
        .apple-card-summary, .x-post-text {
            font-size: 0.84rem !important;
            line-height: 1.48 !important;
        }
        .pill, .portal-tag, .indian-portal-tag, .cat-badge, .conf-review-badge, .x-metric-item {
            font-size: 0.69rem !important;
            padding: 2px 7px !important;
        }
        .sec-tag-chip {
            font-size: 0.67rem !important;
            padding: 2px 6px !important;
        }
        .time-badge {
            margin-left: auto !important;
            font-size: 0.7rem !important;
        }

        /* Mobile Dialog Modal & Editorial Studio Touch Ergonomics */
        div[data-testid="stDialog"] [data-testid="stDialogContent"] {
            width: 95vw !important;
            max-width: 95vw !important;
            padding: 16px 14px 20px 14px !important;
            border-radius: 18px !important;
        }
        /* Crucial: Prevent iOS Safari auto-zoom on input/textarea focus (< 16px triggers zoom) */
        div[data-testid="stDialog"] div[data-testid="stTextInput"] input,
        div[data-testid="stDialog"] div[data-testid="stTextArea"] textarea {
            font-size: 16px !important;
        }
        div[data-testid="stDialog"] div[data-testid="stTextInput"] div[data-baseweb="input"],
        div[data-testid="stDialog"] div[data-testid="stTextInput"] div[data-baseweb="base-input"] {
            min-height: 46px !important;
        }
        div[data-testid="stDialog"] div[data-testid="stTextArea"] textarea {
            min-height: 140px !important;
            max-height: 38vh !important;
            padding: 12px 14px !important;
            line-height: 1.62 !important;
            -webkit-overflow-scrolling: touch !important;
        }
        /* Apple HIG 44px minimum touch targets on mobile for all dialog buttons */
        div[data-testid="stDialog"] .stButton > button {
            height: 44px !important;
            min-height: 44px !important;
            font-size: 0.9rem !important;
            border-radius: 10px !important;
        }
        /* Symmetrical 50% / 50% layout for mobile edit action buttons */
        div[data-testid="stDialog"] div[data-testid="stHorizontalBlock"]:has(.editorial-edit-actions-anchor) {
            display: flex !important;
            flex-direction: row !important;
            width: 100% !important;
            gap: 8px !important;
        }
        div[data-testid="stDialog"] div[data-testid="stHorizontalBlock"]:has(.editorial-edit-actions-anchor) > div[data-testid="stColumn"] {
            flex: 1 1 50% !important;
            min-width: 0 !important;
            width: 50% !important;
        }
    }

    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after { animation: none !important; transition: none !important; }
    }
</style>
"""

AUTH_CSS = "<style>\n" + _DESIGN_TOKENS_CSS + _PHASE2_ENHANCEMENTS_CSS + """
    /* ── Reset & Base ─────────────────────────────────── */
    html, body, .stMarkdown, p, label, h1, h2, button, input {
        font-family: var(--font) !important;
        -webkit-font-smoothing: antialiased !important;
        -moz-osx-font-smoothing: grayscale !important;
    }

    /* ── Ambient Background ───────────────────────────── */
    [data-testid="stAppViewContainer"], .main {
        background: linear-gradient(160deg, #F0F4FA 0%, #E8EDF6 30%, #F4F1F8 60%, #EDF3FA 100%) !important;
        min-height: 100dvh;
    }

    /* ── Hide chrome ──────────────────────────────────── */
    [data-testid="stSidebar"], [data-testid="collapsedControl"],
    header[data-testid="stHeader"], div[data-testid="InputInstructions"],
    [data-testid="stDecoration"] { display: none !important; }

    /* ── Layout ───────────────────────────────────────── */
    .block-container {
        padding-top: 12vh !important;
        max-width: 400px !important;
        margin: 0 auto !important;
        padding-left: 20px !important;
        padding-right: 20px !important;
    }

    /* ── Card (the form) ──────────────────────────────── */
    div[data-testid="stForm"] {
        background: rgba(255, 255, 255, 0.82) !important;
        -webkit-backdrop-filter: saturate(180%) blur(28px) !important;
        backdrop-filter: saturate(180%) blur(28px) !important;
        border: 1px solid rgba(255, 255, 255, 0.55) !important;
        border-radius: 24px !important;
        padding: 44px 36px 32px 36px !important;
        box-shadow:
            0 0 0 0.5px rgba(0, 0, 0, 0.03),
            0 2px 4px rgba(0, 0, 0, 0.02),
            0 12px 40px rgba(0, 0, 0, 0.06) !important;
        animation: auth-card-enter 0.7s var(--ease) both;
    }

    @keyframes auth-card-enter {
        from { opacity: 0; transform: translateY(16px) scale(0.98); }
        to   { opacity: 1; transform: translateY(0) scale(1); }
    }

    /* ── Header ───────────────────────────────────────── */
    .auth-header { text-align: center; margin-bottom: 28px; }

    .auth-header__icon-ring {
        display: inline-flex; align-items: center; justify-content: center;
        width: 56px; height: 56px; border-radius: 16px;
        background: linear-gradient(135deg, #DC143C 0%, #C41230 100%);
        box-shadow: 0 4px 14px rgba(220, 20, 60, 0.25), 0 1px 3px rgba(0, 0, 0, 0.08);
        margin-bottom: 18px;
        animation: auth-icon-enter 0.8s var(--ease) 0.15s both;
    }
    .auth-header__icon-ring svg { display: block; }

    @keyframes auth-icon-enter {
        from { opacity: 0; transform: scale(0.7) rotate(-8deg); }
        to   { opacity: 1; transform: scale(1) rotate(0deg); }
    }

    .auth-header__title {
        font-size: 1.65rem !important;
        font-weight: 700 !important;
        color: var(--label) !important;
        letter-spacing: -0.025em !important;
        margin: 0 0 2px 0 !important;
        padding: 0 !important;
        line-height: 1.2 !important;
    }
    .auth-header__subtitle {
        font-size: 0.84rem;
        font-weight: 500;
        color: var(--label-3);
        letter-spacing: 0.02em;
        margin: 0;
    }

    /* ── Input Field ──────────────────────────────────── */
    div[data-testid="stForm"] div[data-baseweb="input"] {
        margin-top: 4px !important;
    }
    div[data-testid="stForm"] div[data-baseweb="input"] > div {
        min-height: 50px !important;
        border-radius: 14px !important;
        background: rgba(255, 255, 255, 0.65) !important;
        border-color: rgba(0, 0, 0, 0.08) !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease, background 0.2s ease !important;
    }
    div[data-testid="stForm"] div[data-baseweb="input"] > div:focus-within {
        border-color: var(--tint) !important;
        box-shadow: 0 0 0 3.5px rgba(0, 102, 204, 0.12) !important;
        background: #FFFFFF !important;
    }
    div[data-testid="stForm"] input {
        font-size: 0.95rem !important;
        font-weight: 400 !important;
        letter-spacing: 0.01em !important;
    }

    /* ── Submit Button ────────────────────────────────── */
    div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button {
        min-height: 50px !important;
        width: 100% !important;
        border-radius: 14px !important;
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.01em !important;
        background: linear-gradient(180deg, #1A8CFF 0%, #0066CC 100%) !important;
        color: #FFFFFF !important;
        border: none !important;
        box-shadow: 0 1px 3px rgba(0, 102, 204, 0.3), 0 4px 12px rgba(0, 102, 204, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.15) !important;
        transition: transform 0.15s var(--ease), box-shadow 0.15s ease, filter 0.15s ease !important;
        cursor: pointer !important;
    }
    div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button:hover {
        filter: brightness(1.05) !important;
        box-shadow: 0 1px 3px rgba(0, 102, 204, 0.35), 0 6px 18px rgba(0, 102, 204, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.15) !important;
        transform: translateY(-0.5px) !important;
    }
    div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button:active {
        transform: scale(0.985) translateY(0px) !important;
        filter: brightness(0.97) !important;
        box-shadow: 0 1px 2px rgba(0, 102, 204, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.1) !important;
        transition-duration: 0.05s !important;
    }

    /* ── Footer ───────────────────────────────────────── */
    .auth-footer {
        text-align: center;
        font-size: 0.72rem;
        font-weight: 500;
        color: var(--label-3);
        letter-spacing: 0.03em;
        margin-top: 20px;
        opacity: 0.7;
    }
    .auth-footer svg {
        vertical-align: -2px;
        margin-right: 4px;
        opacity: 0.55;
    }
</style>
"""

__all__ = ["APPLE_DESIGN_SYSTEM_CSS", "FEED_CARD_CSS", "AUTH_CSS"]

