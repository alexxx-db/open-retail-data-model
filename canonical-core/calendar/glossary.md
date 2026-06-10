# Calendar Domain — Business Glossary

> Status: 🟡 In progress (v1_mvm) · Last reviewed: 2026-06-09

| Term | Definition |
|---|---|
| **Fiscal calendar** (`fiscal_calendar`) | NRF 4-5-4 retail fiscal calendar at day grain. The single source for all retail-week / period / quarter logic — never derive retail weeks from raw dates. |
| **NRF 4-5-4** | Retail calendar standard: each fiscal quarter has three periods of 4, 5, and 4 weeks (13 weeks/quarter, 52 weeks/year); weeks start on Sunday. |
| **`fiscal_week_id`** | Week identifier `fiscal_year * 100 + fiscal_week` (e.g. `202614`). The week-level join key. |
| **`fiscal_week_index`** | Globally monotonic week counter across the whole calendar; used for trailing N-week windows (e.g. the promotion baseline) that must cross fiscal-year boundaries. |
| **FX rate** (`fx_rate`) | Daily `from_currency_code -> to_currency_code` exchange rate (`rate`); the conversion reference for currency normalization. `to_currency_code` is always the reporting **base currency**, and a self-rate row (`from = to`, `rate = 1`) exists per date. `to_base(amount) = amount * rate`. |
| **Reporting / base currency** | The single currency (`base_currency`, e.g. `USD`) in which the canonical core stores **all** monetary columns. Amounts are normalized at ingest, so `currency_code` is constant across every fact/dim and gold aggregations (`SUM`) are single-currency and correct by construction. |
| **`transaction_currency_code`** | The original currency an amount was sourced/transacted in, kept for lineage only. Never used in arithmetic; reconcile to source via `fx_rate`. |

Type 1 (static reference). Surrogate `calendar_sk`; `date_key` is the day join key. `fx_rate` shares the calendar schema (surrogate `fx_rate_sk`).
