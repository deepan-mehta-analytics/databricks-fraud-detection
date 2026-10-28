# Engineering Decisions

The original brief (`docs/00-initial-brief.md`) was an AI-generated starting
draft, not a verified spec. This page is the narrative thread tying it
together: what the brief assumed, what checking it against current docs (or
a real run) actually found, and what we decided instead. The full evidence
lives in `docs/GAPS.md` (the brief-versus-reality register) and the formal
ADRs in `docs/adr/` — this page is the readable summary that connects them.

---

## ADR 0001 — Streaming checkpoints

**Brief assumed:** checkpoints on DBFS.
**We found:** DBFS root and mounts are deprecated; new Databricks accounts
don't get access to them (`docs/GAPS.md` G-03).
**We decided:** Unity Catalog Volumes instead, path supplied via
`UC_CHECKPOINT_VOLUME` so nothing workspace-specific is committed.
**Verified 2026-09-22:** a real serverless notebook run wrote and read a
Structured Streaming checkpoint on a UC Volume. Confirmed working.
→ [ADR 0001](adr/0001-checkpoints-on-unity-catalog-volumes.md)

---

## ADR 0002 — Governance: grants and row/column security

**Brief assumed:** `GRANT ... TO ROLE business_users` and row-level security
via dynamic views.
**We found:** Unity Catalog grants target users, service principals and
groups — not a `role` principal type, which isn't documented at all
(`docs/GAPS.md` G-06). Row filters and column masks are the native
mechanisms; dynamic views are still supported but positioned for curated or
joined views, not as the primary row-security tool.
**We decided:** grant to groups, use row filters and column masks on Gold
tables, reserve dynamic views for genuinely curated views.
**Verified 2026-09-22:** a grant to the built-in `account users` group, a
row filter and a column mask all ran on Free Edition and were enforced (a
filtered-out row disappeared; the masked column showed `REDACTED`).
**Still open:** whether a *new* custom group can be created on Free Edition.
→ [ADR 0002](adr/0002-group-grants-and-native-row-security.md)

---

## ADR 0003 — Streaming trigger model

**Brief assumed:** Structured Streaming "Real-Time Mode" on serverless
compute.
**We found:** Real-Time Mode needs classic compute (Runtime 16.4 LTS+);
"Lakeflow pipelines and serverless clusters are not supported"
(`docs/GAPS.md` G-02). Free Edition is serverless-only, so Real-Time Mode
is unavailable there. Serverless streaming supports only
`Trigger.AvailableNow` (notebooks/jobs) and Lakeflow pipelines in
continuous mode.
**We decided:** scheduled `Trigger.AvailableNow` jobs as the baseline,
with a continuous Lakeflow pipeline evaluated as the always-on alternative.
Latency is reported as the measured schedule interval plus run time — no
sub-second claim.
**Update 2026-09-24:** the ingest half (Kafka as source) is superseded by
ADR 0007; the `AvailableNow` trigger decision stands.
→ [ADR 0003](adr/0003-streaming-trigger-model-on-serverless.md)

---

## ADR 0004 — Superseded — synthetic identifiers

**Brief assumed:** the Kaggle Credit Card Fraud dataset drives the Kafka
event schema.
**We found:** that dataset has only PCA-anonymized features (`V1`–`V28`),
`Time`, `Amount` and `Class` — no card, merchant or device key
(`docs/GAPS.md` G-04).
**We originally decided:** add seeded synthetic ids so Phase 3 velocity
features could still be built and tested, explicitly accepting they'd show
"no real predictive value."
**Superseded 2026-09-22** by ADR 0006 — see below. Kept for the record.
→ [ADR 0004](adr/0004-seeded-synthetic-identifiers.md)

---

## ADR 0005 — Superseded — bounded Confluent windows

**Brief assumed:** free Confluent credits comfortably cover a multi-month
build.
**We found:** the trial is $400 and expires 30 days after receipt or when
spent, whichever is first; the payment method is charged after
(`docs/GAPS.md` G-07).
**We decided:** don't sign up until the G-01 connection test is actually
ready to run, work in bounded windows, delete the cluster after each one,
log every teardown in `docs/cost-model.md` with no identifiers.
**Superseded 2026-09-24** by ADR 0007 — Free Edition can't reach an
external Kafka broker (G-01), so no Confluent account is created. Kept for
the record.
→ [ADR 0005](adr/0005-bounded-confluent-windows.md)

