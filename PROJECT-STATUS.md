# Databricks Fraud Detection — Project Status

Ecosystem snapshot for this repo. Updated after every meaningful session.
Tracked in git (same convention as `gridpulse-gcp`), so it must stay
public-safe: no account IDs, workspace URLs, cluster IDs, or personal
emails — placeholders only.

## Current phase
Phase 0 done (all 22 gaps resolved; the last, G-09, closed 2026-10-15: total
cost ₹0, since nothing in the project can bill; the ADRs are proposed and await
review) and Phase 1 scaffolding done. Phase 2
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
`docs/GAPS.md`). Phase 5 (Gold alerts and governance) is done
(145 tests at ship, CI green): an append-only alert log, a case table with simulated
verdicts, a managers' summary view, a `gold` SQL task, and group-based
grants with an account-name mask and a closed-cases row filter. Workspace
setup passed 2026-10-11 (custom groups and a second user work on Free
Edition; the warehouse is found by name at deploy time). An external table
on Cloudflare R2 was measured as blocked on Free Edition (G-18), so that
export is not wired in. Workspace checks G2–G8 and G11 passed 2026-10-12:
3,154 alerts, exactly the top 50 per hour; 262 closed cases with matching
verdicts; a rerun wrote 0 rows; a manager sees only closed cases with names
masked; REVOKE takes effect at once; a governed-tag (ABAC) policy works on
Free Edition. The late-hour check G10 passed 2026-10-13: an hour held back
one run arrived with its full 50 alerts, after the next hour's, and earlier
hours were untouched (3,268 alerts, 412 closed, equal to the local
calculator). The write-up landed 2026-10-15: ADRs 0010 (alert log and case
table) and 0011 (governance), GAPS §6 (the G-check log), G-19 (ABAC on Free
Edition), six accepted limitations, exam map 16 / 6 / 11, two new concept
notes, and the README Gold Results; released as `v0.4.0`. Phase 6 is split
into 6a (monitoring view), 6b (job alerting) and 6c (model monitoring). Phase
6a is built and deployed (2026-10-15): a `monitor` SQL task rebuilds six plain
views (model results per hour, hours waiting for verdicts, freshness, rejected
rows, job and pipeline run times from `system.lakeflow`), and two AI/BI
dashboards built from Python refresh after each load (191 tests, CI green). A
review before the first push fixed three counting issues (`0612336`); the
first deploy showed every table widget as invalid, fixed with the full column
settings Databricks exports (`e4a84d3`), plus UTC labels (`a47286a`). Workspace
checks D3a (views on today's data: 412 / 120 / 13 / 72, all equal to the CSV
calculation) and D3 (deploy, 8-task graph, both dashboards render) passed.
On 2026-10-19 the test run (run E, 59 drift hours to hour 480) took 17m 9s
with all 8 tasks green, and the Gold and view checks D5–D6 (5,033 alerts,
405 of 822 frauds caught, 72 hours waiting) equalled the CSV calculation;
both dashboard refreshes succeeded (D9). D7 (run history 17.2 minutes,
matching the Jobs page, after a manual Refresh) and D8 (a manager sees the
same totals, an empty queue, and is refused Platform health and the run
history) passed the same day. Two dashboard texts were reworded after them
(`426ecb2`). 2026-10-26: before the screenshots, a dashboard restyle was
designed and planned: one colour-blind-safe theme in code, fixed meaning
colours with ✓ / ✕ symbols, single-axis charts, coloured table cells,
simulated-hour sliders, cross-filtering and a "Run detail" drill-through page,
all from Databricks' published dashboard JSON reference. It was built
2026-10-27 and checked 2026-10-27/28 (D11–D17 all passed): the first deploy's
cell colours and number formats were fixed by copying a UI export's shapes;
hours now read `Day 20, 23:00 (hour 480)`; cancelled runs are grey; the model
page gained a one-hour picker so a reviews hour can drill to it (`7dcecf2`);
and the reviews page explains why a click can blank a total (`6103505`).
Phase 6a is done (236 tests, CI green): ADR 0012, GAPS G-20 to G-22 with the
D1–D17 log, exam map 18 / 6 / 9, a section-6 concept note, the cost model,
and the README with 12 screenshots, two interaction GIFs and the dashboards'
word list; released as `v0.5.0`. Next: Phase 6b (job alerting) brainstorm.
(as of 2026-10-28)

