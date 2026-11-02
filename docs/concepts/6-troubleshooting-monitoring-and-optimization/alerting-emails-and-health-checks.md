# Alerting Emails: Job Notifications and SQL Alert Tasks

**In plain words:** A dashboard only helps someone who opens it. An alerting email comes to you when something needs a look. This repo has two kinds:
- **job notifications:** an email when the `fraud-ingest` run fails or takes over 30 minutes;
- **two health checks:** SQL alerts that ask "is any stage behind?" and "were any rows rejected in the newest 24 hours?" at the end of every run, and email if the answer is above 0.

They report on the data system, never on payments, so every subject starts "System health check:" to keep them apart from the Gold layer's *fraud alerts*.

**Everyday analogy:** A dashboard is the car's instrument panel; an alerting email is the warning chime. You don't stare at the fuel gauge all day, but you hear the chime when the tank runs low, and the panel then tells you the details.

**Why real teams use it:**
- **Job notifications** are built into every job: emails on start, success, failure, or when a **health rule** such as `RUN_DURATION_SECONDS` is crossed ([job notifications](https://docs.databricks.com/aws/en/jobs/notifications), checked 2026-11-02). The duration email is only sent if that rule exists.
- **A SQL alert** is a query plus a condition (for example "first row of `hours_behind` > 0"). It emails subscribers when the condition is met and, if **Notify on OK** is on, again when it clears ([alerts](https://docs.databricks.com/aws/en/sql/user/alerts/), checked 2026-11-02).
- **The SQL alert task** evaluates an alert from inside a job, independently of the alert's own schedule ([SQL alert task](https://docs.databricks.com/aws/en/jobs/alert)). The check then runs right after new data lands, with no extra schedule.
- **Alerts as code:** a bundle can declare alerts (`alerts:`) next to the jobs, so the queries, limits and wording are reviewed in Git ([bundle resources](https://docs.databricks.com/aws/en/dev-tools/bundles/resources)).

**How this repo uses it:**
- [Health checks](../../../resources/fraud_health_checks.yml) define both alerts:
  - their schedules are **paused**, so only the job runs them;
  - they send one email per problem, then one "back to normal";
  - an empty answer counts as a problem.
- [The job](../../../resources/fraud_ingest_job.yml) emails `${workspace.current_user.userName}`, filled in at deploy time, so no address is ever committed. Its two check tasks use **Run if: All done**, so the data is checked even after an earlier task failed.
- **The stages question** compares the newest hour released with the newest hour in Bronze, Silver and scoring. Each stage defaults to 0 when empty, because `GREATEST` skips blanks and an empty stage would otherwise look "not behind".
- **The email body** is four short HTML paragraphs (the standard template editor allows a short list of tags):
  - an opening line saying no payment needs review;
  - **Status**;
  - **What was found**;
  - **What to do**.
- See [ADR 0013](../../adr/0013-alerting-emails-and-health-checks.md).

**What was verified:** Databricks Free Edition, 2026-11-02 (`docs/GAPS.md` §8, checks V1–V7), with the data kept at hour 480:
- **SQL editor checks:** each check's question gave 0 and 0 on today's data, 5 on the past window holding the 5 known bad rows, and 1 for a pretend unloaded hour.
- **A run with `steps_per_run = 0`:**
  - failed in `release` on its own guard before copying anything;
  - **both checks still ran** and stayed quiet;
  - the failure email arrived;
  - the release log was unchanged.
- **A drill copy of the rejected-rows check** emailed in about 1 minute with its placeholders filled in. Numbers arrive as decimals ("5.0"), so the body puts them at the end of a label.
- **Free Edition specifics:**
  - "Run alert" needs a schedule before it can be clicked;
  - only workspace users can be notified, with no Slack or webhook destinations.

**Not shown:**
- the 30-minute email, which needs a 30-minute run;
- the real "back to normal" email, which needs the data to move past hour 480 (Phase 6c).

**Key terms:** job notification, health rule, SQL alert, SQL alert task, Run if (All done), Notify on OK, notification template, empty result state.

**Go deeper:** private study notes (drills, diagrams, traps) live outside the public repo.
