# Outcome Package — Data Sharing with Suppliers

> Status: ⚪ Planned · Marketplace listing: planned

## Business outcome

Collaborative **category growth** for joint business planning: per category × fiscal period, the revenue/units/margin, a four-way **growth decomposition** (volume / price / mix / distribution that reconciles to total Δrevenue), category share, and the integrated **promo**, **customer-value** and **supplier** signals — so growth can be analysed with and attributed to suppliers. See [`gold/gold_category_growth.sql`](gold/gold_category_growth.sql) and the placement decision + definitions in [`glossary.md`](glossary.md).

### Category Growth — files

| Layer | Object |
|---|---|
| Gold view | [`gold/gold_category_growth.sql`](gold/gold_category_growth.sql) |
| Data quality | [`checks.sql`](checks.sql) |
| Glossary + Domain Brief | [`glossary.md`](glossary.md) |
| Builds on | `sales`, `product`, `fiscal_calendar`; integrates `gold_promo_roi_by_category`, `gold_customer_ltv`, `gold_supplier_scorecard` (NULL-safe) |

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

_List the canonical-core entities this package depends on. (TODO)_

## Design notes

Follows the ORDM [data model principles](../../docs/data-model-principles.md).
