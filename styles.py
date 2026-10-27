"""Global CSS injected into every Streamlit page. Implements CONTRACTS.md section 4.
Enhanced with Liquid Glass, Glassmorphism, 3D Depth, Funky & Stylish Typography,
Scroll Animations, and UPI Holographic styling.
"""

import config

DARK_THEME_CSS = """
<style>
    /* ==========================================================================
       1. FONTS IMPORT & GLOBAL CSS VARIABLES
       ========================================================================== */
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&family=Outfit:wght@300;400;500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Space+Grotesk:wght@400;500;600;700&family=Syne:wght@600;700;800&display=swap');

    :root {
        --bg-space: #070A12;
        --bg-canvas: #0A0E17;
        --glass-surface: rgba(15, 23, 42, 0.65);
        --glass-surface-hover: rgba(30, 41, 59, 0.75);
        --glass-border: rgba(255, 255, 255, 0.12);
        --glass-border-specular: rgba(255, 255, 255, 0.28);
        --glass-glow-violet: rgba(139, 92, 246, 0.28);
        --glass-glow-cyan: rgba(6, 182, 212, 0.22);
        --glass-glow-rose: rgba(236, 72, 153, 0.25);

        --neon-violet: #8B5CF6;
        --neon-purple-glow: #A78BFA;
        --neon-cyan: #06B6D4;
        --neon-sky: #38BDF8;
        --neon-emerald: #10B981;
        --neon-amber: #F59E0B;
        --neon-orange: #F97316;
        --neon-crimson: #EF4444;
        --neon-pink: #EC4899;

        --font-display: 'Syne', -apple-system, sans-serif;
        --font-heading: 'Space Grotesk', -apple-system, sans-serif;
        --font-body: 'Outfit', 'Plus Jakarta Sans', -apple-system, sans-serif;
        --font-mono: 'JetBrains Mono', monospace;
    }

    /* ==========================================================================
       2. BASE STYLING & AMBIENT LIQUID BACKGROUND
       ========================================================================== */
    .stApp {
        background-color: var(--bg-space);
        background-image: 
            radial-gradient(circle at 15% 15%, rgba(139, 92, 246, 0.15) 0%, transparent 45%),
            radial-gradient(circle at 85% 25%, rgba(6, 182, 212, 0.12) 0%, transparent 40%),
            radial-gradient(circle at 50% 85%, rgba(236, 72, 153, 0.10) 0%, transparent 50%),
            radial-gradient(rgba(255, 255, 255, 0.04) 1px, transparent 1px);
        background-size: 100% 100%, 100% 100%, 100% 100%, 36px 36px;
        background-attachment: fixed;
        color: #F9FAFB;
        font-family: var(--font-body);
        -webkit-font-smoothing: antialiased;
        overflow-x: hidden;
    }

    #MainMenu, footer, header { visibility: hidden; height: 0; }

    /* Custom Futuristic Scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    ::-webkit-scrollbar-track {
        background: rgba(10, 14, 23, 0.7);
    }
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(180deg, rgba(139, 92, 246, 0.5), rgba(6, 182, 212, 0.5));
        border-radius: 999px;
        border: 2px solid rgba(10, 14, 23, 0.8);
    }
    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(180deg, #8B5CF6, #06B6D4);
        box-shadow: 0 0 10px rgba(139, 92, 246, 0.8);
    }

    /* Layout Container */
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 2.5rem;
        max-width: 1680px;
    }

    /* Prevent Streamlit from dimming or flickering brightness during auto-refresh reruns */
    [data-stale="true"],
    .stElementContainer[data-stale="true"],
    .element-container[data-stale="true"],
    [data-testid="stAppViewBlockContainer"][data-stale="true"],
    div[data-testid="stVerticalBlock"] > div[data-stale="true"],
    div[data-testid="stHorizontalBlock"] > div[data-stale="true"] {
        opacity: 1 !important;
        filter: none !important;
        transition: none !important;
    }

    /* Hide Streamlit top-right running spinner that causes header jumping */
    [data-testid="stStatusWidget"] {
        visibility: hidden !important;
    }

    /* ==========================================================================
       3. LIQUID GLASS & GLASSMORPHISM SURFACES
       ========================================================================== */
    .liquid-glass {
        background: var(--glass-surface);
        backdrop-filter: blur(24px) saturate(210%);
        -webkit-backdrop-filter: blur(24px) saturate(210%);
        border: 1px solid var(--glass-border);
        box-shadow: 
            0 16px 36px -8px rgba(0, 0, 0, 0.6),
            inset 0 1px 1px 0 var(--glass-border-specular),
            0 0 25px -5px var(--glass-glow-violet);
        border-radius: 16px;
        position: relative;
        overflow: hidden;
        transition: all 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
    }

    .liquid-glass::before {
        content: '';
        position: absolute;
        top: 0; left: -150%; width: 100%; height: 100%;
        background: linear-gradient(
            90deg,
            transparent,
            rgba(255, 255, 255, 0.08),
            rgba(255, 255, 255, 0.18),
            rgba(255, 255, 255, 0.08),
            transparent
        );
        transform: skewX(-25deg);
        pointer-events: none;
        transition: 0.75s ease;
    }

    .liquid-glass:hover::before {
        left: 200%;
    }

    .liquid-glass:hover {
        transform: translateY(-4px) scale(1.01);
        border-color: rgba(255, 255, 255, 0.22);
        box-shadow: 
            0 24px 48px -10px rgba(0, 0, 0, 0.75),
            inset 0 1px 1px 0 rgba(255, 255, 255, 0.45),
            0 0 35px -2px rgba(139, 92, 246, 0.45);
    }

    /* ==========================================================================
       4. KPI CARDS (LIQUID GLASS + 3D DEPTH)
       ========================================================================== */
    .kpi-card {
        background: var(--glass-surface);
        backdrop-filter: blur(22px) saturate(200%);
        -webkit-backdrop-filter: blur(22px) saturate(200%);
        border: 1px solid var(--glass-border);
        border-radius: 16px;
        padding: 22px 24px;
        height: 100%;
        position: relative;
        overflow: hidden;
        box-shadow: 
            0 12px 30px -6px rgba(0, 0, 0, 0.55),
            inset 0 1px 1px 0 var(--glass-border-specular),
            0 0 20px -8px rgba(139, 92, 246, 0.2);
        transition: all 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
        transform-style: preserve-3d;
        perspective: 800px;
    }

    .kpi-card::after {
        content: '';
        position: absolute;
        bottom: 0; left: 0; right: 0; height: 3px;
        background: linear-gradient(90deg, transparent, var(--neon-violet), var(--neon-cyan), transparent);
        opacity: 0.6;
        transition: opacity 0.3s ease;
    }

    .kpi-card:hover {
        transform: translateY(-5px);
        border-color: rgba(167, 139, 250, 0.4);
        box-shadow: 
            0 20px 45px -8px rgba(0, 0, 0, 0.7),
            inset 0 1px 1px 0 rgba(255, 255, 255, 0.5),
            0 0 30px rgba(139, 92, 246, 0.4);
    }

    .kpi-card:hover::after {
        opacity: 1;
        height: 4px;
    }

    .kpi-label {
        font-family: var(--font-heading);
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #94A3B8;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 6px;
    }

    .kpi-value {
        font-family: var(--font-display);
        font-size: 36px;
        font-weight: 800;
        letter-spacing: -0.03em;
        line-height: 1.1;
        background: linear-gradient(135deg, #FFFFFF 20%, #E2E8F0 60%, #A78BFA 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-variant-numeric: tabular-nums;
        text-shadow: 0 0 25px rgba(255, 255, 255, 0.15);
    }

    .kpi-delta {
        font-family: var(--font-mono);
        font-size: 12px;
        font-weight: 600;
        margin-top: 8px;
        color: var(--neon-emerald);
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 3px 8px;
        border-radius: 6px;
        background: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.2);
    }

    .kpi-delta.neg {
        color: var(--neon-crimson);
        background: rgba(239, 68, 68, 0.1);
        border-color: rgba(239, 68, 68, 0.2);
    }

    /* ==========================================================================
       5. SCORE BADGES & PULSES
       ========================================================================== */
    .score-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 4px 12px;
        border-radius: 999px;
        font-family: var(--font-mono);
        font-size: 12px;
        font-weight: 800;
        letter-spacing: 0.04em;
        font-variant-numeric: tabular-nums;
        backdrop-filter: blur(10px);
        transition: all 0.25s ease;
    }

    .score-safe {
        background: rgba(16, 185, 129, 0.18);
        color: #34D399;
        border: 1px solid rgba(16, 185, 129, 0.5);
        box-shadow: 0 0 12px rgba(16, 185, 129, 0.3);
    }

    .score-monitor {
        background: rgba(245, 158, 11, 0.18);
        color: #FBBF24;
        border: 1px solid rgba(245, 158, 11, 0.5);
        box-shadow: 0 0 12px rgba(245, 158, 11, 0.3);
    }

    .score-stepup {
        background: rgba(249, 115, 22, 0.2);
        color: #FB923C;
        border: 1px solid rgba(249, 115, 22, 0.6);
        box-shadow: 0 0 14px rgba(249, 115, 22, 0.35);
    }

    .score-block {
        background: rgba(239, 68, 68, 0.22);
        color: #F87171;
        border: 1px solid rgba(239, 68, 68, 0.7);
        box-shadow: 0 0 18px rgba(239, 68, 68, 0.5);
        animation: criticalPulse 1.8s infinite ease-in-out;
    }

    @keyframes criticalPulse {
        0%, 100% { box-shadow: 0 0 12px rgba(239, 68, 68, 0.4); transform: scale(1); }
        50% { box-shadow: 0 0 24px rgba(239, 68, 68, 0.85); transform: scale(1.04); }
    }

    .live-dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #10B981;
        margin-right: 7px;
        box-shadow: 0 0 10px #10B981;
        animation: liveBeacon 1.6s cubic-bezier(0.4, 0, 0.6, 1) infinite;
        vertical-align: middle;
    }

    @keyframes liveBeacon {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.35; transform: scale(1.4); }
    }

    /* ==========================================================================
       6. LIVE ALERT ROWS & STREAM WITH SCROLL ANIMATIONS
       ========================================================================== */
    .alert-row {
        display: flex;
        align-items: center;
        gap: 14px;
        padding: 12px 18px;
        border-left: 4px solid #334155;
        background: rgba(15, 23, 42, 0.65);
        backdrop-filter: blur(18px) saturate(180%);
        -webkit-backdrop-filter: blur(18px) saturate(180%);
        border-radius: 10px;
        border-top: 1px solid rgba(255, 255, 255, 0.06);
        border-bottom: 1px solid rgba(0, 0, 0, 0.3);
        margin-bottom: 8px;
        font-size: 13px;
        font-variant-numeric: tabular-nums;
        transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
        position: relative;
        overflow: hidden;
    }

    .alert-row:hover {
        background: rgba(30, 41, 59, 0.85);
        transform: translateX(4px) scale(1.005);
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4), inset 0 1px 1px rgba(255, 255, 255, 0.15);
    }

    .alert-row.block {
        border-left-color: var(--neon-crimson);
        background: linear-gradient(90deg, rgba(239, 68, 68, 0.12) 0%, rgba(15, 23, 42, 0.7) 35%);
    }
    .alert-row.block:hover {
        box-shadow: 0 0 20px rgba(239, 68, 68, 0.25);
    }

    .alert-row.stepup {
        border-left-color: var(--neon-orange);
        background: linear-gradient(90deg, rgba(249, 115, 22, 0.10) 0%, rgba(15, 23, 42, 0.7) 35%);
    }

    .alert-row.monitor {
        border-left-color: var(--neon-amber);
        background: linear-gradient(90deg, rgba(245, 158, 11, 0.08) 0%, rgba(15, 23, 42, 0.7) 35%);
    }

    .alert-row.safe {
        border-left-color: var(--neon-emerald);
    }

    .alert-time {
        color: #94A3B8;
        width: 72px;
        font-family: var(--font-mono);
        font-size: 12px;
    }

    .alert-acct {
        color: #E2E8F0;
        width: 200px;
        font-family: var(--font-mono);
        font-size: 12px;
        letter-spacing: -0.01em;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .alert-amt {
        color: #FFFFFF;
        width: 100px;
        font-family: var(--font-display);
        font-weight: 700;
        font-size: 14px;
        text-align: right;
        margin-right: 6px;
    }

    .alert-act {
        color: #CBD5E1;
        width: 110px;
        font-family: var(--font-heading);
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        text-align: right;
    }

    /* ==========================================================================
       7. EXPLANATION BARS & DECISION TRACE
       ========================================================================== */
    .explain-row {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 12px;
        font-size: 13px;
    }

    .explain-label {
        flex: 0 0 220px;
        color: #CBD5E1;
        font-family: var(--font-heading);
        font-weight: 500;
    }

    .explain-bar-wrap {
        flex: 1;
        height: 10px;
        background: rgba(30, 41, 59, 0.7);
        border-radius: 999px;
        overflow: hidden;
        border: 1px solid rgba(255, 255, 255, 0.08);
        padding: 1px;
    }

    .explain-bar {
        height: 100%;
        background: linear-gradient(90deg, #8B5CF6, #38BDF8);
        border-radius: 999px;
        box-shadow: 0 0 10px rgba(139, 92, 246, 0.6);
        transition: width 0.8s cubic-bezier(0.16, 1, 0.3, 1);
    }

    .explain-val {
        flex: 0 0 60px;
        text-align: right;
        color: #F8FAFC;
        font-family: var(--font-mono);
        font-weight: 700;
        font-variant-numeric: tabular-nums;
    }

    /* ==========================================================================
       8. SECTION HEADERS & BRAND ACCENTS
       ========================================================================== */
    .section-header {
        font-family: var(--font-heading);
        font-size: 13px;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #94A3B8;
        margin: 22px 0 12px 0;
        padding-bottom: 8px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .section-header::before {
        content: '';
        display: inline-block;
        width: 4px;
        height: 14px;
        background: linear-gradient(180deg, var(--neon-violet), var(--neon-cyan));
        border-radius: 2px;
        box-shadow: 0 0 8px var(--neon-violet);
    }

    /* ==========================================================================
       9. TABS NAVIGATION (LIQUID PILLS WITH UNDERGLOW)
       ========================================================================== */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: rgba(15, 23, 42, 0.7);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        padding: 6px;
        border-radius: 14px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.5), inset 0 1px 1px rgba(255, 255, 255, 0.15);
        margin-bottom: 20px;
    }

    .stTabs [data-baseweb="tab"] {
        background: transparent;
        color: #94A3B8;
        border-radius: 10px;
        padding: 10px 22px;
        font-family: var(--font-heading);
        font-weight: 700;
        font-size: 13px;
        letter-spacing: 0.04em;
        border: 1px solid transparent;
        transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
    }

    .stTabs [data-baseweb="tab"]:hover {
        color: #F8FAFC;
        background: rgba(255, 255, 255, 0.06);
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(139, 92, 246, 0.35), rgba(6, 182, 212, 0.25)) !important;
        color: #FFFFFF !important;
        border: 1px solid rgba(167, 139, 250, 0.5) !important;
        box-shadow: 0 0 20px rgba(139, 92, 246, 0.35), inset 0 1px 1px rgba(255, 255, 255, 0.3) !important;
    }

    /* ==========================================================================
       10. STREAMLIT BUTTONS & INTERACTIVE TACTILE CONTROLS
       ========================================================================== */
    .stButton > button {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.8), rgba(15, 23, 42, 0.9));
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        color: #F8FAFC;
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 12px;
        font-family: var(--font-heading);
        font-weight: 700;
        font-size: 13px;
        letter-spacing: 0.03em;
        padding: 9px 18px;
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.2);
        transition: all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
    }

    .stButton > button:hover {
        background: linear-gradient(135deg, rgba(139, 92, 246, 0.45), rgba(6, 182, 212, 0.35));
        border-color: #A78BFA;
        color: #FFFFFF;
        transform: translateY(-2px);
        box-shadow: 0 10px 25px rgba(139, 92, 246, 0.4), inset 0 1px 1px rgba(255, 255, 255, 0.4);
    }

    .stButton > button:active {
        transform: translateY(1px);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
    }

    /* Tactical Action Buttons */
    .btn-block-action button {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.4), rgba(185, 28, 28, 0.6)) !important;
        border-color: #EF4444 !important;
        box-shadow: 0 0 18px rgba(239, 68, 68, 0.4) !important;
    }
    .btn-block-action button:hover {
        box-shadow: 0 0 30px rgba(239, 68, 68, 0.75) !important;
    }

    .btn-stepup-action button {
        background: linear-gradient(135deg, rgba(249, 115, 22, 0.35), rgba(194, 65, 12, 0.5)) !important;
        border-color: #F97316 !important;
        box-shadow: 0 0 16px rgba(249, 115, 22, 0.35) !important;
    }

    .btn-allow-action button {
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.35), rgba(4, 120, 87, 0.5)) !important;
        border-color: #10B981 !important;
        box-shadow: 0 0 16px rgba(16, 185, 129, 0.35) !important;
    }

    /* ==========================================================================
       11. DATAFRAMES & TABLES
       ========================================================================== */
    .stDataFrame {
        background: var(--glass-surface);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid var(--glass-border);
        border-radius: 14px;
        overflow: hidden;
        box-shadow: 0 12px 30px rgba(0, 0, 0, 0.5), inset 0 1px 1px rgba(255, 255, 255, 0.15);
    }

    /* Form Controls & Radios */
    .stSelectbox > div > div {
        background: rgba(15, 23, 42, 0.7) !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 10px !important;
        color: #F8FAFC !important;
    }

    .stRadio > div {
        background: rgba(15, 23, 42, 0.6);
        padding: 8px 12px;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.08);
    }

    /* UPI Attack Simulator Preset Pill */
    .upi-pill-btn {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 14px;
        border-radius: 12px;
        font-family: var(--font-heading);
        font-size: 12px;
        font-weight: 700;
        cursor: pointer;
        transition: all 0.25s ease;
        border: 1px solid rgba(255, 255, 255, 0.12);
        background: rgba(15, 23, 42, 0.75);
    }
</style>
"""


