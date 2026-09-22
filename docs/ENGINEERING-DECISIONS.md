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
**Still open:** whether groups, row filters and column masks all run on
Free Edition — verification spike planned before Phase 5.
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
**Still open:** the ingest half of this decision depends on G-01 (whether
Free Edition serverless can reach Confluent Cloud at all).
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

## ADR 0005 — Bounded Confluent windows

**Brief assumed:** free Confluent credits comfortably cover a multi-month
build.
**We found:** the trial is $400 and expires 30 days after receipt or when
spent, whichever is first; the payment method is charged after
(`docs/GAPS.md` G-07).
**We decided:** don't sign up until the G-01 connection test is actually
ready to run, work in bounded windows, delete the cluster after each one,
log every teardown in `docs/cost-model.md` with no identifiers.
**Still open:** whether a Basic cluster can be paused, and the reactivation
terms.
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
notebook built on PaySim was also confirmed readable and has reusable
Phase-4 patterns (balance-delta features, a classifier pipeline, MLflow
logging) — though it computes fraud via hand-rolled rules instead of
PaySim's own `isFraud` label, a pattern this project does not copy.
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
**Still open:** exact row/fraud counts need verification from the real
downloaded file — an automated read returned inconsistent numbers, so none
were reported as fact.
→ [ADR 0006](adr/0006-paysim-dataset-instead-of-synthetic-identifiers.md)

---

## Reading this alongside the code

Every decision above is `Proposed`, not yet `Accepted` — that flip happens
only on the user's explicit review, tracked in the project's own working
notes (not part of this public repo). Treat "Proposed" as "this is the
current plan, backed by evidence," not "this is undecided."
