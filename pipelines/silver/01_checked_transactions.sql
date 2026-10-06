-- ── ① Every Bronze row with a verdict (spec §5). PRIVATE: not published to the catalog. ──
-- Expectations warn only: they count each rule's failures per run on the Data quality tab.
-- They are evaluated independently, so one row can fail several (a malformed amount fails amount_valid and fully_parsed).
CREATE OR REFRESH PRIVATE MATERIALIZED VIEW silver_checked_transactions (  -- verdict view
  CONSTRAINT has_id EXPECT (transaction_id IS NOT NULL),                                       -- rule 1
  CONSTRAINT has_time EXPECT (transaction_time IS NOT NULL),                                   -- rule 2
  CONSTRAINT time_matches_step EXPECT (COALESCE(step BETWEEN 1 AND 743                         -- rule 3: step in range...
    AND transaction_time = timestampadd(HOUR, step - 1, to_timestamp('${anchor}', "yyyy-MM-dd'T'HH:mm:ssX")), FALSE)),  -- ...and time = anchor + (step-1) h
  CONSTRAINT amount_valid EXPECT (COALESCE(amount >= 0, FALSE)),                               -- rule 4: zero allowed
  CONSTRAINT type_known EXPECT (COALESCE(transaction_type IN ('PAYMENT', 'TRANSFER', 'CASH_OUT', 'CASH_IN', 'DEBIT'), FALSE)),  -- rule 5
  CONSTRAINT accounts_present EXPECT (sender_account IS NOT NULL AND receiver_account IS NOT NULL),  -- rule 6
  CONSTRAINT labels_valid EXPECT (COALESCE(fraud_label IN (0, 1) AND flagged_by_old_rules IN (0, 1), FALSE)),  -- rule 7
  CONSTRAINT fully_parsed EXPECT (_rescued_data IS NULL),                                      -- rule 8
  CONSTRAINT first_copy EXPECT (verdict NOT IN ('duplicate_copy', 'conflicting_duplicate'))    -- rule 9
)                                                                                              -- end expectations
COMMENT 'Every Bronze row plus its verdict: the first broken rule, ok, or a duplicate outcome.'  -- table comment
AS                                                                                             -- the query follows
-- ── Rules 1-8 in precedence order (NULL-safe: COALESCE turns unknown into broken) ──
WITH rules AS (                                                                                -- one verdict per rule check
  SELECT *,                                                                                    -- every Bronze column (channel only if present)
    sha2(to_json(named_struct(                                                                 -- content fingerprint for copy comparison
      'step', step, 'transaction_time', transaction_time, 'transaction_type', transaction_type,  -- payment identity
      'amount', amount, 'sender_account', sender_account, 'receiver_account', receiver_account,  -- money and accounts
      'sender_balance_before', sender_balance_before, 'sender_balance_after', sender_balance_after,  -- sender balances
      'receiver_balance_before', receiver_balance_before, 'receiver_balance_after', receiver_balance_after,  -- receiver balances
      'fraud_label', fraud_label, 'flagged_by_old_rules', flagged_by_old_rules)), 256) AS content_hash,  -- labels; metadata excluded
    CASE                                                                                       -- first broken rule wins
      WHEN transaction_id IS NULL THEN 'missing_id'                                            -- rule 1
      WHEN transaction_time IS NULL THEN 'missing_time'                                        -- rule 2
      WHEN NOT COALESCE(step BETWEEN 1 AND 743                                                 -- rule 3: range...
        AND transaction_time = timestampadd(HOUR, step - 1, to_timestamp('${anchor}', "yyyy-MM-dd'T'HH:mm:ssX")), FALSE)  -- ...and consistency
        THEN 'time_step_mismatch'                                                              -- rule 3 verdict
      WHEN NOT COALESCE(amount >= 0, FALSE) THEN 'bad_amount'                                  -- rule 4
      WHEN NOT COALESCE(transaction_type IN ('PAYMENT', 'TRANSFER', 'CASH_OUT', 'CASH_IN', 'DEBIT'), FALSE) THEN 'unknown_type'  -- rule 5
      WHEN sender_account IS NULL OR receiver_account IS NULL THEN 'missing_account'           -- rule 6
      WHEN NOT COALESCE(fraud_label IN (0, 1) AND flagged_by_old_rules IN (0, 1), FALSE) THEN 'bad_label'  -- rule 7
      WHEN _rescued_data IS NOT NULL THEN 'unparsed_value'                                     -- rule 8
    END AS rule_verdict                                                                        -- NULL = passed rules 1-8
  FROM workspace.fraud.bronze_transactions                                                     -- Bronze (outside the pipeline)
),                                                                                             -- end rules
-- ── Rule 9: rank copies among valid rows only, earliest arrival first ──
ranked AS (                                                                                    -- copy number per ID
  SELECT *,                                                                                    -- rules output
    ROW_NUMBER() OVER (PARTITION BY transaction_id, rule_verdict IS NULL                       -- valid rows ranked separately
      ORDER BY file_arrived_at, ingested_at, source_file) AS copy_number,                      -- arrival order
    FIRST_VALUE(content_hash) OVER (PARTITION BY transaction_id, rule_verdict IS NULL          -- the first copy's content
      ORDER BY file_arrived_at, ingested_at, source_file) AS first_content_hash                -- same ordering
  FROM rules                                                                                   -- from the rule checks
)                                                                                              -- end ranked
SELECT *,                                                                                      -- everything so far
  CASE                                                                                         -- final verdict
    WHEN rule_verdict IS NOT NULL THEN rule_verdict                                            -- broke a rule
    WHEN copy_number = 1 THEN 'ok'                                                             -- first valid copy
    WHEN content_hash = first_content_hash THEN 'duplicate_copy'                               -- identical copy: removed
    ELSE 'conflicting_duplicate'                                                               -- different content: rejected
  END AS verdict                                                                               -- one per row
FROM ranked;                                                                                   -- end ①
