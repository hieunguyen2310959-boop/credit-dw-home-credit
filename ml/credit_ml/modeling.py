"""Chia tap, pipeline Logistic Regression, baseline va danh gia.

Nguyen tac: preprocessing (imputer/scaler/encoder) chi fit tren TRAIN; chon C/nguong tren VALID;
HOLDOUT chi dung de bao cao mot lan.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, brier_score_loss, confusion_matrix,
                             log_loss, precision_recall_curve, roc_auc_score)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from . import config as C
from .features import log1p_money


# ---------------------------------------------------------------- split
def make_split(ids: pd.Series, y: pd.Series, seed=C.SPLIT_SEED,
               holdout=C.HOLDOUT_FRACTION, valid=C.VALID_FRACTION) -> pd.DataFrame:
    """Chia phan tang theo y, khong giao nhau. Tra ve DataFrame(application_id, split)."""
    idx = np.arange(len(ids))
    rest, ho = train_test_split(idx, test_size=holdout, stratify=y.values, random_state=seed)
    rel_valid = valid / (1 - holdout)
    tr, va = train_test_split(rest, test_size=rel_valid, stratify=y.values[rest], random_state=seed)
    split = np.empty(len(ids), dtype=object)
    split[tr], split[va], split[ho] = "train", "valid", "holdout"
    out = pd.DataFrame({C.ID_COLUMN: ids.values, "split": split})
    assert out[C.ID_COLUMN].is_unique
    return out


# ---------------------------------------------------------------- pipeline
def build_pipeline(C_value: float = 1.0, max_iter: int = 1000) -> Pipeline:
    pre = ColumnTransformer([
        ("num", Pipeline([("impute", SimpleImputer(strategy="median", add_indicator=True)),
                          ("scale", StandardScaler())]), C.NUMERIC_FEATURES),
        ("cat", Pipeline([("impute", SimpleImputer(strategy="constant", fill_value="Unknown")),
                          ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=20))]),
         C.CATEGORICAL_FEATURES),
    ], verbose_feature_names_out=True)
    return Pipeline([
        ("log_money", FunctionTransformer(log1p_money, validate=False)),
        ("pre", pre),
        ("clf", LogisticRegression(C=C_value, solver="lbfgs", max_iter=max_iter)),
    ])


def fit_pipeline(X: pd.DataFrame, y, C_value=1.0) -> Pipeline:
    pipe = build_pipeline(C_value)
    pipe.fit(X[C.PREDICTORS], np.asarray(y, dtype=int))
    return pipe


def predict_score(pipe, X: pd.DataFrame) -> np.ndarray:
    return pipe.predict_proba(X[C.PREDICTORS])[:, 1]


# ---------------------------------------------------------------- baselines
def prior_baseline(y_train) -> DummyClassifier:
    d = DummyClassifier(strategy="prior")
    d.fit(np.zeros((len(y_train), 1)), np.asarray(y_train, dtype=int))
    return d


def ext_mean_rule_score(X: pd.DataFrame) -> np.ndarray:
    """Baseline luat don gian: rui ro = 1 - trung binh EXT_SOURCE co san; thieu het -> trung vi 0.5."""
    m = X[["ext_source_1", "ext_source_2", "ext_source_3"]].mean(axis=1, skipna=True)
    return (1.0 - m.fillna(0.5)).to_numpy()


# ---------------------------------------------------------------- metrics
def threshold_metrics(y, p, thr: float) -> dict:
    y = np.asarray(y, dtype=int)
    pred = (p >= thr).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    prec = tp / (tp + fp) if (tp + fp) else None
    rec = tp / (tp + fn) if (tp + fn) else None
    return {"threshold": float(thr), "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
            "precision": None if prec is None else float(prec),
            "recall": None if rec is None else float(rec),
            "flagged_share": float(pred.mean())}


def best_f1_threshold(y, p) -> float:
    """Chon nguong F1 toi da - CHI goi tren VALID."""
    prec, rec, thr = precision_recall_curve(np.asarray(y, dtype=int), p)
    f1 = 2 * prec[:-1] * rec[:-1] / np.clip(prec[:-1] + rec[:-1], 1e-12, None)
    return float(thr[int(np.nanargmax(f1))])


def bootstrap_auc_ci(y, p, n_boot=200, seed=0, alpha=0.05):
    rng = np.random.default_rng(seed)
    y = np.asarray(y, dtype=int)
    n = len(y)
    vals = []
    for _ in range(n_boot):
        i = rng.integers(0, n, n)
        if y[i].min() == y[i].max():
            continue
        vals.append(roc_auc_score(y[i], p[i]))
    lo, hi = np.quantile(vals, [alpha / 2, 1 - alpha / 2])
    return float(lo), float(hi)


def score_metrics(y, p) -> dict:
    y = np.asarray(y, dtype=int)
    return {"n_evaluated": int(len(y)), "n_positive": int(y.sum()),
            "positive_rate": float(y.mean()),
            "roc_auc": float(roc_auc_score(y, p)),
            "pr_auc": float(average_precision_score(y, p)),
            "brier": float(brier_score_loss(y, np.clip(p, 0, 1))),
            "log_loss": float(log_loss(y, np.clip(p, 1e-15, 1 - 1e-15)))}


def calibration_table(y, p, bins=10) -> pd.DataFrame:
    """Chia theo decile cua diem: so ho so, diem TB, ty le nhan quan sat."""
    df = pd.DataFrame({"y": np.asarray(y, dtype=int), "p": p})
    df["bin"] = pd.qcut(df["p"].rank(method="first"), bins, labels=False)
    t = df.groupby("bin").agg(n=("y", "size"), mean_score=("p", "mean"),
                              observed_rate=("y", "mean"), min_score=("p", "min"),
                              max_score=("p", "max")).reset_index()
    return t


def band_table(y, p, review_thr, decline_thr) -> pd.DataFrame:
    band = np.where(p >= decline_thr, "HIGH", np.where(p >= review_thr, "MEDIUM", "LOW"))
    df = pd.DataFrame({"band": band, "y": np.asarray(y, dtype=int)})
    t = df.groupby("band").agg(n=("y", "size"), difficulty_count=("y", "sum"),
                               observed_rate=("y", "mean")).reindex(["LOW", "MEDIUM", "HIGH"])
    t["share"] = t["n"] / t["n"].sum()
    return t.reset_index()


def coefficient_table(pipe) -> pd.DataFrame:
    names = pipe.named_steps["pre"].get_feature_names_out()
    coef = pipe.named_steps["clf"].coef_[0]
    return pd.DataFrame({"feature": names, "coef": coef}).assign(
        abs_coef=lambda d: d["coef"].abs()).sort_values("abs_coef", ascending=False)
