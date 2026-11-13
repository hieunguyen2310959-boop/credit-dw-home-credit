"""Unit tests for Web DSS safety invariants (fail-closed ML, honest DB save, policy banner, What-If)."""

from __future__ import annotations

import pytest

from pathlib import Path

import app.data_adapter as data_adapter
from app.views.tab_core import (
    _build_autofill_note,
    _fmt_money,
    _format_queue_label,
    _resolve_recommendation_banner,
    persist_decision,
)
from app.views.tab_whatif import run_whatif_simulation


def _sample_row() -> dict:
    return {
        "application_id": 100009,
        "contract_type_name": "Cash loans",
        "amt_income_total": 150000.0,
        "amt_credit": 450000.0,
        "amt_annuity": 25000.0,
        "amt_goods_price": 420000.0,
        "credit_income_ratio": 3.0,
        "age_years": 35.0,
        "employment_days": 1200,
        "income_type": "Working",
        "education_level": "Higher education",
        "family_status": "Married",
        "housing_type": "House / apartment",
        "occupation_type": "Core staff",
        "organization_type": "Business Entity",
        "cnt_children": 0,
        "cnt_fam_members": 2,
        "flag_own_car": True,
        "flag_own_realty": True,
        "ext_source_1": 0.5,
        "ext_source_2": 0.6,
        "ext_source_3": 0.7,
        "previous_application_count": 1,
        "previous_approved_count": 1,
        "previous_refused_count": 0,
        "previous_approval_rate": 1.0,
        "age_band": "25-39",
        "target": 0,
    }


