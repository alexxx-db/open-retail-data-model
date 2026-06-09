# Early Risk Detection — Business Glossary

> Status: 🟡 In progress (v1_mvm) · Last reviewed: 2026-06-09

Business terms for the Supplier Score & Monitoring use case. Vendor-neutral; follows the ORDM [data model principles](../../docs/data-model-principles.md).

## Tables & view

| Object | Grain | Description |
|---|---|---|
| `supplier` (canonical-core) | One version per supplier (SCD2) | Conformed supplier/vendor master; GS1 GLN business key, ISO 3166 country. |
| `purchase_order_line` (canonical-core) | One PO line | Order + receipt/delivery + defect/return + invoice/contract price for one ordered line. |
| `gold_supplier_scorecard` | One supplier × fiscal period | Per-supplier KPIs and the weighted composite score. |
| `gold_procurement_risk` | One supplier (current period) | Risk register: per-factor risk, blended `risk_score`, `risk_tier`, and `top_risk_factors`. |

## KPI terms

| Term | Definition |
|---|---|
| **OTIF** (`otif_pct`) | On-Time In-Full: the share of order lines delivered **both** on time (`actual_delivery_date ≤ promised_date`) **and** in full (`received_qty ≥ ordered_qty × tolerance`, tolerance default 1.0). A line that is late *or* short fails OTIF. |
| **Fill rate** (`fill_rate`) | `SUM(received_qty) / SUM(ordered_qty)` over the period — the proportion of ordered volume actually delivered. |
| **Average lead time** (`avg_lead_time_days`) | Mean of `actual_delivery_date − order_date` (days) over delivered lines. |
| **Lead-time variance** (`lead_time_variance`) | **Population variance** (`var_pop`) of lead time over delivered lines — the consistency of delivery timing. Higher = less reliable. |
| **Defect rate** (`defect_rate`) | `(defective + returned units) / received units` — quality of what arrived. |
| **Price compliance** (`price_compliance_pct`) | Share of lines invoiced at or below the contract price (`unit_price ≤ contract_price`). |
| **Composite supplier score** (`composite_score`) | A single 0–100 score combining the KPIs (see weighting). The objective input to procurement-risk decisions. |

## Weighting scheme & normalization

Each KPI is normalized to a 0–100 sub-score (higher = better) **before** weighting; the weights live in the view's `w` CTE (surfaced, not buried) and sum to 100:

| KPI | Weight | Normalization (0–100, higher better) |
|---|---|---|
| OTIF | **35** | `otif_pct × 100` |
| Fill rate | **25** | `min(fill_rate, 1) × 100` |
| Lead-time reliability | **20** | `100 × max(0, 1 − lead_time_variance / VAR_CAP)`, `VAR_CAP = 25` days² |
| Defect | **15** | `100 × max(0, 1 − defect_rate / DEFECT_CAP)`, `DEFECT_CAP = 0.10` |
| Price compliance | **5** | `price_compliance_pct × 100` |

`composite_score = Σ(weight × sub-score) / Σ(weight)` (Σ weight = 100), so it is a 0–100 weighted average. `composite_score` is NULL only when a component KPI is undefined for that supplier × period (surfaced as a DQ metric, never a failure). Weights and caps are configurable in one documented place (the `w` CTE).

## Procurement risk terms (`gold_procurement_risk`)

| Term | Definition |
|---|---|
| **Procurement risk** | Where procurement is exposed — not just a low scorecard, but deteriorating trend, single-source dependence, and spend/geographic concentration — blended into a tiered `risk_score` so the team can triage. |
| **Trend risk** | Deterioration in `composite_score` over the trailing **K = 4** fiscal periods (configurable). `trend_delta = composite_current − mean(composite over the prior K periods)`; only declines count: `trend_risk = 100 × min(max(−trend_delta / 30, 0), 1)`. A falling supplier surfaces even when its current score is still acceptable. |
| **Concentration / HHI** | Supplier-spend concentration within a category, via the **Herfindahl–Hirschman Index** = Σ(supplier spend share²) per category. **FRACTIONAL [0,1]** convention (1 = single supplier). A supplier's `concentration_hhi` is its spend-weighted average category HHI; `concentration_risk = 100 × concentration_hhi`. |
| **Single source** | `single_source_flag` is TRUE when the supplier is the **sole** source of ≥ 1 SKU; `single_sourced_sku_count` exposes how many. A single point of failure in supply. |
| **Geo risk** | `geo_risk = 100 ×` the largest share the supplier's own country holds of any category it serves; `geo_concentration_flag` when that exceeds the **0.60** threshold — geographic single-country dependence. |
| **Risk score** | Weighted blend (weights in the view's `w` CTE, sum to 100): **performance 25, trend 30, concentration 20, single_source 15, geo 10**. |
| **Risk tier** | `LOW` (< 25), `MEDIUM` (< 50), `HIGH` (< 75), `CRITICAL` (≥ 75) on `risk_score`, **with two escalators**: `single_source_flag` OR a steep trend (`trend_risk ≥ 70`) force at least **HIGH**, so those exposures always surface for triage. |
| **Top risk factors** | The up-to-3 factors with the largest weighted contribution to `risk_score`, so the register explains itself. |