---

## ADR 0006 — Dataset switched to PaySim

**Prompted by:** the user supplying two Kaggle dataset links and a
Databricks reference notebook for evaluation (2026-09-22), not a gap found
during routine research.
**We found:** PaySim (`kaggle.com/datasets/ealaxi/paysim1`, CC BY-SA 4.0)
is a mobile-money transaction simulator with real transaction actor keys
(`nameOrig`, `nameDest`) — exactly what ADR 0004 had to work around with
synthetic ids. The brief's originally assumed Kafka schema (`card_id`,
`merchant_id`, `device_id`) is actually a much closer shape to PaySim than
to the PCA-anonymized dataset it was paired with — the brief was likely
written with a PaySim-shaped dataset in mind. A public Databricks reference
notebook built on PaySim was also confirmed readable and has some reusable
Phase-4 patterns (a classifier pipeline, cross-validation, MLflow logging)
— though it computes fraud via hand-rolled rules instead of PaySim's own
`isFraud` label, a pattern this project does not copy.
**We decided:** switch to PaySim, use its native `isFraud` label as ground
truth, retire the synthetic-id workaround entirely. This also upgrades
Phase 3's velocity features from demonstration-only to a real signal, since
the account keys are genuine.
**Trade-off, stated plainly:** PaySim is a *simulation*, not real
anonymized transaction data like the previous dataset — the README's
framing moved from "credit-card fraud" to "mobile-money fraud" to stay
honest about what the data actually is. PaySim is also considerably larger
(~6.3M rows vs. ~285K), which may interact with Free Edition's
still-unverified daily compute quota (G-08).
**Verified 2026-09-22:** row/fraud counts confirmed from the real
downloaded file — 6,362,620 rows, 8,213 fraud (~0.129%). A first download
came from an unlicensed Kaggle mirror; caught, cross-verified as content-
identical to the canonical CC BY-SA 4.0 source, and corrected before
committing. Separately, the reference notebook's balance-delta features
turned out to be **label leakage** — the dataset author's own
documentation says those columns must not be used for fraud detection,
since fraud transactions have their balances zeroed after detection. That
pattern is explicitly rejected, not adopted.
**Found later (2026-09-24):** PaySim isn't uniform over time. Fraud stays at
~250 per simulated day, but normal volume collapses after day 17, so any
train/score split has to cut inside days 1–17 (G-10).
→ [ADR 0006](adr/0006-paysim-dataset-instead-of-synthetic-identifiers.md)

---

## ADR 0007 — File-based ingest with Auto Loader

**Brief assumed:** transaction events stream in from Kafka on Confluent
Cloud.
**We found:** Free Edition limits outbound internet to trusted domains
unless an identity-verification step is completed, which this project won't
use, so an external Kafka broker isn't reachable (G-01). Separately, a
per-day count of PaySim showed normal volume collapsing after simulated day
17 (G-10).
**We decided:** replay PaySim as JSON Lines files, one per simulated hour,
and ingest them with Auto Loader in a single stream. Days 1–14 are loaded
first as history; days 15–17 are released a few hours at a time as "live"
data; days 18–31 are held back as a drift test for monitoring. The producer
adds a deterministic `transaction_id` and plain-language time columns. Four
opt-in flags stage real-world problems on purpose: a duplicate file, a late
file, a new field mid-stream, and malformed values.
**Trade-off, stated plainly:** this isn't a real message bus. Latency is
bounded by the job schedule, and event timestamps are synthetic, so only
pipeline lag is reported as a time measurement.
**Still open:** Asset Bundle deploy on Free Edition (G-11), invalid-JSON-line
behaviour, and whether the backfill run fits the daily quota (G-08).
→ [ADR 0007](adr/0007-file-based-ingest-with-auto-loader.md)

---

## ADR 0008 — Silver on a declarative pipeline

