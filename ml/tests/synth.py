"""Sinh du lieu GIA LAP (SYNTHETIC) cung schema Home Credit CHI de kiem thu code.
KHONG dung de bao cao ket qua ML."""
import numpy as np
import pandas as pd


def make_synthetic(n=6000, seed=7, dirty=True):
    rng = np.random.default_rng(seed)
    ids = np.arange(100001, 100001 + n)
    ext = rng.uniform(0, 1, (n, 3))
    income = np.exp(rng.normal(11.8, 0.5, n)).round(2)
    credit = (income * rng.uniform(0.5, 6, n)).round(2)
    annuity = (credit / rng.uniform(10, 40, n)).round(2)
    age = rng.uniform(21, 68, n)
    logit = -2.6 - 2.5 * (ext[:, 1] - 0.5) - 1.5 * (ext[:, 2] - 0.5) + 0.25 * np.log(credit / income)
    y = (rng.uniform(size=n) < 1 / (1 + np.exp(-logit))).astype(int)
    app = pd.DataFrame({
        "SK_ID_CURR": ids, "TARGET": y,
        "NAME_CONTRACT_TYPE": rng.choice(["Cash loans", "Revolving loans"], n, p=[.9, .1]),
        "AMT_INCOME_TOTAL": income, "AMT_CREDIT": credit, "AMT_ANNUITY": annuity,
        "DAYS_BIRTH": (-age * 365.25).astype(int),
        "DAYS_EMPLOYED": -rng.integers(0, 9000, n),
        "NAME_INCOME_TYPE": rng.choice(["Working", "Pensioner", "Commercial associate", "State servant"], n),
        "NAME_EDUCATION_TYPE": rng.choice(["Secondary / secondary special", "Higher education", "Incomplete higher"], n),
        "EXT_SOURCE_1": ext[:, 0], "EXT_SOURCE_2": ext[:, 1], "EXT_SOURCE_3": ext[:, 2],
        "EXTRA_UNUSED_COL": 1,
    })
    if dirty:
        pens = app["NAME_INCOME_TYPE"] == "Pensioner"
        app.loc[pens, "DAYS_EMPLOYED"] = 365243
        for c, frac in (("EXT_SOURCE_1", .5), ("EXT_SOURCE_3", .2), ("AMT_ANNUITY", .01)):
            app.loc[rng.uniform(size=n) < frac, c] = np.nan
        app.loc[app.index[:3], "AMT_INCOME_TOTAL"] = [-5, 0, np.nan]
        app.loc[app.index[3], "EXT_SOURCE_2"] = 1.7
        app.loc[app.index[4], "DAYS_BIRTH"] = 100
        app.loc[app.index[5], "NAME_EDUCATION_TYPE"] = "  "
        app.loc[app.index[6], "NAME_CONTRACT_TYPE"] = np.nan
    m = rng.integers(0, 6, n)
    rows = []
    pid = 5_000_000
    for i, k in zip(ids, m):
        for _ in range(k):
            pid += 1
            rows.append((pid, i, rng.choice(["Approved", "Refused", "Canceled", "Unused offer"], p=[.6, .15, .15, .1]),
                         -int(rng.integers(1, 2500))))
    prev = pd.DataFrame(rows, columns=["SK_ID_PREV", "SK_ID_CURR", "NAME_CONTRACT_STATUS", "DAYS_DECISION"])
    if dirty:
        prev["DAYS_DECISION"] = prev["DAYS_DECISION"].astype("float64")
        prev.loc[prev.index[:5], "DAYS_DECISION"] = [1, np.nan, 0, 7, np.nan]
        prev = pd.concat([prev, pd.DataFrame({"SK_ID_PREV": [9_000_001], "SK_ID_CURR": [999],
                                              "NAME_CONTRACT_STATUS": ["Approved"], "DAYS_DECISION": [-3]})])
    prev["NAME_CONTRACT_TYPE"] = "Cash loans"
    prev["AMT_APPLICATION"] = 1000.0
    prev["AMT_CREDIT"] = 900.0
    return app, prev
