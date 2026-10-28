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
    "Simulated hour": "One hour of the replayed month of payments, numbered from 1 to 743. "  # the counter...
                      "Hour 1 is day 1, midnight to 1 am; hour 480 is day 20, 11 pm.",  # step
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
    "Run detail": "A page showing one job run task by task. Open it from a run's bar: right-click, then Drill to.",  # drill-through page
}  # end PLATFORM_WORDS
JARGON = ("precision", "recall", "latency", "p95", "drift", "sla", "throughput", "f1", "auc",  # model and operations jargon
          "percentile", "median", "idempotent", "cardinality", "etl")  # data jargon (CI guard on all visible text)
HOW_TO_READ = "How to read it:"  # starts every chart's description (ruling R-B3)
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
FAILED_OUTCOMES = ("Error", "Failed", "Timed Out", "Canceled", "Cancelled", "Skipped", "Upstream Failed", "Blocked")  # run results shown with ✕
MEANING: dict[str, str] = {  # spec §4.2: value -> its colour on every chart
    "✓ Succeeded": GOOD, "Up to date": GOOD,  # good
    "Confirmed fraud": BAD, "Missed": BAD, "Behind": BAD,  # bad
    **{f"✕ {outcome}": BAD for outcome in FAILED_OUTCOMES},  # every failed run
    "✕ Canceled": "#8C96A5", "✕ Cancelled": "#8C96A5",  # stopped on purpose: grey, not red (owner 2026-10-27)
    "↻ Still running": WAIT_AMBER,  # in progress
    "False alarm": "#B8C4D4",  # neutral grey
    "Caught": "#2A78D6", "Each hour": "#2A78D6", "New rows only": "#2A78D6", "Slowest task": "#2A78D6",  # main blue
    "Average, all hours": "#898781",  # reference grey
    "Full rebuild": "#EB6834",  # orange
    "Other tasks": "#A9C3E6",  # light blue tint
}  # end MEANING
TINT_GREEN, TINT_RED, TINT_BLUE_DARK, TINT_BLUE_LIGHT = "#DDF3E2", "#FBE3E1", "#B9D3F2", "#DCE9F9"  # cell-rule tints
TINT_AMBER, TINT_GREY, TINT_SKY, TINT_LILAC = "#FDF0D2", "#ECEEF2", "#DFF1F7", "#ECE8FB"  # status and job pastels
HOUR_EXAMPLE = "Hour 480 is day 20, 11 pm; each day has 24 hours."  # owner choice 8: hours a person can read


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


HOUR_AXIS_TITLE = "Simulated hour (24 per day: hour 480 = day 20, 23:00)"  # D11 recheck: the axis explains itself


def _readable_hours(x_field: str, encodings: dict[str, Any], fields: list[dict[str, str]],  # an hour axis people can read
                    hover: bool = True) -> None:  # lines skip the hover field: it split the line into dots
    if x_field != "simulated_hour":  # only per-hour charts
        return  # nothing to add
    encodings["x"]["axis"]["title"] = HOUR_AXIS_TITLE  # the numbering, on the axis
    if not hover:  # a line chart
        return  # axis title only
    encodings["extra"] = [{"fieldName": "day_and_time", "displayName": "Day and time (simulated)"}]  # hover shows "Day 20, 23:00"
    fields.append(_field("day_and_time"))  # read it too (same grain: one value per hour)


def bar(name: str, title: str, dataset_name: str, x: tuple[str, str], y: tuple[str, str], how: str,  # chart, data, axes (column, label)
        color: tuple[str, str] | None = None, values: tuple[str, ...] = (), aggregate: str | None = "SUM",  # colour split, pins, sum
        x_scale: str = "quantitative", horizontal: bool = False, sort_by_value: bool = False) -> dict[str, Any]:  # options
    y_field = _field(y[0], aggregate)  # the bar length
    how = f"{how} {HOUR_EXAMPLE}" if "simulated_hour" in x[0] + y[0] else how  # hours explained under the chart
    fields = [_field(x[0]), y_field] + ([_field(color[0])] if color else [])  # columns the chart needs
    across = _axis(x[0], x[1], x_scale, sort_by_value)  # the category or time axis
    length = _axis(y_field["name"], y[1], "quantitative")  # the number axis
    encodings: dict[str, Any] = {"x": length, "y": across} if horizontal else {"x": across, "y": length}  # horizontal swaps
    if color:  # split each bar by a category
        encodings["color"] = {"fieldName": color[0], "displayName": color[1],  # legend...
                              "scale": {"type": "categorical", "mappings": _mappings(values)}}  # ...with meaning colours
    _readable_hours(x[0], encodings, fields)  # owner choice 8 on the axis itself
    spec = {"version": 3, "widgetType": "bar", "frame": _frame(title, _how(how)), "encodings": encodings}  # the chart
    return {"name": name, "queries": _queries(dataset_name, fields, aggregate is None), "spec": spec}  # the widget


