# 🛡️ Databricks Fraud Detection

## ⚡ Quick Summary

A portfolio project to build a streaming fraud detection pipeline on
Databricks: mobile-money transaction events arrive as files picked up by
Auto Loader, land in a medallion (Bronze, Silver, Gold) layout under Unity
Catalog, get scored by an ML model, and surface as alerts in a monitoring
app. It doubles as a hands-on map of the Databricks Data Engineer Associate
syllabus.

**Status: Phase 2 (ingest to Bronze) done and verified in a real workspace.**
The Auto Loader ingest path (splitter, release task, Bronze stream, 44 local
unit tests, CI, Databricks Asset Bundle job) ran end to end on Databricks Free
Edition on 2026-09-24. Every Bronze count matched its expected value exactly
(see Results). Phase 3 (Silver and features) is next. A free Databricks
workspace is used only for short verification runs. Every architecture and
stack choice is provisional until it has been checked against current docs
(see `docs/GAPS.md`).

### Streaming fraud detection, built honestly and torn down after every run

---

## 🏷️ Project Badges

![Status](https://img.shields.io/badge/Status-Phase_2_Verified-green?style=for-the-badge)
![CI](https://img.shields.io/github/actions/workflow/status/deepan-mehta-analytics/databricks-fraud-detection/ci.yml?branch=main&style=for-the-badge&label=CI)
![Platform](https://img.shields.io/badge/Platform-Databricks-red?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

---

## 📌 Project Overview

- **Research first** — every claim in the original brief is re-verified and logged in `docs/GAPS.md` before adoption
- **Cost-disciplined** — cost-bearing resources are deleted after each working window and logged in `docs/cost-model.md`
- **Measured results only** — no metric is reported unless it came from a real run
- **Public-safe** — placeholders only; no workspace URLs, IDs or keys are committed

---

## ⚙️ Tech Stack

Provisional. Only rows marked "verified" have been checked against docs.

| Layer | Tool | Purpose |
|---|---|---|
| Compute / lakehouse | Databricks (Free Edition target) | Pipelines, Unity Catalog, ML (serverless only, limits verified, G-08) |
| Streaming source | Auto Loader over Unity Catalog Volume file drops | Transaction events replayed as JSON Lines files (verified end to end 2026-09-24; Kafka via Confluent is blocked by Free Edition's outbound-network limit, G-01) |
| Governance | Unity Catalog | Grants to groups, row filters, column masks (verified, G-06) |
| Checkpoints | Unity Catalog Volumes | DBFS root is deprecated (verified, G-03) |
| Code delivery | Databricks Git folder | Workspace runs pull this repo by commit (public clone verified on Free Edition, G-12) |

---

## 🎯 Business Problem

> How quickly can a mobile-money transaction be flagged as likely fraud, and
> how do we show that end to end on free or near-free infrastructure?

---

## 🏗️ Architecture

Ingest to Bronze is built and verified (ADR 0007); later layers are provisional.

```
File drops (Auto Loader) -> Bronze -> Silver (+ velocity features) -> ML scoring -> Gold alerts -> Monitoring app
```

| Layer | Phase |
|---|---|
| Ingest to Bronze | 2 |
| Silver and features | 3 |
| Training and scoring | 4 |
| Gold alerts and governance | 5 |
| Monitoring app and alerting | 6 |

---

## 📁 Repository Structure

```
.
├── app/                        ← monitoring app (Phase 6)
├── data/                       ← local datasets, gitignored
├── docs/                       ← brief, gaps register, cost model, ADRs (docs/adr/), engineering decisions log
├── notebooks/                  ← Databricks notebooks: 01_prepare_outbox, 02_release, 03_ingest_bronze, 99_reset
├── resources/
│   └── fraud_ingest_job.yml    ← Asset Bundle job: release -> ingest tasks, paused 10-min schedule
├── sql/
│   ├── 10_fraud_ingest_setup.sql  ← schema, volumes, release_log (run once)
│   └── 20_verify_bronze.sql       ← V2-V4 verification queries + one-row check of every proof
├── src/
│   └── fraud_ingest/           ← contract, split, scenarios, release_log, release, ingest (stdlib only)
├── tests/                      ← 44 unit tests covering the package above
├── .github/workflows/ci.yml    ← hygiene check + unit test job
├── .env.example                ← placeholder configuration
├── databricks.yml              ← Asset Bundle root (dev target, Free Edition)
├── pyproject.toml              ← pytest config (pythonpath, testpaths)
├── requirements-dev.txt        ← pytest, PyYAML
├── Makefile                    ← check-hygiene and test are real; lint/deploy/teardown are honest stubs
└── PROJECT-STATUS.md
```

---

## ▶️ How to Run

**Local (unit tests only — no Databricks needed):**

1. `python -m pip install -r requirements-dev.txt` — install pytest and PyYAML
2. `python -m pytest -q` — run the 44 unit tests (or `make test`, where `make` is available)
3. `make check-hygiene` — verify no local-only or secret file is tracked
4. `make help` — list targets; `lint`, `deploy` and `teardown` are stubs that fail until their phase lands

**Workspace (the path used for the 2026-09-24 verification; each step is done by hand in the UI):**

1. Create a Git folder from this repo (public GitHub clone works on Free Edition with no token, G-12), then run `sql/10_fraud_ingest_setup.sql` once in the SQL editor
2. Upload the PaySim CSV to the `raw` volume
3. Run `notebooks/01_prepare_outbox.py` once to split it into the `outbox` volume (V1)
4. Deploy the job from the Git folder: open `databricks.yml` → deployments icon → target `dev` → Deploy (no CLI or token needed, G-11)
5. Run the `fraud-ingest` job in this order. Scenario settings go in **Run now ⌄ → Run now with different settings**, which applies them to that run only; don't edit the job's defaults:

   | Run | Settings | Releases |
   |---|---|---|
   | 1 | none | backfill, steps 1–336 |
   | 2 | none | 337–342 |
   | 3 | `duplicate_step=340`, `hold_steps=345` | 343–348 without 345, plus a copy of 340 |
   | 4 | `malformed_step=350`, `malformed_rows=5` | 349–354 |
   | 5 | `release_held=true`, `schema_change_from_step=360` | 355–360 plus the late 345; ingest fails once, then retries |
   | 6 | `steps_per_run=48` | 361–408 |
   | 7 | none | nothing; prints "Nothing to release" |

6. Check Bronze with the one-row query at the end of `sql/20_verify_bronze.sql`

---

## 🧪 Tests

`python -m pytest -q` runs **44 passed**, all local — no Databricks needed.
See `tests/README.md` for the file-by-file breakdown. Notebook behavior and
the Delta release log / Bronze table were verified by workspace runs on
2026-09-24 (V1–V6, see Results), not by this local suite.

---

## 📊 Results / Performance

**Phase 2: ingest to Bronze, verified in a Databricks Free Edition workspace on
2026-09-24.** All runs used serverless compute (performance-optimized jobs).
The code came from this repo's Git folder at commit `601e7da`, and the job
was deployed as an Asset Bundle from the workspace UI.

| Check | Expected | Measured |
|---|---|---|
| V1 split: rows / fraud / files | 6,362,620 / 8,213 / 743 | 6,362,620 / 8,213 / 743 ✅ |
| V2 after backfill: rows / fraud / distinct IDs | 4,784,775 / 3,767 / 4,784,775 | exact match ✅ |
| V3 final: rows / fraud / distinct IDs | 5,987,427 / 4,599 / 5,987,417 | exact match ✅ |
| Every row has a parsed event time (`null_times`) | 0 | 0 ✅ |
| Duplicate file: step-340 IDs seen twice | 10 | 10 ✅ |
| Late file: last step to arrive among 343–348 | 345 | 345 ✅ |
| Schema change: `channel` before step 360 / missing from 360 on | 0 / 0 | 0 / 0 ✅ |
| Malformed values kept in `_rescued_data` | 5 | 5 ✅ |
| New column: ingest fails once (`UNKNOWN_FIELD_EXCEPTION`), then an automatic retry succeeds | yes | yes ✅ |
| Replay finished: the next run releases nothing | "Nothing to release" | printed ✅ |
| V6: job deploys as code on Free Edition | — | yes, from the UI, no token ✅ |

**Runtimes** (single runs, not averages):

| Run | What it did | Duration |
|---|---|---|
| Split notebook | 6.36M-row CSV → 743 JSON Lines files | ~7 min |
| Job run 1 | backfill: 336 files, 4,784,775 rows | 4m 22s |
| Job runs 2–5 | 6 steps each, plus the duplicate, late and malformed scenarios | 1m 0s – 1m 34s |
| Job run 6 | remaining 48 replay steps, 801,360 rows | 2m 35s |
| Job run 7 | nothing left: "Nothing to release" | 18s |

**Pipeline lag** (`ingested_at − file_arrived_at`, per file, 409 files):

| Run | Files | Min / median / max (s) |
|---|---|---|
| Backfill | 336 | 48 / 127 / 193 |
| 6-step runs (2–5) | 25 | 14 / 20–28 (per-run medians) / 39 |
| 48-step run | 48 | 14 / 67 / 124 |

The lag measures this batch design, not Auto Loader's detection speed. The
release task copies files one at a time, and ingest starts only when release
finishes, so the first file copied in a run waits longest. The ~14 s floor is
the hand-off between the two tasks plus stream start-up.

No model metrics yet: training starts in Phase 4.

---

## ⚠️ Known Limitations

- Phase 2 figures come from a single verification day (single runs, not
  averages); the Free Edition daily compute quota is still unknown, only
  that one day's runs fit inside it (G-08)
- Open gaps are tracked in `docs/GAPS.md` (currently G-05, G-09)
- A line that is not valid JSON is ingested as one all-null row (its text is
  lost, and the run still succeeds); the `null_times` check flags it, and
  Silver will filter it (`docs/GAPS.md` §3, V5)
- Landing files are kept after ingest, so the data sits in the workspace
  about three times (CSV, outbox, landing) plus Bronze. Free Edition has no
  stated storage quota; archiving processed files with Auto Loader's
  `cleanSource` option is not yet implemented
- Kafka ingest via Confluent Cloud is not usable on Free Edition without outbound internet access (measured: serverless compute cannot even resolve untrusted hostnames), so events are replayed as files through Auto Loader instead (G-01)
- PaySim is not uniform over time: legitimate volume collapses after simulated day 17 while fraud stays constant, so only days 1–17 are used for training and scoring, and days 18–31 serve as a labelled drift scenario (G-10)
- Real-Time Mode needs classic compute and is unavailable on Free Edition; serverless streaming supports only `Trigger.AvailableNow` and Lakeflow pipelines (G-02)
- PaySim (ADR 0006) is a synthetic mobile-money simulation, not real anonymized transaction data — verified counts: 6,362,620 rows, 8,213 fraud (~0.129%)
- The Databricks Data Engineer Associate coverage map is not yet built
- If a release run fails and is retried with different scenario flags than the failed attempt, a step can land twice (once under each flag combination); recovery is `99_reset`

## 🔜 Roadmap

- [ ] Phase 0 — research and ADRs
- [x] Phase 1 — scaffolding
- [x] Phase 2 — ingest to Bronze (44 unit tests; workspace runs V1–V6 verified 2026-09-24)
- [ ] Phases 3–7 — features, ML, governance, app, live demo and teardown

---

## 📂 Dataset

[PaySim](https://www.kaggle.com/datasets/ealaxi/paysim1) mobile-money
transaction simulator (CC BY-SA 4.0) — `step, type, amount, nameOrig,
oldbalanceOrg, newbalanceOrig, nameDest, oldbalanceDest, newbalanceDest,
isFraud, isFlaggedFraud`. Supersedes the originally planned Kaggle Credit
Card Fraud dataset (see ADR 0006 and `docs/GAPS.md` G-04). Verified from the
downloaded file: 6,362,620 rows, 8,213 fraud (`isFraud=1`, ~0.129%), 16
flagged-fraud (`isFlaggedFraud=1`), a ~30-day simulation (steps 1–743, 1
step = 1 hour). Volume is not uniform across those days; see Known
Limitations and `docs/GAPS.md` G-10.

---

## 📜 License

Released under the MIT License. See [`LICENSE`](LICENSE).

---

## 👤 Author

**Deepan Mehta** — analytics → data engineering → AI/ML.
