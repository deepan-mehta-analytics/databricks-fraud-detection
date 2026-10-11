-- ── Gold SQL task `gold` (fraud-ingest, after `score`, on the SQL warehouse). Spec §5-7, ADR 0010. ──
-- Location: hard-coded to the bundle defaults workspace.fraud (Global Constraints; CI pins the match).
-- Every write is safe to rerun: alerts are inserted once per payment, cases open once and close once.

-- ── 0. Refuse to run as anyone outside fraud_engineers: masked or filtered reads would corrupt the tables (final review I1) ──
SELECT assert_true(is_account_group_member('fraud_engineers'),                 -- the job identity must be an engineer...
                   'Gold must run as a member of fraud_engineers, masked or filtered reads would corrupt the tables');  -- ...or stop before reading anything

-- ── 1. Tables and view (the first run creates them; later runs leave them alone, plan ruling R1) ──
CREATE TABLE IF NOT EXISTS workspace.fraud.fraud_alerts (                      -- the alert log, append-only
  transaction_id STRING NOT NULL,                                               -- the flagged payment
  step BIGINT NOT NULL,                                                         -- simulated hour
  alert_rank INT NOT NULL,                                                      -- 1 = most suspicious in its hour
  risk_score DOUBLE NOT NULL,                                                   -- model score (a ranking, not a probability)
  model_version STRING NOT NULL,                                                -- which model version scored it
  amount DOUBLE,                                                                -- amount as the model saw it
  transaction_type STRING,                                                      -- payment type
  sender_account STRING,                                                        -- paying account (masked for managers)
  receiver_account STRING,                                                      -- receiving account (masked for managers)
  is_late_alert BOOLEAN NOT NULL,                                               -- added after its hour was first alerted
  alerted_at TIMESTAMP NOT NULL                                                 -- when Gold issued it
) COMMENT 'Append-only alert log: the top 50 payments per simulated hour, never rewritten (ADR 0010).';  -- table comment

CREATE TABLE IF NOT EXISTS workspace.fraud.alert_cases (                       -- one investigation per alert
  transaction_id STRING NOT NULL,                                               -- the alerted payment
  step BIGINT NOT NULL,                                                         -- simulated hour
  risk_score DOUBLE NOT NULL,                                                   -- copied from the alert
  model_version STRING NOT NULL,                                                -- copied from the alert
  sender_account STRING,                                                        -- paying account (masked for managers)
  receiver_account STRING,                                                      -- receiving account (masked for managers)
  status STRING NOT NULL,                                                       -- open, then closed
  verdict STRING,                                                               -- confirmed_fraud or false_alarm once closed
  opened_at TIMESTAMP NOT NULL,                                                 -- when the case opened
  closed_at TIMESTAMP                                                           -- when the verdict was recorded
) COMMENT 'Case table: open until the (simulated) reviewer records a verdict 72 simulated hours later (ADR 0010).';  -- table comment

CREATE VIEW IF NOT EXISTS workspace.fraud.alert_summary_hourly                 -- managers' summary, a saved question
COMMENT 'Per simulated hour: alerts, closed cases and verdicts. Row filters on alert_cases still apply to the reader.'  -- view comment
AS SELECT step,                                                                 -- simulated hour
          COUNT(*) AS visible_cases,                                            -- cases this reader may see (the row filter applies)
          COUNT_IF(status = 'closed') AS closed_cases,                          -- investigated
          COUNT_IF(verdict = 'confirmed_fraud') AS confirmed_fraud,             -- real fraud
          COUNT_IF(verdict = 'false_alarm') AS false_alarms,                    -- not fraud
          try_divide(COUNT_IF(verdict = 'confirmed_fraud'), COUNT_IF(status = 'closed')) AS confirmed_share  -- fraud share of closed cases
   FROM workspace.fraud.alert_cases                                             -- the case table
   GROUP BY step;                                                               -- one row per hour

