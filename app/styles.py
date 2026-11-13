"""
Cấu hình giao diện và typography cho cổng thẩm định tín dụng.
"""

import streamlit as st


def inject_enterprise_css():
    st.markdown(
        """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        background-color: #F8FAFC;
        color: #0F172A;
    }

    /* Layout spacing */
    .block-container {
        padding-top: 0.75rem !important;
        padding-bottom: 1.5rem !important;
        padding-left: 1.75rem !important;
        padding-right: 1.75rem !important;
        max-width: 1600px !important;
    }

    /* Streamlit default header reset */
    header[data-testid="stHeader"] {
        height: 0px !important;
        min-height: 0px !important;
        background: transparent !important;
    }
    div[data-testid="stToolbar"] {
        display: none !important;
    }

    /* Tabs navigation */
    div[data-testid="stTabs"] > div:first-child {
        background-color: #FFFFFF;
        padding: 6px 8px;
        border-radius: 10px;
        border: 1px solid #E2E8F0;
        gap: 8px;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
        margin-bottom: 0.5rem;
    }

    button[data-baseweb="tab"] {
        border-radius: 7px !important;
        padding: 8px 16px !important;
        font-size: 0.78rem !important;
        font-weight: 600 !important;
        color: #475569 !important;
        background-color: transparent !important;
        border: 1px solid transparent !important;
        transition: all 0.15s ease !important;
        height: 36px !important;
    }

    button[data-baseweb="tab"]:hover {
        color: #0F172A !important;
        background-color: #F1F5F9 !important;
    }

    button[data-baseweb="tab"][aria-selected="true"] {
        background-color: #1D4ED8 !important;
        color: #FFFFFF !important;
        box-shadow: 0 2px 6px rgba(29, 78, 216, 0.25) !important;
    }

    /* Hide default tab indicator */
    div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] {
        display: none !important;
    }

    /* Border container styling */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0 !important;
        border-radius: 12px !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
        padding: 0.95rem 1.1rem !important;
        margin-bottom: 4px !important;
    }

    /* Standard vertical spacing */
    div[data-testid="stVerticalBlock"] {
        gap: 0.72rem !important;
    }

    /* Action buttons */
    div.stButton > button[kind="primary"] {
        background: linear-gradient(180deg, #2563EB 0%, #1D4ED8 100%) !important;
        color: #FFFFFF !important;
        border: 1px solid #1E40AF !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 0.8rem !important;
        padding: 0.45rem 1rem !important;
        box-shadow: 0 1px 2px rgba(29, 78, 216, 0.2) !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background: #1E40AF !important;
    }

    div.stButton > button[kind="secondary"] {
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 0.78rem !important;
        border: 1px solid #CBD5E1 !important;
        color: #334155 !important;
        background-color: #FFFFFF !important;
    }

    /* Form labels */
    label[data-testid="stWidgetLabel"] p {
        font-size: 0.78rem !important;
        font-weight: 600 !important;
        color: #334155 !important;
    }

    /* Queue card radio options */
    .st-key-queue_radio,
    .st-key-queue_radio > div,
    .st-key-queue_radio div[data-testid="stRadio"],
    .st-key-queue_radio div[data-testid="stRadioGroup"] {
        width: 100% !important;
    }

    .st-key-queue_radio div[data-testid="stRadioGroup"] {
        display: flex !important;
        flex-direction: column !important;
        gap: 8px !important;
        width: 100% !important;
    }

    .st-key-queue_radio div[data-testid="stRadioGroup"] > div {
        width: 100% !important;
        display: flex !important;
    }

    .st-key-queue_radio [data-testid="stRadioOption"] {
        width: 100% !important;
        min-width: 100% !important;
        min-height: 56px !important;
        height: auto !important;
        background-color: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 10px !important;
        padding: 9px 14px !important;
        margin: 0 !important;
        display: flex !important;
        align-items: center !important;
        box-sizing: border-box !important;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03) !important;
        cursor: pointer !important;
        transition: all 0.15s ease !important;
    }

    .st-key-queue_radio [data-testid="stRadioOption"]:hover {
        border-color: #93C5FD !important;
        background-color: #F8FAFC !important;
        box-shadow: 0 3px 8px rgba(37, 99, 235, 0.06) !important;
        transform: translateY(-1px);
    }

    .st-key-queue_radio [data-testid="stRadioOption"][data-selected="true"],
    .st-key-queue_radio div[data-testid="stRadioGroup"] > div[data-selected="true"] [data-testid="stRadioOption"],
    .st-key-queue_radio [data-testid="stRadioOption"]:has(input:checked) {
        border: 1.5px solid #1D4ED8 !important;
        border-left: 4px solid #1D4ED8 !important;
        background: linear-gradient(180deg, #F0F7FF 0%, #E0EFFF 100%) !important;
        box-shadow: 0 2px 8px rgba(29, 78, 216, 0.12) !important;
    }

    /* Radio button circle hidden for modern list card appearance */
    .st-key-queue_radio [data-testid="stRadioOption"] span:first-child,
    .st-key-queue_radio [data-testid="stRadioOption"] input,
    .st-key-queue_radio [data-testid="stRadioOption"] div[class*="e1dm8mpf4"] {
        display: none !important;
        width: 0px !important;
        height: 0px !important;
        margin: 0px !important;
    }

    .st-key-queue_radio [data-testid="stRadioOption"] > div {
        width: 100% !important;
        display: flex !important;
        align-items: center !important;
    }

    .st-key-queue_radio [data-testid="stRadioOption"] div[data-testid="stMarkdownContainer"] {
        width: 100% !important;
        flex: 1 1 auto !important;
        overflow: hidden !important;
    }
    .st-key-queue_radio [data-testid="stRadioOption"] div[data-testid="stMarkdownContainer"] p {
        width: 100% !important;
        margin: 0 !important;
        line-height: 1.4 !important;
        white-space: nowrap !important;
        text-overflow: ellipsis !important;
        overflow: hidden !important;
    }
    .st-key-queue_radio [data-testid="stRadioOption"] div[data-testid="stMarkdownContainer"] p:first-child {
        font-size: 0.84rem !important;
        font-weight: 700 !important;
        color: #0F172A !important;
        display: flex !important;
        justify-content: space-between !important;
        align-items: center !important;
        width: 100% !important;
    }
    .st-key-queue_radio [data-testid="stRadioOption"] div[data-testid="stMarkdownContainer"] p:last-child {
        font-size: 0.74rem !important;
        color: #64748B !important;
        margin-top: 3px !important;
    }

    .st-key-queue_radio [data-testid="stRadioOption"] code {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.72rem !important;
        font-weight: 700 !important;
        padding: 2px 8px !important;
        border-radius: 6px !important;
        background-color: #F1F5F9 !important;
        color: #334155 !important;
        border: 1px solid #E2E8F0 !important;
        letter-spacing: 0.02em !important;
    }

    .st-key-queue_radio [data-testid="stRadioOption"][data-selected="true"] code,
    .st-key-queue_radio [data-testid="stRadioOption"]:has(input:checked) code {
        background-color: #FFFFFF !important;
        color: #1D4ED8 !important;
        border-color: #BFDBFE !important;
        box-shadow: 0 1px 2px rgba(29, 78, 216, 0.1) !important;
    }

    /* Decision button segment */
    .st-key-decision_radio,
    .st-key-decision_radio > div,
    .st-key-decision_radio div[data-testid="stRadio"],
    .st-key-decision_radio div[data-testid="stRadioGroup"] {
        width: 100% !important;
    }

    .st-key-decision_radio div[data-testid="stRadioGroup"] {
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        justify-content: space-between !important;
        align-items: stretch !important;
        gap: 8px !important;
        width: 100% !important;
    }

    .st-key-decision_radio div[data-testid="stRadioGroup"] > div {
        flex: 1 1 0 !important;
        width: 0 !important;
        min-width: 0 !important;
        display: flex !important;
    }

    .st-key-decision_radio [data-testid="stRadioOption"] {
        flex: 1 1 100% !important;
        width: 100% !important;
        min-width: 0 !important;
        max-width: 100% !important;
        min-height: 40px !important;
        height: 40px !important;
        background-color: #FFFFFF !important;
        border: 1.5px solid #CBD5E1 !important;
        border-radius: 8px !important;
        padding: 4px 6px !important;
        margin: 0px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        text-align: center !important;
        box-sizing: border-box !important;
        cursor: pointer !important;
        white-space: nowrap !important;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04) !important;
        transition: all 0.15s ease !important;
    }

    /* Radio button appearance reset */
    .st-key-decision_radio [data-testid="stRadioOption"] span,
    .st-key-decision_radio [data-testid="stRadioOption"] input,
    .st-key-decision_radio [data-testid="stRadioOption"] div[class*="e1dm8mpf4"] {
        display: none !important;
        width: 0px !important;
        height: 0px !important;
    }

    .st-key-decision_radio [data-testid="stRadioOption"] > div {
        width: 100% !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 0 !important;
    }

    .st-key-decision_radio [data-testid="stRadioOption"]:hover {
        border-color: #3B82F6 !important;
        background-color: #F8FAFC !important;
    }

    .st-key-decision_radio [data-testid="stRadioOption"][data-selected="true"],
    .st-key-decision_radio div[data-testid="stRadioGroup"] > div[data-selected="true"] [data-testid="stRadioOption"],
    .st-key-decision_radio [data-testid="stRadioOption"]:has(input:checked) {
        border: 2px solid #1D4ED8 !important;
        background: linear-gradient(180deg, #EFF6FF 0%, #DBEAFE 100%) !important;
        box-shadow: 0 0 0 1px #1D4ED8 !important;
    }

    .st-key-decision_radio [data-testid="stRadioOption"] div[data-testid="stMarkdownContainer"] {
        width: 100% !important;
        text-align: center !important;
    }

    .st-key-decision_radio [data-testid="stRadioOption"] div[data-testid="stMarkdownContainer"] p {
        font-size: 0.78rem !important;
        font-weight: 600 !important;
        color: #1E293B !important;
        white-space: nowrap !important;
        text-align: center !important;
        margin: 0 !important;
    }

    .st-key-decision_radio [data-testid="stRadioOption"][data-selected="true"] p,
    .st-key-decision_radio div[data-testid="stRadioGroup"] > div[data-selected="true"] p,
    .st-key-decision_radio [data-testid="stRadioOption"]:has(input:checked) p {
        color: #1D4ED8 !important;
        font-weight: 700 !important;
    }

    /* Utility classes */
    .mono {
        font-family: 'JetBrains Mono', monospace;
        font-variant-numeric: tabular-nums;
    }

    /* Sticky header container */
    div[data-testid="stElementContainer"]:has(.enterprise-header),
    div[data-testid="element-container"]:has(.enterprise-header),
    div:has(> .enterprise-header) {
        position: sticky !important;
        top: 0px !important;
        z-index: 999999 !important;
        background-color: #F8FAFC !important;
        padding-top: 4px !important;
        padding-bottom: 4px !important;
    }

    .enterprise-header {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 10px 18px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 2px 10px rgba(15, 23, 42, 0.08) !important;
        margin-bottom: 8px;
    }
    .kpi-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 12px 16px;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
    }
    .section-title {
        font-size: 0.76rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: #334155;
        display: flex;
        align-items: center;
        gap: 6px;
        margin-bottom: 6px;
    }
    .kv-row {
        display: flex;
        justify-content: space-between;
        padding: 6px 0;
        border-bottom: 1px solid #F1F5F9;
        font-size: 0.8rem;
    }
    .kv-row:last-child {
        border-bottom: none;
    }
    .kv-label {
        color: #64748B;
    }
    .kv-val {
        font-weight: 600;
        color: #0F172A;
    }
</style>
""",
        unsafe_allow_html=True,
    )


