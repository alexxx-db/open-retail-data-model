"""Tests for the Trade Promotion use case.

Static contract tests (no engine) keep the DDL, generator, DQ checks and the
gold view mutually consistent. Engine tests use an in-process DuckDB fixture
to validate the *real* gold SQL logic — promotion attribution, the trailing
non-promoted baseline (including the < 4 weeks -> NULL rule), and that the
gold view returns rows on a representative dataset.
"""

import ast
import glob
import os
import re

import pytest
import sqlglot
import sqlglot.expressions as E

from tools.ordm_config import resolve

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GENERATOR = os.path.join(REPO, "synthetic-data", "generators", "trade_promotion.py")
GOLD = os.path.join(REPO, "outcome-packages", "promote-with-purpose", "gold", "gold_trade_promotion.sql")

# table -> (ddl path, surrogate key, generator *_COLUMNS constant)
TABLES = {
    "product": ("canonical-core/product/tables/product.sql", "product_sk", "PRODUCT_COLUMNS"),
    "store": ("canonical-core/store/tables/store.sql", "store_sk", "STORE_COLUMNS"),
    "fiscal_calendar": ("canonical-core/calendar/tables/fiscal_calendar.sql", "calendar_sk", "FISCAL_CALENDAR_COLUMNS"),
    "sales": ("canonical-core/transaction/tables/sales.sql", "sales_sk", "SALES_COLUMNS"),
    "promotion": ("outcome-packages/promote-with-purpose/tables/promotion.sql", "promo_sk", "PROMOTION_COLUMNS"),
    "promotion_scope": ("outcome-packages/promote-with-purpose/tables/promotion_scope.sql", "scope_sk", "PROMOTION_SCOPE_COLUMNS"),
}
COMMENT_LINE = re.compile(r"^\s*([a-z][a-z0-9_]*)\s+[A-Za-z].*?COMMENT\s+'([^']*)'")
ALLOWED_VALUES = re.compile(r"Allowed values:\s*([^.]+)\.")


# ---------- helpers ----------

def _detok(text):
    # Resolve ${catalog}/${*_schema} to real identifiers via the shared resolver.
    return resolve(text, "ordm")


def _ddl(table):
    return _detok(open(os.path.join(REPO, TABLES[table][0])).read())


def _ddl_columns(table):
    create = next(s for s in sqlglot.parse(_ddl(table), read="databricks", error_level="ignore")
                  if isinstance(s, E.Create))
    sk = TABLES[table][1]
    return [c.name for c in create.find_all(E.ColumnDef) if c.name != sk]


def _col_comments(table):
    out = {}
    for line in _ddl(table).splitlines():
        m = COMMENT_LINE.match(line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def _generator_constants():
    mod = ast.parse(open(GENERATOR).read())
    out = {}
    for node in mod.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.List) \
                and all(isinstance(e, ast.Constant) for e in node.value.elts):
            out[node.targets[0].id] = [e.value for e in node.value.elts]
    return out


# ---------- static: DDL / generator / enums ----------

@pytest.mark.parametrize("table", list(TABLES))
def test_ddl_parses_as_create(table):
    create = next((s for s in sqlglot.parse(_ddl(table), read="databricks", error_level="ignore")
                   if isinstance(s, E.Create)), None)
    assert create is not None, f"{table} did not parse as CREATE TABLE"


@pytest.mark.parametrize("table", list(TABLES))
def test_generator_columns_match_ddl(table):
    gen = set(_generator_constants()[TABLES[table][2]])
    ddl = set(_ddl_columns(table))
    assert gen == ddl, f"{table} drift — missing={sorted(ddl - gen)} extra={sorted(gen - ddl)}"


ENUM_COLUMN_TO_CONST = {
    ("promotion", "promo_type"): "PROMO_TYPES",
    ("promotion", "funding_type"): "FUNDING_TYPES",
    ("promotion", "funded_by"): "FUNDED_BY",
    ("product", "product_status"): "PRODUCT_STATUS",
    ("product", "unit_of_measure"): "UNITS_OF_MEASURE",
    ("store", "store_format"): "STORE_FORMATS",
    ("store", "store_status"): "STORE_STATUS",
}


@pytest.mark.parametrize("key", list(ENUM_COLUMN_TO_CONST))
def test_generator_enum_within_ddl_domain(key):
    table, column = key
    gen = set(_generator_constants()[ENUM_COLUMN_TO_CONST[key]])
    m = ALLOWED_VALUES.search(_col_comments(table).get(column, ""))
    assert m, f"{table}.{column} has no 'Allowed values:' enum in the DDL comment"
    ddl_vals = {v.strip() for v in m.group(1).split(",")}
    assert gen <= ddl_vals, f"{table}.{column}: generator emits {sorted(gen - ddl_vals)} outside the DDL enum"


