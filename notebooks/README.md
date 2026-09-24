# notebooks/

Databricks notebooks for the Phase 2 ingest pipeline (features, training and
scoring land in Phases 3–4). Notebooks must contain no workspace URLs, IDs or
secrets. Each imports `fraud_ingest` from `../src` at the top.

Run order:

1. `01_prepare_outbox.py` — one-time: splits the PaySim CSV in the `raw`
   volume into 743 per-step JSON Lines files under `outbox` (V1).
2. `02_release.py` — the `release` job task: copies the next steps from
   `outbox` into `landing`, logging each to `release_log` (backfill first,
   then K replay/drift steps per run, plus any duplicate/held/schema-change/
   malformed scenario flags passed as job parameters).
3. `03_ingest_bronze.py` — the `ingest` job task: runs the Auto Loader
   stream from `landing` into `bronze_transactions` (`Trigger.AvailableNow`,
   one automatic retry).
4. `99_reset.py` — **destructive**. Drops Bronze, empties the release log,
   and clears `landing`/`pipeline_state` (never `outbox` or `raw`). Requires
   the widget `confirm=RESET`; otherwise it raises and changes nothing.
