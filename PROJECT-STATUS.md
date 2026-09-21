# Databricks Fraud Detection — Project Status

Ecosystem snapshot for this repo. Updated after every meaningful session.
Tracked in git (same convention as `gridpulse-gcp`), so it must stay
public-safe: no account IDs, workspace URLs, cluster IDs, or personal
emails — placeholders only.

## Current phase
Pre-Phase 0 — local folder skeleton only. Local git repo initialised (no
remote yet), no cloud resources provisioned, no code written. The original brief is captured in
`docs/00-initial-brief.md` and is a **non-binding draft**; every stack and
architecture decision is to be re-researched before it is adopted (see
`docs/GAPS.md`).

## Phase status

Provisional — to be replaced by the real plan once Phase 0 research lands.

| Phase | Status | Notes |
|---|---|---|
| 0 — Research & decisions (verify open questions, write ADRs) | ⏳ Pending | drives `docs/GAPS.md` |
| 1 — Scaffolding (git repo, CI, Makefile, per-directory READMEs) | ⏳ Pending | |
| 2 — Ingest → Bronze | ⏳ Pending | |
| 3 — Silver + velocity features | ⏳ Pending | |
| 4 — ML training + in-stream scoring | ⏳ Pending | |
| 5 — Gold alerts + Unity Catalog governance | ⏳ Pending | |
| 6 — Monitoring app + Workflows/alerting | ⏳ Pending | |
| 7 — Live demo window + teardown | ⏳ Pending | |

## Last commit
Local scaffold commit only (`git log`); no remote configured yet.

## Metrics
No results yet. No number is reported until it is measured from a real run.

## Known gaps
See `docs/GAPS.md` — the brief-versus-reality register and the exam-coverage
gap map.
