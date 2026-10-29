"""Integration tests: a dedicated empty PostgreSQL DB, never a live user DB."""
import os
from pathlib import Path
import psycopg
from psycopg.types.json import Jsonb
import pytest

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def db():
    dsn = os.environ.get('TEST_DATABASE_URL')
    if not dsn:
        pytest.fail('TEST_DATABASE_URL must name a dedicated empty database')
    with psycopg.connect(dsn, autocommit=True) as c:
        schemas = ['ops', 'staging', 'dw', 'ml', 'mart']
        # Only test database explicitly marked in its name is accepted.
        assert 'test' in c.info.dbname, 'Refuse to reset non-test database'
        for name in reversed(schemas):
            c.execute(f'DROP SCHEMA IF EXISTS {name} CASCADE')
        yield c

def initialize(c):
    schema = ROOT / 'sql' / '001_schema.sql'
    assert schema.exists(), 'Core schema migration is not implemented'
    c.execute(schema.read_text(encoding='utf-8'))
    views = ROOT / 'sql' / '002_views.sql'
    assert views.exists(), 'Views migration is not implemented'
    c.execute(views.read_text(encoding='utf-8'))

def test_core_schema_and_views(db):
    initialize(db)
    tables = db.execute("SELECT table_schema||'.'||table_name FROM information_schema.tables WHERE table_type='BASE TABLE' AND table_schema IN ('ops','staging','dw','ml')").fetchall()
    assert {x[0] for x in tables} == {'ops.etl_runs','staging.application','staging.previous_application','dw.dim_applicant_profile','dw.dim_contract_type','dw.fact_application','ml.model_runs','ml.assessments'}
    feature_cols = [x[0] for x in db.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='mart' AND table_name='application_features_v1'")]
    assert 'target' not in feature_cols
    assert 'application_id' in feature_cols
    assert db.execute('SELECT count(*) FROM mart.latest_assessment_v1').fetchone()[0] == 0
    # Applying migrations twice is safe.
    initialize(db)
