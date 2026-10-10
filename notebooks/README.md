# notebooks/

Databricks notebooks for ingest (Phase 2) and the fraud model (Phase 4);
Silver is a Lakeflow pipeline (`pipelines/`). Notebooks must contain no workspace URLs, IDs or
secrets. Each imports `fraud_ingest` or `fraud_model` from `../src` at the top.

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
4. `04_train_model.py` — the `fraud-train` job task (on demand): fits
   gradient-boosted trees and a logistic baseline on Silver, compares them on
   a held-out time window, logs both to MLflow and registers the winner in
   Unity Catalog as `@challenger`.
5. `05_score_transactions.py` — the `score` task of `fraud-ingest`, after
   `silver`: scores payments from step 337 on that are not yet scored, with
   the `@champion` version, and appends them with the features it saw to
   `transaction_risk_scores`. With no champion yet it scores nothing and
   succeeds.
6. `06_promote_model.py` — owner-run: points `@champion` (or another alias)
   at a chosen model version and prints before and after.
7. `07_evaluate_model.py` — owner-run, after the fact: scores steps 337–408
   with a given model, reads the labels, and logs precision and recall at 50
   alerts per hour, PR-AUC and two baselines to that model's MLflow run.

Notebooks 04, 05 and 07 start with `%pip install scikit-learn==1.7.2` and a
Python restart. Serverless job tasks can land on different environment
versions (environment 5 ships scikit-learn 1.6.1, environment 6 ships 1.7.2),
and a bundle deploy does not keep a job-level environment on a notebook task,
so the pin lives in the notebooks. A guard still stops the run if the model's
logged version and the running version differ.
8. `99_reset.py` — **destructive**. Drops Bronze and the risk scores, empties
   the release log, and clears `landing`/`pipeline_state` (never `outbox` or
   `raw`). Requires
   the widget `confirm=RESET`; otherwise it raises and changes nothing.
