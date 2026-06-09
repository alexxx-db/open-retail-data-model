# Outcome Package — Actionable Customer Understanding

> Status: ⚪ Planned · Marketplace listing: planned

## Business outcome

A per-customer **lifetime value** view — historical realized margin plus a transparent forward estimate — with **RFM** segmentation and **value tiers**, consumable by promo targeting and category growth. Built on the **base** dimensional model (`customer_order_line` + `product` margin + the NRF 4-5-4 calendar), **not** the in-progress C360/CDP layer. Keyed on the customer surrogate; no raw PII. See [`gold/gold_customer_ltv.sql`](gold/gold_customer_ltv.sql) and [`glossary.md`](glossary.md).

### Customer Lifetime Value — files

| Layer | Object |
|---|---|
| Gold view | [`gold/gold_customer_ltv.sql`](gold/gold_customer_ltv.sql) |
| Data quality | [`checks.sql`](checks.sql) |
| Glossary | [`glossary.md`](glossary.md) |
| Synthetic data | `synthetic-data/generators/customer_ltv.py` |
| Builds on | `customer_order_line` (canonical-core/order), `profile`, `product`, `fiscal_calendar` |

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
