-- ── Monitoring SQL task `monitor` (fraud-ingest, after `gold`, on the SQL warehouse). Phase 6a spec §5.1, ADR 0012. ──
-- Location: hard-coded to the bundle defaults workspace.fraud, like gold.sql (Global Constraints; CI pins the match).
-- Only plain views: they store nothing, so every run and rerun is safe. Each view is re-granted right after it is recreated.
-- Job and pipeline history comes from system.lakeflow, picked by name, never by ID. No ID column reaches a view.

-- ── 1. Is the model still good? Reads the label only for hours whose verdicts are in (owner ruling 2026-10-15) ──
CREATE OR REPLACE VIEW workspace.fraud.model_accuracy_by_hour (               -- one row per simulated hour and model version
  step COMMENT 'Simulated hour: one step is one hour of the replayed PaySim month.',  -- hour
  model_version COMMENT 'Which saved version of the fraud model flagged these payments.',  -- version
  flagged_payments COMMENT 'Flagged payments (cases) you may see for this hour. Managers see closed cases only.',  -- cases
  closed_cases COMMENT 'Cases with a verdict.',                                 -- verdict recorded
  confirmed_fraud COMMENT 'Closed cases that really were fraud.',               -- real fraud
  false_alarms COMMENT 'Closed cases that were honest payments.',               -- not fraud
  share_flagged_that_were_fraud COMMENT 'Of the flagged payments with a verdict, the share that were fraud. Empty until the verdicts are in.',  -- hit share
  fraud_in_hour COMMENT 'All fraud in this hour, flagged or not. Empty until the verdicts are in.',  -- every fraud
  share_of_fraud_caught COMMENT 'Of all the fraud in this hour, the share that was flagged. Empty until the verdicts are in.',  -- caught share
  verdicts_ready COMMENT 'True once the hour is 72 simulated hours older than the newest scored hour.'  -- ready flag
) COMMENT 'How good the flags were, per simulated hour and model version. The row filter on alert_cases applies to the reader.'  -- view comment
AS WITH cutoff AS (                                                             -- the newest hour whose verdicts are in
  SELECT (SELECT MAX(step) FROM workspace.fraud.transaction_risk_scores) - 72 AS last_ready_step),  -- same data clock as the closing MERGE
cases AS (                                                                      -- the reader's cases per hour and version
  SELECT step, model_version,                                                   -- keys
         COUNT(*) AS flagged_payments,                                          -- visible cases
         COUNT_IF(status = 'closed') AS closed_cases,                           -- with a verdict
         COUNT_IF(verdict = 'confirmed_fraud') AS confirmed_fraud,              -- real fraud
         COUNT_IF(verdict = 'false_alarm') AS false_alarms                      -- honest payments
  FROM workspace.fraud.alert_cases                                              -- the case table, filtered for the reader
  GROUP BY step, model_version),                                                -- one row per hour and version
fraud AS (                                                                      -- all fraud per hour, only once verdicts are in
  SELECT step, SUM(fraud_label) AS fraud_in_hour                                -- the label: the second of the two allowed reads
  FROM workspace.fraud.silver_transactions                                      -- clean payments
  WHERE step <= (SELECT MAX(step) FROM workspace.fraud.transaction_risk_scores) - 72  -- never before a real team would know
  GROUP BY step)                                                                -- one row per hour
SELECT c.step, c.model_version, c.flagged_payments, c.closed_cases, c.confirmed_fraud, c.false_alarms,  -- counts
       CASE WHEN c.step <= k.last_ready_step THEN try_divide(c.confirmed_fraud, c.closed_cases) END,  -- empty while waiting
       f.fraud_in_hour,                                                         -- empty while waiting (the LEFT JOIN finds nothing)
       CASE WHEN c.step <= k.last_ready_step THEN try_divide(c.confirmed_fraud, f.fraud_in_hour) END,  -- empty while waiting
       c.step <= k.last_ready_step                                              -- verdicts_ready
FROM cases AS c                                                                 -- the reader's cases
CROSS JOIN cutoff AS k                                                          -- one cutoff row
LEFT JOIN fraud AS f ON f.step = c.step;                                        -- fraud totals for ready hours only
GRANT SELECT ON TABLE workspace.fraud.model_accuracy_by_hour TO `fraud_engineers`;  -- engineers (the schema grant covers them too)
GRANT SELECT ON TABLE workspace.fraud.model_accuracy_by_hour TO `fraud_reviewers`;  -- reviewers
GRANT SELECT ON TABLE workspace.fraud.model_accuracy_by_hour TO `fraud_managers`;   -- managers: closed cases only, through the row filter

