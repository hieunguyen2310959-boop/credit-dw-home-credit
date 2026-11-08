"""
TAB 4: NHẬT KÝ KIỂM TOÁN & VẬN HÀNH (AUDIT TRAIL & ETL RUNS)
Lưu vết các quyết định phê duyệt/từ chối của Cán bộ (Officer) vào bảng app.credit_decisions
và giám sát tiến trình trích xuất nạp dữ liệu ETL (ops.etl_runs).
"""

import pandas as pd
import streamlit as st


def render_tab_audit():
    """Render giao diện chính của Tab 4 (Audit Trail & ETL Monitoring)."""
    n_cohort = len(st.session_state.applications)

    with st.container(border=True):
        st.markdown(
            '<div class="section-title">📜 NHẬT KÝ RA QUYẾT ĐỊNH CỦA CÁN BỘ'
            " (AUDIT TRAIL - APP.CREDIT_DECISIONS)</div>",
            unsafe_allow_html=True,
        )
        audit_df = pd.DataFrame(st.session_state.audit_logs)
        st.dataframe(audit_df, use_container_width=True, hide_index=True)

    with st.container(border=True):
        st.markdown(
            '<div class="section-title">⚙️ GIÁM SÁT TIẾN TRÌNH ETL KHO DỮ LIỆU'
            " (OPS.ETL_RUNS - ĐÃ CHUẨN HÓA BADGE NGHIỆP VỤ)</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
<table style="width:100%; border-collapse:collapse; font-size:0.78rem; text-align:left;">
    <thead>
        <tr style="background:#F8FAFC; border-bottom:1px solid #E2E8F0; color:#475569;">
            <th style="padding:10px 12px;">Mã Đợt ETL</th>
            <th style="padding:10px 12px;">Bắt Đầu / Hoàn Thành</th>
            <th style="padding:10px 12px;">Trạng Thái</th>
            <th style="padding:10px 12px;">Thống Kê Dòng Dữ Liệu (Row Counts)</th>
            <th style="padding:10px 12px;">Chứng Thực Toàn Vẹn (Manifest SHA-256)</th>
        </tr>
    </thead>
    <tbody>
        <tr style="border-bottom:1px solid #F1F5F9;">
            <td class="mono" style="padding:10px 12px; font-weight:700;">#ETL-02</td>
            <td class="mono" style="padding:10px 12px; color:#475569;">2026-11-08 00:15:00 <span style="color:#94A3B8;">(1.2s)</span></td>
            <td style="padding:10px 12px;">
                <span style="background:#ECFDF5; color:#059669; border:1px solid #A7F3D0; padding:2px 8px; border-radius:999px; font-weight:600; font-size:0.7rem;">
                    ● Succeeded
                </span>
            </td>
            <td style="padding:10px 12px;">
                <span class="mono" style="background:#F1F5F9; padding:2px 8px; border-radius:6px; margin-right:4px;">raw_apps: <b>{n_cohort}</b></span>
                <span class="mono" style="background:#EFF6FF; color:#1D4ED8; padding:2px 8px; border-radius:6px; margin-right:4px;">dw_mart: <b>{n_cohort}</b></span>
                <span class="mono" style="background:#ECFDF5; color:#059669; padding:2px 8px; border-radius:6px;">clean_rate: <b>100%</b></span>
            </td>
            <td class="mono" style="padding:10px 12px; color:#475569;">
                <code style="background:#F8FAFC; border:1px solid #E2E8F0; padding:2px 6px; border-radius:4px;">app_train: 52e96b89...1112</code>
                <code style="background:#F8FAFC; border:1px solid #E2E8F0; padding:2px 6px; border-radius:4px; margin-left:4px;">prev_app: 5046cd65...7ee0</code>
            </td>
        </tr>
    </tbody>
</table>
""",
            unsafe_allow_html=True,
        )
