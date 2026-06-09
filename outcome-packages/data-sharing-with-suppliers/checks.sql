-- ============================================================
-- ORDM · Outcome Package · Data Sharing with Suppliers · data-quality checks
-- Version: v1_mvm · Generated: 2026-06-09 · LLM-generated: true · Reviewed: 2026-06-09
-- Each assertion SELECTs violating rows; 0 rows = PASS. `metric` checks report
-- a value and never fail the run.
-- ============================================================

-- check: growth_decomposition_reconciles | severity: error
-- The four effects must sum to delta_revenue within tolerance (when a prior period exists).
SELECT * FROM ${catalog}.${dss_schema}.gold_category_growth
WHERE delta_revenue IS NOT NULL
  AND ABS((distribution_effect + volume_effect + price_effect + mix_effect) - delta_revenue) > 0.01;

-- check: category_share_sums_to_one | severity: error
-- category_share must sum to ~1.0 across categories within each fiscal period.
SELECT fiscal_year, fiscal_period, SUM(category_share) AS share_sum
FROM ${catalog}.${dss_schema}.gold_category_growth
GROUP BY fiscal_year, fiscal_period
HAVING ABS(SUM(category_share) - 1.0) > 0.001;

-- check: growth_pct_null_only_when_prior_absent | severity: error
-- pop_growth_pct may be NULL only when the prior period is absent or zero.
SELECT * FROM ${catalog}.${dss_schema}.gold_category_growth
WHERE pop_growth_pct IS NULL AND prior_period_revenue IS NOT NULL AND prior_period_revenue <> 0;

-- check: category_growth_rowcount | severity: metric
SELECT COUNT(*) AS rows FROM ${catalog}.${dss_schema}.gold_category_growth;

-- check: promo_contribution_null_rate | severity: metric
-- Reported only: NULL-rate of the promo signal (degraded if gold_promo_roi is absent).
SELECT ROUND(AVG(CASE WHEN promo_contribution IS NULL THEN 1.0 ELSE 0.0 END), 4) AS promo_null_rate
FROM ${catalog}.${dss_schema}.gold_category_growth;

-- check: value_mix_null_rate | severity: metric
-- Reported only: NULL-rate of the value-tier-mix signal (degraded if gold_customer_ltv is absent).
SELECT ROUND(AVG(CASE WHEN value_share_platinum IS NULL THEN 1.0 ELSE 0.0 END), 4) AS value_mix_null_rate
FROM ${catalog}.${dss_schema}.gold_category_growth;

-- check: supplier_contribution_null_rate | severity: metric
-- Reported only: NULL-rate of the supplier signal (degraded if procurement/scorecard is absent).
SELECT ROUND(AVG(CASE WHEN top_supplier_id IS NULL THEN 1.0 ELSE 0.0 END), 4) AS supplier_null_rate
FROM ${catalog}.${dss_schema}.gold_category_growth;
