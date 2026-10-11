-- ── Run once in the SQL editor by the owner, after the first job run with `gold` (the tables must exist). Spec §8, ADR 0011. ──
-- The owner must be a member of fraud_engineers before running this (sheet G1b): the job runs as the owner,
-- and both functions exempt that group, so the job never reads or writes masked data.
-- Idempotent: functions are replaced, filters and masks re-set, grants repeated without error.

-- ── 1. Functions ──
CREATE OR REPLACE FUNCTION workspace.fraud.mask_account(account STRING)        -- column mask for account names
RETURNS STRING                                                                  -- same type as the column
COMMENT 'Real account name for engineers and reviewers, REDACTED for everyone else.'  -- what it does
RETURN CASE WHEN is_account_group_member('fraud_engineers') OR is_account_group_member('fraud_reviewers')  -- trusted groups
            THEN account                                                        -- investigators need the identity
            ELSE 'REDACTED' END;                                                -- everyone else sees a blacked-out value

CREATE OR REPLACE FUNCTION workspace.fraud.cases_visible(status STRING)        -- row filter for the case table
RETURNS BOOLEAN                                                                 -- true = show the row
COMMENT 'Engineers and reviewers see every case, everyone else sees closed cases only.'  -- what it does
RETURN is_account_group_member('fraud_engineers') OR is_account_group_member('fraud_reviewers')  -- trusted groups see all
       OR status = 'closed';                                                    -- open cases stay with the investigators

-- ── 2. Attach the filter and the masks ──
ALTER TABLE workspace.fraud.alert_cases SET ROW FILTER workspace.fraud.cases_visible ON (status);  -- managers: closed only
ALTER TABLE workspace.fraud.alert_cases ALTER COLUMN sender_account SET MASK workspace.fraud.mask_account;  -- payer hidden from managers
ALTER TABLE workspace.fraud.alert_cases ALTER COLUMN receiver_account SET MASK workspace.fraud.mask_account;  -- receiver hidden from managers
ALTER TABLE workspace.fraud.fraud_alerts ALTER COLUMN sender_account SET MASK workspace.fraud.mask_account;  -- defence in depth on the log
ALTER TABLE workspace.fraud.fraud_alerts ALTER COLUMN receiver_account SET MASK workspace.fraud.mask_account;  -- defence in depth on the log

-- ── 3. Grants: engineers schema-wide, reviewers and managers table by table ──
GRANT USE CATALOG ON CATALOG workspace TO `fraud_engineers`;                   -- enter the catalog
GRANT USE CATALOG ON CATALOG workspace TO `fraud_reviewers`;                   -- enter the catalog
GRANT USE CATALOG ON CATALOG workspace TO `fraud_managers`;                    -- enter the catalog
GRANT USE SCHEMA, SELECT, EXECUTE ON SCHEMA workspace.fraud TO `fraud_engineers`;  -- everything, including tables added later
GRANT USE SCHEMA ON SCHEMA workspace.fraud TO `fraud_reviewers`;               -- enter the schema only
GRANT USE SCHEMA ON SCHEMA workspace.fraud TO `fraud_managers`;                -- enter the schema only
GRANT SELECT ON TABLE workspace.fraud.fraud_alerts TO `fraud_reviewers`;       -- the alert log
GRANT SELECT, MODIFY ON TABLE workspace.fraud.alert_cases TO `fraud_reviewers`;  -- read cases and record verdicts
GRANT SELECT ON TABLE workspace.fraud.alert_summary_hourly TO `fraud_reviewers`;  -- the summary view
GRANT SELECT ON TABLE workspace.fraud.alert_cases TO `fraud_managers`;         -- closed cases, names masked
GRANT SELECT ON TABLE workspace.fraud.alert_summary_hourly TO `fraud_managers`;  -- the summary view

-- ── 4. Check (G6a) ──
SHOW GRANTS ON SCHEMA workspace.fraud;                                          -- expect the three schema grants above
