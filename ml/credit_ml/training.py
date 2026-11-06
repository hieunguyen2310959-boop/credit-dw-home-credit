"""Gom cac buoc sau khi train: reference stats + manifest (tai lap duoc)."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C
from .artifacts import sha256_file
from .policy import PolicyConfig


def compute_reference_stats(pipe, X_train: pd.DataFrame, policy_quantile=0.99) -> dict:
    """Thong ke THAM CHIEU tinh tu TRAIN: trung binh feature da bien doi (de giai thich LR)
    va nguong p99 cua credit_income_ratio (canh bao bat thuong)."""
    Xt = pipe.named_steps["log_money"].transform(X_train[C.PREDICTORS])
    z = pipe.named_steps["pre"].transform(Xt)
    z = z.toarray() if hasattr(z, "toarray") else np.asarray(z)
    names = pipe.named_steps["pre"].get_feature_names_out()
    ratio = X_train["credit_income_ratio"].dropna()
    return {
        "transformed_mean": {str(n): float(m) for n, m in zip(names, z.mean(axis=0))},
        "credit_income_ratio_p99": float(ratio.quantile(policy_quantile)),
        "n_train": int(len(X_train)),
    }


def file_record(path, role, rows=None) -> dict:
    p = Path(path)
    rec = {"role": role, "file": p.name, "sha256": sha256_file(p)}
    if rows is not None:
        rec["rows"] = int(rows)
    return rec


def build_manifest(*, model_name, selected_C, tuning, split_counts, split_ids_rel, split_ids_sha,
                   data_files, build_report, label_stats, evaluation_metrics, policy: PolicyConfig,
                   reference_stats, smoke_test, notes=None) -> dict:
    return {
        "manifest_version": 1,
        "model_name": model_name,
        "feature_version": C.FEATURE_VERSION,
        "trained_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "predictors": C.PREDICTORS,
        "numeric_features": C.NUMERIC_FEATURES,
        "categorical_features": C.CATEGORICAL_FEATURES,
        "algorithm": {"estimator": "LogisticRegression(lbfgs, no class_weight)", "C": selected_C,
                      "preprocessing": "log1p(money) -> median impute + missing indicator -> StandardScaler; "
                                       "categorical constant 'Unknown' -> OneHot(min_frequency=20)",
                      "tuning_on": "validation split", "tuning_table": tuning},
        "split": {"seed": C.SPLIT_SEED, "fractions": {"train": 1 - C.HOLDOUT_FRACTION - C.VALID_FRACTION,
                                                      "valid": C.VALID_FRACTION, "holdout": C.HOLDOUT_FRACTION},
                  "counts": split_counts, "ids_file": split_ids_rel, "ids_sha256": split_ids_sha,
                  "stratified_by": "target"},
        "data": {"files": data_files, "cohort": "application_train", "label_stats": label_stats,
                 "build_report": build_report},
        "evaluation_metrics": evaluation_metrics,
        "policy": policy.to_dict(),
        "reference_stats": reference_stats,
        "smoke_test": smoke_test,
        "notes": notes or [],
    }
