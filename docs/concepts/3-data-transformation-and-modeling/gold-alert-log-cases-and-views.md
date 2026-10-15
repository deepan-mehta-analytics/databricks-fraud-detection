# Gold: an Alert Log, a Case Table, and a View

**In plain words:** Gold is the layer people act on. Here it turns model scores into a fraud team's work queue. The alert log (`fraud_alerts`) records which payments were flagged, the top 50 per simulated hour, and is never edited. The case table (`alert_cases`) records where each investigation stands, open or closed with a verdict. A plain view (`alert_summary_hourly`) gives managers per-hour totals and stores nothing.

**Everyday analogy:** The alert log is a hospital's admissions book: once a patient is written in, the line is never rubbed out. The case table is the whiteboard by the ward door showing each patient's current status. The view is the nurse who adds up the whiteboard whenever someone asks, so the total is always current.

**Why real teams use it:** Keeping *what happened* (an event log) apart from *where things stand* (current state) is a standard pattern in banking, retail and ticketing systems. An alert is a promise to a reviewer, so it must not change after it is handed out. That is why an append-only table fits better than a materialized view, which recalculates whenever late data arrives ([views and materialized views](https://docs.databricks.com/aws/en/ldp/concepts), checked 2026-10-11). Writes use `MERGE … WHEN NOT MATCHED THEN INSERT`, so a rerun adds nothing. Alerts follow a fixed budget per hour, sized to the review team, not a probability cut-off.

**How this repo uses it:** A SQL task, `gold`, runs after scoring in the `fraud-ingest` job ([SQL file](../../../sql/gold/gold.sql)). It adds the top 50 alerts for every hour not yet alerted, opens a case per alert, and closes cases 72 simulated hours later with a verdict taken from the dataset's label (simulated reviewers, the same 3-day delay the model was trained with). See [ADR 0010](../../adr/0010-gold-alert-log-and-case-table.md).

**What was verified:** 2026-10-12, Databricks Free Edition: the first run with the `gold` task wrote 3,154 alerts over 82 hours, exactly the number a pure-Python calculator predicted from the CSV. Rebuilding the top 50 per hour independently found 0 missing and 0 extra alerts. 262 of 3,154 cases were closed, and every verdict matched the dataset's label. Running the job again changed nothing: the run's own metrics reported 0 rows written. 2026-10-13: an hour held back and released late (hour 419) got 50 fresh alerts, none marked late, about 14 minutes after the next hour's. Earlier hours were untouched, and the totals moved to 3,268 alerts and 412 closed cases, again matching the calculator.

**Key terms:** Gold layer, append-only table, event log, current state, plain view, `MERGE`, SQL task.

**Go deeper:** private study notes (drills, diagrams, traps) live outside the public repo.
