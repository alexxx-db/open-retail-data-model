# Actionable Customer Understanding — Business Glossary

> Status: 🟡 In progress (v1_mvm) · Last reviewed: 2026-06-09

Business terms for the Customer Lifetime Value use case. Vendor-neutral; follows the ORDM [data model principles](../../docs/data-model-principles.md).

## Tables & view

| Object | Grain | Description |
|---|---|---|
| `customer_order_line` (canonical-core) | One customer × order × product line | Customer-attributed purchases (the base for per-customer value). |
| `gold_customer_ltv` | One customer (by surrogate) | Historical + predicted CLV, RFM segmentation, value tiers. Keys on the surrogate; **no raw PII**. |

## Terms

| Term | Definition |
|---|---|
| **CLV — historical** (`historical_clv`) | Total **realized gross margin** to date: `SUM(net_amount − units × unit_cost)`. Can be negative (a real loss). |
| **CLV — predicted** (`predicted_clv`) | A transparent forward estimate, **NOT an ML model**: `avg_order_margin × frequency_per_period × expected_active_periods`, clamped to ≥ 0. `expected_active_periods = GREATEST(0, LEAST(tenure_periods, HORIZON_CAP=12) − recency_periods)` — loyalty (tenure) extends the horizon, recency shrinks it. A **heuristic starter metric**; if/when an MLflow model exists it can replace this (follow-up, not pulled into the view). |
| **Recency** (`recency_periods`) | Fiscal periods (NRF 4-5-4) since the customer's last order. |
| **Frequency** (`frequency`) | Distinct purchase occasions (`order_id`) in the observation window. |
| **Monetary** (`total_spend`, `avg_order_value`) | Total net spend and spend per order. |
| **RFM** (`r_score`, `f_score`, `m_score`, `rfm_score`) | Quintile (1–5) of Recency, Frequency, Monetary via `NTILE(5)` over the population (boundaries = 20/40/60/80th percentiles). **5 = best** (most recent / frequent / highest spend). `rfm_score = 100·R + 10·F + M` (classic 111–555 cell). |
| **Value tier** (`value_tier`) | `historical_clv` quartiles (`NTILE(4)`): **PLATINUM** (top) / **GOLD** / **SILVER** / **BRONZE** (bottom). |
| **Churn-risk proxy** (`churn_risk_proxy`) | Heuristic flag: recency > 2.0 × the customer's own average cadence (`tenure_periods / frequency`). Clearly a proxy, not a model. |

## PII handling

The view keys on the customer **surrogate** (`profile_sk`) plus the pseudonymous business key `profile_id`. Raw PII — `loyalty_id`, `household_id`, names, date of birth — is **never** carried here; it stays in the governed `profile` dimension (tagged `dbx_pii_*`). A DQ check (`ltv_no_raw_pii`) and a test assert PII absence on the gold schema.