def line(name: str, title: str, dataset_name: str, x: tuple[str, str], y: tuple[str, str], how: str,  # chart, data, axes
         color: tuple[str, str], values: tuple[str, ...], x_scale: str = "quantitative") -> dict[str, Any]:  # one line per series
    fields = [_field(x[0]), _field(y[0]), _field(color[0])]  # one row per point, already computed in SQL
    how = f"{how} {HOUR_EXAMPLE}" if "simulated_hour" in x[0] + y[0] else how  # hours explained under the chart
    encodings = {"x": _axis(x[0], x[1], x_scale), "y": _axis(y[0], y[1], "quantitative"),  # across and up
                 "color": {"fieldName": color[0], "displayName": color[1],  # one line per series...
                           "scale": {"type": "categorical", "mappings": _mappings(values)}}}  # ...in its meaning colour
    _readable_hours(x[0], encodings, fields, hover=False)  # owner choice 8 on the axis itself
    spec = {"version": 3, "widgetType": "line", "frame": _frame(title, _how(how)), "encodings": encodings}  # the chart
    return {"name": name, "queries": _queries(dataset_name, fields, True), "spec": spec}  # the widget


NUMBER_FORMATS: dict[str, dict[str, Any]] = {  # table number kinds -> documented format (D3: 4.600 showed)
    "integer": {"type": "number-plain", "abbreviation": "none",  # whole numbers, in the shape...
                "decimalPlaces": {"type": "exact", "places": 0}, "hideGroupSeparator": True},  # ...the UI exports
    "float": {"type": "number-plain", "abbreviation": "none",  # one decimal place (D11: "number" showed 17.20)...
              "decimalPlaces": {"type": "exact", "places": 1}, "hideGroupSeparator": True},  # ...as exported
}  # end NUMBER_FORMATS


def cell_rule(op: str, value: str, tint: str) -> dict[str, Any]:  # one conditional cell colour
    return {"condition": {"operand": {"type": "data-value", "value": value}, "operator": op},  # when it applies
            "backgroundColor": tint}  # bare hex string, as the UI exports it (D11: {"hex": ...} was dropped)


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
    if "format" not in shown:  # a plain count
        shown["format"] = {"type": "number-plain", "abbreviation": "none",  # 2,511, never 2.51K (D11 recheck)
                           "decimalPlaces": {"type": "max", "places": 1}}  # whole numbers stay whole
    encodings: dict[str, Any] = {"value": shown}  # what is shown
    fields = [value_field]  # what is read
    if target:  # a comparison number
        fields.append(_field(target[0], aggregate))  # read it too
        encodings["target"] = {"fieldName": fields[-1]["name"], "displayName": target[1],  # Databricks colours the change...
                               "format": shown["format"]}  # ...shown like the value (D11: a bare 0.14 under 17%)
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


def _day_and_time(hour: str) -> str:  # SQL: 480 -> "Day 20, 23:00 (hour 480)" (owner choice 8)
    return (f"concat('Day ', CAST(floor(({hour} - 1) / 24) + 1 AS STRING), ', ',"  # the simulated day...
            f" lpad(CAST(({hour} - 1) % 24 AS STRING), 2, '0'), ':00 (hour ', CAST({hour} AS STRING), ')')")  # ...time, and the hour kept


