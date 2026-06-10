"""Tests for Customer Lifetime Value (gold_customer_ltv).

Static contract tests (incl. a PII-absence assertion on the gold schema) plus
Spark fixtures (the Databricks engine) running the REAL view: RFM quintile assignment, historical_clv
= sum of margin, predicted_clv reproduced from the documented heuristic, and
predicted_clv never negative.
"""

import ast
import os
import re

import pytest
import sqlglot
import sqlglot.expressions as E

from tools.ordm_config import resolve, view_select_body

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DDL = os.path.join(REPO, "canonical-core", "order", "tables", "customer_order_line.sql")
LTV = os.path.join(REPO, "outcome-packages", "actionable-customer-understanding", "gold", "gold_customer_ltv.sql")
GENERATOR = os.path.join(REPO, "synthetic-data", "generators", "customer_ltv.py")

PII_COLUMNS = {"loyalty_id", "household_id", "first_name", "middle_name", "last_name",
               "date_of_birth", "name_prefix", "name_suffix", "contact_value"}


def _outputs():
    # Parse the SELECT body (form-agnostic: gold_customer_ltv is a materialized view).
    sel = sqlglot.parse_one(view_select_body(resolve(open(LTV).read(), "c")),
                            read="databricks", error_level="ignore")
    return set(sel.named_selects)


# ---------- static ----------

def test_generator_columns_match_ddl():
    create = next(s for s in sqlglot.parse(resolve(open(DDL).read(), "c"), read="databricks", error_level="ignore")
                  if isinstance(s, E.Create))
    ddl = {c.name for c in create.find_all(E.ColumnDef) if c.name != "order_line_sk"}
    mod = ast.parse(open(GENERATOR).read())
    gen = {e.value for n in mod.body if isinstance(n, ast.Assign)
           and getattr(n.targets[0], "id", "") == "CUSTOMER_ORDER_LINE_COLUMNS" for e in n.value.elts}
    assert ddl == gen, f"drift: missing={sorted(ddl - gen)} extra={sorted(gen - ddl)}"


def test_view_exposes_required_columns():
    required = {"profile_sk", "recency_periods", "frequency", "total_spend", "avg_order_value",
                "historical_clv", "predicted_clv", "r_score", "f_score", "m_score", "rfm_score",
                "value_tier", "churn_risk_proxy"}
    assert required <= _outputs(), f"missing: {sorted(required - _outputs())}"


def test_no_raw_pii_in_gold_schema():
    # The PII-absence guarantee: no PII column appears in the view's output.
    leaked = PII_COLUMNS & _outputs()
    assert not leaked, f"gold view exposes raw PII: {sorted(leaked)}"
    assert "profile_sk" in _outputs(), "view must key on the customer surrogate"


def test_no_banned_or_hardcoded():
    txt = open(LTV).read()
    assert not re.search(r"GROUP\s+BY\s+ALL|\b1\s*=\s*1\b", txt, re.I)
    assert not re.search(r"https?://[\w.-]*databricks|retail_mvm|retail_ecm|Copyright|SPDX|Licensed under", txt, re.I)


# ---------- engine: Spark fixture running the real view ----------

import datetime

_SUBS = [
    ("${catalog}.${order_schema}.customer_order_line", "customer_order_line"),
    ("${catalog}.${product_schema}.product", "product"),
    ("${catalog}.${calendar_schema}.fiscal_calendar", "fiscal_calendar"),
]
_ORDER_SCHEMA = ("profile_sk int, profile_id string, order_id string, product_sk int, "
                 "order_date date, units int, net_amount double")


def _view_body():
    # The REAL gold SQL with UC names rewritten to fixture temp views; Spark runs it
    # verbatim. view_select_body handles the materialized-view header.
    body = view_select_body(open(LTV).read())
    for a, b in _SUBS:
        body = body.replace(a, b)
    return body


def _date(fp):
    # unique date per fiscal period (the value only matters as a join key)
    return datetime.date(2024, 1, 1) + datetime.timedelta(days=fp * 31)


