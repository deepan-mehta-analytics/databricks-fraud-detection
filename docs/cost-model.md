# Cost Model

Only verified figures appear here. Anything unverified is marked `unverified`
and tracked in `docs/GAPS.md` (G-08, G-09). No total is quoted until G-08 is
settled.

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

At this size, incremental refresh did not shorten an update: fixed pipeline
start-up and planning (about 1.5–2 minutes) dominates (GAPS G-15). All of
the above, plus the scenario runs, fitted within one day's quota.

## Unverified inputs

| Item | Status |
|---|---|
| Free Edition numeric quotas (daily compute quota, model-serving endpoint count) | unverified; feature-level limits are verified, see G-08 |
| Whether a Confluent Basic cluster can be paused, and trial reactivation terms | unverified, see G-07 |
| Total monthly cost (the brief's ₹0–400 claim) | unverified, see G-09 |

---

## Teardown log

Cost-bearing resources are torn down after every working window. Record each
teardown here, with no cluster IDs or account identifiers (this repo is public).

| Date | Resource | Action | Confirmed by |
|---|---|---|---|
| — | — | — | — |
