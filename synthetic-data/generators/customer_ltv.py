# ============================================================
# ORDM · Synthetic data · Customer Lifetime Value generator
# Version: v1_mvm
# Generated: 2026-06-09
# LLM-generated: true (maintainer-reviewed before release)
# Last reviewed: 2026-06-09
# ============================================================
# Populates the canonical-core customer_order_line fact with a realistic,
# SKEWED value distribution: most customers have few orders (long low-value
# tail), a few have many (high-value head), so CLV tiers and RFM quintiles
# populate meaningfully. Orders/customer ~ max * u^value_skew (configurable).
#
# Reuses the customer profile dimension (run the customer generator first) and
# product / store / fiscal_calendar (run the trade_promotion generator first).
# Shared helpers come from _common (extended, not forked).
# ============================================================

import os
import sys

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

try:
    from _common import (RECORD_SOURCE, get_param, load_domain_config, _frac, _pick, _write,
                         attach_random_dim)
except ImportError:  # ensure sibling modules are importable when run as a notebook
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _common import (RECORD_SOURCE, get_param, load_domain_config, _frac, _pick, _write,
                         attach_random_dim)

# Column contracts — MUST match the DDL (minus IDENTITY *_sk).
# Verified against the DDL by tests/test_customer_ltv.py.
CUSTOMER_ORDER_LINE_COLUMNS = [
    "order_line_id", "order_id", "profile_sk", "profile_id", "product_sk",
    "product_id", "store_sk", "store_id", "order_date", "event_timestamp", "units",
    "gross_amount", "net_amount", "currency_code", "transaction_currency_code",
    "record_source", "load_timestamp",
]
PAYMENT_COLUMNS = [
    "payment_id", "order_id", "profile_sk", "profile_id", "payment_type",
    "payment_method", "payment_status", "amount", "currency_code",
    "transaction_currency_code", "event_timestamp", "record_source", "load_timestamp",
]
PAYMENT_METHODS = ["card", "cash", "wallet", "bank_transfer", "gift_card", "voucher"]


def load_config():
    c = load_domain_config("customer_ltv")
    vols = c.get("volumes", {}) or {}
    return {
        "seed": c.get("seed", 4004),
        "max_orders": vols.get("max_orders_per_customer", 40),
        "value_skew": vols.get("value_skew", 4.0),
        "lines_per_order_max": vols.get("lines_per_order_max", 4),
    }


def build_order_lines(spark, profiles_current, products_current, stores_current,
                      start_date, n_days, seed, max_orders, value_skew, lines_per_order_max,
                      base_currency):
    start = F.lit(start_date)
    prod_dim = products_current.select("product_sk", "product_id", "list_price")
    store_dim = stores_current.select("store_sk", "store_id")
    n_products, n_stores = prod_dim.count(), store_dim.count()

    # orders per customer from a skewed draw: most low, a few high.
    customers = (profiles_current.select("profile_sk", "profile_id")
                 .withColumn("_u", _frac(seed, "vol", "profile_id"))
                 .withColumn("orders_count",
                             F.greatest(F.ceil(F.lit(float(max_orders))
                                               * F.pow(F.col("_u"), F.lit(float(value_skew)))).cast("int"),
                                        F.lit(1))))

    orders = (customers
              .withColumn("order_idx", F.explode(F.expr("sequence(1, orders_count)")))
              .withColumn("order_id", F.concat_ws("-", F.lit("ORD"), F.col("profile_id"), F.col("order_idx")))
              .withColumn("_oh", F.abs(F.hash("profile_id", "order_idx", F.lit(seed))))
              .withColumn("order_date", F.date_add(start, F.col("_oh") % F.lit(max(1, n_days))))
              .withColumn("n_lines", (F.col("_oh") % F.lit(max(1, lines_per_order_max)) + F.lit(1)).cast("int")))
    # ship-to store per order via broadcast join (no driver collect / array literal)
    orders = attach_random_dim(orders, store_dim, n_stores, "store", seed, "profile_id", "order_idx")

    lines = (orders
             .withColumn("line_idx", F.explode(F.expr("sequence(1, n_lines)")))
             .withColumn("units",
                         (F.abs(F.hash("profile_id", "order_idx", "line_idx", F.lit(seed))) % F.lit(5) + F.lit(1)).cast("int")))
    # product per line via broadcast join (attaches product_sk, product_id, list_price)
    lines = attach_random_dim(lines, prod_dim, n_products, "prod", seed, "profile_id", "order_idx", "line_idx")
    lines = (lines
             .withColumn("gross_amount", F.round(F.col("units") * F.col("list_price"), 2))
             # net = gross less a 0-20% discount draw
             .withColumn("net_amount",
                         F.round(F.col("gross_amount")
                                 * (F.lit(1.0) - _frac(seed, "disc", "profile_id", "order_idx", "line_idx") * F.lit(0.2)), 2))
             # Amounts are in the reporting/base currency; consumer orders are
             # transacted in the home market (= base).
             .withColumn("currency_code", F.lit(base_currency))
             .withColumn("transaction_currency_code", F.lit(base_currency))
             .withColumn("order_line_id",
                         F.concat_ws("-", F.lit("ORDL"), F.col("profile_id"), F.col("order_idx"), F.col("line_idx")))
             # Event-time (UTC): the order date plus a deterministic intraday hour.
             .withColumn("event_timestamp",
                         F.expr("cast(order_date as timestamp) + make_interval(0, 0, 0, 0, "
                                "cast(abs(hash(profile_id, order_idx, line_idx)) % 24 as int))"))
             .withColumn("record_source", F.lit(RECORD_SOURCE))
             .withColumn("load_timestamp", F.current_timestamp()))
    return lines


