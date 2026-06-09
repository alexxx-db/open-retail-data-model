"""Tests for Category Growth (gold_category_growth).

Static contract tests + a DuckDB fixture running the REAL view: the four growth
effects reconcile to delta_revenue, category_share sums to ~1 per period, YoY
uses the correct fiscal-period comparison, and the view degrades gracefully
(rows returned, upstream-derived columns NULL) when an upstream view is empty.
"""

import os
import re

import pytest
import sqlglot
import sqlglot.expressions as E

from tools.ordm_config import resolve

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VIEW = os.path.join(REPO, "outcome-packages", "data-sharing-with-suppliers", "gold", "gold_category_growth.sql")


# ---------- static ----------

def test_view_parses_and_exposes_columns():
    create = next(s for s in sqlglot.parse(resolve(open(VIEW).read(), "c"), read="databricks", error_level="ignore")
                  if isinstance(s, E.Create))
    outputs = set(create.expression.named_selects)
    required = {"category", "fiscal_year", "fiscal_period", "category_revenue", "category_margin",
                "delta_revenue", "pop_growth_pct", "yoy_growth_pct", "distribution_effect",
                "volume_effect", "price_effect", "mix_effect", "category_share",
                "promo_contribution", "value_share_platinum", "supplier_top_share"}
    assert required <= outputs, f"missing: {sorted(required - outputs)}"


def test_no_banned_or_hardcoded():
    txt = open(VIEW).read()
    assert not re.search(r"GROUP\s+BY\s+ALL|\b1\s*=\s*1\b", txt, re.I)
    assert not re.search(r"https?://[\w.-]*databricks|retail_mvm|retail_ecm|Copyright|SPDX|Licensed under", txt, re.I)


# ---------- engine: DuckDB fixture running the real view ----------

_SUBS = [
    ("${catalog}.${transaction_schema}.sales", "sales"),
    ("${catalog}.${product_schema}.product", "product"),
    ("${catalog}.${calendar_schema}.fiscal_calendar", "fiscal_calendar"),
    ("${catalog}.${promo_schema}.gold_promo_roi_by_category", "gold_promo_roi_by_category"),
    ("${catalog}.${order_schema}.customer_order_line", "customer_order_line"),
    ("${catalog}.${acu_schema}.gold_customer_ltv", "gold_customer_ltv"),
    ("${catalog}.${procurement_schema}.purchase_order_line", "purchase_order_line"),
    ("${catalog}.${risk_schema}.gold_supplier_scorecard", "gold_supplier_scorecard"),
]


def _view_body():
    raw = open(VIEW).read()
    body = raw[raw.index(" AS", raw.index("CREATE OR REPLACE VIEW")) + 3:].strip().rstrip(";")
    for a, b in _SUBS:
        body = body.replace(a, b)
    return body.replace("AS STRING)", "AS VARCHAR)")   # Spark STRING -> DuckDB VARCHAR


def _con(populate_upstream=False):
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect()
    con.execute("CREATE TABLE product(product_sk INT, category VARCHAR, subcategory VARCHAR, unit_cost DECIMAL(18,2))")
    con.execute("INSERT INTO product VALUES (1,'bev','regular',4),(2,'bev','premium',8),(3,'snack','regular',3)")
    con.execute("CREATE TABLE fiscal_calendar(date_key DATE, fiscal_year INT, fiscal_period INT)")
    con.execute("INSERT INTO fiscal_calendar VALUES "
                "(DATE '2024-01-07',2024,1),(DATE '2024-02-07',2024,2),(DATE '2023-02-07',2023,2)")
    con.execute("CREATE TABLE sales(product_sk INT, store_sk INT, date_key DATE, units INT, net_revenue DECIMAL(18,2))")
    DA, DB = "DATE '2024-01-07'", "DATE '2024-02-07'"
    rows = [
        # period A (bev rev 300, units 25, dist 3 ; snack rev 40)
        (1, 1, DA, 10, 100), (1, 2, DA, 10, 100), (2, 1, DA, 5, 100), (3, 1, DA, 8, 40),
        # period B (bev rev 484, units 34, dist 4 ; snack rev 40)
        (1, 1, DB, 12, 132), (1, 2, DB, 12, 132), (2, 1, DB, 4, 88), (2, 2, DB, 6, 132), (3, 1, DB, 8, 40),
    ]
    for r in rows:
        con.execute(f"INSERT INTO sales VALUES ({r[0]},{r[1]},{r[2]},{r[3]},{r[4]})")
    # YoY prior year for bev (fy2023 fp2): one line
    con.execute(f"INSERT INTO sales VALUES (1,1,DATE '2023-02-07',10,90)")

    # upstream views (as tables) -- empty unless populated
    con.execute("CREATE TABLE gold_promo_roi_by_category(category VARCHAR, end_date DATE, incremental_margin DECIMAL(18,2))")
    con.execute("CREATE TABLE customer_order_line(profile_sk INT, product_sk INT, order_date DATE, net_amount DECIMAL(18,2))")
    con.execute("CREATE TABLE gold_customer_ltv(profile_sk INT, value_tier VARCHAR)")
    con.execute("CREATE TABLE purchase_order_line(supplier_id VARCHAR, product_sk INT, received_qty INT, unit_price DECIMAL(18,2))")
    con.execute("CREATE TABLE gold_supplier_scorecard(supplier_id VARCHAR, composite_score DOUBLE)")
    if populate_upstream:
        con.execute("INSERT INTO gold_promo_roi_by_category VALUES ('bev', DATE '2024-02-07', 25)")
        con.execute("INSERT INTO customer_order_line VALUES (1,1,DATE '2024-02-07',200),(2,2,DATE '2024-02-07',100)")
        con.execute("INSERT INTO gold_customer_ltv VALUES (1,'PLATINUM'),(2,'BRONZE')")
        con.execute("INSERT INTO purchase_order_line VALUES ('SUP1',1,100,5),('SUP2',2,40,5)")
        con.execute("INSERT INTO gold_supplier_scorecard VALUES ('SUP1',80),('SUP2',60)")
    con.execute("CREATE VIEW gold_category_growth AS " + _view_body())
    return con