def _build(spark, cal_fps, order_rows):
    spark.createDataFrame([(1, 6.0)], "product_sk int, unit_cost double").createOrReplaceTempView("product")
    spark.createDataFrame([(_date(fp), 2024, fp) for fp in cal_fps],
                          "date_key date, fiscal_year int, fiscal_period int").createOrReplaceTempView("fiscal_calendar")
    spark.createDataFrame(order_rows, _ORDER_SCHEMA).createOrReplaceTempView("customer_order_line")
    spark.sql("CREATE OR REPLACE TEMP VIEW gold_customer_ltv AS " + _view_body())


def _rfm_build(spark):
    # 5 customers: frequency & spend increase C1..C5; recency increases C1..C5
    # (C1 most recent). One product, units=2, net=50 -> margin/order = 38.
    plan = {1: (1, 10), 2: (2, 9), 3: (3, 8), 4: (4, 7), 5: (5, 6)}  # profile_sk: (orders, last_fp)
    rows = [(sk, f"C{sk}", f"C{sk}-O{o}", 1, _date(fp), 2, 50.0)
            for sk, (n_orders, fp) in plan.items() for o in range(1, n_orders + 1)]
    _build(spark, (6, 7, 8, 9, 10), rows)


def test_one_row_per_customer(spark):
    _rfm_build(spark)
    assert spark.sql("SELECT COUNT(*) AS n FROM gold_customer_ltv").first().n == 5


def test_rfm_quintiles_assigned(spark):
    _rfm_build(spark)
    c1 = spark.sql("SELECT r_score,f_score,m_score,rfm_score FROM gold_customer_ltv WHERE profile_id='C1'").first()
    c5 = spark.sql("SELECT r_score,f_score,m_score,rfm_score FROM gold_customer_ltv WHERE profile_id='C5'").first()
    # C1: most recent (R=5) but fewest orders/spend (F=1,M=1)
    assert tuple(c1) == (5, 1, 1, 511)
    # C5: most dormant (R=1) but most orders/spend (F=5,M=5)
    assert tuple(c5) == (1, 5, 5, 155)


def test_value_tier_spread_and_historical_clv(spark):
    _rfm_build(spark)
    tiers = {r.profile_id: r.value_tier for r in
             spark.sql("SELECT profile_id, value_tier FROM gold_customer_ltv").collect()}
    assert tiers['C5'] == 'PLATINUM' and tiers['C1'] == 'BRONZE'
    assert spark.sql("SELECT COUNT(DISTINCT value_tier) AS n FROM gold_customer_ltv").first().n == 4
    # historical_clv(C3) = 3 orders * (50 - 2*6) = 114
    clv3 = float(spark.sql("SELECT historical_clv FROM gold_customer_ltv WHERE profile_id='C3'").first()[0])
    assert clv3 == pytest.approx(114.0)


def test_predicted_clv_reproduces_from_inputs(spark):
    # CP: 4 orders one per period (10..13); a later dummy order (CD) sets the
    # current period to 16 so recency = 3, tenure = 7.
    rows = [(1, "CP", f"CP-O{o}", 1, _date(fp), 2, 50.0) for o, fp in enumerate([10, 11, 12, 13], start=1)]
    rows.append((9, "CD", "CD-O1", 1, _date(16), 2, 50.0))
    _build(spark, (10, 11, 12, 13, 16), rows)
    pred = float(spark.sql("SELECT predicted_clv FROM gold_customer_ltv WHERE profile_id='CP'").first()[0])
    # avg_order_margin=38 ; freq_per_period=4/7 ; expected_active=min(7,12)-3=4
    expected = 38 * (4 / 7) * 4
    assert pred == pytest.approx(expected, abs=1e-6)


def test_predicted_clv_never_negative(spark):
    # net 30 < units(10) * unit_cost(6)=60 -> margin -30 (realized loss is real)
    _build(spark, (10,), [(1, "CN", "CN-O1", 1, _date(10), 10, 30.0)])
    hist, pred = spark.sql(
        "SELECT historical_clv, predicted_clv FROM gold_customer_ltv WHERE profile_id='CN'").first()
    assert float(hist) == pytest.approx(-30.0)   # historical can be negative
    assert float(pred) == pytest.approx(0.0)     # predicted is clamped to >= 0
