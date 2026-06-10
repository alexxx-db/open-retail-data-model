# ============================================================
# ORDM · Synthetic data · Trade Promotion use case generator
# Version: v1_mvm
# Generated: 2026-06-09
# LLM-generated: true (maintainer-reviewed before release)
# Last reviewed: 2026-06-09
# ============================================================
# Populates the Trade Promotion use case end to end:
#   canonical-core: product, store, fiscal_calendar (NRF 4-5-4), sales
#   promote-with-purpose: promotion (+ NO_PROMO member), promotion_scope
# and stamps a subset of sales-fact rows with promo_sk inside each promo's
# date + scope window, so promoted and non-promoted sales both exist.
#
# Engine: dbldatagen for high-volume entities (product, store), PySpark for
# the calendar and the relational/attribution work, and a small seeded
# driver-side build for the promotion calendar (seasonal, windowed). All
# volumes come from synthetic-data/seeds.yaml (no hardcoded magic numbers).
# Shared helpers come from _common (the generator framework is extended,
# not forked).
# ============================================================

import os
import random
import sys

import dbldatagen as dg
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql import types as T
from pyspark.sql.window import Window

try:
    from _common import (RECORD_SOURCE, get_param, load_domain_config, _write,
                         attach_random_dim)
except ImportError:  # ensure sibling modules are importable when run as a notebook
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _common import (RECORD_SOURCE, get_param, load_domain_config, _write,
                         attach_random_dim)

# ------------------------------------------------------------
# Column contracts — MUST match the table DDL (minus IDENTITY *_sk).
# Verified against the DDL by tests/test_trade_promotion.py.
# ------------------------------------------------------------
PRODUCT_COLUMNS = [
    "product_id", "gtin", "sku", "product_name", "brand", "category",
    "subcategory", "department", "unit_of_measure", "list_price", "unit_cost",
    "currency_code", "product_status", "effective_from_date",
    "effective_to_date", "current_flag", "record_source", "load_timestamp",
]
STORE_COLUMNS = [
    "store_id", "gln", "store_name", "store_format", "region", "district",
    "city", "state_province", "country_code", "open_date", "store_status",
    "effective_from_date", "effective_to_date", "current_flag",
    "record_source", "load_timestamp",
]
FISCAL_CALENDAR_COLUMNS = [
    "date_key", "calendar_year", "calendar_month", "calendar_day",
    "day_of_week", "day_name", "is_weekend", "is_holiday", "fiscal_year",
    "fiscal_quarter", "fiscal_period", "fiscal_week", "fiscal_week_id",
    "fiscal_week_index", "fiscal_week_start_date", "fiscal_week_end_date",
    "record_source", "load_timestamp",
]
SALES_COLUMNS = [
    "sales_id", "date_key", "product_sk", "product_id", "store_sk",
    "store_id", "promo_sk", "promo_id", "units", "gross_revenue",
    "discount_amount", "net_revenue", "currency_code", "record_source",
    "load_timestamp",
]
PROMOTION_COLUMNS = [
    "promo_id", "promo_name", "promo_type", "funding_type", "funded_by",
    "supplier_share_pct", "start_date", "end_date", "fiscal_week_start",
    "fiscal_week_end", "planned_discount_pct", "planned_lift_pct",
    "planned_trade_spend", "effective_from_date", "effective_to_date",
    "current_flag", "record_source", "load_timestamp",
]
PROMOTION_SCOPE_COLUMNS = [
    "scope_id", "promo_sk", "promo_id", "product_sk", "product_id",
    "store_sk", "store_id", "record_source", "load_timestamp",
]

