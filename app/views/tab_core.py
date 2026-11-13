"""
Phân hệ thẩm định hồ sơ tín dụng: hàng đợi tiếp nhận, panel quyết định và hồ sơ 360 độ.
"""

import html
import inspect
from datetime import datetime
import plotly.graph_objects as go
import streamlit as st
from app.data_adapter import (
    REVIEW_THRESHOLD,
    DECLINE_THRESHOLD,
    MODEL_NAME_LABEL,
    fetch_dwh_kpi_summary,
    save_audit_decision_to_db,
    fetch_audit_history_from_db,
    fetch_application_by_id,
    fetch_live_applications_batch,
    get_last_db_error,
    get_db_vendor_label,
    sync_app_status_from_logs,
)


def _fmt_money(val: float | None, u_sfx: str) -> str:
    """Định dạng số tiền giữ nguyên N/A cho giá trị thiếu ('Thiếu khác 0')."""
    if val is None:
        return "N/A"
    return f"{float(val):,.1f}{u_sfx}"


def _format_alert_items(alerts: list) -> list[str]:
    """Chuẩn hóa danh sách cảnh báo từ Policy/ML thành các chuỗi dễ đọc."""
    formatted = []
    for item in alerts or []:
        if isinstance(item, dict):
            code = str(item.get("code", "ALERT")).strip()
            msg = str(item.get("message", "")).strip()
            sev = str(item.get("severity", "")).strip().upper()
            prefix = f"[{sev}] " if sev else ""
            formatted.append(f"{prefix}{code}: {msg}" if msg else f"{prefix}{code}")
        else:
            formatted.append(str(item))
    return formatted


def _format_queue_label(aid: str, app_record: dict) -> str:
    """Định dạng nhãn hồ sơ trong hàng đợi, an toàn khi pd=None (ML_ERROR)."""
    r_level = app_record.get("risk_level", "ERROR")
    pd_val = app_record.get("pd")
    rec_code = app_record.get("recommendation_code", "")
    if app_record.get("ml_error") or pd_val is None or r_level == "ERROR":
        pd_badge = "PD: ERROR (ML_ERROR)"
    else:
        pd_badge = f"PD: {float(pd_val):.3f}"
        if r_level == "LOW" and rec_code == "REVIEW":
            pd_badge = f"PD: {float(pd_val):.3f} • REVIEW"
    u_sfx = app_record.get("unit_suffix", "K")
    credit_disp = _fmt_money(app_record.get("credit"), u_sfx)
    status_lbl = (
        "Đã xử lý"
        if app_record.get("status") in ("Đã xử lý", "Đã duyệt")
        else "Chờ duyệt"
    )
    return (
        f"**#{aid} • {app_record['applicant']}** &nbsp; `{pd_badge}`\n\n"
        f"{app_record['product']} • {credit_disp} — {status_lbl}"
    )


