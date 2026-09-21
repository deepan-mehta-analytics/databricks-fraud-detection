# Initial Brief — Databricks Real-Time Fraud Detection (DRAFT, NOT BINDING)

> Captured 2026-09-21 from the user's original prompt, verbatim. This is a
> starting draft. All tech-stack, architecture, and engineering decisions are
> open to re-research and change in the working sessions.

---

Build a production-grade real-time fraud detection pipeline on Databricks that demonstrates Databricks Certified Data Engineer Associate skills. The pipeline must process streaming transaction events, apply ML-powered fraud scoring, and enforce data governance using Unity Catalog.

## Tech Stack Requirements

### Ingestion Layer
- Use **Confluent Cloud Basic cluster** (free tier: $400 credits for 30 days, then $0.01/topic-hour for incremental usage).
- Configure Kafka topic: `transactions_raw` with JSON schema (transaction_id, card_id, amount, merchant_id, timestamp, device_id, merchant_category).
- Set retention: 7 days, 3 replicas, 100 MB/s throughput (Basic tier limit).

### Streaming Processing
- Use **Databricks Spark Structured Streaming in Real-Time Mode** (serverless compute, Free Edition quota: 2X-Small SQL warehouse).
- Implement exactly-once processing with checkpointing on DBFS.
- Parse JSON, deduplicate by transaction_id, enrich with merchant/category lookup tables.
- Write to Delta Lake Bronze table: `fraud_detection.bronze.transactions`.

### Velocity Feature Engineering
- Compute rolling 5-minute features per card_id:
  - `transaction_count_5min`
  - `avg_amount_5min`
  - `max_amount_5min`
  - `device_velocity` (unique devices in 5 min)
- Use window functions with `watermark("timestamp", "5 minutes")`.
- Write features to **Databricks Lakebase** (Free Edition includes 1 Lakebase project) for real-time ML scoring.

### ML-Powered Fraud Scoring
- Train a **RandomForest classifier** on Kaggle Credit Card Fraud dataset (284,807 transactions, 492 fraud cases).
- Register model in **MLflow Model Registry** (unlimited in Free Edition) under `fraud_detection.models.fraud_detector_v1`.
- Log metrics: precision=0.92, recall=0.87, AUC=0.94.
- Deploy as **Spark UDF** for real-time inference in streaming pipeline.
- Score transactions in-stream; flag high-risk (>0.85 probability) for manual review.

### Delta Lake Medallion Architecture
- **Bronze:** Raw transactions (append-only, schema evolution enabled).
- **Silver:** Enriched transactions with velocity features (MERGE INTO for deduplication).
- **Gold:** Aggregated fraud alerts (transaction_id, fraud_score, risk_level, timestamp).
- Enable Delta Lake features: `delta.autoOptimize`, `delta.autoCompact`, `delta.logRetentionDuration = interval 30 days`.

### Unity Catalog Governance
- Create catalog namespace: `fraud_detection` with schemas: `bronze`, `silver`, `gold`, `models`.
- Implement row-level security:
  - Business users: SELECT only on `gold.fraud_alerts`.
  - Engineers: SELECT on `bronze`, `silver`, `gold`, `models`.
- Enable automatic lineage tracking from Kafka → Bronze → Silver → Gold → ML model.
- Mask PII columns (card_id, device_id) using dynamic views for non-engineering users.

### Monitoring & Alerting
- Build **Databricks App** (Streamlit, Free Edition includes 1 app) for live dashboard:
  - Real-time fraud rate (% flagged transactions).
  - P95 scoring latency (target: <300ms).
  - Model drift (precision/recall by hour).
- Set up Databricks Workflows for:
  - Daily model retraining (trigger at 2 AM IST).
  - Backfill job for historical data (on-demand).
  - Alerting: Email/Slack on fraud spike (>5% in 10 mins).

## Vendor & Pricing Strategy

### Databricks
- Use **Databricks Free Edition** (serverless-only, per-account quotas on compute, jobs, pipelines, model serving, Lakebase, apps).
- Fair-usage quota: 99% of users never hit it. If exceeded, compute shuts down for the day.
- If you hit quotas, apply for **14-day Premium Trial** ($400 credits via AWS/Azure/GCP Marketplace).
- Cost: **₹0/month** (Free Edition covers entire project).

### Confluent Cloud (Kafka)
- Use **Confluent Cloud Basic tier** (free tier: $400 credits for 30 days, then pay-as-you-go).
- Basic tier limits: 100 MB/s throughput, 5 TB storage, 1,500 partitions, 99.5% uptime SLA.
- Incremental cost after free credits: $0.01/topic-hour (≈₹0.83/hour).
- For 1M events/day (≈30M/month), estimated cost: **$0–5/month** (well within free tier).

### Total Monthly Cost
- **Databricks:** ₹0 (Free Edition).
- **Confluent Cloud:** ₹0–400 (free tier covers 1M events/day).
- **Total:** **₹0–400/month** (mostly free for 3-month build).

## Implementation Notes
- Use serverless compute for all workloads (Free Edition is serverless-only).
- Monitor quota usage in Databricks workspace settings.
- Use Delta Lake `VACUUM` with 7-day retention to manage storage costs.
- For MLflow, register models with `mlflow.register_model(model_uri, "fraud_detection.models.fraud_detector_v1")`.
- For Unity Catalog, use `CREATE CATALOG fraud_detection` and `GRANT SELECT ON CATALOG fraud_detection TO ROLE business_users`.

---

## Open questions to verify in the working session (added by Claude, unverified)

These are things I'd check against current docs before committing to the brief, not settled facts:

- **Free Edition network access** — serverless-only workspaces may restrict outbound internet; confirm a Confluent Cloud Kafka connection is actually reachable.
- **Real-Time Mode availability** — confirm it runs on serverless / Free Edition rather than only on dedicated compute.
- **DBFS checkpoints** — DBFS root is generally discouraged/disabled on newer workspaces; Unity Catalog Volumes are the likely replacement.
- **Kaggle dataset vs. schema** — the Kaggle Credit Card Fraud data has PCA features (V1–V28), Time, Amount; it has no card_id / merchant / device fields, so the Kafka event schema needs a synthetic generator or a mapping strategy.
- **Model metrics** — precision/recall/AUC should be measured and logged from the real run, not fixed in advance.
- **UC governance syntax** — Unity Catalog grants go to groups/principals (not `ROLE`); row filters and column masks are the native mechanisms alongside dynamic views.
- **Confluent free credits** — the 30-day window is shorter than a multi-month build; plan the cost/teardown accordingly.
- **Exam alignment** — check which brief items actually map to the Data Engineer Associate syllabus versus extras.
