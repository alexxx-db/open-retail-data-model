"""Tests for Procurement Risk Detection (gold_procurement_risk).

Static contract tests + a DuckDB fixture running the REAL view to prove the
multi-factor logic: a deteriorating-but-currently-OK supplier surfaces via
trend (independent of its current score), a sole-source supplier is flagged
(and escalated to HIGH even with a low blended score), HHI math is correct,
and top_risk_factors reflects the actual top contributors.
"""

import os
import re

import pytest
import sqlglot
import sqlglot.expressions as E

from tools.ordm_config import resolve

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RISK = os.path.join(REPO, "outcome-packages", "early-risk-detection", "gold", "gold_procurement_risk.sql")


# ---------- static ----------

def test_view_parses_and_exposes_columns():
    raw = resolve(open(RISK).read(), "c")
    create = next(s for s in sqlglot.parse(raw, read="databricks", error_level="ignore")
                  if isinstance(s, E.Create))
    outputs = set(create.expression.named_selects)
    required = {"supplier_id", "performance_risk", "trend_risk", "concentration_risk",
                "concentration_hhi", "single_source_flag", "single_sourced_sku_count",
                "geo_risk", "geo_concentration_flag", "risk_score", "risk_tier", "top_risk_factors"}
    assert required <= outputs, f"missing: {sorted(required - outputs)}"


def test_no_banned_or_hardcoded():
    txt = open(RISK).read()
    assert not re.search(r"GROUP\s+BY\s+ALL|\b1\s*=\s*1\b", txt, re.I)
    assert not re.search(r"https?://[\w.-]*databricks|retail_mvm|retail_ecm|Copyright|SPDX|Licensed under", txt, re.I)


# ---------- engine: DuckDB fixture running the real view ----------

_SUBS = [
    ("${catalog}.${risk_schema}.gold_supplier_scorecard", "gold_supplier_scorecard"),
    ("${catalog}.${supplier_schema}.supplier", "supplier"),
    ("${catalog}.${procurement_schema}.purchase_order_line", "purchase_order_line"),
    ("${catalog}.${product_schema}.product", "product"),
]


def _view_body():
    raw = open(RISK).read()
    body = raw[raw.index(" AS", raw.index("CREATE OR REPLACE VIEW")) + 3:].strip().rstrip(";")
    for a, b in _SUBS:
        body = body.replace(a, b)
    return body


def _fixture():
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect()
    con.execute("CREATE TABLE supplier(supplier_sk INT, supplier_id VARCHAR, supplier_name VARCHAR, "
                "country_code VARCHAR, current_flag BOOLEAN)")
    con.execute("INSERT INTO supplier VALUES (1,'S1','S1','US',true),(2,'S2','S2','DE',true),(3,'S3','S3','US',true)")
    con.execute("CREATE TABLE product(product_sk INT, product_id VARCHAR, category VARCHAR, current_flag BOOLEAN)")
    con.execute("INSERT INTO product VALUES (1,'PA','bev',true),(3,'EX1','snack',true),(4,'PC','snack',true)")
    # scorecard history: S1 declines (98,95,92,85 -> current 70); S2/S3 single current period
    con.execute("CREATE TABLE gold_supplier_scorecard(supplier_sk INT, supplier_id VARCHAR, "
                "fiscal_year INT, fiscal_period INT, composite_score DOUBLE)")
    for fp, cs in [(1, 98), (2, 95), (3, 92), (4, 85), (5, 70)]:
        con.execute(f"INSERT INTO gold_supplier_scorecard VALUES (1,'S1',2024,{fp},{cs})")
    con.execute("INSERT INTO gold_supplier_scorecard VALUES (2,'S2',2024,5,95)")
    con.execute("INSERT INTO gold_supplier_scorecard VALUES (3,'S3',2024,5,90)")
    # spend (received_qty x unit_price); unit_price=1 so received_qty = spend
    con.execute("CREATE TABLE purchase_order_line(supplier_id VARCHAR, product_id VARCHAR, product_sk INT, "
                "received_qty INT, unit_price DECIMAL(18,2))")
    con.executemany("INSERT INTO purchase_order_line VALUES (?,?,?,?,1)", [
        ('S1', 'PA', 1, 400),    # bev: S1 400
        ('S3', 'PA', 1, 600),    # bev: S3 600 (PA multi-sourced)
        ('S2', 'EX1', 3, 500),   # snack: EX1 SOLE-sourced by S2
        ('S3', 'PC', 4, 150),    # snack: S3
        ('S1', 'PC', 4, 50),     # snack: S1 (PC multi-sourced)
    ])
    con.execute("CREATE VIEW gold_procurement_risk AS " + _view_body())
    return con


def _row(con, sid):
    cols = ("performance_risk,trend_risk,concentration_risk,concentration_hhi,single_source_flag,"
            "single_sourced_sku_count,risk_score,risk_tier,top_risk_factors")
    return con.execute(f"SELECT {cols} FROM gold_procurement_risk WHERE supplier_id='{sid}'").fetchone()


def test_returns_one_row_per_supplier():
    con = _fixture()
    assert con.execute("SELECT COUNT(*) FROM gold_procurement_risk").fetchone()[0] == 3


def test_trend_risk_surfaces_declining_supplier():
    con = _fixture()
    perf, trend, conc, hhi, ss_flag, ss_cnt, score, tier, factors = _row(con, 'S1')
    # current composite 70 (OK -> perf_risk 30); trailing mean 92.5 -> delta -22.5 -> trend_risk 75
    assert float(trend) == pytest.approx(75.0)
    assert float(perf) == pytest.approx(30.0)        # current score is NOT the dominant driver
    assert tier in ("HIGH", "CRITICAL")
    assert "trend" in factors                         # trend is a top contributor
    assert not ss_flag                                # NOT driven by single-source


def test_single_source_flagged_and_escalates():
    con = _fixture()
    perf, trend, conc, hhi, ss_flag, ss_cnt, score, tier, factors = _row(con, 'S2')
    assert ss_flag is True
    assert ss_cnt == 1
    assert tier == "HIGH"
    assert float(score) < 50                          # blended score alone = MEDIUM; the flag escalated it
    assert "single_source" in factors


def test_hhi_math():
    con = _fixture()
    # snack HHI = (500^2 + 150^2 + 50^2) / 700^2 = 0.561224 ; S2 only serves snack
    hhi_s2 = float(_row(con, 'S2')[3])
    assert hhi_s2 == pytest.approx(0.561224, abs=1e-5)
    # bev HHI = (400^2 + 600^2)/1000^2 = 0.52 ; S1 weighted across bev(400)+snack(50)
    hhi_s1 = float(_row(con, 'S1')[3])
    expected_s1 = (400 * 0.52 + 50 * 0.561224) / 450
    assert hhi_s1 == pytest.approx(expected_s1, abs=1e-5)


def test_single_source_only_where_sole():
    con = _fixture()
    assert _row(con, 'S1')[4] is False    # S1 sources only multi-sourced SKUs
    assert _row(con, 'S2')[4] is True     # S2 sole-sources EX1


def test_hhi_in_unit_range_all_rows():
    con = _fixture()
    bad = con.execute("SELECT COUNT(*) FROM gold_procurement_risk "
                      "WHERE concentration_hhi < 0 OR concentration_hhi > 1").fetchone()[0]
    assert bad == 0
