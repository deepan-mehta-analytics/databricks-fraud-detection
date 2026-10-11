-- ── Run once in the SQL editor by the owner, after the R2 credential and external location exist (sheet G1g-G1h). Spec §10. ──
-- Replace <bucket> and <account-id> IN THE EDITOR ONLY. Never commit real values (CI checks every tracked file).

-- ── 1. Can serverless reach R2? (G1i) An error naming the host or DNS means Free Edition's network limit blocks it. ──
LIST 'r2://<bucket>@<account-id>.r2.cloudflarestorage.com/';                   -- empty result is fine: the bucket is new

-- ── 2. The external table: Unity Catalog keeps the catalogue entry, the files stay in your bucket ──
CREATE TABLE IF NOT EXISTS workspace.fraud.closed_alerts_export (              -- closed cases for auditors and other tools
  transaction_id STRING NOT NULL,                                               -- the case
  step BIGINT NOT NULL,                                                         -- simulated hour
  risk_score DOUBLE NOT NULL,                                                   -- model score
  model_version STRING NOT NULL,                                                -- which model decided
  verdict STRING NOT NULL,                                                      -- confirmed_fraud or false_alarm
  closed_at TIMESTAMP NOT NULL                                                  -- when the verdict was recorded
) USING DELTA                                                                   -- Delta files in R2
COMMENT 'External table on Cloudflare R2: closed cases without account names (ADR 0011).'  -- table comment
LOCATION 'r2://<bucket>@<account-id>.r2.cloudflarestorage.com/closed_alerts_export';  -- LOCATION makes it external

-- ── 3. Check: the Type row must read EXTERNAL and Location must start with r2:// ──
DESCRIBE TABLE EXTENDED workspace.fraud.closed_alerts_export;                  -- table details
