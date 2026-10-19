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

-- ── D5: Gold after run E (segment=drift, steps_per_run=59). Highlight the block, Run: one row ──
WITH result AS (                                                                -- the four Gold numbers
  SELECT COUNT(*) AS alerts,                                                    -- expect 5033
         MAX(step) AS newest_flagged_hour,                                      -- expect 480
         (SELECT COUNT_IF(status = 'closed') FROM workspace.fraud.alert_cases) AS closed,  -- expect 2916
         (SELECT COUNT_IF(status = 'open') FROM workspace.fraud.alert_cases) AS open  -- expect 2117
  FROM workspace.fraud.fraud_alerts)                                            -- the alert log
SELECT *, (alerts = 5033 AND newest_flagged_hour = 480 AND closed = 2916 AND open = 2117)  -- every value matched?
          AS all_as_expected FROM result;                                       -- expect true

-- ── D6: the view numbers after run E (spec §6). Highlight the block, Run: one row ──
WITH ready AS (SELECT * FROM workspace.fraud.model_accuracy_by_hour WHERE verdicts_ready),  -- hours 337-408
     hours AS (SELECT DISTINCT step, fraud_in_hour FROM ready),                -- fraud once per hour, whatever the versions
     result AS (                                                                -- every D6 value side by side
  SELECT SUM(confirmed_fraud) AS confirmed_fraud,                               -- expect 405 (Phase 4 M6)
         SUM(closed_cases) AS checked_cases,                                    -- expect 2916
         (SELECT SUM(fraud_in_hour) FROM hours) AS all_fraud,                   -- expect 822
         ROUND(SUM(confirmed_fraud) / SUM(closed_cases), 3) AS share_flagged_that_were_fraud,  -- expect 0.139
         ROUND(SUM(confirmed_fraud) / (SELECT SUM(fraud_in_hour) FROM hours), 3) AS share_of_fraud_caught,  -- expect 0.493
         COUNT(DISTINCT step) AS hours_with_verdicts,                           -- expect 72
         MIN(step) AS first_hour, MAX(step) AS last_hour,                       -- expect 337, 408
         (SELECT COUNT(DISTINCT step) FROM workspace.fraud.model_accuracy_by_hour  -- hours still waiting...
          WHERE NOT verdicts_ready) AS hours_waiting,                           -- ...expect 72 (409-480)
         (SELECT COUNT_IF(share_flagged_that_were_fraud IS NOT NULL OR share_of_fraud_caught IS NOT NULL  -- any number...
                 OR fraud_in_hour IS NOT NULL)                                  -- ...on a waiting hour...
          FROM workspace.fraud.model_accuracy_by_hour WHERE NOT verdicts_ready) AS waiting_with_numbers,  -- ...expect 0
         (SELECT format_string('%d / %d / %d', newest_hour_scored, newest_hour_with_verdicts, hours_waiting)  -- the waiting view
          FROM workspace.fraud.hours_waiting_for_verdicts) AS waiting_view,     -- expect 480 / 408 / 72
         (SELECT format_string('%d / %d / %d / %d', newest_hour_released, newest_hour_ingested,  -- the freshness view...
                               newest_hour_scored, newest_hour_flagged)         -- ...four stages
          FROM workspace.fraud.data_freshness) AS freshness,                    -- expect 480 / 480 / 480 / 480
         (SELECT concat_ws(', ', collect_list(format_string('%s %d at %d-%d',   -- the rejected shelf...
                 reason, rows_rejected, first_hour, last_hour)))                -- ...one entry per reason
          FROM workspace.fraud.rejected_rows_by_reason) AS rejected             -- expect bad_amount 5 at 350-350
  FROM ready)                                                                   -- one row
SELECT *, (confirmed_fraud = 405 AND checked_cases = 2916 AND all_fraud = 822   -- counts...
           AND share_flagged_that_were_fraud = 0.139 AND share_of_fraud_caught = 0.493  -- ...shares...
           AND hours_with_verdicts = 72 AND first_hour = 337 AND last_hour = 408  -- ...ready hours...
           AND hours_waiting = 72 AND waiting_with_numbers = 0                  -- ...waiting hours...
           AND waiting_view = '480 / 408 / 72' AND freshness = '480 / 480 / 480 / 480'  -- ...the two small views...
           AND rejected = 'bad_amount 5 at 350-350')                            -- ...and the shelf
          AS all_as_expected FROM result;                                       -- expect true

