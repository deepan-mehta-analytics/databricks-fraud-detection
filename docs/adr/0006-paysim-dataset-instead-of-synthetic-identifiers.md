# ADR 0006: PaySim Dataset Instead of Synthetic Identifiers

## Status
Proposed. Supersedes [ADR 0004](0004-seeded-synthetic-identifiers.md). Not yet
accepted by the user. Row/fraud counts verified 2026-09-22 against the real
downloaded file (see Context).

## Context
ADR 0004 worked around a real gap (G-04): the originally chosen Kaggle
Credit Card Fraud dataset (`mlg-ulb/creditcardfraud`) has no card, merchant
or device key, only PCA-anonymized features. The workaround was to add
seeded synthetic ids, explicitly accepting that Phase 3 velocity features
would show "no real predictive value."

The user pointed to two Kaggle links and a public Databricks reference
notebook for evaluation. Read via a real scraper (Firecrawl, JS-rendered
content, not a title-only guess):

- **PaySim** (canonical source `kaggle.com/datasets/ealaxi/paysim1`,
  CC BY-SA 4.0; also mirrored at `mtalaltariq/paysim-data`, license unclear
  there — use the canonical source) is a mobile-money transaction simulator
  with native actor keys: `step, type, amount, nameOrig, oldbalanceOrg,
  newbalanceOrig, nameDest, oldbalanceDest, newbalanceDest, isFraud,
  isFlaggedFraud`. `nameOrig`/`nameDest` are exactly the missing key G-04
  identified — natively, not injected.
- The original brief's assumed Kafka schema (`transaction_id, card_id,
  amount, merchant_id, timestamp, device_id, merchant_category`) is a much
  closer shape to PaySim's real columns than to the PCA-anonymized dataset
  actually used — the brief was likely written with a PaySim-shaped dataset
  in mind.
- Databricks publishes a reference notebook ("Financial Fraud Detection
  using Decision Tree Machine Learning Models") built on PaySim, confirmed
  by reading its actual content. It is old (Community Edition, classic
  compute, batch only — no streaming, no Unity Catalog, not directly
  reusable for Phases 2–3), but its Phase-4-relevant patterns are real:
  `orgDiff`/`destDiff` balance-delta feature engineering, a
  `StringIndexer` → `VectorAssembler` → `DecisionTreeClassifier` pipeline,
  `CrossValidator` hyperparameter search, an unbalanced-vs-balanced
  training comparison, and MLflow logging calls. It also computes fraud via
  **hand-rolled business rules** instead of the dataset's own `isFraud`
  column — a pattern this ADR explicitly does not adopt (see Alternatives
  rejected).
- Row/fraud counts could not be trusted from the scrape: the extractor
  returned the same implausible figure (`6,353,307`) as both "row count"
  and "fraud count" across two different PaySim page reads, and a third
  read of the canonical page returned a different, also-unverified row
  count (`1,000,000`). None of those were reported as fact.
- **Verified 2026-09-22** by direct inspection of the real downloaded file
  (`wc -l` / `awk`, not a scraper): 6,362,620 rows, 8,213 fraud
  (`isFraud=1`, ~0.129%), 16 flagged-fraud (`isFlaggedFraud=1`), step range
  1–743 (~30-day simulation, 1 step = 1 hour). File size (493,534,783
  bytes) matches the earlier scraped figure exactly — it was specifically
  the row/fraud counts that were scraper noise, not the file size.

## Decision
- Adopt PaySim (`ealaxi/paysim1`) as the dataset driving the Kafka event
  schema and the Bronze/Silver/Gold pipeline, replacing the Kaggle Credit
  Card Fraud dataset and ADR 0004's synthetic-id workaround.
- Use PaySim's own `isFraud` column as the real fraud label. Do not adopt
  the reference notebook's rule-based labeling — using the dataset's actual
  label is both simpler and more honest for a portfolio project that
  otherwise insists on measured, not fabricated, results.
- Treat the reference notebook's Phase-4 patterns (balance-delta features,
  the classifier pipeline shape, cross-validation, MLflow logging) as
  inspiration to adapt, not code to copy — Databricks' public export states
  no explicit reuse license, and the pipeline needs rewriting for
  serverless/streaming anyway.
- Row and fraud counts have been verified by inspecting the downloaded file
  directly (same method already used to verify the original Kaggle dataset
  for G-04) — see Context.

## Consequences
**Positive:** removes the synthetic-id workaround entirely — no generator
component to build or test. Phase 3 velocity features become a real signal
instead of a demonstration-only one, since `nameOrig`/`nameDest` are real
transaction actors. A public, verified reference notebook exists for
Phase 4's ML approach.

**Negative:** PaySim is a *simulation* of mobile-money transactions, not
real anonymized transaction data like the previous dataset — the README's
"credit-card fraud" framing needs a wording pass (this is mobile-money/
P2P-transfer fraud, not card-present fraud) to stay honest; flagged here so
it isn't silently glossed over in the next README sweep. PaySim is
meaningfully larger than the previous dataset (documented as ~6.3M rows /
~493 MB vs. ~285K rows / ~151 MB) — this may interact with Free Edition's
still-unverified daily compute quota (G-08) more than the smaller dataset
would have; consider sampling for the streaming demo if quota pressure
appears during Phase 2 testing.

## Alternatives rejected
- **Keep ADR 0004's synthetic-id approach** — rejected; PaySim removes the
  need for it outright.
- **Use the `mtalaltariq/paysim-data` mirror directly** — rejected in favor
  of the canonical `ealaxi/paysim1` source, which has a clear, confirmed
  license (CC BY-SA 4.0) and traceable provenance.
- **Copy the reference notebook's rule-based fraud labeling** — rejected;
  PaySim's own `isFraud` column is the real label, and fabricating rules to
  approximate it would be circular and less honest.
- **Full ~6.3M-row PaySim file for every phase** — not yet decided; flagged
  as a Free Edition quota risk (G-08) to revisit once real Phase 2 quota
  usage is observed, not decided speculatively here.