-- ── 2. Is the data fresh? Newest hour at each stage, and the latest run's wait from landing to scored ──
CREATE OR REPLACE VIEW workspace.fraud.data_freshness (                       -- one row
  newest_hour_released COMMENT 'Newest simulated hour copied to the landing folder.',  -- release
  newest_hour_ingested COMMENT 'Newest simulated hour loaded into the Bronze table.',  -- Bronze
  newest_hour_scored COMMENT 'Newest simulated hour the model has scored.',     -- scoring
  newest_hour_flagged COMMENT 'Newest simulated hour with flagged payments.',   -- Gold
  median_minutes_landing_to_scored COMMENT 'Latest scoring run only: half of its payments waited less than this many minutes from landing to being scored.',  -- typical wait
  slowest_minutes_landing_to_scored COMMENT 'Latest scoring run only: the longest wait in minutes from landing to being scored.'  -- longest wait
) COMMENT 'How fresh the data is at each stage, and how long the latest scored payments waited.'  -- view comment
AS WITH latest_run AS (                                                         -- payments scored by the newest scoring run
  SELECT timestampdiff(SECOND, t.file_arrived_at, s.scored_at) AS seconds_waited  -- landing to scored
  FROM workspace.fraud.transaction_risk_scores AS s                             -- the decision log
  JOIN workspace.fraud.silver_transactions AS t ON t.transaction_id = s.transaction_id  -- arrival time from Silver
  WHERE s.scored_at = (SELECT MAX(scored_at) FROM workspace.fraud.transaction_risk_scores))  -- newest run only (ruling R6)
SELECT (SELECT MAX(step) FROM workspace.fraud.release_log WHERE status = 'released'),  -- released (held hours excluded)
       (SELECT MAX(step) FROM workspace.fraud.bronze_transactions),             -- ingested
       (SELECT MAX(step) FROM workspace.fraud.transaction_risk_scores),         -- scored
       (SELECT MAX(step) FROM workspace.fraud.fraud_alerts),                    -- flagged
       (SELECT ROUND(median(seconds_waited) / 60.0, 1) FROM latest_run),        -- typical wait in minutes
       (SELECT ROUND(MAX(seconds_waited) / 60.0, 1) FROM latest_run);           -- longest wait in minutes
GRANT SELECT ON TABLE workspace.fraud.data_freshness TO `fraud_engineers`;     -- engineers only

-- ── 3. Is the data clean? Rows Silver set aside, by reason ──
CREATE OR REPLACE VIEW workspace.fraud.rejected_rows_by_reason (              -- one row per reason
  reason COMMENT 'The first check the row failed, as a code. bad_amount means the amount was missing or below zero.',  -- code
  rows_rejected COMMENT 'How many rows were set aside for this reason.',        -- count
  first_hour COMMENT 'First simulated hour with such a row.',                   -- earliest
  last_hour COMMENT 'Last simulated hour with such a row.'                      -- latest
) COMMENT 'Rows Silver set aside, by reason. The rows themselves stay in silver_rejected_transactions.'  -- view comment
AS SELECT rejection_reason, COUNT(*), MIN(step), MAX(step)                      -- reason, count, hour range
FROM workspace.fraud.silver_rejected_transactions                               -- the rejected shelf
GROUP BY rejection_reason;                                                      -- one row per reason
GRANT SELECT ON TABLE workspace.fraud.rejected_rows_by_reason TO `fraud_engineers`;  -- engineers only

-- ── 4. Are the jobs healthy? Minutes per run and per task, from the platform's own run history ──
CREATE OR REPLACE VIEW workspace.fraud.job_run_times (                        -- one row per job run and task
  job_name COMMENT 'The job, without any development-mode prefix.',             -- job
  run_started_at COMMENT 'When the run started.',                               -- start
  run_finished_at COMMENT 'When the run finished.',                             -- end
  minutes_taken COMMENT 'Minutes from the run start to its end, including start-up and waiting.',  -- run minutes
  outcome COMMENT 'How the run ended, such as SUCCEEDED or FAILED. Empty while it is still running.',  -- run result
  task_name COMMENT 'One step of the run, such as ingest or score.',            -- task
  task_minutes COMMENT 'Minutes from the task start to its end, a retry included.',  -- task minutes
  task_outcome COMMENT 'How the task ended.'                                    -- task result
) COMMENT 'Job runs of fraud-ingest and fraud-train from system.lakeflow, picked by name. Rows arrive up to an hour after a run ends.'  -- view comment
AS WITH job_names AS (                                                          -- the newest name of every job
  SELECT workspace_id, job_id, regexp_replace(name, '^\\[dev [^\\]]*\\] ', '') AS job_name  -- prefix stripped (ruling R2)
  FROM system.lakeflow.jobs                                                     -- one row per job change
  QUALIFY ROW_NUMBER() OVER (PARTITION BY workspace_id, job_id ORDER BY change_time DESC) = 1),  -- latest change only
