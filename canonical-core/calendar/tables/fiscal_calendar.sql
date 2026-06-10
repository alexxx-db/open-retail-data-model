-- ============================================================
-- ORDM · Canonical Core · Calendar domain
-- Table: fiscal_calendar
-- Layer: canonical core (silver / conformed reference)
-- Version: v1_mvm
-- Generated: 2026-06-09
-- LLM-generated: true (maintainer-reviewed before release)
-- Last reviewed: 2026-06-09
-- ============================================================
-- NRF 4-5-4 retail fiscal calendar at DAY grain. All retail-week / period
-- / quarter logic MUST join here rather than deriving weeks from raw dates.
-- Type 1 (static reference; no SCD). fiscal_week_id is the join key for
-- week-level logic; fiscal_week_index is a globally monotonic week number
-- used for trailing-window ("last N weeks") calculations across year
-- boundaries.
-- ============================================================

CREATE TABLE IF NOT EXISTS ${catalog}.${calendar_schema}.fiscal_calendar (
  calendar_sk           BIGINT GENERATED ALWAYS AS IDENTITY
                          COMMENT 'Surrogate key.',
  date_key              DATE NOT NULL
                          COMMENT 'The calendar date (ISO 8601). Natural key; join target for the sales fact.',

  calendar_year         INT COMMENT 'Gregorian calendar year.',
  calendar_month        INT COMMENT 'Gregorian month (1-12).',
  calendar_day          INT COMMENT 'Day of month (1-31).',
  day_of_week           INT COMMENT 'ISO day of week (1=Monday .. 7=Sunday).',
  day_name              STRING COMMENT 'Day name (monday .. sunday).',
  is_weekend            BOOLEAN COMMENT 'TRUE for Saturday/Sunday.',
  is_holiday            BOOLEAN COMMENT 'TRUE if a recognized retail holiday.',

  -- NRF 4-5-4 fiscal attributes
  fiscal_year           INT COMMENT 'NRF 4-5-4 fiscal year.',
  fiscal_quarter        INT COMMENT 'NRF fiscal quarter (1-4).',
  fiscal_period         INT COMMENT 'NRF fiscal period / retail month (1-12), following the 4-5-4 week pattern.',
  fiscal_week           INT COMMENT 'NRF fiscal week within the fiscal year (1-53).',
  fiscal_week_id        INT COMMENT 'Week identifier = fiscal_year * 100 + fiscal_week (e.g. 202614). Week-level join key.',
  fiscal_week_index     INT COMMENT 'Globally monotonic week counter across the whole calendar; use for trailing N-week windows.',
  fiscal_week_start_date DATE COMMENT 'First date (Sunday, NRF convention) of the fiscal week.',
  fiscal_week_end_date   DATE COMMENT 'Last date (Saturday) of the fiscal week.',

  record_source         STRING    COMMENT 'Originating system of record (vendor-neutral label).',
  load_timestamp        TIMESTAMP COMMENT 'Timestamp this row was loaded into the canonical core (UTC, ISO 8601).',

  CONSTRAINT pk_fiscal_calendar PRIMARY KEY (calendar_sk)
)
USING DELTA
CLUSTER BY (date_key)
-- Deletion vectors speed row-level MERGE/UPDATE (SCD2 version closes, corrections).
TBLPROPERTIES (delta.enableDeletionVectors = true)
COMMENT 'ORDM canonical-core NRF 4-5-4 retail fiscal calendar (day grain). Conformed time dimension.';
