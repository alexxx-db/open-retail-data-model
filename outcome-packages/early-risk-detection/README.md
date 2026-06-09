# Outcome Package — Early Risk Detection

> Status: ⚪ Planned · Marketplace listing: planned

## Business outcome

A merchant / supply-chain lead sees a **per-supplier scorecard** — OTIF, fill rate, lead-time variance, defect rate, price compliance — and a **weighted composite score (0–100)** per supplier × fiscal period, refreshed on a rolling NRF 4-5-4 basis. It is the objective input to procurement-risk decisions, and the foundation a downstream risk-detection use case builds on. See [`gold/gold_supplier_scorecard.sql`](gold/gold_supplier_scorecard.sql) and [`glossary.md`](glossary.md).

### Supplier Score & Monitoring — files

| Layer | Object |
|---|---|
| Gold view | [`gold/gold_supplier_scorecard.sql`](gold/gold_supplier_scorecard.sql) |
| Data quality | [`checks.sql`](checks.sql) |
| Glossary | [`glossary.md`](glossary.md) |
| Synthetic data | `synthetic-data/generators/supplier_monitoring.py` |

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

- `supplier` (canonical-core/supplier) — the scored vendors (GS1 GLN, ISO 3166)
- `purchase_order_line` (canonical-core/procurement) — order + receipt + defect + price facts
- `fiscal_calendar` (canonical-core/calendar) — NRF 4-5-4 fiscal period grain
- `product`, `store` (canonical-core) — conformed PO-line dimensions

## Design notes

Follows the ORDM [data model principles](../../docs/data-model-principles.md).
