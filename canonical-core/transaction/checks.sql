-- ============================================================
-- ORDM · Canonical Core · Transaction domain · data-quality checks
-- Version: v1_mvm · Generated: 2026-06-09 · LLM-generated: true · Reviewed: 2026-06-09
-- Each assertion SELECTs violating rows; 0 rows = PASS. Cross-schema FK
-- checks resolve the sales fact against product / store / promotion.
-- ============================================================

-- check: sales_keys_not_null | severity: error
SELECT * FROM ${catalog}.${transaction_schema}.sales
WHERE sales_sk IS NULL OR sales_id IS NULL OR date_key IS NULL
   OR product_id IS NULL OR store_id IS NULL;

-- check: sales_promo_attribution_present | severity: error
-- Every sale must carry a promotion surrogate (the NO_PROMO member when not promoted).
SELECT * FROM ${catalog}.${transaction_schema}.sales
WHERE promo_sk IS NULL OR promo_id IS NULL;

-- check: sales_promotion_fk_orphan | severity: error
SELECT s.* FROM ${catalog}.${transaction_schema}.sales s
LEFT JOIN ${catalog}.${promo_schema}.promotion p ON s.promo_sk = p.promo_sk
WHERE s.promo_sk IS NOT NULL AND p.promo_sk IS NULL;

-- check: sales_product_fk_orphan | severity: error
SELECT s.* FROM ${catalog}.${transaction_schema}.sales s
LEFT JOIN ${catalog}.${product_schema}.product p ON s.product_sk = p.product_sk
WHERE s.product_sk IS NOT NULL AND p.product_sk IS NULL;

-- check: sales_store_fk_orphan | severity: error
SELECT s.* FROM ${catalog}.${transaction_schema}.sales s
LEFT JOIN ${catalog}.${store_schema}.store st ON s.store_sk = st.store_sk
WHERE s.store_sk IS NOT NULL AND st.store_sk IS NULL;

-- check: sales_nonnegative_measures | severity: warn
SELECT * FROM ${catalog}.${transaction_schema}.sales
WHERE units < 0 OR gross_revenue < 0 OR net_revenue < 0;

-- check: sales_calendar_coverage | severity: error
-- Every selling date must exist in the fiscal calendar (required for week rollups).
SELECT s.date_key FROM ${catalog}.${transaction_schema}.sales s
LEFT JOIN ${catalog}.${calendar_schema}.fiscal_calendar c ON s.date_key = c.date_key
WHERE c.date_key IS NULL
GROUP BY s.date_key;

-- check: sales_single_reporting_currency | severity: error
-- Monetary columns are normalized to the base currency, so currency_code must
-- be constant across the fact (gold SUMs are then single-currency by construction).
SELECT COUNT(DISTINCT currency_code) AS distinct_currencies
FROM ${catalog}.${transaction_schema}.sales
HAVING COUNT(DISTINCT currency_code) > 1;
