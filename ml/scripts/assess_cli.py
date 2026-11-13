"""Vi du tham chieu cho nguoi 3: cham 1 ho so tu DW va ghi ml.assessments trong 1 transaction.

  python scripts/assess_cli.py --application-id 100002 --models-root ml_outputs/models

Khong train, khong doc TARGET. Feature doc tu mart.application_features_v1 (cung contract luc train).
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from credit_ml import inference as I

COLS = ("application_id, model_run_id, status, feature_snapshot, risk_score, risk_band, "
        "recommendation, policy_version, reason_codes")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--application-id", type=int, required=True)
    ap.add_argument("--models-root", type=Path, required=True)
    ap.add_argument("--model-run-id", type=int, help="mac dinh: model_run moi nhat")
    args = ap.parse_args()
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    dsn = os.environ.get("DATABASE_URL") or ap.error("Dat DATABASE_URL")

    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        feat = conn.execute("SELECT * FROM mart.application_features_v1 WHERE application_id=%s",
                            (args.application_id,)).fetchone()
        if feat is None:
            print(json.dumps({"http": 404, "status": "not_found", "application_id": args.application_id}))
            sys.exit(2)
        q = "SELECT model_run_id, artifact_path FROM ml.model_runs "
        q += "WHERE model_run_id=%s" if args.model_run_id else "ORDER BY model_run_id DESC LIMIT 1"
        mr = conn.execute(q, (args.model_run_id,) if args.model_run_id else ()).fetchone()
        if mr is None:
            print(json.dumps(I.not_ready_result(args.application_id, "NO_REGISTERED_MODEL")))
            sys.exit(3)
        try:
            bundle = I.load_bundle(args.models_root, Path(mr["artifact_path"]).parent.as_posix(), mr["model_run_id"])
        except I.ModelNotReady as exc:
            print(json.dumps(I.not_ready_result(args.application_id, "MODEL_ARTIFACT_UNAVAILABLE")))
            print(str(exc), file=sys.stderr)
            sys.exit(3)
        try:
            result = I.assess(bundle, args.application_id, feat, model_run_id=mr["model_run_id"])
        except I.InvalidFeatures as exc:
            result = I.failed_result(args.application_id, mr["model_run_id"], exc.codes, feat)
        row = I.to_db_row(result)
        with conn.transaction():
            aid = conn.execute(
                f"INSERT INTO ml.assessments({COLS}) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING assessment_id",
                (row["application_id"], row["model_run_id"], row["status"], Jsonb(row["feature_snapshot"]),
                 row["risk_score"], row["risk_band"], row["recommendation"], row["policy_version"],
                 Jsonb(row["reason_codes"]))).fetchone()["assessment_id"]
    result["assessment_id"] = aid
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
