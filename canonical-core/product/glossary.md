# Product Domain — Business Glossary

> Status: 🟡 In progress (v1_mvm) · Last reviewed: 2026-06-09

| Term | Definition |
|---|---|
| **Product** (`product`) | Conformed product master (SCD2). One logical sellable item, versioned over time. |
| **GTIN** | GS1 Global Trade Item Number (UPC/EAN). A product business key. **Not PII.** |
| **SKU** | Stock keeping unit code. A product business key. **Not PII.** |
| **Category / subcategory / department** | Merchandising hierarchy attributes used to roll up and scope analytics. |
| **List price** | Standard shelf price in the catalog currency (ISO 4217); not a derived metric. |
| **Unit cost** | Standard unit cost (COGS) in the catalog currency. Basis for margin (`revenue − units × unit_cost`); a master cost attribute, not a derived metric. |

Surrogate `product_sk` is the join/FK target; `product_id` is the durable business key. No sales/margin aggregates live here (principle #4).
