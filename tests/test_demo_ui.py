"""Kiểm tra demo offline, không đọc/ghi database thật."""
from pathlib import Path
import sys

from streamlit.testing.v1 import AppTest
import streamlit as st
import psycopg
import pandas as pd
import os
import pytest
from test_database import db, initialize
from test_etl import loader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_demo_and_error_paths(monkeypatch):
    import app.data_adapter as adapter
    import app.views.tab_core as core
    import app.views.tab_whatif as whatif

    monkeypatch.setattr(adapter, 'get_db_connection', lambda: None)
    st.cache_data.clear()
    at = AppTest.from_file(str(ROOT / 'app/main.py'), default_timeout=60).run()
    assert not at.exception
    assert len(at.tabs) == 4
    aid = at.session_state['last_selected_id']

    # Policy REVIEW phải thắng màu LOW của điểm model.
    record = at.session_state['applications'][aid]
    record['risk_level'] = 'LOW'
    record['recommendation_code'] = 'REVIEW'
    at.run()
    assert any('Khuyến nghị Hệ thống: Thẩm Định Bổ Sung' in x.value for x in at.markdown)

    # Giả lập phiên live nhưng DB không lưu được: không cập nhật trạng thái.
    at.session_state['is_live_db'] = True
    monkeypatch.setattr(core, 'save_audit_decision_to_db', lambda record: False)
    old_status = at.session_state['applications'][aid]['status']
    next(b for b in at.button if 'SAVE' in b.label).click().run()
    assert any('Không lưu được' in x.value for x in at.error)
    assert at.session_state['applications'][aid]['status'] == old_status
    assert not at.toast

    at.session_state['is_live_db'] = False
    next(b for b in at.button if 'SAVE' in b.label).click().run()
    assert any('chỉ lưu quyết định trong phiên' in x.value for x in at.toast)

    monkeypatch.setattr(whatif, 'ML_LOADED', False)
    at.run()
    assert any('Chưa thể chạy what-if' in x.value for x in at.error)
    assert not at.exception

    def fail_assess(*args, **kwargs):
        raise ValueError('Simulated invalid input')

    monkeypatch.setattr(whatif, 'ML_LOADED', True)
    monkeypatch.setattr(whatif, 'assess', fail_assess)
    at.run()
    assert any('Không tính được kịch bản' in x.value for x in at.error)
    assert not any('Điểm rủi ro mới:' in x.value for x in at.markdown)

    monkeypatch.setattr(adapter, 'ML_LOADED', False)
    blocked = AppTest.from_file(str(ROOT / 'app/main.py'), default_timeout=60).run()
    assert any('Chưa tải được mô hình' in x.value for x in blocked.error)
    assert not blocked.exception


@pytest.mark.skipif(not os.environ.get('TEST_DATABASE_URL'), reason='Needs a dedicated local test database')
def test_local_database_demo_end_to_end(db, loader, monkeypatch):
    import app.data_adapter as adapter

    initialize(db)
    loader.load_csv(db, ROOT / 'data/fixtures/application_train.csv',
                    ROOT / 'data/fixtures/previous_application.csv')
    from credit_ml.features import read_application_csv, read_previous_csv, build_feature_table
    from credit_ml.config import NUMERIC_FEATURES
    expected, _, _ = build_feature_table(
        read_application_csv(ROOT / 'data/fixtures/application_train.csv'),
        read_previous_csv(ROOT / 'data/fixtures/previous_application.csv'))
    cur = db.execute('SELECT * FROM mart.application_features_v1 ORDER BY application_id')
    actual = pd.DataFrame(cur.fetchall(),columns=[x.name for x in cur.description])
    for col in NUMERIC_FEATURES:
        actual[col] = pd.to_numeric(actual[col]).astype(float)
    pd.testing.assert_frame_equal(actual[expected.columns], expected.sort_values('application_id').reset_index(drop=True), check_dtype=False)
    before = db.execute('SELECT count(*),sum(amt_credit) FROM dw.fact_application').fetchone()
    monkeypatch.setattr(adapter, 'get_db_connection', lambda: psycopg.connect(
        os.environ['TEST_DATABASE_URL'], autocommit=True))
    st.cache_data.clear()
    at = AppTest.from_file(str(ROOT / 'app/main.py'), default_timeout=60).run()
    assert not at.exception
    assert at.session_state['is_live_db']
    aid = at.session_state['last_selected_id']

    dimension = next(x for x in at.selectbox if 'Dimension' in x.label)
    for label in dimension.options:
        dimension.select(label).run()
        assert not at.exception

    income = next(x for x in at.slider if 'Thu nhập' in x.label)
    income.set_value(income.value + 5).run()
    assert not at.exception
    assert db.execute('SELECT count(*),sum(amt_credit) FROM dw.fact_application').fetchone() == before

    next(b for b in at.button if 'SAVE' in b.label).click().run()
    assert not at.exception
    assert db.execute('SELECT count(*) FROM app.credit_decisions WHERE application_id=%s', (int(aid),)).fetchone()[0] == 1
    # Phiên mới phải đọc lại bản ghi thật, không phụ thuộc session cũ.
    fresh = AppTest.from_file(str(ROOT / 'app/main.py'), default_timeout=60).run()
    assert not fresh.exception
    assert any(x['Mã Hồ Sơ'] == '#' + aid for x in fresh.session_state['audit_logs'])
    assert fresh.session_state['applications'][aid]['status'] == 'Đã duyệt'
    st.cache_data.clear()
