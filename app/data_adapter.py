"""
Tầng tích hợp dữ liệu kho (DWH) và mô hình suy luận rủi ro tín dụng (ML Inference).
"""

import os
from datetime import datetime
from pathlib import Path
import sys
import pandas as pd
import psycopg
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
    ML_LOAD_ERROR = None
    REVIEW_THRESHOLD = float(MODEL_BUNDLE.policy.review_threshold)   # 0.10
    DECLINE_THRESHOLD = float(MODEL_BUNDLE.policy.decline_threshold) # 0.25
    MODEL_NAME_LABEL = f"{MODEL_BUNDLE.model_name} ({MODEL_BUNDLE.policy.version})"
except Exception as exc:
    MODEL_BUNDLE = None
    ML_LOADED = False
    ML_LOAD_ERROR = f"{type(exc).__name__}: {exc}"
    REVIEW_THRESHOLD = 0.10
    DECLINE_THRESHOLD = 0.25
    MODEL_NAME_LABEL = "logistic_regression_v1 (policy_v1_illustrative)"


def get_db_vendor_label(dsn: str | None = None) -> str:
    """Trả về nhãn nền tảng cơ sở dữ liệu dựa trên DATABASE_URL cấu hình."""
    url = os.environ.get("DATABASE_URL", "") if dsn is None else dsn
    if "neon.tech" in url:
        return "Neon Cloud"
    if "localhost" in url or "127.0.0.1" in url:
        return "Local PostgreSQL"
    if url:
        return "Cloud PostgreSQL"
    return "Offline Demo"


