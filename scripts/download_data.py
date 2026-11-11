"""Utility script to download the Home Credit Default Risk dataset into data/raw.

Source: Community-verified dataset mirror on Hugging Face (identical to Kaggle competition files).
"""
import argparse
import csv
import hashlib
from pathlib import Path
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / 'data' / 'raw'

FILES = {
    'application_train.csv': {
        'url': 'https://huggingface.co/datasets/minhSpaceX/home_credit/resolve/main/application_train.csv',
        'required': True,
        'min_size_mb': 150,
    },
    'previous_application.csv': {
        'url': 'https://huggingface.co/datasets/minhSpaceX/home_credit/resolve/main/previous_application.csv',
        'required': True,
        'min_size_mb': 350,
    },
    'application_test.csv': {
        'url': 'https://huggingface.co/datasets/minhSpaceX/home_credit/resolve/main/application_test.csv',
        'required': False,
        'min_size_mb': 20,
    },
}

APP_FIELDS = [
    'SK_ID_CURR', 'TARGET', 'NAME_CONTRACT_TYPE', 'AMT_INCOME_TOTAL',
    'AMT_CREDIT', 'AMT_ANNUITY', 'AMT_GOODS_PRICE', 'DAYS_BIRTH',
    'DAYS_EMPLOYED', 'NAME_INCOME_TYPE', 'NAME_EDUCATION_TYPE',
    'OCCUPATION_TYPE', 'NAME_FAMILY_STATUS', 'CNT_CHILDREN',
    'CNT_FAM_MEMBERS', 'FLAG_OWN_CAR', 'FLAG_OWN_REALTY',
    'EXT_SOURCE_1', 'EXT_SOURCE_2', 'EXT_SOURCE_3'
]

PREV_FIELDS = [
    'SK_ID_PREV', 'SK_ID_CURR', 'NAME_CONTRACT_STATUS',
    'NAME_CONTRACT_TYPE', 'AMT_APPLICATION', 'AMT_CREDIT', 'DAYS_DECISION'
]


def download_file(filename, meta, force=False):
    dest = RAW_DIR / filename
    if dest.exists() and not force:
        size_mb = dest.stat().st_size / (1024 * 1024)
        if size_mb >= meta['min_size_mb']:
            print(f"[OK] {filename} already exists ({size_mb:.1f} MB), skipping.")
            return True
        else:
            print(f"[WARN] {filename} exists but seems incomplete ({size_mb:.1f} MB), re-downloading...")

    url = meta['url']
    print(f"\n[DOWNLOADING] {filename} from {url}")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    start = time.time()
    temp_dest = dest.with_suffix('.tmp')

    try:
        with urllib.request.urlopen(req) as resp, open(temp_dest, 'wb') as out:
            total_size = int(resp.headers.get('Content-Length', 0))
            downloaded = 0
            last_report = 0

            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
                elapsed = time.time() - start
                speed = downloaded / (1024 * 1024) / max(elapsed, 0.001)

                if downloaded - last_report >= 10 * 1024 * 1024 or downloaded == total_size:
                    last_report = downloaded
                    percent = (downloaded / total_size * 100) if total_size > 0 else 0
                    print(f"  -> {downloaded / (1024*1024):.1f}/{total_size / (1024*1024):.1f} MB ({percent:.1f}%) at {speed:.2f} MB/s", end='\r')

        temp_dest.replace(dest)
        total_mb = dest.stat().st_size / (1024 * 1024)
        print(f"\n[SUCCESS] {filename} saved ({total_mb:.1f} MB in {time.time() - start:.1f}s)")
        return True
    except Exception as e:
        if temp_dest.exists():
            temp_dest.unlink()
        print(f"\n[ERROR] Failed to download {filename}: {e}", file=sys.stderr)
        return False


def verify_headers():
    print("\n--- Verifying CSV Schemas for ETL ---")
    all_ok = True

    # Check application_train.csv
    app_path = RAW_DIR / 'application_train.csv'
    if app_path.exists():
        with open(app_path, newline='', encoding='utf-8-sig') as f:
            header = set(csv.DictReader(f).fieldnames or [])
            missing = set(APP_FIELDS) - header
            if missing:
                print(f"[FAIL] application_train.csv missing required fields: {missing}")
                all_ok = False
            else:
                print("[PASS] application_train.csv contains all 20 required APP_FIELDS")

    # Check previous_application.csv
    prev_path = RAW_DIR / 'previous_application.csv'
    if prev_path.exists():
        with open(prev_path, newline='', encoding='utf-8-sig') as f:
            header = set(csv.DictReader(f).fieldnames or [])
            missing = set(PREV_FIELDS) - header
            if missing:
                print(f"[FAIL] previous_application.csv missing required fields: {missing}")
                all_ok = False
            else:
                print("[PASS] previous_application.csv contains all 7 required PREV_FIELDS")

    return all_ok


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--force', action='store_true', help='Force re-download even if files exist')
    parser.add_argument('--verify-only', action='store_true', help='Only verify existing files')
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if not args.verify_only:
        for fname, meta in FILES.items():
            success = download_file(fname, meta, force=args.force)
            if not success and meta['required']:
                print(f"[FATAL] Required file {fname} could not be downloaded.", file=sys.stderr)
                sys.exit(1)

    ok = verify_headers()
    if ok:
        print("\nAll dataset files are verified and ready for ETL loading!")
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
