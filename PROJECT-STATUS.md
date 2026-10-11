# Databricks Fraud Detection — Project Status

Ecosystem snapshot for this repo. Updated after every meaningful session.
Tracked in git (same convention as `gridpulse-gcp`), so it must stay
public-safe: no account IDs, workspace URLs, cluster IDs, or personal
emails — placeholders only.

## Current phase
Phase 0 in progress (17 of 18 gaps resolved: all but G-09, the cost
recompute) and Phase 1 scaffolding done. Phase 2
(Auto Loader ingest to Bronze) is done: 44 local unit tests at ship, CI, and a
Databricks Asset Bundle job, verified end to end in the Free Edition
workspace on 2026-09-24 (V1–V6; every Bronze count matched exactly — see the
README Results).
Published to GitHub on 2026-09-24 (public, CI green on the first run). A Databricks Free
Edition workspace has been provisioned (2026-09-22); no Confluent Cloud
resources exist (Kafka is ruled out, G-01). The dataset was switched from Kaggle Credit Card Fraud
to PaySim (ADR 0006, 2026-09-22, canonical `ealaxi/paysim1` source,
CC BY-SA 4.0), after evaluating user-supplied reference links. The
Databricks reference notebook cited in ADR 0006 had a balance-column
label-leakage issue, caught and excluded before any Phase 3/4 code was
written. G-01 (Kafka ingest via Confluent) is closed: a serverless egress probe
(2026-09-24) showed untrusted hosts do not resolve, so Auto Loader file
ingest is the Phase 2 path; its design is recorded as ADR 0007
(2026-09-24). A per-day count of PaySim showed legitimate volume collapsing
after simulated day 17, so the train/score split and replay window were
set inside days 1–17 (G-10). Phase 3 (Silver) is done: a Lakeflow pipeline of four materialized
views, verified in the workspace on 2026-10-06/07 (S1–S6, all exact) and
recorded as ADR 0008. Phase 4 (training and batch scoring) is done: gradient-boosted trees
trained on demand, registered in Unity Catalog with `@champion` /
`@challenger` aliases, and a `score` task that logs every decision.
Workspace checks M1–M8 passed 2026-10-08 to 2026-10-11. At 50 alerts per
hour the champion caught 405 of 822 frauds in hours 337–408 (PR-AUC
0.346), against 352 for "largest amount first"; the 3-day label delay cost
1 caught fraud. Recorded as ADR 0009. The model notebooks pin scikit-learn
1.7.2 themselves (`806763a`), because a job-level environment pin
(`e7c6453`) did not survive the deploy. The original brief is captured in
`docs/00-initial-brief.md` and is a **non-binding draft**; every stack and
architecture decision is to be re-researched before it is adopted (see
`docs/GAPS.md`). Phase 5 (Gold alerts and governance) is built and pushed
(145 tests, CI green): an append-only alert log, a case table with simulated
verdicts, a managers' summary view, a `gold` SQL task, and group-based
grants with an account-name mask and a closed-cases row filter. Workspace
setup passed 2026-10-11 (custom groups and a second user work on Free
Edition; the warehouse is found by name at deploy time). An external table
on Cloudflare R2 was measured as blocked on Free Edition (G-18), so that
export is not wired in. The first Gold run waits for the daily compute limit
to reset. (as of 2026-10-11)

## Phase status

Provisional — to be replaced by the real plan once Phase 0 research lands.

