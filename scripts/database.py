"""Small PostgreSQL CLI; no model training or fabricated metrics.

SQL identifiers are internal constants; source values use COPY/parameters.
Failed ETL rolls back staging+DW and writes a safe run failure outside that txn.
"""
import argparse
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import os
from pathlib import Path
import sys

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
APP_FIELDS = ['SK_ID_CURR','TARGET','NAME_CONTRACT_TYPE','AMT_INCOME_TOTAL','AMT_CREDIT','AMT_ANNUITY','AMT_GOODS_PRICE','DAYS_BIRTH','DAYS_EMPLOYED','NAME_INCOME_TYPE','NAME_EDUCATION_TYPE','OCCUPATION_TYPE','NAME_FAMILY_STATUS','CNT_CHILDREN','CNT_FAM_MEMBERS','FLAG_OWN_CAR','FLAG_OWN_REALTY','EXT_SOURCE_1','EXT_SOURCE_2','EXT_SOURCE_3']
PREV_FIELDS = ['SK_ID_PREV','SK_ID_CURR','NAME_CONTRACT_STATUS','NAME_CONTRACT_TYPE','AMT_APPLICATION','AMT_CREDIT','DAYS_DECISION']
INTEGER = {'SK_ID_CURR','SK_ID_PREV','TARGET','DAYS_BIRTH','DAYS_EMPLOYED','DAYS_DECISION','CNT_CHILDREN'}
NUMBER = {'AMT_INCOME_TOTAL','AMT_CREDIT','AMT_ANNUITY','AMT_GOODS_PRICE','CNT_FAM_MEMBERS','AMT_APPLICATION'}
FLOAT = {'EXT_SOURCE_1','EXT_SOURCE_2','EXT_SOURCE_3'}
LOCK_KEY = 4031261


def init_db(conn):
    """Non-destructive bootstrap. Future changes require new explicit migrations."""
    with conn.transaction():
        for name in ('001_schema.sql','002_views.sql'):
            conn.execute((ROOT/'sql'/name).read_text(encoding='utf-8'))
        app_sql = ROOT / 'sql' / '005_app_decisions.sql'
        if app_sql.exists():
            conn.execute(app_sql.read_text(encoding='utf-8'))


def parse_value(name, value):
    if value is None or not value.strip():
        return None
    value = value.strip()
    if name in INTEGER | NUMBER | FLOAT:
        try:
            number = Decimal(value)
            if not number.is_finite():
                raise ValueError('Non-finite numeric input')
            if name in INTEGER:
                if number != number.to_integral_value():
                    raise ValueError('Non-integer input')
                return int(number)
            return float(number) if name in FLOAT else number
        except InvalidOperation as exc:
            raise ValueError('Invalid numeric input') from exc
    return value


def file_ref(path, role):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    # Do not persist full local paths or credentials in metadata.
    return {'role':role,'file':path.name,'sha256':digest.hexdigest()}