# ── Fraud operations: datasets (all three groups; filters and masks apply to the viewer) ──
OPEN_CASES = dataset("open_cases", "Open cases", sql(  # flagged payments still waiting for a verdict
    "SELECT step AS simulated_hour,",  # the hour
    f"       {_day_and_time('step')} AS day_and_time,",  # the same hour, readable
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
    f"SELECT step AS simulated_hour, {_day_and_time('step')} AS day_and_time, 'Confirmed fraud' AS outcome, confirmed_fraud AS cases",  # fraud
    "FROM workspace.fraud.alert_summary_hourly WHERE closed_cases > 0",  # hours with verdicts
    "UNION ALL",  # stacked with
    f"SELECT step, {_day_and_time('step')}, 'False alarm', false_alarms",  # honest payments
    "FROM workspace.fraud.alert_summary_hourly WHERE closed_cases > 0",  # hours with verdicts
))  # end REVIEW_OUTCOMES
PER_HOUR = (  # one row per hour with verdicts, shares made from counts (review I2)
    "WITH per_hour AS (SELECT step,",  # the hour
    "                         SUM(confirmed_fraud) AS caught,",  # real fraud we flagged
    "                         SUM(closed_cases) AS flagged_with_verdict,",  # flagged payments with a verdict
    "                         MAX(fraud_in_hour) AS fraud_in_hour,",  # every fraud that hour, counted once
    "                         try_divide(SUM(confirmed_fraud), SUM(closed_cases)) AS share_flagged",  # share 1
    "                  FROM workspace.fraud.model_accuracy_by_hour",  # the model view
    "                  WHERE verdicts_ready",  # waiting hours have no point, never a zero
    "                  GROUP BY step)",  # one row per hour, however many model versions
)  # end PER_HOUR
MODEL_BY_HOUR = dataset("model_by_hour", "Percent flagged that were fraud, per hour", sql(*PER_HOUR,  # the share line
    f"SELECT step AS simulated_hour, {_day_and_time('step')} AS day_and_time, 'Each hour' AS series,",  # one point per hour
    "       ROUND(100 * share_flagged, 1) AS percent_flagged_that_were_fraud",  # 0.139 -> 13.9
    "FROM per_hour",  # every ready hour
    "UNION ALL",  # with the flat reference line
    f"SELECT step, {_day_and_time('step')}, 'Average, all hours',",  # same hours
    "       ROUND(100 * try_divide(SUM(caught) OVER (), SUM(flagged_with_verdict) OVER ()), 1)",  # fixed: every ready hour
    "FROM per_hour",  # the same rows
))  # end MODEL_BY_HOUR
FRAUD_CAUGHT_BY_HOUR = dataset("fraud_caught_by_hour", "Fraud caught and missed, per hour", sql(*PER_HOUR,  # the stacked bars
    f"SELECT step AS simulated_hour, {_day_and_time('step')} AS day_and_time, 'Caught' AS result, caught AS payments FROM per_hour",  # flagged and fraud
    "UNION ALL",  # stacked on
    f"SELECT step, {_day_and_time('step')}, 'Missed', fraud_in_hour - caught FROM per_hour",  # fraud we did not flag
))  # end FRAUD_CAUGHT_BY_HOUR
MODEL_TOTALS = dataset("model_totals", "Model results so far", sql(  # every hour with verdicts, together (ruling R8)
    "WITH ready AS (SELECT * FROM workspace.fraud.model_accuracy_by_hour WHERE verdicts_ready),",  # hours with verdicts
    "     hours AS (SELECT DISTINCT step, fraud_in_hour FROM ready),",  # fraud once per hour
    "     recent AS (SELECT * FROM ready WHERE step > (SELECT MAX(step) FROM ready) - 24),",  # newest 24 ready hours (Review Focus 3)
    "     recent_hours AS (SELECT DISTINCT step, fraud_in_hour FROM recent),",  # their fraud, once per hour
    "     totals AS (SELECT (SELECT SUM(confirmed_fraud) FROM ready) AS confirmed_fraud,",  # real fraud flagged
    "                       (SELECT SUM(closed_cases) FROM ready) AS checked_cases,",  # flagged with a verdict
    "                       (SELECT SUM(fraud_in_hour) FROM hours) AS all_fraud,",  # every fraud in those hours
    "                       (SELECT SUM(confirmed_fraud) FROM recent) AS recent_fraud,",  # newest 24 hours: fraud flagged
    "                       (SELECT SUM(closed_cases) FROM recent) AS recent_checked,",  # ...flagged with a verdict
    "                       (SELECT SUM(fraud_in_hour) FROM recent_hours) AS recent_all_fraud,",  # ...every fraud
    "                       (SELECT hours_waiting FROM workspace.fraud.hours_waiting_for_verdicts) AS hours_waiting)",  # review I1
    "SELECT confirmed_fraud, checked_cases, all_fraud, hours_waiting,",  # the counts
    "       ROUND(try_divide(confirmed_fraud, checked_cases), 3) AS share_flagged_that_were_fraud,",  # 0.139 after run E
    "       ROUND(try_divide(confirmed_fraud, all_fraud), 3) AS share_of_fraud_caught,",  # 0.493 after run E
    "       ROUND(try_divide(recent_fraud, recent_checked), 3) AS newest_24h_share_flagged_that_were_fraud,",  # newest 24 hours
    "       ROUND(try_divide(recent_fraud, recent_all_fraud), 3) AS newest_24h_share_of_fraud_caught",  # newest 24 hours
    "FROM totals",  # one row
))  # end MODEL_TOTALS


