-- ============================================================
-- ORDM · Canonical Core · Customer domain
-- File: relationships.sql
-- Version: v1_mvm
-- Generated: 2026-06-09
-- LLM-generated: true (maintainer-reviewed before release)
-- Last reviewed: 2026-06-09
-- ============================================================
-- Cross-table relationships for the customer domain. Run AFTER the
-- tables in tables/ exist. Unity Catalog foreign keys are informational
-- (NOT ENFORCED) — they document the model and feed BI/Genie, they do
-- not validate data.
--
-- A UC FK must reference the parent's declared PRIMARY KEY, which here
-- is the surrogate _sk. So declared FKs below reference profile_sk (the
-- version-specific parent reference). Each child also carries the
-- durable profile_id for version-independent ("current") joins.
-- ============================================================

-- profile (1) ──< (N) address / contact / consent
ALTER TABLE ${catalog}.${customer_schema}.address
  ADD CONSTRAINT fk_address_profile
  FOREIGN KEY (profile_sk) REFERENCES ${catalog}.${customer_schema}.profile (profile_sk);

ALTER TABLE ${catalog}.${customer_schema}.contact
  ADD CONSTRAINT fk_contact_profile
  FOREIGN KEY (profile_sk) REFERENCES ${catalog}.${customer_schema}.profile (profile_sk);

ALTER TABLE ${catalog}.${customer_schema}.consent
  ADD CONSTRAINT fk_consent_profile
  FOREIGN KEY (profile_sk) REFERENCES ${catalog}.${customer_schema}.profile (profile_sk);

-- ------------------------------------------------------------
-- Logical relationships on business keys (NOT declared as UC FKs).
-- Under SCD2 the business key is not unique, so it cannot be a UC FK
-- target. These are documented here for modelers and downstream tools;
-- enforce in ETL / quality checks instead.
--
--   account.primary_contact_profile_id  ->  profile.profile_id
--   account.parent_account_id           ->  account.account_id   (self, org hierarchy)
--   address.profile_id                  ->  profile.profile_id   (durable join, is_current = TRUE)
--   contact.profile_id                  ->  profile.profile_id   (durable join, is_current = TRUE)
--   consent.profile_id                  ->  profile.profile_id   (durable join, is_current = TRUE)
-- ------------------------------------------------------------
