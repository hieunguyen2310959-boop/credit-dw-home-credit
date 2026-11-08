"""
TAB 2: BÁO CÁO PHÂN TÍCH ĐA CHIỀU OLAP (ROLL-UP & SLICE & DICE)
Hiển thị biểu đồ cột phân bổ rủi ro và bảng ma trận phân bổ giá trị tín dụng (Cross-tab matrix),
đồng bộ động 100% với danh sách hồ sơ trong Data Mart.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def render_tab_olap():
    """Render giao diện chính của Tab 2 (OLAP Analytics & Matrix)."""
    apps_list = list(st.session_state.applications.values())

    with st.container(border=True):
        st.markdown(
            '<div class="section-title">📊 PHÂN TÍCH ĐA CHIỀU OLAP (ROLL-UP &'
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
    <strong>Quy ước DWH (sql/004_analytics.sql):</strong><br>
    • Đã chuẩn hóa nhãn khuyết về <code>Unknown</code>.<br>
    • Không nhân bản dòng hồ sơ khi nối lịch sử.<br>
    • Hiển thị rõ nhãn cho phân khúc có tỷ lệ <code>0.0%</code>.
</div>
""",
                unsafe_allow_html=True,
            )

        with olap_right:
            # Tính toán động hoàn toàn từ tập hồ sơ hiện tại
            if dim_choice == "Nhóm độ tuổi (Age Band)":
                groups = [
                    ("Nhóm 25-39 tuổi", [a for a in apps_list if a["age_band"] == "25-39"]),
                    ("Nhóm 40-59 tuổi", [a for a in apps_list if a["age_band"] == "40-59"]),
                ]
            elif dim_choice == "Loại hợp đồng (Contract Type)":
                groups = [
                    ("Cash loans", [a for a in apps_list if a["short_product"] == "Cash loans"]),
                    ("Revolving loans", [a for a in apps_list if a["short_product"] == "Revolving loans"]),
                    ("Unknown (Đã chuẩn hóa)", [a for a in apps_list if a["short_product"] == "Unknown"]),
                ]
            else:
                groups = [
                    ("Lương DN (Working)", [a for a in apps_list if a["features"]["income_type"] == "Working"]),
                    ("Chủ DN (Commercial)", [a for a in apps_list if a["features"]["income_type"] == "Commercial associate"]),
                ]

            categories = [g[0] for g in groups]
            vals = []
            for _, subset in groups:
                n_sub = len(subset)
                if "Tỷ lệ" in measure_choice:
                    rate = (sum(1 for a in subset if a.get("target") == 1) / n_sub * 100.0) if n_sub else 0.0
                    vals.append(rate)
                elif "Tổng giá trị" in measure_choice:
                    vals.append(sum(a["credit"] for a in subset))
                else:
                    vals.append(n_sub)

            plot_vals = [v if v > 0 else 1.5 for v in vals]
            bar_colors = [
                "#991B1B" if ("%" in measure_choice and v > 20)
                else ("#10B981" if v == 0 else "#1D4ED8")
                for v in vals
            ]
            bar_labels = [
                f"{v:.1f}% (An toàn)"
                if ("%" in measure_choice and v == 0)
                else (
                    f"{v:.1f}%"
                    if "%" in measure_choice
                    else (f"{v:.1f}M" if "Credit" in measure_choice else f"{v} hồ sơ")
                )
                for v in vals
            ]

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
                    text=f"{measure_choice} theo {dim_choice}",
                    font=dict(size=14, color="#0F172A"),
                ),
                height=310,
                margin=dict(l=20, r=20, t=45, b=20),
                yaxis=dict(
                    title=measure_choice,
                    range=[0, max(plot_vals) * 1.25],
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
            '<div class="section-title">🧮 BẢNG MA TRẬN PHÂN BỔ GIÁ TRỊ TÍN DỤNG'
            " (CROSS-TAB MATRIX - ĐỒNG BỘ COHORT)</div>",
            unsafe_allow_html=True,
        )
        age_25_39 = [a for a in apps_list if a["age_band"] == "25-39"]
        age_40_59 = [a for a in apps_list if a["age_band"] == "40-59"]

        def sum_prod(subset, prod_name):
            matched = [a for a in subset if a["short_product"] == prod_name]
            tot = sum(a["credit"] for a in matched)
            cnt = len(matched)
            return f"{tot:.1f}M ({cnt} đơn)"

        matrix_df = pd.DataFrame({
            "Nhóm độ tuổi (age_band)": ["25 - 39 tuổi", "40 - 59 tuổi", "Tổng cộng danh mục"],
            "Cash loans": [
                sum_prod(age_25_39, "Cash loans"),
                sum_prod(age_40_59, "Cash loans"),
                sum_prod(apps_list, "Cash loans"),
            ],
            "Revolving loans": [
                sum_prod(age_25_39, "Revolving loans"),
                sum_prod(age_40_59, "Revolving loans"),
                sum_prod(apps_list, "Revolving loans"),
            ],
            "Unknown (Đã chuẩn hóa)": [
                sum_prod(age_25_39, "Unknown"),
                sum_prod(age_40_59, "Unknown"),
                sum_prod(apps_list, "Unknown"),
            ],
            "Tổng giá trị tín dụng": [
                f"{sum(a['credit'] for a in age_25_39):.1f}M ({len(age_25_39)} đơn)",
                f"{sum(a['credit'] for a in age_40_59):.1f}M ({len(age_40_59)} đơn)",
                f"{sum(a['credit'] for a in apps_list):.1f}M ({len(apps_list)} đơn)",
            ],
        })
        st.dataframe(matrix_df, use_container_width=True, hide_index=True)