# ── Fraud operations: pages ───────────────────────────────────
def operations_dashboard() -> dict[str, Any]:  # "Fraud operations": reviewers, managers, engineers
    queue = page("queue", "What is waiting for review?",  # page 1
        (counter("open_count", "Open cases you can see, waiting for a verdict", "open_case_count", ("open_cases", "Open cases")), GRID_WIDTH, 2),  # the reader's own count (D8)
        (table("open_table", "Open cases, newest hour first, most suspicious first", "open_cases", [  # the queue
            ("simulated_hour", "Simulated hour", "integer"), ("day_and_time", "Day and time (simulated)", "string"), ("risk_score", "Risk score", "float"), ("payment", "Payment", "string"),  # what
            ("paying_account", "Paying account", "string"), ("receiving_account", "Receiving account", "string"),  # who
            ("case_opened_at", "Case opened at (UTC)", "string")],  # when, as SQL text (ruling R-B4)
            "Each row is one flagged payment still waiting for its verdict. Managers see 0 and an "  # the sentence
            "empty table here: open cases are shown to reviewers and engineers only. "  # row filter, explained (D8)
            "Anyone who may not see account names sees REDACTED."), GRID_WIDTH, 8),  # masks
    )  # end queue
    outcomes = page("outcomes", "How did the reviews turn out?",  # page 2
        (header("outcomes_header", "How did the reviews turn out?",  # the question...
                "Every flagged payment gets a verdict 3 simulated days later. Drag the slider or click a bar to "  # ...and
                "narrow the totals and the chart together; right-click a bar, then Drill to, to see that hour "  # how to use the page...
                "on the model page."), 4, 2),  # ...and reach the model page (D15b)
        (range_slider("outcomes_hours", "Simulated hours (24 per day)", [("review_outcomes", "simulated_hour")]), 2, 2),  # narrows the page
        (counter("fraud_total", "Confirmed fraud", "review_outcomes", ("cases", "Confirmed fraud"),  # 405 on all hours
                 "Flagged payments that really were fraud, in the hours shown.", aggregate="SUM",  # what it counts
                 where="`outcome` = 'Confirmed fraud'"), 3, 2),  # one verdict
        (counter("false_alarm_total", "False alarms", "review_outcomes", ("cases", "False alarms"),  # 2,511 on all hours
                 "Flagged payments that turned out to be honest, in the hours shown.", aggregate="SUM",  # what it counts
                 where="`outcome` = 'False alarm'"), 3, 2),  # the other verdict
        (bar("outcomes_bar", "Verdicts per simulated hour", "review_outcomes",  # stacked bars
             ("simulated_hour", "Simulated hour"), ("cases", "Cases"),  # axes
             "Each bar is one simulated hour, split into confirmed fraud (red) and false alarms (grey). "  # the sentence
             f"Only hours whose verdicts are in have a bar; newer hours are {WAITING}.",  # waiting
             color=("outcome", "Verdict"), values=("Confirmed fraud", "False alarm")), GRID_WIDTH, 6),  # by verdict
    )  # end outcomes
    model = page("model", "Is the model still good?",  # page 3
        (header("model_header", "Is the model still good?",  # the question...
                "The slider and the hour picker narrow the two charts. The big numbers always cover every hour whose "  # ...what moves
                "verdicts are in, and the shares compare the newest 24 of those hours with all of them."), GRID_WIDTH, 2),  # ...and what the shares mean
        (range_slider("model_hours", "Simulated hours (24 per day)", [("model_by_hour", "simulated_hour"),  # narrows the line...
                                                         ("fraud_caught_by_hour", "simulated_hour")]), 3, 2),  # ...and the bars
        (single_select("model_hour_pick", "One simulated hour", [("review_outcomes", "simulated_hour"),  # filled by a drill from reviews (D15b)
                                                                 ("model_by_hour", "simulated_hour"),  # narrows the line...
                                                                 ("fraud_caught_by_hour", "simulated_hour")]), 3, 2),  # ...and the bars
        (counter("flagged_share", "Flagged payments that were fraud, newest 24 hours with verdicts", "model_totals",  # share 1
                 ("newest_24h_share_flagged_that_were_fraud", "Newest 24 hours"),  # the value
                 "Of the payments we flagged, how many were really fraud, compared with all hours.",  # the comparison
                 percent=True, target=("share_flagged_that_were_fraud", "All hours")), 2, 3),  # 14% after run E
        (counter("caught_share", "Fraud we caught, newest 24 hours with verdicts", "model_totals",  # share 2
                 ("newest_24h_share_of_fraud_caught", "Newest 24 hours"),  # the value
                 "Of all the fraud, how much we flagged, compared with all hours.",  # the comparison
                 percent=True, target=("share_of_fraud_caught", "All hours")), 2, 3),  # 49% after run E
        (counter("hours_waiting", f"Hours still {WAITING}", "model_totals", ("hours_waiting", "Hours"),  # 72 after run E
                 "Scored hours whose verdicts have not arrived yet."), 2, 3),  # review I1
        (counter("confirmed_count", "Confirmed fraud, all hours", "model_totals", ("confirmed_fraud", "Payments"),  # 405
                 "Flagged payments that really were fraud."), 2, 2),  # count 1
        (counter("checked_count", "Flagged payments with a verdict, all hours", "model_totals",  # 2,916
                 ("checked_cases", "Payments"), "The first share divides confirmed fraud by this."), 2, 2),  # count 2
        (counter("fraud_count", "All fraud in those hours", "model_totals", ("all_fraud", "Payments"),  # 822
                 "The second share divides confirmed fraud by this."), 2, 2),  # count 3
        (line("flagged_line", "Percent of flagged payments that were fraud, per simulated hour", "model_by_hour",  # the share line
              ("simulated_hour", "Simulated hour"), ("percent_flagged_that_were_fraud", "Percent that were fraud"),  # axes
              "The blue line is each hour; the grey line is the average over every hour with verdicts and stays put "  # the sentence
              f"when you move the slider. Higher is better. Newer hours are {WAITING} and are not drawn yet.",  # waiting
              color=("series", "Line"), values=("Each hour", "Average, all hours")), GRID_WIDTH, 6),  # blue and grey
        (bar("caught_bar", "Fraud caught and missed, per simulated hour", "fraud_caught_by_hour",  # stacked bars
             ("simulated_hour", "Simulated hour"), ("payments", "Fraud payments"),  # axes
             "Each bar is all the fraud in one simulated hour: blue was flagged for review, red slipped through. "  # the sentence
             f"Hours with no bar are {WAITING}, or had no fraud at all.",  # waiting or nothing to catch
             color=("result", "Result"), values=("Caught", "Missed")), GRID_WIDTH, 6),  # blue and red
    )  # end model
    return {"datasets": [OPEN_CASES, OPEN_CASE_COUNT, REVIEW_OUTCOMES, MODEL_BY_HOUR, FRAUD_CAUGHT_BY_HOUR, MODEL_TOTALS],  # six datasets
            "pages": [queue, outcomes, model, word_page(WORD_LIST)],  # four pages
            "uiSettings": {"theme": THEME}}  # spec §4.1


