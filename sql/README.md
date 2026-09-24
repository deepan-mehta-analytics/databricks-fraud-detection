# sql/

Unity Catalog DDL for the Phase 2 ingest pipeline. Grants, row filters and
column masks (Phase 5) land later — grants will target groups or principals,
not roles (see G-06).

- `10_fraud_ingest_setup.sql` — run once, user-run, in the SQL editor.
  Idempotent (`CREATE ... IF NOT EXISTS`). Creates the `workspace.fraud`
  schema, the four volumes (`raw`, `outbox`, `landing`, `pipeline_state`),
  and the `release_log` table. `bronze_transactions` is created by the
  Auto Loader stream itself, not by this script.
- `20_verify_bronze.sql` — verification queries for the workspace runs
  V2–V4: Bronze row/fraud/distinct-ID totals, the duplicate-step proof, the
  late-file arrival-order proof, the schema-change `channel` proof, the
  malformed-row `_rescued_data` proof, and a per-file ingest-lag query.
