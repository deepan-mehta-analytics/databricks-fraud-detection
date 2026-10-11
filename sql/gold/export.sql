-- ── Gold SQL task `export` (fraud-ingest, after `gold`). Spec §10, ADR 0011. ──
-- Copies newly closed cases to the external table on Cloudflare R2, created once by sql/51_export_setup.sql.
-- No account names: files outside Unity Catalog can't be masked, so only what an auditor needs leaves (data minimisation).
MERGE INTO workspace.fraud.closed_alerts_export AS e                           -- the external table (files in R2)
USING (SELECT transaction_id, step, risk_score, model_version, verdict, closed_at  -- what an auditor needs
       FROM workspace.fraud.alert_cases                                         -- the case table
       WHERE status = 'closed') AS c                                            -- closed cases only
ON e.transaction_id = c.transaction_id                                          -- one row per case
WHEN NOT MATCHED THEN INSERT (transaction_id, step, risk_score, model_version, verdict, closed_at)  -- columns
  VALUES (c.transaction_id, c.step, c.risk_score, c.model_version, c.verdict, c.closed_at);  -- copied once