FEATURE_LABELS_VI = {
    "ext_source_1": "Điểm nguồn ngoài 1 (EXT_1)",
    "ext_source_2": "Điểm nguồn ngoài 2 (EXT_2)",
    "ext_source_3": "Điểm nguồn ngoài 3 (EXT_3)",
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


def mark_ml_error(app_record: dict, error_detail: str) -> dict:
    """Đưa hồ sơ về trạng thái lỗi ML fail-closed để chặn phê duyệt tự động."""
    app_record["pd"] = None
    app_record["risk_level"] = "ERROR"
    app_record["recommendation_code"] = "ML_ERROR"
    app_record["default_decision"] = "👁 Xem xét thêm"
    app_record["ml_error"] = error_detail
    app_record["assessment_result"] = None
    app_record["reason_codes"] = ["ML_SCORING_FAILED"]
    app_record["alerts"] = [
        {"code": "ML_SCORING_ERROR", "severity": "high", "message": error_detail}
    ]
    app_record["drivers"] = []
    try:
        st.error("Chưa tải được mô hình. Kiểm tra artifact và phiên bản thư viện trước khi chấm điểm.")
    except Exception:
        pass
    return app_record


def enrich_with_real_ml(app_record: dict) -> dict:
    """Suy luận điểm rủi ro qua mô hình ML (fail-closed khi model lỗi hoặc thiếu)."""
    if not ML_LOADED or MODEL_BUNDLE is None:
        return mark_ml_error(
            app_record,
            ML_LOAD_ERROR or "Mô hình ML chưa được nạp (MODEL_BUNDLE=None).",
        )
    try:
        res = assess(MODEL_BUNDLE, int(app_record["id"]), app_record["features"])
        app_record["ml_error"] = None
        app_record["assessment_result"] = res
        app_record["pd"] = float(res["risk_score"])
        app_record["risk_level"] = str(res["risk_band"])
        rec_code = str(res["recommendation"])
        app_record["recommendation_code"] = rec_code
        app_record["reason_codes"] = list(res.get("reason_codes", []))
        app_record["alerts"] = list(res.get("alerts", []))

        rec_to_decision = {
            "APPROVE_SIMULATION": "✓ Phê duyệt",
            "REVIEW": "👁 Xem xét thêm",
            "DECLINE_SIMULATION": "✕ Từ chối",
        }
        if app_record.get("status") not in ("Đã xử lý", "Đã duyệt"):
            app_record["default_decision"] = rec_to_decision.get(
                rec_code, "👁 Xem xét thêm"
            )

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
    except Exception as exc:
        return mark_ml_error(app_record, f"{type(exc).__name__}: {exc}")
    return app_record


LAST_DB_ERROR: str | None = None


def get_last_db_error() -> str | None:
    """Trả về thông báo lỗi DB gần nhất (nếu có) để giao diện hiển thị trung thực."""
    return LAST_DB_ERROR


def get_db_connection():
    global LAST_DB_ERROR
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        LAST_DB_ERROR = "Biến môi trường DATABASE_URL chưa được cấu hình."
        return None
    conn = None
    try:
        conn = psycopg.connect(dsn, autocommit=True, connect_timeout=8)
        conn.execute("SET statement_timeout = 0")
        LAST_DB_ERROR = None
        return conn
    except Exception as exc:
        LAST_DB_ERROR = f"{type(exc).__name__}: {exc}"
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        return None


@st.cache_data(ttl=600, show_spinner=False)
def fetch_dwh_kpi_summary():
    """Lấy số liệu tổng hợp trực tiếp từ mart.application_overview_v1 (307,511 hồ sơ)."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn:
            r = conn.execute("""
                SELECT
                    count(*) AS total_applications,
                    count(target) AS labeled_applications,
                    count(*) FILTER (WHERE target = 1) AS bad_loans_count,
                    round((count(*) FILTER (WHERE target = 1)::numeric / NULLIF(count(target), 0) * 100), 2) AS bad_rate,
                    sum(amt_credit) AS total_credit
                FROM mart.application_overview_v1;
            """).fetchone()
            if r:
                return {
                    "total_applications": int(r[0]),
                    "labeled_applications": int(r[1]),
                    "bad_loans_count": int(r[2]),
                    "bad_rate": float(r[3]) if r[3] is not None else 0.0,
                    "total_credit": float(r[4]) if r[4] is not None else 0.0,
                    "source": f"{get_db_vendor_label()} (PostgreSQL)"
                }
    except Exception:
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return None


@st.cache_data(ttl=600, show_spinner=False)
def fetch_olap_distribution(dim_choice: str, measure_choice: str):
    """Truy vấn phân bổ đa chiều OLAP trực tiếp từ mart.application_overview_v1."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn:
            if dim_choice == "Nhóm độ tuổi (Age Band)":
                sql_q = """
                    SELECT
                        age_band AS category,
                        count(*) AS count_val,
                        round((count(*) FILTER (WHERE target = 1)::numeric / NULLIF(count(target), 0) * 100), 2) AS bad_rate,
                        sum(amt_credit) AS total_credit
                    FROM mart.application_overview_v1
                    GROUP BY age_band
                    ORDER BY CASE age_band WHEN '<25' THEN 1 WHEN '25-39' THEN 2 WHEN '40-59' THEN 3 WHEN '60+' THEN 4 ELSE 5 END;
                """
            elif dim_choice == "Loại hợp đồng (Contract Type)":
                sql_q = """
                    SELECT
                        COALESCE(contract_type_name, 'Unknown') AS category,
                        count(*) AS count_val,
                        round((count(*) FILTER (WHERE target = 1)::numeric / NULLIF(count(target), 0) * 100), 2) AS bad_rate,
                        sum(amt_credit) AS total_credit
                    FROM mart.application_overview_v1
                    GROUP BY contract_type_name
                    ORDER BY count_val DESC;
                """
            elif dim_choice == "Trình độ học vấn (Education Level)":
                sql_q = """
                    SELECT
                        COALESCE(education_level, 'Unknown') AS category,
                        count(*) AS count_val,
                        round((count(*) FILTER (WHERE target = 1)::numeric / NULLIF(count(target), 0) * 100), 2) AS bad_rate,
                        sum(amt_credit) AS total_credit
                    FROM mart.application_overview_v1
                    GROUP BY education_level
                    ORDER BY count_val DESC;
                """
            else:
                sql_q = """
                    SELECT
                        COALESCE(income_type, 'Unknown') AS category,
                        count(*) AS count_val,
                        round((count(*) FILTER (WHERE target = 1)::numeric / NULLIF(count(target), 0) * 100), 2) AS bad_rate,
                        sum(amt_credit) AS total_credit
                    FROM mart.application_overview_v1
                    GROUP BY income_type
                    ORDER BY count_val DESC
                    LIMIT 6;
                """
            rows = conn.execute(sql_q).fetchall()
            if not rows:
                return None
            categories = []
            vals = []
            labels = []
            for r in rows:
                cat = str(r[0])
                cnt = int(r[1])
                rate = float(r[2]) if r[2] is not None else 0.0
                credit_m = float(r[3]) / 1e6 if r[3] is not None else 0.0

                categories.append(cat)
                if "Tỷ lệ" in measure_choice:
                    vals.append(rate)
                    labels.append(f"{rate:.1f}%")
                elif "Tổng giá trị" in measure_choice:
                    vals.append(credit_m)
                    labels.append(f"{credit_m:,.0f}M")
                else:
                    vals.append(cnt)
                    labels.append(f"{cnt:,} đơn")
            return {
                "categories": categories,
                "vals": vals,
                "labels": labels
            }
    except Exception:
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


@st.cache_data(ttl=600, show_spinner=False)
def fetch_olap_cross_tab():
    """Truy vấn ma trận chéo Cross-tab từ mart.application_overview_v1 kèm Bad Rate %."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn:
            rows = conn.execute("""
                SELECT
                    age_band,
                    count(*) FILTER (WHERE contract_type_name = 'Cash loans') AS cash_cnt,
                    coalesce(sum(amt_credit) FILTER (WHERE contract_type_name = 'Cash loans'), 0) AS cash_credit,
                    count(*) FILTER (WHERE contract_type_name = 'Revolving loans') AS rev_cnt,
                    coalesce(sum(amt_credit) FILTER (WHERE contract_type_name = 'Revolving loans'), 0) AS rev_credit,
                    count(*) AS total_cnt,
                    coalesce(sum(amt_credit), 0) AS total_credit,
                    count(target) AS labeled_cnt,
                    count(*) FILTER (WHERE target = 1) AS bad_cnt
                FROM mart.application_overview_v1
                GROUP BY age_band
                ORDER BY CASE age_band WHEN '<25' THEN 1 WHEN '25-39' THEN 2 WHEN '40-59' THEN 3 WHEN '60+' THEN 4 ELSE 5 END;
            """).fetchall()
            if not rows:
                return None

            data = {
                "Nhóm độ tuổi (age_band)": [],
                "Cash loans (M | Đơn)": [],
                "Revolving loans (M | Đơn)": [],
                "Tổng tín dụng (M | Đơn)": [],
                "Tỷ lệ rủi ro (TARGET=1)": [],
            }
            total_cash_cnt = 0
            total_cash_credit = 0.0
            total_rev_cnt = 0
            total_rev_credit = 0.0
            overall_cnt = 0
            overall_credit = 0.0
            overall_labeled = 0
            overall_bad = 0

            for r in rows:
                band, c_cnt, c_crd, r_cnt, r_crd, t_cnt, t_crd, l_cnt, b_cnt = r
                c_crd_m = float(c_crd) / 1e6
                r_crd_m = float(r_crd) / 1e6
                t_crd_m = float(t_crd) / 1e6

                total_cash_cnt += c_cnt
                total_cash_credit += c_crd_m
                total_rev_cnt += r_cnt
                total_rev_credit += r_crd_m
                overall_cnt += t_cnt
                overall_credit += t_crd_m
                overall_labeled += l_cnt
                overall_bad += b_cnt

                bad_rate = (b_cnt / l_cnt * 100.0) if l_cnt > 0 else 0.0

                data["Nhóm độ tuổi (age_band)"].append(f"Nhóm {band} tuổi")
                data["Cash loans (M | Đơn)"].append(f"{c_crd_m:,.1f}M ({c_cnt:,} đơn)")
                data["Revolving loans (M | Đơn)"].append(f"{r_crd_m:,.1f}M ({r_cnt:,} đơn)")
                data["Tổng tín dụng (M | Đơn)"].append(f"{t_crd_m:,.1f}M ({t_cnt:,} đơn)")
                data["Tỷ lệ rủi ro (TARGET=1)"].append(f"{bad_rate:.2f}% ({b_cnt:,}/{l_cnt:,})")

            overall_bad_rate = (overall_bad / overall_labeled * 100.0) if overall_labeled > 0 else 0.0
            data["Nhóm độ tuổi (age_band)"].append("Tổng cộng danh mục")
            data["Cash loans (M | Đơn)"].append(f"{total_cash_credit:,.1f}M ({total_cash_cnt:,} đơn)")
            data["Revolving loans (M | Đơn)"].append(f"{total_rev_credit:,.1f}M ({total_rev_cnt:,} đơn)")
            data["Tổng tín dụng (M | Đơn)"].append(f"{overall_credit:,.1f}M ({overall_cnt:,} đơn)")
            data["Tỷ lệ rủi ro (TARGET=1)"].append(f"{overall_bad_rate:.2f}% ({overall_bad:,}/{overall_labeled:,})")

            return pd.DataFrame(data)
    except Exception:
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


@st.cache_data(ttl=60, show_spinner=False)
def fetch_etl_runs():
    """Lấy danh sách các đợt nạp ETL từ ops.etl_runs."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn:
            rows = conn.execute("""
                SELECT etl_run_id, started_at, finished_at, status, row_counts, source_manifest
                FROM ops.etl_runs
                ORDER BY etl_run_id DESC;
            """).fetchall()
            return rows
    except Exception:
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _ensure_app_decisions_table(conn) -> None:
    """Đảm bảo schema app và bảng app.credit_decisions tồn tại (hỗ trợ cả Local DB mới)."""
    conn.execute("CREATE SCHEMA IF NOT EXISTS app;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS app.credit_decisions (
            decision_id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            application_id BIGINT,
            applicant_name TEXT,
            decision TEXT,
            reason_code TEXT,
            notes TEXT,
            officer_id TEXT,
            decided_at TIMESTAMPTZ DEFAULT now()
        );
        """
    )


def save_audit_decision_to_db(record: dict, app_record: dict | None = None) -> bool:
    """Lưu quyết định của cán bộ vào app.credit_decisions và (nếu hợp lệ) lưu vết chấm điểm vào ml.assessments."""
    global LAST_DB_ERROR
    conn = get_db_connection()
    if not conn:
        return False
    try:
        from psycopg.types.json import Jsonb
        from credit_ml import inference as ml_inference

        with conn:
            with conn.transaction():
                if conn.execute("SELECT to_regclass('app.credit_decisions')").fetchone()[0] is None:
                    _ensure_app_decisions_table(conn)
                raw_id = str(record.get("Mã Hồ Sơ", "0")).replace("#", "").strip()
                app_id = int(raw_id) if raw_id.isdigit() else 0
                conn.execute(
                    """
                    INSERT INTO app.credit_decisions (
                        application_id, applicant_name, decision, reason_code, notes, officer_id, decided_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        app_id,
                        record.get("Khách Hàng", "Unknown"),
                        record.get("Quyết Định", "Chưa rõ"),
                        record.get("Mã Lý Do", ""),
                        record.get("Ghi Chú Nghiệp Vụ", ""),
                        record.get("Cán Bộ Thẩm Định", "Officer"),
                        record.get("Thời Gian Ghi Nhận", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    ),
                )

                # Lưu vết chấm điểm ML vào ml.assessments khi hồ sơ thuộc DW và đã có model_run_id đã đăng ký
                if (
                    app_record is not None
                    and app_record.get("is_real_dwh")
                    and app_record.get("assessment_result") is not None
                ):
                    mr_row = conn.execute(
                        "SELECT model_run_id FROM ml.model_runs ORDER BY model_run_id DESC LIMIT 1"
                    ).fetchone()
                    if mr_row is not None:
                        db_res = dict(app_record["assessment_result"])
                        db_res["model_run_id"] = int(mr_row[0])
                        row_ml = ml_inference.to_db_row(db_res)
                        conn.execute(
                            """
                            INSERT INTO ml.assessments (
                                application_id, model_run_id, status, feature_snapshot,
                                risk_score, risk_band, recommendation, policy_version, reason_codes
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
                            """,
                            (
                                row_ml["application_id"],
                                row_ml["model_run_id"],
                                row_ml["status"],
                                Jsonb(row_ml["feature_snapshot"]),
                                row_ml["risk_score"],
                                row_ml["risk_band"],
                                row_ml["recommendation"],
                                row_ml["policy_version"],
                                Jsonb(row_ml["reason_codes"]),
                            ),
                        )
            LAST_DB_ERROR = None
            return True
    except Exception as exc:
        LAST_DB_ERROR = f"{type(exc).__name__}: {exc}"
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


def fetch_audit_history_from_db():
    """Đọc lịch sử quyết định từ app.credit_decisions trên Kho dữ liệu (DWH)."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn:
            rows = conn.execute("""
                SELECT decision_id, application_id, applicant_name, decision, reason_code, notes, officer_id, decided_at
                FROM app.credit_decisions
                ORDER BY decision_id DESC;
            """).fetchall()
            logs = []
            for r in rows:
                logs.append({
                    "Mã GD": f"DEC-{r[0]:03d}",
                    "Mã Hồ Sơ": f"#{r[1]}",
                    "Khách Hàng": r[2],
                    "Quyết Định": r[3],
                    "Mã Lý Do": r[4],
                    "Ghi Chú Nghiệp Vụ": r[5] or "",
                    "Cán Bộ Thẩm Định": r[6] or "Officer",
                    "Thời Gian Ghi Nhận": str(r[7])[:19] if r[7] else "",
                })
            return logs
    except Exception:
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _row_to_app_dict(d: dict) -> dict:
    """Chuyển đổi một dòng dữ liệu từ mart.application_overview_v1 thành đối tượng hồ sơ chuẩn DSS."""
    aid = str(d["application_id"])
    raw_credit = float(d["amt_credit"]) if d.get("amt_credit") is not None else None
    raw_income = float(d["amt_income_total"]) if d.get("amt_income_total") is not None else None
    raw_annuity = float(d["amt_annuity"]) if d.get("amt_annuity") is not None else None
    raw_goods = float(d["amt_goods_price"]) if d.get("amt_goods_price") is not None else raw_credit

    unit_scale = 1000.0
    credit_val = (raw_credit / unit_scale) if raw_credit is not None else None
    income_val = (raw_income / unit_scale) if raw_income is not None else None
    annuity_val = (raw_annuity / unit_scale) if raw_annuity is not None else None
    goods_val = (raw_goods / unit_scale) if raw_goods is not None else None

    ratio_val = (raw_credit / raw_income) if (raw_credit is not None and raw_income is not None and raw_income > 0) else None

    features = {
        "amt_income_total": raw_income,
        "amt_credit": raw_credit,
        "amt_annuity": raw_annuity,
        "credit_income_ratio": ratio_val,
        "age_years": float(d["age_years"]) if d.get("age_years") is not None else None,
        "employment_days": int(d["employment_days"]) if d.get("employment_days") is not None else None,
        "income_type": str(d["income_type"]) if d.get("income_type") else "Unknown",
        "education_level": str(d["education_level"]) if d.get("education_level") else "Unknown",
        "contract_type_name": str(d["contract_type_name"]) if d.get("contract_type_name") else "Unknown",
        "ext_source_1": float(d["ext_source_1"]) if d.get("ext_source_1") is not None else None,
        "ext_source_2": float(d["ext_source_2"]) if d.get("ext_source_2") is not None else None,
        "ext_source_3": float(d["ext_source_3"]) if d.get("ext_source_3") is not None else None,
        "previous_application_count": int(d["previous_application_count"]) if d.get("previous_application_count") is not None else 0,
        "previous_approved_count": int(d["previous_approved_count"]) if d.get("previous_approved_count") is not None else 0,
        "previous_refused_count": int(d["previous_refused_count"]) if d.get("previous_refused_count") is not None else 0,
        "previous_approval_rate": float(d["previous_approval_rate"]) if d.get("previous_approval_rate") is not None else None,
    }

    emp_str = f"{(d['employment_days'] / 365.25):.1f} năm" if d.get("employment_days") is not None else "N/A (Không làm việc / NULL)"
    age_band_str = str(d.get("age_band") or "Unknown")
    age_str = f"{int(d['age_years'])} tuổi ({age_band_str})" if d.get("age_years") is not None else "Unknown"
    assets_str = ("Có Ô tô" if d.get("flag_own_car") else "Chưa có Ô tô") + " • " + ("Có BĐS" if d.get("flag_own_realty") else "Chưa có BĐS")

    occ_raw = d.get("occupation_type")
    inc_raw = d.get("income_type") or "Unknown"
    short_label = str(occ_raw) if occ_raw else str(inc_raw)
    cnt_child = int(d["cnt_children"]) if d.get("cnt_children") is not None else 0
    cnt_fam = int(float(d["cnt_family_members"])) if d.get("cnt_family_members") is not None else 1

    app_obj = {
        "id": aid,
        "applicant": short_label,
        "product": str(d.get("contract_type_name") or "Unknown"),
        "short_product": str(d.get("contract_type_name") or "Unknown"),
        "income": income_val,
        "credit": credit_val,
        "annuity": annuity_val,
        "goods": goods_val,
        "unit_scale": unit_scale,
        "unit_suffix": "K",
        "target": d.get("target"),
        "pd": None,
        "risk_level": "ERROR",
        "recommendation_code": "ML_ERROR",
        "sla": "45 phút",
        "status": "Chờ duyệt",
        "default_decision": "👁 Xem xét thêm",
        "ml_error": None,
        "reason_codes": [],
        "alerts": [],
        "age_band": age_band_str,
        "age": age_str,
        "emp_years": emp_str,
        "edu": str(d.get("education_level") or "Unknown"),
        "inc_type": str(inc_raw),
        "occupation": str(occ_raw) if occ_raw else "Chưa khai báo (Unknown)",
        "family_info": f"{cnt_child} con • {cnt_fam} thành viên",
        "marital": str(d.get("family_status") or "Unknown"),
        "assets": assets_str,
        "hist_total": f"{d.get('previous_application_count', 0)} đơn hợp lệ",
        "hist_app": f"{d.get('previous_approved_count', 0)} lần",
        "hist_ref": f"{d.get('previous_refused_count', 0)} lần",
        "hist_rate": f"{(float(d['previous_approval_rate'])*100):.1f}%" if d.get("previous_approval_rate") is not None else "N/A (Chưa có LS)",
        "ext1": f"{float(d['ext_source_1']):.3f}" if d.get("ext_source_1") is not None else "N/A",
        "ext2": f"{float(d['ext_source_2']):.3f}" if d.get("ext_source_2") is not None else "N/A",
        "ext3": f"{float(d['ext_source_3']):.3f}" if d.get("ext_source_3") is not None else "N/A",
        "dpd": "Không phát sinh trễ hạn",
        "features": features,
        "drivers": [],
        "is_real_dwh": True
    }
    return enrich_with_real_ml(app_obj)


@st.cache_data(ttl=600, show_spinner=False)
def fetch_live_applications_sample(limit: int = 15):
    """Kéo một tập hồ sơ thật ban đầu từ mart.application_overview_v1."""
    conn = get_db_connection()
    if not conn:
        return {}
    try:
        with conn:
            cur = conn.execute("SELECT * FROM mart.application_overview_v1 ORDER BY application_id LIMIT %s", (limit,))
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
            real_apps = {}
            for r in rows:
                d = dict(zip(cols, r))
                app_obj = _row_to_app_dict(d)
                real_apps[app_obj["id"]] = app_obj
            return real_apps
    except Exception:
        return {}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def fetch_application_by_id(app_id: int):
    """Tìm kiếm trực tiếp hồ sơ theo ID từ mart.application_overview_v1 (trong toàn bộ 307,511 hồ sơ)."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn:
            cur = conn.execute("SELECT * FROM mart.application_overview_v1 WHERE application_id = %s", (app_id,))
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            d = dict(zip(cols, row))
            return _row_to_app_dict(d)
    except Exception:
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def fetch_live_applications_batch(limit: int = 20, offset: int = 0):
    """Nạp thêm một lô hồ sơ từ mart.application_overview_v1 theo phân trang offset."""
    conn = get_db_connection()
    if not conn:
        return {}
    try:
        with conn:
            cur = conn.execute(
                "SELECT * FROM mart.application_overview_v1 ORDER BY application_id LIMIT %s OFFSET %s",
                (limit, offset)
            )
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
            res = {}
            for r in rows:
                d = dict(zip(cols, r))
                app_obj = _row_to_app_dict(d)
                res[app_obj["id"]] = app_obj
            return res
    except Exception:
        return {}
    finally:
        try:
            conn.close()
        except Exception:
            pass


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
                "unit_scale": 1000.0,
                "unit_suffix": "K",
                "target": 1,
                "pd": None,
                "risk_level": "ERROR",
                "recommendation_code": "ML_ERROR",
                "sla": "45 phút",
                "status": "Chờ duyệt",
                "default_decision": "👁 Xem xét thêm",
                "ml_error": None,
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
                # Đúng 16 predictors theo contracts/features-v1.json & thang đo Home Credit gốc (unit_scale=1000)
                "features": {
                    "amt_income_total": 100_000.0,
                    "amt_credit": 200_000.0,
                    "amt_annuity": 10_000.0,
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
                "drivers": [],
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
                "unit_scale": 1000.0,
                "unit_suffix": "K",
                "target": 0,
                "pd": None,
                "risk_level": "ERROR",
                "recommendation_code": "ML_ERROR",
                "sla": "2 giờ 10 phút",
                "status": "Chờ duyệt",
                "default_decision": "👁 Xem xét thêm",
                "ml_error": None,
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
                    "amt_income_total": 180_000.0,
                    "amt_credit": 300_000.0,
                    "amt_annuity": 15_000.0,
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
                "drivers": [],
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
                "unit_scale": 1000.0,
                "unit_suffix": "K",
                "target": 0,
                "pd": None,
                "risk_level": "ERROR",
                "recommendation_code": "ML_ERROR",
                "sla": "12 phút (Khẩn)",
                "status": "Chờ duyệt",
                "default_decision": "👁 Xem xét thêm",
                "ml_error": None,
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
                    "amt_income_total": 120_000.0,
                    "amt_credit": 500_000.0,
                    "amt_annuity": 28_500.0,
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
                "drivers": [],
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
                "unit_scale": 1000.0,
                "unit_suffix": "K",
                "target": 0,
                "pd": None,
                "risk_level": "ERROR",
                "recommendation_code": "ML_ERROR",
                "sla": "30 phút",
                "status": "Chờ duyệt",
                "default_decision": "👁 Xem xét thêm",
                "ml_error": None,
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
                    "amt_income_total": 90_000.0,
                    "amt_credit": 220_000.0,
                    "amt_annuity": 16_500.0,
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
                "drivers": [],
            },
        }

        live_samples = {}
        try:
            live_samples = fetch_live_applications_sample(limit=16)
        except Exception:
            live_samples = {}

        if live_samples:
            st.session_state.applications = live_samples
            st.session_state.is_live_db = True
        else:
            st.session_state.applications = {
                aid: enrich_with_real_ml(app_data) for aid, app_data in raw_apps.items()
            }
            st.session_state.is_live_db = False

    if "audit_logs" not in st.session_state:
        db_logs = fetch_audit_history_from_db()
        if db_logs is not None:
            st.session_state.audit_logs = db_logs
        elif not st.session_state.get("is_live_db"):
            st.session_state.audit_logs = [
                {
                    "Mã GD": "LOCAL-901",
                    "Mã Hồ Sơ": "#1002",
                    "Khách Hàng": "Trần Thị Bích Ngọc",
                    "Quyết Định": "Phê duyệt",
                    "Mã Lý Do": "PAS_01: Đạt toàn bộ tiêu chí khẩu vị rủi ro chuẩn",
                    "Ghi Chú Nghiệp Vụ": (
                        "Bản ghi mẫu ngoại tuyến (chưa kết nối DB)."
                    ),
                    "Cán Bộ Thẩm Định": "Officer (Offline Demo)",
                    "Thời Gian Ghi Nhận": "2026-11-08 01:40:19",
                }
            ]
        else:
            st.session_state.audit_logs = []

    sync_app_status_from_logs(st.session_state.applications, st.session_state.audit_logs)

    if "draft_note" not in st.session_state:
        st.session_state.draft_note = ""
    if "draft_note_area" not in st.session_state:
        st.session_state.draft_note_area = st.session_state.draft_note

    first_aid = next(iter(st.session_state.applications.keys()), "100002")
    if "last_selected_id" not in st.session_state or st.session_state.last_selected_id not in st.session_state.applications:
        st.session_state.last_selected_id = first_aid

    if "sim_selected_id" not in st.session_state or st.session_state.sim_selected_id not in st.session_state.applications:
        st.session_state.sim_selected_id = first_aid


def sync_app_status_from_logs(applications: dict, audit_logs: list) -> None:
    """Đồng bộ trạng thái 'Đã xử lý' và quyết định gần nhất từ nhật ký kiểm toán sang danh sách Queue."""
    # audit_logs đã sắp giảm dần theo thời gian/decision_id nên chỉ áp dụng bản ghi mới nhất cho mỗi ID
    seen_ids: set[str] = set()
    for log_item in audit_logs or []:
        logged_id = str(log_item.get("Mã Hồ Sơ", "")).replace("#", "").strip()
        if not logged_id or logged_id in seen_ids or logged_id not in applications:
            continue
        seen_ids.add(logged_id)
        applications[logged_id]["status"] = "Đã xử lý"
        dec_text = str(log_item.get("Quyết Định", ""))
        for opt in ("✓ Phê duyệt", "👁 Xem xét thêm", "✕ Từ chối"):
            if dec_text and dec_text in opt:
                applications[logged_id]["default_decision"] = opt
                break
