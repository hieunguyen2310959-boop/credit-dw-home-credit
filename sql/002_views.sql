-- Explicit columns; the predictor view intentionally excludes target and metadata.
CREATE OR REPLACE VIEW mart.application_features_v1 AS
SELECT f.application_id, f.amt_income_total, f.amt_credit, f.amt_annuity,
    CASE WHEN f.amt_income_total>0 THEN (f.amt_credit/f.amt_income_total)::double precision END AS credit_income_ratio,
    p.age_years, f.employment_days, p.income_type, p.education_level,
    c.contract_type_name, f.ext_source_1, f.ext_source_2, f.ext_source_3,
    f.previous_application_count, f.previous_approved_count, f.previous_refused_count,
    CASE WHEN f.previous_application_count>0
        THEN f.previous_approved_count::double precision/f.previous_application_count END AS previous_approval_rate
FROM dw.fact_application f
JOIN dw.dim_applicant_profile p USING (applicant_profile_key)
JOIN dw.dim_contract_type c USING (contract_type_key);

CREATE OR REPLACE VIEW mart.application_overview_v1 AS
SELECT f.application_id, f.data_source, f.etl_run_id,
    p.age_years, p.age_band, p.education_level, p.income_type, p.occupation_type,
    p.family_status, p.cnt_children, p.cnt_family_members, p.flag_own_car, p.flag_own_realty,
    c.contract_type_name, f.amt_income_total, f.amt_credit, f.amt_annuity, f.amt_goods_price,
    f.employment_days, f.ext_source_1, f.ext_source_2, f.ext_source_3,
    f.previous_application_count, f.previous_approved_count, f.previous_refused_count,
    CASE WHEN f.previous_application_count>0
        THEN f.previous_approved_count::double precision/f.previous_application_count END AS previous_approval_rate,
    f.target
FROM dw.fact_application f
JOIN dw.dim_applicant_profile p USING (applicant_profile_key)
JOIN dw.dim_contract_type c USING (contract_type_key);

-- Latest SUCCESS, not latest attempt. UI must display its time/model.
CREATE OR REPLACE VIEW mart.latest_assessment_v1 AS
SELECT DISTINCT ON (application_id)
    application_id, assessment_id, model_run_id, assessed_at, risk_score,
    risk_band, recommendation, policy_version, reason_codes
FROM ml.assessments
WHERE status='succeeded'
ORDER BY application_id, assessed_at DESC, assessment_id DESC;
