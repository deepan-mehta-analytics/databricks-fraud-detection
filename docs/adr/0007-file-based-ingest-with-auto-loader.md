# ADR 0007: File-Based Ingest with Auto Loader

## Status
Proposed (2026-09-24). Supersedes [ADR 0005](0005-bounded-confluent-windows.md)
and the Bronze-ingest half of [ADR 0003](0003-streaming-trigger-model-on-serverless.md).
ADR 0003's trigger decision (`Trigger.AvailableNow` on serverless) still stands
and is used here.

## Context
The brief assumed transaction events would arrive from Kafka on Confluent
Cloud. On Databricks Free Edition, outbound internet access from serverless
compute is limited to a set of trusted domains unless the account completes an
identity verification step that this project will not use. So a connection
to an external Kafka broker is not expected to work (`docs/GAPS.md` G-01).
Ingest needs a source that lives entirely inside the workspace.

Other constraints:
- Serverless supports only `Trigger.AvailableNow` or Lakeflow pipelines (G-02).
- Checkpoints on a Unity Catalog Volume are verified to work (ADR 0001).
- Free Edition allows one active Lakeflow pipeline per type (G-08).
- PaySim is not uniform over time. Legitimate volume collapses after simulated
  day 17 while fraud stays at ~250 per day, so a late train/score cut would
  compare a 0.1% fraud rate with a 1.5% one (G-10).

## Decision
Replay PaySim as files and ingest them with Auto Loader.

- **Producer:** a one-time Databricks job splits the CSV into one JSON Lines
  file per simulated hour (`step`), in an "outbox" Volume. A release task
  copies the next steps into a landing Volume on each run. No personal access
  token, laptop, or outbound network is involved.
- **One stream, two stages:** the first ingest run loads the backfill
  (days 1–14, steps 1–336: 4,784,775 rows, 3,767 fraud). Later runs pick up
  only newly released files from the live replay (days 15–17, steps 337–408:
  1,202,642 rows, 822 fraud), 6 steps per run by default. Days 18–31 are held
  back as a labelled drift scenario for monitoring, never as scoring data.
- **Consumer:** a Databricks Job with a release task, then an ingest task.
  Auto Loader reads JSON Lines with `Trigger.AvailableNow` into a Bronze Delta
  table. The checkpoint and schema location live on a Volume. A schedule is
  defined but paused, because the daily compute quota is unconfirmed.
- **Record contract:** plain-language field names. A deterministic
  `transaction_id` is stamped by the producer, since PaySim has none. There
  are three time columns: `transaction_time` (hourly, from `step`, synthetic
  anchor date), `file_arrived_at` and `ingested_at`. Key fields get typed
  schema hints so bad values land in `_rescued_data` instead of failing the
  stream.
- **Staged problems:** opt-in release flags re-drop a duplicate file, hold a
  file back and release it late, add a new field mid-replay (schema
  evolution), and inject malformed values. Each has a documented, checkable
  proof.
- **Label:** `fraud_label` stays in the record, as in PaySim. Scoring reads
  through a view that excludes it. A separate delayed-label feed is a roadmap
  item.

## Consequences
**Positive:**
- Works on Free Edition as it is.
- Exercises Auto Loader's core features directly: incremental file
  discovery, checkpoints, schema inference, hints and evolution, and rescued
  data.
- Gives a time-based train/score split with matched fraud rates (0.079% vs.
  0.068%), avoiding temporal leakage.
- Every staged problem is reproducible and verifiable.

**Negative:**
- Not a real message bus. Latency is bounded below by the job schedule, and
  no sub-second figure is claimed.
- A new column makes the ingest run fail once, by Auto Loader's design, and
  recover on an automatic retry.
- The event timestamps are synthetic. Only `ingested_at − file_arrived_at`
  (pipeline lag) is a meaningful time measurement.

**Checked in real runs (2026-09-24, see `docs/GAPS.md`):**
- Asset Bundles deploy on Free Edition from the workspace UI, with no CLI or
  token (G-11).
- A completely invalid JSON line becomes one all-null row, with
  `_rescued_data` null too, and the run succeeds (GAPS §3, V5). Silver must
  filter such rows.
- The backfill (4,784,775 rows, 4m 22s) and the rest of the scenario runs
  fitted within one day's quota (G-08; the numeric quota is still unknown).
- The new-column fail-then-retry behaved as designed on the schema-change
  run.

## Alternatives rejected
- **Kafka on Confluent Cloud (ADR 0005)** — blocked by the outbound-network
  limit (G-01).
- **Laptop uploader via CLI/SDK** — needs a personal access token and a
  running laptop.
- **CSV or Parquet landing files** — CSV gives a weaker schema-evolution
  story and isn't event-shaped. Parquet is an analytics format with little
  for inference or rescued data to show.
- **Lakeflow pipeline for Bronze** — it hides the checkpoint mechanics, and
  its single active slot is reserved for Silver. A continuous pipeline also
  burns compute between scheduled file drops.
- **Cut at step 600** — a 15× fraud-rate shift between training and scoring
  (G-10).
- **Row-content hash as ID** — silently merges genuinely identical
  transactions.
