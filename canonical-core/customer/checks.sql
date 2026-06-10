-- ============================================================
-- ORDM · Canonical Core · Customer domain
-- File: checks.sql  (data-quality assertions)
-- Version: v1_mvm
-- Generated: 2026-06-09
-- LLM-generated: true (maintainer-reviewed before release)
-- Last reviewed: 2026-06-09
-- ============================================================
-- Each assertion SELECTs the VIOLATING rows. 0 rows returned = PASS.
-- Run by data-quality/run_checks.py, which substitutes ${catalog} and
-- ${customer_schema} (= the domain name) and fails the run if any error-severity
-- check returns rows. Format per check:
--   -- check: <name> | severity: error|warn
--   -- <one-line description>
--   <SELECT ...>;   (ends with a semicolon)
-- ============================================================

-- ---------- profile ----------

-- check: profile_keys_not_null | severity: error
-- Surrogate key, business key, SCD2 start date and current flag are mandatory.
SELECT * FROM ${catalog}.${customer_schema}.profile
WHERE profile_sk IS NULL OR profile_id IS NULL
   OR effective_from_date IS NULL OR is_current IS NULL;

-- check: profile_business_key_unique_current | severity: error
-- A business key must resolve to at most one current version.
SELECT profile_id, COUNT(*) AS current_versions
FROM ${catalog}.${customer_schema}.profile
WHERE is_current = true
GROUP BY profile_id
HAVING COUNT(*) > 1;

-- check: profile_customer_status_domain | severity: error
-- customer_status must be within the declared enum.
SELECT * FROM ${catalog}.${customer_schema}.profile
WHERE customer_status IS NOT NULL
  AND customer_status NOT IN ('prospect', 'active', 'inactive', 'closed');

-- check: profile_scd2_current_open | severity: error
-- The current version must have an open (NULL) end date; non-current must be closed.
SELECT * FROM ${catalog}.${customer_schema}.profile
WHERE (is_current = true  AND effective_to_date IS NOT NULL)
   OR (is_current = false AND effective_to_date IS NULL);

-- check: profile_scd2_date_order | severity: error
-- When set, the end date must be strictly after the start date.
SELECT * FROM ${catalog}.${customer_schema}.profile
WHERE effective_to_date IS NOT NULL
  AND effective_to_date <= effective_from_date;

-- ---------- address ----------

-- check: address_keys_not_null | severity: error
SELECT * FROM ${catalog}.${customer_schema}.address
WHERE address_sk IS NULL OR address_id IS NULL OR profile_id IS NULL
   OR is_current IS NULL;

-- check: address_profile_fk_orphan | severity: error
-- Every address must reference an existing profile (by surrogate FK).
SELECT a.* FROM ${catalog}.${customer_schema}.address a
LEFT JOIN ${catalog}.${customer_schema}.profile p ON a.profile_sk = p.profile_sk
WHERE a.profile_sk IS NOT NULL AND p.profile_sk IS NULL;

-- check: address_profile_businesskey_orphan | severity: error
-- The durable owner business key must also exist on profile.
SELECT a.* FROM ${catalog}.${customer_schema}.address a
LEFT JOIN (SELECT DISTINCT profile_id FROM ${catalog}.${customer_schema}.profile) p
  ON a.profile_id = p.profile_id
WHERE p.profile_id IS NULL;

-- check: address_type_domain | severity: error
SELECT * FROM ${catalog}.${customer_schema}.address
WHERE address_type IS NOT NULL
  AND address_type NOT IN ('billing', 'shipping', 'home', 'work', 'other');

-- check: address_country_code_iso | severity: warn
-- ISO 3166-1 alpha-2 is two characters.
SELECT * FROM ${catalog}.${customer_schema}.address
WHERE country_code IS NOT NULL AND LENGTH(country_code) <> 2;

-- ---------- contact ----------

