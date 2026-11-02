# ADR 0013: Alerting Emails from Job Notifications and Two Health Checks

## Status
Proposed (2026-11-02). Builds on the monitoring views of
[ADR 0012](0012-monitoring-dashboards-and-views.md): dashboards show the state,
alerting emails push it.

## Context
The Phase 6a dashboards only help someone who opens them. Phase 6b adds a
message when something goes wrong. The constraints:

- **Free Edition.** The limits page says nothing about alerts or email, so a
  hand-made probe (P4, 2026-11-02) came first. It found:
  - SQL alerts exist and save themselves.
  - **Run alert stays disabled until the alert has a schedule.**
  - Notifications can go only to the workspace's users: no Slack or webhook
    destinations are set up.
  - The email arrived in about 1 minute.
- **About 3 job runs a day.** An alert on its own schedule would spend
  warehouse time even when no new data has arrived.
- **A public repo.** No email address, workspace URL or ID may be committed.
- **Two kinds of "alert".** The Gold layer already has *fraud alerts*:
  payments flagged for review (ADR 0010). A message about the data system must
  never be mistaken for one, especially by a reader such as a manager who
  isn't an engineer.
- **The replay stays at hour 480.** Every Phase 6a number and screenshot is a
  snapshot at that hour. The proof must not move the data.

## Decision
1. **Job health from job notifications.** `fraud-ingest` has:
   - a health rule (`RUN_DURATION_SECONDS` greater than **1,800**; the slowest
     measured run took 17 m 9 s);
   - emails `on_failure` and `on_duration_warning_threshold_exceeded`;
   - `no_alert_for_canceled_runs` and `no_alert_for_skipped_runs` set.
2. **Data health from two SQL alerts written in the bundle**
   (`resources/fraud_health_checks.yml`), called **health checks**:
   - **stages behind:** the newest hour released minus the newest hour in
     Bronze, Silver and scoring (`GREATEST` of the three). Each stage defaults
     to 0 when empty, so an empty stage counts as fully behind.
   - **rejected rows:** rows Silver set aside in the newest 24 released hours.

   Both fire above 0. `empty_result_state` is TRIGGERED, `notify_on_ok` is on,
   and `retrigger_seconds` is 0: one email per problem, then one "back to
   normal" email.
3. **The job evaluates them.** Two alert tasks (`check_stages_behind`,
   `check_rejected_rows`) run after `monitor` with **Run if: All done**, so they
   also run after an earlier failure. The alerts' own schedules are required
   but **paused**. The tasks add no subscribers, so each problem sends one
   email.
4. **One recipient, filled in at deploy:** `${workspace.current_user.userName}`.
   **Need-to-know:** alerting emails go to engineers only; managers and
   reviewers never get them.
5. **Wording that can't be mistaken for fraud news:**
   - Every subject and title starts **"System health check:"**.
   - Every body opens with *"This email is about the data system that feeds
     the fraud checks, not about any payment or customer. No payment needs
     review because of it."*
   - The body then has three bold-labelled HTML paragraphs: **Status**, **What
     was found**, **What to do**.
   - The emails are called **alerting emails**: they report a state rather
     than warn of one.

## Consequences
**Measured on Free Edition (2026-11-02, checks V1–V7, `docs/GAPS.md` §8):**
- Each check's query in the SQL editor gave 0 and 0 on today's data, 5 on the
  past window with the 5 bad rows, and 1 for a pretend unloaded hour.
- The deploy accepted the `alerts` resource and `alert_task` as written. It
  filled in a real address and shows Run if **All done**.
- **A run with `steps_per_run = 0`:**
  - `release` failed on its own guard (`ValueError: steps_per_run must be at
    least 1`) before copying anything;
  - **both checks still ran** and stayed quiet;
  - the run ended Failed and the failure email arrived;
  - the release log was unchanged (480 / 484).
- A drill copy of the rejected-rows check sent its email in about 1 minute,
  with the placeholders filled in. Bundle text lands in the alert's
  **standard** template editor, where HTML renders as formatted email.

**Trade-offs:**
- **Not proven:**
  - the "too long" email (it needs a 30-minute run), and whether it arrives
    mid-run;
  - the real "back to normal" email (it needs the data to move past hour 480,
    planned for Phase 6c).
- **Two emails for one problem.** A run that fails after `release` can send
  both the failure email and a "stages behind" email. This is the price of
  checking data even after a failure.
- **Databricks' fixed wording:**
  - The job failure email can't be customised.
  - Numbers show as decimals ("5.0").
  - Every alert email carries a Databricks line naming the alert's owner by
    address, so public screenshots crop it out.
- **Rejected rows with a missing or garbled hour number** fall outside the
  24-hour window. No scenario in this repo produces them.

## Alternatives rejected
- **Alerts on their own schedules.** They would spend warehouse time with no
  new data, and run out of step with the job.
- **Slack or webhook messages.** They need an admin-made destination, and
  outbound calls from Free Edition are limited. None exists here.
- **Hand-made alerts in the UI.** They can't be reviewed, tested or redeployed
  like the rest of the bundle.
- **One check over the `data_freshness` view.** The view has no Silver column,
  and the checks must work even when `monitor` failed.
- **Proving the alerts by moving the replay past hour 480.** That would change
  every Phase 6a number and screenshot. A guarded failing run, SQL-editor
  checks and a throw-away drill copy prove the same parts without moving data.
- **The Markdown template editor.** It has no placeholder for the result
  value.
