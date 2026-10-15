"""The two AI/BI dashboards as code (Phase 6a spec §5.2, ADR 0012). scripts/build_dashboards.py writes them to dashboards/."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
from __future__ import annotations  # modern type hints on 3.11

import json                         # render the dashboard files
from typing import Any, Callable    # type hints

# ── Plain words (owner rule 2026-10-15) ───────────────────────
WORD_LIST: dict[str, str] = {  # term -> one plain sentence; on both dashboards and in the README
    "Flagged payment": "A payment the model ranked among the 50 most suspicious of its hour, so a person should look at it.",  # alert
    "Case": "The review of one flagged payment. It stays open until its verdict is recorded.",  # case
    "Verdict": "The answer to a case: confirmed fraud or false alarm. It arrives 3 simulated days after the payment.",  # verdict
    "Confirmed fraud": "A flagged payment that really was fraud.",  # true positive
    "False alarm": "A flagged payment that turned out to be honest.",  # false positive
    "Simulated hour": "One hour of the replayed month of payments, numbered from 1 to 743.",  # step
    "Model version": "Which saved copy of the fraud model made the decision. Each new copy gets the next number.",  # registry version
    "Champion model": "The model version currently trusted to score new payments.",  # alias
    "Risk score": "How suspicious the model found a payment. Higher is more suspicious. It ranks payments, it is not a chance.",  # score
    "Rejected row": "A payment record that failed a basic check, such as an amount below zero, and was set aside.",  # quarantine
    "Job run": "One run of the scheduled work that releases, loads, cleans, scores and flags payments.",  # job run
    "Task": "One step inside a job run, such as loading or scoring.",  # task
    "REDACTED": "Shown instead of an account name to people who may not see who paid whom.",  # column mask
}  # end WORD_LIST
PLATFORM_WORDS: dict[str, str] = {  # extra terms on the engineers' dashboard
    "Landing folder": "Where each simulated hour's file of payments arrives before it is loaded.",  # landing volume
    "Pipeline update": "One run of the cleaning step that turns loaded payments into clean ones.",  # pipeline update
    "Full rebuild": "A pipeline update that redoes everything from the start instead of only the new rows.",  # full refresh
}  # end PLATFORM_WORDS
JARGON = ("precision", "recall", "latency", "p95", "drift", "sla", "throughput", "f1", "auc",  # model and operations jargon
          "percentile", "median", "idempotent", "cardinality", "etl")  # data jargon (CI guard on all visible text)
HOW_TO_READ = "How to read it:"  # every chart has a text line containing this
WAITING = "waiting for verdicts (3 days)"  # how an hour without verdicts is described
REASON_WORDS: dict[str, str] = {  # Silver rejection codes -> plain words
    "missing_id": "Payment ID missing",  # rule 1
    "missing_time": "Payment time missing",  # rule 2
    "time_step_mismatch": "Payment time does not match its simulated hour",  # rule 3
    "bad_amount": "Amount missing or below zero",  # rule 4
    "unknown_type": "Unknown payment type",  # rule 5
    "missing_account": "Account name missing",  # rule 6
    "bad_label": "Fraud answer is not 0 or 1",  # rule 7
    "unparsed_value": "A value could not be read",  # rule 8
    "conflicting_duplicate": "Two different records with the same payment ID",  # rule 9
}  # end REASON_WORDS
OPERATIONS_SOURCES = frozenset({"alert_cases", "alert_summary_hourly", "model_accuracy_by_hour",  # all three groups...
                                "hours_waiting_for_verdicts"})  # ...have grants on these
PLATFORM_SOURCES = frozenset({"job_run_times", "pipeline_update_times", "data_freshness", "rejected_rows_by_reason"})  # engineers
GRID_WIDTH = 6  # AI/BI dashboards lay widgets out on a 6-column grid


# ── Building blocks ───────────────────────────────────────────
def sql(*lines: str) -> str:  # join SQL lines (one Python comment per line at the call site)
    return "\n".join(lines)  # one statement


def dataset(name: str, title: str, query: str) -> dict[str, Any]:  # one SQL dataset
    return {"name": name, "displayName": title, "query": query}  # the form in Databricks' bundle example


def _field(column: str, aggregate: str | None = None) -> dict[str, str]:  # one query field
    if aggregate is None:  # a plain column
        return {"name": column, "expression": f"`{column}`"}  # as is
    return {"name": f"{aggregate.lower()}({column})", "expression": f"{aggregate}(`{column}`)"}  # aggregated


def _queries(dataset_name: str, fields: list[dict[str, str]], disaggregated: bool) -> list[dict[str, Any]]:  # a widget's query
    return [{"name": "main_query",  # one query per widget
             "query": {"datasetName": dataset_name, "fields": fields, "disaggregated": disaggregated}}]  # what it reads


def _frame(title: str) -> dict[str, Any]:  # a widget's visible title
    return {"showTitle": True, "title": title}  # shown above the widget


def text(name: str, markdown: str) -> dict[str, Any]:  # a text box
    return {"name": name, "textbox_spec": markdown}  # Markdown text


def how_to_read(name: str, sentence: str) -> dict[str, Any]:  # the one line under each chart
    return text(name, f"**{HOW_TO_READ}** {sentence}")  # bold lead, plain sentence


def bar(name: str, title: str, dataset_name: str, x: tuple[str, str], y: tuple[str, str],  # chart, data, axes (column, label)
        color: tuple[str, str] | None = None, aggregate: str = "SUM", x_scale: str = "quantitative") -> dict[str, Any]:  # options
    y_field = _field(y[0], aggregate)  # the bar height
    fields = [_field(x[0]), y_field] + ([_field(color[0])] if color else [])  # columns the chart needs
    encodings: dict[str, Any] = {  # what goes where
        "x": {"fieldName": x[0], "displayName": x[1], "axis": {"title": x[1]}, "scale": {"type": x_scale}},  # across
        "y": {"fieldName": y_field["name"], "displayName": y[1], "axis": {"title": y[1]},  # up...
              "scale": {"type": "quantitative"}},  # ...as a number
    }  # end encodings
    if color:  # split each bar by a category
        encodings["color"] = {"fieldName": color[0], "displayName": color[1], "scale": {"type": "categorical"}}  # legend
    spec = {"version": 3, "widgetType": "bar", "frame": _frame(title), "encodings": encodings}  # the chart
    return {"name": name, "queries": _queries(dataset_name, fields, False), "spec": spec}  # the widget


COLUMN_FORMATS: dict[str, dict[str, str]] = {  # column type -> how it shows (keys as in Databricks' exports)
    "string": {"displayAs": "string", "alignContent": "left"},  # text
    "integer": {"displayAs": "number", "alignContent": "right", "numberFormat": "0"},  # whole numbers
    "float": {"displayAs": "number", "alignContent": "right", "numberFormat": "0.0"},  # one decimal place (D3: 4.600)
    "datetime": {"displayAs": "datetime", "alignContent": "right", "dateTimeFormat": "YYYY-MM-DD HH:mm"},  # times
}  # end COLUMN_FORMATS


def _column(field: str, label: str, kind: str, order: int) -> dict[str, Any]:  # one table column, fully specified
    return {"fieldName": field, "displayName": label, "title": label, "type": kind,  # what and its label
            **COLUMN_FORMATS[kind], "visible": True, "order": order,  # how it shows, in which place
            "allowHTML": False, "allowSearch": False, "booleanValues": ["false", "true"],  # export defaults...
            "highlightLinks": False, "useMonospaceFont": False, "preserveWhitespace": False,  # ...display
            "imageUrlTemplate": "{{ @ }}", "imageTitleTemplate": "{{ @ }}", "imageWidth": "", "imageHeight": "",  # ...images
            "linkUrlTemplate": "{{ @ }}", "linkTextTemplate": "{{ @ }}", "linkTitleTemplate": "{{ @ }}",  # ...links
            "linkOpenInNewTab": True}  # D3: two-key columns showed "Invalid widget definition is imported"


def table(name: str, title: str, dataset_name: str, columns: list[tuple[str, str, str]]) -> dict[str, Any]:  # a table
    spec = {"version": 1, "widgetType": "table", "frame": _frame(title),  # the table...
            "invisibleColumns": [], "allowHTMLByDefault": False, "itemsPerPage": 25,  # ...table-level export...
            "paginationSize": "default", "condensed": True, "withRowNumber": False,  # ...defaults
            "encodings": {"columns": [_column(c, label, kind, 100000 + i)  # every column, in order
                                      for i, (c, label, kind) in enumerate(columns)]}}  # (field, label, type)
    return {"name": name, "queries": _queries(dataset_name, [_field(c) for c, _, _ in columns], True), "spec": spec}  # raw rows


def counter(name: str, title: str, dataset_name: str, value: tuple[str, str]) -> dict[str, Any]:  # one big number
    spec = {"version": 2, "widgetType": "counter", "frame": _frame(title),  # the counter...
            "encodings": {"value": {"fieldName": value[0], "displayName": value[1]}}}  # ...and its value
    return {"name": name, "queries": _queries(dataset_name, [_field(value[0])], True), "spec": spec}  # one row


def stack(*items: tuple[dict[str, Any], int, int]) -> list[dict[str, Any]]:  # place (widget, width, height) left to right
    layout: list[dict[str, Any]] = []  # placed widgets
    x = y = row_height = 0  # cursor and current row height
    for widget, width, height in items:  # in reading order
        if x + width > GRID_WIDTH:  # no room left on this row
            x, y, row_height = 0, y + row_height, 0  # start the next row
        layout.append({"widget": widget, "position": {"x": x, "y": y, "width": width, "height": height}})  # place it
        x, row_height = x + width, max(row_height, height)  # move the cursor
    return layout  # the page layout


def page(name: str, title: str, *items: tuple[dict[str, Any], int, int]) -> dict[str, Any]:  # one dashboard page
    return {"name": name, "displayName": title, "layout": stack(*items)}  # title and widgets


def word_page(words: dict[str, str]) -> dict[str, Any]:  # the "What these words mean" page
    lines = "\n".join(f"- **{term}** — {meaning}" for term, meaning in words.items())  # one line per term
    return page("words", "What these words mean",  # plain title
                (text("word_list", f"# What these words mean\n\n{lines}"), GRID_WIDTH, 10))  # one text box


def render(dashboard: dict[str, Any]) -> str:  # the .lvdash.json text
    return json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n"  # stable, readable, UTF-8


# ── Fraud operations: datasets (all three groups; filters and masks apply to the viewer) ──
OPEN_CASES = dataset("open_cases", "Open cases", sql(  # flagged payments still waiting for a verdict
    "SELECT step AS simulated_hour,",  # the hour
    "       risk_score,",  # how suspicious
    "       transaction_id AS payment,",  # which payment
    "       sender_account AS paying_account,",  # REDACTED for managers (mask)
    "       receiver_account AS receiving_account,",  # REDACTED for managers (mask)
    "       opened_at AS case_opened_at",  # when the case opened
    "FROM workspace.fraud.alert_cases",  # row filter: managers see no open cases
    "WHERE status = 'open'",  # still waiting
    "ORDER BY step DESC, risk_score DESC",  # newest hour first, most suspicious first
))  # end OPEN_CASES
OPEN_CASE_COUNT = dataset("open_case_count", "Open case count", sql(  # how many cases wait
    "SELECT COUNT(*) AS open_cases",  # the number
    "FROM workspace.fraud.alert_cases",  # row filter applies
    "WHERE status = 'open'",  # still waiting
))  # end OPEN_CASE_COUNT
REVIEW_OUTCOMES = dataset("review_outcomes", "Review outcomes per hour", sql(  # one row per hour and verdict
    "SELECT step AS simulated_hour, 'Confirmed fraud' AS outcome, confirmed_fraud AS cases",  # fraud
    "FROM workspace.fraud.alert_summary_hourly WHERE closed_cases > 0",  # hours with verdicts
    "UNION ALL",  # stacked with
    "SELECT step, 'False alarm', false_alarms",  # honest payments
    "FROM workspace.fraud.alert_summary_hourly WHERE closed_cases > 0",  # hours with verdicts
))  # end REVIEW_OUTCOMES
MODEL_BY_HOUR = dataset("model_by_hour", "Model results per hour", sql(  # the two shares per hour (review I2)
    "SELECT step AS simulated_hour,",  # the hour
    "       array_join(sort_array(collect_set(CAST(model_version AS STRING))), ' and ') AS model_version,",  # e.g. "3 and 4"
    "       try_divide(SUM(confirmed_fraud), SUM(closed_cases)) AS share_flagged_that_were_fraud,",  # from counts
    "       try_divide(SUM(confirmed_fraud), MAX(fraud_in_hour)) AS share_of_fraud_caught",  # fraud counted once
    "FROM workspace.fraud.model_accuracy_by_hour",  # the model view
    "WHERE verdicts_ready",  # waiting hours have no bar, never a zero
    "GROUP BY step",  # one row per hour, however many model versions
))  # end MODEL_BY_HOUR
MODEL_TOTALS = dataset("model_totals", "Model results so far", sql(  # every hour with verdicts, together (ruling R8)
    "WITH ready AS (SELECT * FROM workspace.fraud.model_accuracy_by_hour WHERE verdicts_ready),",  # hours with verdicts
    "     hours AS (SELECT DISTINCT step, fraud_in_hour FROM ready),",  # fraud once per hour
    "     totals AS (SELECT (SELECT SUM(confirmed_fraud) FROM ready) AS confirmed_fraud,",  # real fraud flagged
    "                       (SELECT SUM(closed_cases) FROM ready) AS checked_cases,",  # flagged with a verdict
    "                       (SELECT SUM(fraud_in_hour) FROM hours) AS all_fraud,",  # every fraud in those hours
    "                       (SELECT hours_waiting FROM workspace.fraud.hours_waiting_for_verdicts) AS hours_waiting)",  # review I1
    "SELECT confirmed_fraud, checked_cases, all_fraud, hours_waiting,",  # the counts
    "       ROUND(try_divide(confirmed_fraud, checked_cases), 3) AS share_flagged_that_were_fraud,",  # 0.139 after run E
    "       ROUND(try_divide(confirmed_fraud, all_fraud), 3) AS share_of_fraud_caught",  # 0.493 after run E
    "FROM totals",  # one row
))  # end MODEL_TOTALS


# ── Fraud operations: pages ───────────────────────────────────
def operations_dashboard() -> dict[str, Any]:  # "Fraud operations": reviewers, managers, engineers
    queue = page("queue", "What is waiting for review?",  # page 1
        (counter("open_count", "Open cases waiting for a verdict", "open_case_count", ("open_cases", "Open cases")), GRID_WIDTH, 2),  # total
        (table("open_table", "Open cases, newest hour first, most suspicious first", "open_cases", [  # the queue
            ("simulated_hour", "Simulated hour", "integer"), ("risk_score", "Risk score", "float"), ("payment", "Payment", "string"),  # what
            ("paying_account", "Paying account", "string"), ("receiving_account", "Receiving account", "string"),  # who
            ("case_opened_at", "Case opened at (UTC)", "datetime")]), GRID_WIDTH, 8),  # when
        (how_to_read("open_how", "Each row is one flagged payment still waiting for its verdict. If you may not see "  # the line
                     "open cases, the table is empty. If you may not see account names, they show as REDACTED."), GRID_WIDTH, 1),  # masks
    )  # end queue
    outcomes = page("outcomes", "How did the reviews turn out?",  # page 2
        (bar("outcomes_bar", "Confirmed fraud and false alarms per simulated hour", "review_outcomes",  # stacked bars
             ("simulated_hour", "Simulated hour"), ("cases", "Cases"), color=("outcome", "Verdict")), GRID_WIDTH, 6),  # by verdict
        (how_to_read("outcomes_how", "Each bar is one simulated hour, split into confirmed fraud and false alarms. "  # the line
                     f"Only hours whose verdicts are in have a bar; newer hours are {WAITING}."), GRID_WIDTH, 1),  # waiting
    )  # end outcomes
    model = page("model", "Is the model still good?",  # page 3
        (counter("flagged_share", "Of the payments we flagged, how many were really fraud", "model_totals",  # share 1
                 ("share_flagged_that_were_fraud", "Share that were fraud")), 2, 2),  # 0.139 after run E
        (counter("caught_share", "Of all the fraud, how much we caught", "model_totals",  # share 2
                 ("share_of_fraud_caught", "Share of fraud caught")), 2, 2),  # 0.493 after run E
        (counter("hours_waiting", f"Hours still {WAITING}", "model_totals", ("hours_waiting", "Hours")), 2, 2),  # waiting
        (how_to_read("totals_how", "The first two numbers cover every hour whose verdicts are in. "  # the line
                     "0.14 means 14 out of every 100."), GRID_WIDTH, 1),  # reading a share
        (table("totals_table", "The counts behind those shares", "model_totals", [  # the counts
            ("confirmed_fraud", "Confirmed fraud", "integer"), ("checked_cases", "Flagged payments with a verdict", "integer"),  # flagged
            ("all_fraud", "All fraud in those hours", "integer")]), GRID_WIDTH, 2),  # every fraud
        (how_to_read("counts_how", "Confirmed fraud divided by flagged payments with a verdict gives the first share; "  # the line
                     "divided by all fraud, the second."), GRID_WIDTH, 1),  # how the shares are made
        (bar("flagged_bar", "Of the payments we flagged, how many were really fraud, per simulated hour", "model_by_hour",  # per hour
             ("simulated_hour", "Simulated hour"), ("share_flagged_that_were_fraud", "Share that were fraud"),  # axes
             color=("model_version", "Model version"), aggregate="AVG"), GRID_WIDTH, 5),  # one bar per hour
        (how_to_read("flagged_how", "Each bar is one simulated hour, coloured by model version. Taller is better. "  # the line
                     f"Hours with no bar are {WAITING}."), GRID_WIDTH, 1),  # waiting
        (bar("caught_bar", "Of all the fraud, how much we caught, per simulated hour", "model_by_hour",  # per hour
             ("simulated_hour", "Simulated hour"), ("share_of_fraud_caught", "Share of fraud caught"),  # axes
             color=("model_version", "Model version"), aggregate="AVG"), GRID_WIDTH, 5),  # one bar per hour
        (how_to_read("caught_how", "Each bar is one simulated hour. Taller is better. Hours with no bar are "  # the line
                     f"{WAITING}, or had no fraud at all."), GRID_WIDTH, 1),  # waiting or nothing to catch
    )  # end model
    return {"datasets": [OPEN_CASES, OPEN_CASE_COUNT, REVIEW_OUTCOMES, MODEL_BY_HOUR, MODEL_TOTALS],  # five datasets
            "pages": [queue, outcomes, model, word_page(WORD_LIST)]}  # four pages


# ── Platform health: datasets (engineers only) ────────────────
def _plain_outcome(column: str) -> str:  # SUCCEEDED -> Succeeded, TIMED_OUT -> Timed Out, empty -> Still running
    return f"coalesce(initcap(replace({column}, '_', ' ')), 'Still running')"  # SQL expression


JOB_RUNS = dataset("job_runs", "Job runs", sql(  # one row per run
    f"SELECT DISTINCT job_name, run_started_at, minutes_taken, {_plain_outcome('outcome')} AS outcome",  # run columns
    "FROM workspace.fraud.job_run_times",  # the jobs view
    "ORDER BY run_started_at DESC",  # newest first
))  # end JOB_RUNS
TASK_TIMES = dataset("task_times", "Task minutes", sql(  # one row per task of each fraud-ingest run
    f"SELECT run_started_at, task_name, task_minutes, {_plain_outcome('task_outcome')} AS task_outcome",  # task columns
    "FROM workspace.fraud.job_run_times",  # the jobs view
    "WHERE job_name = 'fraud-ingest' AND task_name IS NOT NULL",  # the loading job's tasks
))  # end TASK_TIMES
PIPELINE_UPDATES = dataset("pipeline_updates", "Pipeline updates", sql(  # one row per update
    f"SELECT update_started_at, minutes_taken, {_plain_outcome('outcome')} AS outcome,",  # update columns
    "       CASE WHEN full_rebuild THEN 'Full rebuild' ELSE 'New rows only' END AS update_kind",  # plain kind
    "FROM workspace.fraud.pipeline_update_times",  # the pipeline view
    "ORDER BY update_started_at DESC",  # newest first
))  # end PIPELINE_UPDATES
FRESHNESS = dataset("freshness", "Newest hour at each stage", sql(  # one row per stage
    "SELECT '1. Copied to the landing folder' AS stage, newest_hour_released AS newest_simulated_hour FROM workspace.fraud.data_freshness",  # release
    "UNION ALL SELECT '2. Loaded', newest_hour_ingested FROM workspace.fraud.data_freshness",  # Bronze
    "UNION ALL SELECT '3. Scored by the model', newest_hour_scored FROM workspace.fraud.data_freshness",  # scoring
    "UNION ALL SELECT '4. Flagged for review', newest_hour_flagged FROM workspace.fraud.data_freshness",  # Gold
))  # end FRESHNESS
WAIT = dataset("wait", "Wait from landing to scored", sql(  # the latest run's waits
    "SELECT median_minutes_landing_to_scored AS typical_minutes,",  # half waited less
    "       slowest_minutes_landing_to_scored AS longest_minutes",  # the slowest payment
    "FROM workspace.fraud.data_freshness",  # one row
))  # end WAIT
REJECTIONS = dataset("rejections", "Rows set aside", sql(  # one row per reason, in plain words
    "SELECT CASE reason " + " ".join(f"WHEN '{code}' THEN '{words}'" for code, words in REASON_WORDS.items()),  # plain reason
    "            ELSE reason END AS reason,",  # an unknown code shows as is
    "       rows_rejected, first_hour, last_hour",  # count and hour range
    "FROM workspace.fraud.rejected_rows_by_reason",  # the shelf summary
    "ORDER BY rows_rejected DESC",  # biggest first
))  # end REJECTIONS


# ── Platform health: pages ────────────────────────────────────
def platform_dashboard() -> dict[str, Any]:  # "Platform health": engineers only
    jobs = page("jobs", "Are the jobs healthy?",  # page 1
        (bar("run_minutes", "Minutes per job run", "job_runs", ("run_started_at", "Run started (UTC)"),  # per run
             ("minutes_taken", "Minutes"), color=("job_name", "Job"), x_scale="temporal"), GRID_WIDTH, 5),  # by job
        (how_to_read("run_minutes_how", "Each bar is one run, placed at the time it started. Taller means slower. "  # the line
                     "A run shows up here up to an hour after it finishes."), GRID_WIDTH, 1),  # system table lag (ruling R3)
        (table("run_table", "Every job run and how it ended", "job_runs", [  # the run list
            ("job_name", "Job", "string"), ("run_started_at", "Started (UTC)", "datetime"), ("minutes_taken", "Minutes", "float"),  # what and how long
            ("outcome", "How it ended", "string")]), GRID_WIDTH, 5),  # result
        (how_to_read("run_table_how", "Anything other than Succeeded is a run that needs a look."), GRID_WIDTH, 1),  # failures
        (bar("task_minutes", "Minutes per task in each run of fraud-ingest", "task_times", ("run_started_at", "Run started (UTC)"),  # per task
             ("task_minutes", "Minutes"), color=("task_name", "Task"), x_scale="temporal"), GRID_WIDTH, 5),  # stacked by task
        (how_to_read("task_minutes_how", "Each bar is one run, split into its tasks. The tallest part is "  # the line
                     "where the time goes. The two dashboard refreshes run side by side, so a bar can be "  # review M4
                     "taller than the run itself."), GRID_WIDTH, 1),  # reading a stacked bar
        (bar("pipeline_minutes", "Minutes the cleaning pipeline itself spent per update", "pipeline_updates",  # per update
             ("update_started_at", "Update started (UTC)"), ("minutes_taken", "Minutes"),  # axes
             color=("update_kind", "Kind of update"), x_scale="temporal"), GRID_WIDTH, 5),  # by kind
        (how_to_read("pipeline_minutes_how", "Compare with the silver task above: the difference is the time spent "  # the line
                     "starting up and waiting, not cleaning."), GRID_WIDTH, 1),  # G-15 story
    )  # end jobs
    data = page("data", "Is the data fresh and clean?",  # page 2
        (table("freshness_table", "Newest simulated hour at each stage", "freshness", [  # four stages
            ("stage", "Stage", "string"), ("newest_simulated_hour", "Newest simulated hour", "integer")]), GRID_WIDTH, 4),  # stage and hour (D3: height 3 clipped row 4)
        (how_to_read("freshness_how", "After a run all four numbers should be equal. A lower number shows "  # the line
                     "where payments are stuck."), GRID_WIDTH, 1),  # reading it
        (counter("typical_wait", "Typical minutes from landing to scored", "wait",  # half waited less
                 ("typical_minutes", "Minutes")), 3, 2),  # latest run
        (counter("longest_wait", "Longest minutes from landing to scored", "wait",  # the slowest payment
                 ("longest_minutes", "Minutes")), 3, 2),  # latest run
        (how_to_read("wait_how", "Both numbers cover the latest scoring run only. Half of its payments waited "  # the line
                     "less than the typical number."), GRID_WIDTH, 1),  # plain words for the middle value
        (table("rejections_table", "Rows set aside, by reason", "rejections", [  # the shelf
            ("reason", "Why it was set aside", "string"), ("rows_rejected", "Rows", "integer"),  # reason and count
            ("first_hour", "First simulated hour", "integer"), ("last_hour", "Last simulated hour", "integer")]), GRID_WIDTH, 3),  # range
        (how_to_read("rejections_how", "Each row is one reason a payment record failed a basic check. "  # the line
                     "Set-aside rows are kept for checking, never scored."), GRID_WIDTH, 1),  # what happens to them
    )  # end data
    return {"datasets": [JOB_RUNS, TASK_TIMES, PIPELINE_UPDATES, FRESHNESS, WAIT, REJECTIONS],  # six datasets
            "pages": [jobs, data, word_page({**WORD_LIST, **PLATFORM_WORDS})]}  # three pages


DASHBOARDS: dict[str, Callable[[], dict[str, Any]]] = {  # bundle resource key (and file name) -> builder
    "fraud_operations": operations_dashboard,  # dashboards/fraud_operations.lvdash.json
    "platform_health": platform_dashboard,  # dashboards/platform_health.lvdash.json
}  # end DASHBOARDS