# ── Platform health: datasets (engineers only) ────────────────
def _plain_outcome(column: str) -> str:  # SUCCEEDED -> ✓ Succeeded, TIMED_OUT -> ✕ Timed Out, empty -> ↻ Still running
    return (f"CASE WHEN {column} IN ('SUCCEEDED', 'COMPLETED') THEN '✓ Succeeded'"  # jobs say SUCCEEDED, pipelines COMPLETED
            f" WHEN {column} IS NULL THEN '↻ Still running'"  # no result yet (Review Focus 1)
            f" ELSE concat('✕ ', initcap(replace({column}, '_', ' '))) END")  # every other result needs a look


def _run_label(started: str) -> str:  # "10-19 04:53 ingest": start time plus short job name (Review Focus 5)
    return f"concat(date_format({started}, 'MM-dd HH:mm'), ' ', replace(job_name, 'fraud-', ''))"  # SQL expression


JOB_RUNS = dataset("job_runs", "Job runs", sql(  # one row per run, oldest first
    f"SELECT DISTINCT {_run_label('run_started_at')} AS run_label,",  # one bar per run, alphabetical = by time
    "       job_name,",  # which job
    "       date_format(run_started_at, 'yyyy-MM-dd HH:mm') AS started,",  # as text (ruling R-B4)
    f"       minutes_taken, {_plain_outcome('outcome')} AS outcome",  # how long and how it ended
    "FROM workspace.fraud.job_run_times",  # the jobs view (one row per task, hence DISTINCT)
    "ORDER BY started",  # oldest to newest
))  # end JOB_RUNS
NEWEST_RUN = dataset("newest_run", "Newest fraud-ingest run", sql(  # one row (ruling R-B5)
    f"SELECT DISTINCT date_format(run_started_at, 'yyyy-MM-dd HH:mm') AS started, minutes_taken, {_plain_outcome('outcome')} AS outcome",  # its columns
    "FROM workspace.fraud.job_run_times",  # the jobs view
    "WHERE job_name = 'fraud-ingest'",  # the loading job...
    "  AND run_started_at = (SELECT MAX(run_started_at) FROM workspace.fraud.job_run_times WHERE job_name = 'fraud-ingest')",  # ...newest run
))  # end NEWEST_RUN
TASK_TIMES = dataset("task_times", "Task minutes", sql(  # one row per task of each fraud-ingest run
    f"SELECT {_run_label('run_started_at')} AS run_label, task_name, task_minutes",  # same label as job_runs, for the picker
    "FROM workspace.fraud.job_run_times",  # the jobs view
    "WHERE job_name = 'fraud-ingest' AND task_name IS NOT NULL",  # the loading job's tasks
))  # end TASK_TIMES
NEWEST_RUN_TASKS = dataset("newest_run_tasks", "Tasks of the newest run", sql(  # where the newest run spent its time
    "WITH tasks AS (SELECT task_name, task_minutes FROM workspace.fraud.job_run_times",  # the jobs view
    "               WHERE job_name = 'fraud-ingest' AND task_name IS NOT NULL",  # the loading job's tasks...
    "                 AND run_started_at = (SELECT MAX(run_started_at) FROM workspace.fraud.job_run_times WHERE job_name = 'fraud-ingest'))",  # ...newest run
    "SELECT task_name, task_minutes,",  # each task
    "       CASE WHEN task_minutes = MAX(task_minutes) OVER () THEN 'Slowest task' ELSE 'Other tasks' END AS task_kind",  # highlight one
    "FROM tasks",  # the newest run's tasks
))  # end NEWEST_RUN_TASKS
PIPELINE_UPDATES = dataset("pipeline_updates", "Pipeline updates", sql(  # one row per update, oldest first
    "SELECT date_format(update_started_at, 'MM-dd HH:mm') AS update_label,",  # one bar per update
    f"       minutes_taken, {_plain_outcome('outcome')} AS outcome,",  # how long and how it ended
    "       CASE WHEN full_rebuild THEN 'Full rebuild' ELSE 'New rows only' END AS update_kind",  # plain kind
    "FROM workspace.fraud.pipeline_update_times",  # the pipeline view
    "ORDER BY update_started_at",  # oldest to newest
))  # end PIPELINE_UPDATES
FRESHNESS = dataset("freshness", "Newest hour at each stage", sql(  # one row per stage
    "WITH stages AS (",  # each stage beside the landing folder's hour
    "  SELECT '1. Copied to the landing folder' AS stage, newest_hour_released AS hour, newest_hour_released AS released FROM workspace.fraud.data_freshness",  # release
    "  UNION ALL SELECT '2. Loaded', newest_hour_ingested, newest_hour_released FROM workspace.fraud.data_freshness",  # Bronze
    "  UNION ALL SELECT '3. Scored by the model', newest_hour_scored, newest_hour_released FROM workspace.fraud.data_freshness",  # scoring
    "  UNION ALL SELECT '4. Flagged for review', newest_hour_flagged, newest_hour_released FROM workspace.fraud.data_freshness)",  # Gold
    "SELECT stage, hour AS newest_simulated_hour, released - hour AS hours_behind,",  # how far each stage lags
    f"       {_day_and_time('hour')} AS newest_day_and_time,",  # the newest hour, readable
    "       CASE WHEN released - hour = 0 THEN 'Up to date' ELSE 'Behind' END AS stage_status",  # Review Focus 2
    "FROM stages",  # four rows
    "ORDER BY stage",  # in pipeline order
))  # end FRESHNESS
WAIT = dataset("wait", "Wait from landing to scored", sql(  # the latest run's waits
    "SELECT median_minutes_landing_to_scored AS typical_minutes,",  # half waited less
    "       slowest_minutes_landing_to_scored AS longest_minutes",  # the slowest payment
    "FROM workspace.fraud.data_freshness",  # one row
))  # end WAIT
REJECTIONS = dataset("rejections", "Rows set aside", sql(  # one row per reason, in plain words
    "SELECT CASE reason " + " ".join(f"WHEN '{code}' THEN '{words}'" for code, words in REASON_WORDS.items()),  # plain reason
    "            ELSE reason END AS reason,",  # an unknown code shows as is
    f"       rows_rejected, {_day_and_time('first_hour')} AS first_day_and_time,",  # count and first hour, readable
    f"       {_day_and_time('last_hour')} AS last_day_and_time",  # last hour, readable
    "FROM workspace.fraud.rejected_rows_by_reason",  # the shelf summary
    "ORDER BY rows_rejected DESC",  # biggest first
))  # end REJECTIONS
OUTCOMES = ("✓ Succeeded", "↻ Still running", *(f"✕ {o}" for o in FAILED_OUTCOMES))  # every outcome pin
RUN_COLUMNS = [("run_label", "Run (UTC)", "string"), ("job_name", "Job", "string"),  # which run
               ("minutes_taken", "Minutes", "float"), ("outcome", "How it ended", "string")]  # how long, how it ended
