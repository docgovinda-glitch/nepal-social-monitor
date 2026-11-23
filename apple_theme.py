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

_PHASE3_ENHANCEMENTS_CSS = """
    /* ═══════════════════════════════════════════════════════════
       PHASE 3: ADMIN DASHBOARD, HELP SYSTEM, ACTIVITY LOG, i18n
       ═══════════════════════════════════════════════════════════ */

    /* 3.1: Admin Dashboard Cards */
    .admin-section {
        display: flex; flex-direction: column; gap: 16px;
        padding: 16px; background: linear-gradient(180deg, #FAFBFD 0%, #F5F7FA 100%);
        border-radius: 14px; margin-bottom: 16px;
    }
    .admin-card {
        background: var(--surface);
        border: 1px solid var(--separator);
        border-radius: 12px;
        padding: 16px;
        display: flex; justify-content: space-between;
        align-items: center; gap: 16px;
    }
    .admin-card--dangerous {
        border-color: rgba(185, 28, 28, 0.2);
        background: rgba(254, 226, 226, 0.3);
    }
    .admin-card__content {
        display: flex; flex-direction: column;
        gap: 4px; flex: 1;
    }
    .admin-card__label {
        font-size: 0.84rem; font-weight: 600; color: var(--label);
    }
    .admin-card__description {
        font-size: 0.75rem; color: var(--label-2);
    }
    .admin-card__action {
        display: flex; gap: 6px;
    }

    /* 3.2: Contextual Help Tooltips */
    .help-tooltip {
        display: inline-flex; align-items: center; justify-content: center;
        width: 20px; height: 20px;
        border-radius: 50%; background: rgba(0, 102, 204, 0.1);
        color: var(--tint); font-size: 0.75rem; font-weight: 700;
        cursor: help; transition: all 0.15s ease;
    }
    .help-tooltip:hover {
        background: var(--tint-soft);
        transform: scale(1.1);
    }
    .help-tooltip__content {
        position: absolute; z-index: 1000;
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(0, 0, 0, 0.1);
        border-radius: 10px;
        padding: 10px 14px;
        font-size: 0.75rem; line-height: 1.4;
        color: var(--label); max-width: 240px;
        box-shadow: 0 10px 26px rgba(0, 0, 0, 0.12);
    }

    /* 3.3: Activity Log & Timeline */
    .activity-log {
        background: var(--surface);
        border: 1px solid var(--separator);
        border-radius: 14px;
        padding: 16px 0;
    }
    .activity-item {
        display: flex; gap: 12px;
        padding: 12px 16px;
        border-bottom: 1px solid var(--separator);
        transition: background 0.15s ease;
    }
    .activity-item:hover {
        background: var(--surface-muted);
    }
    .activity-item:last-child {
        border-bottom: none;
    }
    .activity-item__icon {
        display: flex; align-items: center; justify-content: center;
        width: 32px; height: 32px; min-width: 32px;
        border-radius: 8px; background: var(--tint-soft);
        color: var(--tint); font-size: 0.95rem;
    }
    .activity-item__content {
        display: flex; flex-direction: column;
        gap: 2px; flex: 1;
    }
    .activity-item__title {
        font-size: 0.84rem; font-weight: 600; color: var(--label);
    }
    .activity-item__time {
        font-size: 0.72rem; color: var(--label-3);
    }

    /* 3.4: Health Metrics Dashboard */
    .health-metrics-grid {
        display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 12px; margin-bottom: 16px;
    }
    .health-metric-card {
        background: var(--surface);
        border: 1px solid var(--separator);
        border-radius: 12px;
        padding: 16px;
        text-align: center;
    }
    .health-metric-value {
        font-size: 1.8rem; font-weight: 700;
        color: var(--label); line-height: 1;
    }
    .health-metric-label {
        font-size: 0.75rem; color: var(--label-2);
        margin-top: 6px; font-weight: 500;
    }
    .health-metric-sparkline {
        height: 24px; margin-top: 8px;
        background: var(--surface-muted);
        border-radius: 4px;
    }

    /* 3.5: Scheduled Export Card */
    .scheduled-export-card {
        background: linear-gradient(135deg, #E0E7FF 0%, #F0E7FF 100%);
        border: 1px solid rgba(99, 102, 241, 0.2);
        border-radius: 14px;
        padding: 16px;
        display: flex; justify-content: space-between;
        align-items: center; gap: 16px;
    }
    .scheduled-export-card__info {
        display: flex; flex-direction: column;
        gap: 4px;
    }
    .scheduled-export-card__time {
        font-size: 0.84rem; font-weight: 650; color: #4F46E5;
    }
    .scheduled-export-card__freq {
        font-size: 0.72rem; color: #6366F1;
    }

    /* 3.6: Localization Support */
    .lang-selector {
        display: flex; gap: 4px;
    }
    .lang-button {
        padding: 6px 10px;
        border: 1px solid var(--separator);
        border-radius: 8px;
        background: var(--surface);
        font-size: 0.72rem; font-weight: 600;
        color: var(--label-2);
        cursor: pointer;
        transition: all 0.15s ease;
    }
    .lang-button.active {
        background: var(--tint-soft);
        border-color: var(--tint);
        color: var(--tint);
    }
    .lang-button:hover {
        border-color: var(--tint);
    }

    /* 3.7: Getting Started Guide */
    .onboarding-card {
        background: linear-gradient(135deg, #F0FDF4 0%, #ECFDF5 100%);
        border: 1px solid rgba(21, 128, 61, 0.2);
        border-radius: 14px;
        padding: 16px;
        margin-bottom: 16px;
        display: flex; justify-content: space-between;
        align-items: center; gap: 12px;
    }
    .onboarding-card__content {
        display: flex; flex-direction: column;
        gap: 4px;
    }
    .onboarding-card__title {
        font-size: 0.95rem; font-weight: 650;
        color: #15803D;
    }
    .onboarding-card__steps {
        font-size: 0.75rem; color: #22C55E;
        line-height: 1.5;
    }
    .onboarding-card__close {
        flex-shrink: 0; width: 24px; height: 24px;
        border: none; background: rgba(21, 128, 61, 0.1);
        border-radius: 6px; color: #15803D;
        cursor: pointer; transition: all 0.15s ease;
    }
    .onboarding-card__close:hover {
        background: rgba(21, 128, 61, 0.2);
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
    .sync-status-pill--waiting {
        color: #64748B;
        background: linear-gradient(90deg, #F1F5F9 0%, #E2E8F0 50%, #F1F5F9 100%);
        background-size: 200% 100%;
        animation: sync-shimmer 1.8s ease-in-out infinite;
    }
    @keyframes sync-shimmer {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
    }
    .sync-fresh-chip {
        margin-left: auto; font-size: 0.7rem; font-weight: 600;
        color: #64748B; white-space: nowrap;
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
        overflow: hidden !important;
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

FEED_CARD_CSS = f"<style>\n{_DESIGN_TOKENS_CSS}\n{_PHASE1_ENHANCEMENTS_CSS}\n{_PHASE2_ENHANCEMENTS_CSS}\n{_PHASE3_ENHANCEMENTS_CSS}\n{_PILL_AND_FEED_CARD_CSS}\n</style>"

APPLE_DESIGN_SYSTEM_CSS = "<style>\n" + _DESIGN_TOKENS_CSS + _PHASE1_ENHANCEMENTS_CSS + _PHASE2_ENHANCEMENTS_CSS + _PHASE3_ENHANCEMENTS_CSS + """

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

    /* Tooltips: one compact dark glass tip (outer layers are transparent so nothing stacks into a box-in-a-box) */
    div[data-baseweb="tooltip"], div[role="tooltip"], div[data-baseweb="popover"]:has(div[data-testid="stTooltipContent"]) {
        background: transparent !important; border: 0 !important; box-shadow: none !important; padding: 0 !important; border-radius: 0 !important;
        backdrop-filter: none !important; -webkit-backdrop-filter: none !important;
    }
    div[data-testid="stTooltipContent"] {
        background: rgba(29, 29, 31, 0.92) !important; color: #F5F5F7 !important;
        backdrop-filter: blur(16px) saturate(160%) !important; -webkit-backdrop-filter: blur(16px) saturate(160%) !important;
        border: 0 !important; border-radius: 8px !important; padding: 6px 10px !important; max-width: 260px !important;
        box-shadow: 0 6px 18px rgba(0, 0, 0, 0.22) !important;
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", sans-serif !important;
        font-size: 0.74rem !important; font-weight: 550 !important; letter-spacing: 0 !important; line-height: 1.3 !important;
    }
    div[data-testid="stTooltipContent"], div[data-testid="stTooltipContent"] * {
        color: #F5F5F7 !important;
    }
    div[data-testid="stTooltipContent"] > div, div[data-testid="stTooltipContent"] p, div[data-testid="stTooltipContent"] [data-testid="stMarkdownContainer"] {
        background: transparent !important; border: 0 !important; box-shadow: none !important; padding: 0 !important; margin: 0 !important; border-radius: 0 !important;
        font-size: inherit !important; font-weight: inherit !important; white-space: normal !important;
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

AUTH_CSS = "<style>\n" + _DESIGN_TOKENS_CSS + _PHASE2_ENHANCEMENTS_CSS + _PHASE3_ENHANCEMENTS_CSS + """
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



_COMPACT_UX_CSS = """
    /* ===== Compact UX: fewer rows, no overlap, minimal scrolling ===== */
    .feed-card-inner { display: block; }
    /* Dialog action strip is icons only at every width */
    div[data-testid="stDialog"] div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(5)) > div[data-testid="stColumn"]:not(:last-child) .stButton button [data-testid="stMarkdownContainer"] { display: none !important; }

    /* WhatsApp glyph replaces the generic share/send icon */
    [class*="st-key-btn_gen_"] button [data-testid="stIconMaterial"], [class*="st-key-dlg_conf_"] button[kind="primary"] [data-testid="stIconMaterial"], [class*="st-key-dlg_rd_conf_"] button[kind="primary"] [data-testid="stIconMaterial"] {
        font-size: 0 !important; width: 18px !important; height: 18px !important; display: inline-block !important; background: currentColor !important;
        -webkit-mask: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22%3E%3Cpath d=%22M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z%22/%3E%3C/svg%3E") center / contain no-repeat; mask: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22%3E%3Cpath d=%22M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z%22/%3E%3C/svg%3E") center / contain no-repeat;
    }
    [class*="st-key-btn_gen_"] button[kind="primary"], [class*="st-key-dlg_conf_"] button[kind="primary"], [class*="st-key-dlg_rd_conf_"] button[kind="primary"] { background: var(--green-soft) !important; color: var(--green) !important; }
    [class*="st-key-btn_gen_"] button[kind="primary"]:hover, [class*="st-key-dlg_conf_"] button[kind="primary"]:hover, [class*="st-key-dlg_rd_conf_"] button[kind="primary"]:hover { background: var(--green-soft) !important; filter: brightness(0.96); }
    [class*="st-key-btn_gen_"] button *, [class*="st-key-dlg_conf_"] button[kind="primary"] *, [class*="st-key-dlg_rd_conf_"] button[kind="primary"] * { color: inherit !important; }
    .feed-btn--wa { background: var(--green-soft) !important; border-color: transparent !important; color: var(--green) !important; min-inline-size: 40px; padding: 0 12px; }
    .feed-btn--wa:hover { filter: brightness(0.96); }
    .feed-btn--wa svg { width: 18px; height: 18px; fill: currentColor; }

    .feed-card-stripe { border-radius: 0; z-index: 1; }
    .sec-tag-more { display: none; background: #EEF2F7; font-weight: 650; }
    .sync-fresh-chip .fresh-short { display: none; }

    /* Dialog action strip (5+ columns): tighter buttons, Send label may wrap instead of truncating */
    div[data-testid="stDialog"] div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(5)) .stButton button { padding: 0 8px !important; }
    div[data-testid="stDialog"] div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(5)) > div[data-testid="stColumn"]:last-child .stButton button {
        height: auto !important; min-height: 38px !important; padding: 4px 10px !important; line-height: 1.2 !important;
    }
    div[data-testid="stDialog"] div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(5)) > div[data-testid="stColumn"]:last-child .stButton button p { white-space: normal !important; }

    @media (max-width: 640px) {
        /* Card header: always one row; long source names truncate instead of wrapping */
        .apple-card-meta { flex-wrap: nowrap; gap: 5px; margin-bottom: 7px; }
        .apple-card-meta > * { flex-shrink: 0; }
        .apple-card-meta .portal-tag, .apple-card-meta .indian-portal-tag {
            display: block; flex-shrink: 1; min-width: 0; max-width: 44%;
            overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
        }
        .apple-card-meta .cat-badge { flex-shrink: 1; min-width: 0; max-width: 42%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .apple-card-meta .indian-portal-tag { max-width: 36%; }
        .apple-card-meta .pill, .apple-card-meta .portal-tag, .apple-card-meta .indian-portal-tag,
        .apple-card-meta .cat-badge, .apple-card-meta .conf-review-badge { padding: 2px 7px; font-size: 0.68rem; }
        .apple-card-meta .time-badge { margin-left: auto; font-size: 0.7rem; }
        .apple-card-meta .cat-ico, .apple-card-meta .conf-review-badge .rv-word { display: none; }
        .apple-card-title { margin-bottom: 4px !important; }
        .apple-card-summary { -webkit-line-clamp: 2 !important; }

        /* Footer: one row = first tag + "+N" on the left, compact actions on the right */
        .feed-card-wrap { padding: 12px 14px 10px 17px !important; }
        .feed-card-wrap .feed-card-footer { margin-top: 8px; padding-top: 8px; gap: 8px; }
        .feed-card-wrap .feed-card-footer:has(.chip-row) { flex-wrap: nowrap; }
        .feed-card-wrap .feed-card-footer .chip-row { flex: 1 1 0; min-width: 0; flex-wrap: nowrap; overflow: hidden; }
        .feed-card-wrap .chip-row .sec-tag-chip { padding: 2px 7px; font-size: 0.68rem; white-space: nowrap; flex-shrink: 0; }
        .feed-card-wrap .chip-row:has(.sec-tag-more) .sec-tag-chip:not(.sec-tag-more):nth-child(n+2) { display: none; }
        .feed-card-wrap .chip-row .sec-tag-chip:first-child { flex-shrink: 1; min-width: 0; display: block; overflow: hidden; text-overflow: ellipsis; }
        .feed-card-wrap .sec-tag-more { display: inline-flex; }
        .feed-card-wrap .feed-card-actions { flex-wrap: nowrap; flex-shrink: 0; gap: 5px; }
        .feed-card-wrap .feed-btn { height: 34px; min-block-size: 34px; min-inline-size: 36px; padding: 0 11px; }
        .feed-card-wrap .feed-btn__label { display: none; }

        /* Sync bar: one compact row */
        .sync-status-bar { padding: 6px 9px; gap: 5px; margin: 2px 0 8px 0; justify-content: flex-start; }
        .sync-status-pill { padding: 3px 8px; font-size: 0.68rem; gap: 3px; }
        .sync-status-pill .sp-name { display: none; }
        .sync-fresh-chip { font-size: 0.68rem; }
        .sync-fresh-chip .fresh-long { display: none; }
        .sync-fresh-chip .fresh-short { display: inline; }

        /* Dialogs: keep action buttons side by side (Streamlit stacks columns on phones) */
        div[data-testid="stDialog"] [data-testid="stDialogContent"] { padding: 14px 12px !important; }
        div[data-testid="stDialog"] div[data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 6px !important; }
        div[data-testid="stDialog"] div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
            flex: 1 1 0 !important; min-width: 0 !important; width: auto !important;
        }
        div[data-testid="stDialog"] div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(3)):not(:has(> div[data-testid="stColumn"]:nth-child(4))) > div[data-testid="stColumn"]:first-child {
            flex: 1.7 1 0 !important;
        }
        div[data-testid="stDialog"] div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(3)):not(:has(> div[data-testid="stColumn"]:nth-child(4))) > div[data-testid="stColumn"]:last-child {
            flex: 1 1 0 !important;
        }
        div[data-testid="stDialog"] div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(3)):not(:has(> div[data-testid="stColumn"]:nth-child(4))) > div[data-testid="stColumn"]:nth-child(2) {
            flex: 1 1 0 !important;
        }
        div[data-testid="stDialog"] div[data-testid="stHorizontalBlock"] .stButton button {
            height: 38px !important; min-height: 38px !important; padding: 0 5px !important;
            font-size: 0.78rem !important; gap: 4px !important; white-space: nowrap !important;
        }
        div[data-testid="stDialog"] div[data-testid="stHorizontalBlock"] .stButton button p { white-space: nowrap !important; }
        /* 5+ columns (edit/copy/save/close strip + Send): strip on one row, Send full width below */
        div[data-testid="stDialog"] div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(5)) { flex-wrap: wrap !important; row-gap: 8px !important; }
        div[data-testid="stDialog"] div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(5)) > div[data-testid="stColumn"]:last-child {
            flex: 1 1 100% !important;
        }
        div[data-testid="stDialog"] div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(5)) > div[data-testid="stColumn"]:not(:last-child) .stButton button [data-testid="stMarkdownContainer"] { display: none !important; }
        div[data-testid="stDialog"] div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(5)) > div[data-testid="stColumn"]:last-child .stButton button { height: 44px !important; min-height: 44px !important; font-size: 0.86rem !important; white-space: normal !important; }
        div[data-testid="stDialog"] div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(5)) > div[data-testid="stColumn"]:last-child .stButton button p { white-space: normal !important; }

        /* overflow:hidden on the dialog shell would trap sticky children; clip keeps rounded corners without scroll containment */
        div[data-testid="stDialog"] div:has(> [role="dialog"]) { overflow: clip !important; }
        /* Action bar stays reachable while reading long text (sticky must sit on the layout wrapper) */
        div[data-testid="stDialog"] div[data-testid="stLayoutWrapper"]:has(> div[data-testid="stHorizontalBlock"] .stButton),
        div[data-testid="stDialog"] div[data-testid="stLayoutWrapper"]:has(> div[data-testid="stHorizontalBlock"] iframe) {
            position: sticky; bottom: 0; z-index: 6; background: #FFFFFF;
            padding: 8px 0 10px 0; margin-top: 4px;
        }

        /* Reader: one scroll area, tighter padding */
        .fulltext-reader-box { padding: 12px 13px; margin: 4px 0 8px 0; border-radius: 12px; }
        .fulltext-reader-box__title { font-size: 1.05rem; }
        .fulltext-reader-box__body { max-height: none !important; overflow: visible !important; padding-right: 0; margin-bottom: 8px; font-size: 0.92rem; line-height: 1.66; }
        .reader-para { margin-bottom: 9px; }

        /* Destination selector: wrap instead of clipping the second group */
        div[data-testid="stDialog"] div[data-testid="stButtonGroup"] { overflow: visible !important; }
        div[data-testid="stDialog"] div[data-testid="stButtonGroup"] [role="radiogroup"] { flex-wrap: wrap !important; row-gap: 4px !important; }
        div[data-testid="stDialog"] div[data-testid="stButtonGroup"] button[data-variant="segmented_control"] { flex: 1 1 auto !important; white-space: normal !important; font-size: 0.78rem !important; }
    }
