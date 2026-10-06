-- ── ③ The rejected shelf: every row that failed a rule or conflicted (spec §6, Q1) ──
-- Keeps every Bronze column, including _rescued_data and any synthetic field, as raw evidence. Not a model input.
CREATE OR REFRESH MATERIALIZED VIEW silver_rejected_transactions                               -- published rejected shelf
COMMENT 'Bronze rows rejected by Silver, with the first broken rule (or conflicting_duplicate) as rejection_reason.'  -- table comment
AS SELECT                                                                                      -- reason first
  verdict AS rejection_reason,                                                                 -- why it was shelved
  * EXCEPT (verdict, rule_verdict, copy_number, content_hash, first_content_hash)              -- original Bronze columns only
FROM silver_checked_transactions                                                               -- verdict view
WHERE verdict NOT IN ('ok', 'duplicate_copy');                                                 -- identical copies are counted, not shelved
