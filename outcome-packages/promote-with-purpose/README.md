# Outcome Package — Promote with Purpose

> Status: ⚪ Planned · Marketplace listing: planned

## Business outcome

A planner can see every **trade promotion** as a structured entity — its mechanics, funding, product/store scope, planned lift, and the dates and fiscal weeks it ran — and can tie promoted periods back to actual sales. The `promotion` dimension and `promotion_scope` bridge make each deal queryable; the sales fact carries a `promo_sk` so promoted and non-promoted sales are both first-class; and the `gold_trade_promotion` view rolls everything up to promo × product × store × fiscal week with allocated trade spend and a trailing non-promoted **baseline**. This is the clean foundation the **Post-Promotion ROI** use case builds on (baseline vs promoted units → incremental lift vs trade spend).

### Trade Promotion use case — files

| Layer | Object |
|---|---|
| Dimension | [`tables/promotion.sql`](tables/promotion.sql) (SCD2, incl. reserved `NO_PROMO` member) |
| Bridge | [`tables/promotion_scope.sql`](tables/promotion_scope.sql) (product × store coverage) |
| Gold view | [`gold/gold_trade_promotion.sql`](gold/gold_trade_promotion.sql) |
| Relationships | [`relationships.sql`](relationships.sql) |
| Data quality | [`checks.sql`](checks.sql) |
| Glossary | [`glossary.md`](glossary.md) |
| Synthetic data | `synthetic-data/generators/trade_promotion.py` |

## Contents

The layout is the same in every outcome package. One file per table / per metric view keeps parallel work conflict-free.

| Path | Purpose |
|---|---|
| `tables/<table>.sql` | Outcome-specific extension tables (one file each) |
| `metric-views/<metric>.yml` | One UC Metric View per file (measures, dimensions, joins) |
| `agent-metadata.yml` | Synonyms, display names, glossary terms for Genie / AI-BI |
| `sample-queries.sql` | Example queries |
| `notebook-templates/` | Reusable notebooks |

## Builds on (canonical core)

- `product` (canonical-core/product) — promoted items and category attributes
- `store` (canonical-core/store) — promoted locations
- `fiscal_calendar` (canonical-core/calendar) — NRF 4-5-4 retail weeks
- `sales` (canonical-core/transaction) — POS sales, attributed to promotions via `promo_sk`

## Design notes

Follows the ORDM [data model principles](../../docs/data-model-principles.md).
