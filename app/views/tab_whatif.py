"""
TAB 3: MÔ PHỎNG KỊCH BẢN TÍN DỤNG (WHAT-IF ANALYSIS)
Cho phép cán bộ thẩm định giả định thay đổi hạn mức, thu nhập và cấu hình khẩu vị rủi ro
để quan sát sự thay đổi điểm rủi ro ML và khuyến nghị hệ thống trước khi quyết định.
"""

import streamlit as st
from app.data_adapter import (
    MODEL_BUNDLE,
    ML_LOADED,
    ML_LOAD_ERROR,
    REVIEW_THRESHOLD,
    DECLINE_THRESHOLD,
)

try:
    from credit_ml.inference import assess
    from credit_ml.policy import PolicyConfig
except ImportError:
    assess = None
    PolicyConfig = None


def run_whatif_simulation(
    sim_app: dict,
    sim_id: str,
    cur_credit: float,
    new_credit: float,
    new_income: float,
    new_lev: float,
    unit_scale: float,
    rev_thresh: float,
    dec_thresh: float,
    ml_loaded: bool | None = None,
    model_bundle=None,
    assess_fn=None,
    policy_cfg_cls=None,
    ml_load_error: str | None = None,
) -> dict:
    """Chạy mô phỏng What-If hoàn toàn qua credit_ml; không dùng công thức heuristic thay thế."""
    ml_loaded = ML_LOADED if ml_loaded is None else ml_loaded
    model_bundle = MODEL_BUNDLE if model_bundle is None else model_bundle
    assess_fn = assess if assess_fn is None else assess_fn
    policy_cfg_cls = PolicyConfig if policy_cfg_cls is None else policy_cfg_cls
    if rev_thresh >= dec_thresh:
        return {
            "status": "invalid_thresholds",
            "error": "Lỗi cấu hình PolicyConfig: `review_threshold` phải nhỏ hơn `decline_threshold`!",
            "new_pd": None,
            "delta_pd": None,
            "new_rec": "INVALID_THRESHOLDS",
        }

    base_pd_raw = sim_app.get("pd")
    if sim_app.get("ml_error") or base_pd_raw is None:
        return {
            "status": "ml_error",
            "error": str(
                sim_app.get("ml_error")
                or "Hồ sơ gốc chưa có điểm rủi ro hợp lệ từ mô hình ML (ML_ERROR)."
            ),
            "new_pd": None,
            "delta_pd": None,
            "new_rec": "ML_ERROR",
        }

    if not ml_loaded or model_bundle is None or assess_fn is None or policy_cfg_cls is None:
        return {
            "status": "ml_error",
            "error": str(
                ml_load_error
                or "Mô hình ML chưa sẵn sàng (MODEL_BUNDLE=None), không thể mô phỏng What-If."
            ),
            "new_pd": None,
            "delta_pd": None,
            "new_rec": "ML_ERROR",
        }

    try:
        scenario_features = dict(sim_app["features"])
        scenario_features["amt_credit"] = float(new_credit) * unit_scale
        scenario_features["amt_income_total"] = float(new_income) * unit_scale
        scenario_features["credit_income_ratio"] = float(new_lev)
        if cur_credit > 0 and scenario_features.get("amt_annuity") is not None:
            scenario_features["amt_annuity"] = (
                float(scenario_features["amt_annuity"]) * (float(new_credit) / cur_credit)
            )

        custom_policy = policy_cfg_cls(
            version=model_bundle.policy.version + "+what_if",
            review_threshold=float(rev_thresh),
            decline_threshold=float(dec_thresh),
            ratio_extreme_threshold=model_bundle.policy.ratio_extreme_threshold,
        )
        after_res = assess_fn(
            model_bundle,
            int(sim_id),
            scenario_features,
            policy=custom_policy,
        )
        new_pd = float(after_res["risk_score"])
        base_pd = float(base_pd_raw)
        return {
            "status": "ok",
            "error": None,
            "new_pd": new_pd,
            "delta_pd": new_pd - base_pd,
            "new_rec": str(after_res["recommendation"]),
            "alerts": list(after_res.get("alerts", [])),
        }
    except Exception as exc:
        return {
            "status": "ml_error",
            "error": (
                f"Suy luận What-If thất bại ({type(exc).__name__}: {exc}). "
                "Hệ thống chặn hiển thị điểm giả định (Fail-Closed)."
            ),
            "new_pd": None,
            "delta_pd": None,
            "new_rec": "ML_ERROR",
        }


