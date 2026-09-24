-- ── Run once in the SQL editor (user-run). Idempotent: safe to re-run. ──
CREATE SCHEMA IF NOT EXISTS workspace.fraud;               -- project schema in the Free Edition default catalog

-- ── Volumes ───────────────────────────────────────────────────
CREATE VOLUME IF NOT EXISTS workspace.fraud.raw;           -- the uploaded PaySim CSV
CREATE VOLUME IF NOT EXISTS workspace.fraud.outbox;        -- 743 per-step JSON Lines files
CREATE VOLUME IF NOT EXISTS workspace.fraud.landing;       -- released files: the only folder Auto Loader reads
CREATE VOLUME IF NOT EXISTS workspace.fraud.pipeline_state; -- Auto Loader schema location + checkpoint

-- ── Release log (columns must match RELEASE_LOG_COLUMNS in release_log.py) ──
CREATE TABLE IF NOT EXISTS workspace.fraud.release_log (   -- one row per released or held step
  step INT,                                                -- PaySim step
  segment STRING,                                          -- backfill / replay / drift
  file_name STRING,                                        -- landing file name
  scenario STRING,                                         -- '', duplicate, late, schema_change, malformed
  status STRING,                                           -- released / held
  released_at STRING                                       -- ISO-8601 UTC write time
);                                                         -- Bronze is created by the stream itself
