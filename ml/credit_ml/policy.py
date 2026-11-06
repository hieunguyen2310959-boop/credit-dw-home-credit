"""Policy DSS mo phong (KHONG phai chinh sach ngan hang that).

Theo ban thao nhom: thieu du lieu quan trong / canh bao cao -> REVIEW; neu khong:
 p >= decline -> DECLINE_SIMULATION; review <= p < decline -> REVIEW; p < review -> APPROVE_SIMULATION.
Nguong 0.25 / 0.10 la gia tri MINH HOA cho nhom duyet; khong lay nguong scorecard 750/600/450.
"Bat thuong" khong dong nghia gian lan.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict

APPROVE, REVIEW, DECLINE = "APPROVE_SIMULATION", "REVIEW", "DECLINE_SIMULATION"
BAND_LOW, BAND_MEDIUM, BAND_HIGH = "LOW", "MEDIUM", "HIGH"


@dataclass(frozen=True)
class PolicyConfig:
    version: str = "policy_v1_illustrative"
    review_threshold: float = 0.10
    decline_threshold: float = 0.25
    critical_fields: tuple = ("amt_income_total", "amt_credit", "age_years")
    ratio_extreme_threshold: float | None = None   # dat tu p99 cua TRAIN (reference_stats)
    refusal_share_alert: float = 0.5               # canh bao thong tin, khong ep REVIEW
    refusal_min_count: int = 3

    def __post_init__(self):
        if not (0.0 < self.review_threshold < self.decline_threshold < 1.0):
            raise ValueError("Can 0 < review_threshold < decline_threshold < 1")

    def to_dict(self):
        d = asdict(self)
        d["critical_fields"] = list(self.critical_fields)
        return d

    @classmethod
    def from_dict(cls, d: dict):
        d = dict(d)
        if "critical_fields" in d:
            d["critical_fields"] = tuple(d["critical_fields"])
        return cls(**d)


def _missing(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v))


def data_alerts(features: dict, cfg: PolicyConfig):
    """Tra ve (alerts, high_severity: bool). Moi alert la dict {code, severity}."""
    alerts = []
    for f in cfg.critical_fields:
        if _missing(features.get(f)):
            alerts.append({"code": f"MISSING_CRITICAL_{f.upper()}", "severity": "high"})
    inc = features.get("amt_income_total")
    if not _missing(inc) and inc <= 0:
        alerts.append({"code": "INCOME_NOT_POSITIVE", "severity": "high"})
    ext = [features.get(f"ext_source_{i}") for i in (1, 2, 3)]
    if all(_missing(v) for v in ext):
        alerts.append({"code": "ALL_EXTERNAL_SCORES_MISSING", "severity": "high"})
    ratio = features.get("credit_income_ratio")
    if cfg.ratio_extreme_threshold is not None and not _missing(ratio) and ratio > cfg.ratio_extreme_threshold:
        alerts.append({"code": "ANOMALY_CREDIT_INCOME_RATIO_EXTREME", "severity": "high"})
    cnt, ref = features.get("previous_application_count"), features.get("previous_refused_count")
    if not _missing(cnt) and not _missing(ref) and cnt >= cfg.refusal_min_count and ref / cnt >= cfg.refusal_share_alert:
        alerts.append({"code": "HIGH_PREVIOUS_REFUSAL_SHARE", "severity": "info"})
    return alerts, any(a["severity"] == "high" for a in alerts)


def risk_band(score: float, cfg: PolicyConfig) -> str:
    if score >= cfg.decline_threshold:
        return BAND_HIGH
    return BAND_MEDIUM if score >= cfg.review_threshold else BAND_LOW


def apply_policy(score: float, features: dict, cfg: PolicyConfig | None = None) -> dict:
    cfg = cfg or PolicyConfig()
    if not (isinstance(score, (int, float)) and math.isfinite(score) and 0.0 <= score <= 1.0):
        raise ValueError("risk_score phai huu han trong [0,1]")
    alerts, high = data_alerts(features, cfg)
    band = risk_band(score, cfg)
    if score >= cfg.decline_threshold:
        base, score_reason = DECLINE, "SCORE_ABOVE_DECLINE_THRESHOLD"
    elif score >= cfg.review_threshold:
        base, score_reason = REVIEW, "SCORE_IN_REVIEW_RANGE"
    else:
        base, score_reason = APPROVE, "SCORE_BELOW_REVIEW_THRESHOLD"
    reasons = [score_reason]
    recommendation = base
    if high:
        recommendation = REVIEW
        reasons.append("DATA_ALERT_FORCES_REVIEW")
    reasons += [a["code"] for a in alerts]
    return {"risk_band": band, "recommendation": recommendation,
            "policy_version": cfg.version, "reason_codes": reasons, "alerts": alerts,
            "score_based_recommendation": base}
