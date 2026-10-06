# pipelines/

Lakeflow declarative pipeline sources (SQL), deployed by the Asset Bundle
(`resources/fraud_silver_pipeline.yml`) and run as the `silver` task of the
`fraud-ingest` job after Bronze ingest.

`silver/` — Phase 3 Silver (design: ADR 0008):

- `01_checked_transactions.sql` — private (unpublished) view: every Bronze
  row plus a verdict, with nine warn-only expectations that count each rule
  on the pipeline's Data quality tab.
- `02_transactions.sql` — `silver_transactions`: clean payments, first copy
  per ID, fixed columns (no synthetic `channel`, no label-leaking balances),
  fail-the-run guards.
- `03_rejected_transactions.sql` — `silver_rejected_transactions`: rejected
  rows with `rejection_reason`.
- `04_transaction_features.sql` — `silver_transaction_features`: keys plus
  seven warning signs counted from earlier hours only.

CI checks these files' structure only (`tests/test_silver_sql.py`); the SQL
logic is verified by a real workspace run against
`scripts/expected_silver.py` (see `sql/31_verify_silver.sql`).

**First deploy and after a reset** (`notebooks/99_reset.py`): Silver reads
Bronze incrementally, so it must be rebuilt by hand whenever Bronze is
recreated. Order: run the `fraud-ingest` job once so Bronze exists, run
`sql/30_silver_setup.sql`, then open the `fraud-silver` pipeline and click
**Full refresh all**. The job's `silver` task never does a full refresh on
its own (`full_refresh: false`).

**Location:** the catalog and schema come from the bundle variables
`catalog` / `schema` in `databricks.yml`, shared by the job and the
pipeline (the pipeline reads Bronze as `${bronze_table}`). Change them
there and redeploy, not in the job's Run now parameters, or the job and the
pipeline would point at different places.
