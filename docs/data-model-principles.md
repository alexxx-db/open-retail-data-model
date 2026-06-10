# ORDM data model design principles

These are the design conventions ORDM follows. They keep the model vendor-neutral, consistent, and easy to adopt.

## 0. ORDM scope: both canonical core (silver) and outcome packages (gold), as applicable

ORDM publishes two layers, role-named to avoid medallion-vocabulary disputes:

- **Canonical core** (= Databricks-strict silver) — conformed business entities: Customer, Product, Order, Transaction, Inventory, Store. 3NF, with FKs and MDM-style discipline. Shared primitives every listing builds on.
- **Outcome packages** (= gold + semantic) — the 12 marketplace listings. Each is a bundle: subset of canonical core + UC Metric Views + UC Business Semantics + denormalized analytical views + glossary, all aligned to a specific business outcome (Customer 360, Sponsored Products Placement, etc.).

What ORDM does *not* publish:

- **Source integration** (bronze + source-aligned silver) — customer-specific ingest from SAP/Shopify/POS/etc. Partner-proprietary, varies per customer.
- **Customer extensions** (custom gold) — customer-built KPIs, dashboards, role-based access on top of ORDM.

"As applicable" means not every domain ships both layers in v1 — publish what's mature, expand iteratively. A domain might launch with canonical core only, or with a single outcome package only, depending on partner readiness.

## 1. Vendor-neutral by construction

- No vendor names in column comments. Replace `Informatica MDM` → *"the customer master data system"*, `Salesforce Commerce Cloud` → *"the e-commerce platform"*, etc.
- Enum constraints only for *type categories* (`payment_method_type ∈ {credit_card, debit_card, wallet, gift_card, store_credit, bnpl}`), not specific brands/providers.
- `card_brand`, `wallet_provider`, `bnpl_provider` are free `STRING` with a comment listing "common values include…".
- **No example brands** ("Nike" etc.) in comments.

## 2. Shared common layer + pillar-specific extensions (Rob Saker's principle)

The 12 outcome pillars are not 12 data domains. The architecture is:

- **Shared common layer**: Customer, Product, Location, Transaction defined *once*.
- **Pillar-specific extensions**: only the tables and metric views unique to that outcome (e.g., foot-traffic for *Connected Store Signals*, sponsored-placement for *Commerce Media Networks*).

So *Customer 360* (Unified Customer View pillar) and *Shopping Assistant* (Agentic Commerce pillar) both reference the *same* Customer entity — no redefinitions, no drift across listings.

## 3. Truly minimum-viable in MVM

Customer = `profile` + `address` + `contact` + `consent` (+ optional `account` for B2B). Not 10 tables and 335 columns.

The Google Retail Data Model covers customer in ~60 attributes. ARTS ODM 7.3 covers it in ~80. ORDM MVM target is in the same range, not the 335-column union of every vendor's opinions.

## 4. No derived columns on master tables

Master entities (`profile`, `account`, `product`) do not store:
- Aggregates (`total_lifetime_orders`, `outstanding_balance`, `last_purchase_date`)
- Predictive scores (`cltv_score`, `cac_amount`, `churn_risk_score`)
- Survey results (`nps_score`)

These belong in **metric views** or **materialized views**. Putting them on master tables creates write amplification and consistency bugs.

## 5. One source of truth per concept (no duplication)

The original schema has marketing consent expressed in **four** places (`profile`, `account`, `contact`, `consent`). ORDM:

- Consent lives in the `consent` table only.
- Communication preferences live in a separate `communication_preference` table.
- No redundant opt-in flags on master entities.

## 6. No god-tables

Each table represents one coherent business concept. The original `preference` table conflated 12 unrelated concepts (communication channel, dietary restriction, brand preference, delivery preference, payment preference, …) — that's an EAV anti-pattern. ORDM splits these into focused tables with a small `customer_attribute(key, value)` extensibility table for the long tail.

## 7. Domains organized by entity, not by use case

- `customer` domain = identity / contact / address / consent.
- `service` domain = `service_case` and related (NOT inside customer).
- `marketing` or `customer_intelligence` domain = segments, memberships, scores.
- `privacy` or `compliance` domain = `consent` (regulator-facing, not identity).

## 8. Consistent SCD pattern for master tables

Master entities (`profile`, `account`, `address`, `product`, `store`, `supplier`, `promotion`, `consent`) use SCD Type 2:
- `effective_from_date`, `effective_to_date`, `is_current` — **date-grained on every master** (one consistent SCD2 temporal type). Where instant precision is legally required (e.g. `consent`), keep a *separate* `*_timestamp` column (`decision_timestamp`) rather than promoting the SCD2 window to TIMESTAMP.
- No destructive update via `last_modified_timestamp` only