# ------------------------------------------------------------
# Vocabularies (enum domains match the DDL "Allowed values").
# ------------------------------------------------------------
PROMO_TYPES = ["TPR", "FEATURE", "DISPLAY", "FEATURE_AND_DISPLAY", "BOGO", "COUPON", "BUNDLE"]
FUNDING_TYPES = ["OFF_INVOICE", "BILL_BACK", "SCAN_DOWN", "LUMP_SUM"]
FUNDED_BY = ["SUPPLIER", "RETAILER", "SHARED"]
PRODUCT_STATUS = ["active", "inactive", "discontinued"]
STORE_STATUS = ["active", "inactive", "closed"]
STORE_FORMATS = ["hypermarket", "supermarket", "convenience", "drugstore", "online"]
UNITS_OF_MEASURE = ["each", "kg", "g", "l", "ml", "pack"]
CATEGORIES = ["beverages", "snacks", "dairy", "bakery", "household", "personal_care"]
SUBCATEGORIES = ["regular", "premium", "value", "organic"]
DEPARTMENTS = ["grocery", "fresh", "non_food", "health_beauty"]
BRANDS = ["brand_a", "brand_b", "brand_c", "brand_d", "private_label"]
REGIONS = ["north", "south", "east", "west", "central"]
COUNTRY_CODES = ["US", "CA", "GB", "FR", "DE"]
CURRENCIES = ["USD", "EUR", "GBP", "CAD"]

NO_PROMO_ID = "NO_PROMO"


# ------------------------------------------------------------
# Config
# ------------------------------------------------------------
def load_config():
    c = load_domain_config("trade_promotion")
    vols = c.get("volumes", {}) or {}
    fan = c.get("fanout", {}) or {}
    seas = c.get("seasonality", {}) or {}
    post = c.get("post_promo", {}) or {}
    return {
        "seed": c.get("seed", 2002),
        "products": vols.get("products", 120),
        "stores": vols.get("stores", 30),
        "promotions": vols.get("promotions", 60),
        "calendar_start_date": vols.get("calendar_start_date", "2024-01-07"),
        "calendar_weeks": vols.get("calendar_weeks", 110),
        "daily_sales_density": vols.get("daily_sales_density", 0.06),
        "scope_products_max": fan.get("scope_products_per_promo_max", 15),
        "scope_stores_max": fan.get("scope_stores_per_promo_max", 12),
        "promo_duration_weeks_max": fan.get("promo_duration_weeks_max", 4),
        "quarter_weights": seas.get("quarter_weights", [2, 1, 1, 4]),
        "forward_buy_weeks": post.get("forward_buy_weeks", 2),
        "forward_buy_dip_factor": post.get("forward_buy_dip_factor", 0.55),
        "cannibalization_dip_factor": post.get("cannibalization_dip_factor", 0.70),
    }


# ------------------------------------------------------------
# Fiscal calendar (NRF 4-5-4), day grain, built in PySpark from a day index.
#
# SIMPLIFICATION: this models a fixed 52-week (4-5-4) fiscal year and does NOT
# insert the NRF 53rd "leap" week that occurs roughly every 5-6 years. For the
# synthetic demo calendar this is acceptable, but it means multi-year spans can
# drift from the official NRF calendar at year boundaries. A real deployment
# should source an authoritative 4-5-4 calendar (incl. 53-week years). The
# calendar DQ check `calendar_weeks_per_year_4_5_4` reports any fiscal year that
# is not 52 or 53 weeks so this assumption is visible, not silent.
# ------------------------------------------------------------
def build_fiscal_calendar(spark, start_date_str, weeks, seed):
    base_year = int(start_date_str[:4])
    n_days = weeks * 7
    df = spark.range(0, n_days).withColumnRenamed("id", "day_offset")
    start = F.to_date(F.lit(start_date_str))
    w = (F.col("day_offset") / F.lit(7)).cast("int")          # 0-based week index
    ww = (w % F.lit(52)) + F.lit(1)                            # week within fiscal year (1..52; see note: no 53rd week)
    quarter = ((ww - F.lit(1)) / F.lit(13)).cast("int") + F.lit(1)
    wiq = ((ww - F.lit(1)) % F.lit(13)) + F.lit(1)            # week within quarter (1..13)
    period_in_q = (F.when(wiq <= F.lit(4), F.lit(1))
                    .when(wiq <= F.lit(9), F.lit(2))
                    .otherwise(F.lit(3)))
    fiscal_year = F.lit(base_year) + (w / F.lit(52)).cast("int")
    return (df
            .withColumn("date_key", F.date_add(start, F.col("day_offset")))
            .withColumn("_w", w)
            .withColumn("calendar_year", F.year("date_key"))
            .withColumn("calendar_month", F.month("date_key"))
            .withColumn("calendar_day", F.dayofmonth("date_key"))
            # ISO day of week (1=Mon..7=Sun) from Spark dayofweek (1=Sun..7=Sat)
            .withColumn("_dow", F.dayofweek("date_key"))
            .withColumn("day_of_week", F.when(F.col("_dow") == 1, F.lit(7)).otherwise(F.col("_dow") - 1))
            .withColumn("day_name", F.lower(F.date_format("date_key", "EEEE")))
            .withColumn("is_weekend", F.col("_dow").isin(1, 7))
            .withColumn("is_holiday",
                        ((F.col("calendar_month") == 12) & (F.col("calendar_day") == 25)) |
                        ((F.col("calendar_month") == 1) & (F.col("calendar_day") == 1)))
            .withColumn("fiscal_year", fiscal_year)
            .withColumn("fiscal_quarter", quarter)
            .withColumn("fiscal_period", (quarter - F.lit(1)) * F.lit(3) + period_in_q)
            .withColumn("fiscal_week", ww)
            .withColumn("fiscal_week_id", F.col("fiscal_year") * F.lit(100) + ww)
            .withColumn("fiscal_week_index", F.col("_w") + F.lit(1))
            .withColumn("fiscal_week_start_date", F.date_add(start, F.col("_w") * F.lit(7)))
            .withColumn("fiscal_week_end_date", F.date_add(start, F.col("_w") * F.lit(7) + F.lit(6)))
            .withColumn("record_source", F.lit(RECORD_SOURCE))
            .withColumn("load_timestamp", F.current_timestamp()))


