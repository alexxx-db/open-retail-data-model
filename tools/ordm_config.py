# ============================================================
# ORDM · shared SQL token resolver
# ============================================================
# Single source of truth for resolving the ${catalog} / ${<domain>_schema}
# tokens used throughout the SQL. Schema names are read from databricks.yml
# `variables` (the project config — guardrail #1: never hardcode a schema),
# so the DQ runner, the tests, and any future deploy runner all resolve
# tokens the same way. Pure stdlib + PyYAML (no Spark) so it imports anywhere.
# ============================================================

import os
import re

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATABRICKS_YML = os.path.join(REPO_ROOT, "databricks.yml")

# Matches the CREATE header of a view OR a materialized view, regardless of
# CREATE [OR REPLACE|OR REFRESH] [MATERIALIZED] VIEW <name> [SCHEDULE ...] AS ...
_CREATE_VIEW_RE = re.compile(
    r"CREATE\s+(?:OR\s+(?:REPLACE|REFRESH)\s+)?(?:MATERIALIZED\s+)?VIEW\b.*?\bAS\b",
    re.IGNORECASE | re.DOTALL,
)

# Safety net only — used when databricks.yml cannot be read. databricks.yml
# remains authoritative; keep these in sync with its `variables` defaults.
_FALLBACK = {
    "customer_schema": "customer",
    "product_schema": "product",
    "store_schema": "store",
    "calendar_schema": "calendar",
    "transaction_schema": "transaction",
    "promo_schema": "promote_with_purpose",
    "supplier_schema": "supplier",
    "procurement_schema": "procurement",
    "risk_schema": "early_risk_detection",
    "order_schema": "orders",
    "payment_schema": "payment",
    "acu_schema": "actionable_customer_understanding",
    "dss_schema": "data_sharing_with_suppliers",
}


def schema_defaults():
    """Return {token: schema_name} read from databricks.yml `variables`."""
    defaults = dict(_FALLBACK)
    try:
        import yaml
        with open(DATABRICKS_YML) as fh:
            data = yaml.safe_load(fh) or {}
        for name, spec in (data.get("variables") or {}).items():
            if name.endswith("_schema") and isinstance(spec, dict) and "default" in spec:
                defaults[name] = spec["default"]
    except Exception:
        pass  # fall back to the built-in defaults
    return defaults


def view_select_body(sql_text):
    """Return the SELECT body of a CREATE [OR REPLACE | OR REFRESH] [MATERIALIZED]
    VIEW statement — form-agnostic, so plain views and materialized views are
    handled the same way (the SELECT logic is identical)."""
    m = _CREATE_VIEW_RE.search(sql_text)
    if not m:
        raise ValueError("no 'CREATE ... VIEW ... AS' found")
    return sql_text[m.end():].strip().rstrip(";")


def resolve(sql, catalog, overrides=None):
    """Substitute ${catalog} and every ${<domain>_schema} token in `sql`.

    `overrides` (token -> schema) wins over the databricks.yml defaults, so a
    deploy/DQ run can target non-default schemas via job parameters.
    """
    mapping = schema_defaults()
    if overrides:
        mapping.update({k: v for k, v in overrides.items() if v})
    text = sql.replace("${catalog}", catalog)
    for token, value in mapping.items():
        text = text.replace("${" + token + "}", value)
    return text
