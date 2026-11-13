"""Kiem thu code ML bang du lieu SYNTHETIC. Khong dung de bao cao metric."""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from synth import make_synthetic
from credit_ml import config as C, features as F, modeling as M, training as T, artifacts as A
from credit_ml import inference as I, whatif as W
from credit_ml.policy import PolicyConfig, apply_policy

APP_COLS = C.APP_COLUMNS


def tiny_sources():
    # Cung 3 ho so + 5 lich su nhu tests/test_etl.py cua nguoi 1
    app = pd.DataFrame([
        [1001, 1, "Cash loans", 100, 200, 10, -10957, -365, "Working", "Higher education", .3, .4, .5],
        [1002, 0, "Revolving loans", 0, 300, 15, -18263, 365243, "Pensioner", "", np.nan, np.nan, .6],
        [1003, 0, "", 200, 500, 20, np.nan, np.nan, "Working", "", np.nan, np.nan, np.nan],
    ], columns=[c for c in APP_COLS])
    prev = pd.DataFrame([
        [11, 1001, "Approved", -30], [12, 1001, "Refused", -10], [13, 1001, "Approved", 1],
        [14, 9999, "Approved", -1], [15, 1001, "Canceled", np.nan],
    ], columns=C.PREV_COLUMNS)
    return app, prev


def test_feature_contract_matches_person1_rules():
    X, lab, rep = F.build_feature_table(*tiny_sources())
    r = X.set_index("application_id")
    assert list(X.columns) == ["application_id"] + C.PREDICTORS and "target" not in X
    assert (r.loc[1001, ["previous_application_count", "previous_approved_count", "previous_refused_count"]].tolist() == [2, 1, 1])
    assert r.loc[1001, "previous_approval_rate"] == 0.5
    assert math.isnan(r.loc[1002, "credit_income_ratio"])       # income = 0
    assert math.isnan(r.loc[1002, "employment_days"])           # sentinel 365243
    assert math.isnan(r.loc[1003, "age_years"]) and r.loc[1003, "contract_type_name"] == "Unknown"
    assert math.isnan(r.loc[1003, "previous_approval_rate"])    # khong co lich su
    assert rep["previous"] == {"input": 5, "orphan": 1, "future": 1, "unknown_cutoff": 1}
    assert abs(r.loc[1001, "age_years"] - 10957 / 365.25) < 1e-12


def test_predictors_match_shared_contract_file():
    contract = json.loads((Path(__file__).resolve().parents[2] / "contracts" / "features-v1.json").read_text())
    assert contract["predictors"] == C.PREDICTORS
    assert set(contract["excluded_from_predictors"]).isdisjoint(C.PREDICTORS)


@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    app, prev = make_synthetic(3000)
    X, lab, _ = F.build_feature_table(app, prev)
    y = lab["target"].astype(int)
    sp = M.make_split(X["application_id"], y)
    tr = (sp["split"] == "train").values
    pipe = M.fit_pipeline(X[tr], y[tr], 0.1)
    ref = T.compute_reference_stats(pipe, X[tr])
    pol = PolicyConfig(ratio_extreme_threshold=ref["credit_income_ratio_p99"])
    root = tmp_path_factory.mktemp("models")
    A.save_bundle(root / "m1", pipe, {"model_name": C.MODEL_NAME, "feature_version": C.FEATURE_VERSION,
                                      "policy": pol.to_dict(), "reference_stats": ref})
    return {"X": X, "y": y, "split": sp, "pipe": pipe, "root": root, "bundle": I.load_bundle(root, "m1", 5)}


def test_split_disjoint_stratified(trained):
    sp, y = trained["split"], trained["y"]
    assert sp["application_id"].is_unique and set(sp["split"]) == {"train", "valid", "holdout"}
    rates = [y[(sp["split"] == s).values].mean() for s in ("train", "valid", "holdout")]
    assert max(rates) - min(rates) < 0.01


def test_assess_matches_pipeline_and_has_no_label(trained):
    b, X = trained["bundle"], trained["X"]
    for _, row in X.head(25).iterrows():
        f = I.features_from_row(row)
        r = I.assess(b, int(row["application_id"]), f)
        expect = M.predict_score(trained["pipe"], X.loc[[row.name]])[0]
        assert abs(r["risk_score"] - expect) < 1e-12
        assert set(r["feature_snapshot"]) == set(C.PREDICTORS)
        json.dumps(r, allow_nan=False)          # khong NaN/Infinity
        assert r["model_run_id"] == 5 and r["status"] == "succeeded"
        db = I.to_db_row(r)
        assert db["risk_band"] and db["recommendation"] and 0 <= db["risk_score"] <= 1


@pytest.mark.parametrize("bad", ["target", "TARGET", "risk_score", "recommendation", "data_source"])
def test_forbidden_keys_rejected(trained, bad):
    f = I.features_from_row(trained["X"].iloc[0])
    with pytest.raises(I.InvalidFeatures) as e:
        I.assess(trained["bundle"], 1, {**f, bad: 1})
    assert any(c.startswith("FORBIDDEN_KEY") for c in e.value.codes)


