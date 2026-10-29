"""Database integration invariants. Model/assessment rows here are TEST ONLY."""
import json
from datetime import datetime, timezone
import pytest
import psycopg
from psycopg.types.json import Jsonb
from test_database import db,initialize
from test_etl import loader,sources

@pytest.fixture
def loaded(db,loader,tmp_path):
    initialize(db)
    app,prev=sources(tmp_path)
    loader.load_csv(db,app,prev)
    model=db.execute("""INSERT INTO ml.model_runs(model_name,feature_version,artifact_path,data_snapshot_ref,evaluation_metrics)
        VALUES ('TEST_ONLY_NO_REAL_MODEL','application_features_v1','tests/nonexistent-test-only.joblib','synthetic-fixture',%s) RETURNING model_run_id""",(Jsonb({'test_only':True}),)).fetchone()[0]
    return db,loader,app,prev,model

def add_assessment(c,model,**changes):
    record={'application_id':1001,'model_run_id':model,'status':'succeeded','feature_snapshot':Jsonb({'amt_credit':200,'missing':None}),
        'risk_score':.2,'risk_band':'medium','recommendation':'review_simulation','policy_version':'TEST_ONLY','reason_codes':Jsonb(['TEST_ONLY'])}
    record.update(changes)
    cols=','.join(record)
    vals=','.join(['%s']*len(record))
    return c.execute(f'INSERT INTO ml.assessments({cols}) VALUES ({vals}) RETURNING assessment_id',tuple(record.values())).fetchone()[0]

def test_model_artifact_cannot_change_after_used(loaded):
    c,_,_,_,model=loaded
    add_assessment(c,model)
    with pytest.raises(psycopg.Error):
        c.execute('UPDATE ml.model_runs SET artifact_path=%s WHERE model_run_id=%s',('replaced.joblib',model))
    assert c.execute('SELECT artifact_path FROM ml.model_runs WHERE model_run_id=%s',(model,)).fetchone()[0]=='tests/nonexistent-test-only.joblib'


@pytest.mark.parametrize('changes',[
    {'risk_score':None}, {'risk_score':-0.1}, {'risk_score':1.1},
    {'risk_score':float('nan')}, {'risk_score':float('inf')},
    {'feature_snapshot':Jsonb({'TARGET':0})},
    {'feature_snapshot':Jsonb({'nested':{'target':1}})},
    {'feature_snapshot':Jsonb({'x':'NaN'})},
    {'feature_snapshot':Jsonb([])},
    {'status':'failed'},
    {'status':'failed','risk_score':None,'risk_band':None,'recommendation':None,'reason_codes':Jsonb([])},
    {'application_id':99999}, {'model_run_id':99999},
])
def test_reject_invalid_assessments(loaded,changes):
    c,_,_,_,model=loaded
    with pytest.raises(psycopg.Error):
        add_assessment(c,model,**changes)
    assert c.execute('SELECT count(*) FROM ml.assessments').fetchone()[0]==0


def test_latest_success_tie_break_and_failure_not_fake_score(loaded):
    c,_,_,_,model=loaded
    when=datetime(2026,1,1,tzinfo=timezone.utc)
    first=add_assessment(c,model,assessed_at=when,risk_score=.1)
    second=add_assessment(c,model,assessed_at=when,risk_score=.2)
    add_assessment(c,model,status='failed',risk_score=None,risk_band=None,recommendation=None,reason_codes=Jsonb(['ERROR']))
    assert c.execute('SELECT assessment_id,risk_score FROM mart.latest_assessment_v1').fetchone()==(second,.2)
    assert second>first
    assert c.execute('SELECT count(*) FROM dw.fact_application').fetchone()[0]==3


def test_rerun_preserves_assessments_and_fixed_dataset_refuses_change(loaded):
    c,load,app,prev,model=loaded
    assessment=add_assessment(c,model)
    load.load_csv(c,app,prev)
    assert c.execute('SELECT assessment_id FROM ml.assessments').fetchone()[0]==assessment
    with app.open('a',encoding='utf-8') as f:
        f.write('\n')
    with pytest.raises(ValueError,match='Fixed dataset'):
        load.load_csv(c,app,prev)
    assert c.execute('SELECT count(*) FROM dw.fact_application').fetchone()[0]==3
    assert c.execute("SELECT status FROM ops.etl_runs ORDER BY etl_run_id DESC LIMIT 1").fetchone()[0]=='failed'


def test_transaction_rollback_retains_previous_dw(loaded,monkeypatch):
    c,load,app,prev,_=loaded
    old=c.execute('SELECT etl_run_id FROM dw.fact_application ORDER BY application_id').fetchall()
    def fail_after_load(conn):
        raise ValueError('Injected reconciliation failure')
    monkeypatch.setattr(load,'quality',fail_after_load)
    with pytest.raises(ValueError,match='Injected'):
        load.load_csv(c,app,prev)
    assert c.execute('SELECT etl_run_id FROM dw.fact_application ORDER BY application_id').fetchall()==old
    assert c.execute("SELECT status FROM ops.etl_runs ORDER BY etl_run_id DESC LIMIT 1").fetchone()[0]=='failed'


def test_profile_cannot_be_attached_to_wrong_application(loaded):
    c,_,_,_,_=loaded
    # Unique + composite FK prevent a source/profile mismatch.
    with pytest.raises(psycopg.Error):
        c.execute('UPDATE dw.dim_applicant_profile SET source_application_id=1009 WHERE source_application_id=1001')


def test_unlabeled_source_never_counted_as_target_zero(db,loader,tmp_path):
    initialize(db)
    app,prev=sources(tmp_path)
    import csv
    with app.open(newline='',encoding='utf-8') as f:
        reader=csv.DictReader(f); fields=reader.fieldnames; row=next(reader)
    row['SK_ID_CURR']='1004';row['TARGET']=''
    test=tmp_path/'application_test.csv'
    with test.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerow(row)
    loader.load_csv(db,app,prev,test)
    assert db.execute('SELECT count(*),count(target),count(*) FILTER(WHERE target=1) FROM dw.fact_application').fetchone()==(4,3,1)
    assert db.execute('SELECT target FROM dw.fact_application WHERE application_id=1004').fetchone()[0] is None


def test_duplicate_source_rolls_back_and_logs_failure(db,loader,tmp_path):
    initialize(db)
    app,prev=sources(tmp_path)
    import csv
    with app.open(newline='',encoding='utf-8') as f:
        rows=list(csv.reader(f))
    with app.open('a',newline='',encoding='utf-8') as f:
        csv.writer(f).writerow(rows[1])
    with pytest.raises(psycopg.errors.UniqueViolation):
        loader.load_csv(db,app,prev)
    assert db.execute('SELECT count(*) FROM staging.application').fetchone()[0]==0
    assert db.execute('SELECT count(*) FROM dw.fact_application').fetchone()[0]==0
    status,error=db.execute('SELECT status,error_message FROM ops.etl_runs').fetchone()
    assert status=='failed'
    assert 'Laborers' not in error  # Raw customer rows must not leak to error log.
