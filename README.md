# 🛡️ Databricks Fraud Detection

## ⚡ Quick Summary

A portfolio project to build a streaming fraud detection pipeline on
Databricks: mobile-money transaction events from Kafka land in a medallion
(Bronze, Silver, Gold) layout under Unity Catalog, get scored by an ML
model, and surface as alerts in a monitoring app. It doubles as a hands-on
map of the Databricks Data Engineer Associate syllabus.

**Status: scaffold only.** No pipeline code exists yet and no cloud resources
are provisioned. Every architecture and stack choice is provisional until it
has been checked against current docs (see `docs/GAPS.md`).

### Streaming fraud detection, built honestly and torn down after every run

---

## 🏷️ Project Badges

![Status](https://img.shields.io/badge/Status-Scaffold-orange?style=for-the-badge)
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
| Streaming source | Confluent Cloud Kafka (Basic) | Transaction events (pricing verified, G-07) |
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
Kafka events -> Bronze -> Silver (+ velocity features) -> ML scoring -> Gold alerts -> Monitoring app
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
├── app/            ← monitoring app (Phase 6)
├── data/           ← local datasets, gitignored
├── docs/           ← brief, gaps register, cost model, ADRs (docs/adr/), engineering decisions log
├── notebooks/      ← Databricks notebooks (Phases 2–4)
├── sql/            ← Unity Catalog DDL and grants (Phase 5)
├── src/            ← shared Python modules
├── tests/          ← tests (none yet)
├── .github/workflows/ci.yml  ← hygiene check only
├── .env.example    ← placeholder configuration
├── Makefile        ← honest stubs
└── PROJECT-STATUS.md
```

---

## ▶️ How to Run

Nothing runs yet. Available today:

1. `make check-hygiene` — verify no local-only or secret file is tracked
2. `make help` — list targets; the rest are stubs that fail until their phase lands

---

## 🧪 Tests

No tests yet. Planned with the first Python source in Phase 2.

---

## 📊 Results / Performance

None. No number is reported until it is measured from a real run.

---

## ⚠️ Known Limitations

- Scaffold only; no pipeline exists
- Open gaps are tracked in `docs/GAPS.md` (currently G-01, G-05, G-09)
- Real-Time Mode needs classic compute and is unavailable on Free Edition; serverless streaming supports only `Trigger.AvailableNow` and Lakeflow pipelines (G-02)
- PaySim (ADR 0006) is a synthetic mobile-money simulation, not real anonymized transaction data — verified counts: 6,362,620 rows, 8,213 fraud (~0.129%)
- The Databricks Data Engineer Associate coverage map is not yet built

## 🔜 Roadmap

- [ ] Phase 0 — research and ADRs
- [x] Phase 1 — scaffolding
- [ ] Phases 2–7 — ingest, features, ML, governance, app, live demo and teardown

---

## 📂 Dataset

[PaySim](https://www.kaggle.com/datasets/ealaxi/paysim1) mobile-money
transaction simulator (CC BY-SA 4.0) — `step, type, amount, nameOrig,
oldbalanceOrg, newbalanceOrig, nameDest, oldbalanceDest, newbalanceDest,
isFraud, isFlaggedFraud`. Supersedes the originally planned Kaggle Credit
Card Fraud dataset (see ADR 0006 and `docs/GAPS.md` G-04). Verified from the
downloaded file: 6,362,620 rows, 8,213 fraud (`isFraud=1`, ~0.129%), 16
flagged-fraud (`isFlaggedFraud=1`), a ~30-day simulation (steps 1–743, 1
step = 1 hour).

---

## 📜 License

Released under the MIT License. See [`LICENSE`](LICENSE).

---

## 👤 Author

**Deepan Mehta** — analytics → data engineering → AI/ML.
