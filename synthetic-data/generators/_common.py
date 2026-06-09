# ============================================================
# ORDM · Synthetic data · shared generator helpers
# Version: v1_mvm
# Generated: 2026-06-09
# LLM-generated: true (maintainer-reviewed before release)
# Last reviewed: 2026-06-09
# ============================================================
# Engine helpers shared by every domain/use-case generator (customer,
# trade promotion, …). Kept in one place so generators extend rather than
# fork the framework. Pure PySpark; no hardcoded catalog/schema.
# ============================================================

import os

from pyspark.sql import functions as F

RECORD_SOURCE = "synthetic-generator"


def get_param(name, default=None):
    """Read a parameter: notebook widget on Databricks, else env, else default."""
    try:
        return dbutils.widgets.get(name)  # noqa: F821 (injected in notebooks)
    except Exception:
        return os.environ.get(name.upper(), default)


def load_domain_config(domain):
    """Return the seeds.yaml config dict for a domain (volumes/fanout/seed), or {}."""
    path = os.path.join(os.path.dirname(__file__), "..", "seeds.yaml")
    try:
        import yaml
        with open(path) as fh:
            data = yaml.safe_load(fh) or {}
        return (data.get("domains", {}) or {}).get(domain, {}) or {}
    except Exception:
        return {}


# ---- deterministic helpers (order-independent: pure functions of keys+seed) ----

def _pick(arr, seed, salt, *keys):
    """Deterministically pick an element of `arr` from the given keys."""
    n = len(arr)
    idx = (F.abs(F.hash(*keys, F.lit(salt), F.lit(seed))) % F.lit(n)).cast("int")
    return F.element_at(F.array(*[F.lit(v) for v in arr]), idx + F.lit(1))


def _frac(seed, salt, *keys):
    """Deterministic pseudo-random fraction in [0,1)."""
    return (F.abs(F.hash(*keys, F.lit(salt), F.lit(seed))) % F.lit(10000)) / F.lit(10000.0)


def _count_1_to_max(maximum, seed, salt, *keys):
    """Deterministic integer in [1, maximum]."""
    return (F.abs(F.hash(*keys, F.lit(salt), F.lit(seed))) % F.lit(maximum)).cast("int") + F.lit(1)


def _write(spark, df, fqtn, columns, mode):
    """Insert the non-identity columns; Delta assigns the IDENTITY *_sk."""
    df.select(*columns).createOrReplaceTempView("ordm_gen_tmp")
    col_list = ", ".join(columns)
    if mode == "append":
        spark.sql(f"INSERT INTO {fqtn} ({col_list}) SELECT {col_list} FROM ordm_gen_tmp")
    else:
        spark.sql(f"INSERT OVERWRITE TABLE {fqtn} ({col_list}) SELECT {col_list} FROM ordm_gen_tmp")
    return spark.table(fqtn)