def _resolve_recommendation_banner(
    active_app: dict,
    review_threshold: float,
    decline_threshold: float,
) -> dict:
    """Tính toán banner khuyến nghị bám sát Policy (recommendation_code) và Fail-Closed."""
    pd_val = active_app.get("pd")
    ml_error = active_app.get("ml_error")
    r_level = active_app.get("risk_level", "ERROR")
    rec_code = active_app.get("recommendation_code", "ML_ERROR")
    alerts_text = _format_alert_items(active_app.get("alerts", []))

    if ml_error or pd_val is None or rec_code == "ML_ERROR" or r_level == "ERROR":
        err_msg = html.escape(str(ml_error or "Không có điểm rủi ro hợp lệ từ mô hình ML."))
        return {
            "bg": "#FFF1F2",
            "border": "#E11D48",
            "badge_bg": "#BE123C",
            "badge_text": "LỖI CHẤM ĐIỂM ML (ML_ERROR)",
            "title": "Không thể chấm điểm rủi ro ML — Chặn phê duyệt tự động (FAIL-CLOSED)",
            "subtitle": (
                f"Mô hình ML không khả dụng hoặc suy luận thất bại ({err_msg})."
                " Vui lòng kiểm tra pipeline ML trước khi phê duyệt hồ sơ."
            ),
            "alerts_text": alerts_text,
        }

    pd_num = float(pd_val)
    if rec_code == "APPROVE_SIMULATION":
        return {
            "bg": "#ECFDF5",
            "border": "#10B981",
            "badge_bg": "#059669",
            "badge_text": f"MỨC RỦI RO: {r_level} • APPROVE",
            "title": "Khuyến nghị Hệ thống: Phê Duyệt Hồ Sơ (APPROVE_SIMULATION)",
            "subtitle": (
                f"Điểm rủi ro mô hình nằm trong vùng an toàn"
                f" (risk_score = {pd_num:.3f} < {review_threshold:.2f})."
            ),
            "alerts_text": alerts_text,
        }

    if rec_code == "REVIEW":
        if r_level == "LOW":
            sub = (
                f"Điểm mô hình ở mức LOW (risk_score = {pd_num:.3f} < {review_threshold:.2f}),"
                " nhưng Policy bắt buộc REVIEW do cảnh báo chất lượng dữ liệu / đòn bẩy."
            )
        else:
            sub = (
                f"Điểm rủi ro nằm trong vùng cần xem xét kỹ"
                f" ({review_threshold:.2f} ≤ risk_score = {pd_num:.3f} < {decline_threshold:.2f})."
                " Khuyến nghị kiểm tra chứng từ thu nhập hoặc chạy What-If."
            )
        return {
            "bg": "#FFFBEB",
            "border": "#F59E0B",
            "badge_bg": "#D97706",
            "badge_text": f"MỨC RỦI RO: {r_level} • REVIEW",
            "title": "Khuyến nghị Hệ thống: Thẩm Định Bổ Sung (REVIEW)",
            "subtitle": sub,
            "alerts_text": alerts_text,
        }

    return {
        "bg": "#FFF1F2",
        "border": "#F43F5E",
        "badge_bg": "#E11D48",
        "badge_text": f"MỨC RỦI RO: {r_level} • DECLINE",
        "title": "Khuyến nghị Hệ thống: Từ Chối Mô Phỏng (DECLINE_SIMULATION)",
        "subtitle": (
            f"Điểm rủi ro mô hình vượt ngưỡng từ chối"
            f" (risk_score = {pd_num:.3f} ≥ {decline_threshold:.2f})."
        ),
        "alerts_text": alerts_text,
    }


def _build_autofill_note(
    active_app: dict,
    chosen_decision: str,
    review_threshold: float,
    decline_threshold: float,
) -> str:
    """Tạo nội dung mẫu ghi chú thẩm định, tránh lỗi định dạng khi pd=None."""
    u_sfx = active_app.get("unit_suffix", "M")
    pd_val = active_app.get("pd")
    if active_app.get("ml_error") or pd_val is None:
        return (
            f"Hồ sơ #{active_app['id']} ({active_app['applicant']}) đang gặp lỗi chấm điểm ML"
            f" ({active_app.get('ml_error') or 'ML_ERROR'}). Chuyển xem xét thủ công trước khi quyết định."
        )
    pd_num = float(pd_val)
    credit_disp = _fmt_money(active_app.get("credit"), u_sfx)
    if "Phê duyệt" in chosen_decision:
        return (
            f"Đồng ý cấp tín dụng {credit_disp} cho"
            f" KH #{active_app['id']} ({active_app['applicant']}). Điểm rủi ro"
            f" {pd_num:.3f} < {review_threshold:.2f}."
        )
    if "Xem xét" in chosen_decision:
        return (
            f"Hồ sơ #{active_app['id']} có điểm rủi ro {pd_num:.3f}"
            f" (khuyến nghị: {active_app.get('recommendation_code', 'REVIEW')})."
            f" Cần xác minh thêm chứng từ/dòng tiền của KH ({active_app['applicant']})."
        )
    return (
        f"Từ chối cấp tín dụng {credit_disp} do điểm rủi ro"
        f" {pd_num:.3f} >= {decline_threshold:.2f}."
    )


