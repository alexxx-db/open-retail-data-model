"""Tests for the Post-Promotion ROI use case.

Static contract tests keep the gold views consistent and guardrail-clean.
Engine tests run the REAL gold SQL (gold_weekly_baseline -> gold_promo_roi_by_category
-> gold_promo_roi) against an in-process DuckDB fixture with hand-computed
expectations, proving the ROI math, cannibalization and forward-buy detection,
and the divide-by-zero -> NULL path.
"""

import os
import re

import pytest
import sqlglot
import sqlglot.expressions as E

from tools.ordm_config import resolve

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GOLD = os.path.join(REPO, "outcome-packages", "promote-with-purpose", "gold")
WB = os.path.join(GOLD, "gold_weekly_baseline.sql")
BYCAT = os.path.join(GOLD, "gold_promo_roi_by_category.sql")
ROI = os.path.join(GOLD, "gold_promo_roi.sql")
PERF = os.path.join(GOLD, "gold_promo_performance.sql")
PRODUCT_DDL = os.path.join(REPO, "canonical-core", "product", "tables", "product.sql")


# ---------- static ----------

@pytest.mark.parametrize("path", [WB, BYCAT, ROI, PERF])
def test_view_parses(path):
    raw = resolve(open(path).read(), "c")
    create = next((s for s in sqlglot.parse(raw, read="databricks", error_level="ignore")
                   if isinstance(s, E.Create)), None)
    assert create is not None, f"{os.path.basename(path)} did not parse as CREATE VIEW"


def test_roi_view_exposes_required_columns():
    raw = resolve(open(ROI).read(), "c")
    create = next(s for s in sqlglot.parse(raw, read="databricks", error_level="ignore")
                  if isinstance(s, E.Create))
    outputs = set(create.expression.named_selects)
    required = {"promo_id", "baseline_units", "baseline_revenue", "baseline_margin",
                "incremental_units", "incremental_revenue", "incremental_margin",
                "trade_spend", "roi", "planned_lift_pct", "realized_lift_pct",
                "cannibalization_units", "cannibalization_margin",
                "forward_buy_units", "forward_buy_margin", "net_incremental_margin"}
    assert required <= outputs, f"gold_promo_roi missing: {sorted(required - outputs)}"


def test_margin_source_present():
    cols = open(PRODUCT_DDL).read()
    assert re.search(r"\bunit_cost\b", cols), "product is missing unit_cost (margin source)"


def test_no_banned_or_hardcoded_in_gold():
    bad = []
    for f in os.listdir(GOLD):
        if not f.endswith(".sql"):
            continue
        txt = open(os.path.join(GOLD, f)).read()
        if re.search(r"GROUP\s+BY\s+ALL|\b1\s*=\s*1\b", txt, re.I) \
           or re.search(r"https?://[\w.-]*databricks|retail_mvm|retail_ecm|Copyright|SPDX|Licensed under", txt, re.I):
            bad.append(f)
    assert not bad, f"banned pattern / hardcoded id / license header in: {bad}"


# ---------- engine: DuckDB fixture running the real ROI SQL ----------

_SUBS = [
    ("${catalog}.${transaction_schema}.sales", "sales"),
    ("${catalog}.${calendar_schema}.fiscal_calendar", "fiscal_calendar"),
    ("${catalog}.${product_schema}.product", "product"),
    ("${catalog}.${promo_schema}.promotion_scope", "promotion_scope"),
    ("${catalog}.${promo_schema}.gold_weekly_baseline", "gold_weekly_baseline"),
    ("${catalog}.${promo_schema}.gold_promo_roi_by_category", "gold_promo_roi_by_category"),
    ("${catalog}.${promo_schema}.promotion", "promotion"),
]


def _view_body(path):
    raw = open(path).read()
    body = raw[raw.index(" AS", raw.index("CREATE OR REPLACE VIEW")) + 3:].strip().rstrip(";")
    for a, b in _SUBS:
        body = body.replace(a, b)
    return body