**Brief assumed:** a Silver layer that "cleans and enriches" the stream,
without saying how bad rows, duplicates, late data or feature timing are
handled.
**We found:** in PaySim, senders almost never repeat, but receivers do: 3,877
of the 4,563 accounts that receive fraud receive more than one payment. So
the warning signs belong on the receiving account. Four zero-amount payments
are all fraud, so a "positive amount" rule would discard real fraud. Time
moves in whole hours, so "same hour" needs an explicit rule.
**We decided:** a Lakeflow declarative pipeline of four materialized views,
run as a job task after ingest. A private view gives every Bronze row a
verdict, counted by warn-only expectations. The verdict splits the rows into
a clean table (with fail-loud guards) and a rejected shelf that keeps the
reason and the raw evidence. Identical copies are dropped and counted. Six
receiver features and one sender feature use earlier hours only. Payments
are immutable, so there is no upsert path.
**Trade-off, stated plainly:** at bank scale this would be streaming tables
plus a feature store. Materialized views fit 6M rows, and they correct late
data on their own. CI checks the SQL's structure, not its logic. The logic
was proven in the workspace against a local calculator.
**Verified 2026-10-06/07:** the row accounting reconciled exactly (5,987,412
clean + 5 rejected + 10 copies = 5,987,427). One receiver's features matched
three ways. A late file corrected a later payment's features. After the first
full build, updates ran incrementally, even with expectations in place, though
fixed overhead kept each update at about 2 minutes.
→ [ADR 0008](adr/0008-silver-on-a-declarative-pipeline.md)

---

## ADR 0009 — Batch scoring with MLflow and Unity Catalog

**Brief assumed:** a RandomForest classifier with fixed headline metrics, a
Spark UDF scoring the stream in flight, alerts above a 0.85 probability
cut-off, and a daily retrain at 2 AM IST.
**We found:** Free Edition can't host online feature lookups, and on
serverless, Spark ML runs through Spark Connect with a 100 MB model cap. Fraud
is about 0.1% of payments, and it only ever appears in TRANSFER and CASH_OUT
payments. A replay delivers no new labels, so a nightly retrain would have
nothing new to learn. Sampled scores aren't calibrated probabilities, so a
fixed cut-off doesn't size the review workload.
**We decided:** gradient-boosted trees in scikit-learn, trained on demand on a
sample and picked over a logistic baseline on a time-based comparison window.
They're registered in Unity Catalog with `@challenger` / `@champion` aliases
and an explicit promotion step. A `score` task after Silver scores each new
payment in pandas chunks through the same feature builder as training. It
appends to a decision log that keeps the features as the model saw them.
Alerts are the top 50 per simulated hour. A label-delay setting measures what
late fraud labels cost.
**Trade-off, stated plainly:** no real-time scoring, a manual promotion
instead of a CI gate, and scores that rank payments rather than give
probabilities. MLflow isn't pinned (job tasks got 3.8.1, training 3.12.0);
scikit-learn is.
**Verified 2026-10-08 to 2026-10-11:** on hours 337–408 (822 fraud), the
champion caught 405 at 50 alerts per hour (recall 0.493, PR-AUC 0.346),
against 367 for logistic and 352 for "largest amount first". Training with no
label delay caught 406 (PR-AUC 0.379). The first scoring run logged 1,205,673
payments once each, a rerun added none, and after a promotion the next hour's
6 payments carried the new version.
→ [ADR 0009](adr/0009-batch-scoring-with-mlflow-and-unity-catalog.md)

---

## ADR 0010 — Gold alert log and case table

