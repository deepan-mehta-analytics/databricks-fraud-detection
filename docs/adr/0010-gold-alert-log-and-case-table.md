# ADR 0010: Gold Alert Log and Case Table

## Status
Proposed (2026-10-15). Builds on [ADR 0009](0009-batch-scoring-with-mlflow-and-unity-catalog.md):
Gold reads the scoring decision log, `transaction_risk_scores`.
Label-rule wording widened by [ADR 0012](0012-monitoring-dashboards-and-views.md) (2026-10-15): two statements, both behind the 72-hour cutoff.

## Context
Phase 4 writes one risk score per payment. A fraud team needs more than
scores: a fixed-size work queue, a record of what was flagged, and a place to
track each investigation until a verdict. The constraints:

- A review team can handle a fixed number of alerts. ADR 0009 sized it at 50
  per simulated hour (`ALERT_BUDGET_DEFAULT`).
- An alert is a promise to a reviewer. If the queue changed after it was
  handed out, a case could vanish halfway through an investigation.
- Files can arrive late (Silver's S5 check proved a late file changes later
  features), so an hour that was already alerted can receive more payments.
- Real fraud labels arrive later than the payment. The model was trained with
  a 3-day label delay.
- Free Edition runs SQL on one serverless SQL warehouse, and a job can run a
  SQL file as a task.

Measured on `data/paysim.csv` (2026-10-11) for the scored hours 337–418:
1,205,679 payments in 82 hours, 25 of them with fewer than 50 payments, so
the budget gives 3,154 alerts. The newest scored hour, 418, puts the closing
cutoff at 346 and gives 262 closed cases.

## Decision
1. **An append-only alert log, `fraud_alerts`.** For each hour that has scores
   but no alerts yet, payments are ranked by risk score and the top 50 are
   written, with ties going to the smaller `transaction_id` so a rerun picks
   the same ones. An alerted hour is never re-ranked. Writes use
   `MERGE … WHEN NOT MATCHED THEN INSERT`, so a rerun adds nothing, and the SQL
   never updates or deletes the log (CI text guard).
2. **A late-payment rule.** A payment that reaches an already-alerted hour is
   alerted with `is_late_alert = true` if the hour still has room under its
   budget, or if it beats the hour's lowest alert score. A batch of late
   payments fills only the room that is left (final review M1).
3. **A case table, `alert_cases`, one row per alert.** Each case starts `open`
   and closes once, with a verdict (`confirmed_fraud` or `false_alarm`), when
   its hour is at least 72 simulated hours older than the newest scored hour.
   This is the data's own clock, so reruns behave the same. The verdict comes
   from the dataset's label: the reviewers are simulated. The label is read in
   that one statement only (CI text guard).
4. **A plain view, `alert_summary_hourly`,** gives per-hour totals (alerts,
   closed, confirmed fraud, false alarms). It stores nothing and is always
   current.
5. **One SQL file task, `gold`,** runs after `score` in `fraud-ingest` on the
   SQL warehouse. The warehouse is found by name with a bundle `lookup`
   variable, so no warehouse ID appears in this public repo.
6. **The file creates its own tables** with `IF NOT EXISTS`, so the first run
   needs no setup step (plan ruling R1).
7. **A guard at the top.** The file stops at once unless the job's identity is
   in `fraud_engineers`. A masked or filtered identity would copy `REDACTED`
   into the tables or skip cases (final review I1). Account names for new
   cases come from Silver, never through the masked log.
8. **A local calculator** (`src/fraud_gold/expected.py`,
   `scripts/expected_gold.py`) predicts every count from the CSV before each
   run.

Planning rulings: R3 — the G10 check tests a late *hour*, not a late
*payment*. The replay delivers one file per hour, so one payment can never
arrive late for an hour that was already alerted. The late-payment rule is
proven by the calculator test and the SQL text guard instead.

## Consequences
**Positive:**
- Alerts never change after they are written, and a rerun is a no-op (G3b:
  the run's own query metrics reported 0 rows written).
- The event log (what was flagged) and the current state (where each case
  stands) are kept apart, which is the standard pattern in case-management
  systems.
- The workload is fixed by the budget, not by how busy the hour was.

**Negative:**
- Verdicts are simulated from labels, and one person plays every role.
- Gold runs once per job run, not as each payment is scored.
- A real late *payment* never happens in this replay, so the late rule is
  shown in tests only.
- The SQL task adds a SQL-warehouse start to every job run (see
  `docs/cost-model.md`).

**Checked in real runs (2026-10-12 and 2026-10-13, see `docs/GAPS.md` §6):**
- G2: run A, the first with the `gold` task, succeeded in 4 m 20 s.
- G3: 3,154 alerts, 3,154 distinct, 82 hours, steps 337–418, 0 late,
  0 duplicate ranks, the calculator's figures exactly.
- G4: rebuilding the top 50 per hour from the decision log found 0 missing and
  0 extra alerts.
- G5: 3,154 cases, 262 closed, 2,892 open, newest closed hour 346, and all 262
  verdicts matched the label.
- G3b: run B, with nothing new, changed nothing (14 m 52 s; the Silver
  pipeline update took 11 m 45 s of it, Gold 42 s).
- G10: hour 419 was held back (run C) and released late (run D). It got 50
  fresh alerts, 0 marked late, about 14 minutes after hour 420's. Hour 420
  got 50 and hour 421 got 14. The totals reached 3,268 alerts and 412 closed
  cases, and the calculator run with `--last-step 421` gave the same numbers.
- G11: the Lineage tab of `alert_cases` shows `fraud_alerts`,
  `silver_transactions` and the `fraud-ingest` job upstream, and the summary
  view downstream.

## Alternatives rejected
- **A materialized view for alerts:** it would re-pick the top 50 whenever late
  data arrived, so alerts could vanish from a reviewer's queue.
- **Alerting every payment above a score cut-off:** the queue would swing with
  traffic, and sampled scores are rankings, not probabilities (ADR 0009).
- **Ignoring late payments:** a late fraud would never reach a reviewer.
- **One table holding alerts and verdicts:** closing a case would mean editing
  the log.
- **A filter on verdicts computed from another table:** a row filter that
  looks up another table makes `MERGE` into the protected table fail
  (documented), so the case table carries its own `status` column.
- **A notebook task:** the logic is pure SQL, and a SQL task shows the
  warehouse path the exam covers (4.2).
- **A separate setup file for the tables:** unnecessary with `IF NOT EXISTS`
  (R1).
