"""Luu / tai artifact an toan: sha256, manifest, duong dan tuong doi, kiem tra phien ban."""
from __future__ import annotations

import hashlib
import json
import math
import platform
import sys
from pathlib import Path

import joblib

MANIFEST_NAME = "model_manifest.json"
PIPELINE_NAME = "pipeline.joblib"


def sha256_file(path, block=1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(block), b""):
            h.update(chunk)
    return h.hexdigest()


def library_versions() -> dict:
    import numpy, pandas, sklearn
    return {"python": platform.python_version(), "scikit-learn": sklearn.__version__,
            "pandas": pandas.__version__, "numpy": numpy.__version__, "joblib": joblib.__version__}


def json_safe(obj):
    """Doi NaN/Inf -> None, numpy -> python; JSON hop le cho JSONB."""
    import numpy as np
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    if isinstance(obj, np.generic):
        obj = obj.item()
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


def save_bundle(model_dir, pipeline, manifest: dict) -> dict:
    model_dir = Path(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    art = model_dir / PIPELINE_NAME
    joblib.dump(pipeline, art, compress=3)
    manifest = dict(manifest)
    manifest["artifact"] = {"file": PIPELINE_NAME, "sha256": sha256_file(art)}
    manifest["libraries"] = library_versions()
    (model_dir / MANIFEST_NAME).write_text(
        json.dumps(json_safe(manifest), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return manifest


def resolve_model_dir(models_root, relative_dir) -> Path:
    """Chi cho phep thu muc nam TRONG models_root (khong nhan duong dan tuy y tu nguoi dung)."""
    root = Path(models_root).resolve()
    target = (root / relative_dir).resolve()
    if root != target and root not in target.parents:
        raise ValueError("Duong dan model nam ngoai models_root")
    return target


def load_manifest(model_dir) -> dict:
    return json.loads((Path(model_dir) / MANIFEST_NAME).read_text(encoding="utf-8"))


def load_pipeline(model_dir, verify=True):
    model_dir = Path(model_dir)
    manifest = load_manifest(model_dir)
    art = model_dir / manifest["artifact"]["file"]
    if verify and sha256_file(art) != manifest["artifact"]["sha256"]:
        raise ValueError("sha256 artifact khong khop manifest - file da bi sua hoac hong")
    import sklearn
    trained_with = manifest.get("libraries", {}).get("scikit-learn")
    warn = None
    if trained_with and trained_with != sklearn.__version__:
        warn = (f"scikit-learn khi train={trained_with}, hien tai={sklearn.__version__}; "
                f"nen pip install scikit-learn=={trained_with}")
    return joblib.load(art), manifest, warn
