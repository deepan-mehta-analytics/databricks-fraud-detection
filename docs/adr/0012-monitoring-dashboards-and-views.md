# ADR 0012: Monitoring with Views, Two AI/BI Dashboards, and System Tables

## Status
Proposed (2026-10-15; restyle and interactions added 2026-10-28). Widens the
label-rule wording of [ADR 0010](0010-gold-alert-log-and-case-table.md) and
keeps the grants model of [ADR 0011](0011-governance-groups-masks-and-external-export.md).

## Context
The original brief pictured a Streamlit app showing a 95th-percentile
per-payment latency and a nightly 2 AM retrain. The built system is different:

- **Scoring is batch.** A job run releases a slice of simulated hours, loads,
  cleans, scores and flags them in one pass, so "per-payment latency" has no
  meaning. The useful question is how long a payment waited from landing to
  being scored in the latest run.
- **The scheduled retrain was rejected** in [ADR 0009](0009-batch-scoring-with-mlflow-and-unity-catalog.md).
- **Three audiences** (engineers, reviewers, managers) already have different
  rights on the Gold tables (ADR 0011). A monitoring screen must not undo that.
- **Verdicts arrive 3 simulated days late**, so the newest 72 hours have no
  answer yet. Showing them as 0% would look like a broken model.
- **Free Edition limits:** about 3 job runs a day, one pipeline, up to 3 apps,
  and nothing documented about system tables. Two probes were run before the
  plan:
  - **P1** (2026-10-15): `system.lakeflow` is readable. Its
    `*_duration_seconds` columns are 0, but `period_start_time` and
    `period_end_time` are filled.
  - **P2** (2026-10-15): a template Streamlit app ran and got its own service
    principal, which was removed when the app was deleted.
- The repo is public: no job, dashboard, warehouse or workspace ID may be
  committed, and jobs deploy in development mode with a `[dev <user>] ` name
  prefix.

## Decision
1. **Plain views, rebuilt each run.** A `monitor` job task runs
   `sql/monitoring/monitoring.sql`, which only creates views and grants:
   `model_accuracy_by_hour`, `hours_waiting_for_verdicts`, `data_freshness`,
   `rejected_rows_by_reason`, `job_run_times`, `pipeline_update_times`. Every
   `CREATE OR REPLACE VIEW` is followed at once by its grants, so a rebuild
   never drops a group's access. The two model views go to all three groups;
   the rest to `fraud_engineers` only.
2. **Two AI/BI dashboards, one per audience**, deployed by the bundle:
   - **Fraud operations** (all three groups): the review queue, review
     outcomes, and "Is the model still good?".
   - **Platform health** (engineers only): job runs, task times, pipeline
     updates, data freshness, set-aside rows, and a Run detail page.
3. **Viewer credentials** (`embed_credentials: false`): every query runs as
   the person looking, so the row filter and masks of ADR 0011 apply. A
   manager sees 0 open cases and `REDACTED` names.
4. **Dashboard tasks** `refresh_operations` and `refresh_platform` run after
   `monitor`. Stated plainly (plan ruling R1): without shared data
   permissions, the task refreshes the dashboard as the job's identity, and
   other viewers can't see that cached result; their screens query live data
   when opened. The tasks prove the dashboard task type, keep the owner's
   cached view current, and are the hook for emailed snapshots in Phase 6b.
5. **Job history from `system.lakeflow`, matched by name.** Minutes are
   `MAX(period_end_time) - MIN(period_start_time)` per run, because the
   duration columns are 0 and long runs or retries are split across several
   timeline rows. Jobs and the pipeline are matched by name after stripping
   the development-mode prefix, never by ID.
6. **The label rule, widened.** `fraud_label` is read in exactly two job-SQL
   statements, the case-closing `MERGE` and `model_accuracy_by_hour`, and
   both apply the same 72-hour cutoff. This replaces ADR 0010's
   one-statement wording and keeps its principle: no answer is used before it
   would really exist. Hours inside the cutoff show as "waiting for verdicts",
   never as 0.
