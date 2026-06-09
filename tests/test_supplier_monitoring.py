"""Tests for the Supplier Score & Monitoring use case.

Static contract tests keep the DDL, generator and gold view consistent and
guardrail-clean. Engine tests run the REAL gold_supplier_scorecard SQL against
an in-process DuckDB fixture with hand-computed KPIs, proving each KPI, the
composite from documented weights, and that OTIF requires BOTH on-time AND
in-full.
"""

import ast
import os
import re

import pytest
import sqlglot
import sqlglot.expressions as E

from tools.ordm_config import resolve

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GENERATOR = os.path.join(REPO, "synthetic-data", "generators", "supplier_monitoring.py")
SUPPLIER_DDL = os.path.join(REPO, "canonical-core", "supplier", "tables", "supplier.sql")
POL_DDL = os.path.join(REPO, "canonical-core", "procurement", "tables", "purchase_order_line.sql")
SCORECARD = os.path.join(REPO, "outcome-packages", "early-risk-detection", "gold", "gold_supplier_scorecard.sql")

TABLES = {
    "supplier": (SUPPLIER_DDL, "supplier_sk", "SUPPLIER_COLUMNS"),
    "purchase_order_line": (POL_DDL, "po_line_sk", "PO_LINE_COLUMNS"),
}


def _ddl_columns(path, sk):
    create = next(s for s in sqlglot.parse(resolve(open(path).read(), "c"), read="databricks", error_level="ignore")
                  if isinstance(s, E.Create))
    return [c.name for c in create.find_all(E.ColumnDef) if c.name != sk]


def _generator_constants():
    mod = ast.parse(open(GENERATOR).read())
    return {n.targets[0].id: [e.value for e in n.value.elts] for n in mod.body
            if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
            and isinstance(n.value, ast.List) and all(isinstance(e, ast.Constant) for e in n.value.elts)}


# ---------- static ----------

@pytest.mark.parametrize("table", list(TABLES))
def test_generator_columns_match_ddl(table):
    path, sk, const = TABLES[table]
    gen = set(_generator_constants()[const])
    ddl = set(_ddl_columns(path, sk))
    assert gen == ddl, f"{table} drift — missing={sorted(ddl - gen)} extra={sorted(gen - ddl)}"


def test_scorecard_exposes_required_columns():
    raw = resolve(open(SCORECARD).read(), "c")
    create = next(s for s in sqlglot.parse(raw, read="databricks", error_level="ignore")
                  if isinstance(s, E.Create))
    outputs = set(create.expression.named_selects)
    required = {"supplier_id", "fiscal_year", "fiscal_period", "order_lines", "otif_pct",
                "fill_rate", "avg_lead_time_days", "lead_time_variance", "defect_rate",
                "price_compliance_pct", "composite_score"}
    assert required <= outputs, f"scorecard missing: {sorted(required - outputs)}"


def test_supplier_uses_gln_and_iso_country():
    ddl = open(SUPPLIER_DDL).read()
    assert re.search(r"\bgln\b", ddl) and "Global Location Number" in ddl
    assert "ISO 3166" in ddl


def test_no_banned_or_hardcoded():
    paths = [SUPPLIER_DDL, POL_DDL, SCORECARD,
             os.path.join(REPO, "canonical-core", "procurement", "relationships.sql"),
             os.path.join(REPO, "canonical-core", "supplier", "checks.sql"),
             os.path.join(REPO, "canonical-core", "procurement", "checks.sql"),
             os.path.join(REPO, "outcome-packages", "early-risk-detection", "checks.sql")]
    bad = [os.path.relpath(p, REPO) for p in paths
           if re.search(r"GROUP\s+BY\s+ALL|\b1\s*=\s*1\b", open(p).read(), re.I)
           or re.search(r"https?://[\w.-]*databricks|retail_mvm|retail_ecm|Copyright|SPDX|Licensed under",
                        open(p).read(), re.I)]
    assert not bad, f"banned/hardcoded/license in: {bad}"


# ---------- engine: DuckDB fixture running the real scorecard SQL ----------

_SUBS = [
    ("${catalog}.${procurement_schema}.purchase_order_line", "purchase_order_line"),
    ("${catalog}.${calendar_schema}.fiscal_calendar", "fiscal_calendar"),
    ("${catalog}.${supplier_schema}.supplier", "supplier"),
]


def _scorecard_body():
    raw = open(SCORECARD).read()
    body = raw[raw.index(" AS", raw.index("CREATE OR REPLACE VIEW")) + 3:].strip().rstrip(";")
    for a, b in _SUBS:
        body = body.replace(a, b)
    # Spark datediff(end, start) -> DuckDB date subtraction (integer days)
    body = body.replace("datediff(pol.actual_delivery_date, pol.order_date)",
                        "(pol.actual_delivery_date - pol.order_date)")
    return body


