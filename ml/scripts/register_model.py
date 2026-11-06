"""Dang ky model da train vao ml.model_runs (chay tren Windows, noi co PostgreSQL cua DW).

Chi dang ky khi: sha256 artifact khop, load duoc, cham lai smoke-test cho ra dung diem da luu,
va (mac dinh) sha256 hai CSV nguon khop lan ETL thanh cong gan nhat trong ops.etl_runs.
Chay lai khong tao ban ghi trung (cung data_snapshot_ref -> in ra model_run_id cu).

  python scripts/register_model.py --models-root ml_outputs/models --model-dir logreg_v1_YYYYMMDD
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import psycopg
from psycopg.types.json import Jsonb
from credit_ml import artifacts as A
from credit_ml import inference as I


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models-root", type=Path, required=True)
    ap.add_argument("--model-dir", required=True, help="thu muc con (tuong doi) trong models-root")
    ap.add_argument("--skip-etl-check", action="store_true",
                    help="bo qua doi chieu sha256 nguon voi ops.etl_runs (chi dung khi hieu ro ly do)")
    args = ap.parse_args()
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        ap.error("Dat DATABASE_URL (xem .env.example cua repo DW)")

    model_dir = A.resolve_model_dir(args.models_root, args.model_dir)
    bundle = I.load_bundle(args.models_root, args.model_dir)       # kiem tra sha256 + load
    manifest = bundle.manifest
    if bundle.library_warning:
        print("CANH BAO:", bundle.library_warning)

    smoke = manifest["smoke_test"]
    res = I.assess(bundle, smoke["application_id"], smoke["features"])
    if abs(res["risk_score"] - smoke["expected_risk_score"]) > 1e-9:
        sys.exit("Smoke test that bai: diem cham lai khac diem luu trong manifest")
    print(f"Smoke test OK (risk_score={res['risk_score']:.6f})")

    manifest_sha = A.sha256_file(model_dir / A.MANIFEST_NAME)
    rel = Path(args.model_dir).as_posix().strip("/")
    snapshot_ref = f"{rel}/{A.MANIFEST_NAME}#sha256={manifest_sha}"
    artifact_path = f"{rel}/{manifest['artifact']['file']}"

    with psycopg.connect(dsn) as conn:
        if not args.skip_etl_check:
            row = conn.execute("SELECT etl_run_id, source_manifest FROM ops.etl_runs "
                               "WHERE status='succeeded' ORDER BY etl_run_id DESC LIMIT 1").fetchone()
            if not row:
                sys.exit("Chua co lan ETL thanh cong trong ops.etl_runs")
            db_files = {f["role"]: f["sha256"] for f in row[1]["files"]}
            for f in manifest["data"]["files"]:
                if db_files.get(f["role"]) != f["sha256"]:
                    sys.exit(f"Du lieu train khac du lieu trong DW (role={f['role']}): "
                             "model phai duoc train tren cung CSV da nap vao DW")
            print(f"Doi chieu nguon voi etl_run_id={row[0]}: khop sha256")
        existing = conn.execute("SELECT model_run_id FROM ml.model_runs WHERE data_snapshot_ref=%s",
                                (snapshot_ref,)).fetchone()
        if existing:
            print(json.dumps({"model_run_id": existing[0], "already_registered": True}))
            return
        new_id = conn.execute(
            "INSERT INTO ml.model_runs(model_name, feature_version, trained_at, artifact_path, "
            "data_snapshot_ref, split_seed, evaluation_metrics) VALUES (%s,%s,%s,%s,%s,%s,%s) "
            "RETURNING model_run_id",
            (manifest["model_name"], manifest["feature_version"], manifest["trained_at"], artifact_path,
             snapshot_ref, manifest["split"]["seed"], Jsonb(A.json_safe(manifest["evaluation_metrics"])))
        ).fetchone()[0]
    print(json.dumps({"model_run_id": new_id, "artifact_path": artifact_path, "already_registered": False}))


if __name__ == "__main__":
    main()