def test_sales_fact_has_promo_attribution_fk():
    # Acceptance: the sales fact carries promo_sk.
    assert "promo_sk" in set(_ddl_columns("sales")), "sales fact is missing the promo_sk attribution FK"


def test_gold_view_exposes_required_columns():
    raw = _detok(open(GOLD).read())
    create = next(s for s in sqlglot.parse(raw, read="databricks", error_level="ignore")
                  if isinstance(s, E.Create))
    outputs = set(create.expression.named_selects)
    required = {"promo_id", "promo_type", "funding_type", "funded_by", "product_id",
                "category", "store_id", "fiscal_week_id", "promoted_units",
                "promoted_revenue", "planned_trade_spend", "planned_lift_pct", "baseline_units"}
    assert required <= outputs, f"gold view missing columns: {sorted(required - outputs)}"


# ---------- guardrails on the new SQL ----------

NEW_SQL = (glob.glob(os.path.join(REPO, "canonical-core", "product", "**", "*.sql"), recursive=True)
           + glob.glob(os.path.join(REPO, "canonical-core", "store", "**", "*.sql"), recursive=True)
           + glob.glob(os.path.join(REPO, "canonical-core", "calendar", "**", "*.sql"), recursive=True)
           + glob.glob(os.path.join(REPO, "canonical-core", "transaction", "**", "*.sql"), recursive=True)
           + glob.glob(os.path.join(REPO, "outcome-packages", "promote-with-purpose", "**", "*.sql"), recursive=True))


def test_no_banned_sql_patterns():
    pat = re.compile(r"GROUP\s+BY\s+ALL|\b1\s*=\s*1\b", re.I)
    bad = [os.path.relpath(f, REPO) for f in NEW_SQL if pat.search(open(f).read())]
    assert not bad, f"banned SQL pattern (guardrail #5): {bad}"


def test_no_hardcoded_or_license():
    pat = re.compile(r"https?://[\w.-]*databricks|retail_mvm|retail_ecm|Copyright|SPDX|Licensed under", re.I)
    bad = [os.path.relpath(f, REPO) for f in NEW_SQL if pat.search(open(f).read())]
    assert not bad, f"hardcoded identifier or license header (guardrail #1/#4): {bad}"


# ---------- engine: DuckDB fixture for the real gold SQL ----------

def _gold_body_for_duckdb():
    raw = open(GOLD).read()
    body = raw[raw.index(" AS", raw.index("CREATE OR REPLACE VIEW")) + 3:].strip().rstrip(";")
    repl = [
        ("${catalog}.${transaction_schema}.sales", "sales"),
        ("${catalog}.${calendar_schema}.fiscal_calendar", "fiscal_calendar"),
        ("${catalog}.${promo_schema}.promotion_scope", "promotion_scope"),
        ("${catalog}.${promo_schema}.promotion", "promotion"),
        ("${catalog}.${product_schema}.product", "product"),
        ("${catalog}.${store_schema}.store", "store"),
    ]
    for a, b in repl:
        body = body.replace(a, b)
    return body