# ------------------------------------------------------------
# Product / store masters (dbldatagen)
# ------------------------------------------------------------
def build_products(spark, n, seed):
    spec = (
        dg.DataGenerator(spark, name="product", rows=n, partitions=4,
                         randomSeedMethod="fixed", randomSeed=seed)
        .withColumn("product_id", "string", expr="concat('SKU-', lpad(cast(id as string), 8, '0'))")
        .withColumn("gtin", "string", expr="lpad(cast((id * 13 + 100000000000) as string), 13, '0')")
        .withColumn("sku", "string", expr="concat('S', lpad(cast(id as string), 7, '0'))")
        .withColumn("product_name", "string", expr="concat('Product ', lpad(cast(id as string), 6, '0'))")
        .withColumn("brand", "string", values=BRANDS)
        .withColumn("category", "string", values=CATEGORIES)
        .withColumn("subcategory", "string", values=SUBCATEGORIES)
        .withColumn("department", "string", values=DEPARTMENTS)
        .withColumn("unit_of_measure", "string", values=UNITS_OF_MEASURE)
        .withColumn("_price", "int", minValue=99, maxValue=4999, omit=True)
        .withColumn("list_price", "decimal(18,2)", expr="cast(_price as decimal(18,2)) / 100")
        # Unit cost = 50-80% of list price (deterministic per product), so per-unit
        # margin is positive but compresses under deep promotional discounts.
        .withColumn("_cost_ratio", "int", minValue=50, maxValue=80, omit=True)
        .withColumn("unit_cost", "decimal(18,2)", expr="cast(_price * _cost_ratio as decimal(18,2)) / 10000")
        .withColumn("currency_code", "string", values=CURRENCIES)
        .withColumn("product_status", "string", values=PRODUCT_STATUS, weights=[90, 7, 3])
    )
    return _stamp_scd2(spec.build(), "2018-01-01")


def build_stores(spark, n, seed):
    spec = (
        dg.DataGenerator(spark, name="store", rows=n, partitions=2,
                         randomSeedMethod="fixed", randomSeed=seed)
        .withColumn("store_id", "string", expr="concat('STR-', lpad(cast(id as string), 5, '0'))")
        .withColumn("gln", "string", expr="lpad(cast((id * 7 + 200000000000) as string), 13, '0')")
        .withColumn("store_name", "string", expr="concat('Store ', lpad(cast(id as string), 4, '0'))")
        .withColumn("store_format", "string", values=STORE_FORMATS)
        .withColumn("region", "string", values=REGIONS)
        .withColumn("district", "string", expr="concat('D', lpad(cast(id % 20 as string), 3, '0'))")
        .withColumn("city", "string", expr="concat('City ', cast(id % 50 as string))")
        .withColumn("state_province", "string", expr="concat('S', lpad(cast(id % 30 as string), 2, '0'))")
        .withColumn("country_code", "string", values=COUNTRY_CODES)
        .withColumn("_open_off", "int", minValue=0, maxValue=3650, omit=True)
        .withColumn("open_date", "date", expr="date_add(date'2010-01-01', _open_off)")
        .withColumn("store_status", "string", values=STORE_STATUS, weights=[92, 5, 3])
    )
    return _stamp_scd2(spec.build(), "2010-01-01")


