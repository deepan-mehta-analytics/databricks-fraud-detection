# Databricks Fraud Detection — Project Status

Ecosystem snapshot for this repo. Updated after every meaningful session.
Tracked in git (same convention as `gridpulse-gcp`), so it must stay
public-safe: no account IDs, workspace URLs, cluster IDs, or personal
emails — placeholders only.

## Current phase
Phase 0 in progress (13 of 17 gaps resolved: G-01, G-02, G-03, G-04, G-06,
G-07, G-08, G-10, G-11, G-12, G-13, G-14, G-15) and Phase 1 scaffolding done. Phase 2
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
recorded as ADR 0008. Phase 4 (training and batch scoring) is built and
pushed (115 tests, CI green); its workspace checks are in progress: M1 (model
registry probe), M2 and M3 (both training runs, every count exact), M3b
(scoring with no champion succeeds) and M4a (version 1 promoted) passed on
2026-10-08. The first scoring run (M4b) was refused by the Free Edition
serverless limit (`CLUSTER_CREATION_RESOURCE_EXHAUSTED`) and is retried
after the reset; M4b–M8 are next. The original brief is captured in
`docs/00-initial-brief.md` and is a **non-binding draft**; every stack and
architecture decision is to be re-researched before it is adopted (see
`docs/GAPS.md`). (as of 2026-10-08, end of session)

## Phase status

Provisional — to be replaced by the real plan once Phase 0 research lands.

| Phase | Status | Notes |
|---|---|---|
| 0 — Research & decisions (verify open questions, write ADRs) | 🔄 In progress | G-01, G-02, G-03, G-04, G-06, G-07, G-08 resolved; ADRs 0001–0008 proposed in `docs/adr/` (0004 superseded by 0006; 0005 and the Bronze half of 0003 superseded by 0007, 2026-09-24); ADR 0001 checkpoint-write spike verified 2026-09-22; ADR 0002 grant/row-filter/mask spike verified 2026-09-22 (group creation still open); dataset switched to PaySim, canonical source verified, balance-column leakage risk excluded (ADR 0006, 2026-09-22); G-01 closed by a measured egress probe (2026-09-24), Auto Loader file ingest designed and recorded as ADR 0007 (2026-09-24); G-10 PaySim volume profile measured and train/replay cut set (2026-09-24); G-11 Asset Bundle deploy on Free Edition verified from the workspace UI with no token (2026-09-24); G-12 Git folder clone of a public GitHub repo verified on Free Edition with no token (2026-09-24), so workspace runs will use a Git folder; G-13 (private dataset syntax), G-14 (incremental refresh measured) and G-15 (refresh duration measured) resolved by the Silver runs (2026-10-06/07); G-05, G-09, G-16 and G-17 open; drives `docs/GAPS.md` |
| 1 — Scaffolding (git repo, CI, Makefile, per-directory READMEs) | ✅ Done | Makefile untested locally (no `make` installed); CI (hygiene + unit tests) green on GitHub since 2026-09-24 |
| 2 — Ingest → Bronze | ✅ Done | Designed (ADR 0007); code + 44 unit tests at ship; workspace runs V1–V6 verified 2026-09-24 (5,987,427 Bronze rows, all scenario proofs exact) |
| 3 — Silver + velocity features | ✅ Done | Lakeflow pipeline of 4 SQL materialized views (quality verdicts, clean table, rejected shelf, strict-past receiver features), ADR 0008; 79 local tests; workspace checks S1–S6 all passed 2026-10-06/07 (counts, quality, features three-way identical, late-file recalculation, incremental refresh measured). The Phase 3 add-on (dev/prod targets, CI deploy) is still open |
| 4 — ML training + batch scoring | 🔄 Built, verifying | scikit-learn model (gradient-boosted trees vs a logistic baseline), MLflow + Unity Catalog registry aliases, `score` job task with a decision log; 115 local tests; workspace M1–M4a passed 2026-10-08, M4b (first scoring run) hit the serverless limit and is retried next, M4b–M8 pending; ADR 0009 and the README Model Summary land after verification |
| 5 — Gold alerts + Unity Catalog governance | ⏳ Pending | |
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
Workspace checks S1–S6 passed against `14fa8b3`. 2026-10-08: Silver write-up (ADR 0008, GAPS, exam map, concept notes, cost model); Phase 4 model code `ae65716`, `8b7cf87`, `bb5bbff`, `f7be1eb`, `5b92c9d`, review fixes `d1039b5` (CI green); status docs `476b56c`.

## Releases
| Version | Date | What |
|---|---|---|
| `v0.1.0` | 2026-09-24 | Verified Auto Loader ingest to Bronze (Phase 2) |
| `v0.2.0` | 2026-10-08 | Verified Silver layer: quality rules, dedup, strict-past features (Phase 3) |

Planned: `v0.3.0` ML scoring · `v0.4.0` Gold + governance · `v0.5.0` monitoring app · `v1.0.0` live demo and teardown.

## Metrics
Phase 2 ingest verification (2026-09-24): see the README Results section — Bronze counts, per-run durations, per-file pipeline lag. Phase 3 Silver verification (2026-10-06/07): row accounting 5,987,427 = 5,987,412 + 5 + 10, Silver fraud 4,589, pipeline updates 105 s (full) and 115 s / 107 s (incremental). No model metrics yet (Phase 4).

## Known gaps
See `docs/GAPS.md` — the brief-versus-reality register and the exam-coverage
gap map.
