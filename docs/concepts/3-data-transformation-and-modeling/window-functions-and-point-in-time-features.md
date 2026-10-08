# Window Functions and Point-in-Time Features

**In plain words:** A window function computes a value for each row from a group of related rows, such as "payments to this account in the 24 hours before this one", without collapsing the rows the way `GROUP BY` does. A point-in-time feature uses only what was known *before* the moment being scored.

**Everyday analogy:** It's judging a footballer's form going into today's match from their last five games, without counting today's score.

**Why real teams use it:** Fraud models live on "how busy has this account been lately?" signals. If a feature accidentally includes the current or a later event (leakage), the model looks great in testing and fails in production. With a `RANGE` frame, the bounds are offsets from a single `ORDER BY` value, so `RANGE BETWEEN 24 PRECEDING AND 1 PRECEDING` means "the previous 24 units of time, excluding now" ([docs](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-syntax-window-functions-frame), checked 2026-10-08). `DISTINCT` aggregates are not allowed in window functions ([docs](https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-window-functions), checked 2026-10-08).

**How this repo uses it:** Seven features per payment, partitioned by the receiving account (the "mule" signal in PaySim) or by the sender, ordered by the hourly `step`. Every frame ends at `1 PRECEDING`, so payments in the same hour are never counted. Distinct senders use `size(collect_set(…))` because `COUNT(DISTINCT)` can't be used over a window, and the ratio uses `try_divide` so an empty history gives null instead of an error. See [the feature view](../../../pipelines/silver/04_transaction_features.sql).

**What was verified:** 2026-10-06, workspace run S4 (`14fa8b3`). For one receiver's 21 payments, the pipeline, a hand-written self-join and a local Python calculator gave identical values for all 7 features. CI also checks that every frame ends at `1 PRECEDING` ([GAPS §4](../../GAPS.md)).

**Key terms:** window function, `PARTITION BY`, `RANGE` vs `ROWS` frame, `PRECEDING`, leakage, point-in-time correctness.

**Go deeper:** private study notes (drills, diagrams, traps) live outside the public repo.
