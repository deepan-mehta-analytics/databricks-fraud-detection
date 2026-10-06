# tests/

`python -m pytest -q` runs 77 tests, all local (no Databricks needed):

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
  checks the three tasks (release, ingest, silver), retry, schedule and
  parameter list, plus the `fraud_silver` pipeline resource (serverless,
  triggered, anchor, the four SQL files in order).
- `test_silver_expected.py` — the verdict rules in precedence order, duplicate
  ranking, the Bronze scenario simulation, strict-past features and the
  empty-history nulls.
- `test_silver_sql.py` — text-level guards on the pipeline SQL: private
  verdict view, every verdict and expectation named, FAIL guards, no
  synthetic or balance columns selected, strict-past frames, `try_divide`.

Notebook behavior and the Delta release log/Bronze table are verified by
workspace runs (V1–V6), not by this local suite.
