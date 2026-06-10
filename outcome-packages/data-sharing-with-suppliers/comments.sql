-- ============================================================
-- ORDM · Outcome Package · Data Sharing with Suppliers · column comments
-- Version: v1_mvm · Generated: 2026-06-10 · LLM-generated: true · Reviewed: 2026-06-10
-- Column-level documentation for gold_category_growth (Genie / AI-BI / UC).
-- Run AFTER the view exists.
-- ============================================================

COMMENT ON COLUMN ${catalog}.${dss_schema}.gold_category_growth.category IS 'Merchandising category.';
COMMENT ON COLUMN ${catalog}.${dss_schema}.gold_category_growth.fiscal_year IS 'NRF fiscal year.';
COMMENT ON COLUMN ${catalog}.${dss_schema}.gold_category_growth.fiscal_period IS 'NRF 4-5-4 fiscal period (1-12).';
COMMENT ON COLUMN ${catalog}.${dss_schema}.gold_category_growth.category_revenue IS 'Category net revenue in the period.';
COMMENT ON COLUMN ${catalog}.${dss_schema}.gold_category_growth.category_units IS 'Category units sold in the period.';
COMMENT ON COLUMN ${catalog}.${dss_schema}.gold_category_growth.category_margin IS 'Category gross margin (revenue - units x unit_cost).';
COMMENT ON COLUMN ${catalog}.${dss_schema}.gold_category_growth.prior_period_revenue IS 'Revenue in the prior fiscal period (period_index - 1).';
COMMENT ON COLUMN ${catalog}.${dss_schema}.gold_category_growth.delta_revenue IS 'category_revenue - prior_period_revenue (the four effects reconcile to this).';
COMMENT ON COLUMN ${catalog}.${dss_schema}.gold_category_growth.pop_growth_pct IS 'Period-over-period revenue growth %; NULL when no prior period.';
COMMENT ON COLUMN ${catalog}.${dss_schema}.gold_category_growth.prior_year_revenue IS 'Revenue in the same fiscal period last year (period_index - 12).';
COMMENT ON COLUMN ${catalog}.${dss_schema}.gold_category_growth.yoy_growth_pct IS 'Year-over-year revenue growth %; NULL when no prior-year period.';
COMMENT ON COLUMN ${catalog}.${dss_schema}.gold_category_growth.distribution_effect IS 'Delta-revenue from changing the number of product x store selling points.';
COMMENT ON COLUMN ${catalog}.${dss_schema}.gold_category_growth.volume_effect IS 'Delta-revenue from changing units per selling point (depth).';
COMMENT ON COLUMN ${catalog}.${dss_schema}.gold_category_growth.price_effect IS 'Delta-revenue from like-for-like sub-category price change.';
COMMENT ON COLUMN ${catalog}.${dss_schema}.gold_category_growth.mix_effect IS 'Delta-revenue from shifting the sub-category mix.';
COMMENT ON COLUMN ${catalog}.${dss_schema}.gold_category_growth.category_share IS 'category_revenue / total period revenue (sums to ~1 across categories).';
COMMENT ON COLUMN ${catalog}.${dss_schema}.gold_category_growth.promo_contribution IS 'Incremental margin from promotions in the category that period (NULL if the promo view is absent).';
COMMENT ON COLUMN ${catalog}.${dss_schema}.gold_category_growth.value_share_platinum IS 'Share of customer-attributed category revenue from PLATINUM CLV customers.';
COMMENT ON COLUMN ${catalog}.${dss_schema}.gold_category_growth.value_share_gold IS 'Share of customer-attributed category revenue from GOLD CLV customers.';
COMMENT ON COLUMN ${catalog}.${dss_schema}.gold_category_growth.value_share_silver IS 'Share of customer-attributed category revenue from SILVER CLV customers.';
COMMENT ON COLUMN ${catalog}.${dss_schema}.gold_category_growth.value_share_bronze IS 'Share of customer-attributed category revenue from BRONZE CLV customers.';
COMMENT ON COLUMN ${catalog}.${dss_schema}.gold_category_growth.top_supplier_id IS 'Supplier with the largest share of category procurement spend.';
COMMENT ON COLUMN ${catalog}.${dss_schema}.gold_category_growth.supplier_top_share IS 'That supplier share of category procurement spend.';
COMMENT ON COLUMN ${catalog}.${dss_schema}.gold_category_growth.supplier_top_score IS 'That supplier average scorecard composite (NULL if the scorecard is absent).';
