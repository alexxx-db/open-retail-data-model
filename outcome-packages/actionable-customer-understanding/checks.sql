-- ============================================================
-- ORDM · Outcome Package · Actionable Customer Understanding · data-quality checks
-- Version: v1_mvm · Generated: 2026-06-09 · LLM-generated: true · Reviewed: 2026-06-09
-- Each assertion SELECTs violating rows; 0 rows = PASS. `metric` checks report
-- a value and never fail the run.
-- ============================================================

-- check: ltv_no_raw_pii | severity: error
-- The gold view must NOT expose raw PII columns (loyalty/household ids, names,
-- dob). PII stays in the governed dimension; the view keys on the surrogate.
SELECT column_name
FROM ${catalog}.information_schema.columns
WHERE table_schema = '${acu_schema}'
  AND table_name = 'gold_customer_ltv'
  AND column_name IN ('loyalty_id', 'household_id', 'first_name', 'middle_name',
                      'last_name', 'date_of_birth', 'name_prefix', 'name_suffix', 'contact_value');

-- check: ltv_rfm_components_range | severity: error
SELECT * FROM ${catalog}.${acu_schema}.gold_customer_ltv
WHERE r_score NOT BETWEEN 1 AND 5 OR f_score NOT BETWEEN 1 AND 5 OR m_score NOT BETWEEN 1 AND 5;

-- check: ltv_value_tier_domain | severity: error
SELECT * FROM ${catalog}.${acu_schema}.gold_customer_ltv
WHERE value_tier NOT IN ('PLATINUM', 'GOLD', 'SILVER', 'BRONZE');

-- check: ltv_predicted_clv_nonnegative | severity: error
SELECT * FROM ${catalog}.${acu_schema}.gold_customer_ltv
WHERE predicted_clv < 0;

-- check: ltv_customer_fk_orphan | severity: error
SELECT g.* FROM ${catalog}.${acu_schema}.gold_customer_ltv g
LEFT JOIN ${catalog}.${customer_schema}.profile p ON g.profile_sk = p.profile_sk
WHERE p.profile_sk IS NULL;

-- check: ltv_rowcount | severity: metric
SELECT COUNT(*) AS ltv_rows FROM ${catalog}.${acu_schema}.gold_customer_ltv;

-- check: ltv_value_tier_spread | severity: metric
-- Reported only: distinct value tiers present (4 = full spread).
SELECT COUNT(DISTINCT value_tier) AS distinct_tiers FROM ${catalog}.${acu_schema}.gold_customer_ltv;

-- check: ltv_predicted_clv_null_rate | severity: metric
SELECT ROUND(AVG(CASE WHEN predicted_clv IS NULL THEN 1.0 ELSE 0.0 END), 4) AS predicted_null_rate
FROM ${catalog}.${acu_schema}.gold_customer_ltv;
