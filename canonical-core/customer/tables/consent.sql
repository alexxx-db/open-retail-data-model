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
-- — never as flags on profile/account/contact. Temporal: SCD2, date-grained
-- like every other master (effective_from_date/effective_to_date/is_current);
-- decision_timestamp keeps the legal-grade instant the decision was recorded.
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

  -- SCD2 versioning (principle #8) — date-grained, conformed to every other master.
  effective_from_date   DATE      NOT NULL COMMENT 'SCD2: inclusive start date this consent version became effective.',
  effective_to_date     DATE               COMMENT 'SCD2: exclusive end date; NULL while still in effect.',
  is_current            BOOLEAN   NOT NULL COMMENT 'SCD2: TRUE for the currently effective consent record per (profile, consent_type).',
  decision_timestamp    TIMESTAMP COMMENT 'Legal-grade instant the consent decision was given/withdrawn (UTC, ISO 8601).',

  -- Audit / provenance (standard block; all timestamps UTC)
  created_timestamp        TIMESTAMP COMMENT 'When the record was created in the source system (UTC, ISO 8601).',
  source_updated_timestamp TIMESTAMP COMMENT 'When the record was last modified in the source system (UTC, ISO 8601).',
  record_source         STRING    COMMENT 'Originating system of record (vendor-neutral label).',
  load_timestamp        TIMESTAMP COMMENT 'When this row was loaded into the canonical core (UTC, ISO 8601).',

  CONSTRAINT pk_consent PRIMARY KEY (consent_sk)
)
USING DELTA
CLUSTER BY (profile_id)
-- Deletion vectors speed row-level MERGE/UPDATE (SCD2 version closes, corrections).
TBLPROPERTIES (delta.enableDeletionVectors = true)
COMMENT 'ORDM canonical-core customer consent — the single source of truth for opt-ins and processing permissions.';
