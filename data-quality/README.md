# Data-quality framework

Lightweight, SQL-first data-quality assertions for the ORDM canonical core. Each new table ships a check here (ORDM contribution bar).

## How it works

- **Checks are domain-local.** Each domain owns `canonical-core/<domain>/checks.sql` (alongside its `tables/`, `glossary.md`, `relationships.sql`). Keeping checks next to the model keeps parallel work conflict-free.
- **An assertion is a query that returns the violating rows.** `0 rows = PASS`. There is no separate expectations DSL to learn — if you can write the SQL that finds bad rows, you can write a check.
- **The runner** (`run_checks.py`) discovers every `canonical-core/*/checks.sql` **and** `outcome-packages/*/checks.sql`, resolves `${catalog}` (parameter) and the `${<domain>_schema}` tokens via the shared resolver (`tools/ordm_config.py`, which reads `databricks.yml`), runs each assertion with `spark.sql`, and **fails the run if any `error`-severity check returns rows**. `warn`-severity checks are reported but non-fatal; `metric`-severity checks report a value and never fail.

## Check format

```sql
-- check: <name> | severity: error|warn
-- <one-line description>
SELECT ...        -- returns violating rows
;                 -- terminating semicolon
```

## Running it

As a Databricks notebook/job task (`notebook_path: data-quality/run_checks.py`) with parameters:

| Parameter | Required | Default | Meaning |
|---|---|---|---|
| `catalog` | yes | — | Target Unity Catalog. Never hardcoded (guardrail #1). |
| `domains` | no | all | Comma-separated domains to check (e.g. `customer`). |
| `fail_on` | no | `error` | `error`, or `warn` to also fail on warnings. |

Run it **after** the synthetic-data generators, as a downstream task in the same job.

## Coverage convention

Every table gets, at minimum: mandatory-key not-null, business-key uniqueness among current rows (SCD2), enum-domain membership for coded columns, referential integrity (no FK orphans), and SCD2 date-window sanity. Static structural checks (column contracts, enum/DDL parity, no hardcoded identifiers) live in `tests/` and run without a cluster.
