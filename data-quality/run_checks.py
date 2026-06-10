# ============================================================
# ORDM · Data-quality framework · check runner
# Version: v1_mvm
# Generated: 2026-06-09
# LLM-generated: true (maintainer-reviewed before release)
# Last reviewed: 2026-06-09
# ============================================================
# Discovers the check files (canonical-core/<domain>/checks.sql and
# outcome-packages/<pkg>/checks.sql), resolves ${catalog} and the
# ${<domain>_schema} tokens via the shared resolver (tools/ordm_config.py,
# which reads databricks.yml), runs each assertion via spark.sql, and reports.
# Each assertion SELECTs violating rows; 0 rows = PASS. The run FAILS (raises)
# if any `error`-severity check returns rows; `warn`-severity checks are
# reported but do not fail the run.
#
# Runs as a Databricks notebook/job task. Parameters (widgets):
#   catalog  (required)   — target Unity Catalog (never hardcoded; guardrail #1)
#   domains  (optional)   — comma-separated domains to check; default: all found
#   fail_on  (optional)   — "error" (default) or "warn" (treat warnings as failures)
# ============================================================

import glob
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

from pyspark.sql import SparkSession

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CANONICAL_GLOB = os.path.join(REPO_ROOT, "canonical-core", "*", "checks.sql")
OUTCOME_GLOB = os.path.join(REPO_ROOT, "outcome-packages", "*", "checks.sql")
HEADER_RE = re.compile(r"^--\s*check:\s*(?P<name>[\w]+)\s*\|\s*severity:\s*(?P<sev>error|warn|metric)\s*$",
                       re.IGNORECASE)

# Single source of truth for ${catalog}/${*_schema} resolution (reads the
# schema names from databricks.yml). Same resolver used by the tests.
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
from tools.ordm_config import resolve, schema_defaults  # noqa: E402


def get_param(name, default=None):
    try:
        return dbutils.widgets.get(name)  # noqa: F821 (injected in notebooks)
    except Exception:
        return os.environ.get(name.upper(), default)


def parse_checks(sql_text):
    """Yield (name, severity, query) tuples from a checks.sql file.

    A check starts at a `-- check: <name> | severity: <sev>` header and its
    query runs until the terminating semicolon.
    """
    checks = []
    current = None
    buf = []
    for line in sql_text.splitlines():
        m = HEADER_RE.match(line.strip())
        if m:
            current = (m.group("name"), m.group("sev").lower())
            buf = []
            continue
        if current is None:
            continue
        if line.strip().startswith("--"):
            continue  # description / comment line
        buf.append(line)
        if ";" in line:
            query = "\n".join(buf).strip().rstrip(";").strip()
            if query:
                checks.append((current[0], current[1], query))
            current = None
            buf = []
    return checks


def discover(filter_set=None):
    """Yield (label, path) for every checks.sql — canonical-core domains and
    outcome packages alike. SQL uses ${<domain>_schema} tokens resolved by the
    shared resolver, so no per-file schema bookkeeping is needed here."""
    for path in sorted(glob.glob(CANONICAL_GLOB)) + sorted(glob.glob(OUTCOME_GLOB)):
        label = os.path.basename(os.path.dirname(path))
        if filter_set and label not in filter_set:
            continue
        yield label, path


def _run_one(spark, label, name, severity, query):
    """Execute one check. error/warn checks are COUNT(*)-wrapped so the violation
    count is computed in-engine and NO rows are shipped to the driver; metric
    checks return their scalar value. Returns (label, name, severity, status, value)."""
    try:
        if severity == "metric":
            row = spark.sql(query).first()
            return (label, name, severity, "METRIC", row[0] if row is not None else None)
        violations = spark.sql(f"SELECT COUNT(*) AS n FROM (\n{query}\n) ordm_chk").first()["n"]
        status = "PASS" if violations == 0 else ("FAIL" if severity == "error" else "WARN")
        return (label, name, severity, status, violations)
    except Exception as exc:  # a malformed / under-deployed check is itself a failure
        return (label, name, severity, "ERROR", str(exc))


def run(spark, catalog, filter_set=None, fail_on="error", schema_overrides=None, max_parallel=8):
    if not catalog:
        raise ValueError("`catalog` parameter is required (guardrail #1: no hardcoded catalog).")
    schema_overrides = schema_overrides or {}

    # Collect every check, then run them CONCURRENTLY against the one Spark
    # session -- Spark submits the jobs from multiple threads, so the checks
    # overlap instead of running as ~100 strictly-sequential jobs.
    checks = []
    for label, path in discover(filter_set):
        text = resolve(open(path).read(), catalog, schema_overrides)
        for name, severity, query in parse_checks(text):
            checks.append((label, name, severity, query))

    with ThreadPoolExecutor(max_workers=max(1, max_parallel)) as pool:
        results = list(pool.map(lambda c: _run_one(spark, *c), checks))

    for label, name, severity, status, value in sorted(results, key=lambda r: (r[0], r[1])):
        if status == "METRIC":
            print(f"  [{label}] {name:42} METRIC value={value}")
        elif status == "ERROR":
            print(f"  [{label}] {name:42} ERROR  {value}")
        else:
            print(f"  [{label}] {name:42} {status:5} violations={value}")

    failed = [r for r in results
              if r[3] in ("ERROR", "FAIL")
              or (fail_on == "warn" and r[3] == "WARN")]

    print(f"\n[ordm] data-quality: {len(results)} checks, {len(failed)} failing "
          f"(fail_on={fail_on}).")
    if failed:
        names = ", ".join(f"{lbl}.{n}" for lbl, n, *_ in failed)
        raise AssertionError(f"Data-quality checks failed: {names}")
    return results


def main():
    spark = SparkSession.builder.getOrCreate()
    catalog = get_param("catalog", "")
    domains = get_param("domains", "")
    fail_on = get_param("fail_on", "error")
    filter_set = [d.strip() for d in domains.split(",") if d.strip()] or None
    overrides = {k: get_param(k, "") for k in schema_defaults()}
    overrides = {k: v for k, v in overrides.items() if v}
    max_parallel = int(get_param("max_parallel", "8"))
    run(spark, catalog, filter_set, fail_on, overrides, max_parallel)


if __name__ == "__main__":
    main()
