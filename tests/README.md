# tests/

`python -m pytest -q` runs 189 tests, all local (no Databricks needed):

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
  checks the eight tasks (release, ingest, silver, score, gold, monitor and the two dashboard refreshes), the Gold SQL tasks on the warehouse found by name, retry, schedule and
  parameter list (release and scoring options), the on-demand
  `fraud_train` job and its defaults, plus the `fraud_silver` pipeline resource (serverless,
  triggered, anchor, the four SQL files in order), and that the job and
  the pipeline share one catalog/schema through the bundle variables, and
  that the train, score and evaluate notebooks install the same pinned
  scikit-learn first (so the model loads with the version it was trained
  with, whatever serverless environment the job task is given).
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
- `test_model_runtime.py` — only a not-found registry error may skip
  scoring; MLflow 3 is required; a scikit-learn minor-version mismatch
  between training and scoring is refused.
- `test_gold_expected.py` — the local Gold calculator: alerts per hour
  capped at the budget, the closing cutoff 72 simulated hours back, closed
  cases, the late-alert rule for one payment and for a batch (the room left is filled first), and Silver
  payments per hour from the CSV simulation, plus the one-pass monitoring
  tallies and the `--monitoring` / `--since` printout.
- `test_gold_sql.py` — text guards on the Gold and governance SQL: alerts
  are insert-only, the top-50 budget and tie-break, the late-alert rule,
  the label read only when closing cases, an export without account names,
  masks and the row filter exempting engineers and reviewers, a row filter
  that reads only its own row, per-table grants for reviewers and managers,
  both Gold tasks refusing to run outside the engineers group, case names taken from Silver, no MODIFY grant, the view's visible-cases column, the view checked through the row filter, and no real R2 path or account ID in any tracked text file.
- `test_monitoring_sql.py` — text guards on the monitoring SQL: views and
  grants only, each view re-granted at once, every column commented, the
  fraud label read in exactly two job statements behind the 72-hour cutoff,
  waiting hours empty rather than 0, an hour ready only once Gold has
  closed its cases, waiting hours counted from scored hours (so managers
  see the same count), fraud summed once per hour, jobs and the pipeline
  matched by name with any development-mode prefix stripped, minutes from
  start and end times grouped per run, no ID columns, the verification
  blocks, and one-row after-run checks each ending in `all_as_expected`.
- `test_dashboards.py` — the two dashboards: committed JSON equals the
  builder's output, each dashboard reads only its audience's views, a
  "How to read it" line per chart, the word-list page, the jargon guard,
  unique widgets, no identifiers, viewer credentials and group permissions,
  the waiting counter read from the waiting view, one bar per hour, and
  tables carrying the full column settings Databricks exports (minimal
  columns showed "Invalid widget definition" at D3).

Notebook behavior, the Delta tables, the Silver pipeline and the model
registry are verified by workspace runs (V1–V6, S1–S6, M1–M8, G1–G11, D1–D10), not by this
local suite.
