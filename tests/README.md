# Tests

Static, cluster-free tests that keep the model, the synthetic-data generator, and the data-quality checks mutually consistent and within the ORDM guardrails.

## What they cover

- **DDL** parses as `CREATE TABLE`; every table has a surrogate key + business key.
- **Generator ⇄ DDL**: column contracts match exactly (minus IDENTITY `*_sk`); generated enum values stay within the DDL `Allowed values:` domains.
- **DQ checks**: well-formed headers, catalog/schema tokenized, only reference known tables, and every table is covered.
- **Guardrails**: no hardcoded catalog/workspace (#1), no license headers (#4), no banned SQL patterns (#5).

These need no Databricks connection — they read the SQL/Python as text/AST. Data-quality assertions that need real data live in `data-quality/` and run on a warehouse after generation.

## Running

```bash
pip install -r requirements-dev.txt
pytest -q
```
