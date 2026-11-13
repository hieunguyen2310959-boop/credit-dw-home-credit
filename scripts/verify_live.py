"""Kiểm tra live chỉ đọc: số tổng hợp và tối đa 100 hồ sơ; không ghi DB.

Lấy DATABASE_URL từ môi trường hoặc .env. Không xuất dữ liệu hồ sơ ra tệp.
"""
import json
import os
from pathlib import Path
import sys

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ml'))
from credit_ml.inference import load_bundle, assess


def main():
    load_dotenv(ROOT / '.env')
    result = {}
    bundle = load_bundle(ROOT / 'ml/results/models', 'logreg_v1_20261106')
    with psycopg.connect(os.environ['DATABASE_URL'], sslmode='require',
                         connect_timeout=20) as conn:
        conn.execute('SET TRANSACTION READ ONLY')
        conn.execute("SET LOCAL statement_timeout = '30s'")
        totals = conn.execute('''SELECT count(*),count(DISTINCT application_id),
            count(target),count(*) FILTER(WHERE target=1),sum(amt_credit)
            FROM mart.application_overview_v1''').fetchone()
        assert totals[0] == totals[1]
        result['warehouse'] = dict(zip(['rows','unique_ids','labeled','target_1','credit_sum'], totals))
        result['orphan_dimensions'] = conn.execute('''SELECT count(*) FROM dw.fact_application f
            LEFT JOIN dw.dim_applicant_profile p USING(applicant_profile_key)
            LEFT JOIN dw.dim_contract_type c USING(contract_type_key)
            WHERE p.applicant_profile_key IS NULL OR c.contract_type_key IS NULL''').fetchone()[0]
        assert result['orphan_dimensions'] == 0
        cur = conn.execute('SELECT * FROM mart.application_features_v1 ORDER BY application_id LIMIT 100')
        columns = [x.name for x in cur.description]
        rows = cur.fetchall()
        assert set(columns) == set(bundle.manifest['predictors']) | {'application_id'}
        for values in rows:
            row = dict(zip(columns,values))
            aid = row.pop('application_id')
            scored = assess(bundle,aid,row)
            assert 0 <= scored['risk_score'] <= 1
        result['live_profiles_scored'] = len(rows)
        result['feature_contract_match'] = True
        for key,table in [('staging_history_rows','staging.previous_application'),
                          ('stored_model_count','ml.model_runs'),
                          ('stored_assessment_count','ml.assessments'),
                          ('audit_count','app.credit_decisions')]:
            result[key] = conn.execute('SELECT count(*) FROM ' + table).fetchone()[0]
    out = ROOT / 'docs/evidence/live_verification.json'
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2,default=str))


if __name__ == '__main__':
    main()
