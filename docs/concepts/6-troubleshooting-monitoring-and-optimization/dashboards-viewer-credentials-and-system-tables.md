# Monitoring Dashboards: Viewer Credentials and System Tables

**In plain words:** An AI/BI (Artificial Intelligence / Business Intelligence) dashboard is a set of SQL queries drawn as charts. This repo has two: **Fraud operations** (the review queue, review outcomes, and whether the model is still good) for engineers, reviewers and managers, and **Platform health** (job runs, task times, data freshness, set-aside rows) for engineers only. They read plain views that a `monitor` job task rebuilds each run, plus Databricks' own logbook of job runs, the `system.lakeflow` system tables.

**Everyday analogy:** A dashboard on viewer credentials is a library catalogue terminal: everyone uses the same screen, but it only shows each person the books their card allows. With embedded credentials, the terminal would be logged in as the librarian, and every visitor would see the staff-only shelves too.

**Why real teams use it:**
- **Viewer credentials** (`embed_credentials: false`, which the docs call "individual data permission") run every query with the viewer's own data permissions, so Unity Catalog's grants, row filters and column masks apply per viewer. The compute itself is still granted by the publisher ([share a dashboard](https://docs.databricks.com/aws/en/dashboards/share/share), checked 2026-10-28). One dashboard can then serve several audiences safely.
- **Dashboards as code:** a dashboard is a `.lvdash.json` file that a bundle deploys like a job, so a chart change is reviewed in Git like any other change.
- **A dashboard task** in a job refreshes a dashboard after the data changes ([dashboard task](https://docs.databricks.com/aws/en/jobs/dashboard), checked 2026-10-28). Without shared data permissions it refreshes as the job's identity, and other viewers can't see that cached result; their screens query live data when they open the page.
- **System tables** let you build a job-health page with plain SQL instead of writing your own run timestamps from every task. Records are typically available within an hour of a run ending.

**How this repo uses it:**
- [Monitoring SQL](../../../sql/monitoring/monitoring.sql) creates the views and grants them straight away, so a rebuild never drops a group's access.
- [Dashboard builder](../../../src/fraud_monitoring/dashboards.py) writes both dashboard files from commented Python; a test fails if the committed files drift from it.
- The job runs `monitor`, then two dashboard tasks in parallel ([job](../../../resources/fraud_ingest_job.yml)).
- **The period-time trick:** on Free Edition the `*_duration_seconds` columns in `system.lakeflow` were 0, so run minutes are `MAX(period_end_time) - MIN(period_start_time)` per run. A long run or a retried task is split over several timeline rows, so adding the rows up would double-count.
- Jobs are matched by name with the development-mode `[dev <user>] ` prefix stripped, never by ID, so no ID reaches this public repo.
- See [ADR 0012](../../adr/0012-monitoring-dashboards-and-views.md).

**What was verified:** Databricks Free Edition, 2026-10-15 to 2026-10-28 (`docs/GAPS.md` §7):
- **Run E** (hours 422–480) took 17 min 9 s with all 8 tasks green, including both dashboard tasks. The Platform health page read it back from `system.lakeflow` as 17.2 minutes.
- **Fraud operations** showed 405 confirmed fraud of 2,916 checked payments (0.139) and of 822 fraud in all (0.493), exactly what a pure-Python calculator predicted from the CSV.
- **A test user in the managers group** saw 0 open cases, the same model numbers as the owner, and was refused Platform health and the job-history view.
- **The job's own refresh showed Platform health one run behind** until a manual Refresh, because the system tables had not yet recorded the run (the documented lag).
- **Sliders, click-to-filter and drill-through** (a run bar opens a Run detail page; an hour opens the model page for that hour) all worked after the restyle.

**Key terms:** AI/BI dashboard, viewer credentials, embedded credentials, dashboard task, system tables, `system.lakeflow`, cross-filter, drill-through.

**Go deeper:** private study notes (drills, diagrams, traps) live outside the public repo.