## Phase status

| Phase | Status | Notes |
|---|---|---|
| 0 — Research & decisions (verify open questions, write ADRs) | ✅ Done | G-01, G-02, G-03, G-04, G-06, G-07, G-08 resolved; ADRs 0001–0012 proposed in `docs/adr/` (0004 superseded by 0006; 0005 and the Bronze half of 0003 superseded by 0007, 2026-09-24); ADR 0001 checkpoint-write spike verified 2026-09-22; ADR 0002 grant/row-filter/mask spike verified 2026-09-22 (group creation verified 2026-10-11); dataset switched to PaySim, canonical source verified, balance-column leakage risk excluded (ADR 0006, 2026-09-22); G-01 closed by a measured egress probe (2026-09-24), Auto Loader file ingest designed and recorded as ADR 0007 (2026-09-24); G-10 PaySim volume profile measured and train/replay cut set (2026-09-24); G-11 Asset Bundle deploy on Free Edition verified from the workspace UI with no token (2026-09-24); G-12 Git folder clone of a public GitHub repo verified on Free Edition with no token (2026-09-24), so workspace runs will use a Git folder; G-13 (private dataset syntax), G-14 (incremental refresh measured) and G-15 (refresh duration measured) resolved by the Silver runs (2026-10-06/07); G-05, G-16 and G-17 resolved by the Phase 4 runs (2026-10-11); G-18 (external tables on R2) measured as blocked 2026-10-11; G-19 (ABAC on Free Edition) verified 2026-10-12; G-09 resolved 2026-10-15 (₹0); G-20 (system tables), G-21 (app service principal) and G-22 (dashboard task and viewer credentials) resolved by the Phase 6a probes and checks (2026-10-15 to 2026-10-28); drives `docs/GAPS.md` |
| 1 — Scaffolding (git repo, CI, Makefile, per-directory READMEs) | ✅ Done | Makefile untested locally (no `make` installed); CI (hygiene + unit tests) green on GitHub since 2026-09-24 |
| 2 — Ingest → Bronze | ✅ Done | Designed (ADR 0007); code + 44 unit tests at ship; workspace runs V1–V6 verified 2026-09-24 (5,987,427 Bronze rows, all scenario proofs exact) |
| 3 — Silver + velocity features | ✅ Done | Lakeflow pipeline of 4 SQL materialized views (quality verdicts, clean table, rejected shelf, strict-past receiver features), ADR 0008; 79 local tests at ship; workspace checks S1–S6 all passed 2026-10-06/07 (counts, quality, features three-way identical, late-file recalculation, incremental refresh measured). The Phase 3 add-on (dev/prod targets, CI deploy) is still open |
| 4 — ML training + batch scoring | ✅ Done | scikit-learn model (gradient-boosted trees vs a logistic baseline), MLflow + Unity Catalog registry aliases, `score` job task with a decision log, ADR 0009; 117 local tests at ship; workspace M1–M8 passed 2026-10-08 to 2026-10-11 (1,205,673 payments scored once each; champion 405 of 822 frauds caught at 50 alerts per hour); README Model Summary |
| 5 — Gold alerts + Unity Catalog governance | ✅ Done | Gold SQL task (append-only alerts, cases, summary view), governance SQL (mask, row filter, per-table grants), ABAC probe, local Gold calculator; 145 local tests at ship; final review fixed (run-as guard, view check); workspace G1 passed 2026-10-11 (groups, test user, warehouse lookup), R2 export dropped (blocked, G-18); G2–G8 and G11 passed 2026-10-12 (alerts, cases, rerun, grants, mask, row filter, REVOKE, ABAC policy, lineage); G10 (late hour) passed 2026-10-13; ADRs 0010–0011, README Gold Results, `v0.4.0` 2026-10-15 |
| 6 — Monitoring view (6a), job alerting (6b), model monitoring (6c) | 🔄 In progress | 6a ✅ done: `monitor` SQL task with six plain views and two AI/BI dashboards as code (Fraud operations for all three groups, Platform health for engineers); 236 local tests at ship; deployed 2026-10-15; D3a–D9 passed 2026-10-19 (test run 17m 9s, every view number equal to the CSV calculation, manager view proven); restyle (theme, meaning colours, sliders, cross-filtering, drill-through to Run detail and the model page) built 2026-10-27, D11–D17 passed 2026-10-28; ADR 0012, README screenshots and GIFs, `v0.5.0` 2026-10-28. 6b (job alerting) and 6c (model monitoring) pending |
| 7 — Live demo window + teardown | ⏳ Pending | |

