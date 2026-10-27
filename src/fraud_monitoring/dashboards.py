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
THEME: dict[str, Any] = {  # spec §4.1, identical on both dashboards
    "canvasBackgroundColor": {"light": "#EDF1F6", "dark": "#121821"},  # cool grey page
    "widgetBackgroundColor": {"light": "#FDFDFE", "dark": "#1A2230"},  # near-white cards
    "widgetBorderColor": {"light": "#FDFDFE", "dark": "#1A2230"},  # same as the card: borders hidden
    "fontColor": {"light": "#13294B", "dark": "#E6ECF4"},  # navy ink, also every counter number
    "selectionColor": {"light": "#2A78D6", "dark": "#5A9BE6"},  # filters and selections
    "visualizationColors": ["#2A78D6", "#EB6834", "#1BAF7A", "#EDA100",  # validated palette...
                            "#E87BA4", "#008300", "#6250D6", "#E34948"],  # ...in checked order
    "fontFamily": "Inter",  # probe: omitted if the workspace rejects it
    "widgetCornerRadius": 12,  # rounded cards
    "widgetHeaderAlignment": "LEFT",  # titles on the left
}  # end THEME
GOOD, BAD, WAIT_AMBER = "#0CA30C", "#D03B3B", "#FAB219"  # status colours, always paired with a word or symbol
FAILED_OUTCOMES = ("Error", "Failed", "Timed Out", "Canceled", "Cancelled", "Skipped", "Upstream Failed")  # run results shown with ✕
MEANING: dict[str, str] = {  # spec §4.2: value -> its colour on every chart
    "✓ Succeeded": GOOD, "Up to date": GOOD,  # good
    "Confirmed fraud": BAD, "Missed": BAD, "Behind": BAD,  # bad
    **{f"✕ {outcome}": BAD for outcome in FAILED_OUTCOMES},  # every failed run
    "↻ Still running": WAIT_AMBER,  # in progress
    "False alarm": "#B8C4D4",  # neutral grey
    "Caught": "#2A78D6", "Each hour": "#2A78D6", "New rows only": "#2A78D6", "Slowest task": "#2A78D6",  # main blue
    "Average, all hours": "#898781",  # reference grey
    "Full rebuild": "#EB6834",  # orange
    "Other tasks": "#A9C3E6",  # light blue tint
}  # end MEANING
TINT_GREEN, TINT_RED, TINT_BLUE_DARK, TINT_BLUE_LIGHT = "#DDF3E2", "#FBE3E1", "#B9D3F2", "#DCE9F9"  # cell-rule tints


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


def _frame(title: str, description: str = "") -> dict[str, Any]:  # a widget's visible title and subtext
    frame: dict[str, Any] = {"showTitle": True, "title": title}  # shown above the widget
    if description:  # a sentence under the title
        frame.update(showDescription=True, description=description)  # documented frame keys
    return frame  # the frame


def _how(sentence: str) -> str:  # the "How to read it" subtext of a chart (ruling R-B3)
    return f"{HOW_TO_READ} {sentence}"  # it sits in the widget description


def text(name: str, markdown: str) -> dict[str, Any]:  # a text box
    return {"name": name, "textbox_spec": markdown}  # Markdown text


def header(name: str, question: str, sentence: str) -> dict[str, Any]:  # a page header
    return text(name, f"## {question}\n\n{sentence}")  # the question, then one plain sentence


def _mappings(values: tuple[str, ...]) -> list[dict[str, str]]:  # pinned meaning colours
    return [{"value": v, "color": MEANING[v]} for v in values]  # bare hex, the honoured form


def _axis(field: str, label: str, scale: str, sort_by_value: bool = False) -> dict[str, Any]:  # one chart axis
    axis: dict[str, Any] = {"fieldName": field, "displayName": label, "axis": {"title": label},  # what and its label
                            "scale": {"type": scale}}  # how it is scaled
    if sort_by_value:  # biggest first
        axis["scale"]["sort"] = {"by": "value"}  # documented sort
    return axis  # the axis


