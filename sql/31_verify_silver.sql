-- ── Silver verification (spec §8, S2-S6). Expected values come from scripts/expected_silver.py (Task 4). ──
-- Named parameters (:receiver, :pipeline_id) are typed into the SQL editor's parameter boxes; never commit real IDs.

-- ── S2: accounting and counts (one row) ──
WITH bronze AS (SELECT COUNT(*) AS n FROM workspace.fraud.bronze_transactions),   -- all Bronze rows
     clean AS (SELECT COUNT(*) AS n, SUM(fraud_label) AS fraud,                   -- clean rows and fraud...
                      COUNT(DISTINCT transaction_id) AS ids                       -- ...and distinct IDs
               FROM workspace.fraud.silver_transactions),                         -- clean table
     shelf AS (SELECT COUNT(*) AS n FROM workspace.fraud.silver_rejected_transactions)  -- rejected rows
SELECT bronze.n AS bronze_rows,                                                   -- expect <filled in Task 4>
       clean.n AS silver_rows,                                                    -- expect <filled in Task 4>
       shelf.n AS rejected_rows,                                                  -- expect <filled in Task 4>
       bronze.n - clean.n - shelf.n AS duplicate_copies_removed,                  -- expect <filled in Task 4>
       clean.fraud AS silver_fraud,                                               -- expect <filled in Task 4>
       clean.ids = clean.n AS ids_unique                                          -- expect true
FROM bronze, clean, shelf;                                                        -- one row

-- ── S2: rejected rows by reason ──
SELECT rejection_reason, COUNT(*) AS row_count                                    -- per reason
FROM workspace.fraud.silver_rejected_transactions                                 -- rejected shelf
GROUP BY rejection_reason ORDER BY rejection_reason;                              -- expect <filled in Task 4>

-- ── S4: features as the pipeline computed them, for one receiver (:receiver from Task 4) ──
SELECT transaction_id, step,                                                      -- keys
       receiver_payments_previous_hour, receiver_payments_last_24_hours,          -- counts
       receiver_amount_last_24_hours, receiver_largest_amount_last_24_hours,      -- money
       receiver_distinct_senders_last_24_hours,                                   -- payers
       ROUND(amount_vs_receiver_average_24_hours, 4) AS ratio_4dp,                -- rounded for comparison
       sender_earlier_payments                                                    -- sender history
FROM workspace.fraud.silver_transaction_features                                  -- feature table
WHERE receiver_account = :receiver                                                -- the chosen receiver
ORDER BY step, transaction_id;                                                    -- same order as the calculator

-- ── S4: the same numbers by an independent method (self-join, no window functions) ──
SELECT t.transaction_id, t.step,                                                  -- the judged payment
       COUNT_IF(h.step = t.step - 1) AS receiver_payments_previous_hour,          -- previous hour
       COUNT(h.transaction_id) AS receiver_payments_last_24_hours,                -- 24 hours before
       SUM(h.amount) AS receiver_amount_last_24_hours,                            -- money (NULL when none)
       MAX(h.amount) AS receiver_largest_amount_last_24_hours,                    -- largest (NULL when none)
       COUNT(DISTINCT h.sender_account) AS receiver_distinct_senders_last_24_hours  -- payers
FROM workspace.fraud.silver_transactions t                                        -- each payment to the receiver
LEFT JOIN workspace.fraud.silver_transactions h                                   -- its earlier payments
  ON h.receiver_account = t.receiver_account                                      -- same receiver
 AND h.step BETWEEN t.step - 24 AND t.step - 1                                    -- strict past, 24 steps
WHERE t.receiver_account = :receiver                                              -- the chosen receiver
GROUP BY t.transaction_id, t.step                                                 -- one row per payment
ORDER BY t.step, t.transaction_id;                                                -- same order

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