def _stamp_scd2(df, eff_from):
    return (df
            .withColumn("effective_from_date", F.lit(eff_from).cast("date"))
            .withColumn("effective_to_date", F.lit(None).cast("date"))
            .withColumn("current_flag", F.lit(True))
            .withColumn("record_source", F.lit(RECORD_SOURCE))
            .withColumn("load_timestamp", F.current_timestamp()))


# ------------------------------------------------------------
# Promotion calendar (seeded, seasonal, windowed) — built driver-side.
# ------------------------------------------------------------
_PROMO_SCHEMA = T.StructType([
    T.StructField("promo_id", T.StringType()),
    T.StructField("promo_name", T.StringType()),
    T.StructField("promo_type", T.StringType()),
    T.StructField("funding_type", T.StringType()),
    T.StructField("funded_by", T.StringType()),
    T.StructField("supplier_share_pct", T.DecimalType(5, 2)),
    T.StructField("start_date", T.DateType()),
    T.StructField("end_date", T.DateType()),
    T.StructField("fiscal_week_start", T.IntegerType()),
    T.StructField("fiscal_week_end", T.IntegerType()),
    T.StructField("planned_discount_pct", T.DecimalType(5, 2)),
    T.StructField("planned_lift_pct", T.DecimalType(6, 2)),
    T.StructField("planned_trade_spend", T.DecimalType(18, 2)),
])


def build_promotions(spark, weeks_rows, n, seed, duration_max, quarter_weights, calendar_start):
    """weeks_rows: list of dicts with fiscal_week_id, fiscal_week_index,
    fiscal_quarter, fiscal_week_start_date, fiscal_week_end_date."""
    rnd = random.Random(seed)
    weeks = sorted(weeks_rows, key=lambda r: r["fiscal_week_index"])
    by_index = {r["fiscal_week_index"]: r for r in weeks}
    max_index = max(by_index)
    # Seasonality: weight each week by its quarter's weight.
    weighted = []
    for r in weeks:
        wgt = quarter_weights[(r["fiscal_quarter"] - 1) % len(quarter_weights)]
        weighted.extend([r["fiscal_week_index"]] * int(wgt))

    rows = []
    # Reserved no-promotion member.
    rows.append((NO_PROMO_ID, "No Promotion", None, None, None, None,
                 None, None, None, None, None, None, None))
    for i in range(1, n + 1):
        start_idx = rnd.choice(weighted)
        dur = rnd.randint(1, duration_max)
        end_idx = min(start_idx + dur - 1, max_index)
        sw, ew = by_index[start_idx], by_index[end_idx]
        fby = rnd.choice(FUNDED_BY)
        if fby == "RETAILER":
            share = None
        elif fby == "SUPPLIER":
            share = round(rnd.uniform(80, 100), 2)
        else:  # SHARED
            share = round(rnd.uniform(30, 70), 2)
        rows.append((
            f"PROMO-{i:05d}",
            f"Promotion {i:05d}",
            rnd.choice(PROMO_TYPES),
            rnd.choice(FUNDING_TYPES),
            fby,
            share,
            sw["fiscal_week_start_date"],
            ew["fiscal_week_end_date"],
            sw["fiscal_week_id"],
            ew["fiscal_week_id"],
            round(rnd.uniform(5, 40), 2),
            round(rnd.uniform(10, 120), 2),
            round(rnd.uniform(1000, 50000), 2),
        ))
    df = spark.createDataFrame(rows, schema=_PROMO_SCHEMA)
    # SCD2: effective from the promo start (or calendar start for NO_PROMO).
    return (df
            .withColumn("effective_from_date",
                        F.coalesce(F.col("start_date"), F.lit(calendar_start).cast("date")))
            .withColumn("effective_to_date", F.lit(None).cast("date"))
            .withColumn("current_flag", F.lit(True))
            .withColumn("record_source", F.lit(RECORD_SOURCE))
            .withColumn("load_timestamp", F.current_timestamp()))