## Exam coverage
[Databricks Certified Data Engineer Associate skills-coverage map](docs/exam-guide-map.md)
(guide "Exam Guide - May 2026", fetched 2026-09-27): 18 of 33 official items
shown with real code or a verified run, 6 designed (an ADR or a `docs/GAPS.md`
row), 9 not started (updated 2026-10-28 with the monitoring evidence: 6.1, 6.2); 23 planned, 7 stretch, 3 not planned. Delta log:
`docs/exam-guide-delta.md`.

## Last commit
See `git log` on `main`; CI runs on every push (GitHub Actions: hygiene + unit tests).
Latest content commits (2026-10-06): `900b84c` Silver reference model + CLI,
`19aefd5` Silver pipeline SQL, `81f2531` bundle/job wiring, `f6b5464` measured
expected values, `11fbd03` shared catalog/schema, `14fa8b3` review follow-ups.
Workspace checks S1–S6 passed against `14fa8b3`. 2026-10-08: Silver write-up (ADR 0008, GAPS, exam map, concept notes, cost model); Phase 4 model code `ae65716`, `8b7cf87`, `bb5bbff`, `f7be1eb`, `5b92c9d`, review fixes `d1039b5` (CI green); status docs `476b56c`, `4532973`. 2026-10-10: environment pin `e7c6453` (did not reach the deployed job), scikit-learn pin in the model notebooks `806763a` (CI green), status docs `62ec064`. 2026-10-11: workspace checks M4b–M8 passed against `806763a`; Phase 4 write-up (ADR 0009, GAPS, cost model, README Model Summary) `cd75dc7`, quiet-hours note `ddb199a`, `v0.3.0`. Phase 5: Gold calculator `6ea4f5d`, Gold SQL `126f940`, job wiring `7751e31`, governance `f21743d` + `b6cdc45`, review fixes `ec54bac`, warehouse name `e5fdaf1`, R2 export dropped `4222ecc` (CI green), status docs `bbc00d7`. 2026-10-12: workspace checks G2–G8 and G11 passed against `4222ecc`, status docs `88ff21f`. 2026-10-13: G10 passed against `4222ecc`, status docs `2e2ca68`. 2026-10-15: Phase 5 write-up (ADRs 0010–0011, GAPS, exam map, concept notes, cost model, README), `v0.4.0`. Phase 6a: calculator `86680cf`, monitor SQL `4928ef7`, dashboards `0e538cd`, bundle wiring `d879ad2`, checks `4a8a93e`, review fixes `0612336`, table settings `e4a84d3`, UTC labels `a47286a` (all CI green). 2026-10-19: one-row checks `86e9ed1`, status docs `016944c` and `3f67a2f`, dashboard wording `426ecb2` (CI green); workspace checks D4–D9 passed; README and status sweep `4753f80`. 2026-10-26: dashboard restyle designed and planned (no code yet); status `fa63774` (CI green). 2026-10-27: restyle build `c5c2082`…`ef04ac1`, then fixes from the owner's checks `bea9522`, `cbd7448`, `36fc88e`, `9e5fff9`, `0471bfa` (CI green). 2026-10-28: drill-through picker `7dcecf2`, click wording `6103505` (CI green); Phase 6a write-up `4eac9ee` (ADR 0012), `43634ec` (GAPS), `920c586` (exam map), `75d2f2f` (cost model), `81b0f3c` (concept note), `8ad5c78` (README, screenshots, GIFs, word-list test), then this status update; `v0.5.0`.

