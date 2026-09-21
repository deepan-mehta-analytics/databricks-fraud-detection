# Gaps Register

Two views of "what we don't know or don't cover yet". Both feed the README's
Known Limitations section, so nothing here gets quietly dropped.

Status legend: `⏳ Open` · `🔎 Researching` · `✅ Resolved` · `⚠️ Accepted limitation`

---

## 1. Brief-versus-reality register

Claims in `docs/00-initial-brief.md` checked against current docs or a real
run. Seeded 2026-09-21 from open questions raised when the brief was captured
(none verified yet).

| ID | Brief claim / assumption | What to verify | How | Decision | Status |
|---|---|---|---|---|---|
| G-01 | Free Edition serverless can ingest from Confluent Cloud Kafka | Outbound network access from serverless compute to an external Kafka broker | Databricks docs + a real connection test | — | ⏳ Open |
| G-02 | Structured Streaming "Real-Time Mode" runs on serverless / Free Edition | Feature availability and compute requirements | Databricks docs | — | ⏳ Open |
| G-03 | Checkpoints on DBFS | Whether DBFS root is usable; Unity Catalog Volumes as replacement | Databricks docs | — | ⏳ Open |
| G-04 | Kaggle Credit Card Fraud data drives the Kafka event schema | Dataset has PCA features V1–V28, Time, Amount only — no card / merchant / device fields. Need a synthetic generator or mapping strategy | Dataset inspection | — | ⏳ Open |
| G-05 | Model metrics fixed at precision 0.92 / recall 0.87 / AUC 0.94 | Metrics must be measured and logged from the real training run | Real run | — | ⏳ Open |
| G-06 | `GRANT ... TO ROLE business_users`; "row-level security" via dynamic views | Unity Catalog grants target groups/principals; row filters and column masks are the native mechanisms | UC docs | — | ⏳ Open |
| G-07 | Confluent free credits cover a multi-month build | Credit window (30 days) vs build length; teardown and cost plan | Confluent pricing page | — | ⏳ Open |
| G-08 | Free Edition includes Lakebase, Databricks Apps, model serving with usable quotas | Current availability and quota limits per feature | Databricks docs | — | ⏳ Open |
| G-09 | Total cost ₹0–400/month | Recompute from verified pricing once G-07 and G-08 are settled | Pricing pages | — | ⏳ Open |

Add a row whenever research contradicts the brief. Resolved rows stay in the
table with their decision, so the reasoning remains auditable.

---

## 2. Exam-coverage gap map

Databricks Certified Data Engineer Associate syllabus versus what this
project actually demonstrates.

**Not populated yet.** In the working session, fetch the current official
exam guide first (do not fill this from memory), record its version and
fetch date here, then add one row per official sub-objective:

| § | Sub-objective | Module in this repo | Status |
|---|---|---|---|
| — | — | — | ⏳ Open |

Rows with no module are the gaps. Decide for each: build it, or record it
under Known Limitations.

---

## 3. Accepted limitations

Items promoted from sections 1–2 that we decided to live with. Each becomes
a bullet in the README's Known Limitations.

| ID | Limitation | Why accepted |
|---|---|---|
| — | — | — |
