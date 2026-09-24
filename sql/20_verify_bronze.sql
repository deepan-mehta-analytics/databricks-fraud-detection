-- ── V2 (after run 1) / V3 (after run 13): totals. Expected values: see plan Task 9. ──
SELECT COUNT(*) AS row_count,                              -- all Bronze rows
       SUM(fraud_label) AS fraud_rows,                     -- fraud rows
       COUNT(DISTINCT transaction_id) AS distinct_ids,     -- unique transactions
       COUNT_IF(_rescued_data IS NOT NULL) AS rescued_total, -- expect 5 after run 13 (0 before the malformed run)
       COUNT_IF(transaction_time IS NULL) AS null_times    -- expect 0: every row must carry a parsed event time
FROM workspace.fraud.bronze_transactions;                  -- Bronze table

-- ── V4 duplicate proof: step 340 appears twice per transaction ──
SELECT COUNT(*) AS ids_seen_twice                          -- expected 10 (step 340 has 10 rows)
FROM (SELECT transaction_id FROM workspace.fraud.bronze_transactions  -- Bronze rows
      WHERE step = 340 GROUP BY transaction_id HAVING COUNT(*) = 2);   -- ids loaded twice

-- ── V4 late proof: step 345's file arrived after steps 346-348 ──
SELECT step, MIN(file_arrived_at) AS arrived               -- first arrival per step
FROM workspace.fraud.bronze_transactions                   -- Bronze table
WHERE step BETWEEN 343 AND 348                             -- the held step and its neighbours
GROUP BY step ORDER BY arrived;                            -- 345 should come last

-- ── V4 schema-change proof: channel present from step 360 only ──
SELECT step >= 360 AS after_change,                        -- split at the change step
       COUNT(channel) AS rows_with_channel,                -- non-null channel values
       COUNT(*) AS row_count                               -- all rows
FROM workspace.fraud.bronze_transactions                   -- Bronze table
GROUP BY step >= 360;                                      -- before vs after

-- ── V4 malformed proof: exactly 5 rescued rows ──
SELECT COUNT(*) AS rescued_rows                            -- expected 5
FROM workspace.fraud.bronze_transactions                   -- Bronze table
WHERE amount IS NULL AND _rescued_data IS NOT NULL;        -- broken amount kept in _rescued_data

-- ── Measurement: pipeline lag per file (the only meaningful time figure) ──
SELECT source_file,                                        -- one row per landing file
       timestampdiff(SECOND, MIN(file_arrived_at), MIN(ingested_at)) AS lag_seconds  -- landed -> loaded
FROM workspace.fraud.bronze_transactions                   -- Bronze table
GROUP BY source_file ORDER BY lag_seconds DESC;            -- slowest first
