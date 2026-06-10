-- ============================================================
-- ORDM · Outcome Package · Promote with Purpose
-- File: relationships.sql
-- Version: v1_mvm
-- Generated: 2026-06-09
-- LLM-generated: true (maintainer-reviewed before release)
-- Last reviewed: 2026-06-09
-- ============================================================
-- Relationships for the promotion structures. UC foreign keys are
-- informational (NOT ENFORCED) and reference the parent surrogate PK.
-- Run AFTER promotion, promotion_scope, product and store exist.
-- ============================================================

-- promotion_scope -> promotion / product / store (surrogate FKs)
ALTER TABLE ${catalog}.${promo_schema}.promotion_scope
  ADD CONSTRAINT fk_scope_promotion
  FOREIGN KEY (promo_sk) REFERENCES ${catalog}.${promo_schema}.promotion (promo_sk);

ALTER TABLE ${catalog}.${promo_schema}.promotion_scope
  ADD CONSTRAINT fk_scope_product
  FOREIGN KEY (product_sk) REFERENCES ${catalog}.${product_schema}.product (product_sk);

ALTER TABLE ${catalog}.${promo_schema}.promotion_scope
  ADD CONSTRAINT fk_scope_store
  FOREIGN KEY (store_sk) REFERENCES ${catalog}.${store_schema}.store (store_sk);

-- ------------------------------------------------------------
-- Logical relationships on non-PK keys (NOT declared as UC FKs):
--   promotion.fiscal_week_start -> fiscal_calendar.fiscal_week_id
--   promotion.fiscal_week_end   -> fiscal_calendar.fiscal_week_id
-- (fiscal_calendar PK is calendar_sk; fiscal_week_id is a week-level key.)
-- ------------------------------------------------------------

-- ENFORCED Delta CHECK constraints (always-on; complement the post-hoc DQ checks).
ALTER TABLE ${catalog}.${promo_schema}.promotion
  ADD CONSTRAINT chk_promotion_supplier_share
  CHECK (supplier_share_pct IS NULL OR (supplier_share_pct >= 0 AND supplier_share_pct <= 100));

ALTER TABLE ${catalog}.${promo_schema}.promotion
  ADD CONSTRAINT chk_promotion_spend_nonnegative
  CHECK (planned_trade_spend IS NULL OR planned_trade_spend >= 0);

-- Enum / state-domain CHECK constraints (H-10).
ALTER TABLE ${catalog}.${promo_schema}.promotion
  ADD CONSTRAINT chk_promotion_type
  CHECK (promo_type IS NULL OR promo_type IN ('TPR', 'FEATURE', 'DISPLAY', 'FEATURE_AND_DISPLAY', 'BOGO', 'COUPON', 'BUNDLE'));
ALTER TABLE ${catalog}.${promo_schema}.promotion
  ADD CONSTRAINT chk_promotion_funding_type
  CHECK (funding_type IS NULL OR funding_type IN ('OFF_INVOICE', 'BILL_BACK', 'SCAN_DOWN', 'LUMP_SUM'));
ALTER TABLE ${catalog}.${promo_schema}.promotion
  ADD CONSTRAINT chk_promotion_funded_by
  CHECK (funded_by IS NULL OR funded_by IN ('SUPPLIER', 'RETAILER', 'SHARED'));
