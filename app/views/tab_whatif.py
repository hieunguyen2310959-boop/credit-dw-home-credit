"""
TAB 3: MÔ PHỎNG KỊCH BẢN TÍN DỤNG (WHAT-IF ANALYSIS)
Cho phép cán bộ thẩm định giả định thay đổi hạn mức, thu nhập và cấu hình khẩu vị rủi ro
để quan sát sự thay đổi điểm rủi ro ML và khuyến nghị hệ thống trước khi quyết định.
"""

import streamlit as st
from app.data_adapter import (
    MODEL_BUNDLE,
    ML_LOADED,
    REVIEW_THRESHOLD,
    DECLINE_THRESHOLD,
)

try:
    from credit_ml.inference import assess
    from credit_ml.policy import PolicyConfig
except ImportError:
    assess = None
    PolicyConfig = None


def render_tab_whatif():
    """Render giao diện chính của Tab 3 (What-If Scenario Simulator)."""
    with st.container(border=True):
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
                f" ({a['product']} - {a['credit']:,.1f}{a.get('unit_suffix', 'M')})"
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
        u_sfx = sim_app.get("unit_suffix", "M")
        unit_scale = float(sim_app.get("unit_scale", 1.0))

        cur_credit = max(1.0, float(sim_app["credit"]))
        cur_income = max(1.0, float(sim_app["income"]))
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
            base_lev = (sim_app["credit"] / sim_app["income"]) if sim_app["income"] > 0 else 0.0
            new_lev = (new_credit / new_income) if new_income > 0 else 0.0
            base_pd = float(sim_app["pd"])

            if rev_thresh >= dec_thresh:
                st.error(
                    "⚠️ Lỗi cấu hình PolicyConfig: `review_threshold` phải nhỏ hơn `decline_threshold`!"
                )
                new_pd = base_pd
                new_rec = "INVALID_THRESHOLDS"
            else:
                # Sử dụng trực tiếp dict 16 features chuẩn theo đúng hệ quy chiếu unit_scale
                if ML_LOADED and MODEL_BUNDLE is not None and assess is not None and PolicyConfig is not None:
                    try:
                        scenario_features = dict(sim_app["features"])
                        scenario_features["amt_credit"] = float(new_credit) * unit_scale
                        scenario_features["amt_income_total"] = float(new_income) * unit_scale
                        scenario_features["credit_income_ratio"] = float(new_lev)
                        if cur_credit > 0 and scenario_features.get("amt_annuity") is not None:
                            scenario_features["amt_annuity"] = (
                                float(scenario_features["amt_annuity"]) * (float(new_credit) / cur_credit)
                            )

                        custom_policy = PolicyConfig(
                            version=MODEL_BUNDLE.policy.version + "+what_if",
                            review_threshold=float(rev_thresh),
                            decline_threshold=float(dec_thresh),
                            ratio_extreme_threshold=MODEL_BUNDLE.policy.ratio_extreme_threshold,
                        )
                        after_res = assess(
                            MODEL_BUNDLE,
                            int(sim_id),
                            scenario_features,
                            policy=custom_policy,
                        )
                        new_pd = float(after_res["risk_score"])
                        new_rec = str(after_res["recommendation"])
                    except Exception:
                        new_pd = max(0.010, min(0.950, base_pd + (new_lev - base_lev) * 0.08))
                        new_rec = (
                            "APPROVE_SIMULATION"
                            if new_pd < rev_thresh
                            else ("REVIEW" if new_pd < dec_thresh else "DECLINE_SIMULATION")
                        )
                else:
                    new_pd = max(0.010, min(0.950, base_pd + (new_lev - base_lev) * 0.08))
                    new_rec = (
                        "APPROVE_SIMULATION"
                        if new_pd < rev_thresh
                        else ("REVIEW" if new_pd < dec_thresh else "DECLINE_SIMULATION")
                    )

            delta_pd = new_pd - base_pd
            rec_color = (
                "#059669"
                if new_rec == "APPROVE_SIMULATION"
                else ("#D97706" if new_rec == "REVIEW" else "#E11D48")
            )

            st.markdown(
                f"""
<div class="section-title">⚖️ KẾT QUẢ SO SÁNH TRƯỚC VÀ SAU MÔ PHỎNG (BEFORE VS AFTER)</div>
<div style="display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-top:8px;">
    <div style="background:#F8FAFC; border:1px solid #CBD5E1; border-top:4px solid #64748B; border-radius:10px; padding:14px;">
        <div style="font-size:0.74rem; font-weight:700; color:#475569; margin-bottom:10px;">HỒ SƠ GỐC (BEFORE)</div>
        <div class="kv-row"><span class="kv-label">Tín dụng / Thu nhập:</span><span class="kv-val mono">{sim_app['credit']:,.1f}{u_sfx} / {sim_app['income']:,.1f}{u_sfx}</span></div>
        <div class="kv-row"><span class="kv-label">credit_income_ratio:</span><span class="kv-val mono">{base_lev:.2f}x</span></div>
        <div class="kv-row"><span class="kv-label">Điểm rủi ro ML:</span><span class="kv-val mono">{base_pd:.4f}</span></div>
        <div class="kv-row"><span class="kv-label">Khuyến nghị gốc:</span><span class="kv-val mono">{sim_app.get('recommendation_code', sim_app['risk_level'])}</span></div>
    </div>
    <div style="background:#FFFFFF; border:1px solid {rec_color}; border-top:4px solid {rec_color}; border-radius:10px; padding:14px; box-shadow:0 2px 8px rgba(15,23,42,0.05);">
        <div style="font-size:0.74rem; font-weight:700; color:{rec_color}; margin-bottom:10px;">KỊCH BẢN MỚI (AFTER)</div>
        <div class="kv-row"><span class="kv-label">Tín dụng / Thu nhập mới:</span><span class="kv-val mono">{new_credit:,.1f}{u_sfx} / {new_income:,.1f}{u_sfx}</span></div>
        <div class="kv-row"><span class="kv-label">credit_income_ratio mới:</span><span class="kv-val mono" style="color:#1D4ED8;">{new_lev:.2f}x</span></div>
        <div class="kv-row"><span class="kv-label">Điểm rủi ro mới:</span><span class="kv-val mono" style="color:{rec_color};">{new_pd:.4f} ({delta_pd:+.4f})</span></div>
        <div class="kv-row"><span class="kv-label">Khuyến nghị mới:</span><span class="kv-val mono" style="color:{rec_color};">{new_rec}</span></div>
    </div>
</div>
<div style="font-size:0.74rem; color:#64748B; font-style:italic; margin-top:8px;">
    * Kết quả giả định (hypothetical), đã đồng bộ đúng thang đo đơn vị nguồn (unit_scale={int(unit_scale):,}x) với pipeline ML và không ghi đè dữ liệu gốc DW.
</div>
""",
                unsafe_allow_html=True,
            )

            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            if st.button(
                "📌 Đẩy kết quả mô phỏng sang Ghi chú Phê duyệt",
                type="primary",
                disabled=(rev_thresh >= dec_thresh),
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
