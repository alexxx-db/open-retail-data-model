-- ============================================================
-- ORDM · Canonical Core · Calendar domain
-- Table: fx_rate
-- Layer: canonical core (silver / conformed reference)
-- Version: v1_mvm
-- Generated: 2026-06-10
-- LLM-generated: true (maintainer-reviewed before release)
-- Last reviewed: 2026-06-10
-- ============================================================
-- Daily foreign-exchange rates, the conversion reference for currency
-- normalization. The canonical core stores ALL monetary columns already in
-- the reporting/base currency (the deploy base_currency), so gold
-- aggregations are single-currency and correct by construction. This table
-- is what a source-aligned ETL joins to convert original-currency amounts to
-- base at ingest, and what auditors use to reconcile transaction_currency_code
-- lineage back to source. Type 1 (static reference; no SCD).
--   to_base(amount) = amount * rate   where from_currency_code -> to_currency_code = base
-- A self-rate row (from = to = base, rate = 1) exists for every date.
-- ============================================================

CREATE TABLE IF NOT EXISTS ${catalog}.${calendar_schema}.fx_rate (
  fx_rate_sk            BIGINT GENERATED ALWAYS AS IDENTITY
                          COMMENT 'Surrogate key.',
  fx_rate_id            STRING NOT NULL
                          COMMENT 'Durable business key (date_key|from|to).',

  date_key              DATE NOT NULL
                          COMMENT 'Rate date. FK to fiscal_calendar.date_key (ISO 8601).',
  from_currency_code    STRING NOT NULL COMMENT 'Source currency, ISO 4217 alpha-3.',
  to_currency_code      STRING NOT NULL COMMENT 'Target/reporting currency, ISO 4217 alpha-3 (the base_currency).',
  rate                  DECIMAL(18,8) COMMENT 'Multiply a from-currency amount by rate to get the to-currency amount. 1.0 when from = to.',

  record_source         STRING    COMMENT 'Originating system of record (vendor-neutral label).',
  load_timestamp        TIMESTAMP COMMENT 'Timestamp this row was loaded (ISO 8601).',

  CONSTRAINT pk_fx_rate PRIMARY KEY (fx_rate_sk)
)
USING DELTA
-- Lead with date_key (range-pruned by the ingest join), then the source currency.
CLUSTER BY (date_key, from_currency_code)
TBLPROPERTIES (delta.enableDeletionVectors = true)
COMMENT 'ORDM canonical-core daily FX rates (from -> base). Conversion reference for single-currency normalization.';
