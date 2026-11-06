"""Tai tao mart.application_features_v1 bang pandas, dung cung luat lam sach voi
sql/003_load_dw.sql + sql/002_views.sql.

Quy tac (khop SQL):
  age_years        = -DAYS_BIRTH/365.25 neu DAYS_BIRTH < 0, nguoc lai NULL
  amt_*            = gia tri neu >= 0, nguoc lai NULL
  employment_days  = -DAYS_EMPLOYED neu DAYS_EMPLOYED <= 0 (365243 va >0 -> NULL)
  ext_source_*     = gia tri neu trong [0,1], nguoc lai NULL
  nhan phan loai   = trim; rong/thieu -> 'Unknown'
  lich su          = previous co DAYS_DECISION <= 0 (NULL/tuong lai bi loai), gom theo SK_ID_CURR
  credit_income_ratio    = amt_credit/amt_income_total neu income > 0
  previous_approval_rate = approved/count neu count > 0
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as C


def _read_csv(path, columns, label):
    header = pd.read_csv(path, nrows=0, encoding="utf-8-sig").columns
    if header.duplicated().any():
        raise ValueError(f"{label}: header co cot trung")
    required = set(columns)
    missing = sorted(required - set(header))
    if missing:
        raise ValueError(f"{label}: thieu cot bat buoc {missing}")
    return pd.read_csv(path, usecols=columns, encoding="utf-8-sig", low_memory=False)


def _require_numeric(df, cols, label):
    for col in cols:
        if not pd.api.types.is_numeric_dtype(df[col]):
            coerced = pd.to_numeric(df[col], errors="coerce")
            bad = coerced.isna() & df[col].notna()
            if bad.any():
                raise ValueError(f"{label}: cot {col} co {int(bad.sum())} gia tri khong phai so")
            df[col] = coerced


def read_application_csv(path) -> pd.DataFrame:
    """Doc application_train.csv (co TARGET 0/1)."""
    df = _read_csv(path, C.APP_COLUMNS, "application_train")
    _require_numeric(df, [c for c in C.APP_COLUMNS if not c.startswith("NAME_")], "application_train")
    if df["SK_ID_CURR"].isna().any() or df["SK_ID_CURR"].duplicated().any():
        raise ValueError("application_train: SK_ID_CURR thieu hoac trung")
    df["SK_ID_CURR"] = df["SK_ID_CURR"].astype("int64")
    if df["TARGET"].isna().any() or not df["TARGET"].isin([0, 1]).all():
        raise ValueError("application_train: TARGET phai la 0/1, khong duoc thieu")
    return df


def read_previous_csv(path) -> pd.DataFrame:
    df = _read_csv(path, C.PREV_COLUMNS, "previous_application")
    _require_numeric(df, ["SK_ID_PREV", "SK_ID_CURR", "DAYS_DECISION"], "previous_application")
    if df["SK_ID_PREV"].isna().any() or df["SK_ID_PREV"].duplicated().any():
        raise ValueError("previous_application: SK_ID_PREV thieu hoac trung")
    if df["SK_ID_CURR"].isna().any():
        raise ValueError("previous_application: SK_ID_CURR thieu")
    df["SK_ID_CURR"] = df["SK_ID_CURR"].astype("int64")
    return df


def _clean_label(series: pd.Series) -> pd.Series:
    s = series.astype("string").str.strip()
    s = s.mask(s == "", pd.NA).fillna("Unknown")
    return s.astype(object)


def aggregate_history(app_ids: pd.Series, prev: pd.DataFrame):
    """Tong hop lich su ve 1 dong/SK_ID_CURR TRUOC khi ghep (tranh nhan dong)."""
    in_cohort = prev["SK_ID_CURR"].isin(set(app_ids))
    stats = {
        "input": int(len(prev)),
        "orphan": int((~in_cohort).sum()),
        "future": int((prev["DAYS_DECISION"] > 0).sum()),
        "unknown_cutoff": int(prev["DAYS_DECISION"].isna().sum()),
    }
    eligible = prev[prev["DAYS_DECISION"] <= 0]  # NaN <= 0 la False -> loai, giong SQL
    status = eligible["NAME_CONTRACT_STATUS"]
    g = eligible.assign(
        _appr=(status == "Approved").astype("int64"),
        _ref=(status == "Refused").astype("int64"),
    ).groupby("SK_ID_CURR").agg(
        previous_application_count=("SK_ID_PREV", "size"),
        previous_approved_count=("_appr", "sum"),
        previous_refused_count=("_ref", "sum"),
    )
    return g, stats


def build_feature_table(app: pd.DataFrame, prev: pd.DataFrame):
    """Tra ve (features, labels, report).

    features: 1 dong/application_id, cot = [application_id] + PREDICTORS (khong co TARGET)
    labels  : application_id, target (rieng, de tach y khoi X)
    """
    hist, prev_stats = aggregate_history(app["SK_ID_CURR"], prev)

    def nonneg(col):
        v = app[col].astype("float64")
        return v.where(v >= 0)

    days_birth = app["DAYS_BIRTH"].astype("float64")
    days_emp = app["DAYS_EMPLOYED"].astype("float64")

    f = pd.DataFrame({C.ID_COLUMN: app["SK_ID_CURR"].astype("int64").values})
    f["amt_income_total"] = nonneg("AMT_INCOME_TOTAL").values
    f["amt_credit"] = nonneg("AMT_CREDIT").values
    f["amt_annuity"] = nonneg("AMT_ANNUITY").values
    f["age_years"] = (-days_birth / 365.25).where(days_birth < 0).values
    f["employment_days"] = (-days_emp).where(days_emp <= 0).values
    f["income_type"] = _clean_label(app["NAME_INCOME_TYPE"]).values
    f["education_level"] = _clean_label(app["NAME_EDUCATION_TYPE"]).values
    f["contract_type_name"] = _clean_label(app["NAME_CONTRACT_TYPE"]).values
    for i in (1, 2, 3):
        v = app[f"EXT_SOURCE_{i}"].astype("float64")
        f[f"ext_source_{i}"] = v.where(v.between(0, 1)).values

    h = hist.reindex(app["SK_ID_CURR"].values).fillna(0).astype("int64")
    for col in ("previous_application_count", "previous_approved_count", "previous_refused_count"):
        f[col] = h[col].values

    inc, cred = f["amt_income_total"], f["amt_credit"]
    f["credit_income_ratio"] = (cred / inc).where(inc > 0)
    cnt = f["previous_application_count"]
    f["previous_approval_rate"] = (f["previous_approved_count"] / cnt).where(cnt > 0)

    features = f[[C.ID_COLUMN] + C.PREDICTORS].reset_index(drop=True)
    if features[C.ID_COLUMN].duplicated().any():
        raise ValueError("Feature table khong dung grain: application_id bi trung")
    labels = pd.DataFrame({C.ID_COLUMN: features[C.ID_COLUMN],
                           C.LABEL_COLUMN: app["TARGET"].astype("Int64").values})

    cleaning = {
        "negative_income": int((app["AMT_INCOME_TOTAL"] < 0).sum()),
        "negative_credit": int((app["AMT_CREDIT"] < 0).sum()),
        "invalid_employment": int((app["DAYS_EMPLOYED"] > 0).sum()),
        "invalid_age": int((app["DAYS_BIRTH"] >= 0).sum()),
        "invalid_ext_source": int(sum(((app[f"EXT_SOURCE_{i}"] < 0) | (app[f"EXT_SOURCE_{i}"] > 1)).sum() for i in (1, 2, 3))),
    }
    report = {"applications": int(len(features)), "previous": prev_stats, "cleaning": cleaning}
    return features, labels, report


def log1p_money(df: pd.DataFrame) -> pd.DataFrame:
    """Buoc dau cua pipeline: log1p cho cot tien (>=0 hoac NaN). Phai o module-level de joblib pickle."""
    out = df.copy()
    for col in C.MONEY_FEATURES:
        out[col] = np.log1p(out[col].astype("float64").clip(lower=0))
    return out