-- ── 2. New alerts: top 50 for never-alerted hours, plus late payments that earn a place ──
MERGE INTO workspace.fraud.fraud_alerts AS a                                   -- the alert log
USING (                                                                         -- alerts to add this run
  WITH issued AS (                                                              -- what each alerted hour already has
    SELECT step,                                                                -- simulated hour
           COUNT(*) AS alerts_issued,                                           -- alerts so far
           MIN(risk_score) AS lowest_alert_score,                               -- the bar a late payment must beat
           MAX(alert_rank) AS last_rank                                         -- late alerts are numbered after this
    FROM workspace.fraud.fraud_alerts                                           -- the log as it stands before this run
    GROUP BY step),                                                             -- one row per alerted hour
  new_hour_alerts AS (                                                          -- hours with scores but no alerts yet
    SELECT * FROM (                                                             -- rank first, then keep the top 50
      SELECT s.transaction_id, s.step, s.risk_score, s.model_version, s.amount, s.transaction_type,  -- score row
             ROW_NUMBER() OVER (PARTITION BY s.step ORDER BY s.risk_score DESC, s.transaction_id) AS alert_rank,  -- ties go to the smaller ID
             FALSE AS is_late_alert                                             -- on time
      FROM workspace.fraud.transaction_risk_scores AS s                         -- the decision log
      LEFT ANTI JOIN issued AS i ON i.step = s.step) AS ranked                  -- only hours never alerted
    WHERE alert_rank <= 50),                                                    -- the hourly budget (ALERT_BUDGET_DEFAULT)
  late_alerts AS (                                                              -- payments that reached an already-alerted hour later
    SELECT w.transaction_id, w.step, w.risk_score, w.model_version, w.amount, w.transaction_type,  -- score row
           i.last_rank + w.late_rank AS alert_rank,                             -- numbered after the hour's alerts
           TRUE AS is_late_alert                                                -- flagged as late
    FROM (                                                                      -- late payments, best first within each hour
      SELECT s.transaction_id, s.step, s.risk_score, s.model_version, s.amount, s.transaction_type,  -- score row
             ROW_NUMBER() OVER (PARTITION BY s.step ORDER BY s.risk_score DESC, s.transaction_id) AS late_rank  -- best late payment first
      FROM workspace.fraud.transaction_risk_scores AS s                         -- the decision log
      LEFT SEMI JOIN issued AS h ON h.step = s.step                             -- hours already alerted
      LEFT ANTI JOIN workspace.fraud.fraud_alerts AS f ON f.transaction_id = s.transaction_id) AS w  -- not alerted yet
    JOIN issued AS i ON i.step = w.step                                         -- the hour's alerts so far
    WHERE w.late_rank <= 50 - i.alerts_issued OR w.risk_score > i.lowest_alert_score)  -- fill the room left first, then only payments beating the lowest alert (late_alerts_earned)
  SELECT c.*, t.sender_account, t.receiver_account                              -- add the account names reviewers need
  FROM (SELECT * FROM new_hour_alerts UNION ALL SELECT * FROM late_alerts) AS c  -- every candidate, same column order
  JOIN workspace.fraud.silver_transactions AS t ON t.transaction_id = c.transaction_id  -- clean payments
) AS n                                                                          -- new alerts
ON a.transaction_id = n.transaction_id                                          -- one alert per payment
WHEN NOT MATCHED THEN INSERT (transaction_id, step, alert_rank, risk_score, model_version, amount, transaction_type,  -- columns...
                             sender_account, receiver_account, is_late_alert, alerted_at)  -- ...in table order
  VALUES (n.transaction_id, n.step, n.alert_rank, n.risk_score, n.model_version, n.amount, n.transaction_type,  -- values...
          n.sender_account, n.receiver_account, n.is_late_alert, current_timestamp());  -- ...stamped now

-- ── 3. Open one case per new alert ──
MERGE INTO workspace.fraud.alert_cases AS c                                    -- the case table
USING (SELECT a.transaction_id, a.step, a.risk_score, a.model_version,          -- every alert...
              t.sender_account, t.receiver_account                              -- ...with names straight from Silver, never through the masked log (I1)
       FROM workspace.fraud.fraud_alerts AS a                                   -- the alert log
       JOIN workspace.fraud.silver_transactions AS t ON t.transaction_id = a.transaction_id) AS a  -- clean payments
ON c.transaction_id = a.transaction_id                                          -- one case per alert
WHEN NOT MATCHED THEN INSERT (transaction_id, step, risk_score, model_version, sender_account, receiver_account,  -- columns...
                             status, verdict, opened_at, closed_at)             -- ...in table order
  VALUES (a.transaction_id, a.step, a.risk_score, a.model_version, a.sender_account, a.receiver_account,  -- copied from the alert
          'open', NULL, current_timestamp(), NULL);                             -- a new case starts open

-- ── 4. Close cases 72 simulated hours old with the (simulated) reviewer's verdict ──
MERGE INTO workspace.fraud.alert_cases AS c                                    -- the case table
USING (                                                                         -- cases old enough to close
  SELECT o.transaction_id,                                                      -- the case
         CASE WHEN t.fraud_label = 1 THEN 'confirmed_fraud' ELSE 'false_alarm' END AS verdict  -- the true label, read only here
  FROM workspace.fraud.alert_cases AS o                                         -- the case table
  JOIN workspace.fraud.silver_transactions AS t ON t.transaction_id = o.transaction_id  -- clean payments hold the label
  WHERE o.status = 'open'                                                       -- not yet closed
    AND o.step <= (SELECT MAX(step) FROM workspace.fraud.transaction_risk_scores) - 72  -- 24 x LABEL_DELAY_DAYS_DEFAULT, data clock
) AS v                                                                          -- verdicts to record
ON c.transaction_id = v.transaction_id                                          -- the matching case
WHEN MATCHED AND c.status = 'open' THEN UPDATE SET status = 'closed', verdict = v.verdict, closed_at = current_timestamp();  -- close once
