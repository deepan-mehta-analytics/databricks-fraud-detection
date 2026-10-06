-- ── Silver verification (spec §8, S2-S6). Expected values measured 2026-10-06 with scripts/expected_silver.py over data/paysim.csv. ──
-- Location: written for the default bundle variables (catalog workspace, schema fraud); edit the table names if you changed them.
-- S2's duplicate count is derived by subtraction; S3's first_copy = 10 on the Data quality tab is the independent check.
-- Named parameters (:receiver, :pipeline_id) are typed into the SQL editor's parameter boxes; never commit real IDs.

-- ── S2: accounting and counts (one row) ──
WITH bronze AS (SELECT COUNT(*) AS n FROM workspace.fraud.bronze_transactions),   -- all Bronze rows
     clean AS (SELECT COUNT(*) AS n, SUM(fraud_label) AS fraud,                   -- clean rows and fraud...
                      COUNT(DISTINCT transaction_id) AS ids                       -- ...and distinct IDs
               FROM workspace.fraud.silver_transactions),                         -- clean table
     shelf AS (SELECT COUNT(*) AS n FROM workspace.fraud.silver_rejected_transactions)  -- rejected rows
SELECT bronze.n AS bronze_rows,                                                   -- expect 5987427 (measured 2026-10-06)
       clean.n AS silver_rows,                                                    -- expect 5987412 (measured 2026-10-06)
       shelf.n AS rejected_rows,                                                  -- expect 5 (measured 2026-10-06)
       bronze.n - clean.n - shelf.n AS duplicate_copies_removed,                  -- expect 10 (measured 2026-10-06)
       clean.fraud AS silver_fraud,                                               -- expect 4589 (measured 2026-10-06)
       clean.ids = clean.n AS ids_unique                                          -- expect true
FROM bronze, clean, shelf;                                                        -- one row

-- ── S2: rejected rows by reason ──
SELECT rejection_reason, COUNT(*) AS row_count                                    -- per reason
FROM workspace.fraud.silver_rejected_transactions                                 -- rejected shelf
GROUP BY rejection_reason ORDER BY rejection_reason;                              -- expect one row: bad_amount 5 (measured 2026-10-06)

-- ── S4: features as the pipeline computed them, for one receiver (:receiver = the spot-check receiver) ──
SELECT transaction_id, step,                                                      -- keys
       receiver_payments_previous_hour, receiver_payments_last_24_hours,          -- counts
       receiver_amount_last_24_hours, receiver_largest_amount_last_24_hours,      -- money
       receiver_distinct_senders_last_24_hours,                                   -- payers
       ROUND(amount_vs_receiver_average_24_hours, 4) AS ratio_4dp,                -- rounded for comparison
       sender_earlier_payments                                                    -- sender history
FROM workspace.fraud.silver_transaction_features                                  -- feature table
WHERE receiver_account = :receiver                                                -- the chosen receiver
ORDER BY step, transaction_id;                                                    -- same order as the calculator

-- ── S4: the same numbers by an independent method (self-joins, no window functions) ──
WITH judged AS (                                                                  -- each payment to the receiver
  SELECT transaction_id, step, amount, sender_account                             -- what the joins need
  FROM workspace.fraud.silver_transactions                                        -- clean table
  WHERE receiver_account = :receiver),                                            -- the chosen receiver
receiver_history AS (                                                             -- the receiver's 24 hours before
  SELECT t.transaction_id,                                                        -- the judged payment
         COUNT_IF(h.step = t.step - 1) AS receiver_payments_previous_hour,        -- previous hour
         COUNT(h.transaction_id) AS receiver_payments_last_24_hours,              -- 24 hours before
         SUM(h.amount) AS receiver_amount_last_24_hours,                          -- money (NULL when none)
         MAX(h.amount) AS receiver_largest_amount_last_24_hours,                  -- largest (NULL when none)
         COUNT(DISTINCT h.sender_account) AS receiver_distinct_senders_last_24_hours,  -- payers
         ROUND(try_divide(CAST(MAX(t.amount) AS DOUBLE),                          -- this payment's size...
               try_divide(CAST(SUM(h.amount) AS DOUBLE),                          -- ...over the average...
                          CAST(COUNT(h.transaction_id) AS DOUBLE))), 4) AS ratio_4dp  -- ...NULL when no history or zero average
  FROM judged t                                                                   -- each judged payment
  LEFT JOIN workspace.fraud.silver_transactions h                                 -- its earlier payments
    ON h.receiver_account = :receiver                                             -- same receiver
   AND h.step BETWEEN t.step - 24 AND t.step - 1                                  -- strict past, 24 steps
  GROUP BY t.transaction_id),                                                     -- one row per payment
sender_history AS (                                                               -- the sender's whole earlier history
  SELECT t.transaction_id,                                                        -- the judged payment
         COUNT(s.transaction_id) AS sender_earlier_payments                       -- earlier hours only
  FROM judged t                                                                   -- each judged payment
  LEFT JOIN workspace.fraud.silver_transactions s                                 -- the sender's payments
    ON s.sender_account = t.sender_account                                        -- same sender
   AND s.step < t.step                                                            -- strict past, all hours
  GROUP BY t.transaction_id)                                                      -- one row per payment
SELECT j.transaction_id, j.step,                                                  -- keys
       r.receiver_payments_previous_hour, r.receiver_payments_last_24_hours,      -- counts
       r.receiver_amount_last_24_hours, r.receiver_largest_amount_last_24_hours,  -- money
       r.receiver_distinct_senders_last_24_hours, r.ratio_4dp,                    -- payers and ratio
       s.sender_earlier_payments                                                  -- sender history
FROM judged j                                                                     -- each judged payment
JOIN receiver_history r USING (transaction_id)                                    -- receiver features
JOIN sender_history s USING (transaction_id)                                      -- sender feature
ORDER BY j.step, j.transaction_id;                                                -- same order as the calculator

-- ── S6: refresh technique per flow, newest first (pipeline ID from the pipeline page) ──
SELECT timestamp, message                                                         -- e.g. "Flow '...' has been planned to be executed as ROW_BASED."
FROM event_log(:pipeline_id)                                                      -- the pipeline's event log
WHERE event_type = 'planning_information'                                         -- refresh-technique decisions
ORDER BY timestamp DESC;                                                          -- newest first

-- ── S6: update durations, newest first ──
SELECT origin.update_id,                                                          -- one pipeline update
       MIN(timestamp) AS started_at, MAX(timestamp) AS finished_at,               -- first and last event
       timestampdiff(SECOND, MIN(timestamp), MAX(timestamp)) AS seconds           -- duration
FROM event_log(:pipeline_id)                                                      -- the pipeline's event log
WHERE event_type = 'update_progress'                                              -- update state changes
GROUP BY origin.update_id ORDER BY started_at DESC;                               -- newest first
