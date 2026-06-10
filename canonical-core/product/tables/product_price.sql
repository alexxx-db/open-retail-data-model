-- ============================================================
-- ORDM · Canonical Core · Product domain
-- Table: product_price
-- Layer: canonical core (silver / conformed)
-- Version: v1_mvm
-- Generated: 2026-06-10
-- LLM-generated: true (maintainer-reviewed before release)
-- Last reviewed: 2026-06-10
-- ============================================================
-- Temporal price history — the system of record for prices over time. One
-- date-grained version per (product, price_type); a price change appends a
-- new version and end-dates the prior one, WITHOUT re-versioning the whole
-- product master. product.list_price / product.unit_cost remain on the
-- product dimension as the convenience CURRENT-price snapshot (the mirror of
-- the is_current rows here for price_type list / cost) so the dimensional
-- model keeps a cheap single-row join; this table is where you read price
-- AS OF a date. Amounts are unit-grain DECIMAL(18,4) (principle #9d), in the
-- reporting/base currency (principle #9a).
-- ============================================================

CREATE TABLE IF NOT EXISTS ${catalog}.${product_schema}.product_price (
  product_price_sk      BIGINT GENERATED ALWAYS AS IDENTITY
                          COMMENT 'Surrogate key. Unique per price version.',
  product_price_id      STRING NOT NULL
                          COMMENT 'Durable business key (product_id|price_type|effective_from).',
  product_id            STRING NOT NULL
                          COMMENT 'FK to product (business key). The priced product.',

  price_type            STRING COMMENT 'What the amount represents. Allowed values: list, cost, promotional, contract.',
  amount                DECIMAL(18,4) COMMENT 'Unit-grain price/cost (principle #9d), in the reporting/base currency.',
  currency_code         STRING COMMENT 'Reporting/base currency, ISO 4217 alpha-3. Equals the deploy base_currency; single-currency by construction.',
  transaction_currency_code STRING COMMENT 'Original currency before normalization (lineage only), ISO 4217 alpha-3. Convert with fx_rate.',

  -- SCD2 versioning (principle #8) — date-grained, conformed to every other master.
  effective_from_date   DATE    NOT NULL COMMENT 'SCD2: inclusive start date this price became effective.',
  effective_to_date     DATE             COMMENT 'SCD2: exclusive end date; NULL for the current price.',
  is_current            BOOLEAN NOT NULL COMMENT 'SCD2: TRUE for the currently effective price per (product, price_type).',

  -- Audit / provenance (standard block; all timestamps UTC)
  created_timestamp        TIMESTAMP COMMENT 'When the record was created in the source system (UTC, ISO 8601).',
  source_updated_timestamp TIMESTAMP COMMENT 'When the record was last modified in the source system (UTC, ISO 8601).',
  record_source         STRING    COMMENT 'Originating system of record (vendor-neutral label).',
  load_timestamp        TIMESTAMP COMMENT 'When this row was loaded into the canonical core (UTC, ISO 8601).',

  CONSTRAINT pk_product_price PRIMARY KEY (product_price_sk)
)
USING DELTA
CLUSTER BY (product_id, price_type)
-- Deletion vectors speed row-level MERGE/UPDATE (SCD2 version closes, corrections).
TBLPROPERTIES (delta.enableDeletionVectors = true)
COMMENT 'ORDM canonical-core product price history (SCD2 per product x price_type). Read price AS OF a date here; product dim carries the current snapshot.';
