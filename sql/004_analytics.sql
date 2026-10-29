-- No multiplication by history or assessment rows.
SELECT count(*) AS application_count, count(target) AS labeled_count,
    count(*) FILTER(WHERE target=1) AS difficulty_count,
    count(*) FILTER(WHERE target=1)::numeric / NULLIF(count(target),0) AS observed_difficulty_rate,
    sum(amt_credit) AS total_application_credit
FROM mart.application_overview_v1;

-- Slice/dice via WHERE; roll-up via GROUPING SETS.
SELECT income_type,contract_type_name,count(*) AS applications,count(target) AS labeled,
    count(*) FILTER(WHERE target=1) AS difficulty_count,
    count(*) FILTER(WHERE target=1)::numeric/NULLIF(count(target),0) AS observed_rate
FROM mart.application_overview_v1
GROUP BY GROUPING SETS ((income_type,contract_type_name),(income_type),());

SELECT age_band,count(*) FROM mart.application_overview_v1 GROUP BY age_band;

-- Pivot counts, source category spelling must match dictionary/data.
SELECT income_type,
    count(*) FILTER(WHERE contract_type_name='Cash loans') AS cash_loans,
    count(*) FILTER(WHERE contract_type_name='Revolving loans') AS revolving_loans
FROM mart.application_overview_v1 GROUP BY income_type;

-- Latest success INSIDE one model, not latest globally then filtered.
-- Future API must bind the chosen model ID, not interpolate user SQL.
WITH chosen_model AS (SELECT 1::bigint AS model_run_id), latest AS (
    SELECT DISTINCT ON (a.application_id) a.* FROM ml.assessments a
    JOIN chosen_model m USING(model_run_id) WHERE a.status='succeeded'
    ORDER BY a.application_id,a.assessed_at DESC,a.assessment_id DESC
)
SELECT application_id,model_run_id,risk_score,risk_band,assessed_at FROM latest;
