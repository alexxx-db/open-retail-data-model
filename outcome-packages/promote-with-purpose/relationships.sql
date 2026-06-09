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
