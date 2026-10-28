# sql/

Unity Catalog DDL and verification queries. Every file is written for the
default bundle variables (`workspace.fraud`). Grants target groups, never
roles (G-06).

- `10_fraud_ingest_setup.sql` — run once, user-run, in the SQL editor.
  Idempotent (`CREATE ... IF NOT EXISTS`). Creates the `workspace.fraud`
  schema, the four volumes (`raw`, `outbox`, `landing`, `pipeline_state`),
  and the `release_log` table. `bronze_transactions` is created by the
  Auto Loader stream itself, not by this script.
- `20_verify_bronze.sql` — verification queries for the workspace runs
  V2–V4: Bronze row/fraud/distinct-ID totals, the duplicate-step proof, the
  late-file arrival-order proof, the schema-change `channel` proof, the
  malformed-row `_rescued_data` proof, and a per-file ingest-lag query.
- `30_silver_setup.sql` — run once, user-run, after Bronze exists and again
  after any `99_reset` run. Idempotent. Turns on deletion vectors, row
  tracking and the change data feed on `bronze_transactions`, the Silver
  pipeline's only source, so materialized views can refresh incrementally.
- `31_verify_silver.sql` — verification queries for the Silver checks S2–S6:
  accounting and counts, rejected rows by reason, features against an
  independent self-join covering all seven features, and the pipeline event
  log (refresh technique and update durations). The receiver and pipeline
  ID are named parameters (`:receiver`, `:pipeline_id`); no real ID is
  committed. The expected counts were measured with
  `scripts/expected_silver.py` over `data/paysim.csv`.
- `40_verify_model.sql` — verification queries for the model checks M4, M5
  and M7: scored rows against Silver, no label column in the decision log,
  stored features equal to Silver's, and rows per model version after a
  promotion. The expected values were measured from `data/paysim.csv`.
- `gold/gold.sql` — the `gold` SQL task in `fraud-ingest` (after `score`).
  Creates the Gold tables and view on its first run, adds the top 50 alerts
  for every hour not yet alerted (plus late payments that earn a place) to
  the append-only `fraud_alerts` log, opens one case per alert in
  `alert_cases`, and closes cases 72 simulated hours later with the verdict.
- `gold/export.sql` — designed as an `export` SQL task after `gold`: copies
  newly closed cases, without account names, to an external table on
  Cloudflare R2. Not wired into the job: Free Edition's serverless compute
  can't resolve the R2 storage domain (measured 2026-10-11).
- `monitoring/monitoring.sql` — the `monitor` SQL task in `fraud-ingest`
  (after `gold`). Recreates six plain views — `model_accuracy_by_hour`,
  `hours_waiting_for_verdicts`, `data_freshness`, `rejected_rows_by_reason`,
  `job_run_times`, `pipeline_update_times` — and re-grants each one straight
  away. Job and pipeline history comes from `system.lakeflow`, picked by
  name; minutes come from start and end times because the duration columns
  read 0 on Free Edition. The fraud label is read only for hours whose
  verdicts are in and whose cases Gold has closed. Grants added by hand to
  these views are lost at the next run; add them to this file instead.
- `50_governance.sql` — run once by the owner after the first Gold run: the
  account-name mask and the closed-cases-only row filter (both exempt
  engineers and reviewers), and the group grants (engineers schema-wide,
  reviewers and managers table by table).
- `51_export_setup.sql` — for a workspace that can reach R2 (not Free
  Edition): checks the bucket is reachable, then creates the external
  export table. The bucket
  and account ID are typed in the editor only; the repo keeps placeholders.
- `52_abac_probe.sql` — the tag-based policy (ABAC) probe on a 5-row scratch
  table, with its clean-up.
- `53_verify_gold.sql` — verification queries for the Gold checks G3–G10,
  expected values from `scripts/expected_gold.py` over `data/paysim.csv`.
- `60_probe_system_tables.sql` — the system-table probes P1 and D1b (done
  2026-10-15) and the column checks behind the monitoring views.
- `61_verify_monitoring.sql` — the monitoring checks D3a, D5–D8 and D12
  (the restyled dashboards' numbers), with expected values from
  `scripts/expected_gold.py --monitoring` inline, including a block for the
  test user in `fraud_managers`. D5–D8 and D12 each return one row ending in
  `all_as_expected`, so one Run shows the check.
