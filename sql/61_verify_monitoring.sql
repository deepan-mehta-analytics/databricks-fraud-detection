-- ── Monitoring verification (Phase 6a spec §6-7, sheet D3a-D10). Expected values from scripts/expected_gold.py over data/paysim.csv, 2026-10-15. ──
-- Location: written for the default bundle variables (workspace.fraud). Run one block at a time: the SQL editor shows only the last result.

-- ── D3a: before deploying, after running sql/monitoring/monitoring.sql in the SQL editor (today's data, newest hour 421) ──
WITH hours AS (SELECT DISTINCT step, fraud_in_hour FROM workspace.fraud.model_accuracy_by_hour WHERE verdicts_ready)  -- fraud once per hour
SELECT SUM(closed_cases) AS closed_cases,                                       -- expect 412 (hours 337-349)
       (SELECT SUM(fraud_in_hour) FROM hours) AS fraud_with_verdicts,           -- expect 120
       COUNT(DISTINCT IF(verdicts_ready, step, NULL)) AS hours_with_verdicts,   -- expect 13
       COUNT_IF(NOT verdicts_ready AND (share_flagged_that_were_fraud IS NOT NULL  -- waiting hours with a share...
                OR share_of_fraud_caught IS NOT NULL OR fraud_in_hour IS NOT NULL)) AS waiting_with_numbers,  -- ...expect 0
       MAX(step) AS newest_hour                                                 -- expect 421
FROM workspace.fraud.model_accuracy_by_hour;                                    -- the model view
SELECT * FROM workspace.fraud.hours_waiting_for_verdicts;                       -- expect 421, 349, 72 (hours 350-421)
SELECT * FROM workspace.fraud.data_freshness;                                   -- expect 421 in all four newest_hour columns; both minute columns filled
SELECT * FROM workspace.fraud.rejected_rows_by_reason;                          -- expect one row: bad_amount, 5, 350, 350
SELECT job_name, COUNT(DISTINCT run_started_at) AS runs,                        -- expect fraud-ingest and fraud-train only
       SUM(IF(minutes_taken = 0, 1, 0)) AS zero_minute_rows                     -- expect 0 (minutes from start and end times)
FROM workspace.fraud.job_run_times GROUP BY job_name;                           -- one row per job
SELECT pipeline_name, COUNT(*) AS updates, MAX(update_started_at) AS newest_update  -- expect fraud-silver, at least 1 update
FROM workspace.fraud.pipeline_update_times GROUP BY pipeline_name;              -- one row
SHOW GRANTS ON TABLE workspace.fraud.model_accuracy_by_hour;                    -- expect SELECT for all three groups
SHOW GRANTS ON TABLE workspace.fraud.hours_waiting_for_verdicts;                -- expect SELECT for all three groups

-- ── D5: Gold after run E (segment=drift, steps_per_run=59) ──
SELECT COUNT(*) AS alerts,                                                      -- expect 5033
       MAX(step) AS newest_flagged_hour,                                        -- expect 480
       (SELECT COUNT_IF(status = 'closed') FROM workspace.fraud.alert_cases) AS closed,  -- expect 2916
       (SELECT COUNT_IF(status = 'open') FROM workspace.fraud.alert_cases) AS open  -- expect 2117
FROM workspace.fraud.fraud_alerts;                                              -- the alert log

-- ── D6: the view numbers after run E (spec §6) ──
WITH ready AS (SELECT * FROM workspace.fraud.model_accuracy_by_hour WHERE verdicts_ready),  -- hours 337-408
     hours AS (SELECT DISTINCT step, fraud_in_hour FROM ready)                 -- fraud once per hour, whatever the versions
SELECT SUM(confirmed_fraud) AS confirmed_fraud,                                 -- expect 405 (Phase 4 M6)
       SUM(closed_cases) AS checked_cases,                                      -- expect 2916
       (SELECT SUM(fraud_in_hour) FROM hours) AS all_fraud,                     -- expect 822
       ROUND(SUM(confirmed_fraud) / SUM(closed_cases), 3) AS share_flagged_that_were_fraud,  -- expect 0.139
       ROUND(SUM(confirmed_fraud) / (SELECT SUM(fraud_in_hour) FROM hours), 3) AS share_of_fraud_caught,  -- expect 0.493
       COUNT(DISTINCT step) AS hours_with_verdicts,                             -- expect 72
       MIN(step) AS first_hour, MAX(step) AS last_hour                          -- expect 337, 408
FROM ready;                                                                     -- one row
SELECT COUNT(DISTINCT step) AS hours_waiting,                                   -- expect 72 (409-480)
       COUNT_IF(share_flagged_that_were_fraud IS NOT NULL OR share_of_fraud_caught IS NOT NULL  -- any number...
                OR fraud_in_hour IS NOT NULL) AS waiting_with_numbers           -- ...expect 0
FROM workspace.fraud.model_accuracy_by_hour WHERE NOT verdicts_ready;           -- the waiting hours
SELECT * FROM workspace.fraud.hours_waiting_for_verdicts;                       -- expect 480, 408, 72
SELECT * FROM workspace.fraud.data_freshness;                                   -- expect 480 in all four newest_hour columns
SELECT * FROM workspace.fraud.rejected_rows_by_reason;                          -- expect bad_amount, 5, 350, 350

-- ── D7: at least one hour after run E finished (system tables lag, ruling R3) ──
SELECT job_name, run_started_at, minutes_taken, outcome                         -- run E: fraud-ingest, SUCCEEDED,
FROM workspace.fraud.job_run_times                                              -- minutes within 0.5 of the Jobs UI duration
GROUP BY ALL ORDER BY run_started_at DESC LIMIT 3;                              -- newest runs first
SELECT task_name, task_minutes, task_outcome                                    -- expect 8 rows: release, ingest, silver, score,
FROM workspace.fraud.job_run_times                                              -- gold, monitor, refresh_operations, refresh_platform
WHERE run_started_at = (SELECT MAX(run_started_at) FROM workspace.fraud.job_run_times WHERE job_name = 'fraud-ingest')  -- run E
ORDER BY task_minutes DESC;                                                     -- slowest first
SELECT update_started_at, minutes_taken, outcome, full_rebuild                  -- run E's Silver update: COMPLETED, false,
FROM workspace.fraud.pipeline_update_times ORDER BY update_started_at DESC LIMIT 1;  -- fewer minutes than the silver task

-- ── D8: as the test user (member of fraud_managers only) ──
WITH ready AS (SELECT * FROM workspace.fraud.model_accuracy_by_hour WHERE verdicts_ready),  -- the row filter applies through the view
     hours AS (SELECT DISTINCT step, fraud_in_hour FROM ready)                 -- fraud once per hour
SELECT SUM(confirmed_fraud) AS confirmed_fraud,                                 -- expect 405, the same as the owner
       SUM(closed_cases) AS checked_cases,                                      -- expect 2916
       (SELECT SUM(fraud_in_hour) FROM hours) AS all_fraud,                     -- expect 822
       SUM(flagged_payments) - SUM(closed_cases) AS open_visible                -- expect 0: managers see closed cases only
FROM ready;                                                                     -- one row
SELECT COUNT(*) AS waiting_rows FROM workspace.fraud.model_accuracy_by_hour WHERE NOT verdicts_ready;  -- expect 0: open hours are invisible
SELECT * FROM workspace.fraud.hours_waiting_for_verdicts;                       -- expect 480, 408, 72: the same as the owner (review I1)
SELECT COUNT(*) AS runs FROM workspace.fraud.job_run_times;                     -- expect a permission error (engineers only)