def persist_decision(
    applications: dict,
    audit_logs: list,
    selected_id: str,
    chosen_decision: str,
    chosen_reason: str,
    note_val: str,
    is_live_db: bool,
    save_fn=None,
    fetch_fn=None,
    now_str: str | None = None,
) -> tuple[bool, str, str]:
    """Lưu quyết định thẩm định trung thực: chặn Approve khi ML lỗi và không báo thành công giả khi DB lỗi."""
    save_fn = save_fn or save_audit_decision_to_db
    fetch_fn = fetch_fn or fetch_audit_history_from_db
    active_app = applications[selected_id]
    if (active_app.get("ml_error") or active_app.get("pd") is None) and "Phê duyệt" in chosen_decision:
        return (
            False,
            "error",
            "Không thể Phê duyệt hồ sơ khi mô hình ML đang lỗi (Fail-Closed). Vui lòng chọn '👁 Xem xét thêm' hoặc '✕ Từ chối'.",
        )

    clean_dec = (
        chosen_decision.replace("✓ ", "")
        .replace("👁 ", "")
        .replace("✕ ", "")
        .strip()
    )
    timestamp = now_str or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_log_entry = {
        "Mã GD": f"DEC-{len(audit_logs) + 1:03d}",
        "Mã Hồ Sơ": f"#{selected_id}",
        "Khách Hàng": f"#{selected_id} • {active_app['applicant']}",
        "Quyết Định": clean_dec,
        "Mã Lý Do": chosen_reason,
        "Ghi Chú Nghiệp Vụ": (
            note_val.strip()
            if note_val and note_val.strip()
            else "Ghi nhận quyết định theo quy trình thẩm định chuẩn."
        ),
        "Cán Bộ Thẩm Định": "Officer",
        "Thời Gian Ghi Nhận": timestamp,
    }

    sig_params = inspect.signature(save_fn).parameters
    if "app_record" in sig_params:
        save_ok = bool(save_fn(new_log_entry, app_record=active_app))
    else:
        save_ok = bool(save_fn(new_log_entry))
    if save_ok:
        active_app["status"] = "Đã xử lý"
        active_app["default_decision"] = chosen_decision
        refreshed_logs = fetch_fn()
        if refreshed_logs is not None:
            audit_logs[:] = refreshed_logs
        else:
            audit_logs.insert(0, new_log_entry)
        return (
            True,
            "success",
            f"Đã lưu quyết định cho hồ sơ #{selected_id} vào bảng app.credit_decisions!",
        )

    if is_live_db:
        db_err = get_last_db_error()
        err_suffix = f" ({db_err})" if db_err else ""
        vendor_label = get_db_vendor_label()
        return (
            False,
            "error",
            f"Không lưu được vào Kho dữ liệu ({vendor_label}) cho hồ sơ #{selected_id}{err_suffix} (ghi thất bại)! "
            "Trạng thái hồ sơ và nhật ký kiểm toán chưa được cập nhật.",
        )

    active_app["status"] = "Đã xử lý"
    active_app["default_decision"] = chosen_decision
    new_log_entry["Mã GD"] = f"LOCAL-{len(audit_logs) + 901}"
    new_log_entry["Cán Bộ Thẩm Định"] = "Officer (Offline)"
    audit_logs.insert(0, new_log_entry)
    return (
        True,
        "warning",
        f"Chế độ Offline: Đã lưu tạm quyết định hồ sơ #{selected_id} (chỉ lưu quyết định trong phiên, chưa ghi vào DB).",
    )