**Brief assumed:** a single Gold table,
`fraud_alerts(transaction_id, fraud_score, risk_level, timestamp)`, filled
with every payment above a score cut-off, in its own schema per layer.
**We found:** a fraud team works to a fixed review budget, so a cut-off makes
the queue swing with traffic. An alert must not change after it is handed out,
and late files can add payments to an hour that was already alerted. Real
verdicts arrive days later, and they are a different kind of record (where an
investigation stands) from the alert itself (what was flagged).
**We decided:** an append-only log, `fraud_alerts`, holding the top 50 per
simulated hour (ties go to the smaller ID), with a late-payment rule. A case
table, `alert_cases`, opens one case per alert and closes it 72 simulated hours
later with a verdict taken from the label (simulated reviewers). A plain view
gives managers per-hour totals. All of it is one SQL file task, `gold`, after
`score`, in the existing `workspace.fraud` schema.
**Trade-off, stated plainly:** the verdicts are simulated, Gold runs per job
run rather than per payment, and a truly late payment can't occur in an hourly
replay, so that rule is proven by tests only.
**Verified 2026-10-12 and 2026-10-13:** 3,154 alerts over 82 hours and 262
closed cases, exactly as the local calculator predicted, with 0 missing or
extra alerts and every verdict matching the label. A rerun wrote 0 rows. A
held-back hour released late got 50 fresh alerts, and the totals moved to
3,268 alerts and 412 closed, again matching the calculator.
→ [ADR 0010](adr/0010-gold-alert-log-and-case-table.md)

---

## ADR 0011 — Governance with groups, masks, a tag policy, and an external export

**Brief assumed:** `GRANT … TO ROLE` statements, dynamic views for personal
data, and card or device IDs to protect.
**We found:** grants go to groups, users or service principals; `role` isn't
a principal type (G-06). PaySim's identifiers are account names, not cards.
Free Edition can create custom groups and invite a second user (verified
2026-10-11), and it has the Governed Tags screen that tag-based policies need.
It can't reach Cloudflare R2 (G-18), the same network limit that blocks
Kafka.
**We decided:** three groups (engineers, reviewers, managers). Engineers get a
schema-wide grant, the other two get grants table by table. A row filter shows
managers closed cases only, and a column mask shows them `REDACTED` for account
names. Both functions exempt engineers, and the Gold SQL refuses to run as
anyone outside that group. A tag-based policy was probed on a scratch table.
The R2 export is kept in `sql/` as a documented design, not wired into the job.
**Trade-off, stated plainly:** one person plays every role with one test
user, the job runs as the owner rather than a service principal, the live
tables keep per-table masks, and no external table exists.
**Verified 2026-10-11 and 2026-10-12:** the test user was refused at the
schema with no group. In `fraud_managers` they saw 262 closed cases with every
name `REDACTED`, while the owner saw all 3,154 with none. `REVOKE` cut access
on the next query and `GRANT` restored it. The tag policy masked all 5 scratch
rows for the test user and none for the owner.
→ [ADR 0011](adr/0011-governance-groups-masks-and-external-export.md)

---

## ADR 0012 — Monitoring with views, two AI/BI dashboards, and system tables

**Brief assumed:** a Streamlit app showing a 95th-percentile per-payment
latency, plus a nightly 2 AM retrain.
**We found:** scoring is batch, so per-payment latency has no meaning; the
useful number is how long a payment waited from landing to scored in the
latest run. The retrain was already rejected (ADR 0009). Free Edition exposes
`system.lakeflow`, but its duration columns are 0, so minutes must come from
period start and end times. An app works on Free Edition but would use one of
3 app slots and re-implement the per-viewer security that dashboards get for
free.
**We decided:** plain views rebuilt and re-granted by a `monitor` task; two
AI/BI dashboards per audience (Fraud operations for all three groups, Platform
health for engineers) running with viewer credentials; two dashboard refresh
tasks; job history from `system.lakeflow` matched by name. Both dashboards
are generated from Python, share one theme and meaning colours, and support
sliders, cross-filtering and drill-through.
**Trade-off, stated plainly:** no live auto-refresh, job rows up to an hour
late, no single-payment drill-down, and the refresh tasks only refresh the
owner's cached view.
**Verified 2026-10-15 to 2026-10-28:** run E took 17 min 9 s with all 8 tasks
green; the dashboards showed 405 confirmed fraud of 2,916 checked and 822 in
all, matching the local calculator; a manager saw 0 open cases and was refused
Platform health; every restyle check (D11–D17) passed.
→ [ADR 0012](adr/0012-monitoring-dashboards-and-views.md)

---

## Reading this alongside the code

Every decision above is `Proposed`, not yet `Accepted` — that flip happens
only on the user's explicit review, tracked in the project's own working
notes (not part of this public repo). Treat "Proposed" as "this is the
current plan, backed by evidence," not "this is undecided."
