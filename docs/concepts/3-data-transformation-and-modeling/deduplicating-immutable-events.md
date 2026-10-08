# Deduplicating Immutable Events

**In plain words:** When the same event arrives twice, for example because a file is re-sent, you keep one copy and drop the rest. If the event can never legitimately change (a payment that happened), a second copy with *different* content is not an update. It is a data problem to investigate.

**Everyday analogy:** The post office delivers the same letter twice, and you file one and bin the other. If the second "copy" has a different amount written on it, you don't swap it in; you put it aside and ask questions.

**Why real teams use it:** Upstream systems retry, so duplicates are normal. Counting them proves nothing was lost or double-counted. In SQL, `ROW_NUMBER()` over the ID, ordered by arrival, picks the first copy. In streaming, `dropDuplicatesWithinWatermark` keeps state and catches copies that arrive within the watermark delay ([docs](https://docs.databricks.com/aws/en/pyspark/reference/classes/dataframe/dropDuplicatesWithinWatermark), checked 2026-10-08).

**How this repo uses it:** Rows that pass the quality rules are ranked per `transaction_id` by `file_arrived_at`, then `ingested_at`, then `source_file`. The first copy is kept. A later copy whose content fingerprint (`sha2` over every source field) matches the first is dropped and counted as `duplicate_copy`. One that differs is rejected as `conflicting_duplicate`. There is no upsert path, because payments are immutable. See [the verdict view](../../../pipelines/silver/01_checked_transactions.sql) and [ADR 0008](../../adr/0008-silver-on-a-declarative-pipeline.md).

**What was verified:** 2026-10-06, workspace runs S2–S3 (`14fa8b3`). The 10 rows of a deliberately re-dropped file were removed and counted (`first_copy` showed 10 failures). Silver's `transaction_id` values are all unique, and the row accounting reconciled exactly ([GAPS §4](../../GAPS.md)).

**Key terms:** idempotency, `ROW_NUMBER()`, content hash, immutable event, watermark.

**Go deeper:** private study notes (drills, diagrams, traps) live outside the public repo.