def test_validation_errors(trained):
    f = I.features_from_row(trained["X"].iloc[0])
    for patch, code in [({"ext_source_1": 1.5}, "OUT_OF_RANGE:ext_source_1"),
                        ({"amt_credit": -1}, "NEGATIVE_VALUE:amt_credit"),
                        ({"amt_credit": float("inf")}, "NON_FINITE:amt_credit"),
                        ({"amt_credit": "100"}, "INVALID_TYPE:amt_credit"),
                        ({"junk": 1}, "UNKNOWN_KEY:junk")]:
        with pytest.raises(I.InvalidFeatures) as e:
            I.validate_features({**f, **patch})
        assert code in e.value.codes
    f2 = dict(f); f2.pop("amt_credit")
    with pytest.raises(I.InvalidFeatures):
        I.validate_features(f2)
    nan_ok = I.validate_features({**f, "ext_source_1": float("nan")})
    assert nan_ok["ext_source_1"] is None


def test_missing_values_do_not_crash_and_force_review(trained):
    f = {k: None for k in C.PREDICTORS}
    f.update(income_type=None, education_level=None, contract_type_name=None)
    r = I.assess(trained["bundle"], 1, f)
    assert r["recommendation"] == "REVIEW" and "DATA_ALERT_FORCES_REVIEW" in r["reason_codes"]
    assert r["feature_snapshot"]["income_type"] == "Unknown"


def test_policy_thresholds():
    pol = PolicyConfig()
    ok = {"amt_income_total": 1.0, "amt_credit": 1.0, "age_years": 30.0, "ext_source_1": .5}
    assert apply_policy(0.05, ok, pol)["recommendation"] == "APPROVE_SIMULATION"
    assert apply_policy(0.10, ok, pol)["recommendation"] == "REVIEW"
    assert apply_policy(0.25, ok, pol)["recommendation"] == "DECLINE_SIMULATION"
    assert apply_policy(0.25, ok, pol)["risk_band"] == "HIGH"
    with pytest.raises(ValueError):
        apply_policy(float("nan"), ok, pol)
    with pytest.raises(ValueError):
        PolicyConfig(review_threshold=0.3, decline_threshold=0.2)


def test_whatif_invariants(trained):
    b, X = trained["bundle"], trained["X"]
    row = X[X["amt_income_total"] > 0].iloc[0]
    f = I.features_from_row(row)
    only_thr = W.what_if(b, 1, f, review_threshold=0.01)
    assert only_thr["score_delta"] == 0 and only_thr["is_hypothetical"] and not only_thr["persisted"]
    inc = W.what_if(b, 1, f, income=f["amt_income_total"] * 2)
    assert abs(inc["changed_inputs"]["credit_income_ratio"]["to"] - f["amt_credit"] / (2 * f["amt_income_total"])) < 1e-9
    assert I.features_from_row(row) == f                      # nguon khong bi sua
    with pytest.raises(I.InvalidFeatures):
        W.what_if(b, 1, f, review_threshold=0.5, decline_threshold=0.2)
    with pytest.raises(I.InvalidFeatures):
        W.what_if(b, 1, f, income=-5)


def test_factors_sum_to_logit(trained):
    b, X = trained["bundle"], trained["X"]
    f = I.features_from_row(X.iloc[3])
    clean = I.validate_features(f)
    allf = I.model_factors(b, clean, top_k=1000)
    logit_ref = b.pipeline.named_steps["clf"].intercept_[0] + sum(
        c * b.transformed_mean[n] for n, c in zip(b.pipeline.named_steps["pre"].get_feature_names_out(),
                                                  b.pipeline.named_steps["clf"].coef_[0]))
    p = I.score_clean(b, clean)
    assert abs(sum(x["log_odds_contribution"] for x in allf) + logit_ref - math.log(p / (1 - p))) < 1e-8


def test_artifact_integrity_and_path_safety(trained, tmp_path):
    import shutil
    shutil.copytree(trained["root"], tmp_path / "m")
    with pytest.raises(I.ModelNotReady):
        I.load_bundle(tmp_path / "m", "../etc")
    with pytest.raises(I.ModelNotReady):
        I.load_bundle(tmp_path / "m", "does_not_exist")
    with open(tmp_path / "m" / "m1" / A.PIPELINE_NAME, "ab") as fh:
        fh.write(b"x")
    with pytest.raises(I.ModelNotReady):
        I.load_bundle(tmp_path / "m", "m1")


def test_failed_and_not_ready_shapes():
    nr = I.not_ready_result(1)
    assert nr["risk_score"] is None and nr["model_run_id"] is None
    with pytest.raises(ValueError):
        I.to_db_row(nr)
    fr = I.failed_result(1, 3, ["X"], {"target": 1, **{k: None for k in C.PREDICTORS}})
    assert fr["risk_score"] is None and "target" not in fr["feature_snapshot"] and fr["reason_codes"]
    I.to_db_row(fr)


def test_bad_inputs_in_csv(tmp_path):
    app, prev = make_synthetic(50, dirty=False)
    app.loc[0, "TARGET"] = 2
    p = tmp_path / "a.csv"; app.to_csv(p, index=False)
    with pytest.raises(ValueError):
        F.read_application_csv(p)
    app.loc[0, "TARGET"] = 0; app.drop(columns=["EXT_SOURCE_2"]).to_csv(p, index=False)
    with pytest.raises(ValueError):
        F.read_application_csv(p)
    app["EXT_SOURCE_2"] = 0.5; app.loc[1, "SK_ID_CURR"] = app.loc[0, "SK_ID_CURR"]; app.to_csv(p, index=False)
    with pytest.raises(ValueError):
        F.read_application_csv(p)