## Releases
| Version | Date | What |
|---|---|---|
| `v0.1.0` | 2026-09-24 | Verified Auto Loader ingest to Bronze (Phase 2) |
| `v0.2.0` | 2026-10-08 | Verified Silver layer: quality rules, dedup, strict-past features (Phase 3) |
| `v0.3.0` | 2026-10-11 | Verified fraud model training and batch scoring: champion catches 405 of 822 frauds at 50 alerts per hour (Phase 4) |
| `v0.4.0` | 2026-10-15 | Verified Gold alerts and Unity Catalog governance: 3,268 alerts and 412 closed cases matching the calculator; manager access proven with a second user (Phase 5) |
| `v0.5.0` | 2026-10-28 | Monitoring dashboards for fraud operations and platform health: six views, two AI/BI dashboards as code with one theme, sliders, cross-filtering and drill-through; every number equal to the calculator; manager view proven (Phase 6a) |

Planned: `v0.6.0` job alerting (6b) · `v0.7.0` model monitoring (6c) · `v1.0.0` live demo and teardown.

## Metrics
Phase 2 ingest verification (2026-09-24): see the README Results section — Bronze counts, per-run durations, per-file pipeline lag. Phase 3 Silver verification (2026-10-06/07): row accounting 5,987,427 = 5,987,412 + 5 + 10, Silver fraud 4,589, pipeline updates 105 s (full) and 115 s / 107 s (incremental). Phase 4 model (2026-10-11, hours 337–408, 822 fraud, 50 alerts per hour): champion caught 405 (precision 0.139, recall 0.493, PR-AUC 0.346); no label delay 406 (0.379); logistic 367 (0.028); largest amount first 352 (0.024); old rules 1. Scoring: 1,205,673 payments once each; rerun 0; promotion then 6 drift payments on version 2. Phase 5 Gold (2026-10-12, hours 337–418): 3,154 alerts, 0 missing / 0 extra against an independent top-50 recompute; 3,154 cases, 262 closed (all verdicts match the label), 2,892 open; rerun wrote 0 rows; job runs 4m 20s (first Gold run) and 14m 52s (nothing new, Silver step 11m 45s, Gold step 42s). Late hour (2026-10-13, through hour 421): hour 419 held in run C (5m 15s) and released in run D (4m 34s) got 50 alerts, 0 marked late, alerted after hour 420's; 420: 50, 421: 14; total 3,268 alerts, 412 closed, both equal to the local calculator. Governance (2026-10-12, second test user): no group → refused at the schema; in `fraud_managers` → 262 closed cases, 0 open, 0 real names (view 262, owner 3,154); `REVOKE SELECT` → refused on the next query, `GRANT` → restored; tag-based policy → 5 of 5 scratch rows `REDACTED` for the test user, 0 for the owner. Phase 6a monitoring (2026-10-19, run E to hour 480): 17m 9s, 8 of 8 tasks; 5,033 alerts, 2,916 closed, 2,117 open; model view 405 / 2,916 / 822 (0.139, 0.493), 72 hours with verdicts, 72 waiting; freshness 480 at all four stages; run history 17.2 minutes, Silver update 4.7 of a 7.2-minute task; manager: same totals, 0 open, Platform health and run history refused. Restyle (2026-10-27/28, D11–D17): reviews totals 405 / 2,511; newest 24 hours 0.168 and 0.519 against 0.139 and 0.493 for all hours (17% vs 14%, 52% vs 49%); 0 stages behind; sliders, cross-filtering and both drill-throughs work; the manager sees the same numbers and no Platform health.

## Known gaps
See `docs/GAPS.md` — the brief-versus-reality register and the exam-coverage
gap map.
