-- ── Gold verification (spec §12, sheet G3-G10). Expected values from scripts/expected_gold.py over data/paysim.csv, 2026-10-11. ──
-- Location: written for the default bundle variables (workspace.fraud). Run one block at a time: the SQL editor shows only the last result.

-- ── G3: the alert log (after run A; rerun after run B: must be unchanged) ──
SELECT COUNT(*) AS alerts,                                                     -- expect 3154
       COUNT(DISTINCT transaction_id) AS distinct_alerts,                      -- expect 3154 (one alert per payment)
       COUNT(DISTINCT step) AS hours,                                          -- expect 82
       MIN(step) AS first_step,                                                -- expect 337
       MAX(step) AS last_step,                                                 -- expect 418
       COUNT_IF(is_late_alert) AS late_alerts,                                 -- expect 0 (hourly files: plan ruling R3)
       (SELECT COUNT(*) FROM (SELECT step, alert_rank FROM workspace.fraud.fraud_alerts  -- ranks used twice in an hour...
                              GROUP BY step, alert_rank HAVING COUNT(*) > 1)) AS duplicate_ranks  -- ...expect 0
FROM workspace.fraud.fraud_alerts;                                             -- the alert log

-- ── G4: the alerts are exactly the top 50 per hour by score (run before any late alert exists) ──
WITH top AS (SELECT transaction_id FROM (                                      -- recompute the top 50 independently
               SELECT transaction_id,                                          -- payment
                      ROW_NUMBER() OVER (PARTITION BY step ORDER BY risk_score DESC, transaction_id) AS r  -- same ranking rule
               FROM workspace.fraud.transaction_risk_scores) WHERE r <= 50),   -- the decision log
     issued AS (SELECT transaction_id FROM workspace.fraud.fraud_alerts WHERE NOT is_late_alert)  -- on-time alerts
SELECT (SELECT COUNT(*) FROM top LEFT ANTI JOIN issued USING (transaction_id)) AS missing,  -- expect 0
       (SELECT COUNT(*) FROM issued LEFT ANTI JOIN top USING (transaction_id)) AS extra;    -- expect 0

-- ── G5: cases and verdicts ──
SELECT COUNT(*) AS cases,                                                      -- expect 3154 (one per alert)
       COUNT_IF(c.status = 'closed') AS closed,                                -- expect 262
       COUNT_IF(c.status = 'open') AS open,                                    -- expect 2892
       MAX(CASE WHEN c.status = 'closed' THEN c.step END) AS last_closed_step,  -- expect 346 (418 - 72)
       COUNT_IF(c.status = 'closed' AND c.verdict =                            -- verdicts equal the true label...
                CASE WHEN t.fraud_label = 1 THEN 'confirmed_fraud' ELSE 'false_alarm' END) AS verdicts_matching_label  -- ...expect 262
FROM workspace.fraud.alert_cases AS c                                          -- the case table
JOIN workspace.fraud.silver_transactions AS t USING (transaction_id);          -- labels

-- ── G6-owner: you (engineer + reviewer) see everything, unmasked ──
SELECT COUNT(*) AS cases,                                                      -- expect 3154
       COUNT_IF(sender_account = 'REDACTED' OR receiver_account = 'REDACTED') AS redacted  -- expect 0 (the job writes real names)
FROM workspace.fraud.alert_cases;                                              -- the case table
SELECT SUM(visible_cases) AS visible_cases,                                    -- expect 3154: the view shows you every case
       SUM(closed_cases) AS closed_cases                                       -- expect 262
FROM workspace.fraud.alert_summary_hourly;                                     -- the managers' summary view

-- ── G6-manager: run as the test user once it is in fraud_managers ──
SELECT COUNT(*) AS cases,                                                      -- expect 262 (closed only)
       COUNT_IF(status <> 'closed') AS open_visible,                           -- expect 0
       COUNT_IF(sender_account <> 'REDACTED' OR receiver_account <> 'REDACTED') AS unmasked  -- expect 0
FROM workspace.fraud.alert_cases;                                              -- the case table
SELECT SUM(visible_cases) AS visible_cases,                                    -- expect 262: the row filter applies through the view too
       SUM(closed_cases) AS closed_cases                                       -- expect 262
FROM workspace.fraud.alert_summary_hourly;                                     -- the managers' summary view

-- ── G9: the external export ──
SELECT (SELECT COUNT(*) FROM workspace.fraud.closed_alerts_export) AS exported,  -- expect 262 (equals closed cases)
       (SELECT COUNT(*) FROM workspace.fraud.alert_cases WHERE status = 'closed') AS closed;  -- expect 262
DESCRIBE DETAIL workspace.fraud.closed_alerts_export;                          -- location must start with r2://

-- ── G10: a held hour is alerted fresh when it arrives, earlier hours untouched (after runs C and D) ──
SELECT step,                                                                   -- simulated hour
       COUNT(*) AS alerts,                                                     -- expect 419: 50, 420: 50, 421: 14
       COUNT_IF(is_late_alert) AS late_alerts,                                 -- expect 0 for all three
       MIN(alerted_at) AS first_alerted_at                                     -- 419's must be later than 420's
FROM workspace.fraud.fraud_alerts WHERE step BETWEEN 419 AND 421               -- the drift hours released in runs C and D
GROUP BY step ORDER BY step;                                                   -- one row per hour
SELECT COUNT(*) AS alerts,                                                     -- expect 3268 (3154 + 50 + 50 + 14)
       (SELECT COUNT(*) FROM workspace.fraud.alert_cases WHERE status = 'closed') AS closed  -- expect 412 (cutoff 421 - 72 = 349)
FROM workspace.fraud.fraud_alerts;                                             -- the alert log