def _fixture_con():
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect()
    con.execute("CREATE TABLE product(product_sk INT, product_id VARCHAR, product_name VARCHAR, category VARCHAR, subcategory VARCHAR, brand VARCHAR)")
    con.execute("INSERT INTO product VALUES (1,'P1','Prod 1','beverages','regular','brand_a')")
    con.execute("CREATE TABLE store(store_sk INT, store_id VARCHAR, store_name VARCHAR, store_format VARCHAR, region VARCHAR)")
    con.execute("INSERT INTO store VALUES (1,'S1','Store 1','supermarket','north')")
    # one calendar row per week (week start date), weeks 1..13
    con.execute("CREATE TABLE fiscal_calendar(date_key DATE, fiscal_week_id INT, fiscal_week_index INT)")
    for wk in range(1, 14):
        con.execute(f"INSERT INTO fiscal_calendar VALUES (DATE '2024-01-07' + INTERVAL {(wk-1)*7} DAY, {202400+wk}, {wk})")
    con.execute("""CREATE TABLE promotion(promo_sk INT, promo_id VARCHAR, promo_name VARCHAR,
        promo_type VARCHAR, funding_type VARCHAR, funded_by VARCHAR, planned_lift_pct DECIMAL(6,2),
        planned_trade_spend DECIMAL(18,2), fiscal_week_start INT, fiscal_week_end INT, current_flag BOOLEAN)""")
    con.execute("INSERT INTO promotion VALUES (99,'NO_PROMO','No Promotion',NULL,NULL,NULL,NULL,NULL,NULL,NULL,true)")
    con.execute("INSERT INTO promotion VALUES (1,'P-1','Promo 1','TPR','SCAN_DOWN','SHARED',50,1000,202412,202413,true)")
    con.execute("INSERT INTO promotion VALUES (2,'P-2','Promo 2','FEATURE','BILL_BACK','SUPPLIER',30,600,202403,202403,true)")
    con.execute("CREATE TABLE promotion_scope(promo_sk INT, product_sk INT, store_sk INT)")
    con.execute("INSERT INTO promotion_scope VALUES (1,1,1),(2,1,1)")
    con.execute("CREATE TABLE sales(product_sk INT, store_sk INT, promo_sk INT, promo_id VARCHAR, date_key DATE, units INT, net_revenue DECIMAL(18,2))")
    for wk in range(1, 14):
        d = f"DATE '2024-01-07' + INTERVAL {(wk-1)*7} DAY"
        if wk == 3:
            con.execute(f"INSERT INTO sales VALUES (1,1,2,'P-2',{d},15,150)")
        elif wk in (12, 13):
            con.execute(f"INSERT INTO sales VALUES (1,1,1,'P-1',{d},15,150)")
        else:
            con.execute(f"INSERT INTO sales VALUES (1,1,99,'NO_PROMO',{d},10,100)")
    con.execute("CREATE VIEW gold AS " + _gold_body_for_duckdb())
    return con


def test_gold_view_returns_rows():
    con = _fixture_con()
    n = con.execute("SELECT COUNT(*) FROM gold").fetchone()[0]
    assert n == 3, f"expected 3 promo x product x store x week rows, got {n}"


def test_promoted_week_carries_promo_and_units():
    con = _fixture_con()
    row = con.execute("""SELECT promoted_units, planned_trade_spend, planned_lift_pct
                         FROM gold WHERE promo_id='P-1' AND fiscal_week_id=202412""").fetchone()
    assert row is not None, "missing P-1 / week 202412 row"
    units, spend, lift = row
    assert units == 15, f"promoted_units={units}"
    assert float(spend) == 500.0, f"allocated trade spend={spend}"   # 1000 / (1 scope * 2 weeks)
    assert float(lift) == 50.0


def test_baseline_trailing_average_and_null_rule():
    con = _fixture_con()
    # >= 4 trailing non-promoted weeks -> mean (all 10s)
    b12 = con.execute("SELECT baseline_units FROM gold WHERE promo_id='P-1' AND fiscal_week_id=202412").fetchone()[0]
    assert float(b12) == 10.0, f"week 12 baseline={b12}"
    # < 4 trailing non-promoted weeks -> NULL
    b3 = con.execute("SELECT baseline_units FROM gold WHERE promo_id='P-2' AND fiscal_week_id=202403").fetchone()[0]
    assert b3 is None, f"week 3 baseline should be NULL, got {b3}"


def test_attribution_logic_inside_vs_outside_window():
    # Mirrors the generator's build_sales attribution: a sale inside a scoped
    # promo's date window carries the promo surrogate; outside it carries NO_PROMO.
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect()
    con.execute("CREATE TABLE base(product_sk INT, store_sk INT, date_key DATE)")
    con.execute("INSERT INTO base VALUES (1,1,DATE '2024-03-25'),(1,1,DATE '2024-06-01')")
    con.execute("CREATE TABLE win(w_product_sk INT, w_store_sk INT, w_promo_sk INT, start_date DATE, end_date DATE)")
    con.execute("INSERT INTO win VALUES (1,1,7,DATE '2024-03-20',DATE '2024-03-31')")
    rows = con.execute("""
        WITH m AS (
          SELECT b.date_key,
                 row_number() OVER (PARTITION BY b.product_sk,b.store_sk,b.date_key
                                    ORDER BY w.w_promo_sk NULLS LAST) rn,
                 w.w_promo_sk
          FROM base b
          LEFT JOIN win w ON b.product_sk=w.w_product_sk AND b.store_sk=w.w_store_sk
                         AND b.date_key>=w.start_date AND b.date_key<=w.end_date)
        SELECT date_key, COALESCE(w_promo_sk, 99) AS promo_sk FROM m WHERE rn=1 ORDER BY date_key
    """).fetchall()
    result = {str(d): sk for d, sk in rows}
    assert result["2024-03-25"] == 7, "sale inside the window must carry the promo surrogate"
    assert result["2024-06-01"] == 99, "sale outside the window must carry NO_PROMO (99)"