runs AS (                                                                       -- one row per job run
  SELECT workspace_id, job_id, run_id,                                          -- keys (never shown)
         MIN(period_start_time) AS run_started_at,                              -- earliest slice start
         MAX(period_end_time) AS run_finished_at,                               -- latest slice end
         MAX_BY(result_state, period_end_time) AS outcome                       -- the last slice holds the result
  FROM system.lakeflow.job_run_timeline                                         -- runs longer than an hour have several slices
  GROUP BY workspace_id, job_id, run_id),                                       -- one row per run
tasks AS (                                                                      -- one row per task of a run
  SELECT workspace_id, job_id, job_run_id, task_key,                            -- keys (never shown)
         MIN(period_start_time) AS task_started_at,                             -- first attempt start
         MAX(period_end_time) AS task_finished_at,                              -- last attempt end
         MAX_BY(result_state, period_end_time) AS task_outcome                  -- the last attempt's result
  FROM system.lakeflow.job_task_run_timeline                                    -- task slices and retries
  GROUP BY workspace_id, job_id, job_run_id, task_key)                          -- one row per task, a retry included
SELECT n.job_name, r.run_started_at, r.run_finished_at,                         -- run
       ROUND(timestampdiff(SECOND, r.run_started_at, r.run_finished_at) / 60.0, 1),  -- minutes_taken
       r.outcome, t.task_key,                                                   -- result and task_name
       ROUND(timestampdiff(SECOND, t.task_started_at, t.task_finished_at) / 60.0, 1),  -- task_minutes
       t.task_outcome                                                           -- task result
FROM runs AS r                                                                  -- every run
JOIN job_names AS n ON n.workspace_id = r.workspace_id AND n.job_id = r.job_id  -- its job's name
LEFT JOIN tasks AS t ON t.workspace_id = r.workspace_id AND t.job_id = r.job_id AND t.job_run_id = r.run_id  -- its tasks
WHERE n.job_name IN ('fraud-ingest', 'fraud-train');                            -- this project's jobs, by name
GRANT SELECT ON TABLE workspace.fraud.job_run_times TO `fraud_engineers`;      -- engineers only

-- ── 5. Is the cleaning pipeline healthy? Minutes per update of the Silver pipeline ──
CREATE OR REPLACE VIEW workspace.fraud.pipeline_update_times (                -- one row per pipeline update
  pipeline_name COMMENT 'The pipeline, without any development-mode prefix.',   -- pipeline
  update_started_at COMMENT 'When the update started.',                         -- start
  update_finished_at COMMENT 'When the update finished.',                       -- end
  minutes_taken COMMENT 'Minutes from the update start to its end.',            -- minutes
  outcome COMMENT 'How the update ended, such as COMPLETED or FAILED.',         -- result
  full_rebuild COMMENT 'True when the update redid every table from the start instead of only new rows.'  -- full refresh
) COMMENT 'Updates of the fraud-silver pipeline from system.lakeflow, picked by name.'  -- view comment
AS WITH pipeline_names AS (                                                     -- the newest name of every pipeline
  SELECT workspace_id, pipeline_id, regexp_replace(name, '^\\[dev [^\\]]*\\] ', '') AS pipeline_name  -- prefix stripped
  FROM system.lakeflow.pipelines                                                -- one row per pipeline change
  QUALIFY ROW_NUMBER() OVER (PARTITION BY workspace_id, pipeline_id ORDER BY change_time DESC) = 1),  -- latest change only
updates AS (                                                                    -- one row per update
  SELECT workspace_id, pipeline_id, update_id,                                  -- keys (never shown)
         MIN(period_start_time) AS update_started_at,                           -- earliest slice start
         MAX(period_end_time) AS update_finished_at,                            -- latest slice end
         MAX_BY(result_state, period_end_time) AS outcome,                      -- the last slice holds the result
         bool_or(update_type = 'FULL_REFRESH' OR coalesce(size(full_refresh_selection), 0) > 0) AS full_rebuild  -- any full refresh
  FROM system.lakeflow.pipeline_update_timeline                                 -- update slices
  GROUP BY workspace_id, pipeline_id, update_id)                                -- one row per update
SELECT n.pipeline_name, u.update_started_at, u.update_finished_at,              -- update
       ROUND(timestampdiff(SECOND, u.update_started_at, u.update_finished_at) / 60.0, 1),  -- minutes_taken
       u.outcome, u.full_rebuild                                                -- result
FROM updates AS u                                                               -- every update
JOIN pipeline_names AS n ON n.workspace_id = u.workspace_id AND n.pipeline_id = u.pipeline_id  -- its pipeline's name
WHERE n.pipeline_name = 'fraud-silver';                                         -- this project's pipeline, by name
GRANT SELECT ON TABLE workspace.fraud.pipeline_update_times TO `fraud_engineers`;  -- engineers only