def bar(name: str, title: str, dataset_name: str, x: tuple[str, str], y: tuple[str, str], how: str,  # chart, data, axes (column, label)
        color: tuple[str, str] | None = None, values: tuple[str, ...] = (), aggregate: str | None = "SUM",  # colour split, pins, sum
        x_scale: str = "quantitative", horizontal: bool = False, sort_by_value: bool = False) -> dict[str, Any]:  # options
    y_field = _field(y[0], aggregate)  # the bar length
    fields = [_field(x[0]), y_field] + ([_field(color[0])] if color else [])  # columns the chart needs
    across = _axis(x[0], x[1], x_scale, sort_by_value)  # the category or time axis
    length = _axis(y_field["name"], y[1], "quantitative")  # the number axis
    encodings: dict[str, Any] = {"x": length, "y": across} if horizontal else {"x": across, "y": length}  # horizontal swaps
    if color:  # split each bar by a category
        encodings["color"] = {"fieldName": color[0], "displayName": color[1],  # legend...
                              "scale": {"type": "categorical", "mappings": _mappings(values)}}  # ...with meaning colours
    spec = {"version": 3, "widgetType": "bar", "frame": _frame(title, _how(how)), "encodings": encodings}  # the chart
    return {"name": name, "queries": _queries(dataset_name, fields, aggregate is None), "spec": spec}  # the widget


def line(name: str, title: str, dataset_name: str, x: tuple[str, str], y: tuple[str, str], how: str,  # chart, data, axes
         color: tuple[str, str], values: tuple[str, ...], x_scale: str = "quantitative") -> dict[str, Any]:  # one line per series
    fields = [_field(x[0]), _field(y[0]), _field(color[0])]  # one row per point, already computed in SQL
    encodings = {"x": _axis(x[0], x[1], x_scale), "y": _axis(y[0], y[1], "quantitative"),  # across and up
                 "color": {"fieldName": color[0], "displayName": color[1],  # one line per series...
                           "scale": {"type": "categorical", "mappings": _mappings(values)}}}  # ...in its meaning colour
    spec = {"version": 3, "widgetType": "line", "frame": _frame(title, _how(how)), "encodings": encodings}  # the chart
    return {"name": name, "queries": _queries(dataset_name, fields, True), "spec": spec}  # the widget


NUMBER_FORMATS: dict[str, dict[str, Any]] = {  # table number kinds -> documented format (D3: 4.600 showed)
    "integer": {"type": "number", "decimalPlaces": {"type": "exact", "places": 0}},  # whole numbers
    "float": {"type": "number", "decimalPlaces": {"type": "exact", "places": 1}},  # one decimal place
}  # end NUMBER_FORMATS


def cell_rule(op: str, value: str, tint: str) -> dict[str, Any]:  # one conditional cell colour
    return {"condition": {"operand": {"type": "data-value", "value": value}, "operator": op},  # when it applies
            "backgroundColor": {"hex": tint}}  # the tint behind the text


def table(name: str, title: str, dataset_name: str, columns: list[tuple[str, str, str]], how: str,  # a table
          rules: dict[str, list[dict[str, Any]]] | None = None) -> dict[str, Any]:  # optional cell colours
    shown = []  # the table v2 columns
    for field, label, kind in columns:  # (field, label, kind)
        column: dict[str, Any] = {"fieldName": field, "displayName": label}  # all v2 needs
        if kind in NUMBER_FORMATS:  # a number
            column["format"] = NUMBER_FORMATS[kind]  # fixed decimal places
        if rules and field in rules:  # coloured cells
            column["style"] = {"type": "basic", "rules": rules[field]}  # documented rule block
        shown.append(column)  # in order
    spec = {"version": 2, "widgetType": "table", "frame": _frame(title, _how(how)),  # the table
            "encodings": {"columns": shown}}  # its columns
    return {"name": name, "queries": _queries(dataset_name, [_field(c) for c, _, _ in columns], True), "spec": spec}  # raw rows


