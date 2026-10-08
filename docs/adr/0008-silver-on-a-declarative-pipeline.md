# ADR 0008: Silver on a Declarative Pipeline

## Status
Proposed (2026-10-08). Builds on [ADR 0007](0007-file-based-ingest-with-auto-loader.md):
Bronze is unchanged, and Silver reads it.

## Context
Bronze holds every replayed PaySim row exactly as it arrived: 5,987,427 rows,
including 10 identical copies of a re-dropped file and 5 rows with malformed
amounts that went to `_rescued_data`. Phase 4 needs a clean table of payments
plus warning-sign features, built without leaking the future into the past.

Measured on `data/paysim.csv`, steps 1–408 (2026-10-06):
- Senders almost never repeat: 8,279 of 5,979,126 senders appear more than
  once. Receivers do: 432,585 of 2,554,521 receive more than one payment, and
  3,877 of the 4,563 receivers of fraud receive more than one. So the signal
  is on the receiving account (the "mule" pattern), not the sender.
- All fraud is TRANSFER (2,285) or CASH_OUT (2,304).
- 4 rows have a zero amount, all fraud, so a "positive amount" rule would
  throw away real fraud.
- Time moves in whole hours (`step`), so "same hour" needs a defined rule.

Constraints:
- Free Edition is serverless-only and allows one active pipeline per type
  (G-08). A triggered pipeline is active only while it runs.
- Incremental refresh of materialized views is serverless-only. Window
  functions need `PARTITION BY`, and Databricks may still choose a full
  recompute after its own cost analysis (incremental-refresh docs, read
  2026-10-06, re-checked 2026-10-08).

## Decision
A Lakeflow declarative pipeline (`fraud-silver`, SQL, serverless, triggered)
runs as a `pipeline` task after `ingest` in the same job. It holds four
materialized views:

1. **`silver_checked_transactions`** (PRIVATE, not published to the catalog).
   Every Bronze row plus a `verdict`: the first of 8 rules it breaks, or `ok`.
   Copies of the same `transaction_id` are then ranked by arrival. Later
   copies with identical content become `duplicate_copy`, and copies with
   different content become `conflicting_duplicate`. Nine warn-only
   expectations count each rule's failures on the Data quality tab.
2. **`silver_transactions`**: verdict `ok`, a fixed column list (no synthetic
   `channel`, no label-leaking balances, ADR 0006), and three `FAIL UPDATE`
   guards so that a bug in the split fails the run loudly.
3. **`silver_rejected_transactions`**: the shelf of rows that broke a rule,
   with a `rejection_reason` and every raw column kept as evidence. Identical
   copies are counted, not shelved.
4. **`silver_transaction_features`**: 6 receiver features and 1 sender
   feature, from window frames that all end at `1 PRECEDING`. A payment in
   hour N sees hours before N only, never its own hour.

The row accounting must reconcile: Bronze = clean + rejected + identical
copies removed.

## Consequences
**Positive:**
- No hand-written incremental logic. A late file corrects the affected
  features on the next refresh, because a materialized view is always correct
  for the data present at its update.
- The quality rules are visible per run on the Data quality tab, and the
  rejected rows stay queryable with their reason.
- The receiver features carry a real signal on this dataset, and they use the
  past only.

**Negative:**
- At bank scale, Silver would be streaming tables with stateful dedup, and the
  features would sit in a feature store with millisecond online lookups.
  Materialized views fit 6M rows and the hourly replay (G-02).
- The private verdict view is still stored for the pipeline's lifetime, a
  third copy of the data. It is only kept out of the catalog.
- CI checks the SQL's structure (names, frames, columns), not its logic. The
  logic is proven by the workspace runs against a local calculator.
- After a Bronze reset, Silver needs a manual "Full refresh all", because the
  job task runs without a full refresh.
- Hours 1–24 have only partial history (warm-up). Phase 4 decides whether to
  drop them from training.

**Checked in real runs (2026-10-06/07, see `docs/GAPS.md` and the README
Results):**
- S2: 5,987,427 Bronze = 5,987,412 clean + 5 rejected (`bad_amount`) + 10
  identical copies. Silver fraud 4,589. Every count equals the local
  calculator's.
- S3: the Data quality tab showed `amount_valid` 5, `fully_parsed` 5 and
  `first_copy` 10 failures, and 0 for the others.
- S4: one receiver's 21 feature rows were identical across the pipeline, a
  hand-written self-join and the local calculator.
- S5: a file held back and released late changed a later payment's features
  from "no history" to the complete-data values.
- S6: the first build was a full recompute (the event log said
  `COMPLETE_RECOMPUTE`; the docs page lists the name as `FULL_RECOMPUTE`).
  The two later updates ran incrementally: `WINDOW_FUNCTION` for the verdict
  and feature views, `APPEND_ONLY` for the clean and rejected views. So
  materialized views with expectations did refresh incrementally here. Update
  wall time was 105 s (full), 115 s and 107 s (incremental). At this size,
  fixed pipeline overhead dominates, and incremental refresh did not shorten
  the run.

## Alternatives rejected
- **A hand-written Spark job (MERGE plus checkpoints)**: more code to get
  late-data correction right, and it skips the platform's own quality
  metrics.
- **A hybrid (streaming table for the clean data, a separate job for the
  features)**: two engines to reason about, for no gain at this size. This
  stays the recorded fallback if a full recompute ever becomes too costly.
- **Upsert or row versioning for duplicates**: payments are immutable events.
  A changed copy is a data problem to shelve, not a newer version to keep.
- **A watermark grace period for late files**: rows arriving after the
  watermark would be dropped silently, while materialized views recompute
  correctly instead.
- **Counting payments from the same hour**: with hourly steps, the same-hour
  rows include payments that happened after the current one, which leaks the
  future.
- **`COUNT(DISTINCT …)` over a window**: not supported in window functions
  (`DISTINCT_WINDOW_FUNCTION_UNSUPPORTED`), so distinct senders use
  `size(collect_set(…))`.
