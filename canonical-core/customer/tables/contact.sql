-- ============================================================
-- ORDM · Canonical Core · Customer domain
-- Table: contact
-- Layer: canonical core (silver / conformed)
-- Version: v1_mvm
-- Generated: 2026-06-09
-- LLM-generated: true (maintainer-reviewed before release)
-- Last reviewed: 2026-06-09
-- ============================================================
-- Contact points (email, phone) for a customer profile. Modeled as
-- one coherent concept "a way to reach the customer" with type+value
-- rather than wide email/phone columns (avoids god-table, principle #6).
-- Operational current-state (not SCD2): history captured via audit
-- timestamps and status transitions (principle #8).
-- ============================================================

CREATE TABLE IF NOT EXISTS ${catalog}.${customer_schema}.contact (
  contact_sk            BIGINT GENERATED ALWAYS AS IDENTITY
                          COMMENT 'Surrogate key.',
  contact_id            STRING NOT NULL
                          COMMENT 'Durable natural/business key for the contact point.',

  -- Owning customer
  profile_sk            BIGINT COMMENT 'FK to profile.profile_sk.',
  profile_id            STRING NOT NULL
                          COMMENT 'Durable business key of the owning customer.',

  contact_type          STRING COMMENT 'Type of contact point. Allowed values: email, mobile_phone, landline_phone, fax.',
  contact_value         STRING COMMENT 'The email address or phone number (PII). Format depends on contact_type.',
  country_calling_code  STRING COMMENT 'For phone types: country calling code without the + prefix (e.g. 1, 44).',

  is_primary            BOOLEAN   COMMENT 'TRUE if this is the primary contact point of its type for the customer.',
  is_verified           BOOLEAN   COMMENT 'TRUE if the contact point has been verified (e.g. confirmed email / SMS).',
  verified_timestamp    TIMESTAMP COMMENT 'Timestamp the contact point was verified (ISO 8601); NULL if unverified.',
  contact_status        STRING    COMMENT 'Deliverability/consent status. Allowed values: active, inactive, bounced, opted_out.',

  -- Audit / provenance
  record_source         STRING    COMMENT 'Originating system of record (vendor-neutral label).',
  load_timestamp        TIMESTAMP COMMENT 'Timestamp this row was first loaded (ISO 8601).',
  updated_timestamp     TIMESTAMP COMMENT 'Timestamp this row was last updated (ISO 8601).',

  CONSTRAINT pk_contact PRIMARY KEY (contact_sk)
)
USING DELTA
CLUSTER BY (profile_id)
-- Deletion vectors speed row-level MERGE/UPDATE (SCD2 version closes, corrections).
TBLPROPERTIES (delta.enableDeletionVectors = true)
COMMENT 'ORDM canonical-core customer contact points (email/phone), operational current-state.';

-- PII column classification (principle #11). contact_value may hold an
-- email or a phone number depending on contact_type, so both apply.
ALTER TABLE ${catalog}.${customer_schema}.contact ALTER COLUMN contact_value SET TAGS ('dbx_pii_email' = 'true', 'dbx_pii_phone' = 'true');
