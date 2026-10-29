import csv
import importlib.util
from decimal import Decimal
from pathlib import Path
import sys
import pytest
from test_database import db, initialize, ROOT

APP_FIELDS = ['SK_ID_CURR','TARGET','NAME_CONTRACT_TYPE','AMT_INCOME_TOTAL','AMT_CREDIT','AMT_ANNUITY','AMT_GOODS_PRICE','DAYS_BIRTH','DAYS_EMPLOYED','NAME_INCOME_TYPE','NAME_EDUCATION_TYPE','OCCUPATION_TYPE','NAME_FAMILY_STATUS','CNT_CHILDREN','CNT_FAM_MEMBERS','FLAG_OWN_CAR','FLAG_OWN_REALTY','EXT_SOURCE_1','EXT_SOURCE_2','EXT_SOURCE_3']
PREV_FIELDS = ['SK_ID_PREV','SK_ID_CURR','NAME_CONTRACT_STATUS','NAME_CONTRACT_TYPE','AMT_APPLICATION','AMT_CREDIT','DAYS_DECISION']

@pytest.fixture
def loader():
    path = ROOT/'scripts'/'database.py'
    assert path.exists(), 'CSV loader is not implemented'
    spec = importlib.util.spec_from_file_location('database_cli', path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod

def sources(tmp_path):
    apps = [
        [1001,1,'Cash loans',100,200,10,190,-10957,-365,'Working','Higher education','Laborers','Single',0,1,'Y','N',.3,.4,.5],
        [1002,0,'Revolving loans',0,300,15,'',-18263,365243,'Pensioner','','','Married',1,2,'N','Y','','',.6],
        [1003,0,'',200,500,20,490,'','','Working','','','',0,'','X','N','','',''],
    ]
    prev = [
        [11,1001,'Approved','Cash loans',90,80,-30],
        [12,1001,'Refused','Cash loans',50,0,-10],
        [13,1001,'Approved','Cash loans',700,700,1], # future: excluded
        [14,9999,'Approved','Cash loans',99,99,-1], # orphan: reported
        [15,1001,'Canceled','Cash loans',50,0,''], # unknown cutoff: excluded
    ]
    paths=[]
    for name,fields,rows in [('application_train.csv',APP_FIELDS,apps),('previous_application.csv',PREV_FIELDS,prev)]:
        path=tmp_path/name
        with path.open('w',newline='',encoding='utf-8') as f:
            w=csv.writer(f);w.writerow(fields);w.writerows(rows)
        paths.append(path)
    return paths

def test_etl_idempotence_grain_and_cutoff(db,loader,tmp_path):
    initialize(db)
    app,prev=sources(tmp_path)
    run1=loader.load_csv(db,app,prev)
    values=db.execute('SELECT application_id,applicant_profile_key,contract_type_key FROM dw.fact_application ORDER BY 1').fetchall()
    assert db.execute('SELECT count(*),sum(amt_credit) FROM dw.fact_application').fetchone()==(3,Decimal(1000))
    assert db.execute('SELECT previous_application_count,previous_approved_count,previous_refused_count FROM dw.fact_application WHERE application_id=1001').fetchone()==(2,1,1)
    assert db.execute('SELECT credit_income_ratio,previous_approval_rate FROM mart.application_features_v1 WHERE application_id=1002').fetchone()==(None,None)
    assert db.execute('SELECT employment_days FROM dw.fact_application WHERE application_id=1002').fetchone()[0] is None
    assert db.execute('SELECT flag_own_car FROM dw.dim_applicant_profile WHERE source_application_id=1003').fetchone()[0] is None
    counts=db.execute('SELECT row_counts FROM ops.etl_runs WHERE etl_run_id=%s',(run1,)).fetchone()[0]
    assert counts['previous']['orphan']==1
    assert counts['previous']['future']==1
    assert counts['previous']['unknown_cutoff']==1
    loader.load_csv(db,app,prev)
    assert db.execute('SELECT application_id,applicant_profile_key,contract_type_key FROM dw.fact_application ORDER BY 1').fetchall()==values
    assert db.execute('SELECT count(*),sum(amt_credit) FROM dw.fact_application').fetchone()==(3,Decimal(1000))
