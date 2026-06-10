-- ============================================================
-- ORDM · Outcome Package · Actionable Customer Understanding · column comments
-- Version: v1_mvm · Generated: 2026-06-10 · LLM-generated: true · Reviewed: 2026-06-10
-- Column-level documentation for the gold view, so Genie / AI-BI and Unity
-- Catalog surface business definitions. Run AFTER the view exists.
-- ============================================================

COMMENT ON COLUMN ${catalog}.${acu_schema}.gold_customer_ltv.profile_sk IS 'Customer surrogate key (the governed dimension key).';
COMMENT ON COLUMN ${catalog}.${acu_schema}.gold_customer_ltv.profile_id IS 'Durable, pseudonymous customer business key (not raw PII).';
COMMENT ON COLUMN ${catalog}.${acu_schema}.gold_customer_ltv.recency_periods IS 'Fiscal periods (NRF 4-5-4) since the customer last purchased.';
COMMENT ON COLUMN ${catalog}.${acu_schema}.gold_customer_ltv.frequency IS 'Distinct purchase occasions (orders) in the observation window.';
COMMENT ON COLUMN ${catalog}.${acu_schema}.gold_customer_ltv.total_units IS 'Total units purchased.';
COMMENT ON COLUMN ${catalog}.${acu_schema}.gold_customer_ltv.total_spend IS 'Total net spend.';
COMMENT ON COLUMN ${catalog}.${acu_schema}.gold_customer_ltv.avg_order_value IS 'Average net spend per order (total_spend / frequency).';
COMMENT ON COLUMN ${catalog}.${acu_schema}.gold_customer_ltv.historical_clv IS 'Realized gross margin to date; can be negative (a real loss).';
COMMENT ON COLUMN ${catalog}.${acu_schema}.gold_customer_ltv.expected_active_periods IS 'Survival heuristic: GREATEST(0, LEAST(tenure, 12) - recency) forward periods.';
COMMENT ON COLUMN ${catalog}.${acu_schema}.gold_customer_ltv.predicted_clv IS 'Transparent forward estimate = avg_order_margin x freq_per_period x expected_active_periods; clamped >= 0. Heuristic, not an ML model.';
COMMENT ON COLUMN ${catalog}.${acu_schema}.gold_customer_ltv.r_score IS 'Recency quintile 1-5 (5 = most recent).';
COMMENT ON COLUMN ${catalog}.${acu_schema}.gold_customer_ltv.f_score IS 'Frequency quintile 1-5 (5 = most frequent).';
COMMENT ON COLUMN ${catalog}.${acu_schema}.gold_customer_ltv.m_score IS 'Monetary quintile 1-5 (5 = highest spend).';
COMMENT ON COLUMN ${catalog}.${acu_schema}.gold_customer_ltv.rfm_score IS 'Combined RFM cell = 100*R + 10*F + M (111..555).';
COMMENT ON COLUMN ${catalog}.${acu_schema}.gold_customer_ltv.value_tier IS 'historical_clv quartile: PLATINUM / GOLD / SILVER / BRONZE.';
COMMENT ON COLUMN ${catalog}.${acu_schema}.gold_customer_ltv.churn_risk_proxy IS 'Heuristic flag: recency exceeds 2x the typical purchase cadence (tenure / frequency).';