"""


def _append_css(block: str, extra: str) -> str:
    head, sep, tail = block.rpartition("</style>")
    return head + extra + "\n" + sep + tail


APPLE_DESIGN_SYSTEM_CSS = _append_css(APPLE_DESIGN_SYSTEM_CSS, _COMPACT_UX_CSS)
FEED_CARD_CSS = _append_css(FEED_CARD_CSS, _COMPACT_UX_CSS)


_AUTH_LIGHT_CSS = """
    /* ===== Login: single blue accent, flat and light (Apple style) ===== */
    [data-testid="stAppViewContainer"], .main { background: #F5F5F7 !important; }
    div[data-testid="stForm"] {
        background: #FFFFFF !important;
        -webkit-backdrop-filter: none !important; backdrop-filter: none !important;
        border: 1px solid rgba(0, 0, 0, 0.06) !important;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04), 0 8px 24px rgba(0, 0, 0, 0.05) !important;
    }
    .auth-header__icon-ring { background: #E8F1FC; box-shadow: none; }
    .auth-header__icon-ring svg path { fill: #0066CC; fill-opacity: 1; }
    div[data-testid="stForm"] div[data-baseweb="input"] > div { background: #F5F5F7 !important; border-color: transparent !important; }
    div[data-testid="stForm"] div[data-baseweb="input"] > div:focus-within { background: #FFFFFF !important; border-color: #0066CC !important; box-shadow: 0 0 0 3px rgba(0, 102, 204, 0.14) !important; }
    div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button { background: #0066CC !important; box-shadow: none !important; }
    div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button:hover { background: #0071E3 !important; filter: none !important; box-shadow: none !important; transform: none !important; }
    div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button:active { background: #0058B0 !important; filter: none !important; box-shadow: none !important; }
"""
AUTH_CSS = _append_css(AUTH_CSS, _AUTH_LIGHT_CSS)


_APPLE_POLISH_CSS = """
    /* ===== Apple-grade polish: neutral greys, flat fills, hairlines, one blue ===== */
    :root {
        --bg: #F5F5F7; --surface: #FFFFFF; --surface-muted: #F5F5F7;
        --label: #1D1D1F; --label-2: #424245; --label-3: #6E6E73;
        --separator: rgba(0, 0, 0, 0.08); --separator-strong: rgba(0, 0, 0, 0.14);
        --shadow-1: 0 1px 2px rgba(0, 0, 0, 0.04);
        --shadow-2: 0 4px 16px rgba(0, 0, 0, 0.06);
        --fill: rgba(0, 0, 0, 0.045); --fill-hover: rgba(0, 0, 0, 0.07);
    }
    [data-testid="stAppViewContainer"], .main { background-color: #F5F5F7 !important; }
    .ico { vertical-align: -2px; flex-shrink: 0; }

    /* Brand */
    .brand-tile { display: inline-flex; align-items: center; justify-content: center; width: 24px; height: 24px; border-radius: 7px; background: var(--tint-soft); color: var(--tint); flex-shrink: 0; }
    .brand-name { font-weight: 650; font-size: 0.95rem; letter-spacing: -0.02em; color: var(--label); line-height: 1; }
    .live-status-inline { text-transform: none !important; letter-spacing: 0.01em !important; font-weight: 600 !important; }

    /* Status bar: white hairline instead of tinted gradient */
    .sync-status-bar { background: #FFFFFF; border: 1px solid var(--separator); border-radius: 12px; }
    .sync-status-pill--idle { background: var(--fill); }
    .sync-status-pill .ico, .pill .ico, .sync-fresh-chip .ico, .filter-pill-removable .ico, .counter-badge .ico { margin-right: 1px; }

    /* Inputs, selects, popovers, secondary buttons: soft fill, no outline */
    div[data-testid="stSelectbox"] div:has(> input),
    div[data-testid="stTextInput"]:not(div[data-testid="stForm"] *) div[data-baseweb="input"],
    div[data-baseweb="input"] > div:first-child,
    div[data-baseweb="select"] > div:first-child {
        background-color: var(--fill) !important; border: 1px solid transparent !important;
        box-shadow: none !important; border-radius: 10px !important;
        min-height: 36px !important; height: 36px !important; max-height: 36px !important;
    }
    div[data-testid="stSelectbox"] div:has(> input):hover,
    div[data-baseweb="select"] > div:first-child:hover { background-color: var(--fill-hover) !important; border-color: transparent !important; }
    [data-testid="stPopover"] > button, [data-testid="stPopover"] > div > button, [data-testid="stPopover"] > div > div > button,
    .stButton button[kind="secondary"], div[data-testid="stDownloadButton"] > button, div[data-testid="stLinkButton"] > a {
        background: var(--fill) !important; border: 1px solid transparent !important; box-shadow: none !important;
        border-radius: 10px !important; min-height: 36px !important; height: 36px !important; color: var(--label) !important;
    }
    [data-testid="stPopover"] > button:hover, [data-testid="stPopover"] > div > button:hover,
    .stButton button[kind="secondary"]:hover, div[data-testid="stDownloadButton"] > button:hover, div[data-testid="stLinkButton"] > a:hover {
        background: var(--fill-hover) !important; border-color: transparent !important; box-shadow: none !important;
    }
    .stButton button[kind="primary"] { background: #0066CC !important; border: none !important; box-shadow: none !important; border-radius: 10px !important; }
    .stButton button[kind="primary"]:hover { background: #0071E3 !important; }
    .stButton > button:focus-visible, [data-testid="stPopover"] > button, [data-testid="stPopover"] > div > button, [data-testid="stPopover"] > div > div > button:focus-visible { outline: 2px solid rgba(0, 102, 204, 0.5) !important; outline-offset: 2px !important; }

    /* Cards, metrics, expanders: white surface, hairline, light shadow */
    div[data-testid="stMetric"], div[data-testid="stExpander"], div[data-testid="stForm"], .health-card, .acct-card-rich {
        border: 1px solid var(--separator) !important; border-radius: 14px !important; box-shadow: var(--shadow-1) !important; background: #FFFFFF !important;
    }
    div[data-testid="stExpander"] summary { font-weight: 600; font-size: 0.88rem; }
    div[data-testid="stMetricLabel"], div[data-testid="stMetricLabel"] * { color: var(--label-3) !important; font-weight: 500 !important; font-size: 0.74rem !important; }

    /* Tabs: quiet underline in the one blue */
    div[data-testid="stTabs"] button[role="tab"] { font-size: 0.86rem; font-weight: 600; color: var(--label-3); }
    div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] { color: var(--tint); }
    div[data-testid="stTabs"] [data-baseweb="tab-highlight"] { background-color: var(--tint) !important; }
    div[data-testid="stTabs"] [data-baseweb="tab-border"] { background-color: var(--separator) !important; }

    /* Empty state: line icon in a soft tile */
    .empty-state__icon { display: inline-flex; align-items: center; justify-content: center; width: 52px; height: 52px; border-radius: 16px; background: var(--fill); color: var(--label-3); font-size: 1.5rem; margin-bottom: 8px; }
    .empty-state__title { font-weight: 650; color: var(--label); }
    .empty-state__body { color: var(--label-3); font-size: 0.84rem; }

    /* Headings: quieter, tighter */
    h5, .stMarkdown h5 { font-size: 0.8rem !important; font-weight: 650 !important; letter-spacing: 0.02em !important; text-transform: none; color: var(--label-3) !important; margin-bottom: 6px !important; }
    .onboarding-card__title { font-weight: 650; }
    .stCaption, div[data-testid="stCaptionContainer"] { color: var(--label-3) !important; font-size: 0.76rem !important; }
"""
APPLE_DESIGN_SYSTEM_CSS = _append_css(APPLE_DESIGN_SYSTEM_CSS, _APPLE_POLISH_CSS)
FEED_CARD_CSS = _append_css(FEED_CARD_CSS, _APPLE_POLISH_CSS)


_WORKSPACE_POLISH_CSS = """
    /* ===== Workspaces: Export, Health, X, Directory ===== */
    .page-header { margin: 0 0 8px 0; }
    .page-header__title { font-size: 1.35rem !important; letter-spacing: -0.02em !important; }
    .page-header__subtitle { font-size: 0.76rem; color: var(--label-3); margin-top: 2px; }

    .health-card { padding: 11px 14px 10px 16px; margin-bottom: 6px; }
    .health-card__head { margin-bottom: 4px; }
    .health-card__name { font-size: 0.95rem; }
    .health-card__meta { display: inline-flex; align-items: center; gap: 4px; font-size: 0.74rem; color: var(--label-3); }
    .health-card__stats { gap: 6px; font-size: 0.78rem; color: var(--label-3); margin: 4px 0; }
    .health-card__latest { display: flex; align-items: center; gap: 8px; padding: 6px 10px; margin-top: 4px; font-size: 0.8rem; background: var(--fill); }
    .health-card__latest > a:first-child { flex: 1 1 0; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--label-2); text-decoration: none; }
    .health-card__latest .hc-link { flex-shrink: 0; display: inline-flex; color: var(--label-3); }
    .hc-actions-anchor { display: none; }

    @media (max-width: 640px) {
        /* Metric rows: two per line instead of one tall stack */
        div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"] [data-testid="stMetric"]) { flex-wrap: wrap !important; gap: 8px !important; }
        div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"] [data-testid="stMetric"]) > div[data-testid="stColumn"] { flex: 1 1 calc(50% - 8px) !important; min-width: 0 !important; width: auto !important; }
        /* 6-KPI rows (Health): three per line */
        div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(6)):has([data-testid="stMetric"]) > div[data-testid="stColumn"] { flex: 1 1 calc(33.33% - 8px) !important; }
        div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(6)):has([data-testid="stMetric"]) div[data-testid="stMetricValue"],
        div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]:nth-child(6)):has([data-testid="stMetric"]) div[data-testid="stMetricValue"] * { font-size: 1.05rem !important; }
        div[data-testid="stElementContainer"]:has(> .hc-actions-anchor), div[data-testid="stElementContainer"]:has(.hc-actions-anchor) { display: none !important; }
        div[data-testid="stMetric"] { padding: 10px 12px !important; }
        div[data-testid="stMetricValue"], div[data-testid="stMetricValue"] * { font-size: 1.25rem !important; }

        /* Per-source actions: one icon row */
        div[data-testid="stHorizontalBlock"]:has(.hc-actions-anchor):has(.hc-actions-anchor):has(.hc-actions-anchor):has(.hc-actions-anchor):has(.hc-actions-anchor) { flex-wrap: nowrap !important; gap: 6px !important; align-items: center !important; }
        div[data-testid="stHorizontalBlock"]:has(.hc-actions-anchor):has(.hc-actions-anchor):has(.hc-actions-anchor):has(.hc-actions-anchor):has(.hc-actions-anchor) > div[data-testid="stColumn"] { flex: 1 1 0 !important; min-width: 0 !important; width: auto !important; }
        div[data-testid="stHorizontalBlock"]:has(.hc-actions-anchor):has(.hc-actions-anchor):has(.hc-actions-anchor):has(.hc-actions-anchor):has(.hc-actions-anchor) .stButton > button [data-testid="stMarkdownContainer"] { display: none !important; }
        div[data-testid="stHorizontalBlock"]:has(.hc-actions-anchor):has(.hc-actions-anchor):has(.hc-actions-anchor):has(.hc-actions-anchor):has(.hc-actions-anchor) .stButton > button { padding: 0 !important; }
        div[data-testid="stHorizontalBlock"]:has(.hc-actions-anchor):has(.hc-actions-anchor):has(.hc-actions-anchor):has(.hc-actions-anchor):has(.hc-actions-anchor) div[data-testid="stExpander"] summary { padding: 6px 8px; }
    }
"""
APPLE_DESIGN_SYSTEM_CSS = _append_css(APPLE_DESIGN_SYSTEM_CSS, _WORKSPACE_POLISH_CSS)


_NOLINES_CSS = """
    /* ===== No decorative lines: no side strips, dividers, underlines or outlines ===== */
    .feed-card-stripe, .health-card::before { display: none !important; }
    .feed-card-wrap { border-color: transparent !important; box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04), 0 2px 10px rgba(0, 0, 0, 0.04) !important; }
    .feed-card-footer, .x-engagement-bar { border-top: none !important; }
    .fulltext-reader-box { border: none !important; }
    .fulltext-reader-box__meta { border-bottom: none !important; }
    .sync-status-bar, .empty-state, .wa-already-sent-notice, .onboarding-card, .search-sidebar { border: none !important; }
    .empty-state { background: var(--fill) !important; }
    div[data-testid="stMetric"], div[data-testid="stExpander"], div[data-testid="stForm"], .health-card, .acct-card-rich, .admin-card {
        border-color: transparent !important;
    }
    div[data-testid="stDialog"] [data-testid="stDialogContent"] { border: none !important; }
    .pill, .portal-tag, .indian-portal-tag, .cat-badge, .conf-review-badge, .sec-tag-chip, .x-metric-item, .x-sentiment-badge, .status-pill { border-color: transparent !important; }
    hr, div[data-testid="stDivider"] { display: none !important; }
    div[data-testid="stTextInputRootElement"]:not(#a), div[data-testid="stTextAreaRootElement"]:not(#a), div[data-testid="stNumberInputContainer"]:not(#a) { background: var(--fill) !important; border: none !important; border-radius: 10px !important; box-shadow: none !important; }
    div[data-testid="stForm"] div[data-testid="stTextInputRootElement"]:not(#a) { background: #F5F5F7 !important; border-radius: 14px !important; min-height: 50px; }
    div[data-testid="stForm"] div[data-testid="stTextInputRootElement"]:focus-within { background: #FFFFFF !important; box-shadow: 0 0 0 3px rgba(0, 102, 204, 0.18) !important; }
    div[data-testid="stTabs"] [data-baseweb="tab-border"], div[data-testid="stTabs"] [data-baseweb="tab-highlight"] { display: none !important; }
    div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] { background: var(--tint-soft); border-radius: 999px; }
    div[data-testid="stTabs"] button[role="tab"] { border-radius: 999px; }
    div[data-testid="stTab"] .react-aria-SelectionIndicator { display: none !important; }
    div[data-testid="stTabs"] [role="tablist"]::after, div[data-testid="stTabs"] [role="tablist"]::before { display: none !important; content: none !important; }
    div[data-testid="stExpander"], div[data-testid="stExpander"] details, div[data-testid="stExpanderDetails"] { border: none !important; }
    div[data-testid="stTabs"] > div:first-of-type, div[data-testid="stTabs"] [role="tablist"] { border-bottom: none !important; box-shadow: none !important; }
    div[data-testid="stTab"] { border-radius: 999px !important; color: var(--label-3); padding-left: 12px !important; padding-right: 12px !important; }
    div[data-testid="stTab"][aria-selected="true"] { background: var(--tint-soft) !important; color: var(--tint) !important; }
    div[data-testid="stTab"] p { color: inherit !important; font-weight: 600; font-size: 0.86rem; }

    /* Header row + nav: filled pill for the active item instead of an underline */
    div[data-testid="stHorizontalBlock"]:has(.editorial-brand-anchor) { border-bottom: none !important; }
    div[data-testid="stButtonGroup"] button, div[data-testid="stButtonGroup"] button[data-variant="segmented_control"], div[data-baseweb="button-group"] button {
        border-bottom: none !important; border-radius: 999px !important; height: 32px !important; min-height: 32px !important;
        padding: 0 12px !important; color: var(--label-3) !important;
    }
    div[data-testid="stButtonGroup"] button:hover:not([data-selected]), div[data-testid="stButtonGroup"] button[data-variant="segmented_control"]:hover:not([data-selected]), div[data-baseweb="button-group"] button:hover {
        background: var(--fill) !important; border-bottom: none !important; border-radius: 999px !important; color: var(--label) !important;
    }
    div[data-testid="stButtonGroup"] button[data-selected], div[data-testid="stButtonGroup"] button[data-variant="segmented_control"][data-selected],
    div[data-testid="stButtonGroup"] button[aria-checked="true"], div[data-baseweb="button-group"] button[aria-checked="true"] {
        background: var(--tint-soft) !important; color: var(--tint) !important; border-bottom: none !important; border-radius: 999px !important;
    }
    div[data-testid="stHorizontalBlock"]:has(.theme-row-anchor) div[data-testid="stButtonGroup"] button { padding: 0 9px !important; min-width: 0 !important; }
    div[data-testid="stElementContainer"]:has(.theme-row-anchor) { display: none !important; }
    @media (max-width: 640px) {
        div[data-testid="stHorizontalBlock"]:has(.theme-row-anchor):has(.theme-row-anchor):has(.theme-row-anchor):has(.theme-row-anchor):has(.theme-row-anchor) { flex-direction: row !important; flex-wrap: wrap !important; gap: 2px 8px !important; align-items: center !important; }
        div[data-testid="stHorizontalBlock"]:has(.theme-row-anchor):has(.theme-row-anchor):has(.theme-row-anchor):has(.theme-row-anchor):has(.theme-row-anchor) > div[data-testid="stColumn"]:nth-child(1) { flex: 1 1 0 !important; min-width: 0 !important; width: auto !important; }
        div[data-testid="stHorizontalBlock"]:has(.theme-row-anchor):has(.theme-row-anchor):has(.theme-row-anchor):has(.theme-row-anchor):has(.theme-row-anchor) > div[data-testid="stColumn"]:nth-child(2) { flex: 0 0 auto !important; min-width: 0 !important; width: auto !important; }
        div[data-testid="stHorizontalBlock"]:has(.theme-row-anchor):has(.theme-row-anchor):has(.theme-row-anchor):has(.theme-row-anchor):has(.theme-row-anchor) > div[data-testid="stColumn"]:nth-child(3) { flex: 1 1 100% !important; min-width: 0 !important; width: 100% !important; }
    }
"""
APPLE_DESIGN_SYSTEM_CSS = _append_css(APPLE_DESIGN_SYSTEM_CSS, _NOLINES_CSS)
FEED_CARD_CSS = _append_css(FEED_CARD_CSS, _NOLINES_CSS)


_DARK_CSS_BODY = """
    :root {
        color-scheme: dark;
        --bg: #000000; --surface: #1C1C1E; --surface-muted: #2C2C2E;
        --label: #F5F5F7; --label-2: #D1D1D6; --label-3: #A1A1AA;
        --separator: rgba(255, 255, 255, 0.10); --separator-strong: rgba(255, 255, 255, 0.16);
        --tint: #4DA3FF; --tint-hover: #74B8FF; --tint-soft: rgba(77, 163, 255, 0.18); --link: #64B5FF;
        --green: #32D74B; --green-soft: rgba(50, 215, 75, 0.16);
        --amber: #FFD60A; --amber-soft: rgba(255, 214, 10, 0.16);
        --red: #FF7A7A; --red-soft: rgba(255, 99, 99, 0.18);
        --fill: rgba(255, 255, 255, 0.09); --fill-hover: rgba(255, 255, 255, 0.14);
        --shadow-1: 0 1px 2px rgba(0, 0, 0, 0.6); --shadow-2: 0 8px 24px rgba(0, 0, 0, 0.6);
    }
    html, body, .stApp, [data-testid="stAppViewContainer"], .main, [data-testid="stMain"] { background: #000000 !important; color: #F5F5F7 !important; }
    [data-testid="stHeader"], header[data-testid="stHeader"] { background: transparent !important; }
    [data-testid="stHeader"] * { color: #D1D1D6 !important; }
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, .stApp p, .stApp li, .stApp label, .stApp summary,
    .stApp [data-testid="stWidgetLabel"] *, .stApp [data-testid="stMarkdownContainer"] { color: #F5F5F7; }
    .stApp a { color: #64B5FF; }
    .stApp [data-testid="stCaptionContainer"], .stApp .stCaption { color: #A1A1AA !important; }
    h5, .stMarkdown h5 { color: #A1A1AA !important; }
    .page-header__title, .brand-name, .apple-card-title a, .health-card__name, .empty-state__title { color: #F5F5F7 !important; }
    .page-header__subtitle, .empty-state__body, .health-card__meta, .health-card__stats, .time-badge, .lang-label { color: #A1A1AA !important; }
    .apple-card-summary, .x-post-text, .reader-para, .fulltext-reader-box__body { color: #D1D1D6 !important; }
    .apple-card-native-title { color: #A1A1AA !important; }

    /* Surfaces */
    .feed-card-wrap, .apple-news-card, .health-card, .acct-card-rich, .admin-card, .sync-status-bar, .fulltext-reader-box, .onboarding-card, .search-sidebar,
    div[data-testid="stMetric"], div[data-testid="stExpander"], div[data-testid="stForm"], div[data-testid="stVerticalBlockBorderWrapper"]:has(.feed-card-anchor) {
        background: #1C1C1E !important; box-shadow: none !important; border-color: transparent !important;
    }
    .apple-news-card, .x-post-card { background: transparent !important; }
    .feed-card-wrap:hover { box-shadow: none !important; border-color: transparent !important; }
    .health-card__latest, .empty-state, .sync-status-pill--idle { background: rgba(255, 255, 255, 0.07) !important; }
    .health-card__latest > a:first-child { color: #D1D1D6 !important; }
    .fulltext-reader-box__title { color: #F5F5F7 !important; }
    .fulltext-reader-box__meta { color: #A1A1AA !important; }
    .empty-state__icon { background: rgba(255, 255, 255, 0.09) !important; color: #A1A1AA !important; }

    /* Chips, pills, badges */
    .pill, .portal-tag, .indian-portal-tag, .cat-badge, .sec-tag-chip, .x-metric-item, .status-pill, .x-sentiment-badge, .sec-tag-more {
        background: rgba(255, 255, 255, 0.10) !important; color: #E5E5EA !important; border-color: transparent !important;
    }
    .indian-portal-tag { background: rgba(255, 159, 10, 0.18) !important; color: #FFB340 !important; }
    .cat-badge--internal { background: rgba(124, 122, 255, 0.22) !important; color: #B8B6FF !important; }
    .cat-badge--external { background: rgba(191, 90, 242, 0.22) !important; color: #DDA6FF !important; }
    .cat-badge--economy { background: rgba(50, 215, 75, 0.18) !important; color: #6BE585 !important; }
    .cat-badge--international { background: rgba(124, 122, 255, 0.22) !important; color: #B8B6FF !important; }
    .cat-badge--india { background: rgba(255, 159, 10, 0.18) !important; color: #FFB340 !important; }
    .cat-badge--china { background: rgba(255, 99, 99, 0.2) !important; color: #FF9B9B !important; }
    .cat-badge--pakistan { background: rgba(50, 215, 75, 0.18) !important; color: #6BE585 !important; }
    .cat-badge--bangladesh { background: rgba(100, 210, 255, 0.18) !important; color: #7DD8FF !important; }
    .conf-review-badge, .pill--warn { background: rgba(255, 214, 10, 0.18) !important; color: #FFD60A !important; }
    .pill--success, .status-pill--ok, .sync-status-pill--done { background: rgba(50, 215, 75, 0.18) !important; color: #6BE585 !important; }
    .status-pill--warn, .sync-status-pill--running, .sync-status-pill--waiting { background: rgba(255, 214, 10, 0.18) !important; color: #FFD60A !important; animation: none !important; }
    .status-pill--fail, .sync-status-pill--error { background: rgba(255, 99, 99, 0.2) !important; color: #FF9B9B !important; }
    .pill--tint, .filter-pill-removable { background: rgba(77, 163, 255, 0.18) !important; color: #7DBBFF !important; }
    .sync-status-pill--idle { color: #A1A1AA !important; }
    .sync-fresh-chip { color: #A1A1AA !important; }
    .brand-tile { background: rgba(77, 163, 255, 0.18); color: #7DBBFF; }
    .hl-av--in { background: rgba(255, 159, 10, 0.2) !important; color: #FFB340 !important; }
    .hl-src { color: #E5E5EA !important; }
    .live-status-inline { background: rgba(50, 215, 75, 0.18) !important; color: #6BE585 !important; }
    .wa-already-sent-notice { background: rgba(50, 215, 75, 0.14) !important; color: #6BE585 !important; }
    .extraction-badge, .share-draft-pill { background: rgba(255, 255, 255, 0.10) !important; color: #E5E5EA !important; border-color: transparent !important; }
    .extraction-badge--full, .share-draft-pill--saved, .share-draft-pill--sent { background: rgba(50, 215, 75, 0.18) !important; color: #6BE585 !important; }
    .extraction-badge--partial, .share-draft-pill--unsaved { background: rgba(255, 214, 10, 0.18) !important; color: #FFD60A !important; }

    /* Inputs, selects, popovers, buttons */
    div[data-testid="stSelectbox"] div:has(> input), div[data-testid="stTextInput"] div[data-baseweb="input"], div[data-baseweb="input"] > div:first-child,
    div[data-baseweb="select"] > div:first-child, div[data-baseweb="textarea"], div[data-testid="stForm"] div[data-baseweb="input"] > div {
        background-color: rgba(255, 255, 255, 0.10) !important; color: #F5F5F7 !important; border-color: transparent !important;
    }
    div[data-baseweb="select"] *, div[data-baseweb="input"] input, div[data-baseweb="textarea"] textarea, div[data-testid="stSelectbox"] * { color: #F5F5F7 !important; }
    div[data-baseweb="input"] input::placeholder, div[data-baseweb="textarea"] textarea::placeholder { color: #8E8E93 !important; }
    div[data-baseweb="select"] svg, div[data-testid="stSelectbox"] svg { fill: #A1A1AA !important; color: #A1A1AA !important; }
    [data-baseweb="popover"] > div, [data-baseweb="menu"], ul[role="listbox"], [data-testid="stPopoverBody"], div[data-baseweb="popover"] div[data-baseweb="menu"] {
        background: #2C2C2E !important; color: #F5F5F7 !important; border: none !important; box-shadow: 0 12px 32px rgba(0, 0, 0, 0.6) !important;
    }
    [data-baseweb="menu"] li, ul[role="listbox"] li, [data-baseweb="menu"] * { color: #F5F5F7 !important; background: transparent !important; }
    [data-baseweb="menu"] li:hover, ul[role="listbox"] li:hover, ul[role="listbox"] li[aria-selected="true"] { background: rgba(255, 255, 255, 0.12) !important; }
    [data-testid="stPopover"] > button, [data-testid="stPopover"] > div > button, .stButton > button[kind="secondary"], div[data-testid="stDownloadButton"] > button, div[data-testid="stLinkButton"] > a,
    div[data-testid="stDialog"] .stButton > button {
        background: rgba(255, 255, 255, 0.10) !important; color: #F5F5F7 !important; border-color: transparent !important;
    }
    [data-testid="stPopover"] button *, .stButton > button[kind="secondary"] *, div[data-testid="stDownloadButton"] button *, div[data-testid="stLinkButton"] a * { color: #F5F5F7 !important; }
    [data-testid="stPopover"] > button:hover, .stButton > button[kind="secondary"]:hover, div[data-testid="stDownloadButton"] > button:hover, div[data-testid="stLinkButton"] > a:hover { background: rgba(255, 255, 255, 0.16) !important; }
    .stButton > button[kind="primary"], div[data-testid="stDialog"] .stButton > button[kind="primary"] { background: #0A84FF !important; color: #FFFFFF !important; }
    .stButton > button[kind="primary"] * { color: #FFFFFF !important; }
    .stButton:not(#a) button:not(#a):not([kind="primary"]), [data-testid="stPopover"]:not(#a) > button:not(#a), [data-testid="stPopover"]:not(#a) > div > button:not(#a),
    div[data-testid="stHorizontalBlock"]:not(#a) .stButton button:not([kind="primary"]), div[data-testid="stHorizontalBlock"]:not(#a) [data-testid="stPopover"] button {
        background: rgba(255, 255, 255, 0.10) !important; color: #F5F5F7 !important; border-color: transparent !important;
    }
    .stButton:not(#a) button:not(#a):not([kind="primary"]) *, [data-testid="stPopover"]:not(#a) button * { color: #F5F5F7 !important; }
    .stButton > button[disabled] { opacity: 0.45 !important; }
    div[data-testid="stToggle"] label, div[data-testid="stCheckbox"] label { color: #F5F5F7 !important; }

    /* Dialogs */
    div[data-testid="stDialog"] [data-testid="stDialogContent"], div[data-testid="stDialog"] div[role="dialog"] { background: #1C1C1E !important; color: #F5F5F7 !important; box-shadow: 0 24px 64px rgba(0, 0, 0, 0.7) !important; }
    div[data-testid="stDialog"] { background: rgba(0, 0, 0, 0.6) !important; }
    div[data-testid="stDialog"] div:has(> [role="dialog"]), div[data-testid="stDialog"] [role="dialog"] { background: #1C1C1E !important; color: #F5F5F7 !important; }
    div[data-testid="stDialog"] h1, div[data-testid="stDialog"] h2, div[data-testid="stDialog"] [data-testid="stDialogContent"] * { color: #F5F5F7; }
    div[data-testid="stDialog"] svg { fill: currentColor; }
    div[data-testid="stDialog"] button[aria-label="Close"], div[data-testid="stDialog"] button[aria-label="Close"] * { color: #F5F5F7 !important; background: transparent !important; }
    div[data-testid="stDialog"] .stButton > button[kind="primary"] { border: none !important; }
    div[data-testid="stDialog"] div[data-testid="stHorizontalBlock"]:has(> div[data-testid="stColumn"]) { background-color: transparent; }
    .wa-dest-label { color: #A1A1AA !important; }
    [data-testid="stPopoverBody"] [data-testid="stWidgetLabel"] *, div[data-testid="stDialog"] [data-testid="stWidgetLabel"] * { color: #D1D1D6 !important; }
    [data-testid="stPopoverBody"] [data-testid="stMarkdownContainer"] *, [data-testid="stPopoverBody"] p, [data-testid="stPopoverBody"] label { color: #F5F5F7; }
    [data-testid="stPopoverBody"] [data-testid="stCaptionContainer"], [data-testid="stPopoverBody"] [data-testid="stCaptionContainer"] * { color: #A1A1AA !important; }
    div[data-testid="stDateInputField"]:not(#a), div[data-testid="stTimeInputTimeDisplay"]:not(#a), div[data-testid="stDateInput"] [data-baseweb]:not(#a), div[data-testid="stTimeInput"] [data-baseweb]:not(#a) { background: #3A3A3C !important; color: #F5F5F7 !important; border: none !important; }
    div[data-testid="stDateInputField"] *, div[data-testid="stTimeInputTimeDisplay"] * { color: #F5F5F7 !important; }
    div[data-testid="stDateInput"] svg, div[data-testid="stTimeInput"] svg { fill: #A1A1AA !important; color: #A1A1AA !important; }
    div[data-testid="stToggle"] [role="switch"][aria-checked="true"], div[data-testid="stToggle"] input:checked + div { background-color: #0A84FF !important; }
    div[data-testid="stTextInputRootElement"] [data-testid="stIconMaterial"], div[data-testid="stTextInputRootElement"] span[role="img"] { color: #A1A1AA !important; }
    div[data-testid="stTextInputRootElement"] input::placeholder { font-weight: 400 !important; color: #8E8E93 !important; }
    div[data-testid="stDialog"] div[data-testid="stLayoutWrapper"]:has(> div[data-testid="stHorizontalBlock"] .stButton),
    div[data-testid="stDialog"] div[data-testid="stLayoutWrapper"]:has(> div[data-testid="stHorizontalBlock"] iframe) { background: #1C1C1E !important; border-top-color: transparent !important; }

    /* Nav, tabs, expanders, metrics */
    div[data-testid="stButtonGroup"] button, div[data-testid="stButtonGroup"] button[data-variant="segmented_control"] { color: #A1A1AA !important; }
    div[data-testid="stButtonGroup"] button *, div[data-testid="stButtonGroup"] button[data-variant="segmented_control"] * { color: inherit !important; }
    div[data-testid="stButtonGroup"] button:hover:not([data-selected]) { color: #F5F5F7 !important; background: rgba(255, 255, 255, 0.09) !important; }
    div[data-testid="stButtonGroup"] button[data-selected], div[data-testid="stButtonGroup"] button[aria-checked="true"] { color: #7DBBFF !important; background: rgba(77, 163, 255, 0.2) !important; }
    div[data-testid="stTabs"] button[role="tab"] { color: #A1A1AA !important; }
    div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] { color: #7DBBFF !important; background: rgba(77, 163, 255, 0.2) !important; }
    div[data-testid="stExpander"] summary, div[data-testid="stExpander"] summary * { color: #F5F5F7 !important; }
    div[data-testid="stExpander"] details { background: transparent !important; border: none !important; }
    div[data-testid="stMetricLabel"], div[data-testid="stMetricLabel"] * { color: #A1A1AA !important; }
    div[data-testid="stMetricValue"], div[data-testid="stMetricValue"] * { color: #F5F5F7 !important; }
    div[data-testid="stMetricDelta"] * { filter: brightness(1.25); }

    div[data-testid="stTab"] { color: #A1A1AA !important; }
    div[data-testid="stTab"][aria-selected="true"] { color: #7DBBFF !important; background: rgba(77, 163, 255, 0.2) !important; }

    /* Alerts: tinted dark panels with light text */
    div[data-testid="stAlert"], div[data-testid="stAlert"] * { color: #F5F5F7 !important; }
    div[data-testid="stAlert"], div[data-testid="stAlertContainer"] { background-color: rgba(255, 255, 255, 0.09) !important; }
    div[data-testid="stAlertContainer"] { background-color: transparent !important; }
    div[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) { background-color: rgba(255, 214, 10, 0.15) !important; }
    div[data-testid="stAlert"]:has([data-testid="stAlertContentInfo"]) { background-color: rgba(77, 163, 255, 0.17) !important; }
    div[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]) { background-color: rgba(50, 215, 75, 0.15) !important; }
    div[data-testid="stAlert"]:has([data-testid="stAlertContentError"]) { background-color: rgba(255, 99, 99, 0.17) !important; }

    /* Tables / editors are canvas-based: tone them down rather than blinding white */
    div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] { filter: invert(0.9) hue-rotate(180deg); border-radius: 12px; }

    /* Feed component (inside its iframe) */
    html, body { color: #F5F5F7 !important; }
    .feed-btn { background: rgba(255, 255, 255, 0.11) !important; color: #F5F5F7 !important; border-color: transparent !important; }
    .feed-btn:hover { background: rgba(255, 255, 255, 0.17) !important; }
    .feed-btn--primary { background: #0A84FF !important; color: #FFFFFF !important; }
    .feed-btn--primary:hover { background: #3396FF !important; }
    .x-author-name { color: #F5F5F7 !important; }
    .x-author-handle { color: #A1A1AA !important; }
    .x-type-badge { color: #7DBBFF !important; }
    .x-post-text b { color: #7DBBFF !important; }
    .x-sentiment-positive { background: rgba(50, 215, 75, 0.18) !important; color: #6BE585 !important; }
    .x-sentiment-alert { background: rgba(255, 99, 99, 0.2) !important; color: #FF9B9B !important; }
    #scroll-sentinel, .feed-end-note { color: #A1A1AA !important; }

    /* Login */
    div[data-testid="stForm"] { background: #1C1C1E !important; }
    .auth-header__icon-ring { background: rgba(77, 163, 255, 0.18) !important; }
    .auth-header__icon-ring { color: #7DBBFF !important; }
    .auth-header__icon-ring svg path { fill: none !important; stroke: currentColor !important; }
    .auth-header__title { color: #F5F5F7 !important; }
    .auth-header__subtitle, .auth-footer { color: #A1A1AA !important; }
    div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"] { background: #0A84FF !important; color: #FFFFFF !important; border: none !important; }
    div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"] * { color: #FFFFFF !important; }
    div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button[kind="secondaryFormSubmit"] { background: rgba(255, 255, 255, 0.12) !important; color: #F5F5F7 !important; border: none !important; }
    div[data-testid="stForm"] div[data-testid="stFormSubmitButton"] button[kind="secondaryFormSubmit"] * { color: #F5F5F7 !important; }
    div[data-testid="stForm"] div[data-baseweb="input"]:not(#a) { background: #2C2C2E !important; border: none !important; }
    div[data-testid="stForm"] div[data-baseweb="input"]:not(#a) > div:not(#a), div[data-testid="stForm"] div[data-baseweb="base-input"]:not(#a), div[data-testid="stForm"] input:not(#a) { background: transparent !important; color: #F5F5F7 !important; border: none !important; }
    div[data-testid="stForm"] input:not(#a)::placeholder { color: #8E8E93 !important; opacity: 1 !important; }
    div[data-testid="stTextInputRootElement"]:not(#a), div[data-testid="stTextAreaRootElement"]:not(#a), div[data-testid="stNumberInputContainer"]:not(#a) { background: #2C2C2E !important; border: none !important; }
    div[data-testid="stForm"] div[data-testid="stTextInputRootElement"]:not(#a) { background: #2C2C2E !important; }
    div[data-testid="stForm"] div[data-testid="stTextInputRootElement"]:not(#a):focus-within { background: #3A3A3C !important; box-shadow: 0 0 0 3px rgba(77, 163, 255, 0.35) !important; }
    div[data-testid="stTextInputRootElement"] input, div[data-testid="stTextAreaRootElement"] textarea { color: #F5F5F7 !important; }
    div[data-testid="stTextInputRootElement"] button, div[data-testid="stTextInputRootElement"] svg { color: #A1A1AA !important; fill: #A1A1AA !important; background: transparent !important; }
    div[data-testid="stForm"] div[data-baseweb="input"] svg { fill: #A1A1AA !important; color: #A1A1AA !important; }
"""


def theme_override_css(mode: str) -> str:
    """Returns the dark-mode override stylesheet for 'dark', an OS-driven one for 'auto', or '' for 'light'."""
    body = _DARK_MIN if "_DARK_MIN" in globals() else _DARK_CSS_BODY
    if mode == "dark":
        return "<style>" + body + "</style>"
    if mode == "light":
        return ""
    return "<style>@media (prefers-color-scheme: dark) {" + body + "}</style>"


_HEADLINE_UX_CSS = """
    /* ===== Headline-first cards, soft buttons, bottom tab bar ===== */
    .hl-card { display: flex; flex-direction: column; gap: 7px; min-width: 0; }
    .hl-meta { display: flex; align-items: center; gap: 7px; min-width: 0; font-size: 0.74rem; color: var(--label-3); }
    .hl-av { width: 22px; height: 22px; border-radius: 7px; background: var(--fill); color: var(--label-2); display: inline-flex; align-items: center; justify-content: center; font-size: 0.6rem; font-weight: 700; flex: none; text-transform: uppercase; }
    .hl-av--in { background: rgba(244, 125, 32, 0.14); color: #C2410C; }
    .hl-src { color: var(--label-2); font-weight: 650; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .hl-dot { flex: none; }
    .hl-time { flex: none; white-space: nowrap; }
    .hl-sp { flex: 1 1 0; min-width: 0; }
    .hl-chip { display: inline-flex; align-items: center; gap: 4px; flex: none; padding: 2px 8px; border-radius: 999px; background: var(--fill); color: var(--label-2); font-size: 0.7rem; font-weight: 650; }
    .hl-chip--warn { background: var(--amber-soft); color: var(--amber); }
    .hl-chip--ok { background: var(--green-soft); color: var(--green); padding: 2px 6px; }
    .hl-title { margin: 0 !important; padding: 0 !important; font-size: 1.02rem !important; font-weight: 650 !important; line-height: 1.4 !important; letter-spacing: -0.012em !important; text-wrap: pretty; }
    .hl-title a { color: var(--label) !important; text-decoration: none !important; }
    .hl-title a:hover { color: var(--link) !important; }
    .feed-card-wrap { padding: 14px 16px 10px 16px !important; }
    .feed-card-wrap .feed-card-footer { margin-top: 8px; padding-top: 0; justify-content: flex-end; }
    .feed-card-wrap .feed-btn { background: var(--fill) !important; color: var(--label-2) !important; }
    .feed-card-wrap .feed-btn--wa { background: var(--green-soft) !important; color: var(--green) !important; }
    @media (max-width: 640px) {
        .feed-card-wrap { padding: 12px 14px 8px 14px !important; }
        .feed-card-wrap .feed-card-footer { margin-top: 6px; }
        .hl-title { font-size: 0.98rem !important; }
    }

    /* One calm primary: tinted fill + coloured label instead of a solid colour block */
    .stButton:not(#a):not(#b) button[kind="primary"]:not(#a):not(#b), div[data-testid="stFormSubmitButton"]:not(#a):not(#b) button[kind="primaryFormSubmit"]:not(#a):not(#b),
    div[data-testid="stDownloadButton"]:not(#a):not(#b) button[kind="primary"]:not(#a):not(#b), div[data-testid="stForm"]:not(#a):not(#b) div[data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"]:not(#a):not(#b) {
        background: var(--tint-soft) !important; color: var(--tint) !important; border: none !important; box-shadow: none !important; font-weight: 650 !important;
    }
    .stButton:not(#a):not(#b) button[kind="primary"]:not(#a):not(#b) *, div[data-testid="stFormSubmitButton"]:not(#a):not(#b) button[kind="primaryFormSubmit"]:not(#a):not(#b) *,
    div[data-testid="stDownloadButton"]:not(#a):not(#b) button[kind="primary"]:not(#a):not(#b) * { color: inherit !important; }
    .stButton:not(#a):not(#b) button[kind="primary"]:not(#a):not(#b):hover, div[data-testid="stFormSubmitButton"]:not(#a):not(#b) button[kind="primaryFormSubmit"]:not(#a):not(#b):hover { filter: brightness(0.96); box-shadow: none !important; }
    [class*="st-key-btn_gen_"]:not(#a):not(#b) button[kind="primary"]:not(#a):not(#b), [class*="st-key-dlg_conf_"]:not(#a):not(#b) button[kind="primary"]:not(#a):not(#b), [class*="st-key-dlg_rd_conf_"]:not(#a):not(#b) button[kind="primary"]:not(#a):not(#b) {
        background: var(--green-soft) !important; color: var(--green) !important;
    }

    /* Bottom tab bar on phones: the same workspace control, moved to the thumb */
    @media (max-width: 640px) {
        .block-container { padding-bottom: 88px !important; }
        .st-key-app_nav_seg:not(#a):not(#b) {
            position: fixed !important; left: 0 !important; right: 0 !important; bottom: 0 !important; z-index: 999 !important; width: 100% !important;
            background: var(--surface) !important; box-shadow: 0 -8px 24px rgba(0, 0, 0, 0.07) !important;
            padding: 6px max(6px, env(safe-area-inset-left, 0px)) calc(6px + env(safe-area-inset-bottom, 0px)) max(6px, env(safe-area-inset-right, 0px)) !important; margin: 0 !important;
        }
        .st-key-app_nav_seg:not(#a):not(#b) div[data-testid="stButtonGroup"], .st-key-app_nav_seg:not(#a):not(#b) [role="radiogroup"] {
            width: 100% !important; justify-content: space-between !important; flex-wrap: nowrap !important; overflow: visible !important; gap: 0 !important;
        }
        .st-key-app_nav_seg:not(#a):not(#b) button:not(#a):not(#b) {
            flex: 1 1 0 !important; min-width: 0 !important; width: auto !important; height: auto !important; min-height: 50px !important; padding: 5px 2px !important;
            border-radius: 12px !important; background: transparent !important; color: var(--label-3) !important; flex-direction: column !important;
        }
        .st-key-app_nav_seg:not(#a):not(#b) button:not(#a):not(#b) * { font-size: 0.64rem !important; line-height: 1.15 !important; font-weight: 600 !important; }
        .st-key-app_nav_seg:not(#a):not(#b) button:not(#a):not(#b) > div { width: 100% !important; }
        .st-key-app_nav_seg:not(#a):not(#b) button:not(#a):not(#b) > div > span { display: flex !important; flex-direction: column !important; align-items: center !important; justify-content: center !important; gap: 3px !important; }
        .st-key-app_nav_seg:not(#a):not(#b) button:not(#a):not(#b) p { margin: 0 !important; }
        .st-key-app_nav_seg:not(#a):not(#b) button:not(#a):not(#b) [data-testid="stIconMaterial"] { font-size: 1.45rem !important; line-height: 1 !important; }
        .st-key-app_nav_seg:not(#a):not(#b) button:not(#a):not(#b):not(:has([data-testid="stIconMaterial"])) * { font-size: 1.2rem !important; }
        .st-key-app_nav_seg:not(#a):not(#b) button[aria-checked="true"]:not(#a):not(#b) { background: transparent !important; color: var(--tint) !important; }
        .st-key-app_nav_seg:not(#a):not(#b) button[aria-checked="true"]:not(#a):not(#b) * { font-weight: 700 !important; }
    }
"""
APPLE_DESIGN_SYSTEM_CSS = _append_css(APPLE_DESIGN_SYSTEM_CSS, _HEADLINE_UX_CSS)
FEED_CARD_CSS = _append_css(FEED_CARD_CSS, _HEADLINE_UX_CSS)


_POLISH2_CSS = """
    /* ===== Polish pass ===== */
    /* Header: brand sits left, not spread across the row */
    .editorial-brand-anchor:not(#a):not(#b) { justify-content: flex-start !important; width: auto !important; gap: 8px !important; }

    /* Status bar: a single quiet line when everything is up to date */
    .sync-status-bar--calm { background: transparent !important; box-shadow: none !important; padding: 2px 4px !important; margin: 0 !important; gap: 7px; justify-content: flex-start; font-size: 0.74rem; font-weight: 500; color: var(--label-3); }
    .dot-ok { width: 7px; height: 7px; border-radius: 50%; background: var(--green); display: inline-block; flex: none; }

    /* Cards */
    .hl-title { line-height: 1.45 !important; }
    .feed-card-wrap .feed-btn { height: 34px; min-block-size: 34px; }
    .feed-btn:active, .stButton button:active, .st-key-app_nav_seg button:active { transform: scale(0.96); }
    .feed-card-wrap .feed-card-footer:has(.x-metrics-group) { flex-wrap: nowrap; justify-content: space-between; gap: 8px; }
    .feed-card-wrap .x-metrics-group { flex-wrap: nowrap; gap: 10px; min-width: 0; overflow: hidden; }
    .feed-card-wrap .x-metric-item { background: transparent !important; padding: 0 !important; font-size: 0.76rem; color: var(--label-3) !important; gap: 4px; }
    .feed-card-wrap .x-sentiment-badge { background: transparent !important; padding: 0 !important; font-size: 0.74rem; font-weight: 650; }
    .feed-card-wrap .x-sentiment-positive { color: var(--green) !important; }
    .feed-card-wrap .x-sentiment-alert { color: var(--red) !important; }

    @media (max-width: 640px) {
        /* Tab bar: soft pill behind the active icon, like iOS */
        .st-key-app_nav_seg:not(#a):not(#b) button:not(#a):not(#b) > div > span > span:first-child { display: inline-flex !important; align-items: center; justify-content: center; padding: 3px 16px !important; border-radius: 999px; transition: background-color 0.18s ease; }
        .st-key-app_nav_seg:not(#a):not(#b) button[aria-checked="true"]:not(#a):not(#b) > div > span > span:first-child { background: var(--tint-soft); }
        .st-key-app_nav_seg:not(#a):not(#b) { box-shadow: 0 -10px 28px rgba(0, 0, 0, 0.06) !important; }
    }
    @media (prefers-reduced-motion: reduce) {
        .feed-btn:active, .stButton button:active, .st-key-app_nav_seg button:active { transform: none; }
    }
"""
APPLE_DESIGN_SYSTEM_CSS = _append_css(APPLE_DESIGN_SYSTEM_CSS, _POLISH2_CSS)
FEED_CARD_CSS = _append_css(FEED_CARD_CSS, _POLISH2_CSS)


_NAV_ICONS_CSS = """
    /* ===== Workspace icons: Nepal peaks, India chakra, X logo, Health pulse (drawn as masks over the Material placeholder) ===== */
    .st-key-app_nav_seg:not(#a):not(#b):not(#c) button:nth-of-type(1):not(#z) [data-testid="stIconMaterial"],
    .st-key-app_nav_seg:not(#a):not(#b):not(#c) button:nth-of-type(2):not(#z) [data-testid="stIconMaterial"],
    .st-key-app_nav_seg:not(#a):not(#b):not(#c) button:nth-of-type(3):not(#z) [data-testid="stIconMaterial"],
    .st-key-app_nav_seg:not(#a):not(#b):not(#c) button:nth-of-type(4):not(#z) [data-testid="stIconMaterial"],
    .st-key-app_nav_seg:not(#a):not(#b):not(#c) button:nth-of-type(6):not(#z) [data-testid="stIconMaterial"] {
        display: inline-block !important; font-size: 0 !important; width: 18px !important; min-width: 18px !important; max-width: none !important; flex: 0 0 auto !important; height: 18px !important; background: currentColor !important;
        -webkit-mask-repeat: no-repeat; mask-repeat: no-repeat; -webkit-mask-position: center; mask-position: center; -webkit-mask-size: contain; mask-size: contain;
    }
    .st-key-app_nav_seg:not(#a):not(#b):not(#c) button:nth-of-type(1):not(#z) [data-testid="stIconMaterial"] { -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M5 4h11a1 1 0 0 1 1 1v15H6a2 2 0 0 1-2-2V5a1 1 0 0 1 1-1z%22/%3E%3Cpath d=%22M17 9h3v9a2 2 0 0 1-2 2M8 8h6M8 12h6M8 16h3%22/%3E%3C/svg%3E"); mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M5 4h11a1 1 0 0 1 1 1v15H6a2 2 0 0 1-2-2V5a1 1 0 0 1 1-1z%22/%3E%3Cpath d=%22M17 9h3v9a2 2 0 0 1-2 2M8 8h6M8 12h6M8 16h3%22/%3E%3C/svg%3E"); }
    .st-key-app_nav_seg:not(#a):not(#b):not(#c) button:nth-of-type(2):not(#z) [data-testid="stIconMaterial"] { -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M2 19 8.5 7 13 15l2.5-4L22 19z%22/%3E%3Cpath d=%22m7 10 1.5 1.5L10 10%22/%3E%3C/svg%3E"); mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M2 19 8.5 7 13 15l2.5-4L22 19z%22/%3E%3Cpath d=%22m7 10 1.5 1.5L10 10%22/%3E%3C/svg%3E"); }
    .st-key-app_nav_seg:not(#a):not(#b):not(#c) button:nth-of-type(3):not(#z) [data-testid="stIconMaterial"] { -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Ccircle cx=%2212%22 cy=%2212%22 r=%229%22/%3E%3Ccircle cx=%2212%22 cy=%2212%22 r=%221.6%22/%3E%3Cpath d=%22M12 3v7.4M12 13.6V21M3 12h7.4M13.6 12H21M5.6 5.6l5.2 5.2M13.2 13.2l5.2 5.2M18.4 5.6l-5.2 5.2M10.8 13.2l-5.2 5.2%22/%3E%3C/svg%3E"); mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Ccircle cx=%2212%22 cy=%2212%22 r=%229%22/%3E%3Ccircle cx=%2212%22 cy=%2212%22 r=%221.6%22/%3E%3Cpath d=%22M12 3v7.4M12 13.6V21M3 12h7.4M13.6 12H21M5.6 5.6l5.2 5.2M13.2 13.2l5.2 5.2M18.4 5.6l-5.2 5.2M10.8 13.2l-5.2 5.2%22/%3E%3C/svg%3E"); }
    .st-key-app_nav_seg:not(#a):not(#b):not(#c) button:nth-of-type(4):not(#z) [data-testid="stIconMaterial"] { -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22black%22%3E%3Cpath d=%22M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z%22/%3E%3C/svg%3E"); mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22black%22%3E%3Cpath d=%22M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z%22/%3E%3C/svg%3E"); }
    .st-key-app_nav_seg:not(#a):not(#b):not(#c) button:nth-of-type(6):not(#z) [data-testid="stIconMaterial"] { -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M3 12h4l3-8 4 16 3-8h4%22/%3E%3C/svg%3E"); mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M3 12h4l3-8 4 16 3-8h4%22/%3E%3C/svg%3E"); }
    @media (max-width: 640px) {
        .st-key-app_nav_seg:not(#a):not(#b):not(#c) button:nth-of-type(1):not(#z) [data-testid="stIconMaterial"],
    .st-key-app_nav_seg:not(#a):not(#b):not(#c) button:nth-of-type(2):not(#z) [data-testid="stIconMaterial"],
        .st-key-app_nav_seg:not(#a):not(#b):not(#c) button:nth-of-type(3):not(#z) [data-testid="stIconMaterial"],
        .st-key-app_nav_seg:not(#a):not(#b):not(#c) button:nth-of-type(4):not(#z) [data-testid="stIconMaterial"],
        .st-key-app_nav_seg:not(#a):not(#b):not(#c) button:nth-of-type(6):not(#z) [data-testid="stIconMaterial"] { width: 24px !important; min-width: 24px !important; height: 24px !important; }
        /* Stop sideways drift of the whole page on phones */
        html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], section.main { overflow-x: hidden !important; max-width: 100vw; }
    }
    /* Login logo: line icon in the accent colour */
    .auth-header__icon-ring { color: #0066CC; }
    .auth-header__icon-ring svg path { fill: none !important; stroke: currentColor !important; }
"""
APPLE_DESIGN_SYSTEM_CSS = _append_css(APPLE_DESIGN_SYSTEM_CSS, _NAV_ICONS_CSS)
AUTH_CSS = _append_css(AUTH_CSS, _NAV_ICONS_CSS)


_TOOLBAR_CSS = """
    /* ===== Toolbar row (title + tools) ===== */
    div[data-testid="stElementContainer"]:has(.tb-anchor) { display: none !important; }
    div[data-testid="stHorizontalBlock"]:has(.tb-anchor) .stButton button, div[data-testid="stHorizontalBlock"]:has(.tb-anchor) [data-testid="stPopover"] button { padding: 0 8px !important; min-width: 0 !important; }
"""
APPLE_DESIGN_SYSTEM_CSS = _append_css(APPLE_DESIGN_SYSTEM_CSS, _TOOLBAR_CSS)

_DESKTOP_CSS = """
"""
APPLE_DESIGN_SYSTEM_CSS = _append_css(APPLE_DESIGN_SYSTEM_CSS, _DESKTOP_CSS)

_RAIL_CSS = """
/* ===== Side rail: the workspace control becomes a fixed left rail on every screen size ===== */
:root { --rail-w: 76px; }
@media (max-width: 640px) { :root { --rail-w: 60px; } }
.st-key-app_nav_seg:not(#a):not(#b):not(#c) {
  position: fixed !important; left: 0 !important; top: 0 !important; bottom: 0 !important; right: auto !important; width: var(--rail-w) !important; max-width: none !important; margin: 0 !important;
  z-index: 999 !important; background: var(--surface) !important; box-shadow: 1px 0 0 var(--hair, rgba(0,0,0,.06)) !important;
  padding: calc(12px + env(safe-area-inset-top, 0px)) 4px calc(12px + env(safe-area-inset-bottom, 0px)) max(4px, env(safe-area-inset-left, 0px)) !important; overflow-y: auto !important;
}
.st-key-app_nav_seg:not(#a):not(#b):not(#c) { display: flex !important; flex-direction: column !important; justify-content: center !important; }
.st-key-app_nav_seg:not(#a):not(#b):not(#c) > * { flex: 0 0 auto !important; width: 100% !important; }
.st-key-app_nav_seg:not(#a):not(#b):not(#c) div[data-testid="stButtonGroup"], .st-key-app_nav_seg:not(#a):not(#b):not(#c) [role="radiogroup"] {
  display: flex !important; flex-direction: column !important; flex-wrap: nowrap !important; align-items: stretch !important; justify-content: flex-start !important; gap: 6px !important; width: 100% !important; overflow: visible !important; background: transparent !important; padding: 0 !important;
}
.st-key-app_nav_seg:not(#a):not(#b):not(#c) button:not(#a):not(#b):not(#c) {
  flex: 0 0 auto !important; width: 100% !important; min-width: 0 !important; height: auto !important; min-height: 54px !important; padding: 7px 2px !important;
  border-radius: 14px !important; background: transparent !important; color: var(--label-3, #8E8E93) !important; flex-direction: column !important; box-shadow: none !important;
}
.st-key-app_nav_seg:not(#a):not(#b):not(#c) button:not(#a):not(#b):not(#c) * { font-size: 0.64rem !important; line-height: 1.15 !important; font-weight: 600 !important; }
.st-key-app_nav_seg:not(#a):not(#b):not(#c) button:not(#a):not(#b):not(#c) > div { width: 100% !important; }
.st-key-app_nav_seg:not(#a):not(#b):not(#c) button:not(#a):not(#b):not(#c) > div > span { display: flex !important; flex-direction: column !important; align-items: center !important; justify-content: center !important; gap: 4px !important; }
.st-key-app_nav_seg:not(#a):not(#b):not(#c) button:not(#a):not(#b):not(#c) p { margin: 0 !important; }
.st-key-app_nav_seg:not(#a):not(#b):not(#c) button:not(#a):not(#b):not(#c) [data-testid="stIconMaterial"] { font-size: 1.45rem !important; line-height: 1 !important; }
.st-key-app_nav_seg:not(#a):not(#b):not(#c) button[aria-checked="true"]:not(#a):not(#b):not(#c) { background: var(--tint-soft) !important; color: var(--tint) !important; }
.st-key-app_nav_seg:not(#a):not(#b):not(#c) button[aria-checked="true"]:not(#a):not(#b):not(#c) * { font-weight: 700 !important; }
.st-key-app_nav_seg:not(#a):not(#b):not(#c) button:not(#a):not(#b):not(#c) > div > span > span:first-child { padding: 0 !important; background: transparent !important; }
div[data-testid="stMainBlockContainer"], .block-container { padding-left: calc(var(--rail-w) + 14px) !important; padding-bottom: 28px !important; }
@media (max-width: 640px) { div[data-testid="stMainBlockContainer"], .block-container { padding-left: calc(var(--rail-w) + 8px) !important; padding-right: 10px !important; } }
.st-key-new_stories_pill:not(#a):not(#b) { bottom: 24px !important; left: calc(50% + var(--rail-w) / 2) !important; }
"""
_TITLEBAR_CSS = """
/* ===== Title bar: page title + sync pill; on desktop the tool buttons sit on the same row ===== */
.hdr-title-wrap { display: flex; align-items: center; gap: 8px; min-height: 44px; white-space: nowrap; }
.hdr-title { font-size: 1.4rem; font-weight: 700; letter-spacing: -0.03em; line-height: 1.1; color: var(--text-primary, #1d1d1f); }
.hdr-meta { display: inline-flex; align-items: center; }
.hdr-title-wrap .live-status-inline.sync-inline { background: none !important; padding: 0 !important; border-radius: 0; font-size: 0.8rem; font-weight: 550; color: var(--label-3, #6E6E73) !important; display: inline-flex; align-items: center; gap: 7px; letter-spacing: 0; }
.sync-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--dot, #8E8E93); flex: none; }
.sync-dot--live { animation: nm-dot 2.4s ease-in-out infinite; }
@keyframes nm-dot { 0%, 100% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--dot) 45%, transparent); } 50% { box-shadow: 0 0 0 5px transparent; } }
@media (prefers-reduced-motion: reduce) { .sync-dot--live { animation: none; } }
"""
APPLE_DESIGN_SYSTEM_CSS = _append_css(APPLE_DESIGN_SYSTEM_CSS, _RAIL_CSS)

_RAIL_ICONS_CSS = """
/* ===== Rail icons: one consistent set (2px stroke, 26px), darker idle colour, filled when active ===== */

.st-key-app_nav_seg:not(#a):not(#b):not(#c):not(#d) button:nth-of-type(1):not(#z) [data-testid="stIconMaterial"],
.st-key-app_nav_seg:not(#a):not(#b):not(#c):not(#d) button:nth-of-type(2):not(#z) [data-testid="stIconMaterial"],
.st-key-app_nav_seg:not(#a):not(#b):not(#c):not(#d) button:nth-of-type(3):not(#z) [data-testid="stIconMaterial"],
.st-key-app_nav_seg:not(#a):not(#b):not(#c):not(#d) button:nth-of-type(4):not(#z) [data-testid="stIconMaterial"],
.st-key-app_nav_seg:not(#a):not(#b):not(#c):not(#d) button:nth-of-type(5):not(#z) [data-testid="stIconMaterial"],
.st-key-app_nav_seg:not(#a):not(#b):not(#c):not(#d) button:nth-of-type(6):not(#z) [data-testid="stIconMaterial"] {
  display: inline-block !important; font-size: 0 !important; width: 26px !important; min-width: 26px !important; max-width: none !important; height: 26px !important; flex: 0 0 auto !important; background: currentColor !important;
  -webkit-mask-repeat: no-repeat; mask-repeat: no-repeat; -webkit-mask-position: center; mask-position: center; -webkit-mask-size: contain; mask-size: contain;
}
.st-key-app_nav_seg:not(#a):not(#b):not(#c):not(#d) button:nth-of-type(1):not(#z) [data-testid="stIconMaterial"] { -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M5 4h11a1 1 0 0 1 1 1v15H6a2 2 0 0 1-2-2V5a1 1 0 0 1 1-1z%22/%3E%3Cpath d=%22M17 9h3v9a2 2 0 0 1-2 2%22/%3E%3Cpath d=%22M8 8h6M8 12h6M8 16h3%22/%3E%3C/svg%3E"); mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M5 4h11a1 1 0 0 1 1 1v15H6a2 2 0 0 1-2-2V5a1 1 0 0 1 1-1z%22/%3E%3Cpath d=%22M17 9h3v9a2 2 0 0 1-2 2%22/%3E%3Cpath d=%22M8 8h6M8 12h6M8 16h3%22/%3E%3C/svg%3E"); }
.st-key-app_nav_seg:not(#a):not(#b):not(#c):not(#d) button[aria-checked="true"]:nth-of-type(1):not(#z) [data-testid="stIconMaterial"] { -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cdefs%3E%3Cmask id=%22m%22%3E%3Crect width=%2224%22 height=%2224%22 fill=%22white%22/%3E%3Cpath d=%22M8 8h6M8 12h6M8 16h3%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22/%3E%3C/mask%3E%3C/defs%3E%3Cpath d=%22M4.5 3.5h12a1.5 1.5 0 0 1 1.5 1.5v15.5H6.5a3 3 0 0 1-3-3V4.5a1 1 0 0 1 1-1z%22 fill=%22black%22 stroke=%22none%22 mask=%22url%28%23m%29%22/%3E%3Cpath d=%22M18 9h2a1 1 0 0 1 1 1v8a2.5 2.5 0 0 1-2.5 2.5%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 fill=%22none%22/%3E%3C/svg%3E"); mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cdefs%3E%3Cmask id=%22m%22%3E%3Crect width=%2224%22 height=%2224%22 fill=%22white%22/%3E%3Cpath d=%22M8 8h6M8 12h6M8 16h3%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22/%3E%3C/mask%3E%3C/defs%3E%3Cpath d=%22M4.5 3.5h12a1.5 1.5 0 0 1 1.5 1.5v15.5H6.5a3 3 0 0 1-3-3V4.5a1 1 0 0 1 1-1z%22 fill=%22black%22 stroke=%22none%22 mask=%22url%28%23m%29%22/%3E%3Cpath d=%22M18 9h2a1 1 0 0 1 1 1v8a2.5 2.5 0 0 1-2.5 2.5%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 fill=%22none%22/%3E%3C/svg%3E"); }
.st-key-app_nav_seg:not(#a):not(#b):not(#c):not(#d) button:nth-of-type(2):not(#z) [data-testid="stIconMaterial"] { -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M2.5 19 9 8l4 7 2.5-4 6 8z%22/%3E%3C/svg%3E"); mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M2.5 19 9 8l4 7 2.5-4 6 8z%22/%3E%3C/svg%3E"); }
.st-key-app_nav_seg:not(#a):not(#b):not(#c):not(#d) button[aria-checked="true"]:nth-of-type(2):not(#z) [data-testid="stIconMaterial"] { -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M2.5 19 9 8l4 7 2.5-4 6 8z%22 fill=%22black%22 stroke=%22black%22 stroke-width=%222%22 stroke-linejoin=%22round%22/%3E%3C/svg%3E"); mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M2.5 19 9 8l4 7 2.5-4 6 8z%22 fill=%22black%22 stroke=%22black%22 stroke-width=%222%22 stroke-linejoin=%22round%22/%3E%3C/svg%3E"); }
.st-key-app_nav_seg:not(#a):not(#b):not(#c):not(#d) button:nth-of-type(3):not(#z) [data-testid="stIconMaterial"] { -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Ccircle cx=%2212%22 cy=%2212%22 r=%229%22/%3E%3Ccircle cx=%2212%22 cy=%2212%22 r=%221.6%22/%3E%3Cpath d=%22M12 3v7.4M12 13.6V21M3 12h7.4M13.6 12H21M5.6 5.6l5.2 5.2M13.2 13.2l5.2 5.2M18.4 5.6l-5.2 5.2M10.8 13.2l-5.2 5.2%22/%3E%3C/svg%3E"); mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Ccircle cx=%2212%22 cy=%2212%22 r=%229%22/%3E%3Ccircle cx=%2212%22 cy=%2212%22 r=%221.6%22/%3E%3Cpath d=%22M12 3v7.4M12 13.6V21M3 12h7.4M13.6 12H21M5.6 5.6l5.2 5.2M13.2 13.2l5.2 5.2M18.4 5.6l-5.2 5.2M10.8 13.2l-5.2 5.2%22/%3E%3C/svg%3E"); }
.st-key-app_nav_seg:not(#a):not(#b):not(#c):not(#d) button[aria-checked="true"]:nth-of-type(3):not(#z) [data-testid="stIconMaterial"] { -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cdefs%3E%3Cmask id=%22m%22%3E%3Crect width=%2224%22 height=%2224%22 fill=%22white%22/%3E%3Ccircle cx=%2212%22 cy=%2212%22 r=%222.4%22 fill=%22black%22/%3E%3Cpath d=%22M12 5v4.6M12 14.4V19M5 12h4.6M14.4 12H19M7 7l3.3 3.3M13.7 13.7 17 17M17 7l-3.3 3.3M10.3 13.7 7 17%22 stroke=%22black%22 stroke-width=%221.7%22 stroke-linecap=%22round%22/%3E%3C/mask%3E%3C/defs%3E%3Ccircle cx=%2212%22 cy=%2212%22 r=%2210%22 fill=%22black%22 stroke=%22none%22 mask=%22url%28%23m%29%22/%3E%3C/svg%3E"); mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cdefs%3E%3Cmask id=%22m%22%3E%3Crect width=%2224%22 height=%2224%22 fill=%22white%22/%3E%3Ccircle cx=%2212%22 cy=%2212%22 r=%222.4%22 fill=%22black%22/%3E%3Cpath d=%22M12 5v4.6M12 14.4V19M5 12h4.6M14.4 12H19M7 7l3.3 3.3M13.7 13.7 17 17M17 7l-3.3 3.3M10.3 13.7 7 17%22 stroke=%22black%22 stroke-width=%221.7%22 stroke-linecap=%22round%22/%3E%3C/mask%3E%3C/defs%3E%3Ccircle cx=%2212%22 cy=%2212%22 r=%2210%22 fill=%22black%22 stroke=%22none%22 mask=%22url%28%23m%29%22/%3E%3C/svg%3E"); }
.st-key-app_nav_seg:not(#a):not(#b):not(#c):not(#d) button:nth-of-type(4):not(#z) [data-testid="stIconMaterial"] { -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M5 4h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-7l-5 4v-4H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z%22/%3E%3Cpath d=%22M12 13.4 9.2 10.7a1.8 1.8 0 0 1 2.8-2.3 1.8 1.8 0 0 1 2.8 2.3z%22/%3E%3C/svg%3E"); mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M5 4h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-7l-5 4v-4H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z%22/%3E%3Cpath d=%22M12 13.4 9.2 10.7a1.8 1.8 0 0 1 2.8-2.3 1.8 1.8 0 0 1 2.8 2.3z%22/%3E%3C/svg%3E"); }
.st-key-app_nav_seg:not(#a):not(#b):not(#c):not(#d) button[aria-checked="true"]:nth-of-type(4):not(#z) [data-testid="stIconMaterial"] { -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cdefs%3E%3Cmask id=%22m%22%3E%3Crect width=%2224%22 height=%2224%22 fill=%22white%22/%3E%3Cpath d=%22M12 13.4 9.2 10.7a1.8 1.8 0 0 1 2.8-2.3 1.8 1.8 0 0 1 2.8 2.3z%22 fill=%22black%22 stroke=%22black%22 stroke-width=%221.2%22 stroke-linejoin=%22round%22/%3E%3C/mask%3E%3C/defs%3E%3Cpath d=%22M5 4h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-7l-5 4v-4H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z%22 fill=%22black%22 stroke=%22black%22 stroke-width=%222%22 stroke-linejoin=%22round%22 mask=%22url%28%23m%29%22/%3E%3C/svg%3E"); mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cdefs%3E%3Cmask id=%22m%22%3E%3Crect width=%2224%22 height=%2224%22 fill=%22white%22/%3E%3Cpath d=%22M12 13.4 9.2 10.7a1.8 1.8 0 0 1 2.8-2.3 1.8 1.8 0 0 1 2.8 2.3z%22 fill=%22black%22 stroke=%22black%22 stroke-width=%221.2%22 stroke-linejoin=%22round%22/%3E%3C/mask%3E%3C/defs%3E%3Cpath d=%22M5 4h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-7l-5 4v-4H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z%22 fill=%22black%22 stroke=%22black%22 stroke-width=%222%22 stroke-linejoin=%22round%22 mask=%22url%28%23m%29%22/%3E%3C/svg%3E"); }
.st-key-app_nav_seg:not(#a):not(#b):not(#c):not(#d) button:nth-of-type(5):not(#z) [data-testid="stIconMaterial"] { -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M12 15V4M8 8l4-4 4 4%22/%3E%3Cpath d=%22M6 12H5a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-6a1 1 0 0 0-1-1h-1%22/%3E%3C/svg%3E"); mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M12 15V4M8 8l4-4 4 4%22/%3E%3Cpath d=%22M6 12H5a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-6a1 1 0 0 0-1-1h-1%22/%3E%3C/svg%3E"); }
.st-key-app_nav_seg:not(#a):not(#b):not(#c):not(#d) button[aria-checked="true"]:nth-of-type(5):not(#z) [data-testid="stIconMaterial"] { -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cdefs%3E%3Cmask id=%22m%22%3E%3Crect width=%2224%22 height=%2224%22 fill=%22white%22/%3E%3Cpath d=%22M12 17v-5%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22/%3E%3C/mask%3E%3C/defs%3E%3Crect x=%223.5%22 y=%2210%22 width=%2217%22 height=%2211%22 rx=%222.5%22 fill=%22black%22 stroke=%22none%22 mask=%22url%28%23m%29%22/%3E%3Cpath d=%22M12 12.5V3.5M8 7l4-4 4 4%22 stroke=%22black%22 stroke-width=%222.2%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22 fill=%22none%22/%3E%3C/svg%3E"); mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cdefs%3E%3Cmask id=%22m%22%3E%3Crect width=%2224%22 height=%2224%22 fill=%22white%22/%3E%3Cpath d=%22M12 17v-5%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22/%3E%3C/mask%3E%3C/defs%3E%3Crect x=%223.5%22 y=%2210%22 width=%2217%22 height=%2211%22 rx=%222.5%22 fill=%22black%22 stroke=%22none%22 mask=%22url%28%23m%29%22/%3E%3Cpath d=%22M12 12.5V3.5M8 7l4-4 4 4%22 stroke=%22black%22 stroke-width=%222.2%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22 fill=%22none%22/%3E%3C/svg%3E"); }
.st-key-app_nav_seg:not(#a):not(#b):not(#c):not(#d) button:nth-of-type(6):not(#z) [data-testid="stIconMaterial"] { -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M3 12h4l3-8 4 16 3-8h4%22/%3E%3C/svg%3E"); mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%222%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M3 12h4l3-8 4 16 3-8h4%22/%3E%3C/svg%3E"); }
.st-key-app_nav_seg:not(#a):not(#b):not(#c):not(#d) button[aria-checked="true"]:nth-of-type(6):not(#z) [data-testid="stIconMaterial"] { -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%223%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M3 12h4l3-8 4 16 3-8h4%22/%3E%3C/svg%3E"); mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22black%22 stroke-width=%223%22 stroke-linecap=%22round%22 stroke-linejoin=%22round%22%3E%3Cpath d=%22M3 12h4l3-8 4 16 3-8h4%22/%3E%3C/svg%3E"); }
.st-key-app_nav_seg:not(#a):not(#b):not(#c):not(#d) button:not(#z):not(#e):not(#f):not(#g) { color: color-mix(in srgb, var(--label, #1d1d1f) 74%, transparent) !important; }
.st-key-app_nav_seg:not(#a):not(#b):not(#c):not(#d) button:not(#z):not(#e):not(#f):not(#g) * { font-size: 0.68rem !important; font-weight: 650 !important; }
.st-key-app_nav_seg:not(#a):not(#b):not(#c):not(#d) button[aria-checked="true"]:not(#z):not(#e):not(#f):not(#g) { color: var(--tint) !important; }
.st-key-app_nav_seg:not(#a):not(#b):not(#c):not(#d) button[aria-checked="true"]:not(#z):not(#e):not(#f):not(#g) * { font-weight: 750 !important; }
.st-key-app_nav_seg:not(#a):not(#b):not(#c):not(#d) button:not(#z):not(#e):not(#f):not(#g):hover { background: var(--fill, rgba(60,60,67,.08)) !important; }
.st-key-app_nav_seg:not(#a):not(#b):not(#c):not(#d) button[aria-checked="true"]:not(#z):not(#e):not(#f):not(#g):hover { background: var(--tint-soft) !important; }
.st-key-app_nav_seg:not(#a):not(#b):not(#c):not(#d) button:not(#z):not(#e):not(#f):not(#g):active { transform: scale(0.95); }
.st-key-app_nav_seg:not(#a):not(#b):not(#c):not(#d) button:not(#z) [data-testid="stIconMaterial"] { font-size: 0 !important; }
@media (max-width: 640px) { :root { --rail-w: 64px; } }
"""
APPLE_DESIGN_SYSTEM_CSS = _append_css(APPLE_DESIGN_SYSTEM_CSS, _TITLEBAR_CSS)
APPLE_DESIGN_SYSTEM_CSS = _append_css(APPLE_DESIGN_SYSTEM_CSS, _RAIL_ICONS_CSS)

_TB2_CSS = """
/* ===== Title + tools share one row (Streamlit columns); the rail host takes no space ===== */
.st-key-rail_host, div[data-testid="stLayoutWrapper"]:has(> .st-key-rail_host), div[data-testid="stElementContainer"]:has(> .st-key-rail_host) { position: fixed !important; height: 0 !important; min-height: 0 !important; margin: 0 !important; padding: 0 !important; overflow: visible !important; }
div[data-testid="stHorizontalBlock"]:has(.tb-anchor) { gap: 8px !important; row-gap: 6px !important; align-items: center !important; }
div[data-testid="stHorizontalBlock"]:has(.tb-anchor) .stButton button, div[data-testid="stHorizontalBlock"]:has(.tb-anchor) [data-testid="stPopover"] button { height: 38px !important; min-height: 38px !important; background: rgba(60,60,67,.08) !important; border: 0 !important; box-shadow: none !important; }
div[data-testid="stHorizontalBlock"]:has(.tb-anchor) .stButton button:hover, div[data-testid="stHorizontalBlock"]:has(.tb-anchor) [data-testid="stPopover"] button:hover { background: rgba(60,60,67,.14) !important; }
@media (min-width: 900px) {
  .hdr-title-wrap { flex-direction: column; align-items: flex-start; justify-content: center; gap: 6px; min-height: 64px; }
  .hdr-title { font-size: 1.7rem; }
  div[data-testid="stHorizontalBlock"]:has(.tb-anchor) { flex-wrap: nowrap !important; }
  div[data-testid="stHorizontalBlock"]:has(.tb-anchor) > div[data-testid="stColumn"] { flex: 0 0 auto !important; min-width: 0 !important; width: 52px !important; }
  div[data-testid="stHorizontalBlock"]:has(.tb-anchor) > div[data-testid="stColumn"]:nth-child(1) { flex: 1 1 0 !important; width: auto !important; }
  div[data-testid="stHorizontalBlock"]:has(.tb-anchor) > div[data-testid="stColumn"]:nth-child(3) { width: 76px !important; }
  div[data-testid="stHorizontalBlock"]:has(.tb-anchor) > div[data-testid="stColumn"]:nth-child(4) { width: 92px !important; }
  div[data-testid="stHorizontalBlock"]:has(.tb-only-theme) > div[data-testid="stColumn"]:nth-child(2) { width: 52px !important; }
}
@media (max-width: 899px) {
  div[data-testid="stHorizontalBlock"]:has(.tb-anchor):has(.tb-anchor):has(.tb-anchor):has(.tb-anchor):has(.tb-anchor) { flex-wrap: wrap !important; flex-direction: row !important; }
  div[data-testid="stHorizontalBlock"]:has(.tb-anchor):has(.tb-anchor):has(.tb-anchor):has(.tb-anchor):has(.tb-anchor) > div[data-testid="stColumn"] { flex: 1 1 0 !important; min-width: 0 !important; width: auto !important; }
  div[data-testid="stHorizontalBlock"]:has(.tb-anchor):has(.tb-anchor):has(.tb-anchor):has(.tb-anchor):has(.tb-anchor) > div[data-testid="stColumn"]:nth-child(1) { flex: 0 0 100% !important; }
  div[data-testid="stHorizontalBlock"]:has(.tb-anchor):has(.tb-anchor):has(.tb-anchor):has(.tb-anchor):has(.tb-anchor) > div[data-testid="stColumn"]:nth-child(4) { flex: 1.9 1 0 !important; }
  div[data-testid="stHorizontalBlock"]:has(.tb-only-theme):has(.tb-only-theme):has(.tb-only-theme):has(.tb-only-theme):has(.tb-only-theme) > div[data-testid="stColumn"]:nth-child(1) { flex: 1 1 0 !important; }
  div[data-testid="stHorizontalBlock"]:has(.tb-only-theme):has(.tb-only-theme):has(.tb-only-theme):has(.tb-only-theme):has(.tb-only-theme) > div[data-testid="stColumn"]:nth-child(2) { flex: 0 0 52px !important; }
}
"""
APPLE_DESIGN_SYSTEM_CSS = _append_css(APPLE_DESIGN_SYSTEM_CSS, _TB2_CSS)



_DIALOG_TIGHT_CSS = """
    /* ===== Dialogs: no spacer rows, smaller title, tighter rhythm ===== */
    div[data-testid="stElementContainer"]:has(.share-modal-anchor), div[data-testid="stElementContainer"]:has(.read-modal-anchor) { display: none !important; }
    div[data-testid="stDialog"] [data-testid="stVerticalBlock"] { gap: 0.55rem !important; }
    div[data-testid="stDialog"] [role="dialog"] h2 { font-size: 1.2rem !important; font-weight: 650 !important; letter-spacing: -0.015em !important; line-height: 1.3 !important; }
    .share-modal-head { margin: 0 !important; min-height: 0 !important; }
    .fulltext-reader-box { margin: 0 !important; }
    .fulltext-reader-box__header:empty { display: none !important; }
"""
APPLE_DESIGN_SYSTEM_CSS = _append_css(APPLE_DESIGN_SYSTEM_CSS, _DIALOG_TIGHT_CSS)


_TYPE_CSS = """
    /* ===== Type: Devanagari-friendly, no download ===== */
    @font-face { font-family: "NepaliLocal"; font-display: swap; unicode-range: U+0900-097F, U+1CD0-1CF9, U+A8E0-A8FF;
        src: local("Kohinoor Devanagari"), local("Devanagari Sangam MN"), local("Noto Sans Devanagari"), local("Mukta"), local("Nirmala UI"), local("Lohit Devanagari"); }
    .hl-title, .hl-title a, .apple-card-title, .apple-card-title a, .apple-card-summary, .reader-para, .fulltext-reader-box__title, .fulltext-reader-box__body, .share-brief-body {
        font-family: "NepaliLocal", var(--font), sans-serif; letter-spacing: 0 !important; font-feature-settings: "kern" 1, "liga" 1; text-rendering: optimizeLegibility;
        overflow-wrap: break-word; hyphens: manual;
    }
    .hl-title, .apple-card-title { line-height: 1.48 !important; }
    /* Calmer refresh: stale content fades a little instead of flashing */
    div[data-stale="true"] { opacity: 0.6 !important; transition: opacity 0.2s ease; }
    div[data-testid="stElementContainer"]:has(iframe[height="0"]) { display: none !important; }
"""
APPLE_DESIGN_SYSTEM_CSS = _append_css(APPLE_DESIGN_SYSTEM_CSS, _TYPE_CSS)
FEED_CARD_CSS = _append_css(FEED_CARD_CSS, _TYPE_CSS)


_WA_ACTIONS_CSS = """
    /* ===== WhatsApp actions: icon row + group chip, then Send; sticks to the bottom of the dialog ===== */
    [class*="st-key-wa_actions_"]:not(#a):not(#b) { position: sticky; bottom: 0; z-index: 6; background: var(--bg); padding: 6px 0 4px 0; margin-top: 0; }
    [class*="st-key-wa_actions_"]:not(#a):not(#b) div[data-testid="stHorizontalBlock"]:not(#a):not(#b) { flex-wrap: nowrap !important; flex-direction: row !important; gap: 8px !important; }
    [class*="st-key-wa_actions_"]:not(#a):not(#b) div[data-testid="stHorizontalBlock"]:not(#a):not(#b) > div[data-testid="stColumn"] { flex: 1 1 0 !important; min-width: 0 !important; width: auto !important; }
    [class*="st-key-wa_actions_"]:not(#a):not(#b) div[data-testid="stHorizontalBlock"]:has([class*="st-key-wa_pop_"]):not(#a):not(#b) > div[data-testid="stColumn"]:last-child { flex: 3 1 0 !important; }
    [class*="st-key-wa_actions_"] div[data-testid="stHorizontalBlock"] .stButton button [data-testid="stMarkdownContainer"] { display: none !important; }
    [class*="st-key-wa_actions_"] div[data-testid="stHorizontalBlock"] .stButton button { padding: 0 8px !important; }
    [class*="st-key-wa_pop_"] button { justify-content: center !important; }
    [class*="st-key-wa_pop_"] button p { display: flex !important; align-items: center !important; justify-content: flex-start !important; gap: 6px !important; overflow: hidden !important; white-space: nowrap !important; margin: 0 !important; }
    [class*="st-key-wa_pop_"] button p span[role="img"] {
        font-size: 0 !important; width: 18px !important; min-width: 18px !important; height: 18px !important; display: inline-block !important; background: var(--green) !important; vertical-align: middle !important; flex: none !important;
        -webkit-mask: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22%3E%3Cpath d=%22M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z%22/%3E%3C/svg%3E") center / contain no-repeat; mask: url("data:image/svg+xml;utf8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 24 24%22%3E%3Cpath d=%22M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z%22/%3E%3C/svg%3E") center / contain no-repeat;
    }
"""
_WA_ACTIONS_CSS += """
    [class*="st-key-wa_actions_"]:not(#a):not(#b), [class*="st-key-wa_actions_"]:not(#a):not(#b) div[data-testid="stVerticalBlock"]:not(#a):not(#b) { gap: 6px !important; row-gap: 6px !important; }
    [class*="st-key-wa_actions_"]:not(#a):not(#b) div[data-testid="stElementContainer"]:not(#a):not(#b) { margin: 0 !important; }
    [class*="st-key-wa_actions_"] [class*="st-key-dlg_conf_"] .stButton button [data-testid="stMarkdownContainer"]:not(#a):not(#b),
    [class*="st-key-wa_actions_"] [class*="st-key-dlg_rd_conf_"] .stButton button [data-testid="stMarkdownContainer"]:not(#a):not(#b) { display: block !important; }
    [class*="st-key-wa_actions_"] [class*="st-key-dlg_conf_"] .stButton button p, [class*="st-key-wa_actions_"] [class*="st-key-dlg_rd_conf_"] .stButton button p { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    @media (prefers-color-scheme: dark) { [class*="st-key-wa_actions_"]:not(#a):not(#b) { background: #1C1C1E; } }
    :root[data-theme="dark"] [class*="st-key-wa_actions_"]:not(#a):not(#b) { background: #1C1C1E; }
"""
APPLE_DESIGN_SYSTEM_CSS = _append_css(APPLE_DESIGN_SYSTEM_CSS, _WA_ACTIONS_CSS)


_SYNC_SPIN_CSS = """
    @keyframes nm-spin { to { transform: rotate(360deg); } }
    [class*="st-key-btn_sync_run_"] [data-testid="stIconMaterial"] { display: inline-block; animation: nm-spin 1s linear infinite; }
    @media (prefers-reduced-motion: reduce) { [class*="st-key-btn_sync_run_"] [data-testid="stIconMaterial"] { animation: none; } }
"""
APPLE_DESIGN_SYSTEM_CSS = _append_css(APPLE_DESIGN_SYSTEM_CSS, _SYNC_SPIN_CSS)

_NEW_PILL_CSS = """
@keyframes nm-shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
.st-key-busy_pill summary p, .st-key-busy_pill summary span:not([data-testid="stIconMaterial"]), div[data-testid="stSpinner"] p, .feed-loading-pill span:last-child {
  background: linear-gradient(90deg, currentColor 0%, currentColor 35%, #0A84FF 50%, currentColor 65%, currentColor 100%);
  background-size: 200% 100%; -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; color: inherit;
  animation: nm-shimmer 2.2s linear infinite; }
.sync-inline .sp-spin { box-shadow: 0 0 8px rgba(10,132,255,.45); }
@media (prefers-reduced-motion: reduce) { .st-key-busy_pill summary p, div[data-testid="stSpinner"] p { animation: none; -webkit-text-fill-color: currentColor; } }

.sync-inline .sp-chip { display: inline-flex; align-items: center; gap: 3px; color: var(--text-primary, #1d1d1f); font-weight: 650; }
.sync-inline .sp-chip b { color: #1a7f37; } .sync-inline .sp-err { color: #c0392b; font-weight: 800; } .sync-inline .sp-ok { color: #1a7f37; } .sync-inline .sp-wait { opacity: .4; }
.sync-inline .sp-spin { width: 10px; height: 10px; border-radius: 50%; border: 2px solid rgba(0,113,227,.25); border-top-color: #0071e3; animation: nm-spin .8s linear infinite; display: inline-block; }

.st-key-sync_pill:not(#a):not(#b) { position: fixed !important; left: 50%; bottom: 84px; transform: translateX(-50%); z-index: 99998; width: auto !important; }
div[data-testid="stElementContainer"]:has(> .st-key-sync_pill), div[data-testid="stLayoutWrapper"]:has(> .st-key-sync_pill) { position: fixed !important; height: 0 !important; margin: 0 !important; }
.sync-pill { display: inline-flex; align-items: center; gap: 10px; padding: 8px 14px; border-radius: 999px; background: var(--surface); color: var(--text-primary, #1d1d1f); font-size: .8rem; box-shadow: 0 8px 28px rgba(0,0,0,.20); white-space: nowrap; }
.sync-pill .sp-verb { font-weight: 650; }
.sync-pill .sp-chip { display: inline-flex; align-items: center; gap: 4px; opacity: .95; }
.sync-pill .sp-chip b { color: #1a7f37; }
.sync-pill .sp-err { color: #c0392b; font-weight: 700; } .sync-pill .sp-ok { color: #1a7f37; } .sync-pill .sp-wait { opacity: .4; }
.sync-pill .sp-spin { width: 11px; height: 11px; border-radius: 50%; border: 2px solid rgba(0,113,227,.25); border-top-color: #0071e3; animation: nm-spin .8s linear infinite; display: inline-block; }
.sync-pill--final { animation: nm-pill-out .4s ease 4.5s forwards; }
@keyframes nm-pill-out { to { opacity: 0; transform: translateY(8px); visibility: hidden; } }

div[data-testid="stElementContainer"]:has(> .st-key-busy_pill), div[data-testid="stLayoutWrapper"]:has(> .st-key-busy_pill) { position: sticky !important; top: 0; z-index: 50; margin: 0 !important; }
.st-key-busy_pill:not(#a):not(#b) { position: static !important; width: 100% !important; }
.st-key-busy_pill [data-testid="stExpander"], .st-key-busy_pill details { border-radius: 14px !important; background: var(--surface-muted, #F5F5F7) !important; border: 0 !important; box-shadow: 0 2px 10px rgba(0,0,0,.08) !important; overflow: hidden; }
.st-key-busy_pill summary { padding: 8px 12px !important; font-size: .82rem !important; }
.st-key-busy_pill [data-testid="stExpanderDetails"], .st-key-busy_pill details > div:last-child { display: none !important; }

.st-key-new_stories_pill { position: fixed !important; bottom: 88px; left: 50%; transform: translateX(-50%);
  z-index: 999; width: auto !important; margin: 0 !important; }
div[data-testid="stElementContainer"]:has(> .st-key-new_stories_pill),
div[data-testid="stLayoutWrapper"]:has(> .st-key-new_stories_pill) { position: fixed !important; height: 0 !important; margin: 0 !important; }
.st-key-new_stories_pill .stButton button { height: 34px !important; padding: 0 14px !important; border-radius: 999px !important;
  background: rgba(0,113,227,.14) !important; color: #0a58ca !important; border: 0 !important; font-weight: 650 !important;
  backdrop-filter: blur(14px) saturate(1.6); -webkit-backdrop-filter: blur(14px) saturate(1.6);
  box-shadow: 0 4px 16px rgba(0,0,0,.14) !important; }
@media (prefers-color-scheme: dark) { .st-key-new_stories_pill .stButton button { color: #7db8ff !important; background: rgba(10,132,255,.22) !important; } }
:root[data-theme="dark"] .st-key-new_stories_pill .stButton button { color: #7db8ff !important; background: rgba(10,132,255,.22) !important; }
"""
APPLE_DESIGN_SYSTEM_CSS = _append_css(APPLE_DESIGN_SYSTEM_CSS, _NEW_PILL_CSS)
FEED_CARD_CSS = _append_css(FEED_CARD_CSS, ".x-post-header__meta { flex-grow: 1; } .x-post-header__meta .hl-chip--ok { margin-left: auto; }")


import re as _re


def _minify_css(css: str) -> str:
    css = _re.sub(r"/\*.*?\*/", "", css, flags=_re.S)
    css = _re.sub(r"\s+", " ", css)
    css = _re.sub(r"\s*([{};])\s*", r"\1", css)
    return css.strip()


_DARK_MIN = _minify_css(_DARK_CSS_BODY)
APPLE_DESIGN_SYSTEM_CSS = _minify_css(APPLE_DESIGN_SYSTEM_CSS)
FEED_CARD_CSS = _minify_css(FEED_CARD_CSS)
AUTH_CSS = _minify_css(AUTH_CSS)