def build_payments(spark, order_lines, base_currency, seed):
    """One 'sale' payment per order (sum of its line net amounts) plus a small
    share of partial refunds — the tender/settlement side of the order fact."""
    orders = (order_lines.groupBy("order_id", "profile_sk", "profile_id")
              .agg(F.round(F.sum("net_amount"), 2).alias("amount"),
                   F.max("event_timestamp").alias("event_timestamp")))
    method = _pick(PAYMENT_METHODS, seed, "pm", "order_id")
    sale = (orders
            .withColumn("payment_type", F.lit("sale"))
            .withColumn("payment_status", F.lit("captured"))
            .withColumn("payment_method", method)
            .withColumn("payment_id", F.concat_ws("-", F.lit("PAY"), F.col("order_id"))))
    # ~12% of orders draw a partial refund a couple of days later.
    refund = (orders
              .where(_frac(seed, "refund", "order_id") < F.lit(0.12))
              .withColumn("amount", F.round(F.col("amount") * F.lit(0.3), 2))
              .withColumn("payment_type", F.lit("refund"))
              .withColumn("payment_status", F.lit("refunded"))
              .withColumn("payment_method", method)
              .withColumn("event_timestamp",
                          F.col("event_timestamp") + F.expr("make_interval(0, 0, 0, 2)"))
              .withColumn("payment_id", F.concat_ws("-", F.lit("PAYR"), F.col("order_id"))))
    return (sale.unionByName(refund)
            .withColumn("currency_code", F.lit(base_currency))
            .withColumn("transaction_currency_code", F.lit(base_currency))
            .withColumn("record_source", F.lit(RECORD_SOURCE))
            .withColumn("load_timestamp", F.current_timestamp()))


def generate(spark, catalog, schemas, cfg, mode, base_currency="USD"):
    if not catalog:
        raise ValueError("`catalog` parameter is required (guardrail #1: no hardcoded catalog).")

    def fq(schema, table):
        return f"{catalog}.{schemas[schema]}.{table}"

    seed = cfg["seed"]
    print(f"[ordm] generating Customer LTV orders into {catalog} "
          f"(max_orders={cfg['max_orders']}, value_skew={cfg['value_skew']}, seed={seed}, mode={mode})")

    profiles_current = spark.table(fq("customer", "profile")).where("is_current = true")
    products_current = spark.table(fq("product", "product")).where("is_current = true")
    stores_current = spark.table(fq("store", "store")).where("is_current = true")
    calendar_tbl = spark.table(fq("calendar", "fiscal_calendar"))
    cal = calendar_tbl.agg(F.min("date_key").alias("mn"), F.count(F.lit(1)).alias("cnt")).first()
    start_date, n_days = cal["mn"], int(cal["cnt"])

    lines = build_order_lines(spark, profiles_current, products_current, stores_current,
                              start_date, n_days, seed, cfg["max_orders"], cfg["value_skew"],
                              cfg["lines_per_order_max"], base_currency)
    _write(spark, lines, fq("order", "customer_order_line"), CUSTOMER_ORDER_LINE_COLUMNS, mode)

    # Payment events (tender/settlement side of the orders): sales + partial refunds.
    payments = build_payments(spark, lines, base_currency, seed)
    _write(spark, payments, fq("payment", "payment"), PAYMENT_COLUMNS, mode)
    print("[ordm] Customer LTV generation complete.")


def main():
    spark = SparkSession.builder.getOrCreate()
    cfg = load_config()
    catalog = get_param("catalog", "")
    schemas = {
        "customer": get_param("customer_schema", "customer"),
        "product": get_param("product_schema", "product"),
        "store": get_param("store_schema", "store"),
        "calendar": get_param("calendar_schema", "calendar"),
        "order": get_param("order_schema", "orders"),
        "payment": get_param("payment_schema", "payment"),
    }
    mode = get_param("mode", "overwrite")
    base_currency = get_param("base_currency", "USD")
    generate(spark, catalog, schemas, cfg, mode, base_currency)


if __name__ == "__main__":
    main()
