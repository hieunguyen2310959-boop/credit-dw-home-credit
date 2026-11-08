"""
CỔNG THẨM ĐỊNH TÍN DỤNG & HỖ TRỢ QUYẾT ĐỊNH (ENTERPRISE DSS)
Phân hệ Web & Tích hợp DSS (Thành viên C) — Tương thích chuẩn Contract v1 (DW & ML).
Chạy ứng dụng bằng lệnh: streamlit run app/main.py
"""

# ==============================================================================
# 0. ĐẢM BẢO SYS.PATH CHỨA THƯ MỤC GỐC & THƯ MỤC ML (TRƯỚC KHI IMPORT APP)
# ==============================================================================
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if not (PROJECT_ROOT / "ml").exists():
    PROJECT_ROOT = Path(__file__).resolve().parent
ML_PATH = PROJECT_ROOT / "ml"

for p in (PROJECT_ROOT, ML_PATH):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import streamlit as st

# ==============================================================================
# 1. IMPORT CÁC MÔ-ĐUN NỘI BỘ TỪ PACKAGE APP
# ==============================================================================
from app.styles import inject_enterprise_css, render_top_header
from app.data_adapter import init_session_data
from app.views.tab_core import render_tab_core
from app.views.tab_olap import render_tab_olap
from app.views.tab_whatif import render_tab_whatif
from app.views.tab_audit import render_tab_audit

# ==============================================================================
# 2. CẤU HÌNH TRANG (PAGE CONFIG) & TIÊM CSS
# ==============================================================================
st.set_page_config(
    page_title="Home Credit DSS • Cổng Thẩm Định Tín Dụng",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_enterprise_css()
init_session_data()

# ==============================================================================
# 3. RENDER HEADER CỐ ĐỊNH & HỆ THỐNG TABS
# ==============================================================================
render_top_header()

tab_core, tab_olap, tab_whatif, tab_audit = st.tabs([
    "🛡️ THẨM ĐỊNH HỒ SƠ (CORE DSS)",
    "📊 BÁO CÁO PHÂN TÍCH OLAP",
    "🎛️ MÔ PHỎNG KỊCH BẢN (WHAT-IF)",
    "📜 NHẬT KÝ KIỂM TOÁN & VẬN HÀNH",
])

with tab_core:
    render_tab_core()

with tab_olap:
    render_tab_olap()

with tab_whatif:
    render_tab_whatif()

with tab_audit:
    render_tab_audit()
