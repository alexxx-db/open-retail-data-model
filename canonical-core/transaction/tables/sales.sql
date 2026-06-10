-- ============================================================
-- ORDM · Canonical Core · Transaction domain
-- Table: sales
-- Layer: canonical core (silver / conformed fact)
-- Version: v1_mvm
-- Generated: 2026-06-09
-- LLM-generated: true (maintainer-reviewed before release)
-- Last reviewed: 2026-06-09
-- ============================================================
-- POS sales fact at product x store x day grain. Conformed fact shared by
-- outcome packages. Each row is attributed to a promotion via promo_sk:
-- non-promoted sales carry the dedicated "no promotion" member of the
-- promotion dimension (promo_id = 'NO_PROMO'), so promoted vs non-promoted
-- sales are both first-class for downstream ROI work.
-- ============================================================

CREATE TABLE IF NOT EXISTS ${catalog}.${transaction_schema}.sales (
  sales_sk              BIGINT GENERATED ALWAYS AS IDENTITY
                          COMMENT 'Surrogate key.',
  sales_id              STRING NOT NULL
                          COMMENT 'Durable natural/business key for the daily sales record.',

  date_key              DATE NOT NULL
                          COMMENT 'Selling date. FK to fiscal_calendar.date_key (ISO 8601).',

  product_sk            BIGINT COMMENT 'FK to product.product_sk (version-specific).',
  product_id            STRING NOT NULL COMMENT 'Durable product business key.',
  store_sk              BIGINT COMMENT 'FK to store.store_sk (version-specific).',
  store_id              STRING NOT NULL COMMENT 'Durable store business key.',

  -- Promotion attribution (nullable per spec; populated with the NO_PROMO
  -- member surrogate for non-promoted sales, so it is effectively never NULL).
  promo_sk              BIGINT COMMENT 'FK to promotion.promo_sk. Non-promoted rows carry the NO_PROMO member surrogate.',
  promo_id              STRING COMMENT 'Durable promotion business key; equals NO_PROMO when the sale was not on promotion.',

  units                 INT           COMMENT 'Units sold (count).',
  gross_revenue         DECIMAL(18,2) COMMENT 'Gross sales amount before promotional discount, in store currency.',
  discount_amount       DECIMAL(18,2) COMMENT 'Promotional discount amount applied.',
  net_revenue           DECIMAL(18,2) COMMENT 'Net sales amount after discount (gross_revenue - discount_amount).',
  currency_code         STRING        COMMENT 'Currency of monetary columns, ISO 4217 alpha-3.',

  record_source         STRING    COMMENT 'Originating system of record (vendor-neutral label).',
  load_timestamp        TIMESTAMP COMMENT 'Timestamp this row was loaded (ISO 8601).',

  CONSTRAINT pk_sales PRIMARY KEY (sales_sk)
)
USING DELTA
-- Liquid clustering leads with date_key: period-grain gold views join sales to
-- the fiscal calendar and filter/aggregate by time, so date-range pruning matters
-- most. product_sk/store_sk are the next join keys. promo_sk is intentionally NOT
-- a clustering key -- it is low-cardinality (most rows carry the single NO_PROMO
-- member) and would cluster poorly.
CLUSTER BY (date_key, product_sk, store_sk)
COMMENT 'ORDM canonical-core POS sales fact (product x store x day). Carries promo_sk for promotion attribution.';
