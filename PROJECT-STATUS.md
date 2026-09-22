# Databricks Fraud Detection — Project Status

Ecosystem snapshot for this repo. Updated after every meaningful session.
Tracked in git (same convention as `gridpulse-gcp`), so it must stay
public-safe: no account IDs, workspace URLs, cluster IDs, or personal
emails — placeholders only.

## Current phase
Phase 0 in progress (6 of 9 gaps resolved: G-02, G-03, G-04, G-06, G-07,
G-08) and Phase 1 scaffolding done, both committed locally. Local git repo
initialised (no remote yet), no pipeline code written. A Databricks Free
Edition workspace has been provisioned (2026-09-22); no Confluent Cloud
resources exist yet. The dataset was switched from Kaggle Credit Card Fraud
to PaySim (ADR 0006, 2026-09-22) after evaluating user-supplied reference
links. The original brief is captured in `docs/00-initial-brief.md` and is a
**non-binding draft**; every stack and architecture decision is to be
re-researched before it is adopted (see `docs/GAPS.md`). (as of 2026-09-22)

## Phase status

Provisional — to be replaced by the real plan once Phase 0 research lands.

| Phase | Status | Notes |
|---|---|---|
| 0 — Research & decisions (verify open questions, write ADRs) | 🔄 In progress | G-02, G-03, G-04, G-06, G-07, G-08 resolved; ADRs 0001–0006 proposed in `docs/adr/` (0004 superseded by 0006); ADR 0001 checkpoint-write spike verified 2026-09-22; dataset switched to PaySim (ADR 0006, 2026-09-22); drives `docs/GAPS.md` |
| 1 — Scaffolding (git repo, CI, Makefile, per-directory READMEs) | ✅ Done | Makefile untested locally (no `make` installed); CI unrun, no remote |
| 2 — Ingest → Bronze | ⏳ Pending | |
| 3 — Silver + velocity features | ⏳ Pending | |
| 4 — ML training + in-stream scoring | ⏳ Pending | |
| 5 — Gold alerts + Unity Catalog governance | ⏳ Pending | |
| 6 — Monitoring app + Workflows/alerting | ⏳ Pending | |
| 7 — Live demo window + teardown | ⏳ Pending | |

## Last commit
Local commits only (`git log`); no remote configured yet, so CI has not run.

## Metrics
No results yet. No number is reported until it is measured from a real run.

## Known gaps
See `docs/GAPS.md` — the brief-versus-reality register and the exam-coverage
gap map.
