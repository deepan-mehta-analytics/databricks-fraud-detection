-- ── System-table probes P1 and D1b (Phase 6a spec §3, §7). Done by the owner on 2026-10-15; kept so the result can be reproduced. ──
-- Run in the SQL editor on the Serverless Starter Warehouse. The rows carry account, workspace and job IDs: never copy them into the repo.

-- ── P1: are system tables there at all? (2026-10-15: 12 schemas, lakeflow among them) ──
SHOW SCHEMAS IN system;                                                         -- expect lakeflow in the list
SELECT * FROM system.lakeflow.job_run_timeline LIMIT 5;                         -- 2026-10-15: readable; *_duration_seconds all 0

-- ── D1b: which job and pipeline tables exist? (2026-10-15: 8 tables) ──
SHOW TABLES IN system.lakeflow;                                                 -- expect job_run_timeline, job_task_run_timeline, jobs, pipeline_update_timeline, pipelines

-- ── Column check: the columns the monitoring views use (docs fetched 2026-10-15) ──
DESCRIBE TABLE system.lakeflow.jobs;                                            -- workspace_id, job_id, name, change_time
DESCRIBE TABLE system.lakeflow.job_task_run_timeline;                           -- job_run_id, task_key, period_start_time, period_end_time, result_state
DESCRIBE TABLE system.lakeflow.pipelines;                                       -- workspace_id, pipeline_id, name, change_time
DESCRIBE TABLE system.lakeflow.pipeline_update_timeline;                        -- update_id, update_type, full_refresh_selection, result_state