def render_top_header():
    """Header ghim cố định ở đầu trang, chuẩn thương hiệu Home Credit."""
    from app.data_adapter import get_db_vendor_label

    is_live = st.session_state.get("is_live_db", False)
    if is_live:
        vendor_label = get_db_vendor_label()
        status_pill = (
            f'<div style="display:flex; align-items:center; gap:6px; background:#ECFDF5; '
            f'border:1px solid #A7F3D0; border-radius:999px; padding:4px 11px; '
            f'font-size:0.72rem; font-weight:600; color:#065F46;">'
            f'<span style="width:7px; height:7px; border-radius:50%; background:#10B981; display:inline-block;"></span>'
            f'{vendor_label} Live DWH • 307,511 hồ sơ</div>'
        )
    else:
        status_pill = (
            '<div style="display:flex; align-items:center; gap:6px; background:#FFFBEB; '
            'border:1px solid #FDE68A; border-radius:999px; padding:4px 11px; '
            'font-size:0.72rem; font-weight:600; color:#92400E;">'
            '<span style="width:7px; height:7px; border-radius:50%; background:#F59E0B; display:inline-block;"></span>'
            'Offline Mode • Cohort mẫu</div>'
        )

    st.markdown(
        f"""
<div class="enterprise-header">
    <div style="display:flex; align-items:center; gap:12px;">
        <div style="width:38px; height:38px; border-radius:8px; background:#1D4ED8; color:#FFF; font-weight:700; font-size:0.92rem; display:flex; align-items:center; justify-content:center; box-shadow: 0 2px 4px rgba(29,78,216,0.2);">
            HC
        </div>
        <div>
            <div style="font-weight:700; font-size:1.02rem; color:#0F172A; letter-spacing:-0.01em;">
                CỔNG THẨM ĐỊNH TÍN DỤNG & HỖ TRỢ QUYẾT ĐỊNH (DSS)
            </div>
            <div style="font-size:0.7rem; color:#64748B;">
                Đơn vị nguồn chuẩn hóa SI (K = 10³, M = 10⁶, B = 10⁹) • Mô hình Giải thích được ML
            </div>
        </div>
    </div>
    <div style="display:flex; align-items:center; gap:10px;">
        {status_pill}
        <div style="display:flex; align-items:center; gap:8px; background:#EFF6FF; border:1px solid #DBEAFE; border-radius:8px; padding:5px 12px;">
            <div style="width:26px; height:26px; border-radius:50%; background:#1D4ED8; color:#FFF; font-size:0.7rem; font-weight:700; display:flex; align-items:center; justify-content:center;">
                OF
            </div>
            <div style="line-height:1.2;">
                <div style="font-size:0.78rem; font-weight:700; color:#1E3A8A;">Officer</div>
                <div style="font-size:0.65rem; color:#3B82F6; font-weight:500;">Cán bộ thẩm định rủi ro</div>
            </div>
        </div>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )
