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
from pyspark.sql.window import Window

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


def attach_random_dim(fact_df, dim_df, dim_count, salt, seed, *key_cols):
    """Attach a deterministically-chosen row of `dim_df` to each fact row via a
    BROADCAST join on a hashed dense index.

    Scales with the fact table -- no driver-side .collect() of dimension ids and
    no per-row array literal (unlike _pick). `dim_df` must be small enough to
    broadcast (true for conformed dimensions); `dim_count` is its row count
    (a cheap COUNT, not a collect). `dim_df` columns must not collide with the
    fact's columns. Deterministic for a given (key_cols, salt, seed, dim order).
    """
    indexed = dim_df.withColumn("_ord_idx", F.row_number().over(Window.orderBy(*dim_df.columns)) - F.lit(1))
    pick_idx = F.abs(F.hash(*key_cols, F.lit(salt), F.lit(seed))) % F.lit(max(1, int(dim_count)))
    return (fact_df.withColumn("_pick_idx", pick_idx)
            .join(F.broadcast(indexed), F.col("_pick_idx") == F.col("_ord_idx"), "inner")
            .drop("_pick_idx", "_ord_idx"))


def _write(spark, df, fqtn, columns, mode, merge_keys=None):
    """Write the non-identity columns to a Delta table; Delta assigns the
    IDENTITY *_sk. Modes:
      overwrite (default) - INSERT OVERWRITE (idempotent full reload)
      append              - INSERT INTO
      merge               - MERGE upsert on `merge_keys` (idempotent incremental,
                            uses deletion vectors for the row-level updates)
    """
    df.select(*columns).createOrReplaceTempView("ordm_gen_tmp")
    col_list = ", ".join(columns)
    if mode == "merge":
        if not merge_keys:
            raise ValueError("mode='merge' requires merge_keys")
        on = " AND ".join(f"t.{k} = s.{k}" for k in merge_keys)
        set_clause = ", ".join(f"t.{c} = s.{c}" for c in columns)
        ins_vals = ", ".join(f"s.{c}" for c in columns)
        spark.sql(f"MERGE INTO {fqtn} t USING ordm_gen_tmp s ON {on} "
                  f"WHEN MATCHED THEN UPDATE SET {set_clause} "
                  f"WHEN NOT MATCHED THEN INSERT ({col_list}) VALUES ({ins_vals})")
    elif mode == "append":
        spark.sql(f"INSERT INTO {fqtn} ({col_list}) SELECT {col_list} FROM ordm_gen_tmp")
    else:
        spark.sql(f"INSERT OVERWRITE TABLE {fqtn} ({col_list}) SELECT {col_list} FROM ordm_gen_tmp")
    return spark.table(fqtn)
