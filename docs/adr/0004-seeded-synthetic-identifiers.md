# ADR 0004: Seeded Synthetic Identifiers for the Event Schema

## Status
Superseded by [ADR 0006](0006-paysim-dataset-instead-of-synthetic-identifiers.md) (2026-09-22).
PaySim has real transaction actor keys natively, removing the need for the
synthetic-id workaround this ADR describes. Kept for the record of why the
original approach was chosen and what it would have cost.

## Context
The brief drives the Kafka event schema from the Kaggle Credit Card Fraud
dataset. Per the OpenML mirror, the data has `V1`–`V28` (PCA components),
`Time`, `Amount` and `Class`: 284,807 rows with 492 frauds (about 0.17%). It
has no card, merchant or device key (gap G-04, `docs/GAPS.md`), so per-card
velocity features in Phase 3 cannot be computed from the real data.

## Decision
- Add seeded synthetic `synthetic_card_id`, `synthetic_merchant_id` and
  `synthetic_device_id` columns, with the seed recorded in the generator so
  runs are reproducible. The `synthetic_` prefix keeps provenance visible in
  every table.
- Assign the ids independently of `Class`. No fraud pattern is injected
  through them.
- Leave `V1`–`V28`, `Time`, `Amount` and `Class` untouched.
- Report velocity features as a demonstration of pipeline mechanics, not as
  a fraud signal. Model metrics (G-05) come from a real training run and are
  described as based on the real columns only.

## Consequences
**Positive:** Phase 3 windowed aggregation can be built and tested, and no
result is inflated by label leakage through the synthetic keys.
**Negative:** velocity features will show no real predictive value, and the
README must say so plainly. The Kaggle licence and CSV parity with the
OpenML mirror are still unverified.

## Alternatives rejected
- **Use only the real columns** — rejected; drops the velocity-feature phase,
  which is a core streaming demonstration.
- **Inject synthetic fraud rings tied to `Class`** — rejected; circular, and
  it would inflate any metric computed on those features.
- **Find another dataset with card keys** — not researched; possible future
  work if the synthetic approach proves inadequate.
