"""
TAB 1: THẨM ĐỊNH HỒ SƠ TÍN DỤNG (CORE DSS)
Bao gồm thanh KPI Ribbon, Hàng đợi hồ sơ (Queue), Panel quyết định, Đồng hồ rủi ro Gauge và Hồ sơ 360 độ.
"""

from datetime import datetime
import plotly.graph_objects as go
import streamlit as st
from app.data_adapter import REVIEW_THRESHOLD, DECLINE_THRESHOLD, MODEL_NAME_LABEL


def render_kpi_ribbon():
    """Hiển thị 4 chỉ số KPI quan trọng ở đầu Tab Thẩm định."""
    apps = st.session_state.applications
    total_apps = len(apps)
    total_credit = sum(a["credit"] for a in apps.values())
    labeled_apps = [a for a in apps.values() if a.get("target") is not None]
    labeled_count = len(labeled_apps)
    target_1_count = sum(1 for a in labeled_apps if a.get("target") == 1)
    done_count = sum(1 for a in apps.values() if a["status"] == "Đã duyệt")
    bad_rate = (target_1_count / labeled_count) * 100 if labeled_count else 0.0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f"""
<div class="kpi-card">
    <div style="font-size:0.68rem; font-weight:700; color:#64748B; text-transform:uppercase;">TỔNG HỒ SƠ TIẾP NHẬN</div>
    <div style="display:flex; align-items:baseline; gap:6px; margin-top:4px;">
        <span class="mono" style="font-size:1.55rem; font-weight:700; color:#0F172A;">{total_apps}</span>
        <span style="font-size:0.75rem; color:#64748B;">hồ sơ trong cohort</span>
    </div>
    <div style="font-size:0.7rem; color:#2563EB; font-weight:500; margin-top:4px;">⚡ Đúng chuẩn grain 1 dòng/hồ sơ</div>
</div>
""",
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            f"""
<div class="kpi-card">
    <div style="font-size:0.68rem; font-weight:700; color:#64748B; text-transform:uppercase;">TỔNG GIÁ TRỊ TÍN DỤNG ĐỀ NGHỊ</div>
    <div style="display:flex; align-items:baseline; gap:6px; margin-top:4px;">
        <span class="mono" style="font-size:1.55rem; font-weight:700; color:#0F172A;">{total_credit:,.1f}M</span>
        <span style="font-size:0.75rem; color:#64748B;">đơn vị nguồn</span>
    </div>
    <div style="font-size:0.7rem; color:#059669; font-weight:500; margin-top:4px;">✓ SUM(amt_credit) bảo toàn qua ETL</div>
</div>
""",
            unsafe_allow_html=True,
        )

    with c3:
        st.markdown(
            f"""
<div class="kpi-card">
    <div style="font-size:0.68rem; font-weight:700; color:#64748B; text-transform:uppercase;">TỶ LỆ KHÓ KHĂN THANH TOÁN (TARGET=1)</div>
    <div style="display:flex; align-items:baseline; gap:6px; margin-top:4px;">
        <span class="mono" style="font-size:1.55rem; font-weight:700; color:#DC2626;">{bad_rate:.1f}%</span>
        <span style="font-size:0.75rem; color:#64748B;">({target_1_count}/{labeled_count} hồ sơ có nhãn)</span>
    </div>
    <div style="font-size:0.7rem; color:#64748B; margin-top:4px;">Mẫu số: <code>COUNT(target)</code> (không tính tập test)</div>
</div>
""",
            unsafe_allow_html=True,
        )

    with c4:
        st.markdown(
            f"""
<div class="kpi-card">
    <div style="font-size:0.68rem; font-weight:700; color:#64748B; text-transform:uppercase;">TIẾN ĐỘ THẨM ĐỊNH CA</div>
    <div style="display:flex; align-items:baseline; gap:6px; margin-top:4px;">
        <span class="mono" style="font-size:1.55rem; font-weight:700; color:#059669;">{done_count} / {total_apps}</span>
        <span style="font-size:0.75rem; color:#64748B;">đã ghi nhận quyết định</span>
    </div>
    <div style="font-size:0.7rem; color:#64748B; margin-top:4px;">Lưu vết tại app.credit_decisions</div>
</div>
""",
            unsafe_allow_html=True,
        )


