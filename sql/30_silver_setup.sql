-- ── Run once in the SQL editor (user-run), after Bronze exists and again after any 99_reset run. Idempotent. ──
-- Databricks recommends these on materialized-view sources for incremental refresh; some refresh
-- techniques require row tracking (incremental-refresh docs, read 2026-10-06).
ALTER TABLE workspace.fraud.bronze_transactions SET TBLPROPERTIES (  -- Bronze is the Silver pipeline's only source
  delta.enableDeletionVectors = true,                                -- track deleted rows cheaply
  delta.enableRowTracking = true,                                    -- stable row identity for incremental refresh
  delta.enableChangeDataFeed = true                                  -- row-level change feed
);                                                                   -- end properties

-- ── Check: all three should show 'true' ──
SHOW TBLPROPERTIES workspace.fraud.bronze_transactions;              -- look for the three delta.enable* keys
