-- ── Tag-based policy (ABAC) probe, run by the owner after G7 (spec §9, plan ruling R2). Exam 7.4. ──
-- Step 0 (UI, before any SQL): Catalog -> look for "Governed tags" (or Settings -> Governance). Create a governed tag
-- `pii` with allowed value `account_name`. If no such screen exists, record "governed tags not available on Free Edition" and stop.
-- The probe uses a 5-row scratch table so the proven per-table masks are never touched.

-- ── 1. Scratch table (you are an engineer, so it copies real names) ──
CREATE OR REPLACE TABLE workspace.fraud.abac_probe AS                          -- 5 closed cases
SELECT transaction_id, sender_account                                           -- one tagged column is enough
FROM workspace.fraud.alert_cases WHERE status = 'closed' LIMIT 5;               -- small sample

-- ── 2. Tag the column as personal data ──
ALTER TABLE workspace.fraud.abac_probe ALTER COLUMN sender_account SET TAGS ('pii' = 'account_name');  -- the label the policy matches

-- ── 3. One policy for the whole schema: every column tagged pii=account_name is masked for non-trusted readers ──
CREATE OR REPLACE FUNCTION workspace.fraud.redact(value STRING)                -- the policy's mask
RETURNS STRING                                                                  -- same type as the column
RETURN 'REDACTED';                                                              -- the policy decides who it applies to
CREATE POLICY redact_account_names ON SCHEMA workspace.fraud                   -- front-door rule for the schema
  COLUMN MASK workspace.fraud.redact                                            -- mask function
  TO `account users` EXCEPT `fraud_engineers`, `fraud_reviewers`                -- everyone but the trusted groups
  FOR TABLES                                                                    -- applies to tables
  MATCH COLUMNS has_tag_value('pii', 'account_name') AS account                 -- any column with the tag
  ON COLUMN account;                                                            -- mask that column
GRANT SELECT ON TABLE workspace.fraud.abac_probe TO `fraud_managers`;          -- let the test user read it

-- ── 4. Check: test user (in fraud_managers) runs this and should see REDACTED; you should see real names ──
SELECT * FROM workspace.fraud.abac_probe;                                       -- 5 rows

-- ── 5. Clean up after recording the result ──
DROP POLICY redact_account_names ON SCHEMA workspace.fraud;                    -- remove the probe policy
DROP TABLE workspace.fraud.abac_probe;                                          -- remove the scratch table
DROP FUNCTION workspace.fraud.redact;                                           -- remove the probe mask
