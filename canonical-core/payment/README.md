# Canonical Core — Payment

> Status: 🟡 In progress (v1_mvm)

The conformed **Payment** domain. Part of the ORDM [canonical core](../README.md).

## Contents

This is a **data domain** (→ a Unity Catalog schema). One file per table keeps parallel work conflict-free.

| Path | Purpose |
|---|---|
| `tables/payment.sql` | Transaction-grain payment-event fact (sale / refund / adjustment / chargeback) |
| `relationships.sql` | Informational FK to customer + enum/state CHECK constraints |
| `checks.sql` | Data-quality assertions for this domain (run by `data-quality/run_checks.py`) |
| `glossary.md` | Business terms for this domain |
| `samples/` | Small synthetic sample rows |

## Design notes

`payment` is an append-only event fact (no SCD2): one row per payment event, keyed to the order (`order_id`) and the customer (`profile`). It carries its own `event_timestamp` (event-time, UTC) distinct from `load_timestamp` (processing-time). Amounts are normalized to the reporting/base currency (principle #9a); direction is carried by `payment_type`, not the sign. Follows the ORDM [data model principles](../../docs/data-model-principles.md).
