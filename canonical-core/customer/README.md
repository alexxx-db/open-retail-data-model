# Canonical Core — Customer

> Status: ⚪ Planned

The conformed **Customer** domain. Part of the ORDM [canonical core](../README.md).

## Contents

This is a **data domain** (→ a Unity Catalog schema). One file per table keeps parallel work conflict-free.

| Path | Purpose |
|---|---|
| `tables/<table>.sql` | One CREATE TABLE file per entity (e.g. `tables/profile.sql`) |
| `relationships.sql` | Cross-table foreign keys for this domain |
| `checks.sql` | Data-quality assertions for this domain (run by `data-quality/run_checks.py`) |
| `masks.sql` | Unity Catalog column masks enforcing the `dbx_pii_*` tags (PII masked except for the `pii_readers` group) |
| `glossary.md` | Business terms for this domain |
| `samples/` | Small synthetic sample rows |

## Design notes

Follows the ORDM [data model principles](../../docs/data-model-principles.md): vendor-neutral comments, strict typing, no derived metrics on master tables, thin cross-entity FKs, SCD where applicable.

_TODO: add tables.sql_