-- check: contact_keys_not_null | severity: error
SELECT * FROM ${catalog}.${customer_schema}.contact
WHERE contact_sk IS NULL OR contact_id IS NULL OR profile_id IS NULL
   OR contact_type IS NULL OR contact_value IS NULL;

-- check: contact_profile_businesskey_orphan | severity: error
SELECT c.* FROM ${catalog}.${customer_schema}.contact c
LEFT JOIN (SELECT DISTINCT profile_id FROM ${catalog}.${customer_schema}.profile) p
  ON c.profile_id = p.profile_id
WHERE p.profile_id IS NULL;

-- check: contact_type_domain | severity: error
SELECT * FROM ${catalog}.${customer_schema}.contact
WHERE contact_type NOT IN ('email', 'mobile_phone', 'landline_phone', 'fax');

-- check: contact_email_shape | severity: warn
-- Email contact points should look like an email address.
SELECT * FROM ${catalog}.${customer_schema}.contact
WHERE contact_type = 'email' AND contact_value NOT LIKE '%@%.%';

-- ---------- consent ----------

-- check: consent_keys_not_null | severity: error
SELECT * FROM ${catalog}.${customer_schema}.consent
WHERE consent_sk IS NULL OR consent_id IS NULL OR profile_id IS NULL
   OR consent_type IS NULL OR consent_status IS NULL
   OR effective_from_date IS NULL OR is_current IS NULL;

-- check: consent_profile_businesskey_orphan | severity: error
SELECT c.* FROM ${catalog}.${customer_schema}.consent c
LEFT JOIN (SELECT DISTINCT profile_id FROM ${catalog}.${customer_schema}.profile) p
  ON c.profile_id = p.profile_id
WHERE p.profile_id IS NULL;

-- check: consent_type_domain | severity: error
SELECT * FROM ${catalog}.${customer_schema}.consent
WHERE consent_type NOT IN ('marketing_email', 'marketing_sms', 'marketing_phone',
  'marketing_postal', 'data_processing', 'third_party_sharing', 'profiling', 'cookies');

-- check: consent_status_domain | severity: error
SELECT * FROM ${catalog}.${customer_schema}.consent
WHERE consent_status NOT IN ('granted', 'withdrawn', 'pending', 'expired');

-- check: consent_single_current_per_type | severity: error
-- Single source of truth: at most one current consent per (profile, type).
SELECT profile_id, consent_type, COUNT(*) AS current_rows
FROM ${catalog}.${customer_schema}.consent
WHERE is_current = true
GROUP BY profile_id, consent_type
HAVING COUNT(*) > 1;

-- ---------- account ----------

-- check: account_keys_not_null | severity: error
SELECT * FROM ${catalog}.${customer_schema}.account
WHERE account_sk IS NULL OR account_id IS NULL OR is_current IS NULL;

-- check: account_type_domain | severity: error
SELECT * FROM ${catalog}.${customer_schema}.account
WHERE account_type IS NOT NULL
  AND account_type NOT IN ('business', 'government', 'education', 'nonprofit', 'reseller');

-- check: account_credit_limit_nonnegative | severity: error
SELECT * FROM ${catalog}.${customer_schema}.account
WHERE credit_limit_amount IS NOT NULL AND credit_limit_amount < 0;

-- check: account_primary_contact_orphan | severity: error
-- A named primary contact must exist as a profile.
SELECT a.* FROM ${catalog}.${customer_schema}.account a
LEFT JOIN (SELECT DISTINCT profile_id FROM ${catalog}.${customer_schema}.profile) p
  ON a.primary_contact_profile_id = p.profile_id
WHERE a.primary_contact_profile_id IS NOT NULL AND p.profile_id IS NULL;

-- check: account_no_self_parent | severity: error
-- An account cannot be its own parent.
SELECT * FROM ${catalog}.${customer_schema}.account
WHERE parent_account_id IS NOT NULL AND parent_account_id = account_id;
