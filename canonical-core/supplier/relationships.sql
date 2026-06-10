-- ============================================================
-- ORDM · Canonical Core · Supplier domain · relationships
-- Version: v1_mvm · Generated: 2026-06-10 · LLM-generated: true · Reviewed: 2026-06-10
-- ============================================================

-- Enum / state-domain CHECK constraint (H-10; list matches the column comment).
ALTER TABLE ${catalog}.${supplier_schema}.supplier
  ADD CONSTRAINT chk_supplier_status
  CHECK (supplier_status IS NULL OR supplier_status IN ('active', 'inactive', 'suspended'));
