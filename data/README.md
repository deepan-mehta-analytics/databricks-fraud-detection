# data/

Local, regenerable datasets. Contents are gitignored; only this README and
`.gitkeep` are tracked. Never commit the dataset file itself — see ADR 0006
and `docs/GAPS.md` G-04 for why, and `.gitignore`'s `/data/*` rule for how
it's kept out automatically.

## Source

[PaySim](https://www.kaggle.com/datasets/ealaxi/paysim1) — a mobile-money
transaction simulator (CC BY-SA 4.0). Supersedes the originally planned
Kaggle Credit Card Fraud dataset (see ADR 0004, superseded by ADR 0006).

Download it yourself from the link above (file name on Kaggle:
`PS_20174392719_1491204439457_log.csv`) and place it at `data/paysim.csv`
(gitignored automatically). Do not download it from the `mtalaltariq/
paysim-data` mirror — same content (cross-verified below, byte-identical
file size and matching row/fraud/checksum), but its Kaggle license field
literally says "Unknown"; the canonical `ealaxi/paysim1` source has a
confirmed CC BY-SA 4.0 license, so use it for anything citable or public.

## ⚠️ Do not use the balance columns as fraud-detection features

The dataset author states directly on the Kaggle page: "Transactions which
are detected as fraud are cancelled, so for fraud detection these columns
(`oldbalanceOrg`, `newbalanceOrig`, `oldbalanceDest`, `newbalanceDest`)
must not be used." Fraudulent transactions have their balances zeroed
*after* detection, so any feature derived from them (including balance
deltas like `orgDiff`/`newbalanceOrig - oldbalanceOrg`) leaks the label.
This overrides the balance-delta feature pattern from the Databricks
reference notebook cited in ADR 0006 — do not carry that pattern into
Phase 3/4 feature engineering.

## Verified stats (2026-09-22, from the real downloaded file)

- **Rows:** 6,362,620
- **Fraud (`isFraud=1`):** 8,213 (~0.129%)
- **Flagged-fraud (`isFlaggedFraud=1`):** 16
- **Step range:** 1–743 (~30-day simulation, 1 step = 1 hour)
- **File size:** 493,534,783 bytes (~493.5 MB)
- **MD5:** `e92a5f7447f43712f1dca473d0b0fa85` (matches the `mtalaltariq`
  mirror exactly — cross-verified 2026-09-22)
- **Columns:** `step, type, amount, nameOrig, oldbalanceOrg, newbalanceOrig,
  nameDest, oldbalanceDest, newbalanceDest, isFraud, isFlaggedFraud`
