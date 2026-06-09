# ============================================================
# ORDM · Data-quality framework · check runner
# Version: v1_mvm
# Generated: 2026-06-09
# LLM-generated: true (maintainer-reviewed before release)
# Last reviewed: 2026-06-09
# ============================================================
# Discovers the per-domain check files (canonical-core/<domain>/checks.sql),
# substitutes ${catalog} (parameter) and ${schema} (= the domain name, from
# the file path), runs each assertion via spark.sql, and reports violations.
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

from pyspark.sql import SparkSession

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CANONICAL_GLOB = os.path.join(REPO_ROOT, "canonical-core", "*", "checks.sql")
OUTCOME_GLOB = os.path.join(REPO_ROOT, "outcome-packages", "*", "checks.sql")
HEADER_RE = re.compile(r"^--\s*check:\s*(?P<name>[\w]+)\s*\|\s*severity:\s*(?P<sev>error|warn|metric)\s*$",
                       re.IGNORECASE)

# Default schema name per cross-schema token. SQL never hardcodes a schema;
# the runner resolves ${*_schema} tokens here (overridable via job params of
# the same name).
SCHEMA_MAP = {
    "customer_schema": "customer",
    "product_schema": "product",
    "store_schema": "store",
    "calendar_schema": "calendar",
    "transaction_schema": "transaction",
    "promo_schema": "promote_with_purpose",
}
# An outcome-package directory maps to its own schema (the ${schema} token).
PACKAGE_SCHEMA = {"promote-with-purpose": "promote_with_purpose"}


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
    """Yield (label, own_schema, path) for every checks.sql, canonical-core
    domains and outcome packages alike. `own_schema` resolves the ${schema}
    token for that file's home."""
    for path in sorted(glob.glob(CANONICAL_GLOB)):
        domain = os.path.basename(os.path.dirname(path))
        if filter_set and domain not in filter_set:
            continue
        yield domain, domain, path
    for path in sorted(glob.glob(OUTCOME_GLOB)):
        pkg = os.path.basename(os.path.dirname(path))
        if filter_set and pkg not in filter_set:
            continue
        yield pkg, PACKAGE_SCHEMA.get(pkg, pkg.replace("-", "_")), path


def _substitute(text, catalog, own_schema, overrides):
    text = text.replace("${catalog}", catalog).replace("${schema}", own_schema)
    for token, default in SCHEMA_MAP.items():
        text = text.replace("${" + token + "}", overrides.get(token, default))
    return text


def run(spark, catalog, filter_set=None, fail_on="error", schema_overrides=None):
    if not catalog:
        raise ValueError("`catalog` parameter is required (guardrail #1: no hardcoded catalog).")
    schema_overrides = schema_overrides or {}

    results = []
    for label, own_schema, path in discover(filter_set):
        text = _substitute(open(path).read(), catalog, own_schema, schema_overrides)
        for name, severity, query in parse_checks(text):
            try:
                if severity == "metric":
                    row = spark.sql(query).first()
                    value = row[0] if row is not None else None
                    results.append((label, name, severity, "METRIC", value))
                    print(f"  [{label}] {name:42} METRIC value={value}")
                    continue
                violations = spark.sql(query).count()
                status = "PASS" if violations == 0 else ("FAIL" if severity == "error" else "WARN")
            except Exception as exc:  # a malformed/under-deployed check is itself a failure
                violations, status = -1, "ERROR"
                print(f"  [{label}] {name}: query error: {exc}")
            results.append((label, name, severity, status, violations))
            print(f"  [{label}] {name:42} {status:5} violations={violations}")

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
    overrides = {k: get_param(k, "") for k in SCHEMA_MAP}
    overrides = {k: v for k, v in overrides.items() if v}
    run(spark, catalog, filter_set, fail_on, overrides)


if __name__ == "__main__":
    main()
