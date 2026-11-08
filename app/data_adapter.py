"""
TẦNG KẾT NỐI DỮ LIỆU & MACHINE LEARNING ADAPTER (CONTRACT V1)
Nạp model bundle từ Phân hệ Người 2 (ML), chuẩn hóa 16 predictors theo contracts/features-v1.json
và khởi tạo phiên làm việc cho Cán bộ Thẩm định (Officer).
"""

from datetime import datetime
from pathlib import Path
import sys
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if not (PROJECT_ROOT / "ml").exists():
    PROJECT_ROOT = Path(__file__).resolve().parent
ML_PATH = PROJECT_ROOT / "ml"

for p in (PROJECT_ROOT, ML_PATH):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

try:
    from credit_ml.inference import load_bundle, assess
    from credit_ml.policy import PolicyConfig
    from credit_ml.whatif import what_if

    MODELS_DIR = ML_PATH / "results" / "models"
    MODEL_BUNDLE = load_bundle(str(MODELS_DIR), "logreg_v1_20261106", model_run_id=1)
    ML_LOADED = True
    REVIEW_THRESHOLD = float(MODEL_BUNDLE.policy.review_threshold)   # 0.10
    DECLINE_THRESHOLD = float(MODEL_BUNDLE.policy.decline_threshold) # 0.25
    MODEL_NAME_LABEL = f"{MODEL_BUNDLE.model_name} ({MODEL_BUNDLE.policy.version})"
except Exception:
    MODEL_BUNDLE = None
    ML_LOADED = False
    REVIEW_THRESHOLD = 0.10
    DECLINE_THRESHOLD = 0.25
    MODEL_NAME_LABEL = "logistic_regression_v1 (policy_v1_illustrative)"


FEATURE_LABELS_VI = {
    "ext_source_1": "Điểm nguồn ngoài 1 (EXT_1)",
    "ext_source_2": "Điểm nguồn ngoài 2 (EXT_2)",
    "ext_source_3": "Điểm CIC / EXT_3",
    "credit_income_ratio": "Hệ số Tín dụng / Thu nhập",
    "amt_income_total": "Tổng thu nhập khai báo",
    "amt_credit": "Giá trị tín dụng đề nghị",
    "amt_annuity": "Nghĩa vụ trả góp định kỳ",
    "age_years": "Độ tuổi khách hàng",
    "employment_days": "Thâm niên công tác",
    "education_level": "Trình độ học vấn",
    "income_type": "Nhóm nguồn thu nhập",
    "contract_type_name": "Loại hợp đồng vay",
    "previous_application_count": "Số hồ sơ vay trước đây",
    "previous_approved_count": "Số lần được duyệt trước đây",
    "previous_refused_count": "Số lần bị từ chối trước đây",
    "previous_approval_rate": "Tỷ lệ duyệt lịch sử",
}


def enrich_with_real_ml(app_record: dict) -> dict:
    """Chấm điểm thực tế bằng MODEL_BUNDLE của Người 2 (nếu có) trên 16 predictors chuẩn."""
    if not ML_LOADED or MODEL_BUNDLE is None:
        return app_record
    try:
        res = assess(MODEL_BUNDLE, int(app_record["id"]), app_record["features"])
        app_record["pd"] = float(res["risk_score"])
        app_record["risk_level"] = str(res["risk_band"])
        app_record["recommendation_code"] = str(res["recommendation"])
        app_record["reason_codes"] = list(res.get("reason_codes", []))
        app_record["alerts"] = list(res.get("alerts", []))

        # Chuyển model_factors thật (đóng góp log-odds) sang định dạng hiển thị
        real_drivers = []
        for f in res.get("model_factors", []):
            feat_key = f["feature"]
            contrib = float(f["log_odds_contribution"])
            is_lowers = f["direction"] == "lowers_risk"
            desc = "↓ Giảm rủi ro" if is_lowers else "↑ Tăng rủi ro"
            label_vi = FEATURE_LABELS_VI.get(feat_key, feat_key)
            real_drivers.append(
                (f"{feat_key} ({label_vi})", desc, f"{contrib:+.3f}", "pos" if is_lowers else "neg")
            )
        if real_drivers:
            app_record["drivers"] = real_drivers
    except Exception:
        pass
    return app_record