def counter(name: str, title: str, dataset_name: str, value: tuple[str, str], how: str = "",  # one big number
            percent: bool = False, unit: str = "", target: tuple[str, str] | None = None,  # format and comparison
            aggregate: str | None = None, where: str | None = None) -> dict[str, Any]:  # optional sum with a filter
    value_field = _field(value[0], aggregate)  # the number
    shown: dict[str, Any] = {"fieldName": value_field["name"], "displayName": value[1]}  # never a colour key
    if percent:  # a share from 0 to 1
        shown["format"] = {"type": "number-percent", "decimalPlaces": {"type": "max", "places": 0}}  # 0.139 -> 14%
    if unit:  # a number with a unit
        shown["format"] = {"type": "number-plain"}  # plain number...
        shown["formatTemplate"] = "{{@formatted}} " + unit  # ...then the unit
    encodings: dict[str, Any] = {"value": shown}  # what is shown
    fields = [value_field]  # what is read
    if target:  # a comparison number
        fields.append(_field(target[0], aggregate))  # read it too
        encodings["target"] = {"fieldName": fields[-1]["name"], "displayName": target[1]}  # Databricks colours the change
    spec = {"version": 2, "widgetType": "counter", "frame": _frame(title, how), "encodings": encodings}  # the counter
    queries = _queries(dataset_name, fields, aggregate is None)  # one row, or summed rows
    if where:  # a widget query filter on a shared dataset
        queries[0]["query"]["filters"] = [{"expression": where}]  # documented shape
    return {"name": name, "queries": queries, "spec": spec}  # the widget


