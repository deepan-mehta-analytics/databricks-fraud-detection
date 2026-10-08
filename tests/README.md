# tests/

`python -m pytest -q` runs 108 tests, all local (no Databricks needed):

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
  checks the four tasks (release, ingest, silver, score), retry, schedule and
  parameter list (release and scoring options), the on-demand
  `fraud_train` job and its defaults, plus the `fraud_silver` pipeline resource (serverless,
  triggered, anchor, the four SQL files in order), and that the job and
  the pipeline share one catalog/schema through the bundle variables.
- `test_silver_expected.py` — the verdict rules in precedence order, duplicate
  ranking, the Bronze scenario simulation, strict-past features and the
  empty-history nulls, and the one-pass command-line tool against the
  library helpers.
- `test_silver_sql.py` — text-level guards on the pipeline SQL: private
  verdict view, every verdict and expectation named, FAIL guards, no
  synthetic or balance columns selected, the clean table's fixed 12-column
  list (no `*`), every window with a strict-past frame, `try_divide`.

- `test_model_windows.py` — training and comparison windows for a label
  delay of 3 days and 0 days, and refusal of impossible settings.
- `test_model_features.py` — the fixed feature list, the forbidden columns
  (label, IDs, accounts, balances, `channel`, raw step), hour of day,
  `Decimal`/`None` conversion, and unknown payment types.
- `test_model_metrics.py` — precision and recall at a 50-alerts-per-hour
  budget (short hours, ties, missing scores, no fraud), the legacy-rule
  baseline, PR-AUC and the MLflow metric flattening.
- `test_model_training.py` — both models train on missing values, the
  comparison picks the higher PR-AUC, scores are probabilities, an
  all-missing column is kept, feature importances, step chunking.
- `test_model_scoring.py` — the decision-log schema, DDL and rows, and a
  text guard that the scoring code never reads the label.

Notebook behavior, the Delta tables, the Silver pipeline and the model
registry are verified by workspace runs (V1–V6, S1–S6, M1–M7), not by this
local suite.
