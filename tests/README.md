# tests/

`python -m pytest -q` runs 37 tests, all local (no Databricks needed):

- `test_contract.py` — segment boundaries, file naming, transaction ID and
  timestamp derivation, schema hints, volume paths.
- `test_split.py` — CSV-to-outbox splitting: one file per step, plain
  field names and types, deterministic IDs, sort-order enforcement.
- `test_scenarios.py` — the `channel` and malformed-`amount` transforms in
  isolation.
- `test_release_core.py` — the core release run logic: backfill-first,
  K-per-run pacing, crash/resume repair, parameter parsing and validation.
- `test_release_scenarios.py` — the duplicate/late/schema-change/malformed
  scenarios as applied by `run_release`.
- `test_ingest.py` — Auto Loader option construction and that the module
  imports without PySpark installed.
- `test_job_definition.py` — parses `resources/fraud_ingest_job.yml` and
  checks the task graph, retry, schedule and parameter list.

Notebook behavior and the Delta release log/Bronze table are verified by
workspace runs (V1–V6), not by this local suite.
