-- Single fixed dataset, upsert only; preserve surrogate keys and assessments.
INSERT INTO dw.dim_contract_type(contract_type_name)
SELECT DISTINCT COALESCE(NULLIF(trim("NAME_CONTRACT_TYPE"),''),'Unknown') FROM staging.application
ON CONFLICT DO NOTHING;

INSERT INTO dw.dim_applicant_profile (
    source_application_id,age_years,age_band,education_level,income_type,occupation_type,
    family_status,cnt_children,cnt_family_members,flag_own_car,flag_own_realty)
SELECT "SK_ID_CURR",
    CASE WHEN "DAYS_BIRTH"<0 THEN -"DAYS_BIRTH"::double precision/365.25 END,
    CASE WHEN "DAYS_BIRTH" IS NULL OR "DAYS_BIRTH">=0 THEN 'Unknown'
         WHEN -"DAYS_BIRTH"::double precision/365.25<25 THEN '<25'
         WHEN -"DAYS_BIRTH"::double precision/365.25<40 THEN '25-39'
         WHEN -"DAYS_BIRTH"::double precision/365.25<60 THEN '40-59' ELSE '60+' END,
    COALESCE(NULLIF(trim("NAME_EDUCATION_TYPE"),''),'Unknown'),
    COALESCE(NULLIF(trim("NAME_INCOME_TYPE"),''),'Unknown'),
    COALESCE(NULLIF(trim("OCCUPATION_TYPE"),''),'Unknown'),
    COALESCE(NULLIF(trim("NAME_FAMILY_STATUS"),''),'Unknown'),
    CASE WHEN "CNT_CHILDREN">=0 THEN "CNT_CHILDREN" END,
    CASE WHEN "CNT_FAM_MEMBERS">=0 AND "CNT_FAM_MEMBERS"=trunc("CNT_FAM_MEMBERS")
        AND "CNT_FAM_MEMBERS"<=2147483647 THEN "CNT_FAM_MEMBERS"::integer END,
    CASE "FLAG_OWN_CAR" WHEN 'Y' THEN true WHEN 'N' THEN false END,
    CASE "FLAG_OWN_REALTY" WHEN 'Y' THEN true WHEN 'N' THEN false END
FROM staging.application
ON CONFLICT(source_application_id) DO UPDATE SET
    age_years=excluded.age_years,age_band=excluded.age_band,
    education_level=excluded.education_level,income_type=excluded.income_type,
    occupation_type=excluded.occupation_type,family_status=excluded.family_status,
    cnt_children=excluded.cnt_children,cnt_family_members=excluded.cnt_family_members,
    flag_own_car=excluded.flag_own_car,flag_own_realty=excluded.flag_own_realty;

WITH history AS (
    SELECT "SK_ID_CURR",
        count(*)::integer AS total,
        count(*) FILTER (WHERE "NAME_CONTRACT_STATUS"='Approved')::integer AS approved,
        count(*) FILTER (WHERE "NAME_CONTRACT_STATUS"='Refused')::integer AS refused
    FROM staging.previous_application WHERE "DAYS_DECISION"<=0
    GROUP BY "SK_ID_CURR"
)
INSERT INTO dw.fact_application (
    application_id,applicant_profile_key,contract_type_key,etl_run_id,data_source,
    amt_income_total,amt_credit,amt_annuity,amt_goods_price,employment_days,
    ext_source_1,ext_source_2,ext_source_3,previous_application_count,
    previous_approved_count,previous_refused_count,target)
SELECT a."SK_ID_CURR",p.applicant_profile_key,c.contract_type_key,a.etl_run_id,a.data_source,
    CASE WHEN "AMT_INCOME_TOTAL">=0 THEN "AMT_INCOME_TOTAL" END,
    CASE WHEN "AMT_CREDIT">=0 THEN "AMT_CREDIT" END,
    CASE WHEN "AMT_ANNUITY">=0 THEN "AMT_ANNUITY" END,
    CASE WHEN "AMT_GOODS_PRICE">=0 THEN "AMT_GOODS_PRICE" END,
    CASE WHEN "DAYS_EMPLOYED"<=0 AND "DAYS_EMPLOYED">-2147483648 THEN -"DAYS_EMPLOYED" END,
    CASE WHEN "EXT_SOURCE_1" BETWEEN 0 AND 1 THEN "EXT_SOURCE_1" END,
    CASE WHEN "EXT_SOURCE_2" BETWEEN 0 AND 1 THEN "EXT_SOURCE_2" END,
    CASE WHEN "EXT_SOURCE_3" BETWEEN 0 AND 1 THEN "EXT_SOURCE_3" END,
    COALESCE(h.total,0),COALESCE(h.approved,0),COALESCE(h.refused,0),a."TARGET"
FROM staging.application a
JOIN dw.dim_applicant_profile p ON p.source_application_id=a."SK_ID_CURR"
JOIN dw.dim_contract_type c ON c.contract_type_name=COALESCE(NULLIF(trim(a."NAME_CONTRACT_TYPE"),''),'Unknown')
LEFT JOIN history h ON h."SK_ID_CURR"=a."SK_ID_CURR"
ON CONFLICT(application_id) DO UPDATE SET
    applicant_profile_key=excluded.applicant_profile_key,contract_type_key=excluded.contract_type_key,
    etl_run_id=excluded.etl_run_id,data_source=excluded.data_source,
    amt_income_total=excluded.amt_income_total,amt_credit=excluded.amt_credit,
    amt_annuity=excluded.amt_annuity,amt_goods_price=excluded.amt_goods_price,
    employment_days=excluded.employment_days,ext_source_1=excluded.ext_source_1,
    ext_source_2=excluded.ext_source_2,ext_source_3=excluded.ext_source_3,
    previous_application_count=excluded.previous_application_count,
    previous_approved_count=excluded.previous_approved_count,
    previous_refused_count=excluded.previous_refused_count,target=excluded.target;