def _fixture():
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect()
    con.execute("CREATE TABLE product(product_sk INT, product_id VARCHAR, category VARCHAR, "
                "list_price DECIMAL(18,2), unit_cost DECIMAL(18,2), current_flag BOOLEAN)")
    con.execute("INSERT INTO product VALUES (1,'P1','bev',10,6,true),(2,'P2','bev',10,6,true),(3,'P3','snack',10,6,true)")
    con.execute("CREATE TABLE fiscal_calendar(date_key DATE, fiscal_week_id INT, fiscal_week_index INT)")
    for wk in range(1, 16):
        con.execute(f"INSERT INTO fiscal_calendar VALUES (DATE '2024-01-07' + INTERVAL {(wk-1)*7} DAY, {202400+wk}, {wk})")
    con.execute("""CREATE TABLE promotion(promo_sk INT, promo_id VARCHAR, promo_name VARCHAR, promo_type VARCHAR,
        funding_type VARCHAR, funded_by VARCHAR, start_date DATE, end_date DATE, planned_trade_spend DECIMAL(18,2),
        planned_lift_pct DECIMAL(6,2), fiscal_week_start INT, fiscal_week_end INT, current_flag BOOLEAN)""")
    con.execute("INSERT INTO promotion VALUES (99,'NO_PROMO','No Promotion',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,true)")
    con.execute("INSERT INTO promotion VALUES (1,'PR1','Promo 1','TPR','SCAN_DOWN','SHARED',"
                "DATE '2024-03-10',DATE '2024-03-23',100,50,202410,202411,true)")
    con.execute("INSERT INTO promotion VALUES (2,'PR2','Promo 2','FEATURE','BILL_BACK','SUPPLIER',"
                "DATE '2024-02-04',DATE '2024-02-10',0,30,202405,202405,true)")
    con.execute("CREATE TABLE promotion_scope(promo_sk INT, product_sk INT, store_sk INT)")
    con.execute("INSERT INTO promotion_scope VALUES (1,1,1),(2,3,1)")
    con.execute("CREATE TABLE sales(product_sk INT, store_sk INT, promo_id VARCHAR, date_key DATE, units INT, net_revenue DECIMAL(18,2))")

    def ins(product_sk, wk, promo_id, units, net):
        d = f"DATE '2024-01-07' + INTERVAL {(wk-1)*7} DAY"
        con.execute(f"INSERT INTO sales VALUES ({product_sk},1,'{promo_id}',{d},{units},{net})")

    for wk in range(1, 16):
        # P1: normal, then promoted weeks 10-11, then forward-buy dip 12-13, then normal
        if wk in (10, 11):
            ins(1, wk, 'PR1', 15, 135)          # promoted (10% off): 15 units, net 135
        elif wk in (12, 13):
            ins(1, wk, 'NO_PROMO', 4, 40)        # forward-buy dip below baseline (~10)
        else:
            ins(1, wk, 'NO_PROMO', 10, 100)
        # P2: substitute (bev), cannibalized during PR1 window 10-11
        if wk in (10, 11):
            ins(2, wk, 'NO_PROMO', 5, 50)        # cannibalization dip below baseline
        else:
            ins(2, wk, 'NO_PROMO', 10, 100)
        # P3: promoted by PR2 (zero trade spend) week 5
        if wk == 5:
            ins(3, wk, 'PR2', 12, 108)
        else:
            ins(3, wk, 'NO_PROMO', 10, 100)

    con.execute("CREATE VIEW gold_weekly_baseline AS " + _view_body(WB))
    con.execute("CREATE VIEW gold_promo_roi_by_category AS " + _view_body(BYCAT))
    con.execute("CREATE VIEW gold_promo_roi AS " + _view_body(ROI))
    return con


def test_roi_returns_rows():
    con = _fixture()
    n = con.execute("SELECT COUNT(*) FROM gold_promo_roi").fetchone()[0]
    assert n == 2, f"expected PR1 and PR2, got {n}"


def test_roi_math_known_values():
    con = _fixture()
    row = con.execute("""SELECT incremental_margin, trade_spend, roi
                         FROM gold_promo_roi WHERE promo_id='PR1'""").fetchone()
    inc_margin, spend, roi = (float(x) for x in row)
    # promoted_margin = 2*(135 - 15*6) = 90 ; baseline_margin = 20 units * (10-6) = 80
    assert inc_margin == pytest.approx(10.0), inc_margin
    assert spend == pytest.approx(100.0), spend
    assert roi == pytest.approx(0.10), roi          # 10 / 100


def test_cannibalization_detected():
    con = _fixture()
    cu, cm = con.execute("""SELECT cannibalization_units, cannibalization_margin
                            FROM gold_promo_roi WHERE promo_id='PR1'""").fetchone()
    # P2 dip: wk10 (10-5)=5, wk11 (9.375-5)=4.375 -> 9.375 units ; margin 9.375*4 = 37.5
    assert float(cu) == pytest.approx(9.375), cu
    assert float(cm) == pytest.approx(37.5), cm


def test_forward_buy_detected():
    con = _fixture()
    fu, fm = con.execute("""SELECT forward_buy_units, forward_buy_margin
                            FROM gold_promo_roi WHERE promo_id='PR1'""").fetchone()
    # P1 post weeks 12,13: (10-4)=6 + (9-4)=5 -> 11 units ; margin 11*4 = 44
    assert float(fu) == pytest.approx(11.0), fu
    assert float(fm) == pytest.approx(44.0), fm


def test_net_incremental_margin_goes_negative():
    con = _fixture()
    net = con.execute("SELECT net_incremental_margin FROM gold_promo_roi WHERE promo_id='PR1'").fetchone()[0]
    # 10 (incremental) - 37.5 (cannib) - 44 (forward buy) = -71.5
    assert float(net) == pytest.approx(-71.5), net
    any_neg = con.execute("SELECT COUNT(*) FROM gold_promo_roi WHERE net_incremental_margin < 0").fetchone()[0]
    assert any_neg >= 1


def test_divide_by_zero_returns_null():
    con = _fixture()
    roi = con.execute("SELECT roi FROM gold_promo_roi WHERE promo_id='PR2'").fetchone()[0]
    assert roi is None, f"zero trade spend must yield NULL roi, got {roi}"
