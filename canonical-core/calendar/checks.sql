-- ============================================================
-- ORDM · Canonical Core · Calendar domain · data-quality checks
-- Version: v1_mvm · Generated: 2026-06-09 · LLM-generated: true · Reviewed: 2026-06-09
-- Each assertion SELECTs violating rows; 0 rows = PASS.
-- ============================================================

-- check: calendar_keys_not_null | severity: error
SELECT * FROM ${catalog}.${calendar_schema}.fiscal_calendar
WHERE calendar_sk IS NULL OR date_key IS NULL OR fiscal_week_id IS NULL
   OR fiscal_week_index IS NULL;

-- check: calendar_date_unique | severity: error
SELECT date_key, COUNT(*) AS rows
FROM ${catalog}.${calendar_schema}.fiscal_calendar
GROUP BY date_key
HAVING COUNT(*) > 1;

-- check: calendar_fiscal_ranges | severity: error
-- NRF 4-5-4 bounds: week 1-53, quarter 1-4, period 1-12.
SELECT * FROM ${catalog}.${calendar_schema}.fiscal_calendar
WHERE fiscal_week NOT BETWEEN 1 AND 53
   OR fiscal_quarter NOT BETWEEN 1 AND 4
   OR fiscal_period NOT BETWEEN 1 AND 12;

-- check: calendar_week_date_order | severity: warn
SELECT * FROM ${catalog}.${calendar_schema}.fiscal_calendar
WHERE fiscal_week_end_date < fiscal_week_start_date;