-- ── D7: at least one hour after run E finished (system tables lag, ruling R3). Highlight the block, Run: one row ──
WITH run_e AS (SELECT * FROM workspace.fraud.job_run_times                      -- the newest fraud-ingest run, one row per task
               WHERE job_name = 'fraud-ingest'                                  -- this job only
                 AND run_started_at = (SELECT MAX(run_started_at) FROM workspace.fraud.job_run_times  -- newest start...
                                       WHERE job_name = 'fraud-ingest')),       -- ...of fraud-ingest = run E
     silver AS (SELECT * FROM workspace.fraud.pipeline_update_times             -- the newest Silver update = run E's
                ORDER BY update_started_at DESC LIMIT 1),                       -- one row
     result AS (                                                                -- every D7 value side by side
  SELECT MAX(run_started_at) AS run_started_utc,                                -- when run E started (UTC)
         MAX(minutes_taken) AS run_minutes,                                     -- within 0.5 of the D4 duration
         MAX(outcome) AS run_outcome,                                           -- expect SUCCEEDED
         COUNT(*) AS task_rows,                                                 -- expect 8
         COUNT_IF(task_outcome = 'SUCCEEDED') AS tasks_succeeded,               -- expect 8
         MAX(IF(task_name = 'silver', task_minutes, NULL)) AS silver_task_minutes,  -- the job's silver step
         (SELECT minutes_taken FROM silver) AS silver_update_minutes,           -- expect fewer than silver_task_minutes
         (SELECT outcome FROM silver) AS silver_update_outcome,                 -- expect COMPLETED
         (SELECT full_rebuild FROM silver) AS silver_full_rebuild               -- expect false
  FROM run_e)                                                                   -- one row
SELECT *, (run_outcome = 'SUCCEEDED' AND task_rows = 8 AND tasks_succeeded = 8  -- the run...
           AND silver_update_outcome = 'COMPLETED' AND NOT silver_full_rebuild  -- ...the Silver update...
           AND silver_update_minutes < silver_task_minutes)                     -- ...inside its task
          AS all_as_expected FROM result;                                       -- expect true (compare run_minutes with D4 by eye)

-- ── D8: as the test user (member of fraud_managers only). Highlight the first statement, Run: one row; then the second ──
WITH ready AS (SELECT * FROM workspace.fraud.model_accuracy_by_hour WHERE verdicts_ready),  -- the row filter applies through the view
     hours AS (SELECT DISTINCT step, fraud_in_hour FROM ready),                -- fraud once per hour
     result AS (                                                                -- what the manager sees
  SELECT SUM(confirmed_fraud) AS confirmed_fraud,                               -- expect 405, the same as the owner
         SUM(closed_cases) AS checked_cases,                                    -- expect 2916
         (SELECT SUM(fraud_in_hour) FROM hours) AS all_fraud,                   -- expect 822
         SUM(flagged_payments) - SUM(closed_cases) AS open_visible,             -- expect 0: managers see closed cases only
         (SELECT COUNT(*) FROM workspace.fraud.model_accuracy_by_hour           -- rows of hours still waiting...
          WHERE NOT verdicts_ready) AS waiting_rows,                            -- ...expect 0: open hours are invisible
         (SELECT format_string('%d / %d / %d', newest_hour_scored, newest_hour_with_verdicts, hours_waiting)  -- the waiting view
          FROM workspace.fraud.hours_waiting_for_verdicts) AS waiting_view      -- expect 480 / 408 / 72, as the owner (review I1)
  FROM ready)                                                                   -- one row
SELECT *, (confirmed_fraud = 405 AND checked_cases = 2916 AND all_fraud = 822   -- the same numbers as the owner...
           AND open_visible = 0 AND waiting_rows = 0                            -- ...no open cases...
           AND waiting_view = '480 / 408 / 72')                                 -- ...and the same waiting count
          AS all_as_expected FROM result;                                       -- expect true
SELECT COUNT(*) AS runs FROM workspace.fraud.job_run_times;                     -- expect a permission error (engineers only)
