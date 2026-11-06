"""Hop dong feature v1 - phai trung voi contracts/features-v1.json va mart.application_features_v1."""

FEATURE_VERSION = "application_features_v1"
MODEL_NAME = "logistic_regression_v1"

NUMERIC_FEATURES = [
    "amt_income_total", "amt_credit", "amt_annuity", "credit_income_ratio",
    "age_years", "employment_days",
    "ext_source_1", "ext_source_2", "ext_source_3",
    "previous_application_count", "previous_approved_count",
    "previous_refused_count", "previous_approval_rate",
]
CATEGORICAL_FEATURES = ["income_type", "education_level", "contract_type_name"]
# Thu tu giong contracts/features-v1.json
PREDICTORS = [
    "amt_income_total", "amt_credit", "amt_annuity", "credit_income_ratio",
    "age_years", "employment_days", "income_type", "education_level",
    "contract_type_name", "ext_source_1", "ext_source_2", "ext_source_3",
    "previous_application_count", "previous_approved_count",
    "previous_refused_count", "previous_approval_rate",
]
# Cot tien: log1p trong pipeline de giam lech phai (chi la bien doi xac dinh, khong hoc tu du lieu).
MONEY_FEATURES = ["amt_income_total", "amt_credit", "amt_annuity"]

# Khong bao gio duoc nam trong dau vao cham diem / feature_snapshot.
FORBIDDEN_INPUT_KEYS = {
    "target", "label", "y", "recommendation", "risk_score", "risk_band",
    "risk_probability", "data_source", "etl_run_id",
}
ID_COLUMN = "application_id"
LABEL_COLUMN = "target"

# Cot toi thieu can doc tu CSV (trung APP_FIELDS / PREV_FIELDS cua scripts/database.py).
APP_COLUMNS = [
    "SK_ID_CURR", "TARGET", "NAME_CONTRACT_TYPE", "AMT_INCOME_TOTAL", "AMT_CREDIT",
    "AMT_ANNUITY", "DAYS_BIRTH", "DAYS_EMPLOYED", "NAME_INCOME_TYPE",
    "NAME_EDUCATION_TYPE", "EXT_SOURCE_1", "EXT_SOURCE_2", "EXT_SOURCE_3",
]
PREV_COLUMNS = ["SK_ID_PREV", "SK_ID_CURR", "NAME_CONTRACT_STATUS", "DAYS_DECISION"]

SPLIT_SEED = 42
HOLDOUT_FRACTION = 0.20
VALID_FRACTION = 0.20   # ti le tren TOAN BO du lieu (train = 60%)
