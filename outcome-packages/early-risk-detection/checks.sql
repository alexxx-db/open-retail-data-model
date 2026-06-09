-- ============================================================
-- ORDM · Outcome Package · Early Risk Detection · data-quality checks
-- Version: v1_mvm · Generated: 2026-06-09 · LLM-generated: true · Reviewed: 2026-06-09
-- Each assertion SELECTs violating rows; 0 rows = PASS. `metric` checks report
-- a value and never fail the run.
-- ============================================================

-- check: scorecard_otif_pct_range | severity: error
SELECT * FROM ${catalog}.${risk_schema}.gold_supplier_scorecard
WHERE otif_pct IS NOT NULL AND otif_pct NOT BETWEEN 0 AND 1;

-- check: scorecard_fill_rate_range | severity: error
SELECT * FROM ${catalog}.${risk_schema}.gold_supplier_scorecard
WHERE fill_rate IS NOT NULL AND fill_rate NOT BETWEEN 0 AND 1;

-- check: scorecard_defect_rate_range | severity: error
SELECT * FROM ${catalog}.${risk_schema}.gold_supplier_scorecard
WHERE defect_rate IS NOT NULL AND defect_rate NOT BETWEEN 0 AND 1;

-- check: scorecard_composite_range | severity: error
SELECT * FROM ${catalog}.${risk_schema}.gold_supplier_scorecard
WHERE composite_score IS NOT NULL AND composite_score NOT BETWEEN 0 AND 100;

-- check: scorecard_supplier_fk_orphan | severity: error
SELECT g.* FROM ${catalog}.${risk_schema}.gold_supplier_scorecard g
LEFT JOIN ${catalog}.${supplier_schema}.supplier s ON g.supplier_sk = s.supplier_sk
WHERE s.supplier_sk IS NULL;

-- check: scorecard_rowcount | severity: metric
SELECT COUNT(*) AS scorecard_rows FROM ${catalog}.${risk_schema}.gold_supplier_scorecard;

-- check: scorecard_composite_null_rate | severity: metric
-- Reported only: share of supplier x period rows where the composite is undefined.
SELECT ROUND(AVG(CASE WHEN composite_score IS NULL THEN 1.0 ELSE 0.0 END), 4) AS composite_null_rate
FROM ${catalog}.${risk_schema}.gold_supplier_scorecard;

-- check: scorecard_price_compliance_null_rate | severity: metric
-- Reported only: NULL-rate of the price-compliance KPI (invoice vs contract price).
SELECT ROUND(AVG(CASE WHEN price_compliance_pct IS NULL THEN 1.0 ELSE 0.0 END), 4) AS price_compliance_null_rate
FROM ${catalog}.${risk_schema}.gold_supplier_scorecard;

-- check: scorecard_composite_spread | severity: metric
-- Reported only: spread of composite scores (stdev). > 0 => scores are not all identical.
SELECT ROUND(STDDEV_POP(composite_score), 4) AS composite_stddev
FROM ${catalog}.${risk_schema}.gold_supplier_scorecard;
