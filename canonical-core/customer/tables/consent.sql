-- ============================================================
-- ORDM · Canonical Core · Customer domain
-- Table: consent
-- Layer: canonical core (silver / conformed)
-- Version: v1_mvm
-- Generated: 2026-06-09
-- LLM-generated: true (maintainer-reviewed before release)
-- Last reviewed: 2026-06-09
-- ============================================================
-- The single source of truth for customer consent (principle #5).
-- Marketing opt-ins, data-processing permissions, etc. live ONLY here
-- — never as flags on profile/account/contact. Temporal: each consent
-- decision is a versioned row with validity window + current_flag.
-- ============================================================

CREATE TABLE IF NOT EXISTS ${catalog}.${customer_schema}.consent (
  consent_sk            BIGINT GENERATED ALWAYS AS IDENTITY
                          COMMENT 'Surrogate key. Unique per consent version.',
  consent_id            STRING NOT NULL
                          COMMENT 'Durable natural/business key for the consent record.',

  -- Owning customer
  profile_sk            BIGINT COMMENT 'FK to profile.profile_sk.',
  profile_id            STRING NOT NULL
                          COMMENT 'Durable business key of the customer giving/withholding consent.',

  consent_type          STRING COMMENT 'What the consent governs. Allowed values: marketing_email, marketing_sms, marketing_phone, marketing_postal, data_processing, third_party_sharing, profiling, cookies.',
  consent_status        STRING COMMENT 'Current decision. Allowed values: granted, withdrawn, pending, expired.',
  legal_basis           STRING COMMENT 'Lawful basis for processing. Allowed values: consent, contract, legitimate_interest, legal_obligation, vital_interest, public_task.',
  capture_channel       STRING COMMENT 'Channel where consent was captured (vendor-neutral). Allowed values: web, mobile_app, store, call_center, email.',
  disclosure_version    STRING COMMENT 'Identifier/version of the consent statement or privacy notice presented at capture.',

  -- Temporal validity
  valid_from_timestamp  TIMESTAMP NOT NULL COMMENT 'Inclusive start of validity for this consent decision (ISO 8601).',
  valid_to_timestamp    TIMESTAMP          COMMENT 'Exclusive end of validity; NULL while still in effect (ISO 8601).',
  current_flag          BOOLEAN   NOT NULL COMMENT 'TRUE for the currently effective consent record per (profile, consent_type).',

  -- Audit / provenance
  record_source         STRING    COMMENT 'Originating system of record (vendor-neutral label).',
  load_timestamp        TIMESTAMP COMMENT 'Timestamp this row was loaded into the canonical core (ISO 8601).',

  CONSTRAINT pk_consent PRIMARY KEY (consent_sk)
)
USING DELTA
CLUSTER BY (profile_id)
COMMENT 'ORDM canonical-core customer consent — the single source of truth for opt-ins and processing permissions.';
