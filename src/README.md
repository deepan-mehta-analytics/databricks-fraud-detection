# src/

Python modules shared by notebooks and tests. Stdlib only at module level;
PySpark is imported lazily inside the one function that needs it
(`ingest.start_bronze_ingest`), so the package imports cleanly in local
tests without a Spark install.

`fraud_ingest/`:

- `contract.py` — segment boundaries, PaySim-column-to-record-field map, file
  naming, and Auto Loader schema hints shared by the producer and consumer.
- `split.py` — one-time producer step: converts the PaySim CSV into one
  JSON Lines file per step in the outbox.
- `scenarios.py` — opt-in transforms (schema-change `channel` field,
  malformed `amount` values) applied to released copies, never to outbox
  files.
- `release_log.py` — the `ReleaseEntry` row type plus an in-memory log
  (local tests) and a Delta-table-backed log (workspace).
- `release.py` — release task: copies the next PaySim steps from the
  outbox into the landing folder, following backfill-first / K-per-run /
  no-double-release rules, and applies the duplicate/late/schema-change/
  malformed scenarios.
- `ingest.py` — consumer: one Auto Loader stream from the landing folder
  into the Bronze table (`Trigger.AvailableNow`).