SLOW_RUN = {"minutes_taken": [cell_rule(">=", "10", TINT_BLUE_DARK), cell_rule(">=", "5", TINT_BLUE_LIGHT)]}  # slow runs stand out
OUTCOME_TINTS = {"outcome": [cell_rule("contains", "Succeeded", TINT_GREEN),  # text rules need contains (owner probe)
                             cell_rule("contains", "Still running", TINT_AMBER),  # in progress
                             cell_rule("contains", "Cancel", TINT_GREY),  # stopped on purpose, before the red rule
                             cell_rule("contains", "✕", TINT_RED)]}  # every other result needs a look
JOB_TINTS = {"job_name": [cell_rule("contains", "fraud-ingest", TINT_SKY),  # told apart...
                          cell_rule("contains", "fraud-train", TINT_LILAC)]}  # ...never good or bad (owner choice 9)
RUN_RULES = {**SLOW_RUN, **OUTCOME_TINTS, **JOB_TINTS}  # every run list


# ── Platform health: pages ────────────────────────────────────
def platform_dashboard() -> dict[str, Any]:  # "Platform health": engineers only
    jobs = page("jobs", "Are the jobs healthy?",  # page 1
        (header("jobs_header", "Are the jobs healthy?",  # the question...
                "Green runs succeeded, red ones need a look. Click a run or a legend entry to narrow the table below; "  # ...and how
                "right-click a run, then Drill to, to open it on the Run detail page."), GRID_WIDTH, 2),  # to use it
        (table("newest_run_table", "Newest fraud-ingest run", "newest_run", [  # one row (ruling R-B5)
            ("started", "Started (UTC)", "string"), ("minutes_taken", "Minutes", "float"), ("outcome", "How it ended", "string")],  # its columns
            "The loading job's latest run: when it started, how long it took and how it ended.", {**SLOW_RUN, **OUTCOME_TINTS}), GRID_WIDTH, 3),  # what it shows
        (bar("run_minutes", "Minutes per job run, oldest to newest", "job_runs", ("run_label", "Run, by start time (UTC)"),  # per run
             ("minutes_taken", "Minutes"),  # up
             "Each bar is one run, labelled with its start time and job. Taller means slower. "  # the sentence
             "Databricks records a run up to an hour after it ends, but the job refreshes this page as it ends, "  # system table lag (R3)
             "so its newest run is missing until you click Refresh an hour later.",  # D7: in-job refresh is one run behind
             color=("outcome", "How it ended"), values=OUTCOMES, x_scale="categorical"), GRID_WIDTH, 6),  # by result
        (bar("newest_tasks", "Where the time went in the newest run", "newest_run_tasks", ("task_name", "Task"),  # per task
             ("task_minutes", "Minutes"),  # across
             "Each bar is one task of the newest run; the slowest task is in full blue. "  # the sentence
             "The two dashboard refreshes run side by side, so the tasks can add up to more than the run.",  # review M4
             color=("task_kind", "Task"), values=("Slowest task", "Other tasks"), x_scale="categorical",  # highlight one
             horizontal=True, sort_by_value=True), GRID_WIDTH, 5),  # sorted bars
        (bar("pipeline_minutes", "Minutes the cleaning pipeline itself spent per update", "pipeline_updates",  # per update
             ("update_label", "Update started (UTC)"), ("minutes_taken", "Minutes"),  # axes
             "Compare with the silver task above: the difference is the time spent starting up and waiting, not cleaning.",  # G-15 story
             color=("update_kind", "Kind of update"), values=("New rows only", "Full rebuild"), x_scale="categorical"), GRID_WIDTH, 5),  # by kind
        (table("run_table", "Every job run and how it ended", "job_runs", RUN_COLUMNS,  # the run list
               "Anything other than ✓ Succeeded is a run that needs a look. Darker blue minutes are slower runs.",  # failures
               RUN_RULES), GRID_WIDTH, 6),  # minutes, outcome and job tints
    )  # end jobs
    data = page("data", "Is the data fresh and clean?",  # page 2
        (header("data_header", "Is the data fresh and clean?",  # the question...
                "After a run every stage should show the same simulated hour, and no rows should be set aside."), GRID_WIDTH, 2),  # ...what good looks like
        (counter("typical_wait", "Typical wait from landing to scored", "wait", ("typical_minutes", "Minutes"),  # half waited less
                 "Latest scoring run only. Half of its payments waited less than this.", unit="min"), 3, 2),  # plain words for the middle value
        (counter("longest_wait", "Longest wait from landing to scored", "wait", ("longest_minutes", "Minutes"),  # the slowest payment
                 "Latest scoring run only: the slowest payment.", unit="min"), 3, 2),  # latest run
        (bar("freshness_bar", "Newest simulated hour at each stage", "freshness", ("stage", "Stage"),  # per stage
             ("newest_simulated_hour", "Newest simulated hour"),  # across
             "Each bar is one stage, in pipeline order. Green stages are up to date; a red, shorter bar shows where "  # the sentence
             "payments are stuck.", color=("stage_status", "Status"), values=("Up to date", "Behind"),  # by status
             aggregate="MAX", x_scale="categorical", horizontal=True), GRID_WIDTH, 4),  # one value per stage
        (table("behind_table", "Hours behind the landing folder", "freshness", [  # the gap per stage
            ("stage", "Stage", "string"), ("newest_day_and_time", "Newest hour (simulated)", "string"),  # stage and hour
            ("hours_behind", "Hours behind", "integer")],  # the gap
            "0 on a green cell means the stage has caught up; a red cell shows how many hours it lags.",  # the sentence
            {"hours_behind": [cell_rule("=", "0", TINT_GREEN), cell_rule(">", "0", TINT_RED)]}), GRID_WIDTH, 4),  # green or red
        (table("rejections_table", "Rows set aside, by reason", "rejections", [  # the shelf
            ("reason", "Why it was set aside", "string"), ("rows_rejected", "Rows", "integer"),  # reason and count
            ("first_day_and_time", "First seen (simulated)", "string"), ("last_day_and_time", "Last seen (simulated)", "string")],  # range
            "Each row is one reason a payment record failed a basic check. "  # the sentence
            "Set-aside rows are kept for checking, never scored.",  # what happens to them
            {"rows_rejected": [cell_rule(">", "0", TINT_RED)]}), GRID_WIDTH, 3),  # any set-aside row is red
    )  # end data
    detail = page("run_detail", "Run detail",  # page 3, drill-through target
        (header("detail_header", "Run detail",  # the title...
                "Pick a run, or open one from a run's bar on the first page: right-click, then Drill to."), 4, 2),  # ...how to get here
        (single_select("detail_run", "Job run (UTC)", [("job_runs", "run_label"), ("task_times", "run_label")]), 2, 2),  # narrows both
        (table("detail_table", "The picked run", "job_runs", RUN_COLUMNS,  # its summary (ruling R-B5)
               "One row for the picked run; every run while none is picked.", RUN_RULES), GRID_WIDTH, 5),  # what it shows
        (bar("detail_tasks", "Where the time went in this run", "task_times", ("task_name", "Task"),  # per task
             ("task_minutes", "Minutes"),  # across
             "Each bar is one task of the picked run; the longest bar is where the time went. With no run picked it shows each task's "  # the sentence
             "average over all runs. Only fraud-ingest runs record their tasks here, so a fraud-train run shows no bars.", aggregate="AVG", x_scale="categorical", horizontal=True, sort_by_value=True), GRID_WIDTH, 5),  # sorted bars
    )  # end detail
    return {"datasets": [JOB_RUNS, NEWEST_RUN, TASK_TIMES, NEWEST_RUN_TASKS, PIPELINE_UPDATES, FRESHNESS, WAIT, REJECTIONS],  # eight datasets
            "pages": [jobs, data, detail, word_page({**WORD_LIST, **PLATFORM_WORDS})],  # four pages
            "uiSettings": {"theme": THEME}}  # spec §4.1


DASHBOARDS: dict[str, Callable[[], dict[str, Any]]] = {  # bundle resource key (and file name) -> builder
    "fraud_operations": operations_dashboard,  # dashboards/fraud_operations.lvdash.json
    "platform_health": platform_dashboard,  # dashboards/platform_health.lvdash.json
}  # end DASHBOARDS
