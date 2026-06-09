"""Tests for Customer Lifetime Value (gold_customer_ltv).

Static contract tests (incl. a PII-absence assertion on the gold schema) plus
DuckDB fixtures running the REAL view: RFM quintile assignment, historical_clv
= sum of margin, predicted_clv reproduced from the documented heuristic, and
predicted_clv never negative.
"""

import ast
import os
import re

import pytest
import sqlglot
import sqlglot.expressions as E

from tools.ordm_config import resolve

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DDL = os.path.join(REPO, "canonical-core", "order", "tables", "customer_order_line.sql")
LTV = os.path.join(REPO, "outcome-packages", "actionable-customer-understanding", "gold", "gold_customer_ltv.sql")
GENERATOR = os.path.join(REPO, "synthetic-data", "generators", "customer_ltv.py")

PII_COLUMNS = {"loyalty_id", "household_id", "first_name", "middle_name", "last_name",
               "date_of_birth", "name_prefix", "name_suffix", "contact_value"}


def _outputs():
    raw = resolve(open(LTV).read(), "c")
    create = next(s for s in sqlglot.parse(raw, read="databricks", error_level="ignore")
                  if isinstance(s, E.Create))
    return set(create.expression.named_selects)


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


# ---------- engine: DuckDB fixture running the real view ----------

_SUBS = [
    ("${catalog}.${order_schema}.customer_order_line", "customer_order_line"),
    ("${catalog}.${product_schema}.product", "product"),
    ("${catalog}.${calendar_schema}.fiscal_calendar", "fiscal_calendar"),
]


def _view_body():
    raw = open(LTV).read()
    body = raw[raw.index(" AS", raw.index("CREATE OR REPLACE VIEW")) + 3:].strip().rstrip(";")
    for a, b in _SUBS:
        body = body.replace(a, b)
    return body


def _con():
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect()
    con.execute("CREATE TABLE product(product_sk INT, unit_cost DECIMAL(18,2))")
    con.execute("INSERT INTO product VALUES (1, 6)")     # margin/unit at net 50,units 2 -> 50-12=38
    con.execute("CREATE TABLE fiscal_calendar(date_key DATE, fiscal_year INT, fiscal_period INT)")
    con.execute("CREATE TABLE customer_order_line(profile_sk INT, profile_id VARCHAR, order_id VARCHAR, "
                "product_sk INT, order_date DATE, units INT, net_amount DECIMAL(18,2))")
    return con


def _cal(con, fp):
    d = f"DATE '2024-01-01' + INTERVAL {fp} MONTH"
    con.execute(f"INSERT INTO fiscal_calendar VALUES ({d}, 2024, {fp})")
    return d


def _rfm_fixture():
    con = _con()
    # 5 customers: frequency & spend increase C1..C5; recency increases C1..C5
    # (C1 most recent). One product, units=2, net=50 -> margin/order = 38.
    dates = {fp: _cal(con, fp) for fp in (6, 7, 8, 9, 10)}
    plan = {  # profile_sk: (orders, last_fp)
        1: (1, 10), 2: (2, 9), 3: (3, 8), 4: (4, 7), 5: (5, 6),
    }
    for sk, (n_orders, fp) in plan.items():
        for o in range(1, n_orders + 1):
            con.execute(f"INSERT INTO customer_order_line VALUES "
                        f"({sk},'C{sk}','C{sk}-O{o}',1,{dates[fp]},2,50)")
    con.execute("CREATE VIEW gold_customer_ltv AS " + _view_body())
    return con


def test_one_row_per_customer():
    con = _rfm_fixture()
    assert con.execute("SELECT COUNT(*) FROM gold_customer_ltv").fetchone()[0] == 5


def test_rfm_quintiles_assigned():
    con = _rfm_fixture()
    c1 = con.execute("SELECT r_score,f_score,m_score,rfm_score FROM gold_customer_ltv WHERE profile_id='C1'").fetchone()
    c5 = con.execute("SELECT r_score,f_score,m_score,rfm_score FROM gold_customer_ltv WHERE profile_id='C5'").fetchone()
    # C1: most recent (R=5) but fewest orders/spend (F=1,M=1)
    assert tuple(c1) == (5, 1, 1, 511)
    # C5: most dormant (R=1) but most orders/spend (F=5,M=5)
    assert tuple(c5) == (1, 5, 5, 155)


def test_value_tier_spread_and_historical_clv():
    con = _rfm_fixture()
    tiers = {r[0]: r[1] for r in con.execute(
        "SELECT profile_id, value_tier FROM gold_customer_ltv").fetchall()}
    assert tiers['C5'] == 'PLATINUM' and tiers['C1'] == 'BRONZE'
    assert con.execute("SELECT COUNT(DISTINCT value_tier) FROM gold_customer_ltv").fetchone()[0] == 4
    # historical_clv(C3) = 3 orders * (50 - 2*6) = 114
    clv3 = float(con.execute("SELECT historical_clv FROM gold_customer_ltv WHERE profile_id='C3'").fetchone()[0])
    assert clv3 == pytest.approx(114.0)


def test_predicted_clv_reproduces_from_inputs():
    con = _con()
    # One customer, 4 orders one per period (10..13); a later dummy order sets the
    # current period to 16 so recency = 3, tenure = 7.
    dates = {fp: _cal(con, fp) for fp in (10, 11, 12, 13, 16)}
    for o, fp in enumerate([10, 11, 12, 13], start=1):
        con.execute(f"INSERT INTO customer_order_line VALUES (1,'CP','CP-O{o}',1,{dates[fp]},2,50)")
    con.execute(f"INSERT INTO customer_order_line VALUES (9,'CD','CD-O1',1,{dates[16]},2,50)")
    con.execute("CREATE VIEW gold_customer_ltv AS " + _view_body())
    pred = float(con.execute("SELECT predicted_clv FROM gold_customer_ltv WHERE profile_id='CP'").fetchone()[0])
    # avg_order_margin=38 ; freq_per_period=4/7 ; expected_active=min(7,12)-3=4
    expected = 38 * (4 / 7) * 4
    assert pred == pytest.approx(expected, abs=1e-6)


def test_predicted_clv_never_negative():
    con = _con()
    d = _cal(con, 10)
    # net 30 < units(10) * unit_cost(6)=60 -> margin -30 (realized loss is real)
    con.execute(f"INSERT INTO customer_order_line VALUES (1,'CN','CN-O1',1,{d},10,30)")
    con.execute("CREATE VIEW gold_customer_ltv AS " + _view_body())
    hist, pred = con.execute(
        "SELECT historical_clv, predicted_clv FROM gold_customer_ltv WHERE profile_id='CN'").fetchone()
    assert float(hist) == pytest.approx(-30.0)   # historical can be negative
    assert float(pred) == pytest.approx(0.0)     # predicted is clamped to >= 0
