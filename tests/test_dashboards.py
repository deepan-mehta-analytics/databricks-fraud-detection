"""Guards on the two AI/BI dashboards (Phase 6a spec §5.2, §7): built from code, governed sources, plain words."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
import re                 # pattern checks
from pathlib import Path  # locate the files

import pytest             # parametrize
import yaml               # the bundle resource file

from fraud_monitoring import dashboards as d  # the dashboard builder

ROOT = Path(__file__).resolve().parents[1]  # repo root
BUILT = {key: build() for key, build in d.DASHBOARDS.items()}  # both dashboards, built once
SOURCES = {"fraud_operations": d.OPERATIONS_SOURCES, "platform_health": d.PLATFORM_SOURCES}  # what each may read
WORDS = {"fraud_operations": d.WORD_LIST, "platform_health": {**d.WORD_LIST, **d.PLATFORM_WORDS}}  # each word page


def query_text(dataset: dict) -> str:  # a dataset's SQL, in either export form
    return dataset.get("query") or "".join(dataset.get("queryLines", []))  # bundle-example form or newer UI export form


def widgets(dashboard: dict) -> list[dict]:  # every widget on every page
    return [item["widget"] for page in dashboard["pages"] for item in page["layout"]]  # flattened


def widget_text(widget: dict) -> str:  # a text box's Markdown, in either export form
    return widget.get("textbox_spec") or "\n".join(widget.get("multilineTextboxSpec", {}).get("lines", []))  # either


def visible_text(dashboard: dict) -> list[str]:  # every string a viewer reads
    out = [page["displayName"] for page in dashboard["pages"]]  # page titles
    for widget in widgets(dashboard):  # each widget
        out.append(widget_text(widget))  # text boxes
        spec = widget.get("spec", {})  # chart settings
        out += [spec.get("frame", {}).get("title", ""), spec.get("frame", {}).get("description", "")]  # titles
        for encoding in spec.get("encodings", {}).values():  # axes, colours, columns, values
            for entry in encoding if isinstance(encoding, list) else [encoding]:  # table columns are a list
                out += [entry.get("displayName", ""), entry.get("axis", {}).get("title", "")]  # labels
                out += [f.get("displayName", "") for f in entry.get("fields", [])]  # multi-series labels
    return [t for t in out if t]  # non-empty only


@pytest.mark.parametrize("key", list(d.DASHBOARDS))  # both dashboards
def test_committed_files_match_the_builder(key):  # ruling R7: the JSON never drifts from the commented code
    path = ROOT / "dashboards" / f"{key}.lvdash.json"  # committed file
    assert path.read_text(encoding="utf-8") == d.render(BUILT[key])  # rerun scripts/build_dashboards.py if this fails


@pytest.mark.parametrize("key", list(d.DASHBOARDS))  # both dashboards
def test_each_dashboard_reads_only_its_allowed_views(key):  # Review Focus 1: governed sources only
    for dataset in BUILT[key]["datasets"]:  # every dataset
        sql = query_text(dataset)  # its SQL
        tables = re.findall(r"\b(\w+)\.(\w+)\.(\w+)\b", sql)  # catalog.schema.table references
        assert tables, dataset["name"]  # reads something
        assert {(a, b) for a, b, _ in tables} == {("workspace", "fraud")}, dataset["name"]  # project schema only
        assert {t for _, _, t in tables} <= SOURCES[key], dataset["name"]  # only this audience's views
        assert "fraud_label" not in sql and "system." not in sql, dataset["name"]  # label and system tables stay in the views


def specs(dashboard: dict, *kinds: str) -> list[tuple[dict, dict]]:  # (widget, spec) pairs of the given types
    return [(w, w["spec"]) for w in widgets(dashboard) if w.get("spec", {}).get("widgetType") in kinds]  # filtered


@pytest.mark.parametrize("key", list(d.DASHBOARDS))  # both dashboards
def test_every_chart_has_a_how_to_read_description(key):  # owner plain-language rule; ruling R-B3
    charts = specs(BUILT[key], "bar", "line", "table")  # charts and tables
    assert charts  # each dashboard has some
    for widget, spec in charts:  # each
        assert spec["frame"].get("showDescription") is True, widget["name"]  # the sentence is shown
        assert spec["frame"].get("description", "").startswith(d.HOW_TO_READ), widget["name"]  # and reads as one


@pytest.mark.parametrize("key", list(d.DASHBOARDS))  # both dashboards
def test_each_dashboard_ends_with_the_word_list(key):  # owner plain-language rule: a way to look words up
    last = BUILT[key]["pages"][-1]  # the final page
    assert last["displayName"] == "What these words mean"  # plain title
    text = "\n".join(widget_text(item["widget"]) for item in last["layout"])  # its text
    for term, meaning in WORDS[key].items():  # every term
        assert f"**{term}**: {meaning}" in text, term  # term, colon, plain sentence (no em-dash)


@pytest.mark.parametrize("key", list(d.DASHBOARDS))  # both dashboards
def test_both_dashboards_carry_the_theme(key):  # spec §4.1
    assert BUILT[key]["uiSettings"]["theme"] == d.THEME  # the same theme on both
    assert d.THEME["fontColor"]["light"] == "#13294B"  # navy ink


WIDGET_VERSIONS = {"counter": 2, "table": 2, "bar": 3, "line": 3, "range-slider": 2, "filter-single-select": 2}  # reference table


@pytest.mark.parametrize("key", list(d.DASHBOARDS))  # both dashboards
def test_widget_versions_match_the_reference(key):  # Global Constraints: documented versions only
    for widget in widgets(BUILT[key]):  # each widget
        spec = widget.get("spec")  # text boxes have none
        if spec is None:  # a text box
            continue  # nothing to check
        assert WIDGET_VERSIONS.get(spec["widgetType"]) == spec["version"], widget["name"]  # known type, right version
        assert "secondary" not in str(spec["encodings"].get("y", {})), widget["name"]  # no second y-axis


@pytest.mark.parametrize("key", list(d.DASHBOARDS))  # both dashboards
def test_every_page_is_a_canvas_page(key):  # ruling R-B1
    assert all(p["pageType"] == "PAGE_TYPE_CANVAS" for p in BUILT[key]["pages"])  # every page
    assert all("layoutVersion" not in p for p in BUILT[key]["pages"])  # 6-column grid kept


def colour_mappings(dashboard: dict) -> list[dict]:  # every pinned colour on every chart
    out = []  # found mappings
    for _, spec in specs(dashboard, "bar", "line"):  # charts
        out += spec["encodings"].get("color", {}).get("scale", {}).get("mappings", [])  # by a colour column
        out += [f["color"] for e in spec["encodings"].values() if isinstance(e, dict)  # by a y series
                for f in e.get("fields", []) if "color" in f]  # (multi-field charts)
    return out  # all of them


@pytest.mark.parametrize("key", list(d.DASHBOARDS))  # both dashboards
def test_colour_mappings_use_bare_hex_meaning_colours(key):  # spec §4.2: bare hex is the honoured form
    for entry in colour_mappings(BUILT[key]):  # each pin
        if "value" in entry:  # a value -> colour mapping
            assert re.fullmatch(r"#[0-9A-F]{6}", entry["color"]), entry  # bare hex string
            assert entry["color"] == d.MEANING[entry["value"]], entry  # the meaning colour


@pytest.mark.parametrize("key", list(d.DASHBOARDS))  # both dashboards
def test_counters_never_carry_a_colour(key):  # reference: a counter colour renders "unsupported widget definition"
    for widget, spec in specs(BUILT[key], "counter"):  # each counter
        for part in ("value", "target"):  # both encodings
            assert "color" not in spec["encodings"].get(part, {}), widget["name"]  # never coloured


COLUMN_KEYS = {"fieldName", "displayName", "format", "style"}  # documented table v2 column keys used here


@pytest.mark.parametrize("key", list(d.DASHBOARDS))  # both dashboards
def test_tables_use_version_2_with_documented_keys(key):  # reference: table v2 needs only fieldName + displayName
    tables = specs(BUILT[key], "table")  # every table
    assert tables  # each dashboard has tables
    for widget, spec in tables:  # each
        fields = [f["name"] for f in widget["queries"][0]["query"]["fields"]]  # queried columns
        columns = spec["encodings"]["columns"]  # shown columns
        assert [c["fieldName"] for c in columns] == fields, widget["name"]  # one per field, in order
        for column in columns:  # each column
            assert set(column) <= COLUMN_KEYS, (widget["name"], column["fieldName"])  # documented keys only
            if "format" in column:  # a number column
                assert column["format"] in d.NUMBER_FORMATS.values(), column["fieldName"]  # exact 0 or 1 places
    queue = next(s for w, s in specs(BUILT["fraud_operations"], "table") if w["name"] == "open_table")  # the queue
    formats = {c["fieldName"]: c.get("format") for c in queue["encodings"]["columns"]}  # its formats
    assert formats["risk_score"] == d.NUMBER_FORMATS["float"]  # D3: 4.600 shows as 4.6
    assert formats["simulated_hour"] == d.NUMBER_FORMATS["integer"]  # whole hours
    assert formats["payment"] is None  # text has no number format


@pytest.mark.parametrize("key", list(d.DASHBOARDS))  # both dashboards
def test_no_visible_text_has_emoji_or_long_dashes(key):  # spec §2 anti-goals
    for line in visible_text(BUILT[key]):  # each string
        assert "—" not in line and "–" not in line, line  # no em or en dash
        assert {c for c in line if ord(c) > 127} <= set("✓✕↻←→"), line  # only the allowed symbols


@pytest.mark.parametrize("key", list(d.DASHBOARDS))  # both dashboards
def test_no_visible_text_uses_jargon(key):  # owner plain-language rule, CI jargon guard
    pattern = re.compile(r"\b(" + "|".join(d.JARGON) + r")\b", re.I)  # whole words, any case
    hits = [t for t in visible_text(BUILT[key]) if pattern.search(t)]  # offending strings
    assert not hits, hits  # none


def test_page_titles_are_the_plain_questions():  # spec §5.2
    titles = {key: [p["displayName"] for p in dash["pages"]] for key, dash in BUILT.items()}  # page titles
    assert titles["fraud_operations"] == ["What is waiting for review?", "How did the reviews turn out?",  # operations
                                          "Is the model still good?", "What these words mean"]  # pages
    assert titles["platform_health"] == ["Are the jobs healthy?", "Is the data fresh and clean?",  # platform
                                         "Run detail", "What these words mean"]  # pages, Run detail third


@pytest.mark.parametrize("key", list(d.DASHBOARDS))  # both dashboards
def test_widget_names_are_unique_and_queries_point_at_real_datasets(key):  # a broken reference renders an empty widget
    names = [w["name"] for w in widgets(BUILT[key])]  # widget names
    assert len(names) == len(set(names))  # unique
    datasets = {ds["name"] for ds in BUILT[key]["datasets"]}  # dataset names
    used = {q["query"]["datasetName"] for w in widgets(BUILT[key]) for q in w.get("queries", [])}  # referenced
    assert used == datasets  # every reference is real and every dataset is used


def test_dashboard_files_hold_no_workspace_identifiers():  # public repo
    paths = sorted((ROOT / "dashboards").glob("*.lvdash.json")) + [ROOT / "sql" / "monitoring" / "monitoring.sql"]  # new files
    for path in paths:  # each
        text = path.read_text(encoding="utf-8")  # contents
        assert not re.search(r"[0-9a-f]{16}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}", text), path.name  # warehouse IDs, UUIDs
        assert not re.search(r"databricks\.com|azuredatabricks|[\w.+-]+@[\w-]+\.\w+", text), path.name  # URLs, emails


def test_every_rejection_reason_has_plain_words():  # the rejected-rows table never shows a bare code
    sql = (ROOT / "pipelines" / "silver" / "01_checked_transactions.sql").read_text(encoding="utf-8")  # Silver verdicts
    codes = set(re.findall(r"(?:THEN|ELSE) '([a-z_]+)'", sql)) - {"ok", "duplicate_copy"}  # shelved reasons
    assert set(d.REASON_WORDS) == codes  # one plain phrase per reason, no more, no less


DASHBOARD_FILE = ROOT / "resources" / "fraud_dashboards.yml"  # bundle resources for the dashboards


def test_dashboards_use_viewer_credentials_and_group_permissions():  # Review Focus 1; spec §5.2 sharing
    resources = yaml.safe_load(DASHBOARD_FILE.read_text(encoding="utf-8"))["resources"]["dashboards"]  # both resources
    assert set(resources) == set(d.DASHBOARDS)  # one resource per built dashboard
    for key, resource in resources.items():  # each
        assert resource["file_path"] == f"../dashboards/{key}.lvdash.json", key  # the generated file
        assert resource["warehouse_id"] == "${var.warehouse_id}", key  # warehouse found by name
        assert resource["embed_credentials"] is False, key  # viewers' own grants, filter and masks
    assert resources["fraud_operations"]["display_name"] == "Fraud operations"  # plain name
    assert resources["platform_health"]["display_name"] == "Platform health"  # plain name
    levels = {key: {(p["group_name"], p["level"]) for p in r["permissions"]} for key, r in resources.items()}  # who may open
    assert levels["fraud_operations"] == {(g, "CAN_READ") for g in ("fraud_engineers", "fraud_reviewers", "fraud_managers")}  # all three
    assert levels["platform_health"] == {("fraud_engineers", "CAN_READ")}  # engineers only


def test_dashboard_resources_hold_no_identifiers():  # public repo
    text = DASHBOARD_FILE.read_text(encoding="utf-8")  # the YAML
    assert not re.search(r"[0-9a-f]{16}|[0-9a-f]{8}-[0-9a-f]{4}|@", text)  # no IDs, no emails


TIME_FIELDS = {"run_label", "update_label", "started"}  # fields that show a time


def test_every_time_axis_says_utc():  # D3: the system tables and Delta store UTC; the owner's clock is IST
    for key, dashboard in BUILT.items():  # both dashboards
        for widget in widgets(dashboard):  # each widget
            encodings = widget.get("spec", {}).get("encodings", {})  # its encodings
            entries = [e for e in encodings.values() if isinstance(e, dict)]  # axes, colours, values
            entries += [c for e in encodings.values() if isinstance(e, list) for c in e]  # table columns
            entries += encodings.get("fields", []) if isinstance(encodings.get("fields"), list) else []  # filter fields
            for entry in entries:  # each
                if entry.get("fieldName") in TIME_FIELDS or entry.get("scale", {}).get("type") == "temporal":  # a time
                    assert entry.get("displayName", "").endswith("(UTC)"), (key, widget["name"])  # labelled


def test_model_page_counts_waiting_hours_from_the_waiting_view():  # review I1: managers' rows hide waiting hours
    totals = next(ds for ds in BUILT["fraud_operations"]["datasets"] if ds["name"] == "model_totals")  # the counters
    assert "FROM workspace.fraud.hours_waiting_for_verdicts" in query_text(totals)  # counted from scored hours
    assert "NOT verdicts_ready" not in query_text(totals)  # never from the reader's case rows


@pytest.mark.parametrize("name", ["model_by_hour", "fraud_caught_by_hour"])  # both per-hour datasets
def test_model_bars_have_one_row_per_hour(name):  # review I2: shares made from counts, whatever the versions
    by_hour = " ".join(query_text(next(ds for ds in BUILT["fraud_operations"]["datasets"] if ds["name"] == name)).split())
    assert "GROUP BY step" in by_hour  # one row per hour
    assert "SUM(confirmed_fraud)" in by_hour and "MAX(fraud_in_hour)" in by_hour  # fraud counted once per hour
    if name == "model_by_hour":  # the share line
        assert "try_divide(SUM(confirmed_fraud), SUM(closed_cases))" in by_hour  # share 1 from counts


def page_text(key: str, title: str) -> str:  # every string a viewer reads on one page
    page = next(p for p in BUILT[key]["pages"] if p["displayName"] == title)  # the page
    return " ".join(visible_text({"pages": [page]}))  # its titles, labels and text lines


def test_queue_page_tells_managers_why_it_is_empty():  # D8: a manager's 0 and "No data" looked broken
    text = page_text("fraud_operations", "What is waiting for review?")  # the queue page
    assert "Open cases you can see" in text  # the counter says it counts the reader's own view
    assert "Managers see 0 and an empty table here" in text  # the empty state is explained, not a fault


def test_job_page_says_the_job_refresh_misses_its_own_run():  # D7: the in-job refresh ran before the run was recorded
    text = page_text("platform_health", "Are the jobs healthy?")  # the jobs page
    assert "up to an hour after it finishes." not in text  # the old line was only true after a manual refresh
    assert "click Refresh" in text  # how to see the newest run


# ── Fraud operations restyle (dashboard beautify Task 2) ──────
def find(key: str, name: str) -> dict:  # one widget by name
    return next(w for w in widgets(BUILT[key]) if w["name"] == name)  # it must exist


def dataset_sql(key: str, name: str) -> str:  # one dataset's SQL, whitespace collapsed
    return " ".join(query_text(next(ds for ds in BUILT[key]["datasets"] if ds["name"] == name)).split())  # one line


def page_widgets(key: str, title: str) -> list[dict]:  # the widgets on one page
    page = next(p for p in BUILT[key]["pages"] if p["displayName"] == title)  # the page
    return [item["widget"] for item in page["layout"]]  # its widgets


def bindings(widget: dict) -> set[tuple[str, str]]:  # (dataset, field) pairs a filter widget narrows
    names = {q["name"]: q["query"]["datasetName"] for q in widget["queries"]}  # query -> dataset
    return {(names[f["queryName"]], f["fieldName"]) for f in widget["spec"]["encodings"]["fields"]}  # pairs


def test_reviews_page_totals_share_the_chart_dataset():  # spec §4.3: slider and cross-filter narrow both
    items = page_widgets("fraud_operations", "How did the reviews turn out?")  # the page
    counters = [w for w in items if w.get("spec", {}).get("widgetType") == "counter"]  # its totals
    assert {c["queries"][0]["query"]["datasetName"] for c in counters} == {"review_outcomes"}  # shared dataset
    wheres = {c["queries"][0]["query"]["filters"][0]["expression"] for c in counters}  # widget query filters
    assert wheres == {"`outcome` = 'Confirmed fraud'", "`outcome` = 'False alarm'"}  # one per verdict
    bars = [w for w in items if w.get("spec", {}).get("widgetType") == "bar"]  # the chart
    assert [b["queries"][0]["query"]["datasetName"] for b in bars] == ["review_outcomes"]  # same dataset


def test_hour_sliders_bind_to_the_charts_datasets():  # spec §4.3: sliders narrow the charts
    for title, expected in (("How did the reviews turn out?", {("review_outcomes", "simulated_hour")}),  # reviews
                            ("Is the model still good?", {("model_by_hour", "simulated_hour"),  # model line...
                                                          ("fraud_caught_by_hour", "simulated_hour")})):  # ...and bars
        sliders = [w for w in page_widgets("fraud_operations", title) if w.get("spec", {}).get("widgetType") == "range-slider"]  # the slider
        assert len(sliders) == 1 and bindings(sliders[0]) == expected, title  # bound to the chart datasets
        for dataset_name, _ in expected:  # each bound dataset
            assert "simulated_hour" in dataset_sql("fraud_operations", dataset_name), dataset_name  # has the column


def test_model_page_uses_single_axis_charts():  # spec §2 anti-goal: never two y-axes
    line = find("fraud_operations", "flagged_line")["spec"]  # the share line
    assert line["widgetType"] == "line" and line["encodings"]["color"]["fieldName"] == "series"  # one line per series
    assert [m["value"] for m in line["encodings"]["color"]["scale"]["mappings"]] == ["Each hour", "Average, all hours"]  # blue, grey
    bars = find("fraud_operations", "caught_bar")["spec"]  # the caught/missed bars
    assert bars["widgetType"] == "bar" and bars["encodings"]["color"]["fieldName"] == "result"  # stacked by result
    assert [m["value"] for m in bars["encodings"]["color"]["scale"]["mappings"]] == ["Caught", "Missed"]  # blue, red


def test_model_average_is_fixed_over_all_hours():  # spec §4.3: the average does not move with the slider
    assert "OVER ()" in dataset_sql("fraud_operations", "model_by_hour")  # a window over every ready hour


def test_newest_24h_window_counts_only_ready_hours():  # Review Focus 3
    totals = dataset_sql("fraud_operations", "model_totals")  # the counters' SQL
    assert "FROM ready WHERE step > (SELECT MAX(step) FROM ready) - 24" in totals  # newest ready hour, never newest scored
    assert "transaction_risk_scores" not in totals  # not from the scored hours


def test_model_counters_compare_newest_24h_with_all_hours():  # spec §4.3 counter comparison
    for name in ("flagged_share", "caught_share"):  # the two shares
        spec = find("fraud_operations", name)["spec"]  # its settings
        assert spec["encodings"]["value"]["format"]["type"] == "number-percent", name  # 0.139 -> 14%
        assert spec["encodings"]["value"]["fieldName"].startswith("newest_24h_share_"), name  # newest 24 hours
        assert spec["encodings"]["target"]["fieldName"].startswith("share_"), name  # compared with all hours
        assert "compared with all hours" in spec["frame"]["description"], name  # said in words


def test_model_page_says_big_numbers_cover_every_hour():  # spec §4.3: the slider narrows the charts only
    assert "The big numbers always cover every hour" in page_text("fraud_operations", "Is the model still good?")  # said


# ── Platform health restyle and Run detail (dashboard beautify Task 3) ──
KNOWN_STATES = ("SUCCEEDED", "COMPLETED", "ERROR", "FAILED", "TIMED_OUT", "CANCELED", "SKIPPED", "UPSTREAM_FAILED")  # run/update results


def plain(state: str | None) -> str:  # what _plain_outcome's SQL gives for one state (Python mirror)
    if state in ("SUCCEEDED", "COMPLETED"):  # finished well
        return "✓ Succeeded"  # green
    if state is None:  # no result yet
        return "↻ Still running"  # amber
    return "✕ " + state.replace("_", " ").title()  # initcap(replace(x, '_', ' ')) with the cross


def test_outcomes_carry_a_symbol():  # Review Focus 1: a running run is amber, never blank or unmapped
    expression = d._plain_outcome("x")  # the SQL
    for piece in ("'✓ Succeeded'", "'↻ Still running'", "concat('✕ '", "initcap(replace(x, '_', ' '))"):  # its parts
        assert piece in expression, piece  # present
    for state in KNOWN_STATES + (None,):  # every result Databricks records, and none
        assert plain(state) in d.MEANING, state  # each has its meaning colour


def test_run_bars_and_run_table_share_a_dataset():  # spec §4.4 cross-filter
    bar_widget, run_table = find("platform_health", "run_minutes"), find("platform_health", "run_table")  # the pair
    assert {w["queries"][0]["query"]["datasetName"] for w in (bar_widget, run_table)} == {"job_runs"}  # one dataset
    x = bar_widget["spec"]["encodings"]["x"]  # the run axis
    assert x["fieldName"] == "run_label" and x["scale"]["type"] == "categorical"  # one bar per run, no empty time
    assert x["displayName"].endswith("(UTC)")  # times are UTC
    assert bar_widget["spec"]["encodings"]["color"]["fieldName"] == "outcome"  # coloured by how it ended


def test_run_labels_keep_the_job_name():  # Review Focus 5: two jobs starting in the same minute stay apart
    runs = dataset_sql("platform_health", "job_runs")  # the runs SQL
    label = runs[runs.index("concat("):runs.index("AS run_label")]  # the label expression
    assert "replace(job_name, 'fraud-', '')" in label  # short job name in the label
    assert "replace(job_name, 'fraud-', '')" in dataset_sql("platform_health", "task_times")  # same label for the picker


def test_run_detail_page_filters_both_datasets():  # Review Focus 4: engineers only
    assert "Run detail" not in [p["displayName"] for p in BUILT["fraud_operations"]["pages"]]  # not for managers
    pickers = [w for w in page_widgets("platform_health", "Run detail")  # the page's filters
               if w.get("spec", {}).get("widgetType") == "filter-single-select"]  # pick one run
    assert len(pickers) == 1  # one picker
    assert bindings(pickers[0]) == {("job_runs", "run_label"), ("task_times", "run_label")}  # narrows both


def column_rules(key: str, widget_name: str, field: str) -> list[dict]:  # one table column's cell rules
    columns = find(key, widget_name)["spec"]["encodings"]["columns"]  # the table's columns
    return next(c for c in columns if c["fieldName"] == field)["style"]["rules"]  # its rules


def test_freshness_marks_a_stage_behind():  # Review Focus 2
    sql_text = dataset_sql("platform_health", "freshness")  # the stages SQL
    assert re.search(r"CASE WHEN .* = 0 THEN 'Up to date' ELSE 'Behind'", sql_text)  # equal hours are up to date
    assert column_rules("platform_health", "behind_table", "hours_behind") == [  # green when 0, red when behind
        d.cell_rule("=", "0", "#DDF3E2"), d.cell_rule(">", "0", "#FBE3E1")]  # tints
    colour = find("platform_health", "freshness_bar")["spec"]["encodings"]["color"]  # the stage bars
    assert colour["fieldName"] == "stage_status"  # coloured by status


def test_cell_rules_on_minutes_and_rows():  # spec §4.2 table cell rules
    assert column_rules("platform_health", "run_table", "minutes_taken") == [  # slow runs stand out
        d.cell_rule(">=", "10", "#B9D3F2"), d.cell_rule(">=", "5", "#DCE9F9")]  # darker first
    assert column_rules("platform_health", "rejections_table", "rows_rejected") == [d.cell_rule(">", "0", "#FBE3E1")]  # any set-aside row


def test_wait_counters_show_minutes():  # spec §4.4: unit on the number
    for name in ("typical_wait", "longest_wait"):  # both waits
        assert find("platform_health", name)["spec"]["encodings"]["value"]["formatTemplate"] == "{{@formatted}} min", name  # "4.6 min"