def build_promotion_scope(spark, promo_ids, product_ids, store_ids, seed,
                          products_max, stores_max):
    rnd = random.Random(seed + 1)
    rows = []
    for pid in promo_ids:
        prods = rnd.sample(product_ids, min(products_max, len(product_ids)))
        stores = rnd.sample(store_ids, min(stores_max, len(store_ids)))
        for prod in prods:
            for st in stores:
                rows.append((f"SCOPE-{pid}-{prod}-{st}", pid, prod, st))
    schema = T.StructType([
        T.StructField("scope_id", T.StringType()),
        T.StructField("promo_id", T.StringType()),
        T.StructField("product_id", T.StringType()),
        T.StructField("store_id", T.StringType()),
    ])
    return spark.createDataFrame(rows, schema=schema)


# ------------------------------------------------------------
# Sales fact with promotion attribution
# ------------------------------------------------------------
def build_sales(spark, calendar_df, products_current, stores_current,
                promo_windows, fb_windows, cannib_windows, no_promo_sk, seed,
                density, fb_factor, cannib_factor):
    prod = products_current.select("product_sk", "product_id", "list_price")
    stores = stores_current.select("store_sk", "store_id")
    days = calendar_df.select("date_key")
    n_p, n_s, n_d = prod.count(), stores.count(), days.count()

    # Generate exactly the density-thinned number of rows and attach a random
    # product / store / day to each via broadcast joins -- NO product x store x
    # day cartesian. Collisions (same product,store,day) are deduped downstream
    # by the attribution window, so the output is the unique selling combinations.
    n_target = max(1, int(n_p * n_s * n_d * density))
    base = spark.range(0, n_target).withColumnRenamed("id", "_rid")
    base = attach_random_dim(base, prod, n_p, "prod", seed, "_rid")
    base = attach_random_dim(base, stores, n_s, "store", seed, "_rid")
    base = attach_random_dim(base, days, n_d, "day", seed, "_rid")
    base = base.withColumn("base_units",
                           (F.abs(F.hash("product_id", "store_id", "date_key", F.lit(seed))) % F.lit(18) + F.lit(3)))

    # Attribute to a promotion when the day falls inside a scoped promo window.
    matched = (base.join(
                    promo_windows,
                    on=[base.product_sk == promo_windows.w_product_sk,
                        base.store_sk == promo_windows.w_store_sk,
                        base.date_key >= promo_windows.start_date,
                        base.date_key <= promo_windows.end_date],
                    how="left")
               .drop("w_product_sk", "w_store_sk"))
    # When several promos overlap, keep the lowest promo_sk deterministically.
    pick = Window.partitionBy("product_sk", "store_sk", "date_key").orderBy(F.col("w_promo_sk").asc_nulls_last())
    matched = matched.withColumn("_rn", F.row_number().over(pick)).where("_rn = 1")

    # The two value-killers, resolved to a per (product, store, day) flag via the
    # distinct hit sets (range-joined once, so the main path stays an equi-join).
    keys = base.select("product_sk", "store_sk", "date_key")
    fb_hit = (keys.join(fb_windows,
                        on=[keys.product_sk == fb_windows.fb_product_sk,
                            keys.store_sk == fb_windows.fb_store_sk,
                            keys.date_key >= fb_windows.fb_start,
                            keys.date_key <= fb_windows.fb_end], how="inner")
              .select("product_sk", "store_sk", "date_key").distinct()
              .withColumn("_is_fb", F.lit(True)))
    cannib_hit = (keys.join(cannib_windows,
                            on=[keys.product_sk == cannib_windows.c_product_sk,
                                keys.store_sk == cannib_windows.c_store_sk,
                                keys.date_key >= cannib_windows.cstart,
                                keys.date_key <= cannib_windows.cend], how="inner")
                  .select("product_sk", "store_sk", "date_key").distinct()
                  .withColumn("_is_cannib", F.lit(True)))
    matched = (matched
               .join(fb_hit, on=["product_sk", "store_sk", "date_key"], how="left")
               .join(cannib_hit, on=["product_sk", "store_sk", "date_key"], how="left"))

    promoted = F.col("w_promo_sk").isNotNull()
    # Precedence: promoted (lift) > forward-buy dip > cannibalization dip > normal.
    mult = (F.when(promoted, F.lit(1.0) + F.col("w_lift_pct") / F.lit(100.0))
             .when(F.col("_is_fb").isNotNull(), F.lit(float(fb_factor)))
             .when(F.col("_is_cannib").isNotNull(), F.lit(float(cannib_factor)))
             .otherwise(F.lit(1.0)))
    disc_pct = F.when(promoted, F.col("w_discount_pct")).otherwise(F.lit(0.0))
    units = F.greatest(F.round(F.col("base_units") * mult).cast("int"), F.lit(0))
    gross = F.round(units * F.col("list_price"), 2)
    discount = F.round(gross * disc_pct / F.lit(100.0), 2)
    return (matched
            .withColumn("units", units)
            .withColumn("gross_revenue", gross)
            .withColumn("discount_amount", discount)
            .withColumn("net_revenue", F.col("gross_revenue") - F.col("discount_amount"))
            .withColumn("promo_sk", F.coalesce(F.col("w_promo_sk"), F.lit(no_promo_sk)))
            .withColumn("promo_id", F.coalesce(F.col("w_promo_id"), F.lit(NO_PROMO_ID)))
            .withColumn("sales_id", F.concat_ws("-", F.lit("SAL"), F.col("product_id"),
                                                F.col("store_id"), F.col("date_key")))
            .withColumn("record_source", F.lit(RECORD_SOURCE))
            .withColumn("load_timestamp", F.current_timestamp()))


