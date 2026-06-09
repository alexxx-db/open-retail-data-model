# Promote with Purpose — Business Glossary

> Status: 🟡 In progress (v1_mvm) · Last reviewed: 2026-06-09

Business terms for the Trade Promotion use case. Vendor-neutral; follows the ORDM [data model principles](../../docs/data-model-principles.md).

## Tables & view

| Object | Grain | Description |
|---|---|---|
| `promotion` | One version per promotion (SCD2) | The trade-promotion dimension — mechanics, funding, planned lift/spend, and the dates/fiscal weeks it ran. Includes the reserved `NO_PROMO` member. |
| `promotion_scope` | One (promotion, product, store) | The product × store coverage of each promotion. |
| `gold_trade_promotion` | One (promotion, product, store, fiscal week) | Consumable view tying promoted sales, allocated trade spend, planned lift, and a trailing-demand baseline together. |

## Terms

| Term | Definition |
|---|---|
| **Trade promotion** | A time-bound, funded offer a retailer runs on specific products in specific stores (e.g. a temporary price reduction or a feature/display) to drive incremental volume. Modeled as one structured `promotion` row with its mechanics, funding, scope, planned lift, and run dates. |
| **Promo mechanics** (`promo_type`) | *How* the promotion is presented to the shopper. Allowed values: `TPR` (temporary price reduction), `FEATURE` (advertised in a flyer/circular), `DISPLAY` (special in-store placement), `FEATURE_AND_DISPLAY`, `BOGO` (buy-one-get-one), `COUPON`, `BUNDLE`. |
| **Funding type** (`funding_type`) | *How the money flows* for the trade deal. Allowed values: `OFF_INVOICE` (deducted on the purchase invoice), `BILL_BACK` (retailer bills the supplier after the fact), `SCAN_DOWN` (per-unit allowance on scanned sales), `LUMP_SUM` (fixed payment). |
| **Funded by** (`funded_by`) | Which party bears the promotional cost: `SUPPLIER`, `RETAILER`, or `SHARED`. When not solely `RETAILER`, `supplier_share_pct` records the supplier's percentage. |
| **Baseline** (`baseline_units`) | The expected non-promoted demand used to judge incremental lift. ORDM defines it as the mean weekly units over the trailing 8 **non-promoted** fiscal weeks for the same product × store; NULL when fewer than 4 such weeks are available. |
| **Planned lift** (`planned_lift_pct`) | The incremental unit uplift, as a percent over baseline, the promotion is expected to deliver. |
| **Trade spend** (`planned_trade_spend`) | The planned promotional investment for the promotion. In `gold_trade_promotion` it is allocated evenly across the promotion's scope (products × stores) and fiscal weeks. |
| **Promotion scope** | The set of products and stores a promotion applies to (`promotion_scope`). |
| **NO_PROMO member** | The reserved `promotion` row (`promo_id = 'NO_PROMO'`) that non-promoted sales are attributed to, so the sales fact always resolves to a real promotion surrogate. |

## Standards

Dates ISO 8601; retail weeks via the NRF 4-5-4 `fiscal_calendar` (never derived from raw dates); product GTIN and store GLN are GS1 identifiers.
