-- ============================================================
-- ORDM · Outcome Package · Early Risk Detection · column comments
-- Version: v1_mvm · Generated: 2026-06-10 · LLM-generated: true · Reviewed: 2026-06-10
-- Column-level documentation for the gold views (Genie / AI-BI / UC metadata).
-- Run AFTER the views exist.
-- ============================================================

-- gold_supplier_scorecard
COMMENT ON COLUMN ${catalog}.${risk_schema}.gold_supplier_scorecard.supplier_sk IS 'Supplier surrogate key.';
COMMENT ON COLUMN ${catalog}.${risk_schema}.gold_supplier_scorecard.supplier_id IS 'Durable supplier business key.';
COMMENT ON COLUMN ${catalog}.${risk_schema}.gold_supplier_scorecard.supplier_name IS 'Supplier name.';
COMMENT ON COLUMN ${catalog}.${risk_schema}.gold_supplier_scorecard.country_code IS 'Supplier country, ISO 3166-1 alpha-2.';
COMMENT ON COLUMN ${catalog}.${risk_schema}.gold_supplier_scorecard.fiscal_year IS 'NRF fiscal year.';
COMMENT ON COLUMN ${catalog}.${risk_schema}.gold_supplier_scorecard.fiscal_period IS 'NRF 4-5-4 fiscal period (1-12).';
COMMENT ON COLUMN ${catalog}.${risk_schema}.gold_supplier_scorecard.order_lines IS 'Order lines in the period (OTIF / price-compliance denominator).';
COMMENT ON COLUMN ${catalog}.${risk_schema}.gold_supplier_scorecard.otif_pct IS 'On-Time In-Full rate: lines on time AND in full / total lines.';
COMMENT ON COLUMN ${catalog}.${risk_schema}.gold_supplier_scorecard.fill_rate IS 'SUM(received_qty) / SUM(ordered_qty).';
COMMENT ON COLUMN ${catalog}.${risk_schema}.gold_supplier_scorecard.avg_lead_time_days IS 'Mean (actual_delivery_date - order_date) over delivered lines.';
COMMENT ON COLUMN ${catalog}.${risk_schema}.gold_supplier_scorecard.lead_time_variance IS 'Population variance (var_pop) of lead time; higher = less reliable.';
COMMENT ON COLUMN ${catalog}.${risk_schema}.gold_supplier_scorecard.defect_rate IS '(defective + returned units) / received units.';
COMMENT ON COLUMN ${catalog}.${risk_schema}.gold_supplier_scorecard.price_compliance_pct IS 'Share of lines invoiced at or below contract price.';
COMMENT ON COLUMN ${catalog}.${risk_schema}.gold_supplier_scorecard.composite_score IS 'Weighted 0-100 score: OTIF 35, fill 25, lead-time reliability 20, defect 15, price 5.';

-- gold_procurement_risk
COMMENT ON COLUMN ${catalog}.${risk_schema}.gold_procurement_risk.supplier_sk IS 'Supplier surrogate key.';
COMMENT ON COLUMN ${catalog}.${risk_schema}.gold_procurement_risk.supplier_id IS 'Durable supplier business key.';
COMMENT ON COLUMN ${catalog}.${risk_schema}.gold_procurement_risk.supplier_name IS 'Supplier name.';
COMMENT ON COLUMN ${catalog}.${risk_schema}.gold_procurement_risk.country_code IS 'Supplier country, ISO 3166-1 alpha-2.';
COMMENT ON COLUMN ${catalog}.${risk_schema}.gold_procurement_risk.composite_current IS 'Current-period scorecard composite (0-100).';
COMMENT ON COLUMN ${catalog}.${risk_schema}.gold_procurement_risk.performance_risk IS 'Risk from current performance = 100 - composite_current (0-100).';
COMMENT ON COLUMN ${catalog}.${risk_schema}.gold_procurement_risk.trend_risk IS 'Risk from deterioration over the trailing 4 periods (0-100); fires even with an OK current score.';
COMMENT ON COLUMN ${catalog}.${risk_schema}.gold_procurement_risk.concentration_risk IS '100 x concentration_hhi.';
COMMENT ON COLUMN ${catalog}.${risk_schema}.gold_procurement_risk.concentration_hhi IS 'Spend-weighted avg category Herfindahl index, fractional [0,1].';
COMMENT ON COLUMN ${catalog}.${risk_schema}.gold_procurement_risk.single_source_flag IS 'TRUE if the supplier is the sole source of >= 1 SKU.';
COMMENT ON COLUMN ${catalog}.${risk_schema}.gold_procurement_risk.single_sourced_sku_count IS 'Number of SKUs sole-sourced by this supplier.';
COMMENT ON COLUMN ${catalog}.${risk_schema}.gold_procurement_risk.geo_risk IS '100 x the largest single-country spend share among the supplier categories (own country).';
COMMENT ON COLUMN ${catalog}.${risk_schema}.gold_procurement_risk.geo_concentration_flag IS 'TRUE if that country share exceeds 0.60.';
COMMENT ON COLUMN ${catalog}.${risk_schema}.gold_procurement_risk.risk_score IS 'Weighted blend: performance 25, trend 30, concentration 20, single_source 15, geo 10.';
COMMENT ON COLUMN ${catalog}.${risk_schema}.gold_procurement_risk.risk_tier IS 'LOW / MEDIUM / HIGH / CRITICAL; single-source or steep trend escalate to at least HIGH.';
COMMENT ON COLUMN ${catalog}.${risk_schema}.gold_procurement_risk.top_risk_factors IS 'Up to 3 factors with the largest weighted contribution.';
