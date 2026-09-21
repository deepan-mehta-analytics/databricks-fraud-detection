# Cost Model

Only verified figures appear here. Anything unverified is marked `unverified`
and tracked in `docs/GAPS.md` (G-08, G-09). No total is quoted until G-08 is
settled.

---

## Verified inputs

| Item | Figure | Source | Fetched |
|---|---|---|---|
| Confluent trial credit | $400, expires 30 days after receipt or when spent, whichever is first | Confluent free-trial docs (via search summary) | 2026-09-21 |
| Confluent Basic: eCKU | First eCKU free, then $0.14 per eCKU-hour (USD) | Confluent pricing page | 2026-09-21 |
| Confluent Basic: ingress/egress | $0.05 per GB | Confluent pricing page | 2026-09-21 |
| Confluent Basic: storage | $0.08 per GB-month | Confluent pricing page | 2026-09-21 |

## Unverified inputs

| Item | Status |
|---|---|
| Free Edition numeric quotas (daily compute quota, model-serving endpoint count) | unverified; feature-level limits are verified, see G-08 |
| Whether a Confluent Basic cluster can be paused, and trial reactivation terms | unverified, see G-07 |
| Total monthly cost (the brief's ₹0–400 claim) | unverified, see G-09 |

---

## Teardown log

Cost-bearing resources are torn down after every working window. Record each
teardown here, with no cluster IDs or account identifiers (this repo is public).

| Date | Resource | Action | Confirmed by |
|---|---|---|---|
| — | — | — | — |