def _filter_queries(name: str, bindings: list[tuple[str, str]],  # one query per bound dataset...
                    fields: Callable[[str], list[dict[str, str]]]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:  # ...and its encoding
    queries, encoded = [], []  # built side by side
    for dataset_name, field in bindings:  # (dataset, field)
        query_name = f"{name}_{dataset_name}"  # unique per binding
        queries.append({"name": query_name, "query": {"datasetName": dataset_name, "fields": fields(field),  # what it reads
                                                      "disaggregated": False}})  # always false for filters
        encoded.append({"fieldName": field, "queryName": query_name})  # which column it narrows
    return queries, encoded  # both lists


def _bounds(field: str) -> list[dict[str, str]]:  # a slider reads its lowest and highest value
    return [{"name": f"min({field})", "expression": f"MIN(`{field}`)"},  # lowest
            {"name": f"max({field})", "expression": f"MAX(`{field}`)"}]  # highest


def range_slider(name: str, title: str, bindings: list[tuple[str, str]]) -> dict[str, Any]:  # a page slider on a number
    queries, encoded = _filter_queries(name, bindings, _bounds)  # one bounds query per dataset
    spec = {"version": 2, "widgetType": "range-slider", "encodings": {"fields": encoded}, "frame": _frame(title)}  # the slider
    return {"name": name, "queries": queries, "spec": spec}  # the widget


def single_select(name: str, title: str, bindings: list[tuple[str, str]]) -> dict[str, Any]:  # a page pick-one filter
    queries, encoded = _filter_queries(name, bindings, lambda f: [_field(f)])  # the values to pick from
    for entry in encoded:  # each binding
        entry["displayName"] = title  # its label
    spec = {"version": 2, "widgetType": "filter-single-select", "encodings": {"fields": encoded},  # the filter
            "frame": _frame(title)}  # its title
    return {"name": name, "queries": queries, "spec": spec}  # the widget


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
    return {"name": name, "displayName": title, "pageType": "PAGE_TYPE_CANVAS", "layout": stack(*items)}  # ruling R-B1


def word_page(words: dict[str, str]) -> dict[str, Any]:  # the "What these words mean" page
    lines = "\n".join(f"- **{term}**: {meaning}" for term, meaning in words.items())  # one line per term
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
    "       date_format(opened_at, 'yyyy-MM-dd HH:mm') AS case_opened_at",  # when the case opened, as text (R-B4)
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
        (counter("open_count", "Open cases you can see, waiting for a verdict", "open_case_count", ("open_cases", "Open cases")), GRID_WIDTH, 2),  # the reader's own count (D8)
        (table("open_table", "Open cases, newest hour first, most suspicious first", "open_cases", [  # the queue
            ("simulated_hour", "Simulated hour", "integer"), ("risk_score", "Risk score", "float"), ("payment", "Payment", "string"),  # what
            ("paying_account", "Paying account", "string"), ("receiving_account", "Receiving account", "string"),  # who
            ("case_opened_at", "Case opened at (UTC)", "string")],  # when, as SQL text (ruling R-B4)
            "Each row is one flagged payment still waiting for its verdict. Managers see 0 and an "  # the sentence
            "empty table here: open cases are shown to reviewers and engineers only. "  # row filter, explained (D8)
            "Anyone who may not see account names sees REDACTED."), GRID_WIDTH, 8),  # masks
    )  # end queue
    outcomes = page("outcomes", "How did the reviews turn out?",  # page 2
        (bar("outcomes_bar", "Confirmed fraud and false alarms per simulated hour", "review_outcomes",  # stacked bars
             ("simulated_hour", "Simulated hour"), ("cases", "Cases"),  # axes
             "Each bar is one simulated hour, split into confirmed fraud and false alarms. "  # the sentence
             f"Only hours whose verdicts are in have a bar; newer hours are {WAITING}.",  # waiting
             color=("outcome", "Verdict"), values=("Confirmed fraud", "False alarm")), GRID_WIDTH, 6),  # by verdict
    )  # end outcomes
    model = page("model", "Is the model still good?",  # page 3
        (counter("flagged_share", "Of the payments we flagged, how many were really fraud", "model_totals",  # share 1
                 ("share_flagged_that_were_fraud", "Share that were fraud")), 2, 2),  # 0.139 after run E
        (counter("caught_share", "Of all the fraud, how much we caught", "model_totals",  # share 2
                 ("share_of_fraud_caught", "Share of fraud caught")), 2, 2),  # 0.493 after run E
        (counter("hours_waiting", f"Hours still {WAITING}", "model_totals", ("hours_waiting", "Hours")), 2, 2),  # waiting
        (text("totals_how", f"**{HOW_TO_READ}** The first two numbers cover every hour whose verdicts are in. "  # the line
                            "0.14 means 14 out of every 100."), GRID_WIDTH, 1),  # reading a share
        (table("totals_table", "The counts behind those shares", "model_totals", [  # the counts
            ("confirmed_fraud", "Confirmed fraud", "integer"), ("checked_cases", "Flagged payments with a verdict", "integer"),  # flagged
            ("all_fraud", "All fraud in those hours", "integer")],  # every fraud
            "Confirmed fraud divided by flagged payments with a verdict gives the first share; "  # the sentence
            "divided by all fraud, the second."), GRID_WIDTH, 2),  # how the shares are made
        (bar("flagged_bar", "Of the payments we flagged, how many were really fraud, per simulated hour", "model_by_hour",  # per hour
             ("simulated_hour", "Simulated hour"), ("share_flagged_that_were_fraud", "Share that were fraud"),  # axes
             f"Each bar is one simulated hour, coloured by model version. Taller is better. Hours with no bar are {WAITING}.",  # the sentence
             color=("model_version", "Model version"), aggregate="AVG"), GRID_WIDTH, 5),  # one bar per hour
        (bar("caught_bar", "Of all the fraud, how much we caught, per simulated hour", "model_by_hour",  # per hour
             ("simulated_hour", "Simulated hour"), ("share_of_fraud_caught", "Share of fraud caught"),  # axes
             f"Each bar is one simulated hour. Taller is better. Hours with no bar are {WAITING}, or had no fraud at all.",  # the sentence
             color=("model_version", "Model version"), aggregate="AVG"), GRID_WIDTH, 5),  # one bar per hour
    )  # end model
    return {"datasets": [OPEN_CASES, OPEN_CASE_COUNT, REVIEW_OUTCOMES, MODEL_BY_HOUR, MODEL_TOTALS],  # five datasets
            "pages": [queue, outcomes, model, word_page(WORD_LIST)],  # four pages
            "uiSettings": {"theme": THEME}}  # spec §4.1


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
             ("minutes_taken", "Minutes"),  # up
             "Each bar is one run, placed at the time it started. Taller means slower. "  # the sentence
             "Databricks records a run up to an hour after it ends, but the job refreshes this page as it ends, "  # system table lag (R3)
             "so its newest run is missing until you click Refresh an hour later.",  # D7: in-job refresh is one run behind
             color=("job_name", "Job"), x_scale="temporal"), GRID_WIDTH, 5),  # by job
        (table("run_table", "Every job run and how it ended", "job_runs", [  # the run list
            ("job_name", "Job", "string"), ("run_started_at", "Started (UTC)", "string"), ("minutes_taken", "Minutes", "float"),  # what and how long
            ("outcome", "How it ended", "string")],  # result
            "Anything other than Succeeded is a run that needs a look."), GRID_WIDTH, 5),  # failures
        (bar("task_minutes", "Minutes per task in each run of fraud-ingest", "task_times", ("run_started_at", "Run started (UTC)"),  # per task
             ("task_minutes", "Minutes"),  # up
             "Each bar is one run, split into its tasks. The tallest part is where the time goes. "  # the sentence
             "The two dashboard refreshes run side by side, so a bar can be taller than the run itself.",  # review M4
             color=("task_name", "Task"), x_scale="temporal"), GRID_WIDTH, 5),  # stacked by task
        (bar("pipeline_minutes", "Minutes the cleaning pipeline itself spent per update", "pipeline_updates",  # per update
             ("update_started_at", "Update started (UTC)"), ("minutes_taken", "Minutes"),  # axes
             "Compare with the silver task above: the difference is the time spent starting up and waiting, not cleaning.",  # G-15 story
             color=("update_kind", "Kind of update"), values=("New rows only", "Full rebuild"), x_scale="temporal"), GRID_WIDTH, 5),  # by kind
    )  # end jobs
    data = page("data", "Is the data fresh and clean?",  # page 2
        (table("freshness_table", "Newest simulated hour at each stage", "freshness", [  # four stages
            ("stage", "Stage", "string"), ("newest_simulated_hour", "Newest simulated hour", "integer")],  # stage and hour
            "After a run all four numbers should be equal. A lower number shows where payments are stuck."), GRID_WIDTH, 4),  # D3: height 3 clipped row 4
        (counter("typical_wait", "Typical minutes from landing to scored", "wait",  # half waited less
                 ("typical_minutes", "Minutes")), 3, 2),  # latest run
        (counter("longest_wait", "Longest minutes from landing to scored", "wait",  # the slowest payment
                 ("longest_minutes", "Minutes")), 3, 2),  # latest run
        (text("wait_how", f"**{HOW_TO_READ}** Both numbers cover the latest scoring run only. Half of its payments "  # the line
                          "waited less than the typical number."), GRID_WIDTH, 1),  # plain words for the middle value
        (table("rejections_table", "Rows set aside, by reason", "rejections", [  # the shelf
            ("reason", "Why it was set aside", "string"), ("rows_rejected", "Rows", "integer"),  # reason and count
            ("first_hour", "First simulated hour", "integer"), ("last_hour", "Last simulated hour", "integer")],  # range
            "Each row is one reason a payment record failed a basic check. "  # the sentence
            "Set-aside rows are kept for checking, never scored."), GRID_WIDTH, 3),  # what happens to them
    )  # end data
    return {"datasets": [JOB_RUNS, TASK_TIMES, PIPELINE_UPDATES, FRESHNESS, WAIT, REJECTIONS],  # six datasets
            "pages": [jobs, data, word_page({**WORD_LIST, **PLATFORM_WORDS})],  # three pages
            "uiSettings": {"theme": THEME}}  # spec §4.1


DASHBOARDS: dict[str, Callable[[], dict[str, Any]]] = {  # bundle resource key (and file name) -> builder
    "fraud_operations": operations_dashboard,  # dashboards/fraud_operations.lvdash.json
    "platform_health": platform_dashboard,  # dashboards/platform_health.lvdash.json
}  # end DASHBOARDS
