import os
import sys

import pytest

# Make the repo root importable so tests can use the shared resolver
# (tools.ordm_config) — the single source of truth for ${*_schema} tokens.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


@pytest.fixture(scope="session")
def spark():
    """A local Spark session — the SAME engine Databricks runs — for executing
    the real gold-view SQL against temp-view fixtures. No non-Databricks query
    engine is used. Skips (rather than fails) only if Spark/JVM is unavailable."""
    pytest.importorskip("pyspark")
    from pyspark.sql import SparkSession

    session = (
        SparkSession.builder
        .master("local[1]")
        .appName("ordm-sql-tests")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "1")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()
