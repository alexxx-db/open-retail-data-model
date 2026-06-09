-- ============================================================
-- ORDM · Canonical Core · Product domain · data-quality checks
-- Version: v1_mvm · Generated: 2026-06-09 · LLM-generated: true · Reviewed: 2026-06-09
-- Each assertion SELECTs violating rows; 0 rows = PASS.
-- ============================================================

-- check: product_keys_not_null | severity: error
SELECT * FROM ${catalog}.${product_schema}.product
WHERE product_sk IS NULL OR product_id IS NULL OR current_flag IS NULL;

-- check: product_business_key_unique_current | severity: error
SELECT product_id, COUNT(*) AS current_versions
FROM ${catalog}.${product_schema}.product
WHERE current_flag = true
GROUP BY product_id
HAVING COUNT(*) > 1;

-- check: product_status_domain | severity: error
SELECT * FROM ${catalog}.${product_schema}.product
WHERE product_status IS NOT NULL
  AND product_status NOT IN ('active', 'inactive', 'discontinued');

-- check: product_uom_domain | severity: error
SELECT * FROM ${catalog}.${product_schema}.product
WHERE unit_of_measure IS NOT NULL
  AND unit_of_measure NOT IN ('each', 'kg', 'g', 'l', 'ml', 'pack');