def create_gauge_chart(pd_score: float, risk_level: str):
    """Vẽ đồng hồ bán nguyệt hiển thị điểm rủi ro và các dải ngưỡng Policy chuẩn."""
    bar_color = (
        "#10B981"
        if risk_level == "LOW"
        else ("#F59E0B" if risk_level == "MEDIUM" else "#E11D48")
    )
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=pd_score,
            number={
                "valueformat": ".3f",
                "font": {
                    "size": 34,
                    "color": bar_color,
                    "family": "JetBrains Mono",
                },
            },
            title={
                "text": "ĐIỂM RỦI RO MÔ HÌNH (RISK SCORE)",
                "font": {"size": 11, "color": "#475569", "family": "Inter"},
            },
            gauge={
                "axis": {
                    "range": [0, 1],
                    "tickvals": [0, REVIEW_THRESHOLD, DECLINE_THRESHOLD, 0.5, 0.75, 1.0],
                    "tickfont": {"size": 10},
                },
                "bar": {"color": bar_color, "thickness": 0.32},
                "bgcolor": "#F8FAFC",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, REVIEW_THRESHOLD], "color": "#DCFCE7"},
                    {"range": [REVIEW_THRESHOLD, DECLINE_THRESHOLD], "color": "#FEF3C7"},
                    {"range": [DECLINE_THRESHOLD, 1.00], "color": "#FFE4E6"},
                ],
                "threshold": {
                    "line": {"color": "#DC2626", "width": 3},
                    "thickness": 0.8,
                    "value": DECLINE_THRESHOLD,
                },
            },
        )
    )
    fig.update_layout(
        height=225,
        margin=dict(l=24, r=24, t=44, b=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def render_tab_core():
    """Render giao diện chính của Tab 1 (Split-view 2 cột)."""
    render_kpi_ribbon()
    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    col_left, col_right = st.columns([4.2, 7.8], gap="large")

    # ================= CỘT TRÁI: HÀNG ĐỢI + QUYẾT ĐỊNH =================
    with col_left:
        with st.container(border=True):
            st.markdown(
                '<div class="section-title">📋 HÀNG ĐỢI THẨM ĐỊNH (QUEUE)</div>',
                unsafe_allow_html=True,
            )

            search_q = st.text_input(
                "Tìm kiếm nhanh",
                placeholder="Ví dụ: 1001, Nguyễn Văn An...",
                label_visibility="collapsed",
            )
            filter_status = st.selectbox(
                "Lọc trạng thái",
                ["Tất cả hồ sơ", "Chờ duyệt", "Đã duyệt"],
                label_visibility="collapsed",
            )

            filtered_ids = []
            for aid, app in st.session_state.applications.items():
                if (
                    filter_status != "Tất cả hồ sơ"
                    and app["status"] != filter_status
                ):
                    continue
                if (
                    search_q
                    and search_q.lower() not in aid.lower()
                    and search_q.lower() not in app["applicant"].lower()
                ):
                    continue
                filtered_ids.append(aid)

            if not filtered_ids:
                filtered_ids = list(st.session_state.applications.keys())

            def format_queue_option(aid):
                a = st.session_state.applications[aid]
                badge = "✓ Đã xử lý" if a["status"] == "Đã duyệt" else "Chờ duyệt"
                return (
                    f"**#{aid} • {a['applicant']}** &nbsp; `PD: {a['pd']:.3f}`\n\n"
                    f"{a['product']} • {a['credit']:.0f}M — {badge}"
                )

            st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

            selected_id = st.radio(
                "Chọn hồ sơ thẩm định:",
                options=filtered_ids,
                format_func=format_queue_option,
                label_visibility="collapsed",
                key="queue_radio",
            )

            # Reset ghi chú nháp và đồng bộ lựa chọn quyết định khi chuyển hồ sơ
            if selected_id != st.session_state.last_selected_id:
                st.session_state.last_selected_id = selected_id
                st.session_state.draft_note = ""
                st.session_state.decision_radio = st.session_state.applications[selected_id].get(
                    "default_decision", "✓ Phê duyệt"
                )

        active_app = st.session_state.applications[selected_id]

        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

        # Panel Quyết định của cán bộ (Ghim ngay bên dưới Queue)
        with st.container(border=True):
            st.markdown(
                f"""
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
    <span class="section-title" style="margin-bottom:0; font-size:0.75rem; white-space:nowrap;">⚖️ QUYẾT ĐỊNH CỦA CÁN BỘ</span>
    <span class="mono" style="background:#DBEAFE; color:#1D4ED8; font-size:0.72rem; font-weight:700; padding:2px 8px; border-radius:6px; white-space:nowrap;">
        Hồ sơ #{active_app['id']}
    </span>
</div>
""",
                unsafe_allow_html=True,
            )

            decision_options = [
                "✓ Phê duyệt",
                "👁 Xem xét thêm",
                "✕ Từ chối",
            ]
            cur_default = active_app.get("default_decision", "✓ Phê duyệt")
            if "decision_radio" not in st.session_state:
                st.session_state.decision_radio = cur_default

            chosen_decision = st.radio(
                "Lệnh quyết định tín dụng:",
                options=decision_options,
                horizontal=True,
                key="decision_radio",
                label_visibility="collapsed",
            )

            reason_map = {
                "✓ Phê duyệt": [
                    "PAS_01: Đạt toàn bộ tiêu chí khẩu vị rủi ro chuẩn",
                    "PAS_02: Phê duyệt có điều kiện (Giảm hạn mức)",
                ],
                "👁 Xem xét thêm": [
                    "REV_01: Yêu cầu bổ sung sao kê thu nhập 6 tháng",
                    "REV_02: Yêu cầu bổ sung người đồng trả nợ / bảo lãnh",
                ],
                "✕ Từ chối": [
                    "REJ_01: Hệ số tín dụng / thu nhập vượt trần quy định",
                    "REJ_02: Điểm rủi ro mô hình vượt ngưỡng từ chối",
                ],
            }

            chosen_reason = st.selectbox(
                "Mã lý do chuẩn hóa (Reason Code):",
                options=reason_map[chosen_decision],
            )

            col_lbl, col_autofill = st.columns([6.5, 3.5])
            with col_lbl:
                st.markdown(
                    '<span style="font-size:0.78rem; font-weight:600;'
                    ' color:#334155;">Ghi chú thẩm định & Căn cứ:</span>',
                    unsafe_allow_html=True,
                )
            with col_autofill:
                if st.button("✨ Điền mẫu nhanh", use_container_width=True):
                    if "Phê duyệt" in chosen_decision:
                        st.session_state.draft_note = (
                            f"Đồng ý cấp tín dụng {active_app['credit']}M cho"
                            f" KH {active_app['applicant']}. Điểm rủi ro"
                            f" {active_app['pd']:.3f} < {REVIEW_THRESHOLD:.2f}."
                        )
                    elif "Xem xét" in chosen_decision:
                        st.session_state.draft_note = (
                            f"Hồ sơ có điểm rủi ro {active_app['pd']:.3f} nằm"
                            f" trong vùng [{REVIEW_THRESHOLD:.2f}, {DECLINE_THRESHOLD:.2f})."
                            f" Cần xác minh thêm dòng tiền của KH {active_app['applicant']}."
                        )
                    else:
                        st.session_state.draft_note = (
                            f"Từ chối cấp tín dụng do điểm rủi ro"
                            f" {active_app['pd']:.3f} >= {DECLINE_THRESHOLD:.2f}"
                            " và hệ số tín dụng/thu nhập cao."
                        )

            note_val = st.text_area(
                "Ghi chú thẩm định",
                value=st.session_state.draft_note,
                height=72,
                placeholder=(
                    "Nhập căn cứ nghiệp vụ (VD: Thu nhập ổn định, đòn bẩy trong ngưỡng an toàn)..."
                ),
                label_visibility="collapsed",
            )

            col_act1, col_act2 = st.columns([1, 2.2])
            with col_act1:
                if st.button("🎛️ Thử What-If", use_container_width=True):
                    st.session_state.sim_selected_id = selected_id
                    st.toast(
                        f"Đã chọn sẵn hồ sơ #{selected_id} trong Tab 'Mô phỏng Kịch bản (What-If)'!",
                        icon="🎛️",
                    )
            with col_act2:
                if st.button(
                    "💾 LƯU QUYẾT ĐỊNH (SAVE)",
                    type="primary",
                    use_container_width=True,
                ):
                    st.session_state.applications[selected_id]["status"] = "Đã duyệt"
                    st.session_state.applications[selected_id]["default_decision"] = chosen_decision
                    st.session_state.audit_logs.insert(
                        0,
                        {
                            "Mã GD": f"DEC-{901 + len(st.session_state.audit_logs)}",
                            "Mã Hồ Sơ": f"#{selected_id}",
                            "Khách Hàng": active_app["applicant"],
                            "Quyết Định": chosen_decision.replace("✓ ", "").replace("👁 ", "").replace("✕ ", ""),
                            "Mã Lý Do": chosen_reason,
                            "Ghi Chú Nghiệp Vụ": (
                                note_val.strip()
                                if note_val.strip()
                                else "Ghi nhận quyết định theo quy trình thẩm định chuẩn."
                            ),
                            "Cán Bộ Thẩm Định": "Officer",
                            "Thời Gian Ghi Nhận": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        },
                    )
                    st.session_state.draft_note = ""
                    st.toast(
                        f"Đã lưu quyết định cho hồ sơ #{selected_id} vào bảng app.credit_decisions!",
                        icon="✅",
                    )
                    st.rerun()

    # ================= CỘT PHẢI: HỒ SƠ 360 ĐỘ CHI TIẾT =================
    with col_right:
        # 1. Banner Khuyến nghị Hệ thống — ĐỦ 3 CẤP ĐỘ RỦI RO (LOW / MEDIUM / HIGH)
        r_level = active_app["risk_level"]
        if r_level == "LOW":
            banner_bg = "#ECFDF5"
            banner_border = "#10B981"
            badge_bg = "#059669"
            rec_title = "Khuyến nghị Hệ thống: Phê Duyệt Hồ Sơ (APPROVE_SIMULATION)"
            rec_sub = (
                f"Điểm rủi ro mô hình nằm trong vùng an toàn"
                f" (risk_score = {active_app['pd']:.3f} < {REVIEW_THRESHOLD:.2f})."
            )
        elif r_level == "MEDIUM":
            banner_bg = "#FFFBEB"
            banner_border = "#F59E0B"
            badge_bg = "#D97706"
            rec_title = "Khuyến nghị Hệ thống: Thẩm Định Bổ Sung (REVIEW)"
            rec_sub = (
                f"Điểm rủi ro nằm trong vùng cần xem xét kỹ"
                f" ({REVIEW_THRESHOLD:.2f} ≤ risk_score = {active_app['pd']:.3f} < {DECLINE_THRESHOLD:.2f})."
                " Khuyến nghị kiểm tra chứng từ thu nhập hoặc chạy What-If."
            )
        else:
            banner_bg = "#FFF1F2"
            banner_border = "#F43F5E"
            badge_bg = "#E11D48"
            rec_title = "Khuyến nghị Hệ thống: Từ Chối Mô Phỏng (DECLINE_SIMULATION)"
            rec_sub = (
                f"Điểm rủi ro mô hình vượt ngưỡng từ chối"
                f" (risk_score = {active_app['pd']:.3f} ≥ {DECLINE_THRESHOLD:.2f})."
            )

        st.markdown(
            f"""
<div style="background:{banner_bg}; border:1px solid {banner_border}; border-left:5px solid {banner_border}; border-radius:12px; padding:14px 18px; margin-bottom: 14px;">
    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
        <div style="display:flex; align-items:center; gap:10px;">
            <span style="background:{badge_bg}; color:#FFFFFF; font-size:0.68rem; font-weight:700; padding:3px 10px; border-radius:999px; letter-spacing:0.04em;">
                MỨC RỦI RO: {r_level}
            </span>
            <span class="mono" style="font-size:0.76rem; font-weight:700; color:#1E293B;">
                KH: {active_app['applicant'].upper()} • #{active_app['id']}
            </span>
        </div>
        <div class="mono" style="font-size:0.72rem; font-weight:600; color:#334155; background:rgba(255,255,255,0.85); padding:3px 10px; border-radius:6px; border:1px solid rgba(15,23,42,0.08);">
            Model: {MODEL_NAME_LABEL} • SLA: {active_app['sla']}
        </div>
    </div>
    <div style="font-size:1.05rem; font-weight:700; color:#0F172A; margin-top:8px;">
        {rec_title}
    </div>
    <div style="font-size:0.78rem; font-weight:500; color:#334155; margin-top:2px;">
        {rec_sub}
    </div>
</div>
""",
            unsafe_allow_html=True,
        )

        # 2. Biểu đồ Gauge + Yếu tố ảnh hưởng chính (Log-Odds Contributions)
        with st.container(border=True):
            g_col, d_col = st.columns([4.8, 7.2], gap="medium")
            with g_col:
                st.plotly_chart(
                    create_gauge_chart(
                        active_app["pd"], active_app["risk_level"]
                    ),
                    use_container_width=True,
                    config={"displayModeBar": False},
                )
            with d_col:
                st.markdown(
                    '<div class="section-title" style="margin-top:4px;">🧠 YẾU'
                    " TỐ ĐÓNG GÓP LOG-ODDS CHÍNH (MODEL FACTORS):</div>",
                    unsafe_allow_html=True,
                )
                drivers_html = ""
                for feat, desc, val, dtype in active_app["drivers"]:
                    bg_c = "#ECFDF5" if dtype == "pos" else "#FFF1F2"
                    bd_c = "#A7F3D0" if dtype == "pos" else "#FECDD3"
                    tx_c = "#065F46" if dtype == "pos" else "#9F1239"
                    drivers_html += f"""
<div style="background:{bg_c}; border:1px solid {bd_c}; border-radius:8px; padding:9px 12px; margin-bottom:8px; display:flex; justify-content:space-between; align-items:center;">
    <div>
        <span class="mono" style="font-size:0.78rem; font-weight:700; color:{tx_c};">{feat}</span>
        <span style="font-size:0.74rem; font-weight:500; color:{tx_c}; margin-left:6px;">({desc})</span>
    </div>
    <span class="mono" style="font-size:0.8rem; font-weight:700; color:{tx_c};">{val}</span>
</div>
"""
                st.markdown(drivers_html, unsafe_allow_html=True)

        # 3. Tình hình Tài chính & Tỷ số Tín dụng / Thu nhập
        with st.container(border=True):
            leverage = active_app["credit"] / active_app["income"]
            lev_pct = min((leverage / 4.0) * 100, 100)
            lev_color = (
                "#10B981"
                if leverage <= 1.8
                else ("#F59E0B" if leverage <= 2.5 else "#E11D48")
            )
            lev_status = (
                "An toàn (≤ 1.8x)"
                if leverage <= 1.8
                else (
                    "Cảnh báo (1.8x - 2.5x)"
                    if leverage <= 2.5
                    else "Vượt ngưỡng cao (> 2.5x)"
                )
            )

            st.markdown(
                f"""
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
    <span class="section-title" style="margin-bottom:0;">📊 TÌNH HÌNH TÀI CHÍNH & HỆ SỐ TÍN DỤNG / THU NHẬP</span>
    <span style="background:#F1F5F9; color:#334155; font-size:0.72rem; font-weight:600; padding:2px 10px; border-radius:6px;">
        {active_app['product']}
    </span>
</div>
<div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:10px; margin-bottom:12px;">
    <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:10px 10px;">
        <div style="font-size:0.72rem; color:#64748B;">Thu nhập khai báo</div>
        <div class="mono" style="font-size:1.15rem; font-weight:700; color:#0F172A; margin-top:2px; white-space:nowrap;">{active_app['income']:.1f}M</div>
    </div>
    <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:10px 10px;">
        <div style="font-size:0.72rem; color:#64748B;">Giá trị tín dụng (Credit)</div>
        <div class="mono" style="font-size:1.15rem; font-weight:700; color:#1D4ED8; margin-top:2px; white-space:nowrap;">{active_app['credit']:.1f}M</div>
    </div>
    <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:10px 10px;">
        <div style="font-size:0.72rem; color:#64748B;">Khoản trả định kỳ (Annuity)</div>
        <div class="mono" style="font-size:1.15rem; font-weight:700; color:#0F172A; margin-top:2px; white-space:nowrap;">{active_app['annuity']:.1f}M <span style="font-size:0.72rem; font-weight:600; color:#64748B;">/ kỳ</span></div>
    </div>
    <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:10px 10px;">
        <div style="font-size:0.72rem; color:#64748B;">Giá trị hàng hóa (Goods)</div>
        <div class="mono" style="font-size:1.15rem; font-weight:700; color:#0F172A; margin-top:2px; white-space:nowrap;">{active_app['goods']:.1f}M</div>
    </div>
</div>
<div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:10px 14px;">
    <div style="display:flex; justify-content:space-between; font-size:0.76rem; font-weight:600; margin-bottom:6px;">
        <span style="color:#334155;">Hệ số Tín dụng / Thu nhập (credit_income_ratio):</span>
        <span class="mono" style="color:{lev_color}; font-weight:700;">{leverage:.2f}x ({lev_status})</span>
    </div>
    <div style="width:100%; height:8px; background:#E2E8F0; border-radius:999px; overflow:hidden;">
        <div style="width:{lev_pct}%; height:100%; background:{lev_color}; border-radius:999px;"></div>
    </div>
    <div class="mono" style="display:flex; justify-content:space-between; font-size:0.66rem; color:#64748B; margin-top:5px;">
        <span>0x (Chuẩn)</span>
        <span>1.8x (Ngưỡng an toàn)</span>
        <span>2.5x (Ngưỡng cảnh báo)</span>
        <span>4.0x+</span>
    </div>
</div>
""",
                unsafe_allow_html=True,
            )

        # 4. Thông tin Khách hàng & Lịch sử Tín dụng (2 cột)
        c_demo, c_hist = st.columns(2, gap="medium")
        with c_demo:
            with st.container(border=True):
                st.markdown(
                    f"""
<div class="section-title">👤 THÔNG TIN KHÁCH HÀNG</div>
<div class="kv-row"><span class="kv-label">Độ tuổi / Nhóm:</span><span class="kv-val">{active_app['age']}</span></div>
<div class="kv-row"><span class="kv-label">Thời gian làm việc:</span><span class="kv-val">{active_app['emp_years']}</span></div>
<div class="kv-row"><span class="kv-label">Học vấn:</span><span class="kv-val">{active_app['edu']}</span></div>
<div class="kv-row"><span class="kv-label">Nguồn thu nhập:</span><span class="kv-val">{active_app['inc_type']}</span></div>
<div class="kv-row"><span class="kv-label">Tình trạng hôn nhân:</span><span class="kv-val">{active_app['marital']}</span></div>
<div class="kv-row"><span class="kv-label">Tài sản sở hữu:</span><span class="kv-val">{active_app['assets']}</span></div>
""",
                    unsafe_allow_html=True,
                )

        with c_hist:
            with st.container(border=True):
                st.markdown(
                    f"""
<div class="section-title">🏛️ LỊCH SỬ TÍN DỤNG QUÁ KHỨ</div>
<div class="kv-row"><span class="kv-label">Hồ sơ trước (DAYS_DECISION ≤ 0):</span><span class="kv-val mono">{active_app['hist_total']}</span></div>
<div class="kv-row"><span class="kv-label">Đã từng được duyệt:</span><span class="kv-val mono" style="color:#059669;">{active_app['hist_app']}</span></div>
<div class="kv-row"><span class="kv-label">Đã từng bị từ chối:</span><span class="kv-val mono" style="color:#E11D48;">{active_app['hist_ref']}</span></div>
<div class="kv-row"><span class="kv-label">Tỷ lệ duyệt quá khứ:</span><span class="kv-val mono">{active_app['hist_rate']}</span></div>
<div class="kv-row"><span class="kv-label">Điểm CIC / External Score 3:</span><span class="kv-val mono" style="color:#1D4ED8;">{active_app['ext3']}</span></div>
<div class="kv-row"><span class="kv-label">Trạng thái nợ quá hạn:</span><span class="kv-val">{active_app['dpd']}</span></div>
""",
                    unsafe_allow_html=True,
                )
