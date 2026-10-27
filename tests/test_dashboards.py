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
                                         "What these words mean"]  # pages


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


def test_every_time_axis_says_utc():  # D3: the system tables and Delta store UTC; the owner's clock is IST
    for key, dashboard in BUILT.items():  # both dashboards
        for widget in widgets(dashboard):  # each widget
            x = widget.get("spec", {}).get("encodings", {}).get("x", {})  # the across axis, if any
            if x.get("scale", {}).get("type") == "temporal":  # a time axis
                assert x["displayName"].endswith("(UTC)"), (key, widget["name"])  # labelled
                assert x["axis"]["title"].endswith("(UTC)"), (key, widget["name"])  # on screen too


def test_freshness_table_is_tall_enough_for_all_four_stages():  # D3: height 3 clipped "4. Flagged for review"
    item = next(i for p in BUILT["platform_health"]["pages"] for i in p["layout"] if i["widget"]["name"] == "freshness_table")
    assert item["position"]["height"] >= 4  # title, header and four rows


def test_model_page_counts_waiting_hours_from_the_waiting_view():  # review I1: managers' rows hide waiting hours
    totals = next(ds for ds in BUILT["fraud_operations"]["datasets"] if ds["name"] == "model_totals")  # the counters
    assert "FROM workspace.fraud.hours_waiting_for_verdicts" in query_text(totals)  # counted from scored hours
    assert "NOT verdicts_ready" not in query_text(totals)  # never from the reader's case rows


def test_model_bars_have_one_row_per_hour():  # review I2: shares made from counts, whatever the versions
    by_hour = " ".join(query_text(next(ds for ds in BUILT["fraud_operations"]["datasets"] if ds["name"] == "model_by_hour")).split())
    assert "GROUP BY step" in by_hour  # one row per hour
    assert "try_divide(SUM(confirmed_fraud), SUM(closed_cases))" in by_hour  # share 1 from counts
    assert "try_divide(SUM(confirmed_fraud), MAX(fraud_in_hour))" in by_hour  # share 2: fraud counted once


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
