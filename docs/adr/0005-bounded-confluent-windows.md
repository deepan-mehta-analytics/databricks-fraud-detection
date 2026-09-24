# ADR 0005: Bounded Confluent Windows with Teardown

## Status
Superseded by [ADR 0007](0007-file-based-ingest-with-auto-loader.md)
(2026-09-24). Kafka on Confluent Cloud is blocked by Free Edition's
outbound-network limit (G-01), so no Confluent account or cluster will be
created. Kept for the record of the cost analysis and teardown discipline,
which apply again if Kafka ever becomes reachable.

## Context
The brief assumed free Confluent credits cover a multi-month build. Current
documentation says the trial is $400 and expires 30 days after receipt or
when spent, whichever comes first, and that the payment method is charged
after the trial ends (gap G-07, `docs/GAPS.md`). Basic-tier pricing on the
pricing page: first eCKU free, then $0.14 per eCKU-hour; $0.05 per GB
ingress and egress; $0.08 per GB-month storage (USD). Whether a Basic cluster
can be paused, and the reactivation terms, are unverified.

## Decision
- Do not sign up, or create a cluster, until the G-01 connection test is
  ready to run, so the 30-day clock does not start early.
- Run the cluster only inside bounded working windows and delete it after
  each one. Record every teardown in `docs/cost-model.md` without cluster or
  account identifiers.
- The user creates and deletes the cluster, topics and API keys, per the
  project guardrails. Claude hands over the exact commands.
- Do not report a cost figure until it is measured from a real window.

## Consequences
**Positive:** exposure is capped at the trial credit and at the windows
actually used; the repo stays public-safe.
**Negative:** each window recreates the cluster, topic and keys, and the
demo cannot be a permanently running service. If Basic clusters cannot be
paused, deletion is the only way to stop billing.

## Alternatives rejected
- **Leave the cluster running** — rejected; risks charges once the credit
  is spent or expires.
- **Paid pay-as-you-go continuous use** — rejected; outside the near-free
  goal, and no total has been costed (G-09).
- **File-based source through Auto Loader instead of Kafka** — not designed;
  it is the fallback to evaluate if G-01 shows Confluent is unreachable from
  Free Edition.
