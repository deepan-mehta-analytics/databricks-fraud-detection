-- ── Health check verification (Phase 6b spec §6-7, sheet V1a-V1d). Expected values from the state at v0.5.0: newest hour 480, 5 rejected rows at hour 350. ──
-- Location: written for the default bundle variables (workspace.fraud). Run one block at a time: highlight it, Run; each block returns one row.
-- V1a and V1b are the two health checks' questions exactly as deployed (resources/fraud_health_checks.yml); V1c and V1d change one thing to show a problem would be caught.

-- ── V1a: stages behind, today. Expect one column hours_behind = 0 (quiet) ──
WITH newest AS (                                                          -- newest hour at each stage
  SELECT (SELECT MAX(step) FROM workspace.fraud.release_log
          WHERE status = 'released')                    AS released,      -- held hours excluded
         (SELECT MAX(step) FROM workspace.fraud.bronze_transactions) AS ingested,  -- Bronze
         (SELECT MAX(step) FROM workspace.fraud.silver_transactions) AS cleaned,   -- Silver
         (SELECT MAX(step) FROM workspace.fraud.transaction_risk_scores) AS scored) -- model
SELECT GREATEST(released - ingested, released - cleaned, released - scored) AS hours_behind  -- worst gap
FROM newest;                                                              -- always one row

-- ── V1b: rejected rows in the newest 24 released hours, today (hours 457-480). Expect one column new_rejected_rows = 0 (quiet) ──
SELECT COUNT(*) AS new_rejected_rows                                      -- rows set aside
FROM workspace.fraud.silver_rejected_transactions                         -- the rejected shelf
WHERE step > (SELECT MAX(step) FROM workspace.fraud.release_log
              WHERE status = 'released') - 24;                            -- newest 24 released hours

-- ── V1c: the same count over hours 327-350, which hold the 5 rows Phase 3 broke on purpose. Expect new_rejected_rows = 5 (would alert) ──
SELECT COUNT(*) AS new_rejected_rows                                      -- rows set aside
FROM workspace.fraud.silver_rejected_transactions                         -- the rejected shelf
WHERE step BETWEEN 327 AND 350;                                           -- a past 24-hour window with known bad rows

-- ── V1d: stages behind if hour 481 had been released but not loaded. Expect hours_behind = 1 (would alert) ──
WITH newest AS (                                                          -- newest hour at each stage
  SELECT 481                                            AS released,      -- pretend one more hour was released
         (SELECT MAX(step) FROM workspace.fraud.bronze_transactions) AS ingested,  -- Bronze
         (SELECT MAX(step) FROM workspace.fraud.silver_transactions) AS cleaned,   -- Silver
         (SELECT MAX(step) FROM workspace.fraud.transaction_risk_scores) AS scored) -- model
SELECT GREATEST(released - ingested, released - cleaned, released - scored) AS hours_behind  -- worst gap
FROM newest;                                                              -- always one row
