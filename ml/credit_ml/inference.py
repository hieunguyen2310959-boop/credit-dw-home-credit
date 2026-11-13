"""Suy luan cho FastAPI. Khong train, khong doc TARGET, khong ghi DB.

Luong: validate_features -> pipeline.predict_proba -> apply_policy -> dict ket qua.
FE chi can: bundle = load_bundle(...); result = assess(bundle, application_id, features_row, model_run_id=...)
roi INSERT ml.assessments bang to_db_row(result) trong transaction cua API.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd

from . import config as C
from .artifacts import json_safe, load_pipeline, resolve_model_dir
from .policy import PolicyConfig, apply_policy


INTEGER_FEATURES = {"employment_days", "previous_application_count", "previous_approved_count",
                    "previous_refused_count"}


class ModelNotReady(RuntimeError):
    """Chua co model/artifact hop le -> API tra 503 + status not_ready (khong ghi model gia)."""


class InvalidFeatures(ValueError):
    """Dau vao khong hop le -> API tra 422. .codes la danh sach ma loi."""
    def __init__(self, codes):
        self.codes = list(codes)
        super().__init__("; ".join(self.codes))


@dataclass
class ModelBundle:
    pipeline: Any
    manifest: dict
    policy: PolicyConfig
    transformed_mean: dict
    model_run_id: int | None = None
    library_warning: str | None = None
    model_dir: str | None = None

    @property
    def model_name(self):
        return self.manifest["model_name"]


def load_bundle(models_root, relative_dir, model_run_id=None) -> ModelBundle:
    """Tai model tu thu muc nam trong models_root; kiem tra sha256. Loi -> ModelNotReady."""
    try:
        model_dir = resolve_model_dir(models_root, relative_dir)
        pipe, manifest, warn = load_pipeline(model_dir, verify=True)
        policy = PolicyConfig.from_dict(manifest["policy"])
        mean = manifest["reference_stats"]["transformed_mean"]
    except Exception as exc:  # file thieu, sha sai, manifest hong...
        raise ModelNotReady(f"{type(exc).__name__}: {exc}") from exc
    return ModelBundle(pipe, manifest, policy, mean, model_run_id, warn, str(model_dir))


def _to_number(name, v, errors):
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float, Decimal, np.integer, np.floating)):
        errors.append(f"INVALID_TYPE:{name}")
        return None
    v = float(v)
    if math.isnan(v):
        return None
    if math.isinf(v):
        errors.append(f"NON_FINITE:{name}")
        return None
    return v


def validate_features(features: dict) -> dict:
    """Tra ve dict dung 16 predictor (thieu -> None). Cam khoa nhan/ket qua. Loi -> InvalidFeatures."""
    if not isinstance(features, dict):
        raise InvalidFeatures(["FEATURES_NOT_OBJECT"])
    errors = []
    keys = {str(k).lower() for k in features}
    for bad in sorted(keys & C.FORBIDDEN_INPUT_KEYS):
        errors.append(f"FORBIDDEN_KEY:{bad}")
    extra = [k for k in features if k not in C.PREDICTORS and k != C.ID_COLUMN
             and str(k).lower() not in C.FORBIDDEN_INPUT_KEYS]
    errors += [f"UNKNOWN_KEY:{k}" for k in extra]
    errors += [f"MISSING_KEY:{k}" for k in C.PREDICTORS if k not in features]
    if errors:
        raise InvalidFeatures(errors)
    out = {}
    for name in C.PREDICTORS:
        v = features[name]
        if name in C.CATEGORICAL_FEATURES:
            if v is None or (isinstance(v, str) and not v.strip()):
                out[name] = "Unknown"
            elif isinstance(v, str):
                out[name] = v.strip()
            else:
                errors.append(f"INVALID_TYPE:{name}")
        else:
            out[name] = _to_number(name, v, errors)
            if name in INTEGER_FEATURES and out[name] is not None and float(out[name]).is_integer():
                out[name] = int(out[name])
    for name in C.MONEY_FEATURES + ["employment_days", "age_years", "previous_application_count",
                                    "previous_approved_count", "previous_refused_count"]:
        if out.get(name) is not None and out[name] < 0:
            errors.append(f"NEGATIVE_VALUE:{name}")
    for i in (1, 2, 3):
        v = out[f"ext_source_{i}"]
        if v is not None and not 0.0 <= v <= 1.0:
            errors.append(f"OUT_OF_RANGE:ext_source_{i}")
    r = out["previous_approval_rate"]
    if r is not None and not 0.0 <= r <= 1.0:
        errors.append("OUT_OF_RANGE:previous_approval_rate")
    if errors:
        raise InvalidFeatures(errors)
    return out


def _frame(clean: dict) -> pd.DataFrame:
    row = {k: (np.nan if clean[k] is None else clean[k]) for k in C.NUMERIC_FEATURES}
    row.update({k: clean[k] for k in C.CATEGORICAL_FEATURES})
    return pd.DataFrame([row])[C.PREDICTORS]


def score_clean(bundle: ModelBundle, clean: dict) -> float:
    p = float(bundle.pipeline.predict_proba(_frame(clean))[0, 1])
    if not math.isfinite(p) or not 0.0 <= p <= 1.0:
        raise RuntimeError("Model tra diem khong hop le")
    return p


def _origin(transformed_name: str) -> str:
    n = transformed_name
    if n.startswith("num__"):
        n = n[5:]
        return n[len("missingindicator_"):] if n.startswith("missingindicator_") else n
    if n.startswith("cat__"):
        n = n[5:]
        for col in C.CATEGORICAL_FEATURES:
            if n.startswith(col + "_"):
                return col
    return n


def model_factors(bundle: ModelBundle, clean: dict, top_k: int = 3) -> list:
    """Dong gop that cua LR vao log-odds so voi ho so trung binh cua TRAIN:
    sum_j coef_j * (x_j - mean_j), gop ve feature goc. Khong phai quan he nhan qua."""
    pre, clf = bundle.pipeline.named_steps["pre"], bundle.pipeline.named_steps["clf"]
    X = bundle.pipeline.named_steps["log_money"].transform(_frame(clean))
    x = pre.transform(X)
    x = x.toarray() if hasattr(x, "toarray") else np.asarray(x)
    names = pre.get_feature_names_out()
    mean = np.array([bundle.transformed_mean[n] for n in names])
    contrib = clf.coef_[0] * (x[0] - mean)
    agg: dict[str, float] = {}
    for n, c in zip(names, contrib):
        agg[_origin(n)] = agg.get(_origin(n), 0.0) + float(c)
    ranked = sorted(agg.items(), key=lambda kv: abs(kv[1]), reverse=True)[:top_k]
    return [{"feature": k, "log_odds_contribution": v,
             "direction": "raises_risk" if v > 0 else "lowers_risk"} for k, v in ranked if v != 0.0]


def assess(bundle: ModelBundle, application_id: int, features: dict, *,
           policy: PolicyConfig | None = None, model_run_id: int | None = None, top_k: int = 3) -> dict:
    clean = validate_features(features)
    p = score_clean(bundle, clean)
    pol = apply_policy(p, clean, policy or bundle.policy)
    factors = model_factors(bundle, clean, top_k)
    reasons = pol["reason_codes"] + [
        f"MODEL_FACTOR_{'UP' if f['direction'] == 'raises_risk' else 'DOWN'}:{f['feature']}" for f in factors]
    return json_safe({
        "status": "succeeded", "application_id": int(application_id),
        "model_run_id": model_run_id if model_run_id is not None else bundle.model_run_id,
        "model_name": bundle.model_name, "feature_version": bundle.manifest["feature_version"],
        "risk_score": p, "risk_band": pol["risk_band"], "recommendation": pol["recommendation"],
        "policy_version": pol["policy_version"], "reason_codes": reasons,
        "alerts": pol["alerts"], "model_factors": factors, "feature_snapshot": clean,
    })


def not_ready_result(application_id, reason_code="MODEL_NOT_READY",
                     policy_version=PolicyConfig().version) -> dict:
    """KHONG co model_run_id that -> API tra 503, khong INSERT (ml.assessments.model_run_id NOT NULL)."""
    return {"status": "not_ready", "application_id": int(application_id), "model_run_id": None,
            "risk_score": None, "risk_band": None, "recommendation": None,
            "policy_version": policy_version, "reason_codes": [reason_code], "feature_snapshot": None}


def failed_result(application_id, model_run_id, reason_codes, features=None,
                  policy_version=PolicyConfig().version) -> dict:
    """Da chon model nhung cham loi; co the INSERT status='failed' (feature_snapshot khong nhan)."""
    snap = None
    if isinstance(features, dict):
        snap = {k: features.get(k) for k in C.PREDICTORS}
    return json_safe({"status": "failed", "application_id": int(application_id),
                      "model_run_id": model_run_id, "risk_score": None, "risk_band": None,
                      "recommendation": None, "policy_version": policy_version,
                      "reason_codes": list(reason_codes) or ["SCORING_FAILED"],
                      "feature_snapshot": snap if snap is not None else {}})


def to_db_row(result: dict) -> dict:
    """Cac cot de INSERT vao ml.assessments (assessment_id/assessed_at do DB sinh)."""
    if result["status"] == "not_ready":
        raise ValueError("not_ready khong duoc ghi vao ml.assessments (khong co model_run_id)")
    return {k: result[k] for k in ("application_id", "model_run_id", "status", "feature_snapshot",
                                   "risk_score", "risk_band", "recommendation",
                                   "policy_version", "reason_codes")}


def features_from_row(row) -> dict:
    """Doi 1 dong pandas/dict (vd tu mart.application_features_v1) thanh dict 16 predictor, NaN -> None."""
    out = {}
    for k in C.PREDICTORS:
        v = row[k]
        if isinstance(v, (np.floating, float)):
            v = None if math.isnan(v) else float(v)
        elif isinstance(v, np.integer):
            v = int(v)
        elif v is pd.NA:
            v = None
        out[k] = v
    return out