def render_tab_whatif():
    """Render giao diện chính của Tab 3 (What-If Scenario Simulator)."""
    with st.container(border=True):
        if not ML_LOADED or MODEL_BUNDLE is None or assess is None or PolicyConfig is None:
            st.error("Mô hình chưa sẵn sàng (ML_ERROR). Chưa thể chạy what-if.")
        st.markdown(
            '<div class="section-title">🎛️ MÔ PHỎNG KỊCH BẢN TÍN DỤNG WHAT-IF'
            " (SCENARIO SIMULATOR)</div>",
            unsafe_allow_html=True,
        )

        app_keys = list(st.session_state.applications.keys())
        if st.session_state.sim_selected_id not in app_keys:
            st.session_state.sim_selected_id = app_keys[0]

        app_labels = {
            aid: (
                f"Hồ sơ #{aid} • {a['applicant']}"
                f" ({a['product']} - {a['credit']:,.1f}{a.get('unit_suffix', 'K')})"
                if a.get("credit") is not None
                else f"Hồ sơ #{aid} • {a['applicant']} ({a['product']} - N/A)"
            )
            for aid, a in st.session_state.applications.items()
        }
        sim_id = st.selectbox(
            "Chọn hồ sơ cần mô phỏng:",
            options=app_keys,
            key="sim_selected_id",
            format_func=lambda x: app_labels.get(x, f"Hồ sơ #{x}"),
        )
        sim_app = st.session_state.applications[sim_id]
        u_sfx = sim_app.get("unit_suffix", "K")
        unit_scale = float(sim_app.get("unit_scale", 1000.0))

        cur_credit = max(1.0, float(sim_app.get("credit") or 1.0))
        cur_income = max(1.0, float(sim_app.get("income") or 1.0))
        min_credit = max(1.0, float(int(cur_credit * 0.2)))
        max_credit = max(float(int(cur_credit * 2.0)), min_credit + 100.0, 1000.0)
        min_income = max(1.0, float(int(cur_income * 0.2)))
        max_income = max(float(int(cur_income * 2.5)), min_income + 50.0, 500.0)

        s_left, s_right = st.columns([4.5, 7.5], gap="large")
        with s_left:
            st.markdown("**1. Điều chỉnh Tham số Tài chính Giả định:**")
            new_credit = st.slider(
                f"Giá trị tín dụng đề xuất mới ({u_sfx}):",
                min_value=min_credit,
                max_value=max_credit,
                value=cur_credit,
                step=5.0,
            )
            new_income = st.slider(
                f"Thu nhập xác minh giả định ({u_sfx}):",
                min_value=min_income,
                max_value=max_income,
                value=cur_income,
                step=5.0,
            )

            st.markdown("**2. Điều chỉnh Ngưỡng Policy (PolicyConfig):**")
            rev_thresh = st.slider(
                "Ngưỡng xem xét (review_threshold):",
                0.05,
                0.35,
                float(REVIEW_THRESHOLD),
                0.01,
            )
            dec_thresh = st.slider(
                "Ngưỡng từ chối (decline_threshold):",
                0.10,
                0.60,
                float(DECLINE_THRESHOLD),
                0.01,
            )

        with s_right:
            raw_base_credit = sim_app.get("credit")
            raw_base_income = sim_app.get("income")
            base_lev = (
                (raw_base_credit / raw_base_income)
                if (raw_base_credit is not None and raw_base_income is not None and raw_base_income > 0)
                else None
            )
            base_lev_disp = f"{base_lev:.2f}x" if base_lev is not None else "N/A"
            base_cred_disp = f"{raw_base_credit:,.1f}{u_sfx}" if raw_base_credit is not None else "N/A"
            base_inc_disp = f"{raw_base_income:,.1f}{u_sfx}" if raw_base_income is not None else "N/A"
            new_lev = (new_credit / new_income) if new_income > 0 else 0.0
            base_pd_raw = sim_app.get("pd")
            base_pd_disp = f"{float(base_pd_raw):.4f}" if base_pd_raw is not None else "ML_ERROR"

            sim_res = run_whatif_simulation(
                sim_app=sim_app,
                sim_id=sim_id,
                cur_credit=cur_credit,
                new_credit=new_credit,
                new_income=new_income,
                new_lev=new_lev,
                unit_scale=unit_scale,
                rev_thresh=rev_thresh,
                dec_thresh=dec_thresh,
            )

            sim_ok = sim_res["status"] == "ok"
            if not sim_ok:
                st.error(sim_res["error"])
                if sim_res["status"] == "ml_error":
                    st.error("Không tính được kịch bản bằng mô hình. Kiểm tra đầu vào và thử lại.")
            elif sim_res.get("alerts"):
                alert_codes = ", ".join(
                    str(a.get("code", a)) if isinstance(a, dict) else str(a)
                    for a in sim_res["alerts"]
                )
                st.info(
                    f"ℹ️ Chính sách giữ/ép trạng thái `{sim_res['new_rec']}` theo cảnh báo dữ liệu/đòn bẩy: `{alert_codes}`."
                )

            if sim_ok:
                new_pd = sim_res["new_pd"]
                delta_pd = sim_res["delta_pd"]
                new_rec = sim_res["new_rec"]
                rec_color = (
                    "#059669"
                    if new_rec == "APPROVE_SIMULATION"
                    else ("#D97706" if new_rec == "REVIEW" else "#E11D48")
                )
                after_pd_disp = (
                    f"{new_pd:.4f} ({delta_pd:+.4f})"
                    if new_pd is not None and delta_pd is not None
                    else "BLOCKED (ML_ERROR)"
                )

                st.markdown(
                    f"""
<div class="section-title">⚖️ KẾT QUẢ SO SÁNH TRƯỚC VÀ SAU MÔ PHỎNG (BEFORE VS AFTER)</div>
<div style="display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-top:8px;">
    <div style="background:#F8FAFC; border:1px solid #CBD5E1; border-top:4px solid #64748B; border-radius:10px; padding:14px;">
        <div style="font-size:0.74rem; font-weight:700; color:#475569; margin-bottom:10px;">HỒ SƠ GỐC (BEFORE)</div>
        <div class="kv-row"><span class="kv-label">Tín dụng / Thu nhập:</span><span class="kv-val mono">{base_cred_disp} / {base_inc_disp}</span></div>
        <div class="kv-row"><span class="kv-label">credit_income_ratio:</span><span class="kv-val mono">{base_lev_disp}</span></div>
        <div class="kv-row"><span class="kv-label">Điểm rủi ro ML:</span><span class="kv-val mono">{base_pd_disp}</span></div>
        <div class="kv-row"><span class="kv-label">Khuyến nghị gốc:</span><span class="kv-val mono">{sim_app.get('recommendation_code', sim_app['risk_level'])}</span></div>
    </div>
    <div style="background:#FFFFFF; border:1px solid {rec_color}; border-top:4px solid {rec_color}; border-radius:10px; padding:14px; box-shadow:0 2px 8px rgba(15,23,42,0.05);">
        <div style="font-size:0.74rem; font-weight:700; color:{rec_color}; margin-bottom:10px;">KỊCH BẢN MỚI (AFTER)</div>
        <div class="kv-row"><span class="kv-label">Tín dụng / Thu nhập mới:</span><span class="kv-val mono">{new_credit:,.1f}{u_sfx} / {new_income:,.1f}{u_sfx}</span></div>
        <div class="kv-row"><span class="kv-label">credit_income_ratio mới:</span><span class="kv-val mono" style="color:#1D4ED8;">{new_lev:.2f}x</span></div>
        <div class="kv-row"><span class="kv-label">Điểm rủi ro mới:</span><span class="kv-val mono" style="color:{rec_color};">{after_pd_disp}</span></div>
        <div class="kv-row"><span class="kv-label">Khuyến nghị mới:</span><span class="kv-val mono" style="color:{rec_color};">{new_rec}</span></div>
    </div>
</div>
<div style="font-size:0.74rem; color:#64748B; font-style:italic; margin-top:8px;">
    * Kết quả giả định (hypothetical), chấm trực tiếp qua pipeline credit_ml theo đúng thang đo đơn vị nguồn (unit_scale={int(unit_scale):,}x) và không ghi đè dữ liệu gốc DW.
</div>
""",
                    unsafe_allow_html=True,
                )

                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
                if st.button(
                    "📌 Đẩy kết quả mô phỏng sang Ghi chú Phê duyệt",
                    type="primary",
                    disabled=False,
                ):
                    pushed = (
                        f"[Mô phỏng What-If Hồ sơ #{sim_id}]: Điều chỉnh tín dụng về"
                        f" {new_credit:,.1f}{u_sfx}, thu nhập {new_income:,.1f}{u_sfx}"
                        f" (credit_income_ratio = {new_lev:.2f}x) -> risk_score ="
                        f" {new_pd:.4f} ({new_rec})."
                    )
                    st.session_state.pending_autofill_note = pushed
                    st.session_state.pending_sync_sim_id = sim_id
                    st.toast(
                        f"Đã chép kịch bản của hồ sơ #{sim_id} sang Tab Thẩm định (Core DSS)!",
                        icon="📌",
                    )
                    st.rerun()
            else:
                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
                st.button(
                    "📌 Đẩy kết quả mô phỏng sang Ghi chú Phê duyệt",
                    type="primary",
                    disabled=True,
                )