| Phase | Status | Notes |
|---|---|---|
| 0 — Research & decisions (verify open questions, write ADRs) | 🔄 In progress | G-01, G-02, G-03, G-04, G-06, G-07, G-08 resolved; ADRs 0001–0009 proposed in `docs/adr/` (0004 superseded by 0006; 0005 and the Bronze half of 0003 superseded by 0007, 2026-09-24); ADR 0001 checkpoint-write spike verified 2026-09-22; ADR 0002 grant/row-filter/mask spike verified 2026-09-22 (group creation verified 2026-10-11); dataset switched to PaySim, canonical source verified, balance-column leakage risk excluded (ADR 0006, 2026-09-22); G-01 closed by a measured egress probe (2026-09-24), Auto Loader file ingest designed and recorded as ADR 0007 (2026-09-24); G-10 PaySim volume profile measured and train/replay cut set (2026-09-24); G-11 Asset Bundle deploy on Free Edition verified from the workspace UI with no token (2026-09-24); G-12 Git folder clone of a public GitHub repo verified on Free Edition with no token (2026-09-24), so workspace runs will use a Git folder; G-13 (private dataset syntax), G-14 (incremental refresh measured) and G-15 (refresh duration measured) resolved by the Silver runs (2026-10-06/07); G-05, G-16 and G-17 resolved by the Phase 4 runs (2026-10-11); G-18 (external tables on R2) measured as blocked 2026-10-11; G-09 open; drives `docs/GAPS.md` |
| 1 — Scaffolding (git repo, CI, Makefile, per-directory READMEs) | ✅ Done | Makefile untested locally (no `make` installed); CI (hygiene + unit tests) green on GitHub since 2026-09-24 |
| 2 — Ingest → Bronze | ✅ Done | Designed (ADR 0007); code + 44 unit tests at ship; workspace runs V1–V6 verified 2026-09-24 (5,987,427 Bronze rows, all scenario proofs exact) |
| 3 — Silver + velocity features | ✅ Done | Lakeflow pipeline of 4 SQL materialized views (quality verdicts, clean table, rejected shelf, strict-past receiver features), ADR 0008; 79 local tests; workspace checks S1–S6 all passed 2026-10-06/07 (counts, quality, features three-way identical, late-file recalculation, incremental refresh measured). The Phase 3 add-on (dev/prod targets, CI deploy) is still open |
| 4 — ML training + batch scoring | ✅ Done | scikit-learn model (gradient-boosted trees vs a logistic baseline), MLflow + Unity Catalog registry aliases, `score` job task with a decision log, ADR 0009; 117 local tests; workspace M1–M8 passed 2026-10-08 to 2026-10-11 (1,205,673 payments scored once each; champion 405 of 822 frauds caught at 50 alerts per hour); README Model Summary |
| 5 — Gold alerts + Unity Catalog governance | 🔄 Built, verifying | Gold SQL task (append-only alerts, cases, summary view), governance SQL (mask, row filter, per-table grants), ABAC probe, local Gold calculator; 145 local tests; final review fixed (run-as guard, view check); workspace G1 passed 2026-10-11 (groups, test user, warehouse lookup), R2 export dropped (blocked, G-18); G2–G11 pending (first run hit the daily limit) |
| 6 — Monitoring app + Workflows/alerting | ⏳ Pending | |
| 7 — Live demo window + teardown | ⏳ Pending | |

## Exam coverage
[Databricks Certified Data Engineer Associate skills-coverage map](docs/exam-guide-map.md)
(guide "Exam Guide - May 2026", fetched 2026-09-27): 15 of 33 official items
shown with real code or a verified run, 5 designed (an ADR or a `docs/GAPS.md`
row), 13 not started (updated 2026-10-08 with the Silver evidence); 23 planned, 7 stretch, 3 not planned. Delta log:
`docs/exam-guide-delta.md`.

## Last commit
See `git log` on `main`; CI runs on every push (GitHub Actions: hygiene + unit tests).
Latest content commits (2026-10-06): `900b84c` Silver reference model + CLI,
`19aefd5` Silver pipeline SQL, `81f2531` bundle/job wiring, `f6b5464` measured
expected values, `11fbd03` shared catalog/schema, `14fa8b3` review follow-ups.
Workspace checks S1–S6 passed against `14fa8b3`. 2026-10-08: Silver write-up (ADR 0008, GAPS, exam map, concept notes, cost model); Phase 4 model code `ae65716`, `8b7cf87`, `bb5bbff`, `f7be1eb`, `5b92c9d`, review fixes `d1039b5` (CI green); status docs `476b56c`, `4532973`. 2026-10-10: environment pin `e7c6453` (did not reach the deployed job), scikit-learn pin in the model notebooks `806763a` (CI green), status docs `62ec064`. 2026-10-11: workspace checks M4b–M8 passed against `806763a`; Phase 4 write-up (ADR 0009, GAPS, cost model, README Model Summary) `cd75dc7`, quiet-hours note `ddb199a`, `v0.3.0`. Phase 5: Gold calculator `6ea4f5d`, Gold SQL `126f940`, job wiring `7751e31`, governance `f21743d` + `b6cdc45`, review fixes `ec54bac`, warehouse name `e5fdaf1`, R2 export dropped `4222ecc` (CI green).

## Releases
| Version | Date | What |
|---|---|---|
| `v0.1.0` | 2026-09-24 | Verified Auto Loader ingest to Bronze (Phase 2) |
| `v0.2.0` | 2026-10-08 | Verified Silver layer: quality rules, dedup, strict-past features (Phase 3) |
| `v0.3.0` | 2026-10-11 | Verified fraud model training and batch scoring: champion catches 405 of 822 frauds at 50 alerts per hour (Phase 4) |

Planned: `v0.4.0` Gold + governance · `v0.5.0` monitoring app · `v1.0.0` live demo and teardown.

## Metrics
Phase 2 ingest verification (2026-09-24): see the README Results section — Bronze counts, per-run durations, per-file pipeline lag. Phase 3 Silver verification (2026-10-06/07): row accounting 5,987,427 = 5,987,412 + 5 + 10, Silver fraud 4,589, pipeline updates 105 s (full) and 115 s / 107 s (incremental). Phase 4 model (2026-10-11, hours 337–408, 822 fraud, 50 alerts per hour): champion caught 405 (precision 0.139, recall 0.493, PR-AUC 0.346); no label delay 406 (0.379); logistic 367 (0.028); largest amount first 352 (0.024); old rules 1. Scoring: 1,205,673 payments once each; rerun 0; promotion then 6 drift payments on version 2.

## Known gaps
See `docs/GAPS.md` — the brief-versus-reality register and the exam-coverage
gap map.
