-- ── ② Clean payments: first valid copy only, fixed column list (spec §6, Q6) ──
-- channel and the four balance columns are deliberately absent (ADR 0006): they stay in Bronze.
CREATE OR REFRESH MATERIALIZED VIEW silver_transactions (                                      -- published clean table
  CONSTRAINT id_present EXPECT (transaction_id IS NOT NULL) ON VIOLATION FAIL UPDATE,          -- guard: split bug fails the run
  CONSTRAINT time_present EXPECT (transaction_time IS NOT NULL) ON VIOLATION FAIL UPDATE,      -- guard
  CONSTRAINT amount_present EXPECT (amount IS NOT NULL) ON VIOLATION FAIL UPDATE               -- guard
)                                                                                              -- end guards
COMMENT 'Clean PaySim payments: verdict ok, first copy per transaction_id, no synthetic or label-leaking columns.'  -- table comment
AS SELECT                                                                                      -- fixed list
  transaction_id,                                                                              -- unique per row
  step,                                                                                        -- simulated hour
  transaction_time,                                                                            -- synthetic event time
  transaction_type,                                                                            -- PAYMENT, TRANSFER, ...
  amount,                                                                                      -- DECIMAL(18,2)
  sender_account,                                                                              -- paying account
  receiver_account,                                                                            -- receiving account
  fraud_label,                                                                                 -- ground truth (hidden from scoring later)
  flagged_by_old_rules,                                                                        -- PaySim's legacy rule flag
  source_file,                                                                                 -- lineage: landing file
  file_arrived_at,                                                                             -- lineage: arrival time
  ingested_at                                                                                  -- lineage: Bronze load time
FROM silver_checked_transactions                                                               -- verdict view (same pipeline)
WHERE verdict = 'ok';                                                                          -- clean rows only