def render_kpi_ribbon():
    """Hiển thị 4 chỉ số KPI quan trọng ở đầu Tab Thẩm định (kết nối trực tiếp DWH Cloud/Local)."""
    dwh = fetch_dwh_kpi_summary()
    apps = st.session_state.applications
    done_count = len([x for x in st.session_state.get("audit_logs", []) if x.get("Quyết Định") in ("Phê duyệt", "Từ chối", "Xem xét thêm")])

    if dwh:
        total_apps_disp = f"{dwh['total_applications']:,}"
        total_credit_disp = f"{dwh['total_credit'] / 1e9:,.2f}B"
        labeled_count_disp = f"{dwh['labeled_applications']:,}"
        target_1_disp = f"{dwh['bad_loans_count']:,}"
        bad_rate = dwh["bad_rate"]
        vendor_label = get_db_vendor_label()
        source_badge = f"● Live DWH {vendor_label} (PostgreSQL)"
        cohort_subtitle = "hồ sơ trong Kho dữ liệu"
    else:
        total_apps = len(apps)
        total_apps_disp = str(total_apps)
        total_credit_m = sum(
            (a.get("credit") or 0.0) * a.get("unit_scale", 1000.0) / 1e6
            for a in apps.values()
        )
        total_credit_disp = f"{total_credit_m:,.2f}M"
        labeled_apps = [a for a in apps.values() if a.get("target") is not None]
        labeled_count = len(labeled_apps)
        target_1_count = sum(1 for a in labeled_apps if a.get("target") == 1)
        bad_rate = (target_1_count / labeled_count) * 100 if labeled_count else 0.0
        labeled_count_disp = str(labeled_count)
        target_1_disp = str(target_1_count)
        source_badge = "Dữ liệu cohort mẫu (Offline mode)"
        cohort_subtitle = "hồ sơ trong cohort mẫu"

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f"""
<div class="kpi-card">
    <div style="font-size:0.68rem; font-weight:700; color:#64748B; text-transform:uppercase;">TỔNG HỒ SƠ TIẾP NHẬN</div>
    <div style="display:flex; align-items:baseline; gap:6px; margin-top:4px;">
        <span class="mono" style="font-size:1.55rem; font-weight:700; color:#0F172A;">{total_apps_disp}</span>
        <span style="font-size:0.75rem; color:#64748B;">{cohort_subtitle}</span>
    </div>
    <div style="font-size:0.7rem; color:#2563EB; font-weight:500; margin-top:4px;">{source_badge}</div>
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
        <span class="mono" style="font-size:1.55rem; font-weight:700; color:#0F172A;">{total_credit_disp}</span>
        <span style="font-size:0.75rem; color:#64748B;">đơn vị nguồn</span>
    </div>
    <div style="font-size:0.7rem; color:#059669; font-weight:500; margin-top:4px;">SUM(amt_credit) bảo toàn qua ETL</div>
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
        <span style="font-size:0.75rem; color:#64748B;">({target_1_disp}/{labeled_count_disp} hồ sơ có nhãn)</span>
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
        <span class="mono" style="font-size:1.55rem; font-weight:700; color:#059669;">{done_count}</span>
        <span style="font-size:0.75rem; color:#64748B;">quyết định đã lưu vết</span>
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

    with col_left:
        with st.container(border=True):
            st.markdown(
                '<div class="section-title">HÀNG ĐỢI THẨM ĐỊNH (QUEUE)</div>',
                unsafe_allow_html=True,
            )

            if st.session_state.get("pending_sync_sim_id"):
                sync_id = st.session_state.pop("pending_sync_sim_id")
                if sync_id in st.session_state.applications:
                    st.session_state.queue_radio = sync_id
                    st.session_state.last_selected_id = sync_id

            search_q = st.text_input(
                "Tìm kiếm nhanh",
                placeholder="Nhập mã ID (VD: 100009) hoặc nghề nghiệp...",
                label_visibility="collapsed",
            )
            f_col1, f_col2 = st.columns(2, gap="small")
            with f_col1:
                filter_status = st.selectbox(
                    "Trạng thái",
                    ["Tất cả trạng thái", "Chờ duyệt", "Đã xử lý"],
                    label_visibility="collapsed",
                )
            with f_col2:
                filter_risk = st.selectbox(
                    "Mức rủi ro",
                    ["Tất cả rủi ro", "HIGH", "MEDIUM", "LOW", "ERROR"],
                    label_visibility="collapsed",
                )

            clean_q = search_q.strip()
            searched_id = None

            if clean_q:
                cand_id = clean_q.lstrip("#").strip()
                if cand_id.isdigit():
                    searched_id = cand_id
                    int_id = int(cand_id)
                    if cand_id not in st.session_state.applications:
                        with st.spinner(f"Đang tìm hồ sơ #{cand_id} từ Kho DWH..."):
                            fetched_app = fetch_application_by_id(int_id)
                        if fetched_app:
                            st.session_state.applications[cand_id] = fetched_app
                            sync_app_status_from_logs(
                                st.session_state.applications,
                                st.session_state.get("audit_logs", []),
                            )

            filtered_ids = []
            for aid, app in st.session_state.applications.items():
                if filter_status != "Tất cả trạng thái" and app["status"] != filter_status:
                    continue
                if filter_risk != "Tất cả rủi ro" and app["risk_level"] != filter_risk:
                    continue
                if clean_q:
                    if searched_id and aid == searched_id:
                        continue  # Ưu tiên chèn lên đầu danh sách
                    haystack = f"{aid} {app['applicant']} {app.get('occupation', '')} {app.get('inc_type', '')}".lower()
                    if clean_q.lower() not in haystack:
                        continue
                filtered_ids.append(aid)

            if searched_id and searched_id in st.session_state.applications:
                if searched_id not in filtered_ids:
                    filtered_ids.insert(0, searched_id)
                found_src = (
                    f"trực tiếp từ Kho DWH ({get_db_vendor_label()})"
                    if st.session_state.applications[searched_id].get("is_real_dwh")
                    else "trong danh sách phiên làm việc"
                )
                st.markdown(
                    f'<div style="background:#ECFDF5; border:1px solid #A7F3D0; border-radius:6px; padding:4px 8px; margin:2px 0 4px 0; font-size:0.74rem; color:#065F46;">'
                    f"Tìm thấy hồ sơ <b>#{searched_id}</b> {found_src}</div>",
                    unsafe_allow_html=True,
                )
            elif searched_id:
                st.warning(f"Không tìm thấy hồ sơ #{searched_id} trong Kho DWH hoặc danh sách hiện tại.")

            if not filtered_ids:
                st.info(f"Không có hồ sơ nào khớp bộ lọc hiện tại. Đang hiển thị toàn bộ danh sách.")
                filtered_ids = list(st.session_state.applications.keys())

            queue_labels = {
                aid: _format_queue_label(aid, st.session_state.applications[aid])
                for aid in filtered_ids
            }

            def format_queue_option(aid):
                return queue_labels.get(aid, f"#{aid}")

            if searched_id and searched_id in filtered_ids:
                if st.session_state.get("queue_radio") != searched_id:
                    st.session_state.queue_radio = searched_id

            if "queue_radio" in st.session_state and st.session_state.queue_radio not in filtered_ids:
                st.session_state.queue_radio = filtered_ids[0]

            with st.container(height=320, border=False):
                selected_id = st.radio(
                    "Chọn hồ sơ thẩm định:",
                    options=filtered_ids,
                    format_func=format_queue_option,
                    label_visibility="collapsed",
                    key="queue_radio",
                )

            col_btn, col_info = st.columns([1.2, 0.8])
            with col_btn:
                is_live = st.session_state.get("is_live_db", False)
                if st.button(
                    "Nạp thêm 20 hồ sơ",
                    use_container_width=True,
                    disabled=not is_live,
                    help=f"Tải thêm 20 hồ sơ tiếp theo từ Kho DWH ({get_db_vendor_label()} - 307,511 hồ sơ)",
                ):
                    with st.spinner(f"Đang nạp từ Kho DWH ({get_db_vendor_label()})..."):
                        cur_real_cnt = sum(1 for a in st.session_state.applications.values() if a.get("is_real_dwh"))
                        more_batch = fetch_live_applications_batch(limit=20, offset=cur_real_cnt)
                        if more_batch:
                            st.session_state.applications.update(more_batch)
                            sync_app_status_from_logs(
                                st.session_state.applications,
                                st.session_state.get("audit_logs", []),
                            )
                            st.toast(f"Đã nạp thành công {len(more_batch)} hồ sơ mới!")
                            st.rerun()
            with col_info:
                dwh_label = "307.5k" if st.session_state.get("is_live_db") else "Offline"
                st.markdown(
                    f"""
                    <div style="font-size:0.7rem; color:#64748B; text-align:right; padding-top:4px;">
                        Hiển thị: <b>{len(filtered_ids)}/{len(st.session_state.applications)}</b><br>
                        (Kho DWH: <b>{dwh_label}</b>)
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            if selected_id != st.session_state.last_selected_id:
                st.session_state.last_selected_id = selected_id
                st.session_state.draft_note = ""
                st.session_state.draft_note_area = ""
                st.session_state.decision_radio = st.session_state.applications[selected_id].get(
                    "default_decision", "👁 Xem xét thêm"
                )

        active_app = st.session_state.applications[selected_id]

        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown(
                f"""
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
    <span class="section-title" style="margin-bottom:0; font-size:0.75rem; white-space:nowrap;">QUYẾT ĐỊNH CỦA CÁN BỘ</span>
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
            cur_default = active_app.get("default_decision", "👁 Xem xét thêm")
            if "decision_radio" not in st.session_state:
                st.session_state.decision_radio = cur_default

            if active_app.get("ml_error") or active_app.get("pd") is None:
                st.warning(
                    "⚠️ Đang lỗi chấm điểm ML (Fail-Closed): Không cho phép lưu quyết định 'Phê duyệt'."
                )

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

            u_sfx = active_app.get("unit_suffix", "M")
            with col_autofill:
                if st.button("Điền mẫu nhanh", use_container_width=True):
                    auto_txt = _build_autofill_note(
                        active_app,
                        chosen_decision,
                        REVIEW_THRESHOLD,
                        DECLINE_THRESHOLD,
                    )
                    st.session_state.draft_note = auto_txt
                    st.session_state.draft_note_area = auto_txt

            if st.session_state.pop("pending_clear_note", False):
                st.session_state.draft_note = ""
                st.session_state.draft_note_area = ""
            elif st.session_state.get("pending_autofill_note") is not None:
                pushed_note = st.session_state.pop("pending_autofill_note")
                st.session_state.draft_note = pushed_note
                st.session_state.draft_note_area = pushed_note

            note_val = st.text_area(
                "Ghi chú thẩm định",
                key="draft_note_area",
                height=72,
                placeholder=(
                    "Nhập căn cứ nghiệp vụ (VD: Thu nhập ổn định, đòn bẩy trong ngưỡng an toàn)..."
                ),
                label_visibility="collapsed",
            )

            col_act1, col_act2 = st.columns([1, 2.2])
            with col_act1:
                if st.button("Thử What-If", use_container_width=True):
                    st.session_state.sim_selected_id = selected_id
                    st.toast(
                        f"Đã chọn sẵn hồ sơ #{selected_id} trong Tab 'Mô phỏng Kịch bản (What-If)'!"
                    )
            with col_act2:
                if st.button(
                    "LƯU QUYẾT ĐỊNH (SAVE)",
                    type="primary",
                    use_container_width=True,
                ):
                    save_ok, save_level, save_msg = persist_decision(
                        applications=st.session_state.applications,
                        audit_logs=st.session_state.audit_logs,
                        selected_id=selected_id,
                        chosen_decision=chosen_decision,
                        chosen_reason=chosen_reason,
                        note_val=note_val,
                        is_live_db=bool(st.session_state.get("is_live_db")),
                    )
                    if save_ok:
                        st.session_state.pending_clear_note = True
                        st.toast(save_msg)
                        st.rerun()
                    else:
                        st.error(save_msg)

    with col_right:
        banner = _resolve_recommendation_banner(
            active_app, REVIEW_THRESHOLD, DECLINE_THRESHOLD
        )

        t_val = active_app.get("target")
        if t_val == 1:
            gt_pill = '<span style="background:#FEE2E2; color:#991B1B; font-size:0.68rem; font-weight:600; padding:2px 8px; border-radius:6px; border:1px solid #FECACA;">Đối chiếu lịch sử: TARGET=1 (Khó khăn TT)</span>'
        elif t_val == 0:
            gt_pill = '<span style="background:#DCFCE7; color:#166534; font-size:0.68rem; font-weight:600; padding:2px 8px; border-radius:6px; border:1px solid #BBF7D0;">Đối chiếu lịch sử: TARGET=0 (Trả tốt)</span>'
        else:
            gt_pill = '<span style="background:#F1F5F9; color:#475569; font-size:0.68rem; font-weight:600; padding:2px 8px; border-radius:6px;">Chưa có nhãn (Test)</span>'

        alerts_html = ""
        if banner["alerts_text"]:
            items_html = "".join(
                f"<li>{html.escape(item)}</li>" for item in banner["alerts_text"]
            )
            alerts_html = (
                '<div style="margin-top:8px; padding:6px 10px; background:rgba(255,255,255,0.75); '
                'border-radius:8px; border:1px dashed rgba(15,23,42,0.18); font-size:0.74rem; color:#1E293B;">'
                '<b>Cảnh báo chính sách & dữ liệu:</b>'
                f'<ul style="margin:4px 0 0 18px; padding:0;">{items_html}</ul></div>'
            )

        st.markdown(
            f"""
<div style="background:{banner['bg']}; border:1px solid {banner['border']}; border-left:5px solid {banner['border']}; border-radius:12px; padding:14px 18px; margin-bottom: 10px;">
    <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
        <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
            <span style="background:{banner['badge_bg']}; color:#FFFFFF; font-size:0.68rem; font-weight:700; padding:3px 10px; border-radius:999px; letter-spacing:0.04em;">
                {banner['badge_text']}
            </span>
            <span class="mono" style="font-size:0.76rem; font-weight:700; color:#1E293B;">
                KH: {active_app['applicant'].upper()} • #{active_app['id']}
            </span>
            {gt_pill}
        </div>
        <div class="mono" style="font-size:0.72rem; font-weight:600; color:#334155; background:rgba(255,255,255,0.85); padding:3px 10px; border-radius:6px; border:1px solid rgba(15,23,42,0.08);">
            Model: {MODEL_NAME_LABEL} • SLA: {active_app['sla']}
        </div>
    </div>
    <div style="font-size:1.05rem; font-weight:700; color:#0F172A; margin-top:8px;">
        {banner['title']}
    </div>
    <div style="font-size:0.78rem; font-weight:500; color:#334155; margin-top:2px;">
        {banner['subtitle']}
    </div>
    {alerts_html}
</div>
""",
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            g_col, d_col = st.columns([4.8, 7.2], gap="medium")
            with g_col:
                if active_app.get("ml_error") or active_app.get("pd") is None:
                    st.error(
                        "⚠️ Không thể vẽ Gauge PD do mô hình ML lỗi/chưa tải được (ML_ERROR)."
                    )
                else:
                    st.plotly_chart(
                        create_gauge_chart(
                            float(active_app["pd"]), active_app["risk_level"]
                        ),
                        use_container_width=True,
                        config={"displayModeBar": False},
                    )
            with d_col:
                st.markdown(
                    '<div class="section-title" style="margin-top:4px;">'
                    "YẾU TỐ ĐÓNG GÓP LOG-ODDS CHÍNH (MODEL FACTORS):</div>",
                    unsafe_allow_html=True,
                )
                drivers_list = active_app.get("drivers") or []
                if not drivers_list:
                    st.info("Không có phân tích log-odds (mô hình ML chưa chấm được hoặc lỗi suy luận).")
                else:
                    drivers_html = ""
                    for feat, desc, val, dtype in drivers_list:
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

        with st.container(border=True):
            inc_val = active_app.get("income")
            cred_val = active_app.get("credit")
            ann_val = active_app.get("annuity")
            goods_val = active_app.get("goods")
            u_sfx = active_app.get("unit_suffix", "K")

            if inc_val is not None and inc_val > 0 and cred_val is not None:
                leverage = cred_val / inc_val
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
                lev_disp = f"{leverage:.2f}x ({lev_status})"
            else:
                lev_pct = 0.0
                lev_color = "#64748B"
                lev_disp = "N/A (Thiếu thu nhập hoặc tín dụng)"

            st.markdown(
                f"""
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
    <span class="section-title" style="margin-bottom:0;">TÌNH HÌNH TÀI CHÍNH & HỆ SỐ TÍN DỤNG / THU NHẬP</span>
    <span style="background:#F1F5F9; color:#334155; font-size:0.72rem; font-weight:600; padding:2px 10px; border-radius:6px;">
        {active_app['product']} • Đơn vị nguồn ({u_sfx})
    </span>
</div>
<div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:10px; margin-bottom:12px;">
    <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:10px 10px;">
        <div style="font-size:0.72rem; color:#64748B;">Thu nhập khai báo</div>
        <div class="mono" style="font-size:1.15rem; font-weight:700; color:#0F172A; margin-top:2px; white-space:nowrap;">{_fmt_money(inc_val, u_sfx)}</div>
    </div>
    <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:10px 10px;">
        <div style="font-size:0.72rem; color:#64748B;">Giá trị tín dụng (Credit)</div>
        <div class="mono" style="font-size:1.15rem; font-weight:700; color:#1D4ED8; margin-top:2px; white-space:nowrap;">{_fmt_money(cred_val, u_sfx)}</div>
    </div>
    <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:10px 10px;">
        <div style="font-size:0.72rem; color:#64748B;">Khoản trả định kỳ (Annuity)</div>
        <div class="mono" style="font-size:1.15rem; font-weight:700; color:#0F172A; margin-top:2px; white-space:nowrap;">{_fmt_money(ann_val, u_sfx)} <span style="font-size:0.72rem; font-weight:600; color:#64748B;">/ kỳ</span></div>
    </div>
    <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:10px 10px;">
        <div style="font-size:0.72rem; color:#64748B;">Giá trị hàng hóa (Goods)</div>
        <div class="mono" style="font-size:1.15rem; font-weight:700; color:#0F172A; margin-top:2px; white-space:nowrap;">{_fmt_money(goods_val, u_sfx)}</div>
    </div>
</div>
<div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:10px 14px;">
    <div style="display:flex; justify-content:space-between; font-size:0.76rem; font-weight:600; margin-bottom:6px;">
        <span style="color:#334155;">Hệ số Tín dụng / Thu nhập (credit_income_ratio):</span>
        <span class="mono" style="color:{lev_color}; font-weight:700;">{lev_disp}</span>
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

        c_demo, c_hist = st.columns(2, gap="medium")
        occ_disp = active_app.get("occupation", "Chưa khai báo (Unknown)")
        fam_disp = active_app.get("family_info", active_app["marital"])
        ext1_disp = active_app.get("ext1", "N/A")
        ext2_disp = active_app.get("ext2", "N/A")
        ext3_disp = active_app.get("ext3", "N/A")

        with c_demo:
            with st.container(border=True):
                st.markdown(
                    f"""
<div class="section-title">THÔNG TIN KHÁCH HÀNG</div>
<div class="kv-row"><span class="kv-label">Độ tuổi / Nhóm:</span><span class="kv-val">{active_app['age']}</span></div>
<div class="kv-row"><span class="kv-label">Nghề nghiệp / Thu nhập:</span><span class="kv-val">{occ_disp} ({active_app['inc_type']})</span></div>
<div class="kv-row"><span class="kv-label">Thời gian làm việc:</span><span class="kv-val">{active_app['emp_years']}</span></div>
<div class="kv-row"><span class="kv-label">Học vấn:</span><span class="kv-val">{active_app['edu']}</span></div>
<div class="kv-row"><span class="kv-label">Gia đình & Hôn nhân:</span><span class="kv-val">{active_app['marital']} • {fam_disp}</span></div>
<div class="kv-row"><span class="kv-label">Tài sản sở hữu:</span><span class="kv-val">{active_app['assets']}</span></div>
""",
                    unsafe_allow_html=True,
                )

        with c_hist:
            with st.container(border=True):
                st.markdown(
                    f"""
<div class="section-title">LỊCH SỬ TÍN DỤNG & ĐIỂM NGUỒN NGOÀI</div>
<div class="kv-row"><span class="kv-label">Hồ sơ trước (DAYS_DECISION ≤ 0):</span><span class="kv-val mono">{active_app['hist_total']}</span></div>
<div class="kv-row"><span class="kv-label">Đã từng được duyệt / Từ chối:</span><span class="kv-val mono"><span style="color:#059669;">{active_app['hist_app']}</span> / <span style="color:#E11D48;">{active_app['hist_ref']}</span></span></div>
<div class="kv-row"><span class="kv-label">Tỷ lệ duyệt quá khứ:</span><span class="kv-val mono">{active_app['hist_rate']}</span></div>
<div class="kv-row"><span class="kv-label">Điểm nguồn ngoài (EXT_1 / EXT_2):</span><span class="kv-val mono" style="color:#1D4ED8;">{ext1_disp} / {ext2_disp}</span></div>
<div class="kv-row"><span class="kv-label">Điểm CIC / External Score 3:</span><span class="kv-val mono" style="color:#1D4ED8;">{ext3_disp}</span></div>
<div class="kv-row"><span class="kv-label">Trạng thái nợ quá hạn:</span><span class="kv-val">{active_app['dpd']}</span></div>
""",
                    unsafe_allow_html=True,
                )
