"""
Báo cáo phân tích đa chiều OLAP: phân bổ rủi ro danh mục và ma trận chéo (Cross-tab).
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from app.data_adapter import fetch_olap_distribution, fetch_olap_cross_tab, get_db_vendor_label


def render_tab_olap():
    """Render giao diện chính của Tab 2 (OLAP Analytics & Matrix trực tiếp từ DWH)."""
    apps_list = list(st.session_state.applications.values())

    with st.container(border=True):
        st.markdown(
            '<div class="section-title">PHÂN TÍCH ĐA CHIỀU OLAP (ROLL-UP &'
            " SLICE & DICE)</div>",
            unsafe_allow_html=True,
        )
        olap_left, olap_right = st.columns([3.2, 8.8], gap="large")

        with olap_left:
            dim_choice = st.selectbox(
                "Chọn chiều phân tích (Dimension):",
                [
                    "Nhóm độ tuổi (Age Band)",
                    "Loại hợp đồng (Contract Type)",
                    "Nguồn thu nhập (Income Type)",
                    "Trình độ học vấn (Education Level)",
                ],
            )
            measure_choice = st.radio(
                "Chỉ số đo lường (Measure):",
                [
                    "Tỷ lệ khó khăn thanh toán TARGET=1 (%)",
                    "Tổng giá trị tín dụng đề nghị (Credit)",
                    "Số lượng hồ sơ",
                ],
            )
            st.markdown(
                """
<div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:10px; font-size:0.75rem; color:#475569; margin-top:8px;">
    <strong>Quy ước DWH (mart.application_overview_v1):</strong><br>
    • Truy vấn trực tiếp từ <strong>Kho dữ liệu Cloud (307,511 hồ sơ)</strong>.<br>
    • Đã chuẩn hóa nhãn khuyết về <code>Unknown</code>.<br>
    • Đơn vị chuẩn SI: <code>M</code> = Triệu (10⁶), <code>B</code> = Tỷ (10⁹).<br>
    • Hiển thị rõ nhãn cho phân khúc có tỷ lệ <code>0.0%</code>.
