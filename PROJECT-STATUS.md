# Databricks Fraud Detection — Project Status

Ecosystem snapshot for this repo. Updated after every meaningful session.
Tracked in git (same convention as `gridpulse-gcp`), so it must stay
public-safe: no account IDs, workspace URLs, cluster IDs, or personal
emails — placeholders only.

## Current phase
Phase 0 in progress (9 of 12 gaps resolved: G-01, G-02, G-03, G-04, G-06,
G-07, G-08, G-10, G-12) and Phase 1 scaffolding done. Phase 2
(Auto Loader ingest to Bronze) has its code written and covered by 44 local
unit tests, plus CI and a Databricks Asset Bundle job definition — none of
it has yet been run in a Databricks workspace (V1–V6 verification pending).
Published to GitHub on 2026-09-24 (public, CI green on the first run). A Databricks Free
Edition workspace has been provisioned (2026-09-22); no Confluent Cloud
resources exist yet. The dataset was switched from Kaggle Credit Card Fraud
to PaySim (ADR 0006, 2026-09-22, canonical `ealaxi/paysim1` source,
CC BY-SA 4.0), after evaluating user-supplied reference links. The
Databricks reference notebook cited in ADR 0006 had a balance-column
label-leakage issue, caught and excluded before any Phase 3/4 code was
written. G-01 (Kafka ingest via Confluent) is closed: a serverless egress probe
(2026-09-24) showed untrusted hosts do not resolve, so Auto Loader file
ingest is the Phase 2 path; its design is recorded as ADR 0007
(2026-09-24). A per-day count of PaySim showed legitimate volume collapsing
after simulated day 17, so the train/score split and replay window were
set inside days 1–17 (G-10). The original brief is captured in
`docs/00-initial-brief.md` and is a **non-binding draft**; every stack and
architecture decision is to be re-researched before it is adopted (see
`docs/GAPS.md`). (as of 2026-09-24)

## Phase status

Provisional — to be replaced by the real plan once Phase 0 research lands.

| Phase | Status | Notes |
|---|---|---|
| 0 — Research & decisions (verify open questions, write ADRs) | 🔄 In progress | G-01, G-02, G-03, G-04, G-06, G-07, G-08 resolved; ADRs 0001–0007 proposed in `docs/adr/` (0004 superseded by 0006; 0005 and the Bronze half of 0003 superseded by 0007, 2026-09-24); ADR 0001 checkpoint-write spike verified 2026-09-22; ADR 0002 grant/row-filter/mask spike verified 2026-09-22 (group creation still open); dataset switched to PaySim, canonical source verified, balance-column leakage risk excluded (ADR 0006, 2026-09-22); G-01 closed by a measured egress probe (2026-09-24), Auto Loader file ingest designed and recorded as ADR 0007 (2026-09-24); G-10 PaySim volume profile measured and train/replay cut set (2026-09-24); G-11 Asset Bundle deploy on Free Edition open; G-12 Git folder clone of a public GitHub repo verified on Free Edition with no token (2026-09-24), so workspace runs will use a Git folder; drives `docs/GAPS.md` |
| 1 — Scaffolding (git repo, CI, Makefile, per-directory READMEs) | ✅ Done | Makefile untested locally (no `make` installed); CI (hygiene + unit tests) green on GitHub since 2026-09-24 |
| 2 — Ingest → Bronze | 🔄 In progress | Designed (ADR 0007, 2026-09-24); code + 44 unit tests; workspace runs V1–V6 pending |
| 3 — Silver + velocity features | ⏳ Pending | |
| 4 — ML training + in-stream scoring | ⏳ Pending | |
| 5 — Gold alerts + Unity Catalog governance | ⏳ Pending | |
| 6 — Monitoring app + Workflows/alerting | ⏳ Pending | |
| 7 — Live demo window + teardown | ⏳ Pending | |

## Last commit
See `git log` on `main`; CI runs on every push (GitHub Actions: hygiene + unit tests).

## Metrics
No results yet. No number is reported until it is measured from a real run.

## Known gaps
See `docs/GAPS.md` — the brief-versus-reality register and the exam-coverage
gap map.
