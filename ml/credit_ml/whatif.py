"""What-if: gia dinh thu nhap va/hoac nguong policy. Khong ghi de nguon, khong ghi DB.
Ket qua la mo phong, khong dien giai nhu quan he nhan qua."""
from __future__ import annotations

import math
from dataclasses import replace

from .inference import ModelBundle, InvalidFeatures, assess, validate_features

NOTE = ("Ket qua gia dinh (hypothetical), khong ghi vao du lieu goc va khong phai quan he nhan qua; "
        "chi doi nguong policy thi diem model khong doi.")


def what_if(bundle: ModelBundle, application_id: int, features: dict, *,
            income: float | None = None, review_threshold: float | None = None,
            decline_threshold: float | None = None, model_run_id=None) -> dict:
    base_features = validate_features(features)
    scenario = dict(base_features)
    changed = {}
    if income is not None:
        if isinstance(income, bool) or not isinstance(income, (int, float)) or not math.isfinite(income) or income < 0:
            raise InvalidFeatures(["INVALID_WHATIF_INCOME"])
        scenario["amt_income_total"] = float(income)
        credit = scenario["amt_credit"]
        # Feature dan xuat phai tinh lai cung cong thuc voi DW: credit/income khi income > 0
        scenario["credit_income_ratio"] = (credit / income) if (income > 0 and credit is not None) else None
        changed["amt_income_total"] = {"from": base_features["amt_income_total"], "to": float(income)}
        changed["credit_income_ratio"] = {"from": base_features["credit_income_ratio"],
                                          "to": scenario["credit_income_ratio"]}
    pol = bundle.policy
    policy_changes = {}
    new_pol = pol
    if review_threshold is not None or decline_threshold is not None:
        try:
            new_pol = replace(
                pol,
                review_threshold=pol.review_threshold if review_threshold is None else review_threshold,
                decline_threshold=pol.decline_threshold if decline_threshold is None else decline_threshold,
                version=pol.version + "+what_if")
        except ValueError as exc:
            raise InvalidFeatures(["INVALID_WHATIF_THRESHOLDS"]) from exc
        policy_changes = {"review_threshold": {"from": pol.review_threshold, "to": new_pol.review_threshold},
                          "decline_threshold": {"from": pol.decline_threshold, "to": new_pol.decline_threshold}}

    before = assess(bundle, application_id, base_features, model_run_id=model_run_id)
    after = assess(bundle, application_id, scenario, policy=new_pol, model_run_id=model_run_id)

    def brief(r):
        return {k: r[k] for k in ("risk_score", "risk_band", "recommendation", "policy_version",
                                  "reason_codes", "model_factors")}
    return {
        "application_id": int(application_id), "is_hypothetical": True, "persisted": False,
        "changed_inputs": changed, "changed_policy": policy_changes,
        "original": brief(before), "scenario": brief(after),
        "score_delta": after["risk_score"] - before["risk_score"],
        "recommendation_changed": after["recommendation"] != before["recommendation"],
        "note": NOTE,
    }
