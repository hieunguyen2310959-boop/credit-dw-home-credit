"""Comprehensive interactive UI test matrix via Streamlit AppTest (valid, invalid, and error flows)."""

from __future__ import annotations

import os
from pathlib import Path

import dotenv
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import app.data_adapter as data_adapter
import app.views.tab_whatif as tab_whatif

APP_ENTRY = str(Path(__file__).resolve().parents[1] / "app" / "main.py")


def _find_btn(at: AppTest, needle: str):
    for b in at.button:
        if needle in str(b.label):
            return b
    raise AssertionError(f"Button containing {needle!r} not found")


def _find_sb(at: AppTest, needle: str):
    for sb in at.selectbox:
        if needle in str(sb.label):
            return sb
    raise AssertionError(f"Selectbox containing {needle!r} not found")


def _find_radio(at: AppTest, needle: str):
    for r in at.radio:
        if needle in str(r.label):
            return r
    raise AssertionError(f"Radio containing {needle!r} not found")


def test_ui_live_valid_and_edge_searches_and_filters() -> None:
    if not os.environ.get("DATABASE_URL") and not os.path.exists(".env"):
        pytest.skip("Requires DATABASE_URL / .env for live Neon Cloud UI test")

    st.cache_data.clear()
    at = AppTest.from_file(APP_ENTRY, default_timeout=30).run()
    assert not at.exception
    assert not at.error
    assert at.session_state["is_live_db"] is True
    assert len(at.session_state["applications"]) >= 16

    # 1. ID with amt_annuity = NULL (#155054)
    at.text_input[0].set_value("155054").run()
    assert not at.exception
    assert at.session_state["queue_radio"] == "155054"
    assert at.session_state["applications"]["155054"]["annuity"] is None

    # 2. ID with LOW risk_band forced to REVIEW by missing EXT scores (#100402)
    at.text_input[0].set_value("100402").run()
    assert not at.exception
    assert at.session_state["queue_radio"] == "100402"
    assert at.session_state["decision_radio"] == "👁 Xem xét thêm"
    _find_btn(at, "Điền mẫu nhanh").click().run()
    assert not at.exception
    assert "0.094" in at.session_state["draft_note"]
    assert "REVIEW" in at.session_state["draft_note"]

    # 3. Nonexistent numeric ID (#999999999)
    at.text_input[0].set_value("999999999").run()
    assert not at.exception
    assert any("999999999" in str(w.value) for w in at.warning)

    # 4. Nonexistent text search & empty filter combo
    at.text_input[0].set_value("khong_co_ho_so_nao_xyz").run()
    assert not at.exception
    assert any("Không có hồ sơ nào khớp bộ lọc" in str(i.value) for i in at.info)
    at.text_input[0].set_value("").run()

    # 5. Load +20 batch
    before_cnt = len(at.session_state["applications"])
    _find_btn(at, "Nạp thêm 20 hồ sơ").click().run()
    assert not at.exception
    assert len(at.session_state["applications"]) == before_cnt + 20

    # 6. Filter combinations (including ERROR which has 0 rows)
    _find_sb(at, "Mức rủi ro").set_value("ERROR").run()
    assert not at.exception
    _find_sb(at, "Trạng thái").set_value("Đã xử lý").run()
    assert not at.exception
    _find_sb(at, "Mức rủi ro").set_value("Tất cả rủi ro").run()
    _find_sb(at, "Trạng thái").set_value("Tất cả trạng thái").run()


def test_ui_whatif_invalid_thresholds_and_push_note() -> None:
    if not os.environ.get("DATABASE_URL") and not os.path.exists(".env"):
        pytest.skip("Requires DATABASE_URL / .env for live Neon Cloud UI test")

    st.cache_data.clear()
    at = AppTest.from_file(APP_ENTRY, default_timeout=30).run()
    at.text_input[0].set_value("100402").run()
    _find_sb(at, "Chọn hồ sơ cần mô phỏng").set_value("100402").run()
    assert not at.exception
    assert any("ALL_EXTERNAL_SCORES_MISSING" in str(i.value) for i in at.info)

    # Invalid Policy thresholds: review >= decline
    rev_slider = next(s for s in at.slider if "review_threshold" in str(s.label))
    dec_slider = next(s for s in at.slider if "decline_threshold" in str(s.label))
    rev_slider.set_value(0.25).run()
    dec_slider.set_value(0.20).run()
    assert not at.exception
    assert any("review_threshold" in str(e.value) for e in at.error)
    assert _find_btn(at, "Đẩy kết quả mô phỏng").disabled is True

    # Valid thresholds -> push simulated scenario note to Tab 1
    dec_slider.set_value(0.35).run()
    assert not at.exception
    push_btn = _find_btn(at, "Đẩy kết quả mô phỏng")
    assert push_btn.disabled is False
    push_btn.click().run()
    assert not at.exception
    assert "[Mô phỏng What-If Hồ sơ #100402]" in at.session_state["draft_note"]