def init_session_data():
    """Khởi tạo dữ liệu phiên làm việc nếu chưa có trong st.session_state."""
    if "applications" not in st.session_state:
        raw_apps = {
            "1001": {
                "id": "1001",
                "applicant": "Nguyễn Văn An",
                "product": "Vay tiền mặt (Cash Loans)",
                "short_product": "Cash loans",
                "income": 100.0,
                "credit": 200.0,
                "annuity": 10.0,
                "goods": 190.0,
                "target": 1,
                "pd": 0.017,
                "risk_level": "LOW",
                "recommendation_code": "APPROVE_SIMULATION",
                "sla": "45 phút",
                "status": "Chờ duyệt",
                "default_decision": "✓ Phê duyệt",
                "age_band": "25-39",
                "age": "30 tuổi (25-39)",
                "emp_years": "3.5 năm",
                "edu": "Đại học (Higher education)",
                "inc_type": "Lương doanh nghiệp (Working)",
                "marital": "Độc thân (Single)",
                "assets": "Có Ô tô • Chưa có BĐS",
                "hist_total": "2 đơn hợp lệ",
                "hist_app": "1 lần",
                "hist_ref": "1 lần",
                "hist_rate": "50.0%",
                "ext3": "0.640 (Tốt)",
                "dpd": "Không phát sinh trễ hạn",
                # Đúng 16 predictors theo contracts/features-v1.json
                "features": {
                    "amt_income_total": 100.0,
                    "amt_credit": 200.0,
                    "amt_annuity": 10.0,
                    "credit_income_ratio": 2.0,
                    "age_years": 30.0,
                    "employment_days": 1278,
                    "income_type": "Working",
                    "education_level": "Higher education",
                    "contract_type_name": "Cash loans",
                    "ext_source_1": 0.62,
                    "ext_source_2": 0.68,
                    "ext_source_3": 0.64,
                    "previous_application_count": 2,
                    "previous_approved_count": 1,
                    "previous_refused_count": 1,
                    "previous_approval_rate": 0.5,
                },
                "drivers": [
                    ("ext_source_3 (Điểm CIC / EXT_3)", "↓ Giảm rủi ro", "-1.310", "pos"),
                    ("amt_income_total (Tổng thu nhập)", "↑ Tăng rủi ro", "+1.251", "neg"),
                    ("amt_annuity (Trả góp định kỳ)", "↓ Giảm rủi ro", "-0.492", "pos"),
                ],
            },
            "1002": {
                "id": "1002",
                "applicant": "Trần Thị Bích Ngọc",
                "product": "Hạn mức quay vòng (Revolving)",
                "short_product": "Revolving loans",
                "income": 180.0,
                "credit": 300.0,
                "annuity": 15.0,
                "goods": 300.0,
                "target": 0,
                "pd": 0.004,
                "risk_level": "LOW",
                "recommendation_code": "APPROVE_SIMULATION",
                "sla": "2 giờ 10 phút",
                "status": "Đã duyệt",
                "default_decision": "✓ Phê duyệt",
                "age_band": "40-59",
                "age": "44 tuổi (40-59)",
                "emp_years": "8.2 năm",
                "edu": "Sau đại học (Academic degree)",
                "inc_type": "Chủ doanh nghiệp (Commercial)",
                "marital": "Đã kết hôn (Married)",
                "assets": "Có Ô tô • Có BĐS",
                "hist_total": "4 đơn hợp lệ",
                "hist_app": "4 lần",
                "hist_ref": "0 lần",
                "hist_rate": "100.0%",
                "ext3": "0.785 (Rất tốt)",
                "dpd": "Không phát sinh trễ hạn",
                "features": {
                    "amt_income_total": 180.0,
                    "amt_credit": 300.0,
                    "amt_annuity": 15.0,
                    "credit_income_ratio": 300.0 / 180.0,
                    "age_years": 44.0,
                    "employment_days": 2993,
                    "income_type": "Commercial associate",
                    "education_level": "Academic degree",
                    "contract_type_name": "Revolving loans",
                    "ext_source_1": 0.75,
                    "ext_source_2": 0.81,
                    "ext_source_3": 0.785,
                    "previous_application_count": 4,
                    "previous_approved_count": 4,
                    "previous_refused_count": 0,
                    "previous_approval_rate": 1.0,
                },
                "drivers": [
                    ("previous_approval_rate (Tỷ lệ duyệt lịch sử)", "↓ Giảm rủi ro mạnh", "-1.650", "pos"),
                    ("employment_days (Thâm niên công tác)", "↓ Giảm rủi ro", "-0.810", "pos"),
                    ("amt_credit (Giá trị tín dụng đề nghị)", "↑ Tăng nhẹ rủi ro", "+0.215", "neg"),
                ],
            },
            "1003": {
                "id": "1003",
                "applicant": "Lê Hoàng Nam",
                "product": "Vay mua tài sản (Asset-Backed)",
                "short_product": "Unknown",
                "income": 120.0,
                "credit": 500.0,
                "annuity": 28.5,
                "goods": 460.0,
                "target": 0,
                "pd": 0.302,
                "risk_level": "HIGH",
                "recommendation_code": "DECLINE_SIMULATION",
                "sla": "12 phút (Khẩn)",
                "status": "Chờ duyệt",
                "default_decision": "✕ Từ chối",
                "age_band": "25-39",
                "age": "27 tuổi (25-39)",
                "emp_years": "0.8 năm",
                "edu": "Trung học phổ thông (Secondary)",
                "inc_type": "Lương doanh nghiệp (Working)",
                "marital": "Độc thân (Single)",
                "assets": "Chưa có Ô tô • Chưa có BĐS",
                "hist_total": "3 đơn hợp lệ",
                "hist_app": "1 lần",
                "hist_ref": "2 lần",
                "hist_rate": "33.3%",
                "ext3": "0.210 (Kém)",
                "dpd": "Trễ hạn 15 ngày (Kỳ trước)",
                "features": {
                    "amt_income_total": 120.0,
                    "amt_credit": 500.0,
                    "amt_annuity": 28.5,
                    "credit_income_ratio": 500.0 / 120.0,
                    "age_years": 27.0,
                    "employment_days": 292,
                    "income_type": "Working",
                    "education_level": "Secondary / secondary special",
                    "contract_type_name": "Unknown",
                    "ext_source_1": 0.18,
                    "ext_source_2": 0.24,
                    "ext_source_3": 0.21,
                    "previous_application_count": 3,
                    "previous_approved_count": 1,
                    "previous_refused_count": 2,
                    "previous_approval_rate": 1.0 / 3.0,
                },
                "drivers": [
                    ("credit_income_ratio (Hệ số Tín dụng / Thu nhập)", "↑ Tăng rủi ro nghiêm trọng", "+2.140", "neg"),
                    ("ext_source_3 (Điểm CIC / EXT_3)", "↑ Tăng rủi ro cao", "+1.580", "neg"),
                    ("previous_refused_count (Số lần bị từ chối)", "↑ Tăng rủi ro", "+0.890", "neg"),
                ],
            },
            "1004": {
                "id": "1004",
                "applicant": "Phạm Minh Tuấn",
                "product": "Vay tiền mặt (Cash Loans)",
                "short_product": "Cash loans",
                "income": 90.0,
                "credit": 220.0,
                "annuity": 16.5,
                "goods": 200.0,
                "target": 0,
                "pd": 0.131,
                "risk_level": "MEDIUM",
                "recommendation_code": "REVIEW",
                "sla": "30 phút",
                "status": "Chờ duyệt",
                "default_decision": "👁 Xem xét thêm",
                "age_band": "25-39",
                "age": "35 tuổi (25-39)",
                "emp_years": "2.5 năm",
                "edu": "Trung học chuyên nghiệp (Secondary special)",
                "inc_type": "Lương doanh nghiệp (Working)",
                "marital": "Đã kết hôn (Married)",
                "assets": "Chưa có Ô tô • Có BĐS",
                "hist_total": "2 đơn hợp lệ",
                "hist_app": "1 lần",
                "hist_ref": "1 lần",
                "hist_rate": "50.0%",
                "ext3": "0.360 (Trung bình)",
                "dpd": "Không phát sinh trễ hạn",
                "features": {
                    "amt_income_total": 90.0,
                    "amt_credit": 220.0,
                    "amt_annuity": 16.5,
                    "credit_income_ratio": 220.0 / 90.0,
                    "age_years": 35.0,
                    "employment_days": 912,
                    "income_type": "Working",
                    "education_level": "Secondary / secondary special",
                    "contract_type_name": "Cash loans",
                    "ext_source_1": 0.35,
                    "ext_source_2": 0.38,
                    "ext_source_3": 0.36,
                    "previous_application_count": 2,
                    "previous_approved_count": 1,
                    "previous_refused_count": 1,
                    "previous_approval_rate": 0.5,
                },
                "drivers": [
                    ("ext_source_3 (Điểm CIC / EXT_3)", "↑ Cần thẩm định thêm", "+0.380", "neg"),
                    ("credit_income_ratio (Hệ số Tín dụng / Thu nhập)", "↑ Cảnh báo nhẹ", "+0.210", "neg"),
                    ("amt_credit (Giá trị tín dụng đề nghị)", "↓ Trong ngưỡng cân nhắc", "-0.195", "pos"),
                ],
            },
        }

        # Chấm điểm thực tế từng hồ sơ bằng mô hình ML thực tế của Người 2
        st.session_state.applications = {
            aid: enrich_with_real_ml(app_data) for aid, app_data in raw_apps.items()
        }

    if "audit_logs" not in st.session_state:
        st.session_state.audit_logs = [
            {
                "Mã GD": "DEC-901",
                "Mã Hồ Sơ": "#1002",
                "Khách Hàng": "Trần Thị Bích Ngọc",
                "Quyết Định": "Phê duyệt",
                "Mã Lý Do": "PAS_01: Đạt toàn bộ tiêu chí khẩu vị rủi ro chuẩn",
                "Ghi Chú Nghiệp Vụ": (
                    "Khách hàng có lịch sử trả nợ tốt 100%, sở hữu BĐS và ô tô."
                ),
                "Cán Bộ Thẩm Định": "Officer",
                "Thời Gian Ghi Nhận": "2026-11-08 01:40:19",
            }
        ]

    if "draft_note" not in st.session_state:
        st.session_state.draft_note = ""

    if "last_selected_id" not in st.session_state:
        st.session_state.last_selected_id = "1001"

    if "sim_selected_id" not in st.session_state:
        st.session_state.sim_selected_id = "1001"
