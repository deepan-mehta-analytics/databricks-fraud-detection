# Cost Model

Only verified figures appear here. Anything unverified is marked `unverified`
and tracked in `docs/GAPS.md` (G-08).

**Total cost: ₹0 (G-09, 2026-10-15).** Nothing in this project can bill: no
Confluent account (ADR 0007), no Cloudflare R2 bucket or payment method
(G-18), Databricks Free Edition only, where going over the daily limit stops
compute instead of charging (G-08), and GitHub Actions on a public repo. The
real limit is the daily compute quota, so the tables below track time, not
money.

---

## Verified inputs

**Since ADR 0007 (2026-09-24) no Confluent resources will be created.** Ingest
runs entirely inside Databricks Free Edition, so the Confluent rows below are
kept for reference only and are not part of this project's cost.

| Item | Figure | Source | Fetched |
|---|---|---|---|
| Confluent trial credit | $400, expires 30 days after receipt or when spent, whichever is first | Confluent free-trial docs (via search summary) | 2026-09-21 |
| Confluent Basic: eCKU | First eCKU free, then $0.14 per eCKU-hour (USD) | Confluent pricing page | 2026-09-21 |
| Confluent Basic: ingress/egress | $0.05 per GB | Confluent pricing page | 2026-09-21 |
| Confluent Basic: storage | $0.08 per GB-month | Confluent pricing page | 2026-09-21 |

## Measured run durations (Databricks Free Edition, serverless)

Wall-clock times from real runs. They show where the daily quota goes, but no
cost figure can be attached until the numeric quota is known (G-08).

| Run | Duration | Source | Measured |
|---|---|---|---|
| Ingest backfill (4,784,775 rows, Auto Loader) | 4 m 22 s | job run history | 2026-09-24 |
| Job task `release` (Silver first run) | 48 s | job run history | 2026-10-06 |
| Job task `ingest` (Silver first run, no new files) | 20 s | job run history | 2026-10-06 |
| Job task `silver`, first build | 7 m 6 s, including the wait before the pipeline update starts | job run history | 2026-10-06 |
| Silver pipeline update, first build (all 4 views fully recomputed, ~6M rows) | 105 s | pipeline event log | 2026-10-06 |
| Silver pipeline update, incremental (`WINDOW_FUNCTION` / `APPEND_ONLY`) | 115 s and 107 s | pipeline event log | 2026-10-06/07 |
| `fraud-train` job, 3-day label delay (fit on 282,290 sampled rows, two models compared on 810,804 rows) | 2 m 9 s | job run history | 2026-10-08 |
| `fraud-ingest` job, first scoring run (release + ingest + silver + score; 1,205,673 payments scored) | 5 m 3 s | job run history | 2026-10-11 |
| `fraud-ingest` job, rerun with nothing new (0 payments scored) | 8 m 13 s | job run history | 2026-10-11 |
| `fraud-ingest` job, one drift hour released (6 payments scored) | 5 m 27 s | job run history | 2026-10-11 |
| `fraud-ingest` run A, first run with the `gold` SQL task (3,154 alerts written) | 4 m 20 s | job run history | 2026-10-12 |
| `fraud-ingest` run B, nothing new (0 rows written by Gold) | 14 m 52 s: release 46 s, ingest 19 s, silver 11 m 45 s, score 1 m 14 s, gold 42 s | job run history, per-task view | 2026-10-12 |
| `fraud-ingest` run C, one drift hour released, one held | 5 m 15 s | job run history | 2026-10-13 |
| `fraud-ingest` run D, one drift hour plus the held one | 4 m 34 s | job run history | 2026-10-13 |
| `fraud-ingest` run E, drift hours 422–480 (45,093 payments), first run with the `monitor` and dashboard tasks | 17 m 9 s: release 3 m 35 s, ingest 34.7 s, silver 7 m 14 s, score 1 m 36 s, gold 1 m 42 s, monitor 18.9 s, refresh_operations 51.3 s, refresh_platform 2 m 5 s | job run history, per-task view (GAPS §7, D4) | 2026-10-19 |

At this size, incremental refresh did not shorten an update: fixed pipeline
start-up and planning (about 1.5–2 minutes) dominates (GAPS G-15). All of
the above, plus the scenario runs, fitted within one day's quota.

The whole job takes about 5–8 minutes whether it scores 1.2M payments or
none, so run time doesn't track the number of payments scored. Fixed start-up
time, the pipeline's above all (G-15), is the likely main cost (not timed per
task).
The second `fraud-train` run (no label delay) was not timed.

**Gold's share (Phase 5):** the `gold` SQL task took 42 s of run B's
14 m 52 s on the SQL warehouse (its query history showed 16 queries reading
15,199,568 rows and writing 0). The Silver pipeline task took 11 m 45 s of the
same run with nothing new to process, against a whole job of 4 m 20 s on run A
the same day, so the pipeline's start-up time is the main and most variable
cost (GAPS G-15). The first warehouse query of a day starts slowly (cold start,
not timed).

**Monitoring's share (Phase 6a):** on run E the `monitor` task (views and
grants only) took 18.9 s, and the two dashboard refresh tasks ran side by
side after it, the longer one 2 m 5 s, so monitoring added a little over two
minutes to the job. Opening a dashboard runs its queries on the SQL
warehouse, which counts against the daily limit, not a bill. No dashboard schedule was added, so open dashboards don't spend quota
on their own (GAPS MON-REFRESH). Phase 6a used one job run (E); the restyle
checks (D11–D17) needed no job run at all, only deploys and dashboard
refreshes. Cost: ₹0.

**Daily limit, observed (G-08):** on 2026-10-10 the 4th full `fraud-ingest`
run of the day was refused with `CLUSTER_CREATION_RESOURCE_EXHAUSTED` after 3
runs had completed, and the limit also stopped a run on 2026-10-08. On
2026-10-11, 3 job runs, 3 evaluation notebook runs and a few SQL checks fit.
So this project plans for about 3 full ingest runs a day. Databricks
publishes no number or reset time for this limit. Phase 5 kept to 2 job runs a
day on 2026-10-12 and 2026-10-13. On 2026-10-11 a 5th job run was refused at
its Silver task (`RESOURCE_EXHAUSTED`) after 4 had fitted.

## Unverified inputs

| Item | Status |
|---|---|
| Free Edition numeric quotas (daily compute quota, model-serving endpoint count) | unverified as a number; about 3 full ingest runs a day observed, see G-08 |
| Whether a Confluent Basic cluster can be paused, and trial reactivation terms | unverified, see G-07 |

---

## Teardown log

Cost-bearing resources are torn down after every working window. Record each
teardown here, with no cluster IDs or account identifiers (this repo is public).

| Date | Resource | Action | Confirmed by |
|---|---|---|---|
| 2026-10-15 | Probe Databricks App (P2, Streamlit template) and its service principal | Deleted; the service principal disappeared with it, so no app slot stays used | Owner, in the Apps and Service principals screens (GAPS G-21) |
