# Materialized Views and Streaming Tables

**In plain words:** A materialized view stores the result of a query and keeps it up to date. Each refresh makes it correct for the data present at that moment, even when data arrives late or out of order. A streaming table processes each new row exactly once and suits data that only ever grows. A plain view stores nothing and runs its query each time.

**Everyday analogy:** A materialized view is a printed monthly bank statement that the bank reprints when a late transaction shows up. A streaming table is the till receipt roll, which only ever grows. A plain view is asking the cashier to add it up again every time you ask.

**Why real teams use it:** The rule of thumb is a streaming table for append-only, growing data, a materialized view for aggregations, joins or sources that can change, and a view for intermediate steps you don't need to keep ([docs](https://docs.databricks.com/aws/en/ldp/concepts), checked 2026-10-08). On serverless, a materialized view can refresh **incrementally**, processing only what changed. Databricks picks the technique, and window functions need `PARTITION BY` to qualify ([docs](https://docs.databricks.com/aws/en/optimizations/incremental-refresh), checked 2026-10-08). `PRIVATE` keeps a dataset out of the catalog, visible only inside its pipeline ([docs](https://docs.databricks.com/aws/en/ldp/developer/ldp-sql-ref-create-materialized-view), checked 2026-10-08).

**How this repo uses it:** All four Silver datasets are materialized views, so a late file corrects the features on the next refresh with no hand-written logic. The verdict view is `PRIVATE`. Streaming tables were the alternative: they would scale better, but they would need custom late-data handling. See [the pipeline resource](../../../resources/fraud_silver_pipeline.yml) and [ADR 0008](../../adr/0008-silver-on-a-declarative-pipeline.md).

**What was verified:** 2026-10-06/07, workspace runs S5–S6 (`14fa8b3`). A file held back and released late changed a later payment's features to the complete-data values. The event log showed a full recompute on the first build, then incremental updates (`WINDOW_FUNCTION`, `APPEND_ONLY`) on later runs, even with expectations in place. At about 6M rows, every update took about 2 minutes either way, because fixed start-up time dominates ([GAPS G-14, G-15](../../GAPS.md)).

**Key terms:** materialized view, streaming table, view, `PRIVATE`, incremental refresh, refresh technique, event log.

**Go deeper:** private study notes (drills, diagrams, traps) live outside the public repo.
