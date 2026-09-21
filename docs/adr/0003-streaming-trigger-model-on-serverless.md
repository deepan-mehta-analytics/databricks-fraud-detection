# ADR 0003: Streaming Trigger Model on Serverless Compute

## Status
Proposed. The Bronze ingest half depends on the G-01 connection test, which
needs live accounts.

## Context
The brief targeted Structured Streaming "Real-Time Mode". Current
documentation says real-time mode requires classic compute (Runtime 16.4 LTS
or later, autoscaling, Photon and spot instances off) and that "Lakeflow
pipelines and serverless clusters are not supported". Free Edition is
serverless-only with no custom compute, so real-time mode is unavailable
there (gap G-02; the last step is inferred from two pages). On serverless,
only `Trigger.AvailableNow` is supported in notebooks and jobs, plus Lakeflow
pipelines in continuous mode; `ProcessingTime` and `Continuous` triggers are
unsupported. Free Edition also allows at most five concurrent job tasks and
one active Lakeflow pipeline per pipeline type (G-08).

## Decision
Build the baseline as scheduled Databricks Jobs using `Trigger.AvailableNow`
for Bronze and Silver, with checkpoints per ADR 0001. Evaluate a continuous
Lakeflow pipeline as the always-on alternative. The choice between them is
finalised after the G-01 test shows whether serverless can read from
Confluent at all. Latency is reported as the measured schedule interval plus
run time. No sub-second or millisecond figure is claimed.

## Consequences
**Positive:** works on the free tier, and exercises Structured Streaming
checkpointing and incremental processing directly.
**Negative:** end-to-end latency is bounded below by the job schedule, so the
project cannot demonstrate ultra-low-latency scoring. If G-01 shows Kafka is
unreachable from serverless, the ingest source needs a different design,
which would supersede this ADR.

## Alternatives rejected
- **Real-time mode** — rejected; needs classic compute, unavailable on Free
  Edition.
- **`ProcessingTime` or `Continuous` triggers** — rejected; unsupported on
  serverless notebooks and jobs.
- **Classic compute** — rejected for the free tier; Free Edition does not
  support custom compute. Paid alternatives were not costed.