def _check_range(score: int) -> None:
    """Precondition shared by the score helpers. Raises ValueError if out of range."""
    if not isinstance(score, int) or isinstance(score, bool):
        raise ValueError(f"score must be an int in [0, 100], got {score!r}")
    if not (0 <= score <= 100):
        raise ValueError(f"score out of range [0, 100]: {score}")


def score_class(score: int) -> str:
    """Return the CSS class name for a score badge.

    Returns one of: score-safe, score-monitor, score-stepup, score-block.
    Raises ValueError if score is out of range.
    """
    _check_range(score)
    if score < config.THRESHOLD_MONITOR:
        return "score-safe"
    if score < config.THRESHOLD_STEPUP:
        return "score-monitor"
    if score < config.THRESHOLD_BLOCK:
        return "score-stepup"
    return "score-block"


def row_class(score: int) -> str:
    """Return the CSS class name for an alert row. Raises ValueError if out of range."""
    _check_range(score)
    if score < config.THRESHOLD_MONITOR:
        return "safe"
    if score < config.THRESHOLD_STEPUP:
        return "monitor"
    if score < config.THRESHOLD_BLOCK:
        return "stepup"
    return "block"


def score_color(score: int) -> str:
    """Return a hex color string consistent with the score band. Raises ValueError if out of range."""
    _check_range(score)
    if score < config.THRESHOLD_MONITOR:
        return config.COLOR_SAFE
    if score < config.THRESHOLD_STEPUP:
        return config.COLOR_MONITOR
    if score < config.THRESHOLD_BLOCK:
        return config.COLOR_STEPUP
    return config.COLOR_BLOCK
