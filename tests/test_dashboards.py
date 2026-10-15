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


@pytest.mark.parametrize("key", list(d.DASHBOARDS))  # both dashboards
def test_every_chart_has_a_how_to_read_line(key):  # owner plain-language rule
    for page in BUILT[key]["pages"][:-1]:  # every page but the word list
        items = [item["widget"] for item in page["layout"]]  # its widgets
        charts = [w for w in items if w.get("spec", {}).get("widgetType") in ("bar", "table")]  # charts and tables
        lines = [w for w in items if d.HOW_TO_READ in widget_text(w)]  # explanation lines
        assert charts or any(w.get("spec", {}).get("widgetType") == "counter" for w in items), page["name"]  # page shows data
        assert len(lines) >= max(len(charts), 1), page["name"]  # one line per chart, at least one per page


@pytest.mark.parametrize("key", list(d.DASHBOARDS))  # both dashboards
def test_each_dashboard_ends_with_the_word_list(key):  # owner plain-language rule: a way to look words up
    last = BUILT[key]["pages"][-1]  # the final page
    assert last["displayName"] == "What these words mean"  # plain title
    text = "\n".join(widget_text(item["widget"]) for item in last["layout"])  # its text
    for term, meaning in WORDS[key].items():  # every term
        assert f"**{term}** — {meaning}" in text, term  # term and its plain sentence


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