def test_row_to_app_dict_defaults_fail_closed_before_ml(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(data_adapter, "enrich_with_real_ml", lambda rec: rec)
    app_obj = data_adapter._row_to_app_dict(_sample_row())
    assert app_obj["pd"] is None
    assert app_obj["risk_level"] == "ERROR"
    assert app_obj["recommendation_code"] == "ML_ERROR"
    assert app_obj["default_decision"] != "✓ Phê duyệt"


def test_enrich_with_real_ml_fails_closed_when_model_unloaded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(data_adapter, "ML_LOADED", False)
    monkeypatch.setattr(data_adapter, "MODEL_BUNDLE", None)
    monkeypatch.setattr(data_adapter, "ML_LOAD_ERROR", "FileNotFoundError: missing model")

    rec = {"id": "100009", "pd": 0.05, "risk_level": "LOW", "recommendation_code": "APPROVE_SIMULATION", "features": {}}
    out = data_adapter.enrich_with_real_ml(rec)

    assert out["pd"] is None
    assert out["risk_level"] == "ERROR"
    assert out["recommendation_code"] == "ML_ERROR"
    assert out["default_decision"] == "👁 Xem xét thêm"
    assert "missing model" in (out["ml_error"] or "")


def test_enrich_with_real_ml_fails_closed_on_inference_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(data_adapter, "ML_LOADED", True)
    monkeypatch.setattr(data_adapter, "MODEL_BUNDLE", object())

    def boom(*_args, **_kwargs):
        raise RuntimeError("inference corrupted")

    monkeypatch.setattr(data_adapter, "assess", boom)
    rec = {"id": "100009", "pd": 0.05, "risk_level": "LOW", "recommendation_code": "APPROVE_SIMULATION", "features": {}}
    out = data_adapter.enrich_with_real_ml(rec)

    assert out["pd"] is None
    assert out["risk_level"] == "ERROR"
    assert out["recommendation_code"] == "ML_ERROR"
    assert out["default_decision"] == "👁 Xem xét thêm"
    assert "inference corrupted" in (out["ml_error"] or "")


def test_banner_uses_policy_recommendation_even_when_risk_band_low() -> None:
    app_rec = {
        "id": "100009",
        "applicant": "Core staff",
        "product": "Cash loans",
        "credit": 450.0,
        "status": "Chờ duyệt",
        "pd": 0.042,
        "risk_level": "LOW",
        "recommendation_code": "REVIEW",
        "alerts": [
            {
                "code": "ALL_EXTERNAL_SCORES_MISSING",
                "severity": "high",
                "message": "Thiếu cả 3 điểm nguồn ngoài EXT_1/2/3.",
            }
        ],
    }
    banner = _resolve_recommendation_banner(app_rec, 0.10, 0.25)
    assert "REVIEW" in banner["title"]
    assert "APPROVE_SIMULATION" not in banner["title"]
    assert banner["badge_text"] == "MỨC RỦI RO: LOW • REVIEW"
    assert any("ALL_EXTERNAL_SCORES_MISSING" in msg for msg in banner["alerts_text"])

    q_label = _format_queue_label("100009", app_rec)
    assert "REVIEW" in q_label


def test_banner_and_formatters_handle_ml_error_safely() -> None:
    err_app = {
        "id": "100009",
        "applicant": "Core staff",
        "product": "Cash loans",
        "credit": 450.0,
        "status": "Chờ duyệt",
        "pd": None,
        "risk_level": "ERROR",
        "recommendation_code": "ML_ERROR",
        "ml_error": "RuntimeError: missing bundle",
        "alerts": [],
    }
    banner = _resolve_recommendation_banner(err_app, 0.10, 0.25)
    assert banner["badge_text"] == "LỖI CHẤM ĐIỂM ML (ML_ERROR)"
    assert "FAIL-CLOSED" in banner["title"]

    q_label = _format_queue_label("100009", err_app)
    assert "ML_ERROR" in q_label

    note = _build_autofill_note(err_app, "👁 Xem xét thêm", 0.10, 0.25)
    assert "ML_ERROR" in note or "lỗi chấm điểm ML" in note


def test_persist_decision_does_not_fake_success_when_live_db_write_fails() -> None:
    apps = {
        "100009": {
            "id": "100009",
            "applicant": "Core staff",
            "status": "Chờ duyệt",
            "default_decision": "✓ Phê duyệt",
            "pd": 0.04,
            "ml_error": None,
        }
    }
    logs: list[dict] = []

    ok, level, msg = persist_decision(
        applications=apps,
        audit_logs=logs,
        selected_id="100009",
        chosen_decision="✓ Phê duyệt",
        chosen_reason="PAS_01",
        note_val="Test note",
        is_live_db=True,
        save_fn=lambda _rec: False,
        fetch_fn=lambda: None,
        now_str="2026-11-12 20:35:00",
    )

    assert ok is False
    assert level == "error"
    assert "thất bại" in msg.lower()
    assert apps["100009"]["status"] == "Chờ duyệt"
    assert logs == []


def test_persist_decision_blocks_approve_when_ml_error() -> None:
    apps = {
        "100009": {
            "id": "100009",
            "applicant": "Core staff",
            "status": "Chờ duyệt",
            "default_decision": "👁 Xem xét thêm",
            "pd": None,
            "ml_error": "Model unavailable",
        }
    }
    logs: list[dict] = []
    called = False

    def spy_save(_rec: dict) -> bool:
        nonlocal called
        called = True
        return True

    ok, level, _msg = persist_decision(
        applications=apps,
        audit_logs=logs,
        selected_id="100009",
        chosen_decision="✓ Phê duyệt",
        chosen_reason="PAS_01",
        note_val="",
        is_live_db=True,
        save_fn=spy_save,
        fetch_fn=lambda: [],
    )

    assert ok is False
    assert level == "error"
    assert called is False
    assert apps["100009"]["status"] == "Chờ duyệt"


def test_persist_decision_succeeds_honestly_on_db_write_or_offline_mode() -> None:
    apps = {
        "100009": {
            "id": "100009",
            "applicant": "Core staff",
            "status": "Chờ duyệt",
            "default_decision": "✓ Phê duyệt",
            "pd": 0.04,
            "ml_error": None,
        }
    }
    logs: list[dict] = []
    db_snapshot = [{"Mã GD": "DEC-500", "Mã Hồ Sơ": "#100009"}]

    ok, level, msg = persist_decision(
        applications=apps,
        audit_logs=logs,
        selected_id="100009",
        chosen_decision="✓ Phê duyệt",
        chosen_reason="PAS_01",
        note_val="OK",
        is_live_db=True,
        save_fn=lambda _rec: True,
        fetch_fn=lambda: list(db_snapshot),
    )
    assert ok is True
    assert level == "success"
    assert "app.credit_decisions" in msg
    assert apps["100009"]["status"] == "Đã xử lý"
    assert logs == db_snapshot

    offline_apps = {
        "1001": {
            "id": "1001",
            "applicant": "Nguyễn Văn An",
            "status": "Chờ duyệt",
            "default_decision": "✓ Phê duyệt",
            "pd": 0.04,
            "ml_error": None,
        }
    }
    offline_logs: list[dict] = []
    ok_off, lvl_off, msg_off = persist_decision(
        applications=offline_apps,
        audit_logs=offline_logs,
        selected_id="1001",
        chosen_decision="✓ Phê duyệt",
        chosen_reason="PAS_01",
        note_val="Offline test",
        is_live_db=False,
        save_fn=lambda _rec: False,
        fetch_fn=lambda: None,
    )
    assert ok_off is True
    assert lvl_off == "warning"
    assert "Offline" in msg_off
    assert "app.credit_decisions" not in msg_off
    assert len(offline_logs) == 1
    assert offline_logs[0]["Mã GD"].startswith("LOCAL-")


def test_whatif_never_falls_back_to_heuristic_formula() -> None:
    sim_app = {
        "pd": 0.08,
        "ml_error": None,
        "features": {"amt_credit": 200000.0, "amt_income_total": 100000.0, "amt_annuity": 10000.0},
    }

    res_unloaded = run_whatif_simulation(
        sim_app=sim_app,
        sim_id="100009",
        cur_credit=200.0,
        new_credit=300.0,
        new_income=100.0,
        new_lev=3.0,
        unit_scale=1000.0,
        rev_thresh=0.10,
        dec_thresh=0.25,
        ml_loaded=False,
        model_bundle=None,
    )
    assert res_unloaded["status"] == "ml_error"
    assert res_unloaded["new_pd"] is None
    assert res_unloaded["new_rec"] == "ML_ERROR"

    class _DummyPolicy:
        version = "v1"
        ratio_extreme_threshold = 10.0

    class _DummyBundle:
        policy = _DummyPolicy()

    class _DummyPolicyConfig:
        def __init__(self, **_kwargs):
            pass

    def failing_assess(*_args, **_kwargs):
        raise ValueError("feature missing")

    res_exc = run_whatif_simulation(
        sim_app=sim_app,
        sim_id="100009",
        cur_credit=200.0,
        new_credit=300.0,
        new_income=100.0,
        new_lev=3.0,
        unit_scale=1000.0,
        rev_thresh=0.10,
        dec_thresh=0.25,
        ml_loaded=True,
        model_bundle=_DummyBundle(),
        assess_fn=failing_assess,
        policy_cfg_cls=_DummyPolicyConfig,
    )
    assert res_exc["status"] == "ml_error"
    assert res_exc["new_pd"] is None
    assert res_exc["new_rec"] == "ML_ERROR"


def test_missing_money_preserved_as_none_not_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(data_adapter, "enrich_with_real_ml", lambda rec: rec)
    row = _sample_row()
    row["amt_annuity"] = None
    app_obj = data_adapter._row_to_app_dict(row)
    assert app_obj["annuity"] is None
    assert _fmt_money(app_obj["annuity"], "K") == "N/A"
    assert _fmt_money(app_obj["credit"], "K") == "450.0K"


def test_sync_app_status_from_logs_applies_latest_decision() -> None:
    apps = {
        "100009": {"id": "100009", "status": "Chờ duyệt", "default_decision": "✓ Phê duyệt"},
    }
    logs = [
        {"Mã Hồ Sơ": "#100009", "Quyết Định": "Từ chối"},
        {"Mã Hồ Sơ": "#100009", "Quyết Định": "Phê duyệt"},
    ]
    data_adapter.sync_app_status_from_logs(apps, logs)
    assert apps["100009"]["status"] == "Đã xử lý"
    assert apps["100009"]["default_decision"] == "✕ Từ chối"


def test_app_views_have_no_fake_etl_or_heuristic_or_wrong_edu_key() -> None:
    root = Path(__file__).resolve().parents[1] / "app"
    audit_src = (root / "views" / "tab_audit.py").read_text(encoding="utf-8")
    olap_src = (root / "views" / "tab_olap.py").read_text(encoding="utf-8")
    whatif_src = (root / "views" / "tab_whatif.py").read_text(encoding="utf-8")

    assert "clean_rate:" not in audit_src
    assert "#ETL-01" not in audit_src
    assert 'get("education")' not in olap_src
    assert 'get("education_level")' in olap_src
    assert "* 0.08" not in whatif_src


def test_db_vendor_label_detects_cloud_platforms() -> None:
    assert "Neon" in data_adapter.get_db_vendor_label("postgresql://neondb_owner:pw@ep-xyz.ap-southeast-1.aws.neon.tech/neondb")
    assert "Cloud" in data_adapter.get_db_vendor_label("postgresql://postgres:pw@aws-cloud-db.company.com:5432/postgres")
    assert "Local" in data_adapter.get_db_vendor_label("postgresql://postgres:pw@127.0.0.1:5432/credit_dw")
    assert "Offline" in data_adapter.get_db_vendor_label("")

