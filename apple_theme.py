# Modern Apple Design System CSS
APPLE_DESIGN_SYSTEM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=SF+Pro+Display:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    :root {
        --apple-font: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Inter", -apple-system, sans-serif;
        --apple-font-mono: "JetBrains Mono", SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        --apple-bg: #F5F5F7;
        --apple-card-bg: #FFFFFF;
        --apple-border: rgba(0, 0, 0, 0.07);
        --apple-border-subtle: rgba(0, 0, 0, 0.04);
        --apple-text-primary: #1D1D1F;
        --apple-text-secondary: #6E6E73;
        --apple-text-tertiary: #86868B;
        --apple-accent: #0071E3;
        --apple-accent-hover: #0077ED;
        --apple-accent-soft: rgba(0, 113, 227, 0.06);
        --apple-radius-sm: 8px;
        --apple-radius-md: 12px;
        --apple-radius-lg: 16px;
        --apple-radius-pill: 9999px;
        --apple-shadow-card: 0 1px 3px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.02);
        --apple-shadow-hover: 0 8px 24px rgba(0, 0, 0, 0.06), 0 1px 3px rgba(0, 0, 0, 0.02);
        --apple-ease: cubic-bezier(0.16, 1, 0.3, 1);
    }

    /* Global Typography & Smoothing */
    html, body, .stMarkdown, p, label, h1, h2, h3, h4, h5, h6 {
        font-family: var(--apple-font) !important;
        -webkit-font-smoothing: antialiased !important;
        -moz-osx-font-smoothing: grayscale !important;
        color: var(--apple-text-primary);
    }

    /* Clean App Background */
    [data-testid="stAppViewContainer"], .main {
        background-color: var(--apple-bg) !important;
    }

    /* Main Container Padding */
    .block-container {
        padding-top: 1.25rem !important;
        padding-bottom: 3.5rem !important;
        max-width: 1280px !important;
    }

    hr {
        border-color: rgba(0, 0, 0, 0.06) !important;
        margin: 1.25rem 0 !important;
    }

    /* Apple Top Navigation / Header */
    .apple-top-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 14px 22px;
        margin-bottom: 16px;
        background: rgba(255, 255, 255, 0.85);
        backdrop-filter: blur(20px) saturate(180%);
        -webkit-backdrop-filter: blur(20px) saturate(180%);
        border: 1px solid rgba(0, 0, 0, 0.06);
        border-radius: var(--apple-radius-lg);
        box-shadow: var(--apple-shadow-card);
    }

    .apple-top-title-group {
        display: flex;
        align-items: center;
        gap: 12px;
    }

    .apple-flag-icon {
        font-size: 1.8rem;
        line-height: 1;
        display: inline-block;
    }

    .apple-top-title {
        font-size: 1.28rem !important;
        font-weight: 700 !important;
        color: var(--apple-text-primary) !important;
        letter-spacing: -0.02em !important;
        margin: 0 !important;
        line-height: 1.15 !important;
    }

    .apple-top-subtitle {
        font-size: 0.8rem !important;
        color: var(--apple-text-secondary) !important;
        font-weight: 450 !important;
        margin: 2px 0 0 0 !important;
        line-height: 1.2 !important;
    }

    .apple-top-status {
        display: inline-flex;
        align-items: center;
        gap: 7px;
        background: rgba(16, 185, 129, 0.07);
        border: 1px solid rgba(16, 185, 129, 0.2);
        padding: 5px 12px;
        border-radius: var(--apple-radius-pill);
    }

    .apple-live-pulse {
        width: 6px;
        height: 6px;
        background-color: #10B981;
        border-radius: 50%;
        box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.2);
        animation: applePulse 2s infinite;
    }

    @keyframes applePulse {
        0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.5); }
        70% { transform: scale(1); box-shadow: 0 0 0 5px rgba(16, 185, 129, 0); }
        100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }

    .apple-status-text {
        font-size: 0.74rem;
        font-weight: 600;
        color: #047857;
        letter-spacing: 0.01em;
    }

    /* Apple Segmented Control (Tabs) */
    div[data-baseweb="tab-list"], div[role="tablist"] {
        background: rgba(0, 0, 0, 0.05) !important;
        padding: 4px !important;
        border-radius: 12px !important;
        gap: 4px !important;
        border: none !important;
        margin-bottom: 18px !important;
        display: flex !important;
        width: 100% !important;
        box-sizing: border-box !important;
    }

    button[data-baseweb="tab"], div[data-testid="stTab"], [role="tab"] {
        font-family: var(--apple-font) !important;
        border-radius: 9px !important;
        padding: 8px 14px !important;
        font-weight: 550 !important;
        font-size: 0.85rem !important;
        color: var(--apple-text-secondary) !important;
        border: none !important;
        background: transparent !important;
        transition: all 0.18s var(--apple-ease) !important;
        cursor: pointer !important;
        flex: 1 1 auto !important;
        text-align: center !important;
        justify-content: center !important;
        white-space: nowrap !important;
    }

    button[data-baseweb="tab"]:hover, div[data-testid="stTab"]:hover, [role="tab"]:hover {
        color: var(--apple-text-primary) !important;
        background: rgba(255, 255, 255, 0.6) !important;
    }

    button[data-baseweb="tab"][aria-selected="true"], 
    div[data-testid="stTab"][aria-selected="true"], 
    [role="tab"][aria-selected="true"] {
        background: #FFFFFF !important;
        color: var(--apple-text-primary) !important;
        font-weight: 650 !important;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.03) !important;
    }

    div[data-baseweb="tab-border"], div[data-baseweb="tab-highlight"], [data-testid="stTabHighlight"] {
        display: none !important;
    }

    /* Metric Cards - Apple Style */
    div[data-testid="stMetric"] {
        background: #FFFFFF !important;
        border: 1px solid rgba(0, 0, 0, 0.06) !important;
        border-radius: var(--apple-radius-md) !important;
        padding: 14px 18px !important;
        box-shadow: var(--apple-shadow-card) !important;
        transition: all 0.2s var(--apple-ease) !important;
    }

    div[data-testid="stMetric"]:hover {
        border-color: rgba(0, 113, 227, 0.3) !important;
        box-shadow: var(--apple-shadow-hover) !important;
    }

    div[data-testid="stMetricLabel"], div[data-testid="stMetricLabel"] * {
        font-size: 0.76rem !important;
        font-weight: 600 !important;
        color: var(--apple-text-tertiary) !important;
        letter-spacing: 0.02em !important;
        text-transform: uppercase !important;
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: clip !important;
    }

    div[data-testid="stMetricValue"], div[data-testid="stMetricValue"] * {
        font-size: 1.4rem !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
        color: var(--apple-text-primary) !important;
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: clip !important;
    }

    /* Article Cards - Clean Apple Design */
    .apple-news-card {
        background: #FFFFFF;
        border-radius: var(--apple-radius-md);
        border: 1px solid rgba(0, 0, 0, 0.06);
        border-left: 3.5px solid #CBD5E1;
        box-shadow: var(--apple-shadow-card);
        padding: 16px 20px;
        margin-bottom: 12px;
        transition: all 0.2s var(--apple-ease);
        position: relative;
    }

    .apple-news-card:hover {
        box-shadow: var(--apple-shadow-hover);
        border-color: rgba(0, 113, 227, 0.25);
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
        gap: 6px;
        margin-bottom: 8px;
    }

    .apple-card-title {
        margin: 0 0 8px 0 !important;
        font-size: 1.08rem !important;
        font-weight: 650 !important;
        line-height: 1.4 !important;
        letter-spacing: -0.015em !important;
    }

    .apple-card-title a {
        color: var(--apple-text-primary) !important;
        text-decoration: none !important;
        transition: color 0.15s ease;
    }

    .apple-card-title a:hover {
        color: var(--apple-accent) !important;
    }

    .apple-card-summary {
        color: var(--apple-text-secondary);
        font-size: 0.88rem;
        line-height: 1.5;
        margin: 0 0 10px 0;
    }

    /* Badges & Tags */
    .portal-tag {
        background: #1D1D1F;
        color: #FFFFFF;
        padding: 3px 10px;
        border-radius: var(--apple-radius-pill);
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: -0.01em;
    }

    .indian-portal-tag {
        background: #FFF7ED;
        color: #C2410C;
        border: 1px solid #FFEDD5;
        padding: 3px 10px;
        border-radius: var(--apple-radius-pill);
        font-size: 0.72rem;
        font-weight: 600;
    }

    .time-badge {
        background: #F5F5F7;
        color: var(--apple-text-secondary);
        border: 1px solid rgba(0, 0, 0, 0.05);
        padding: 3px 9px;
        border-radius: var(--apple-radius-pill);
        font-size: 0.72rem;
        font-weight: 500;
    }

    .cat-badge-india { background: #FEF3C7; color: #92400E; border: 1px solid #FDE68A; padding: 3px 9px; border-radius: var(--apple-radius-pill); font-size: 0.72rem; font-weight: 600; }
    .cat-badge-china { background: #FEE2E2; color: #991B1B; border: 1px solid #FECACA; padding: 3px 9px; border-radius: var(--apple-radius-pill); font-size: 0.72rem; font-weight: 600; }
    .cat-badge-pakistan { background: #DCFCE7; color: #166534; border: 1px solid #BBF7D0; padding: 3px 9px; border-radius: var(--apple-radius-pill); font-size: 0.72rem; font-weight: 600; }
    .cat-badge-bangladesh { background: #CFFAFE; color: #155E75; border: 1px solid #A5F3FC; padding: 3px 9px; border-radius: var(--apple-radius-pill); font-size: 0.72rem; font-weight: 600; }
    .cat-badge-internal { background: #EEF2FF; color: #3730A3; border: 1px solid #C7D2FE; padding: 3px 9px; border-radius: var(--apple-radius-pill); font-size: 0.72rem; font-weight: 600; }
    .cat-badge-external { background: #F3E8FF; color: #6B21A8; border: 1px solid #E9D5FF; padding: 3px 9px; border-radius: var(--apple-radius-pill); font-size: 0.72rem; font-weight: 600; }
    .cat-badge-economy { background: #ECFDF5; color: #047857; border: 1px solid #A7F3D0; padding: 3px 9px; border-radius: var(--apple-radius-pill); font-size: 0.72rem; font-weight: 600; }
    .cat-badge-others { background: #F1F5F9; color: #475569; border: 1px solid #CBD5E1; padding: 3px 9px; border-radius: var(--apple-radius-pill); font-size: 0.72rem; font-weight: 600; }
    .cat-badge-international { background: #EDE9FE; color: #5B21B6; border: 1px solid #DDD6FE; padding: 3px 9px; border-radius: var(--apple-radius-pill); font-size: 0.72rem; font-weight: 600; }

    .sec-tag-chip {
        background: #F5F5F7;
        color: var(--apple-text-secondary);
        border: 1px solid rgba(0, 0, 0, 0.05);
        padding: 2px 7px;
        border-radius: 6px;
        font-size: 0.7rem;
        font-weight: 500;
    }

    .conf-review-badge {
        background: #FEF3C7;
        color: #92400E;
        border: 1px solid #FDE68A;
        padding: 3px 8px;
        border-radius: var(--apple-radius-pill);
        font-size: 0.72rem;
        font-weight: 650;
    }

    /* Action Buttons in Cards */
    .apple-card-cta {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        background: #F5F5F7;
        color: var(--apple-text-primary) !important;
        border: 1px solid rgba(0, 0, 0, 0.08);
        padding: 5px 12px;
        border-radius: var(--apple-radius-pill);
        font-size: 0.76rem;
        font-weight: 600;
        text-decoration: none !important;
        transition: all 0.18s var(--apple-ease);
    }

    .apple-card-cta:hover {
        background: var(--apple-accent);
        color: #FFFFFF !important;
        border-color: var(--apple-accent);
    }

    .apple-wa-share-btn {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: #F0FDF4;
        color: #15803D !important;
        border: 1px solid #DCFCE7;
        padding: 4.5px 11px;
        border-radius: var(--apple-radius-pill);
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: -0.005em;
        text-decoration: none !important;
        transition: all 0.16s var(--apple-ease);
    }

    .apple-wa-share-btn svg {
        width: 13.5px;
        height: 13.5px;
        flex-shrink: 0;
        fill: currentColor;
    }

    .apple-wa-share-btn:hover {
        background: #16A34A;
        color: #FFFFFF !important;
        border-color: #16A34A;
        box-shadow: 0 2px 6px rgba(22, 163, 74, 0.2);
    }

    /* Filter Banner */
    .apple-filter-banner {
        background: #FFFFFF;
        border: 1px solid rgba(0, 0, 0, 0.06);
        border-radius: var(--apple-radius-md);
        padding: 10px 16px;
        margin-bottom: 14px;
        font-size: 0.82rem;
        color: var(--apple-text-secondary);
        display: flex;
        align-items: center;
        gap: 10px;
        box-shadow: var(--apple-shadow-card);
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #FAFAFC !important;
        border-right: 1px solid rgba(0, 0, 0, 0.06) !important;
    }

    /* Global Input & Select fields */
    div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
        border-radius: 10px !important;
        border-color: rgba(0, 0, 0, 0.1) !important;
        background-color: #FFFFFF !important;
        transition: all 0.18s var(--apple-ease) !important;
    }

    div[data-baseweb="input"] > div:focus-within, div[data-baseweb="select"] > div:focus-within {
        border-color: var(--apple-accent) !important;
        box-shadow: 0 0 0 3px rgba(0, 113, 227, 0.12) !important;
    }

    /* Primary and Secondary Buttons */
    .stButton>button,
    div[data-testid="stDownloadButton"]>button {
        border-radius: 10px !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        padding: 7px 16px !important;
        transition: all 0.18s var(--apple-ease) !important;
        border: 1px solid rgba(0, 0, 0, 0.08) !important;
    }

    .stButton>button[kind="primary"],
    div[data-testid="stDownloadButton"]>button[kind="primary"],
    button[data-testid="baseButton-primary"],
    button[data-testid="stBaseButton-primary"] {
        background-color: #526A85 !important;
        background: #526A85 !important;
        color: #FFFFFF !important;
        border: none !important;
        box-shadow: 0 1px 3px rgba(82, 106, 133, 0.25) !important;
    }

    .stButton>button[kind="primary"] *,
    div[data-testid="stDownloadButton"]>button[kind="primary"] *,
    button[data-testid="baseButton-primary"] *,
    button[data-testid="stBaseButton-primary"] * {
        color: #FFFFFF !important;
    }

    .stButton>button[kind="primary"]:hover,
    div[data-testid="stDownloadButton"]>button[kind="primary"]:hover,
    button[data-testid="baseButton-primary"]:hover,
    button[data-testid="stBaseButton-primary"]:hover {
        background-color: #405872 !important;
        background: #405872 !important;
        color: #FFFFFF !important;
        transform: translateY(-1px);
        box-shadow: 0 3px 8px rgba(64, 88, 114, 0.35) !important;
    }

    /* X Posts Card - Matching render_apple_x_post_card() DOM classes */
    .apple-x-card,
    .x-post-card {
        background: #FFFFFF;
        border-radius: var(--apple-radius-md);
        border: 1px solid rgba(0, 0, 0, 0.06);
        box-shadow: var(--apple-shadow-card);
        padding: 16px 20px;
        margin-bottom: 12px;
        transition: all 0.2s var(--apple-ease);
    }

    .apple-x-card:hover,
    .x-post-card:hover {
        box-shadow: var(--apple-shadow-hover);
        border-color: rgba(82, 106, 133, 0.28);
    }

    .x-post-header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 12px;
        flex-wrap: wrap;
    }

    .x-author-box {
        display: flex;
        align-items: center;
        gap: 10px;
        min-width: 0;
    }

    .x-author-avatar,
    .x-avatar {
        width: 36px !important;
        height: 36px !important;
        min-width: 36px !important;
        border-radius: 50% !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        color: #FFFFFF !important;
        font-weight: 700 !important;
        font-size: 0.78rem !important;
        letter-spacing: 0.02em;
        flex-shrink: 0 !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
    }

    .x-author-meta {
        display: flex;
        flex-direction: column;
        line-height: 1.25;
        min-width: 0;
    }

    .x-author-name {
        font-size: 0.92rem;
        font-weight: 650;
        color: var(--apple-text-primary);
        display: inline-flex;
        align-items: center;
        gap: 4px;
    }

    .x-author-handle {
        font-size: 0.76rem;
        color: var(--apple-text-secondary);
        font-weight: 450;
    }

    .x-type-badge {
        color: #526A85;
        font-weight: 600;
    }

    .x-verified-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 15px;
        height: 15px;
        border-radius: 50%;
        background: #1D9BF0;
        color: #FFFFFF;
        font-weight: 700;
        font-size: 0.62rem;
        line-height: 1;
    }

    .x-post-text {
        font-size: 0.93rem;
        line-height: 1.55;
        color: var(--apple-text-primary);
        margin: 10px 0 12px 0;
        white-space: pre-wrap;
        word-break: break-word;
    }

    .x-engagement-bar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding-top: 10px;
        border-top: 1px solid rgba(0, 0, 0, 0.05);
        gap: 10px;
        flex-wrap: wrap;
    }

    .x-metrics-group {
        display: inline-flex;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
    }

    .x-stat-chip,
    .x-metric-item {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        color: #64748B;
        font-size: 0.75rem;
        font-weight: 550;
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        padding: 2px 8px;
        border-radius: 999px;
    }

    .x-sentiment-badge {
        display: inline-flex;
        align-items: center;
        padding: 2.5px 9px;
        border-radius: 999px;
        font-size: 0.71rem;
        font-weight: 650;
        letter-spacing: 0.01em;
    }
    .x-sentiment-neutral {
        background: #F1F5F9;
        color: #475569;
        border: 1px solid #CBD5E1;
    }
    .x-sentiment-positive {
        background: #ECFDF5;
        color: #047857;
        border: 1px solid #A7F3D0;
    }
    .x-sentiment-alert {
        background: #FEF2F2;
        color: #B91C1C;
        border: 1px solid #FECACA;
    }

    .x-cta-link {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        background: #F5F5F7;
        color: var(--apple-text-primary) !important;
        border: 1px solid rgba(0, 0, 0, 0.08);
        padding: 4.5px 12px;
        border-radius: var(--apple-radius-pill);
        font-size: 0.75rem;
        font-weight: 600;
        text-decoration: none !important;
        transition: all 0.16s var(--apple-ease);
    }
    .x-cta-link:hover {
        background: #526A85;
        color: #FFFFFF !important;
        border-color: #526A85;
    }

    .apple-counter-badge {
        display: inline-block;
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 6px 12px;
        font-size: 0.78rem;
        color: #475569;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
    }

    /* Hide noisy (?) help tooltip icons inside compact sidebar labels */
    section[data-testid="stSidebar"] [data-testid="stTooltipIcon"] {
        display: none !important;
    }

    /* Ensure all sidebar inner input/select surfaces are pure crisp white (#FFFFFF) */
    section[data-testid="stSidebar"] div[data-baseweb="base-input"],
    section[data-testid="stSidebar"] div[data-baseweb="input"],
    section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
        background-color: #FFFFFF !important;
    }

    /* ==========================================
       APPLE TOOLBAR SIDEBAR & COMPACT CONTROLS
       ========================================== */
    section[data-testid="stSidebar"] {
        background-color: #F8FAFC !important;
        border-right: 1px solid #E2E8F0 !important;
        min-width: 300px !important;
    }

    section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
        padding-top: 1rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        padding-bottom: 1.5rem !important;
    }

    /* Reduce vertical gap between sidebar blocks */
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
        gap: 0.48rem !important;
    }

    /* Compact Sidebar Header & Section Titles */
    .cp-header-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 4px;
    }
    .cp-title {
        display: inline-flex;
        align-items: center;
        gap: 7px;
        font-size: 0.92rem;
        font-weight: 700;
        color: #1E293B;
        letter-spacing: -0.015em;
    }
    .cp-sync-time {
        font-size: 0.7rem;
        font-weight: 500;
        color: #64748B;
    }

    .cp-sec-label {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 0.71rem;
        font-weight: 650;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin: 8px 0 6px 0;
    }

    .cp-divider {
        height: 1px;
        background-color: #E2E8F0;
        margin: 6px 0;
        width: 100%;
    }

    /* Compact Widget Labels inside Sidebar */
    section[data-testid="stSidebar"] label[data-testid="stWidgetLabel"] {
        min-height: 16px !important;
        margin-bottom: 2px !important;
    }
    section[data-testid="stSidebar"] label[data-testid="stWidgetLabel"] p {
        font-size: 0.74rem !important;
        font-weight: 600 !important;
        color: #475569 !important;
        letter-spacing: -0.005em !important;
    }

    /* Compact Inputs & Dropdowns in Sidebar (36px height, zero truncation) */
    section[data-testid="stSidebar"] div[data-baseweb="input"] > div,
    section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
        min-height: 36px !important;
        height: 36px !important;
        border-radius: 8px !important;
        border: 1px solid #DCE5EF !important;
        background-color: #FFFFFF !important;
        font-size: 0.81rem !important;
        padding: 0 8px !important;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.02) !important;
    }

    section[data-testid="stSidebar"] div[data-baseweb="select"] span,
    section[data-testid="stSidebar"] div[data-baseweb="select"] div {
        font-size: 0.81rem !important;
        color: #1E293B !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }

    section[data-testid="stSidebar"] input {
        font-size: 0.81rem !important;
        color: #1E293B !important;
        padding: 0 !important;
    }

    /* Compact Primary & Secondary Buttons in Sidebar */
    section[data-testid="stSidebar"] .stButton > button {
        min-height: 35px !important;
        height: 35px !important;
        padding: 0 12px !important;
        font-size: 0.8rem !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        border: 1px solid #DCE5EF !important;
        background-color: #FFFFFF !important;
        color: #334155 !important;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.02) !important;
    }

    section[data-testid="stSidebar"] .stButton > button:hover {
        border-color: #CBD5E1 !important;
        background-color: #F1F5F9 !important;
        color: #0F172A !important;
    }

    section[data-testid="stSidebar"] .stButton > button[kind="primary"],
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"],
    section[data-testid="stSidebar"] button[data-testid="baseButton-primary"] {
        background-color: #526A85 !important;
        background: #526A85 !important;
        color: #FFFFFF !important;
        border: none !important;
        box-shadow: 0 1px 3px rgba(82, 106, 133, 0.25) !important;
    }
    section[data-testid="stSidebar"] .stButton > button[kind="primary"] *,
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] *,
    section[data-testid="stSidebar"] button[data-testid="baseButton-primary"] * {
        color: #FFFFFF !important;
    }
    section[data-testid="stSidebar"] .stButton > button[kind="primary"]:hover,
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]:hover,
    section[data-testid="stSidebar"] button[data-testid="baseButton-primary"]:hover {
        background-color: #405872 !important;
        background: #405872 !important;
        transform: none !important;
        box-shadow: 0 2px 6px rgba(64, 88, 114, 0.3) !important;
    }

    /* Segmented Control & Radio (Timeframe Presets - Single Row 4-Segment Bar) */
    section[data-testid="stSidebar"] [data-testid="stRadio"] > div[role="radiogroup"] {
        background-color: #EDF2F7 !important;
        padding: 3px !important;
        border-radius: 8px !important;
        border: 1px solid #E2E8F0 !important;
        display: grid !important;
        grid-template-columns: repeat(4, 1fr) !important;
        gap: 2px !important;
        width: 100% !important;
        margin-top: 2px !important;
    }
    section[data-testid="stSidebar"] [data-testid="stRadio"] > div[role="radiogroup"] > label {
        margin: 0 !important;
        padding: 3px 1px !important;
        min-height: 28px !important;
        height: 28px !important;
        border-radius: 6px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        cursor: pointer !important;
        background: transparent !important;
        border: none !important;
        transition: all 0.15s ease !important;
        overflow: hidden !important;
    }
    section[data-testid="stSidebar"] [data-testid="stRadio"] > div[role="radiogroup"] > label > div:first-child {
        display: none !important;
    }
    section[data-testid="stSidebar"] [data-testid="stRadio"] > div[role="radiogroup"] > label p,
    section[data-testid="stSidebar"] [data-testid="stRadio"] > div[role="radiogroup"] > label div {
        font-size: 0.68rem !important;
        font-weight: 600 !important;
        color: #475569 !important;
        margin: 0 !important;
        padding: 0 !important;
        white-space: nowrap !important;
        word-break: normal !important;
        overflow: visible !important;
        line-height: 1 !important;
        text-align: center !important;
    }
    section[data-testid="stSidebar"] [data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) {
        background-color: #FFFFFF !important;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08) !important;
    }
    section[data-testid="stSidebar"] [data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) p,
    section[data-testid="stSidebar"] [data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) div {
        color: #1E293B !important;
        font-weight: 700 !important;
    }

    /* Live Tracking Toggle Switch - Muted Slate Blue (#526A85) instead of default red */
    section[data-testid="stSidebar"] label[data-baseweb="checkbox"] > div:first-child {
        background-color: #CBD5E1 !important;
    }
    section[data-testid="stSidebar"] label[data-baseweb="checkbox"]:has(input:checked) > div:first-child {
        background-color: #526A85 !important;
    }

    /* Compact Live Tracking Status Bar */
    .cp-live-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 5px 10px;
        margin-top: 2px;
        font-size: 0.74rem;
    }
    .cp-range-text {
        color: #334155;
        font-weight: 550;
        letter-spacing: -0.01em;
    }
    .cp-status-badge-live {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        background: #ECFDF5;
        color: #047857;
        border: 1px solid #A7F3D0;
        padding: 1px 7px;
        border-radius: 999px;
        font-size: 0.66rem;
        font-weight: 700;
        letter-spacing: 0.03em;
    }
    .cp-status-badge-paused {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        background: #F1F5F9;
        color: #475569;
        border: 1px solid #CBD5E1;
        padding: 1px 7px;
        border-radius: 999px;
        font-size: 0.66rem;
        font-weight: 700;
        letter-spacing: 0.03em;
    }

    /* Active Filter Chips (st.pills) */
    section[data-testid="stSidebar"] [data-testid="stPills"] button,
    [data-testid="stPills"] button {
        min-height: 24px !important;
        height: 24px !important;
        padding: 0 8px !important;
        font-size: 0.72rem !important;
        font-weight: 600 !important;
        border-radius: 999px !important;
        background-color: #EEF2F6 !important;
        color: #334155 !important;
        border: 1px solid #CBD5E1 !important;
    }

    /* Compact Expander for Monitored Sources · 52 */
    section[data-testid="stSidebar"] details {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 8px !important;
        padding: 0 !important;
    }
    section[data-testid="stSidebar"] details summary {
        padding: 7px 10px !important;
        font-size: 0.78rem !important;
        font-weight: 600 !important;
        color: #334155 !important;
    }
    section[data-testid="stSidebar"] details > div {
        padding: 4px 10px 10px 10px !important;
        font-size: 0.75rem !important;
    }

    /* Streamlit Data Editor and Table Cell Padding & Visual Polish */
    div[data-testid="stDataEditor"],
    div[data-testid="stDataFrame"] {
        border-radius: 10px !important;
        border: 1px solid #E2E8F0 !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04) !important;
        overflow: hidden !important;
        background: #FFFFFF !important;
    }
    div[data-testid="stDataEditor"] canvas,
    div[data-testid="stDataFrame"] canvas {
        border-radius: 8px !important;
    }
    
    /* In-Tab Source Control Panel Card */
    .source-control-bar {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 12px 16px 8px 16px;
        margin-bottom: 16px;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
    }
    .source-control-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 10px;
        padding-bottom: 8px;
        border-bottom: 1px solid #F1F5F9;
    }
    .source-control-title {
        font-size: 0.88rem;
        font-weight: 700;
        color: #1E293B;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .source-control-stats {
        font-size: 0.76rem;
        font-weight: 600;
        color: #64748B;
    }

</style>
"""