def _fixture():
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect()
    con.execute("CREATE TABLE supplier(supplier_sk INT, supplier_id VARCHAR, supplier_name VARCHAR, "
                "country_code VARCHAR, current_flag BOOLEAN)")
    con.execute("INSERT INTO supplier VALUES (1,'SUP1','Supplier 1','US',true),(2,'SUP2','Supplier 2','DE',true)")
    con.execute("CREATE TABLE fiscal_calendar(date_key DATE, fiscal_year INT, fiscal_period INT)")
    con.execute("INSERT INTO fiscal_calendar VALUES (DATE '2024-01-07', 2024, 1)")
    con.execute("""CREATE TABLE purchase_order_line(supplier_sk INT, supplier_id VARCHAR, order_date DATE,
        promised_date DATE, actual_delivery_date DATE, ordered_qty INT, received_qty INT,
        defective_qty INT, returned_qty INT, unit_price DECIMAL(18,2), contract_price DECIMAL(18,2))""")

    def line(ssk, sid, ord_off, prom_off, act_off, ordered, received, defective, unit, contract):
        od = "DATE '2024-01-07'"
        con.execute(f"INSERT INTO purchase_order_line VALUES ({ssk},'{sid}',{od},"
                    f"{od} + INTERVAL {prom_off} DAY,{od} + INTERVAL {act_off} DAY,"
                    f"{ordered},{received},{defective},0,{unit},{contract})")

    # SUP1: 4 lines -> OTIF 2/4, fill 380/400, lead {4,5,4,8}, defect 0, price all compliant
    line(1, 'SUP1', 0, 5, 4, 100, 100, 0, 6, 6)   # on-time + in-full  -> OTIF
    line(1, 'SUP1', 0, 5, 5, 100, 100, 0, 6, 6)   # on-time + in-full  -> OTIF
    line(1, 'SUP1', 0, 5, 4, 100, 80, 0, 6, 6)    # on-time but SHORT  -> not OTIF
    line(1, 'SUP1', 0, 5, 8, 100, 100, 0, 6, 6)   # LATE but in-full   -> not OTIF
    # SUP2: 2 lines -> OTIF 0, fill 0.7, defect 20/140, late
    line(2, 'SUP2', 0, 5, 9, 100, 70, 10, 6, 6)
    line(2, 'SUP2', 0, 5, 9, 100, 70, 10, 6, 6)

    con.execute("CREATE VIEW gold_supplier_scorecard AS " + _scorecard_body())
    return con


def _row(con, sid):
    return con.execute(f"""SELECT otif_pct, fill_rate, avg_lead_time_days, lead_time_variance,
                                  defect_rate, price_compliance_pct, composite_score
                           FROM gold_supplier_scorecard WHERE supplier_id='{sid}'""").fetchone()


def test_one_row_per_supplier_period():
    con = _fixture()
    n = con.execute("SELECT COUNT(*) FROM gold_supplier_scorecard").fetchone()[0]
    assert n == 2, f"expected one row per supplier x fiscal period, got {n}"


def test_kpis_and_composite_known_values():
    con = _fixture()
    otif, fill, lead, var, defect, price, comp = (float(x) for x in _row(con, 'SUP1'))
    assert otif == pytest.approx(0.5)
    assert fill == pytest.approx(0.95)
    assert lead == pytest.approx(5.25)
    assert var == pytest.approx(2.6875)
    assert defect == pytest.approx(0.0)
    assert price == pytest.approx(1.0)
    # composite = (35*50 + 25*95 + 20*89.25 + 15*100 + 5*100)/100 = 79.1
    assert comp == pytest.approx(79.1)


def test_otif_requires_both_on_time_and_in_full():
    con = _fixture()
    otif = float(_row(con, 'SUP1')[0])
    # 4 lines: 2 fully OK, 1 on-time-but-short, 1 late-but-full.
    # Only-on-time would give 0.75; only-in-full would give 0.75; BOTH gives 0.5.
    assert otif == pytest.approx(0.5)


def test_composite_spread_not_all_identical():
    con = _fixture()
    c1 = float(_row(con, 'SUP1')[6])
    c2 = float(_row(con, 'SUP2')[6])
    assert c2 == pytest.approx(42.5)
    assert c1 != c2
    distinct = con.execute("SELECT COUNT(DISTINCT ROUND(composite_score,4)) FROM gold_supplier_scorecard").fetchone()[0]
    assert distinct > 1
