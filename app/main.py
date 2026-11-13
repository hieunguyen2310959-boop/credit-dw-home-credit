"""
Cổng thẩm định tín dụng và hỗ trợ ra quyết định (Enterprise Credit Decision Support System - DSS).
"""
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
from app.styles import inject_enterprise_css, render_top_header
from app.data_adapter import init_session_data
from app.views.tab_core import render_tab_core
from app.views.tab_olap import render_tab_olap
from app.views.tab_whatif import render_tab_whatif
from app.views.tab_audit import render_tab_audit

st.set_page_config(
    page_title="Home Credit DSS • Cổng Thẩm Định Tín Dụng",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_enterprise_css()
init_session_data()

render_top_header()

tab_core, tab_olap, tab_whatif, tab_audit = st.tabs([
    "THẨM ĐỊNH HỒ SƠ (CORE DSS)",
    "BÁO CÁO PHÂN TÍCH OLAP",
    "MÔ PHỎNG KỊCH BẢN (WHAT-IF)",
    "NHẬT KÝ KIỂM TOÁN & VẬN HÀNH",
])

with tab_core:
    render_tab_core()

with tab_olap:
    render_tab_olap()

with tab_whatif:
    render_tab_whatif()

with tab_audit:
    render_tab_audit()
