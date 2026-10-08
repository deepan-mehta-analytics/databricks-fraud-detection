-- ── Phase 4 verification (spec §8, M4/M5/M7). Expected values measured 2026-10-08 from data/paysim.csv and the S5 totals. ──
-- Hard-codes workspace.fraud like sql/31 (the bundle variables' defaults); edit the names if the bundle variables change.

-- ── M4: after promoting the D=3 version to @champion and one job run with no release ──
SELECT COUNT(*)                         AS scored_rows,        -- expect 1205673
       COUNT(DISTINCT transaction_id)   AS distinct_ids,       -- expect 1205673 (never scored twice)
       MIN(step)                        AS first_step,         -- expect 337
       MAX(step)                        AS last_step,          -- expect 417
       COUNT(DISTINCT model_version)    AS model_versions      -- expect 1
FROM workspace.fraud.transaction_risk_scores;                  -- the decision log

SELECT COUNT(*) AS silver_rows_to_score                        -- expect 1205673 (1202637 replay + 3036 drift from S5)
FROM workspace.fraud.silver_transactions                       -- clean payments
WHERE step >= 337;                                             -- same filter as the score task

SELECT COUNT(*) AS answer_columns_in_log                       -- expect 0
FROM workspace.information_schema.columns                      -- catalog metadata
WHERE table_schema = 'fraud' AND table_name = 'transaction_risk_scores'  -- the decision log
  AND column_name IN ('fraud_label', 'flagged_by_old_rules');  -- no answer stored with a decision

SELECT COUNT(*) AS features_differ_from_silver                 -- expect 0 (no late file since scoring)
FROM workspace.fraud.transaction_risk_scores s                 -- features as the model saw them
JOIN workspace.fraud.silver_transaction_features f USING (transaction_id)  -- features in Silver now
WHERE NOT (s.receiver_payments_previous_hour <=> CAST(f.receiver_payments_previous_hour AS DOUBLE)                  -- count, previous hour
       AND s.receiver_payments_last_24_hours <=> CAST(f.receiver_payments_last_24_hours AS DOUBLE)                  -- count, 24 hours
       AND s.receiver_amount_last_24_hours <=> CAST(f.receiver_amount_last_24_hours AS DOUBLE)                      -- sum (NULL-safe)
       AND s.receiver_largest_amount_last_24_hours <=> CAST(f.receiver_largest_amount_last_24_hours AS DOUBLE)      -- max (NULL-safe)
       AND s.receiver_distinct_senders_last_24_hours <=> CAST(f.receiver_distinct_senders_last_24_hours AS DOUBLE)  -- distinct payers
       AND s.amount_vs_receiver_average_24_hours <=> f.amount_vs_receiver_average_24_hours                          -- ratio (NULL-safe)
       AND s.sender_earlier_payments <=> CAST(f.sender_earlier_payments AS DOUBLE));                                -- sender history

-- ── M5: run the job again (nothing to release): scored_rows above must still be 1205673 ──

-- ── M7: after promoting version 2 and releasing drift step 418 (6 rows, all fraud, measured) ──
SELECT model_version,                                          -- expect two rows:
       COUNT(*)  AS scored_rows,                               --   version 1: 1205673 rows, steps 337-417
       MIN(step) AS first_step,                                --   version 2: 6 rows, steps 418-418
       MAX(step) AS last_step                                  -- last step scored by this version
FROM workspace.fraud.transaction_risk_scores                   -- the decision log
GROUP BY model_version                                         -- one row per version
ORDER BY CAST(model_version AS INT);                           -- numeric order (text would put 10 before 2)
