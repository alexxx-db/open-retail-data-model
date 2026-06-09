-- ============================================================
-- ORDM · Outcome Package · Promote with Purpose · data-quality checks
-- Version: v1_mvm · Generated: 2026-06-09 · LLM-generated: true · Reviewed: 2026-06-09
-- Each assertion SELECTs violating rows; 0 rows = PASS. `metric` checks
-- report a value and never fail the run.
-- ============================================================

-- ---------- promotion ----------

-- check: promotion_keys_not_null | severity: error
SELECT * FROM ${catalog}.${promo_schema}.promotion
WHERE promo_sk IS NULL OR promo_id IS NULL OR current_flag IS NULL;

-- check: promotion_business_key_unique_current | severity: error
SELECT promo_id, COUNT(*) AS current_versions
FROM ${catalog}.${promo_schema}.promotion
WHERE current_flag = true
GROUP BY promo_id
HAVING COUNT(*) > 1;

-- check: promotion_type_domain | severity: error
SELECT * FROM ${catalog}.${promo_schema}.promotion
WHERE promo_type IS NOT NULL
  AND promo_type NOT IN ('TPR', 'FEATURE', 'DISPLAY', 'FEATURE_AND_DISPLAY', 'BOGO', 'COUPON', 'BUNDLE');

-- check: promotion_funding_type_domain | severity: error
SELECT * FROM ${catalog}.${promo_schema}.promotion
WHERE funding_type IS NOT NULL
  AND funding_type NOT IN ('OFF_INVOICE', 'BILL_BACK', 'SCAN_DOWN', 'LUMP_SUM');

-- check: promotion_funded_by_domain | severity: error
SELECT * FROM ${catalog}.${promo_schema}.promotion
WHERE funded_by IS NOT NULL
  AND funded_by NOT IN ('SUPPLIER', 'RETAILER', 'SHARED');

-- check: promotion_date_order | severity: error
-- End date must not precede start date.
SELECT * FROM ${catalog}.${promo_schema}.promotion
WHERE start_date IS NOT NULL AND end_date IS NOT NULL AND end_date < start_date;

-- check: promotion_supplier_share_range | severity: error
-- supplier_share_pct must be within [0, 100] when present.
SELECT * FROM ${catalog}.${promo_schema}.promotion
WHERE supplier_share_pct IS NOT NULL AND (supplier_share_pct < 0 OR supplier_share_pct > 100);

-- check: promotion_supplier_share_required | severity: error
-- supplier_share_pct is mandatory unless the retailer funds the whole promotion.
SELECT * FROM ${catalog}.${promo_schema}.promotion
WHERE funded_by IS NOT NULL AND funded_by <> 'RETAILER' AND supplier_share_pct IS NULL;

-- ---------- promotion_scope ----------

-- check: scope_keys_not_null | severity: error
SELECT * FROM ${catalog}.${promo_schema}.promotion_scope
WHERE scope_sk IS NULL OR scope_id IS NULL OR promo_id IS NULL
   OR product_id IS NULL OR store_id IS NULL;

-- check: scope_promotion_fk_orphan | severity: error
SELECT sc.* FROM ${catalog}.${promo_schema}.promotion_scope sc
LEFT JOIN ${catalog}.${promo_schema}.promotion p ON sc.promo_sk = p.promo_sk
WHERE sc.promo_sk IS NOT NULL AND p.promo_sk IS NULL;

-- check: scope_product_fk_orphan | severity: error
SELECT sc.* FROM ${catalog}.${promo_schema}.promotion_scope sc
LEFT JOIN ${catalog}.${product_schema}.product p ON sc.product_sk = p.product_sk
WHERE sc.product_sk IS NOT NULL AND p.product_sk IS NULL;

-- check: scope_store_fk_orphan | severity: error
SELECT sc.* FROM ${catalog}.${promo_schema}.promotion_scope sc
LEFT JOIN ${catalog}.${store_schema}.store st ON sc.store_sk = st.store_sk
WHERE sc.store_sk IS NOT NULL AND st.store_sk IS NULL;

-- ---------- gold_trade_promotion ----------

-- check: gold_trade_promotion_rowcount | severity: metric
-- Reported only: number of promo x product x store x week rows in the gold view.
SELECT COUNT(*) AS gold_rows FROM ${catalog}.${promo_schema}.gold_trade_promotion;

-- check: gold_baseline_units_null_rate | severity: metric
-- Reported only (never a failure): share of gold rows whose baseline_units is
-- NULL because fewer than 4 trailing non-promoted weeks were available.
SELECT ROUND(AVG(CASE WHEN baseline_units IS NULL THEN 1.0 ELSE 0.0 END), 4) AS baseline_null_rate
FROM ${catalog}.${promo_schema}.gold_trade_promotion;