Operational entities can use destructive update if history is captured elsewhere (e.g., transaction log).

### 8a. Standard audit block on mutable entities

Every mutable entity (SCD2 masters + operational tables like `contact`/`consent`) carries the same audit block: `created_timestamp` and `source_updated_timestamp` (source-system instants) alongside `record_source` and `load_timestamp` (the pipeline instant). One shape everywhere — no per-table ad-hoc `updated_timestamp`.

## 9. Strict typing — no `STRING` smuggling

Numeric columns are typed numeric:
- Counts and ranks → `INT`
- Scores in defined range → `INT` or `DECIMAL` (whichever fits)
- Dates → `DATE`, timestamps → `TIMESTAMP`
- Currency → `DECIMAL(18,2)` (not `STRING`)

Comments saying "stored as string for flexibility" are a red flag.

### 9a. Single reporting currency in the canonical core

Every monetary column is stored in **one reporting/base currency** (`base_currency`, e.g. `USD`), normalized at ingest. `currency_code` records that base currency and is **constant** across every fact and dimension; `transaction_currency_code` preserves the original currency for lineage only and is never used in arithmetic. The conversion reference is the conformed `calendar.fx_rate` dimension (`to_base(amount) = amount * rate`).

The point: gold aggregations (`SUM(net_revenue)`, `revenue - units * unit_cost`, …) are correct **by construction** — they never sum or subtract mixed currencies. A DQ check on each fact (`*_single_reporting_currency`) enforces the invariant. Storing facts in their original transaction currency and converting in gold is the anti-pattern this avoids.

### 9b. Timestamps are stored in UTC

Every `TIMESTAMP` column holds an instant in **UTC** (the storage contract; column comments say so). Business *dates* (`*_date`, `date_key`) are local calendar dates by design — they are `DATE`, not `TIMESTAMP`. Note that Databricks `TIMESTAMP` is session-zone-aware; adopters reading/writing across zones should set the session to UTC (or use `TIMESTAMP_NTZ` for zone-free wall-clock instants). The rule keeps `created_timestamp` / `source_updated_timestamp` / `load_timestamp` comparable across sources without per-row zone ambiguity.

### 9c. Boolean naming — `is_*`

All boolean columns use the `is_*` prefix (`is_current`, `is_primary`, `is_verified`, `is_weekend`, `is_holiday`). No `*_flag` suffix or bare adjectives — including the SCD2 current-version indicator, which is `is_current` (not `current_flag`).

## 10. Cross-domain FK direction follows dependency

Customer is a *root* entity. Almost nothing should be FK'd *out* of customer into other domains.

- `consent.promo_campaign_id → promotion.promo_campaign` ❌ (consent records exist independently of campaigns)
- `transaction.profile_id → customer.profile` ✅ (transactions depend on customer)

The original schema has 49 cross-domain FKs out of customer — an LLM optimistically adding plausible joins. ORDM keeps customer thin.

## 11. PII isolation for role-based access

PII tags (`dbx_pii_name`, `dbx_pii_phone`, `dbx_pii_email`, `dbx_pii_dob`, `dbx_pii_address`, `dbx_pii_financial`) are useful. Keep them.

Consider a `profile_core` (no PII) + `profile_pii` (separate, restricted-access) split so non-PII workloads stay out of PII scope.

## 12. PCI DSS scope isolation

Tokenized payment instruments live in a `finance.payment_instrument` schema (vault-adjacent), not on customer master. Storing `cardholder_name` on customer puts the customer schema in PCI scope — bad.

## 13. Provenance + version discipline

Every schema file has a header:
- Domain, version (v1_mvm or v1_ecm), generation date
- LLM-generated flag (for transparency to downstream adopters)
- Last reviewed date

This is a quality signal that's missing from auto-generated schemas. Adopters need to know what they're using.

## 14. Catalog naming discipline

MVM and ECM target *different* catalogs (`retail_mvm` vs. `retail_ecm`). Don't have both schema files writing into the same catalog — deployment order then matters and bugs ensue.

## 15. License + NOTICE at every layer

- Every published schema file has a comment header referencing the LICENSE.
- NOTICE file declares: independently authored, not redistribution of ARTS/OMG content, inspired by industry references including ARTS ODM and Google's `retail-data-model`.

---

## What good looks like

A reference data model is the **intersection** of universal concepts, with extensibility hooks for everything else.

The original vibe-modelled schema is the **union** of every retailer's opinions — which is exactly the opposite of what's useful. ORDM's job is to invert that.