</div>
""",
                unsafe_allow_html=True,
            )

        with olap_right:
            olap_live = fetch_olap_distribution(dim_choice, measure_choice)

            if olap_live:
                categories = olap_live["categories"]
                vals = olap_live["vals"]
                bar_labels = olap_live["labels"]
            else:
                vendor_label = get_db_vendor_label()
                st.warning(
                    f"⚠️ Không kết nối được {vendor_label} DWH — Biểu đồ OLAP đang tạm tính trên "
                    f"{len(apps_list)} hồ sơ trong bộ nhớ (không phản ánh toàn bộ 307,511 hồ sơ)."
                )
                if dim_choice == "Nhóm độ tuổi (Age Band)":
                    groups = [
                        ("Nhóm <25 tuổi", [a for a in apps_list if a.get("age_band") == "<25"]),
                        ("Nhóm 25-39 tuổi", [a for a in apps_list if a.get("age_band") == "25-39"]),
                        ("Nhóm 40-59 tuổi", [a for a in apps_list if a.get("age_band") == "40-59"]),
                        ("Nhóm 60+ tuổi", [a for a in apps_list if a.get("age_band") == "60+"]),
                        ("Unknown", [a for a in apps_list if a.get("age_band") == "Unknown"]),
                    ]
                    groups = [(k, v) for k, v in groups if v]
                elif dim_choice == "Loại hợp đồng (Contract Type)":
                    groups = [
                        ("Cash loans", [a for a in apps_list if a.get("short_product") == "Cash loans"]),
                        ("Revolving loans", [a for a in apps_list if a.get("short_product") == "Revolving loans"]),
                        ("Unknown (Đã chuẩn hóa)", [a for a in apps_list if a.get("short_product") == "Unknown"]),
                    ]
                    groups = [(k, v) for k, v in groups if v]
                elif dim_choice == "Trình độ học vấn (Education Level)":
                    edu_keys = sorted({str(a.get("features", {}).get("education_level") or "Unknown") for a in apps_list})
                    groups = [
                        (ek, [a for a in apps_list if str(a.get("features", {}).get("education_level") or "Unknown") == ek])
                        for ek in edu_keys
                    ]
                else:
                    inc_keys = sorted({str(a.get("features", {}).get("income_type") or "Unknown") for a in apps_list})
                    groups = [
                        (ik, [a for a in apps_list if str(a.get("features", {}).get("income_type") or "Unknown") == ik])
                        for ik in inc_keys
                    ]

                categories = [g[0] for g in groups]
                vals = []
                for _, subset in groups:
                    n_sub = len(subset)
                    if "Tỷ lệ" in measure_choice:
                        labeled = [a for a in subset if a.get("target") is not None]
                        rate = (sum(1 for a in labeled if a.get("target") == 1) / len(labeled) * 100.0) if labeled else 0.0
                        vals.append(rate)
                    elif "Tổng giá trị" in measure_choice:
                        tot_m = sum(
                            (a.get("credit") or 0.0) * a.get("unit_scale", 1_000.0) / 1_000_000.0
                            for a in subset
                        )
                        vals.append(tot_m)
                    else:
                        vals.append(n_sub)

                bar_labels = [
                    f"{v:.1f}% (An toàn)"
                    if ("%" in measure_choice and v == 0)
                    else (
                        f"{v:.1f}%"
                        if "%" in measure_choice
                        else (f"{v:,.2f}M" if "Credit" in measure_choice else f"{int(v):,} hồ sơ")
                    )
                    for v in vals
                ]

            plot_vals = vals
            if "%" in measure_choice:
                bar_colors = [
                    "#DC2626" if v >= 10.0
                    else ("#D97706" if v >= 7.0 else ("#10B981" if v == 0 else "#2563EB"))
                    for v in vals
                ]
            else:
                bar_colors = ["#10B981" if v == 0 else "#1D4ED8" for v in vals]

            source_tag = (
                f"Live DWH ({get_db_vendor_label()}) • 307,511 hồ sơ"
                if olap_live
                else f"Chế độ Ngoại tuyến • {len(apps_list)} hồ sơ mẫu"
            )
            fig_olap = go.Figure(
                go.Bar(
                    x=categories,
                    y=plot_vals,
                    text=bar_labels,
                    textposition="outside",
                    marker_color=bar_colors,
                    width=0.42,
                )
            )
            fig_olap.update_layout(
                title=dict(
                    text=f"{measure_choice} theo {dim_choice} ({source_tag})",
                    font=dict(size=14, color="#0F172A"),
                ),
                height=340,
                margin=dict(l=20, r=20, t=48, b=20),
                yaxis=dict(
                    title=measure_choice,
                    range=[0, max(plot_vals) * 1.28] if plot_vals else [0, 10],
                    gridcolor="#F1F5F9",
                ),
                xaxis=dict(title="Phân khúc danh mục"),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(
                fig_olap,
                use_container_width=True,
                config={"displayModeBar": False},
            )

    with st.container(border=True):
        st.markdown(
            '<div class="section-title">BẢNG MA TRẬN PHÂN BỔ GIÁ TRỊ TÍN DỤNG'
            " (CROSS-TAB MATRIX - KHO DỮ LIỆU DWH)</div>",
            unsafe_allow_html=True,
        )
        cross_tab_df = fetch_olap_cross_tab()
        if cross_tab_df is not None:
            st.dataframe(cross_tab_df, use_container_width=True, hide_index=True)
            st.caption(
                "Ghi chú: Giá trị tín dụng hiển thị theo triệu đơn vị nguồn (M). "
                "Cột Tỷ lệ rủi ro (TARGET=1) được tổng hợp trực tiếp trên 307,511 hồ sơ có nhãn lịch sử."
            )
        else:
            band_defs = [
                ("<25", "< 25 tuổi"),
                ("25-39", "25 - 39 tuổi"),
                ("40-59", "40 - 59 tuổi"),
                ("60+", "60+ tuổi"),
            ]
            active_bands = [
                (code, label, [a for a in apps_list if a.get("age_band") == code])
                for code, label in band_defs
            ]
            active_bands = [(c, l, sub) for c, l, sub in active_bands if sub]

            def _fmt_cell(subset, prod_name):
                matched = [a for a in subset if a.get("short_product") == prod_name]
                tot_m = sum((a.get("credit") or 0.0) * a.get("unit_scale", 1_000.0) / 1_000_000.0 for a in matched)
                return f"{tot_m:,.2f}M ({len(matched)} đơn)"

            def _fmt_bad_rate(subset):
                labeled = [a for a in subset if a.get("target") is not None]
                if not labeled:
                    return "N/A"
                bad_cnt = sum(1 for a in labeled if a.get("target") == 1)
                return f"{(bad_cnt / len(labeled) * 100.0):.2f}%"

            matrix_df = pd.DataFrame({
                "Nhóm độ tuổi (age_band)": [l for _, l, _ in active_bands] + ["Tổng cộng danh mục"],
                "Cash loans": [
                    _fmt_cell(sub, "Cash loans") for _, _, sub in active_bands
                ] + [_fmt_cell(apps_list, "Cash loans")],
                "Revolving loans": [
                    _fmt_cell(sub, "Revolving loans") for _, _, sub in active_bands
                ] + [_fmt_cell(apps_list, "Revolving loans")],
                "Unknown (Đã chuẩn hóa)": [
                    _fmt_cell(sub, "Unknown") for _, _, sub in active_bands
                ] + [_fmt_cell(apps_list, "Unknown")],
                "Tổng giá trị tín dụng": [
                    f"{sum((a.get('credit') or 0.0) * a.get('unit_scale', 1_000.0) / 1_000_000.0 for a in sub):,.2f}M ({len(sub)} đơn)"
                    for _, _, sub in active_bands
                ] + [
                    f"{sum((a.get('credit') or 0.0) * a.get('unit_scale', 1_000.0) / 1_000_000.0 for a in apps_list):,.2f}M ({len(apps_list)} đơn)"
                ],
                "Tỷ lệ rủi ro (TARGET=1)": [
                    _fmt_bad_rate(sub) for _, _, sub in active_bands
                ] + [_fmt_bad_rate(apps_list)],
            })
            st.dataframe(matrix_df, use_container_width=True, hide_index=True)