def test_ui_ml_error_fail_closed_blocks_approve_and_whatif(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **kw: None)
    monkeypatch.setattr(data_adapter, "ML_LOADED", False)
    monkeypatch.setattr(data_adapter, "MODEL_BUNDLE", None)
    monkeypatch.setattr(data_adapter, "ML_LOAD_ERROR", "RuntimeError: test_missing_bundle")
    monkeypatch.setattr(tab_whatif, "ML_LOADED", False)
    monkeypatch.setattr(tab_whatif, "MODEL_BUNDLE", None)
    monkeypatch.setattr(tab_whatif, "ML_LOAD_ERROR", "RuntimeError: test_missing_bundle")

    st.cache_data.clear()
    at = AppTest.from_file(APP_ENTRY, default_timeout=30).run()
    assert not at.exception
    assert len(at.error) >= 2  # Core Gauge error + What-If error
    assert any("ML_ERROR" in str(e.value) for e in at.error)
    assert any("Chặn phê duyệt" in str(w.value) or "Fail-Closed" in str(w.value) for w in at.warning)
    assert _find_btn(at, "Đẩy kết quả mô phỏng").disabled is True

    # Quick autofill must not crash when pd=None
    _find_btn(at, "Điền mẫu nhanh").click().run()
    assert not at.exception
    assert "ML_ERROR" in at.session_state["draft_note"] or "lỗi chấm điểm ML" in at.session_state["draft_note"]

    # Force selecting Approve and clicking SAVE -> must FAIL CLOSED with st.error
    _find_radio(at, "Lệnh quyết định tín dụng").set_value("✓ Phê duyệt").run()
    _find_btn(at, "LƯU QUYẾT ĐỊNH").click().run()
    assert not at.exception
    assert any("Fail-Closed" in str(e.value) for e in at.error)
    first_id = at.session_state["queue_radio"]
    assert at.session_state["applications"][first_id]["status"] == "Chờ duyệt"


def test_ui_live_db_save_failure_is_honest_and_keeps_note(monkeypatch: pytest.MonkeyPatch) -> None:
    if not os.environ.get("DATABASE_URL") and not os.path.exists(".env"):
        pytest.skip("Requires DATABASE_URL / .env for live Neon Cloud UI test")

    def fake_fail_save(_record, app_record=None):
        data_adapter.LAST_DB_ERROR = "OperationalError: simulated timeout"
        return False

    import app.views.tab_core as tab_core
    monkeypatch.setattr(tab_core, "save_audit_decision_to_db", fake_fail_save)

    st.cache_data.clear()
    at = AppTest.from_file(APP_ENTRY, default_timeout=30).run()
    sel_id = at.session_state["queue_radio"]
    before_logs = len(at.session_state["audit_logs"])

    at.text_area[0].set_value("Ghi chú quan trọng không được mất").run()
    _find_btn(at, "LƯU QUYẾT ĐỊNH").click().run()
    assert not at.exception
    assert any("thất bại" in str(e.value).lower() and "simulated timeout" in str(e.value) for e in at.error)
    assert at.session_state["applications"][sel_id]["status"] == "Chờ duyệt"
    assert len(at.session_state["audit_logs"]) == before_logs
    assert at.session_state["draft_note_area"] == "Ghi chú quan trọng không được mất"


def test_ui_offline_all_olap_dimensions_measures_and_sync_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **kw: None)

    st.cache_data.clear()
    at = AppTest.from_file(APP_ENTRY, default_timeout=30).run()
    assert not at.exception
    assert at.session_state["is_live_db"] is False

    # Cycle all 4 OLAP dimensions and all 3 measures
    dim_sb = _find_sb(at, "Chọn chiều phân tích")
    meas_radio = _find_radio(at, "Chỉ số đo lường")
    for dim in (
        "Nhóm độ tuổi (Age Band)",
        "Loại hợp đồng (Contract Type)",
        "Nguồn thu nhập (Income Type)",
        "Trình độ học vấn (Education Level)",
    ):
        dim_sb.set_value(dim).run()
        assert not at.exception
    for meas in (
        "Tỷ lệ khó khăn thanh toán TARGET=1 (%)",
        "Tổng giá trị tín dụng đề nghị (Credit)",
        "Số lượng hồ sơ",
    ):
        meas_radio.set_value(meas).run()
        assert not at.exception

    # Click Sync while offline -> honest warning
    _find_btn(at, "Đồng bộ").click().run()
    assert not at.exception
    assert any("Không thể kết nối" in str(w.value) for w in at.warning)

    # Save offline decision -> saved locally with LOCAL-* prefix and warning toast
    sel_id = at.session_state["queue_radio"]
    _find_btn(at, "LƯU QUYẾT ĐỊNH").click().run()
    assert not at.exception
    assert at.session_state["applications"][sel_id]["status"] == "Đã xử lý"
    assert at.session_state["audit_logs"][0]["Mã GD"].startswith("LOCAL-")
