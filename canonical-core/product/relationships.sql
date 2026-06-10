-- ============================================================
-- ORDM · Canonical Core · Product domain · relationships
-- Version: v1_mvm · Generated: 2026-06-10 · LLM-generated: true · Reviewed: 2026-06-10
-- ============================================================

-- ------------------------------------------------------------
-- Logical relationship on a non-PK key (NOT a declared UC FK):
--   product_price.product_id -> product.product_id (business key)
-- Read price AS OF a date from product_price; the product dim carries the
-- current list/cost snapshot.
-- ------------------------------------------------------------

-- Enum / state-domain CHECK constraints (H-10; lists match the column comments).
ALTER TABLE ${catalog}.${product_schema}.product
  ADD CONSTRAINT chk_product_status
  CHECK (product_status IS NULL OR product_status IN ('active', 'inactive', 'discontinued'));
ALTER TABLE ${catalog}.${product_schema}.product
  ADD CONSTRAINT chk_product_unit_of_measure
  CHECK (unit_of_measure IS NULL OR unit_of_measure IN ('each', 'kg', 'g', 'l', 'ml', 'pack'));

ALTER TABLE ${catalog}.${product_schema}.product_price
  ADD CONSTRAINT chk_product_price_type
  CHECK (price_type IN ('list', 'cost', 'promotional', 'contract'));
ALTER TABLE ${catalog}.${product_schema}.product_price
  ADD CONSTRAINT chk_product_price_amount_nonnegative
  CHECK (amount IS NULL OR amount >= 0);