# ------------------------------------------------------------
# Orchestration
# ------------------------------------------------------------
def generate(spark, catalog, schemas, cfg, mode):
    if not catalog:
        raise ValueError("`catalog` parameter is required (guardrail #1: no hardcoded catalog).")

    def fq(schema, table):
        return f"{catalog}.{schemas[schema]}.{table}"

    seed = cfg["seed"]
    print(f"[ordm] generating Trade Promotion into {catalog} "
          f"(products={cfg['products']}, stores={cfg['stores']}, "
          f"promotions={cfg['promotions']}, seed={seed}, mode={mode})")

    # 1. fiscal calendar
    calendar_df = build_fiscal_calendar(spark, cfg["calendar_start_date"], cfg["calendar_weeks"], seed)
    _write(spark, calendar_df, fq("calendar", "fiscal_calendar"), FISCAL_CALENDAR_COLUMNS, mode)
    calendar_tbl = spark.table(fq("calendar", "fiscal_calendar"))

    # 2. product / store masters
    _write(spark, build_products(spark, cfg["products"], seed), fq("product", "product"), PRODUCT_COLUMNS, mode)
    _write(spark, build_stores(spark, cfg["stores"], seed), fq("store", "store"), STORE_COLUMNS, mode)
    products_current = spark.table(fq("product", "product")).where("current_flag = true")
    stores_current = spark.table(fq("store", "store")).where("current_flag = true")

    # 3. promotion calendar (seasonal, windowed)
    weeks_rows = [r.asDict() for r in calendar_tbl
                  .select("fiscal_week_id", "fiscal_week_index", "fiscal_quarter",
                          "fiscal_week_start_date", "fiscal_week_end_date")
                  .distinct().collect()]
    promotions = build_promotions(spark, weeks_rows, cfg["promotions"], seed,
                                  cfg["promo_duration_weeks_max"], cfg["quarter_weights"],
                                  cfg["calendar_start_date"])
    _write(spark, promotions, fq("promo", "promotion"), PROMOTION_COLUMNS, mode)
    promo_current = spark.table(fq("promo", "promotion")).where("current_flag = true")
    no_promo_sk = promo_current.where(F.col("promo_id") == NO_PROMO_ID).select("promo_sk").first()[0]

    # 4. promotion scope (product x store coverage), excluding the NO_PROMO member
    product_ids = [r[0] for r in products_current.select("product_id").collect()]
    store_ids = [r[0] for r in stores_current.select("store_id").collect()]
    real_promo_ids = [r[0] for r in promo_current.where(F.col("promo_id") != NO_PROMO_ID)
                      .select("promo_id").collect()]
    scope_keys = build_promotion_scope(spark, real_promo_ids, product_ids, store_ids,
                                       seed, cfg["scope_products_max"], cfg["scope_stores_max"])
    scope = (scope_keys
             .join(promo_current.select("promo_id", "promo_sk"), on="promo_id", how="inner")
             .join(products_current.select("product_id", "product_sk"), on="product_id", how="inner")
             .join(stores_current.select("store_id", "store_sk"), on="store_id", how="inner")
             .withColumn("record_source", F.lit(RECORD_SOURCE))
             .withColumn("load_timestamp", F.current_timestamp()))
    _write(spark, scope, fq("promo", "promotion_scope"), PROMOTION_SCOPE_COLUMNS, mode)

    # 5. sales fact, attributed via scope + promo date window
    promo_windows = (spark.table(fq("promo", "promotion_scope"))
                     .join(promo_current.select(
                         F.col("promo_sk").alias("w_promo_sk"),
                         F.col("promo_id").alias("w_promo_id"),
                         F.col("start_date"), F.col("end_date"),
                         F.col("planned_discount_pct").alias("w_discount_pct"),
                         F.col("planned_lift_pct").alias("w_lift_pct"),
                         F.col("promo_id")), on="promo_id", how="inner")
                     .select(F.col("product_sk").alias("w_product_sk"),
                             F.col("store_sk").alias("w_store_sk"),
                             "w_promo_sk", "w_promo_id", "start_date", "end_date",
                             "w_discount_pct", "w_lift_pct"))
    # 5a. forward-buy windows: the N weeks AFTER each promo, per promoted product x store.
    scope_tbl = spark.table(fq("promo", "promotion_scope")).select("promo_sk", "product_sk", "store_sk")
    fb_windows = (scope_tbl
                  .join(promo_current.select("promo_sk", "end_date"), on="promo_sk", how="inner")
                  .select(F.col("product_sk").alias("fb_product_sk"),
                          F.col("store_sk").alias("fb_store_sk"),
                          F.date_add("end_date", 1).alias("fb_start"),
                          F.date_add("end_date", cfg["forward_buy_weeks"] * 7).alias("fb_end"))
                  .where("fb_end IS NOT NULL").distinct())

    # 5b. cannibalization windows: substitute SKUs (same category, NOT in scope)
    #     in the promo's stores during the promo window.
    prod_cat = products_current.select("product_sk", "category")
    scope_cat = (scope_tbl
                 .join(promo_current.select("promo_sk", "start_date", "end_date"), on="promo_sk", how="inner")
                 .join(prod_cat, on="product_sk", how="inner")
                 .select("promo_sk", "store_sk", "category", "start_date", "end_date").distinct())
    scope_products = scope_tbl.select("promo_sk", "product_sk").distinct()
    cannib_windows = (scope_cat
                      .join(prod_cat.select(F.col("product_sk").alias("cand_sk"), "category"),
                            on="category", how="inner")
                      .join(scope_products.select("promo_sk", F.col("product_sk").alias("cand_sk")),
                            on=["promo_sk", "cand_sk"], how="left_anti")
                      .select(F.col("cand_sk").alias("c_product_sk"),
                              F.col("store_sk").alias("c_store_sk"),
                              F.col("start_date").alias("cstart"),
                              F.col("end_date").alias("cend")).distinct())

    sales = build_sales(spark, calendar_tbl, products_current, stores_current,
                        promo_windows, fb_windows, cannib_windows, no_promo_sk, seed,
                        cfg["daily_sales_density"], cfg["forward_buy_dip_factor"],
                        cfg["cannibalization_dip_factor"])
    _write(spark, sales, fq("transaction", "sales"), SALES_COLUMNS, mode)

    print("[ordm] Trade Promotion generation complete.")


def main():
    spark = SparkSession.builder.getOrCreate()
    cfg = load_config()
    catalog = get_param("catalog", "")
    schemas = {
        "product": get_param("product_schema", "product"),
        "store": get_param("store_schema", "store"),
        "calendar": get_param("calendar_schema", "calendar"),
        "transaction": get_param("transaction_schema", "transaction"),
        "promo": get_param("promo_schema", "promote_with_purpose"),
    }
    mode = get_param("mode", "overwrite")
    # Allow volume overrides via params (else seeds.yaml defaults).
    for key in ("products", "stores", "promotions", "calendar_weeks"):
        val = get_param(key, "")
        if val:
            cfg[key] = int(val)
    generate(spark, catalog, schemas, cfg, mode)


if __name__ == "__main__":
    main()