def _bevB(con):
    return con.execute("""SELECT delta_revenue, distribution_effect, volume_effect, price_effect, mix_effect
                          FROM gold_category_growth
                          WHERE category='bev' AND fiscal_year=2024 AND fiscal_period=2""").fetchone()


def test_decomposition_reconciles_to_delta_revenue():
    con = _con()
    delta, dist, vol, price, mix = (float(x) for x in _bevB(con))
    assert delta == pytest.approx(184.0)
    assert (dist + vol + price + mix) == pytest.approx(delta, abs=1e-6)   # four effects reconcile
    # and the individual effects (hand-computed)
    assert dist == pytest.approx(100.0, abs=1e-6)
    assert vol == pytest.approx(8.0, abs=1e-6)
    assert price == pytest.approx(44.0, abs=1e-6)
    assert mix == pytest.approx(32.0, abs=1e-6)


def test_category_share_sums_to_one_per_period():
    con = _con()
    for fp in (1, 2):
        total = con.execute(f"SELECT SUM(category_share) FROM gold_category_growth "
                            f"WHERE fiscal_year=2024 AND fiscal_period={fp}").fetchone()[0]
        assert float(total) == pytest.approx(1.0, abs=1e-9)


def test_yoy_uses_fiscal_period_comparison():
    con = _con()
    # bev fp2 2024 (rev 484) vs fp2 2023 (rev 90) -> yoy = 100*(484-90)/90
    yoy = con.execute("SELECT yoy_growth_pct FROM gold_category_growth "
                      "WHERE category='bev' AND fiscal_year=2024 AND fiscal_period=2").fetchone()[0]
    assert float(yoy) == pytest.approx(100.0 * (484 - 90) / 90, abs=1e-6)
    # period 1 (2024 fp1) has no prior period -> pop NULL
    pop1 = con.execute("SELECT pop_growth_pct FROM gold_category_growth "
                       "WHERE category='bev' AND fiscal_year=2024 AND fiscal_period=1").fetchone()[0]
    assert pop1 is None


def test_graceful_degradation_when_upstream_absent():
    con = _con(populate_upstream=False)
    row = con.execute("""SELECT promo_contribution, value_share_platinum, top_supplier_id, supplier_top_share
                         FROM gold_category_growth WHERE category='bev' AND fiscal_period=2""").fetchone()
    assert all(v is None for v in row), f"expected NULL upstream columns when absent, got {row}"
    # still returns rows
    assert con.execute("SELECT COUNT(*) FROM gold_category_growth").fetchone()[0] > 0


def test_upstream_signals_populate_when_present():
    con = _con(populate_upstream=True)
    promo, vsp, top_sup, top_score = con.execute(
        """SELECT promo_contribution, value_share_platinum, top_supplier_id, supplier_top_score
           FROM gold_category_growth WHERE category='bev' AND fiscal_year=2024 AND fiscal_period=2""").fetchone()
    assert float(promo) == pytest.approx(25.0)
    assert float(vsp) == pytest.approx(200.0 / 300.0)   # PLATINUM 200 of 300 customer-attributed bev rev
    assert top_sup == 'SUP1'                             # SUP1 spend 500 > SUP2 200
    assert float(top_score) == pytest.approx(80.0)
