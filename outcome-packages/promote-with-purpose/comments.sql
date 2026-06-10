-- ============================================================
-- ORDM · Outcome Package · Promote with Purpose · column comments
-- Version: v1_mvm · Generated: 2026-06-10 · LLM-generated: true · Reviewed: 2026-06-10
-- Column-level documentation for the consumable gold views (Genie / AI-BI / UC).
-- Run AFTER the views exist.
-- ============================================================

-- gold_promo_roi (one row per promotion)
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_roi.promo_id IS 'Promotion business key.';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_roi.promo_name IS 'Promotion name.';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_roi.promo_type IS 'Mechanic: TPR / FEATURE / DISPLAY / FEATURE_AND_DISPLAY / BOGO / COUPON / BUNDLE.';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_roi.funding_type IS 'OFF_INVOICE / BILL_BACK / SCAN_DOWN / LUMP_SUM.';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_roi.funded_by IS 'SUPPLIER / RETAILER / SHARED.';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_roi.promoted_units IS 'Units sold on promotion.';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_roi.promoted_revenue IS 'Net revenue on promotion.';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_roi.promoted_margin IS 'Gross margin on promotion.';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_roi.baseline_units IS 'Expected non-promoted units over the promo window (trailing-8-week baseline).';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_roi.baseline_revenue IS 'Baseline units valued at normal price.';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_roi.baseline_margin IS 'Baseline units valued at normal margin.';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_roi.incremental_units IS 'promoted_units - baseline_units (NOT clamped; negative = lost volume).';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_roi.incremental_revenue IS 'promoted_revenue - baseline_revenue.';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_roi.incremental_margin IS 'promoted_margin - baseline_margin.';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_roi.trade_spend IS 'Planned trade spend (realized actuals not modelled in v1).';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_roi.roi IS 'incremental_margin / NULLIF(trade_spend, 0); NULL-safe.';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_roi.planned_lift_pct IS 'Planned incremental unit lift %.';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_roi.realized_lift_pct IS '100 x incremental_units / baseline_units.';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_roi.cannibalization_units IS 'Lost units on substitute SKUs (same category, not on promo) during the window.';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_roi.cannibalization_margin IS 'Margin lost to cannibalization.';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_roi.forward_buy_units IS 'Lost units on promoted SKUs in the N weeks after the promo (pantry loading).';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_roi.forward_buy_margin IS 'Margin lost to forward buy.';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_roi.net_incremental_margin IS 'incremental_margin - cannibalization_margin - forward_buy_margin (negative = value destroyed).';

-- gold_promo_performance (operational per-promotion summary)
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_performance.promo_id IS 'Promotion business key.';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_performance.scope_skus IS 'Distinct products in the promotion scope.';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_performance.scope_stores IS 'Distinct stores in the promotion scope.';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_performance.fiscal_weeks IS 'Distinct fiscal weeks the promotion ran.';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_performance.promoted_units IS 'Total promoted units.';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_performance.promoted_revenue IS 'Total promoted net revenue.';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_performance.baseline_units IS 'Total trailing-baseline units over the promo.';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_performance.planned_trade_spend IS 'Total planned trade spend.';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_promo_performance.realized_lift_pct IS '100 x (promoted_units - baseline_units) / baseline_units.';

-- gold_trade_promotion (promo x product x store x fiscal week detail)
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_trade_promotion.fiscal_week_id IS 'Fiscal week identifier (fiscal_year*100 + fiscal_week).';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_trade_promotion.promoted_units IS 'Promoted units for this promo x product x store x week.';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_trade_promotion.promoted_revenue IS 'Promoted net revenue for this cell.';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_trade_promotion.planned_trade_spend IS 'Planned trade spend allocated to this cell (evenly across scope x weeks).';
COMMENT ON COLUMN ${catalog}.${promo_schema}.gold_trade_promotion.baseline_units IS 'Trailing-8-week non-promoted mean units; NULL if < 4 weeks available.';
