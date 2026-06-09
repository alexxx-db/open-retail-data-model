# Data Sharing with Suppliers — Business Glossary

> Status: 🟡 In progress (v1_mvm) · Last reviewed: 2026-06-09

Business terms for the Category Growth use case. Vendor-neutral; follows the ORDM [data model principles](../../docs/data-model-principles.md).

## Domain Brief — placement decision (Phase 0)

The Category Growth use case sits in the **Data Sharing with Suppliers** column but reads like merchandising/assortment analytics. Two interpretations were considered:

- **A — collaborative** (chosen): category growth analysed **with and attributed to suppliers** (joint business planning), reusing the supplier scorecard and procurement spend. Matches the column.
- **B — merchandising**: pure internal category performance, independent of supplier.

**Decision: Interpretation A.** It matches the column, no pre-existing category/assortment asset implied B, and the supplier scorecard + procurement data exist to support supplier attribution. `gold_category_growth` therefore exposes a `supplier_contribution` (top supplier's share of category procurement spend + scorecard composite) alongside the merchandising metrics. The merchandising metrics (decomposition, share) stand on their own, so the view is still useful if the supplier signal is absent.

## Object

| Object | Grain | Description |
|---|---|---|
| `gold_category_growth` | One category × fiscal period | Category performance, growth decomposition, and the integrated promo / customer-value / supplier signals. |

## Terms

| Term | Definition |
|---|---|
| **Category growth** | Period-over-period change in category revenue (`delta_revenue = category_revenue − prior_period_revenue`), with `pop_growth_pct` and `yoy_growth_pct` comparing **like fiscal periods** (period_index = `fiscal_year*12 + fiscal_period`; PoP = index−1, YoY = index−12). |
| **Growth decomposition** | `delta_revenue` split into four effects that **reconcile exactly**. With D = distribution points (distinct product × store), q = units/point, P = avg price (subscripts 0=prior, 1=current): **distribution** `= (D1−D0)·q0·P0`, **volume** `= D1·(q1−q0)·P0`, **price** `= U1·Σ_sc w1·(p1−p0)`, **mix** `= U1·Σ_sc (w1−w0)·p0` (over sub-categories sc, w = unit share, p = sub-category avg price). distribution + volume + price + mix = `delta_revenue`. |
| **Distribution effect** | Revenue change from broader/narrower availability (more or fewer product × store selling points). |
| **Volume effect** | Revenue change from selling more/fewer units per selling point, holding price and mix. |
| **Price effect** | Like-for-like price change within sub-categories. |
| **Mix effect** | Revenue change from shifting the sub-category mix toward higher/lower-priced sub-categories at constant sub-category prices. |
| **Category share** | `category_revenue / total revenue` for the period; sums to ~1.0 across categories. |
| **Promo contribution** | Incremental margin from `gold_promo_roi` attributable to the category that period (the share of growth that was promo-driven). NULL if the promo view is absent. |
| **Value-tier mix** | `value_share_platinum/gold/silver/bronze` — the split of customer-attributed category revenue across CLV value tiers (`gold_customer_ltv`), showing whether growth comes from high- or low-value customers. NULL if the LTV view is absent. |
| **Supplier contribution** (Interpretation A) | `top_supplier_id`, `supplier_top_share` (share of category procurement spend) and `supplier_top_score` (its scorecard composite). NULL if procurement/scorecard is absent. |
