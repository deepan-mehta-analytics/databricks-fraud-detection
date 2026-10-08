# Job Retries, Dependencies, and Schedules

**In plain words:** A Lakeflow Job is a graph of tasks; each task can depend on another finishing first, can retry automatically on failure, and the whole job can run on a schedule instead of by hand.

**Everyday analogy:** It's a recipe with steps in order — you don't start frying until the chopping is done — and if a step gets burned you retry that one step, not the whole meal, and you can set a timer instead of watching it.

**Why real teams use it:** Retries and dependencies keep a pipeline self-healing and correctly ordered without manual babysitting, and schedules give hands-off, repeatable runs ([docs](https://docs.databricks.com/aws/en/jobs/configure-task.html), checked 2026-09-27).

**How this repo uses it:** A three-task job runs `release`, then `ingest`, then `silver` (`depends_on`). `silver` is a pipeline task: it starts one update of the Lakeflow pipeline and finishes when that update does ([docs](https://docs.databricks.com/aws/en/jobs/pipeline), checked 2026-10-08). `ingest` is set to `max_retries: 1` to recover from a schema-change restart, and a 10-minute cron schedule is defined but paused — every real run so far used a manual "Run now". See [job definition](../../../resources/fraud_ingest_job.yml).

**What was verified:** 2026-09-24, workspace run: the new-column job failed once by design and succeeded on the automatic retry (`a6b108c`). 2026-10-06, workspace run S1: all three tasks succeeded in order, with the pipeline task updating the Silver views (`14fa8b3`).

**Key terms:** task graph, `depends_on`, pipeline task, `max_retries`, cron schedule.

**Go deeper:** private study notes (drills, diagrams, traps) live outside the public repo.