def copy_csv(conn, path, table, fields, run_id, source=None):
    count = 0
    with Path(path).open(newline='',encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        header = reader.fieldnames or []
        required = set(fields) - ({'TARGET'} if source=='application_test' else set())
        if len(header)!=len(set(header)) or not required.issubset(header):
            raise ValueError(f'Invalid header for {table}; missing: {sorted(required-set(header))}')
        columns = fields + (['data_source'] if source else []) + ['etl_run_id','source_file']
        statement = sql.SQL('COPY staging.{} ({}) FROM STDIN').format(sql.Identifier(table),sql.SQL(',').join(map(sql.Identifier,columns)))
        with conn.cursor().copy(statement) as copy:
            for line,row in enumerate(reader,2):
                if None in row:
                    raise ValueError(f'Unexpected CSV values at {table} line {line}')
                try:
                    values = [parse_value(name,row.get(name)) for name in fields]
                    if source=='application_train' and values[fields.index('TARGET')] is None:
                        raise ValueError('Missing train label')
                    if source=='application_test' and values[fields.index('TARGET')] is not None:
                        raise ValueError('Test source contains label')
                except ValueError as exc:
                    raise ValueError(f'Invalid field at {table} line {line}: {exc}') from exc
                copy.write_row(values + ([source] if source else []) + [run_id,Path(path).name])
                count += 1
    return count


def quality(conn):
    counts = conn.execute('''SELECT
        (SELECT count(*) FROM dw.fact_application),
        (SELECT count(*) FROM mart.application_features_v1),
        (SELECT count(DISTINCT application_id) FROM mart.application_features_v1),
        (SELECT count(*) FROM staging.application)''').fetchone()
    if len(set(counts))!=1:
        raise ValueError('Application / feature grain reconciliation failed')
    failures = conn.execute('''SELECT count(*) FROM dw.fact_application f
        JOIN staging.application a ON a."SK_ID_CURR"=f.application_id
        WHERE f.target IS DISTINCT FROM a."TARGET" OR
        f.amt_credit IS DISTINCT FROM CASE WHEN a."AMT_CREDIT">=0 THEN a."AMT_CREDIT" END''').fetchone()[0]
    if failures:
        raise ValueError('Target or credit reconciliation failed')
    summary = conn.execute('''SELECT count(*),count(target),count(*) FILTER(WHERE target=1),sum(amt_credit)
        FROM dw.fact_application''').fetchone()
    return dict(zip(('applications','labeled','target_1','total_credit'),summary))


def load_csv(conn, application, previous, test=None):
    """Full fixed-source reload. Same manifest can repeat; changed source refused."""
    if not conn.autocommit:
        raise ValueError('ETL requires an autocommit connection for durable failure logs')
    if not conn.execute('SELECT pg_try_advisory_lock(%s)',(LOCK_KEY,)).fetchone()[0]:
        raise RuntimeError('Another ETL holds the lock')
    run_id = None
    counts = {}
    try:
        manifest = {'files':[file_ref(application,'application_train'),file_ref(previous,'previous_application')]}
        if test:
            manifest['files'].append(file_ref(test,'application_test'))
        run_id = conn.execute('INSERT INTO ops.etl_runs(source_manifest) VALUES (%s) RETURNING etl_run_id',(Jsonb(manifest),)).fetchone()[0]
        last = conn.execute("SELECT source_manifest FROM ops.etl_runs WHERE status='succeeded' ORDER BY etl_run_id DESC LIMIT 1").fetchone()
        if last and last[0] != manifest:
            raise ValueError('Fixed dataset differs from last success; use a NEW database for another dataset')
        with conn.transaction():
            conn.execute('DELETE FROM staging.previous_application')
            conn.execute('DELETE FROM staging.application')
            counts['application_train'] = {'input':copy_csv(conn,application,'application',APP_FIELDS,run_id,'application_train')}
            if test:
                counts['application_test'] = {'input':copy_csv(conn,test,'application',APP_FIELDS,run_id,'application_test')}
            counts['previous'] = {'input':copy_csv(conn,previous,'previous_application',PREV_FIELDS,run_id)}
            counts['previous'].update(dict(zip(('orphan','future','unknown_cutoff'),conn.execute('''SELECT
                count(*) FILTER(WHERE a."SK_ID_CURR" IS NULL),
                count(*) FILTER(WHERE p."DAYS_DECISION">0),
                count(*) FILTER(WHERE p."DAYS_DECISION" IS NULL)
                FROM staging.previous_application p LEFT JOIN staging.application a USING("SK_ID_CURR")''').fetchone())))
            conn.execute((ROOT/'sql'/'003_load_dw.sql').read_text(encoding='utf-8'))
            summary = quality(conn)
            counts['dw'] = {'output':summary['applications']}
            counts['cleaning'] = conn.execute('''SELECT jsonb_build_object(
                'negative_income',count(*) FILTER(WHERE "AMT_INCOME_TOTAL"<0),
                'negative_credit',count(*) FILTER(WHERE "AMT_CREDIT"<0),
                'invalid_employment',count(*) FILTER(WHERE "DAYS_EMPLOYED">0),
                'invalid_age',count(*) FILTER(WHERE "DAYS_BIRTH">=0),
                'invalid_family_size',count(*) FILTER(WHERE "CNT_FAM_MEMBERS"<0 OR "CNT_FAM_MEMBERS"<>trunc("CNT_FAM_MEMBERS")),
                'unknown_car_flag',count(*) FILTER(WHERE "FLAG_OWN_CAR" IS NOT NULL AND "FLAG_OWN_CAR" NOT IN ('Y','N')),
                'invalid_ext_source',count(*) FILTER(WHERE "EXT_SOURCE_1" NOT BETWEEN 0 AND 1 OR "EXT_SOURCE_2" NOT BETWEEN 0 AND 1 OR "EXT_SOURCE_3" NOT BETWEEN 0 AND 1))
                FROM staging.application''').fetchone()[0]
            conn.execute("UPDATE ops.etl_runs SET status='succeeded',finished_at=clock_timestamp(),row_counts=%s WHERE etl_run_id=%s",(Jsonb(counts),run_id))
        return run_id
    except Exception as exc:
        if run_id is not None:
            # Never save DB exception text: it can contain entire input rows.
            safe = str(exc) if isinstance(exc,ValueError) else f'{type(exc).__name__}: ETL rolled back; inspect local traceback'
            conn.execute("UPDATE ops.etl_runs SET status='failed',finished_at=clock_timestamp(),error_message=%s,row_counts=%s WHERE etl_run_id=%s",(safe,Jsonb({'processed_before_rollback':counts,'committed_output':0}),run_id))
        raise
    finally:
        conn.execute('SELECT pg_advisory_unlock(%s)',(LOCK_KEY,))


def main():
    load_dotenv(ROOT/'.env')
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('init-db')
    sub.add_parser('check')
    load=sub.add_parser('load')
    load.add_argument('--application',type=Path,required=True)
    load.add_argument('--previous',type=Path,required=True)
    load.add_argument('--test',type=Path)
    sub.add_parser('demo')
    args=parser.parse_args()
    dsn=os.environ.get('DATABASE_URL')
    if not dsn:
        parser.error('Set DATABASE_URL in .env or environment; see .env.example')
    with psycopg.connect(dsn,autocommit=True) as conn:
        conn.execute('SET statement_timeout = 0')
        if args.command=='init-db':
            init_db(conn)
            print('Core schema and views initialized (no data deleted).')
        elif args.command=='check':
            print(json.dumps(quality(conn),default=str))
        elif args.command=='demo':
            run=load_csv(conn,ROOT/'data/fixtures/application_train.csv',ROOT/'data/fixtures/previous_application.csv')
            print(json.dumps({'synthetic':True,'etl_run_id':run,'summary':quality(conn)},default=str))
        else:
            run=load_csv(conn,args.application,args.previous,args.test)
            print(json.dumps({'etl_run_id':run,'summary':quality(conn)},default=str))


if __name__=='__main__':
    main()
