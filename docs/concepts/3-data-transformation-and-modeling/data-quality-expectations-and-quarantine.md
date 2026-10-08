# Data Quality: Expectations and Quarantine

**In plain words:** An expectation is a named rule on a pipeline dataset, such as "amount is not negative". Each run counts how many rows break it. The rule can just warn and keep the row, drop the row, or fail the whole update. Quarantine means sending the rows that break a rule to their own table instead of losing them.

**Everyday analogy:** It's a quality inspector on a packing line. Some faults get a tick on a clipboard and the box goes on. Some boxes go to a "returns" shelf with a note saying what was wrong. If a box arrives with no label at all, the inspector stops the line.

**Why real teams use it:** Bad rows are counted and kept where people can look at them, so nothing gets "cleaned" away without anyone knowing. Expectations warn by default; `ON VIOLATION DROP ROW` removes the row, and `ON VIOLATION FAIL UPDATE` stops the update and rolls it back. Warn and drop record metrics on the dataset's **Data quality** tab and in the event log ([docs](https://docs.databricks.com/aws/en/ldp/expectations), checked 2026-10-08). Databricks' own quarantine pattern flags each row, then splits the data into a valid set and an invalid set ([docs](https://docs.databricks.com/aws/en/ldp/expectation-patterns), checked 2026-10-08).

**How this repo uses it:** A private view gives each Bronze row a verdict: the first of 8 rules it breaks, or `ok`. Nine warn-only expectations count each rule. Rows marked `ok` go to `silver_transactions`, which has three `FAIL UPDATE` guards in case the split itself has a bug. Rows that broke a rule go to `silver_rejected_transactions` with a `rejection_reason`. Zero amounts are allowed on purpose: all 4 in PaySim are fraud. See [the verdict view](../../../pipelines/silver/01_checked_transactions.sql), [the clean table](../../../pipelines/silver/02_transactions.sql) and [ADR 0008](../../adr/0008-silver-on-a-declarative-pipeline.md).

**What was verified:** 2026-10-06, workspace runs S2–S3 (`14fa8b3`). 5,987,427 Bronze rows = 5,987,412 clean + 5 rejected (`bad_amount`) + 10 identical copies. The Data quality tab showed `amount_valid` 5, `fully_parsed` 5 and `first_copy` 10 failures, exactly as predicted. Expectations are counted independently, so the same 5 malformed rows failed two rules each ([GAPS §4](../../GAPS.md)).

**Key terms:** expectation, `EXPECT`, `DROP ROW`, `FAIL UPDATE`, Data quality tab, quarantine.

**Go deeper:** private study notes (drills, diagrams, traps) live outside the public repo.