7. **Dashboards written as code.** `src/fraud_monitoring/dashboards.py`
   builds both `.lvdash.json` files, because JSON can't carry the line
   comments this repo requires; a test fails if the committed JSON differs
   from the builder. Every JSON shape is copied from an official Databricks
   example or a UI export, never guessed.
8. **A designed look, the same on both dashboards** (restyle, 2026-10-27/28):
   - one theme (soft grey page, white rounded cards, navy text, a
     colour-blind-checked palette);
   - meaning colours pinned to values: green succeeded, red failed or fraud,
     amber still running, grey cancelled or false alarm, always next to a
     word or symbol (✓ ✕ ↻);
   - pastel table cells by rule (slow runs, failed runs, stages behind,
     set-aside rows);
   - hours a person can read: `Day 20, 23:00 (hour 480)` in tables, and an
     axis title plus hover text on charts.
9. **Interactions** (restyle):
   - hour sliders on both operations pages;
   - cross-filtering: clicking a run or an hour narrows the table or totals
     that share its dataset;
   - drill-through: a run bar opens Run detail for that run, and a reviews
     hour opens the model page for that hour. The model page has a one-hour
     drop-down bound to the reviews dataset as well, because "Drill to" only
     offers a page with a filter on the source chart's dataset (D15b).
10. **Plain language.** Page titles are questions, every chart says how to
    read it, each dashboard ends with a "What these words mean" page, and a
    CI test bans jargon words (latency, percentile, drift and others) from
    visible text.

## Consequences
**Positive:**
- Each audience sees its own slice of the truth, enforced by Unity Catalog,
  not by the dashboard.
- No monitoring table to keep in sync: views read the live tables and system
  tables.
- The look and every chart are reviewed in Git like any other code.

**Negative:**
- No live auto-refresh while a page is open; the data changes once per job
  run.
- `system.lakeflow` rows arrive up to an hour after a run ends, so the
  job's own refresh shows Platform health one run behind until someone clicks
  Refresh.
- No drill-down to a single payment (that is a case tool's job).
- Clicking the red or grey part of a stacked reviews bar also picks that
  verdict, so the other total shows "No data". The page header says so.
- "Sort by value" is ignored on horizontal bars, so task charts promise no
  order.

**Checked in real runs (2026-10-15 to 2026-10-28, see `docs/GAPS.md`):**
- D3a: every view and grant ran on the pre-run data (412 closed, 120 fraud,
  newest hour 421) before any job run was spent.
- D4: run E (hours 422–480) took 17 min 9 s, all 8 tasks green, both refresh
  tasks succeeded (D9).
- D5–D7: 5,033 alerts, 2,916 closed, 2,117 open; 405 confirmed fraud of
  2,916 checked (0.139) and of 822 fraud in all (0.493); freshness 480 at
  every stage; the run read back from `system.lakeflow` as 17.2 minutes.
- D8 and D16: the test user in `fraud_managers` saw 0 open cases, the same
  model numbers as the owner, and was refused Platform health and
  `job_run_times`.
- D11–D17 (restyle): every widget renders; sliders, cross-filters and both
  drill-throughs work; cell colours as designed.

## Alternatives rejected
- **A Streamlit app (the brief):** P2 proved an app works on Free Edition,
  but it would use one of 3 app slots, stop on its own, and re-implement
  per-viewer security that dashboards get from viewer credentials.
- **Materialized views for the monitoring tables:** Free Edition allows one
  pipeline, already used by Silver.
- **Embedded credentials:** every viewer would see the publisher's results,
  including open cases and real account names for managers.
- **Our own run timestamps instead of system tables:** extra writes in every
  task, and they would miss runs that fail before the first write.
- **A two-measure stacked bar** to avoid the "No data" total: how a click
  filters it and how each measure is coloured are undocumented, so the
  meaning colours could be lost. Kept as a possible Phase 6c probe.
- **"Ignored filters" on the reviews totals:** set in the editor only, so the
  next deploy would wipe it, and it would also stop a click narrowing the
  totals to that hour.
