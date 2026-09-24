# 🛡️ Databricks Fraud Detection

## ⚡ Quick Summary

A portfolio project to build a streaming fraud detection pipeline on
Databricks: mobile-money transaction events arrive as files picked up by
Auto Loader, land in a medallion (Bronze, Silver, Gold) layout under Unity
Catalog, get scored by an ML model, and surface as alerts in a monitoring
app. It doubles as a hands-on map of the Databricks Data Engineer Associate
syllabus.

**Status: Phase 2 code written; workspace verification pending.** The Auto
Loader ingest path (splitter, release task, Bronze stream, 44 local unit
tests, CI, Databricks Asset Bundle job definition) is written and tested
locally; it has not yet been run in a Databricks workspace. A free Databricks
workspace is used only for short verification spikes. Every architecture and
stack choice is provisional until it has been checked against current docs
(see `docs/GAPS.md`).

### Streaming fraud detection, built honestly and torn down after every run

---

## 🏷️ Project Badges

![Status](https://img.shields.io/badge/Status-Phase_2_In_Progress-yellow?style=for-the-badge)
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
| Streaming source | Auto Loader over Unity Catalog Volume file drops | Transaction events replayed as JSON Lines files (primary path; Kafka via Confluent is blocked by Free Edition's outbound-network limit, G-01) |
| Governance | Unity Catalog | Grants to groups, row filters, column masks (verified, G-06) |
| Checkpoints | Unity Catalog Volumes | DBFS root is deprecated (verified, G-03) |

---

## 🎯 Business Problem

> How quickly can a mobile-money transaction be flagged as likely fraud, and
> how do we show that end to end on free or near-free infrastructure?

---

## 🏗️ Architecture

Provisional, pending Phase 0 decisions.

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
│   └── 20_verify_bronze.sql       ← V2-V4 workspace verification queries
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

**Workspace (outline — not yet run; see `docs/GAPS.md` G-11 and Task 9):**

1. Run `sql/10_fraud_ingest_setup.sql` once in the SQL editor
2. Upload the PaySim CSV to the `raw` volume
3. Run `notebooks/01_prepare_outbox.py` once to split it into the `outbox` volume (V1)
4. Deploy `resources/fraud_ingest_job.yml` via the Databricks Asset Bundle CLI (`databricks bundle deploy`), or recreate the job manually in the UI if bundle deploy is unsupported on Free Edition
5. Run the `fraud-ingest` job repeatedly (backfill, then K-step replay/drift runs) and verify Bronze with `sql/20_verify_bronze.sql` (V2–V4)

---

## 🧪 Tests

`python -m pytest -q` runs **44 passed**, all local — no Databricks needed.
See `tests/README.md` for the file-by-file breakdown. Notebook behavior and
the Delta release log / Bronze table are verified by workspace runs (V1–V6),
not by this local suite.

---

## 📊 Results / Performance

None. No number is reported until it is measured from a real run.

---

## ⚠️ Known Limitations

- Phase 2 ingest code is written and unit-tested locally (44 tests) but has
  not yet run in a Databricks workspace — no Bronze row counts, ingest lag,
  or runtime figures exist yet
- Open gaps are tracked in `docs/GAPS.md` (currently G-01, G-05, G-09, G-11)
- Unverified until a real workspace run (ADR 0007): whether jobs declared as
  code (Asset Bundles) deploy on Free Edition (G-11), and what a completely
  invalid JSON line does on ingest
- Kafka ingest via Confluent Cloud is not usable on Free Edition without outbound internet access, so events are replayed as files through Auto Loader instead (G-01)
- PaySim is not uniform over time: legitimate volume collapses after simulated day 17 while fraud stays constant, so only days 1–17 are used for training and scoring, and days 18–31 serve as a labelled drift scenario (G-10)
- Real-Time Mode needs classic compute and is unavailable on Free Edition; serverless streaming supports only `Trigger.AvailableNow` and Lakeflow pipelines (G-02)
- PaySim (ADR 0006) is a synthetic mobile-money simulation, not real anonymized transaction data — verified counts: 6,362,620 rows, 8,213 fraud (~0.129%)
- The Databricks Data Engineer Associate coverage map is not yet built
- If a release run fails and is retried with different scenario flags than the failed attempt, a step can land twice (once under each flag combination); recovery is `99_reset`

## 🔜 Roadmap

- [ ] Phase 0 — research and ADRs
- [x] Phase 1 — scaffolding
- [ ] Phase 2 — ingest to Bronze (code + 44 unit tests done; workspace runs V1–V6 pending)
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
