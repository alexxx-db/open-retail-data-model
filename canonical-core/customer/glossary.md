# Customer Domain — Business Glossary

> Status: 🟡 In progress (v1_mvm) · Last reviewed: 2026-06-09

Business terms for the ORDM canonical-core **Customer** domain (Unity Catalog schema). Definitions are vendor-neutral and follow the ORDM [data model principles](../../docs/data-model-principles.md).

## Tables

| Table | Grain | SCD | Description |
|---|---|---|---|
| `profile` | One version per individual customer | SCD2 | Conformed individual-customer master — identity, locale, retail identifiers, lifecycle. Shared by every outcome package. |
| `address` | One version per customer address | SCD2 | Postal addresses (billing, shipping, home, work). |
| `contact` | One contact point | Operational (current-state) | Reachable contact points — email / phone. Type+value model. |
| `consent` | One version per consent decision | SCD2 (date) + `decision_timestamp` | **Single source of truth** for opt-ins and processing permissions. Date-grained SCD2 like every other master; `decision_timestamp` keeps the legal-grade instant the decision was recorded. |
| `account` | One version per organization | SCD2 | Optional B2B organization account a customer transacts on behalf of. |

## Key concepts

- **Surrogate key (`*_sk`)** — system-generated `BIGINT IDENTITY`, unique per row/version; the declared PRIMARY KEY and the FK/join target for downstream dimensional models.
- **Business / natural key (`*_id`)** — durable, externally-meaningful identifier, stable across SCD2 versions. Use with `is_current = TRUE` for "current state" joins.
- **SCD2 versioning** — `effective_from_date` / `effective_to_date` / `is_current`. A new version is appended when a tracked attribute changes; the prior version is end-dated. No destructive overwrite of master attributes (principle #8).
- **Audit block** — every mutable entity carries `created_timestamp` and `source_updated_timestamp` (source-system instants) alongside `load_timestamp` (pipeline instant). All timestamps are stored in **UTC** (principle #9b).
- **Consent is centralized** — marketing and processing permissions exist **only** in `consent`, never as flags on `profile`/`account`/`contact` (principle #5).
- **No derived columns on masters** — lifetime value, order counts, churn/CLTV scores, last-purchase dates are computed in outcome-package metric views, not stored here (principle #4).

## Selected terms

| Term | Definition |
|---|---|
| **Profile** | A single individual customer (a person), independent of any organization. |
| **Account** | A business/organization entity (B2B). Its `primary_contact_profile_id` points at the individual who is the main contact. |
| **Household** | A grouping of related individuals (`household_id`). PII. |
| **Loyalty ID** | Identifier of the individual within a loyalty/membership program (`loyalty_id`). PII. |
| **Contact point** | One way to reach a customer (an email address or a phone number), typed via `contact_type`. |
| **Consent type** | The activity a consent decision governs (e.g. `marketing_email`, `data_processing`). |
| **Legal basis** | The lawful basis for processing personal data (e.g. `consent`, `contract`, `legitimate_interest`). |

## Standards used

| Concept | Standard |
|---|---|
| Dates / timestamps | ISO 8601 |
| Country codes | ISO 3166-1 alpha-2 (`nationality_country_code`, `address.country_code`) |
| Language codes | ISO 639-1 alpha-2 (`preferred_language_code`) |
| Currency codes | ISO 4217 alpha-3 (`account.currency_code`) |
| Organization location | GS1 GLN (`account.gln`) |

## PII / sensitivity classification

Tagged via `dbx_pii_*` column tags (principle #11; consumed by governance / dbxmetagen):

| Column(s) | Tag |
|---|---|
| `profile.first_name`, `middle_name`, `last_name` | `dbx_pii_name` |
| `profile.date_of_birth` | `dbx_pii_dob` |
| `profile.loyalty_id`, `profile.household_id` | `dbx_pii` |
| `address.address_line_1`, `address_line_2`, `city`, `postal_code` | `dbx_pii_address` |
| `contact.contact_value` | `dbx_pii_email`, `dbx_pii_phone` |
| `account.tax_id`, `account.credit_limit_amount` | `dbx_pii_financial` |

> Per ORDM/RSK calibration: **UPC/SKU are not PII**; **`loyalty_id` and `household_id` are PII**.
