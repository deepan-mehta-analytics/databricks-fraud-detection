# Exam guide map: Databricks Certified Data Engineer Associate

A skills-coverage matrix: which parts of the official exam guide this repo
demonstrates with real, runnable evidence. It is not exam prep.

Guide: [Databricks Certified Data Engineer Associate exam guide (PDF)](https://www.databricks.com/sites/default/files/2026-05/databricks-certified-data-engineer-associate-exam-guide-may-2026-000.pdf),
"Exam Guide - May 2026" (exam version as of 2026-05-04), fetched 2026-09-27.
Re-checks are logged in [`exam-guide-delta.md`](exam-guide-delta.md).

**Coverage:** 15 ✅ shown · 5 🟡 designed · 13 ⬜ not started, of 33 items.
**Plan:** 23 planned · 7 stretch · 3 not planned.

Status: ✅ shown (code or a verified run in this repo, covering the item's core — a partial ✅ says exactly what's missing in the Skill column), 🟡 designed (cites a public ADR or a `docs/GAPS.md` row, not built to the item's core), ⬜ not started.

## 1. Databricks Intelligence Platform (6%)

| # | Official item (own words) | Skill in this repo | Evidence | Status | Plan tier |
|---|---|---|---|---|---|
| 1.1 | Core platform pieces: the lakehouse architecture, Delta Lake and Unity Catalog | A Unity Catalog schema with 4 governed Volumes and a managed Delta Bronze table, all under one lakehouse namespace ([concept note](concepts/1-databricks-intelligence-platform/delta-bronze-and-unity-catalog.md)) | [setup SQL](../sql/10_fraud_ingest_setup.sql), [ingest](../src/fraud_ingest/ingest.py), `a6b108c` | ✅ | planned |
| 1.2 | Compute choices (serverless, classic job and all-purpose clusters, SQL warehouses): traits, limits, cost, and which fits a workload | partial: only serverless is used and verified; ADR 0003 reasons about serverless versus classic compute for the streaming trigger choice, and GAPS G-08 records Free Edition's serverless-only limits, but no classic cluster or cost comparison is built | [ADR 0003](adr/0003-streaming-trigger-model-on-serverless.md), [GAPS G-08](GAPS.md) | 🟡 | planned |

## 2. Data Ingestion and Loading (21%)

| # | Official item (own words) | Skill in this repo | Evidence | Status | Plan tier |
|---|---|---|---|---|---|
| 2.1 | Ingestion patterns (batch, streaming, incremental) and sources: local files, Lakeflow Connect standard and managed connectors | partial: incremental, file-based streaming ingest from a Unity Catalog Volume ("local files"); Lakeflow Connect standard/managed connectors are not used ([concept note](concepts/2-data-ingestion-and-loading/auto-loader.md)) | [ADR 0007](adr/0007-file-based-ingest-with-auto-loader.md), [release](../notebooks/02_release.py), [ingest](../notebooks/03_ingest_bronze.py), `a6b108c` | ✅ | planned |
| 2.2 | COPY INTO for incremental file loads from cloud storage into UC tables | Not built — Auto Loader was chosen as the single ingest mechanism (ADR 0007); COPY INTO is not used | — | ⬜ | not planned |
| 2.3 | Auto Loader with schema enforcement and evolution (directory listing or file notification) into UC tables | Auto Loader (`cloudFiles`) with pinned schema hints, `addNewColumns` schema evolution and directory listing, writing into a UC Delta table, verified end to end ([concept note](concepts/2-data-ingestion-and-loading/auto-loader.md)) | [ingest.py](../src/fraud_ingest/ingest.py), `a6b108c` | ✅ | planned |
| 2.4 | Configure Lakeflow Connect to ingest enterprise sources into UC tables | Not built — this project has one file-based source (PaySim), not an enterprise connector target | — | ⬜ | not planned |
| 2.5 | JDBC/ODBC or REST clients in notebooks landing data, scheduled with Lakeflow Jobs | Not built — ADR 0007 rejected a laptop/API uploader in favour of file-based release, so no JDBC/ODBC/REST client is used | — | ⬜ | not planned |
| 2.6 | Choose between Auto Loader, Lakeflow Connect, partner connectors and others by volume, frequency, data type and governance | Chose and built Auto Loader over Kafka/Confluent by measured requirements: outbound network access, supported trigger types, quota and data-volume profile ([concept note](concepts/2-data-ingestion-and-loading/choosing-an-ingestion-method.md)) | [ADR 0007](adr/0007-file-based-ingest-with-auto-loader.md), [GAPS G-01](GAPS.md), `a6b108c` | ✅ | planned |
| 2.7 | Semi-structured and unstructured data (JSON, nested) into UC Delta tables | partial: JSON Lines (semi-structured) records ingested into a Delta table with rescued-data capture for bad values; no nested/array fields are demonstrated ([concept note](concepts/2-data-ingestion-and-loading/auto-loader.md)) | [contract.py](../src/fraud_ingest/contract.py), [ingest.py](../src/fraud_ingest/ingest.py), `a6b108c` | ✅ | planned |

## 3. Data Transformation and Modeling (22%)

| # | Official item (own words) | Skill in this repo | Evidence | Status | Plan tier |
|---|---|---|---|---|---|
| 3.1 | Clean Bronze into Silver with PySpark or SQL: nulls, data types | SQL rules give every Bronze row a verdict (missing ID/time/account, step-time mismatch, bad amount, unknown type, bad label, unparsed value); null-safe checks (`COALESCE(…, FALSE)`), typed casts and `try_divide`; clean rows go to `silver_transactions`, rejected rows to a shelf with the reason. Verified: the row accounting reconciled exactly (GAPS §4, S2) ([concept note](concepts/3-data-transformation-and-modeling/data-quality-expectations-and-quarantine.md)) | [pipeline SQL](../pipelines/silver/), [ADR 0008](adr/0008-silver-on-a-declarative-pipeline.md), `19aefd5`, verified at `14fa8b3` | ✅ | planned |
| 3.2 | Combine DataFrames: inner, left, broadcast, multi-key and cross joins; union and union all | Not built — the Silver features use window functions, not joins; a self-join appears only in a verification query (`sql/31_verify_silver.sql`), not in the pipeline | — | ⬜ | stretch |
| 3.3 | Reshape: add, drop, split and rename columns; filter; explode arrays | partial: adds verdict and 7 feature columns, renames `verdict` to `rejection_reason`, drops columns with a fixed list and `* EXCEPT (…)`, and filters by verdict; no split or explode, because PaySim has no array or delimited fields ([concept note](concepts/3-data-transformation-and-modeling/window-functions-and-point-in-time-features.md)) | [pipeline SQL](../pipelines/silver/), `19aefd5`, verified at `14fa8b3` | ✅ | planned |
| 3.4 | Deduplicate and aggregate: count, approximate count distinct, mean, summary | partial: first-arrival dedup on `transaction_id` with `ROW_NUMBER()` plus a content hash (identical copies removed and counted, conflicting copies rejected), and windowed count, sum, max, average ratio and exact distinct count (`size(collect_set(…))`); approximate count distinct and `summary()` are not used ([concept notes](concepts/3-data-transformation-and-modeling/deduplicating-immutable-events.md), [2](concepts/3-data-transformation-and-modeling/window-functions-and-point-in-time-features.md)) | [pipeline SQL](../pipelines/silver/), `19aefd5`, verified at `14fa8b3` (GAPS §4, S2–S4) | ✅ | planned |
| 3.5 | Basic Spark tuning settings (shuffle partitions, default parallelism, executor/driver memory, broadcast threshold) and re-measuring | Not built yet — not on the current roadmap; Free Edition is serverless-only (G-08), so cluster-level tuning knobs may not apply | — | ⬜ | stretch |
| 3.6 | Gold objects in UC: materialized views, views, streaming tables and tables, and when to use each | partial: four materialized views (one private) in a declarative pipeline, with the materialized-view-versus-streaming-table choice reasoned in ADR 0008 and the refresh technique measured (GAPS G-14); built at the Silver layer, not Gold, and no plain view or declarative streaming table is used ([concept note](concepts/3-data-transformation-and-modeling/materialized-views-and-streaming-tables.md)) | [pipeline resource](../resources/fraud_silver_pipeline.yml), [ADR 0008](adr/0008-silver-on-a-declarative-pipeline.md), `81f2531`, verified at `14fa8b3` | ✅ | planned |
| 3.7 | Data quality checks and validation rules for Silver and Gold | Nine warn expectations count each rule's failures on the Data quality tab, three `FAIL UPDATE` guards protect the clean table, and failing rows are quarantined on a rejected shelf. Verified: the tab showed exactly the predicted counts (GAPS §4, S3) ([concept note](concepts/3-data-transformation-and-modeling/data-quality-expectations-and-quarantine.md)) | [pipeline SQL](../pipelines/silver/), `19aefd5`, verified at `14fa8b3` | ✅ | planned |

## 4. Working with Lakeflow Jobs (16%)

| # | Official item (own words) | Skill in this repo | Evidence | Status | Plan tier |
|---|---|---|---|---|---|
| 4.1 | Control flow in Lakeflow Jobs: retries, branching and looping tasks | partial: an automatic retry (`max_retries: 1`) is configured and was verified to recover a failed run after a mid-stream schema change; no branching or looping tasks are used ([concept note](concepts/4-working-with-lakeflow-jobs/job-retries-dependencies-and-schedules.md)) | [job definition](../resources/fraud_ingest_job.yml), `a6b108c` | ✅ | planned |
| 4.2 | Common task types (notebook, SQL, dashboard, pipeline) and their dependencies in the task graph | partial: two notebook tasks and one pipeline task (`silver` runs the Lakeflow pipeline) in a linear dependency chain (`depends_on`); no SQL or dashboard task types are used ([concept note](concepts/4-working-with-lakeflow-jobs/job-retries-dependencies-and-schedules.md)) | [job definition](../resources/fraud_ingest_job.yml), `81f2531`, verified at `14fa8b3` | ✅ | planned |
| 4.3 | Job schedules and trigger types: scheduled, file arrival, table update | partial: a real, committed and deployed scheduled (cron) trigger is configured on the job, though paused — every real run so far used a manual "Run now", not the schedule itself; no file-arrival or table-update trigger is configured ([concept note](concepts/4-working-with-lakeflow-jobs/job-retries-dependencies-and-schedules.md)) | [job definition](../resources/fraud_ingest_job.yml) | ✅ | planned |
| 4.4 | Choose time-based or data-driven triggers from data availability and dependencies | ADR 0007 reasons about keeping the schedule paused because the daily compute quota is unmeasured; it does not compare against a file-arrival or table-update trigger | [ADR 0007](adr/0007-file-based-ingest-with-auto-loader.md) | 🟡 | planned |

## 5. Implementing CI/CD (10%)

| # | Official item (own words) | Skill in this repo | Evidence | Status | Plan tier |
|---|---|---|---|---|---|
| 5.1 | Git Folders in the workspace UI: branches, commit, push, pull requests | partial: clone only — a public GitHub repo was cloned into a workspace Git Folder for code delivery (GAPS G-12); branches, commits, pushes and pull requests from the workspace UI were not exercised | [GAPS G-12](GAPS.md) | 🟡 | planned |
| 5.2 | Bundle variables and target overrides for dev, test and prod | partial: bundle variables `catalog` and `schema` feed the job defaults, the pipeline target and the pipeline's Bronze source, deployed and used on the real runs; there is only one `dev` target, so no target overrides yet (planned as a Phase 3 add-on) | [databricks.yml](../databricks.yml), `11fbd03` | 🟡 | planned |
| 5.3 | Deploy bundles to package and promote jobs, pipelines and other assets across environments | partial: single dev target — the Asset Bundle was deployed from the workspace UI with no CLI or token (GAPS G-11), and it now packages the three-task job and the Silver pipeline together (deployed 2026-10-06); promoting across multiple environments is not shown, since only one target exists | [databricks.yml](../databricks.yml), [job definition](../resources/fraud_ingest_job.yml), [pipeline](../resources/fraud_silver_pipeline.yml), [GAPS G-11](GAPS.md) | 🟡 | planned |
| 5.4 | The Databricks CLI to validate and deploy bundles in automated CI/CD | Not built yet — planned as a Phase 3 add-on: CI deploy with the Databricks CLI from a protected GitHub environment (main-only, approval required). Keyless OIDC federation is not possible on Free Edition (no account console); a one-time OIDC demo on a free trial is optional | — | ⬜ | planned |

## 6. Troubleshooting, Monitoring, and Optimization (10%)

| # | Official item (own words) | Skill in this repo | Evidence | Status | Plan tier |
|---|---|---|---|---|---|
| 6.1 | Spot job-performance trends in the Lakeflow Jobs run history | Not built yet — planned for the Phase 6 monitoring app | — | ⬜ | planned |
| 6.2 | Monitor pipeline health in the Jobs UI: statuses, task graph blockers, run times, failure rates | Not built yet — planned for the Phase 6 monitoring app | — | ⬜ | planned |
| 6.3 | Find bottlenecks (skew, shuffle, disk spill) from stage metrics in the Spark UI | Not built yet — not on the current roadmap wording | — | ⬜ | stretch |
| 6.4 | Liquid Clustering and predictive optimization | Not built yet — not on the current roadmap | — | ⬜ | stretch |
| 6.5 | Diagnose cluster start failures, library conflicts and out-of-memory errors | Not built yet — Free Edition is serverless-only (no custom clusters), so cluster-start failures may not apply; library conflicts or out-of-memory errors could still occur on a serverless job | — | ⬜ | stretch |

## 7. Governance and Security (15%)

| # | Official item (own words) | Skill in this repo | Evidence | Status | Plan tier |
|---|---|---|---|---|---|
| 7.1 | Managed versus external tables in UC: create, modify, delete, convert | Not shown — a managed Delta table is created and dropped, but no external table is created anywhere in this repo, and no ADR or GAPS row discusses choosing managed versus external tables, so the item's core (the managed-versus-external comparison) is not addressed | — | ⬜ | stretch |
| 7.2 | Access control with GRANT, REVOKE and DENY to users, groups and service principals, in the UI and SQL | partial: `GRANT USE CATALOG`/`USE SCHEMA`/`SELECT` to a group verified in SQL; no `REVOKE`, `DENY`, service principal or UI-based grant is shown ([concept note](concepts/7-governance-and-security/grants-row-filters-and-column-masks.md)) | [ADR 0002](adr/0002-group-grants-and-native-row-security.md), [GAPS G-06](GAPS.md) | ✅ | planned |
| 7.3 | Column masking and row-level security by user group | A row filter and a column mask were both created and confirmed enforced for a user group (a filtered-out row was excluded entirely; a masked column returned `REDACTED`) ([concept note](concepts/7-governance-and-security/grants-row-filters-and-column-masks.md)) | [ADR 0002](adr/0002-group-grants-and-native-row-security.md), [GAPS G-06](GAPS.md) | ✅ | planned |
| 7.4 | UC ABAC policies for central row filtering and column masking | Not built — ADR 0002 uses function-based row filters and column masks rather than attribute-based (ABAC) policies | [ADR 0002](adr/0002-group-grants-and-native-row-security.md) | ⬜ | stretch |
