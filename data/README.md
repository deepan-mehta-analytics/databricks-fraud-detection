# data/

Local, regenerable datasets. Contents are gitignored; only this README and
`.gitkeep` are tracked. Never commit the dataset file itself — see ADR 0006
and `docs/GAPS.md` G-04 for why, and `.gitignore`'s `/data/*` rule for how
it's kept out automatically.

## Source

[PaySim](https://www.kaggle.com/datasets/ealaxi/paysim1) — a mobile-money
transaction simulator (CC BY-SA 4.0). Supersedes the originally planned
Kaggle Credit Card Fraud dataset (see ADR 0004, superseded by ADR 0006).

Download it yourself from the link above and place it at `data/paysim.csv`
(gitignored automatically). Do not download it from the `mtalaltariq/
paysim-data` mirror — its license is unclear; use the canonical
`ealaxi/paysim1` source only.

## Verified stats (2026-09-22, from the real downloaded file)

- **Rows:** 6,362,620
- **Fraud (`isFraud=1`):** 8,213 (~0.129%)
- **Flagged-fraud (`isFlaggedFraud=1`):** 16
- **Step range:** 1–743 (~30-day simulation, 1 step = 1 hour)
- **File size:** 493,534,783 bytes (~493.5 MB)
- **Columns:** `step, type, amount, nameOrig, oldbalanceOrg, newbalanceOrig,
  nameDest, oldbalanceDest, newbalanceDest, isFraud, isFlaggedFraud`
