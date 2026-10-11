"""Text guards on the Gold and governance SQL (spec §5-12). CI has no Spark; the logic is proven by G3-G10."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
import re                 # pattern checks
from pathlib import Path  # locate the SQL files

import yaml               # bundle variables

from fraud_gold.expected import CLOSE_DELAY_STEPS  # 72 simulated hours
from fraud_model.windows import ALERT_BUDGET_DEFAULT  # 50 alerts per hour

ROOT = Path(__file__).resolve().parents[1]  # repo root
GOLD = ROOT / "sql" / "gold" / "gold.sql"  # SQL task `gold`
EXPORT = ROOT / "sql" / "gold" / "export.sql"  # SQL task `export`


def code(path: Path) -> str:  # SQL text with -- comments removed (comments may mention guarded words)
    return "\n".join(line.split("--", 1)[0] for line in path.read_text(encoding="utf-8").splitlines())  # strip comments


def statements(sql: str) -> list[str]:  # split code into statements on ';'
    return [s.strip() for s in sql.split(";") if s.strip()]  # non-empty statements


def test_gold_folder_holds_exactly_the_two_task_files():  # the job runs these two
    assert sorted(p.name for p in (ROOT / "sql" / "gold").glob("*.sql")) == ["export.sql", "gold.sql"]  # nothing else


def test_alert_log_is_insert_only():  # spec §5: alerts are never edited; Review Focus 3
    sql = code(GOLD)  # code only
    merges = [s for s in statements(sql) if s.startswith("MERGE INTO workspace.fraud.fraud_alerts")]  # alert MERGE
    assert len(merges) == 1  # exactly one writer
    assert "WHEN NOT MATCHED THEN INSERT" in merges[0] and "WHEN MATCHED" not in merges[0]  # insert, never update
    assert not re.search(r"\b(UPDATE|DELETE\s+FROM|TRUNCATE\s+TABLE|INSERT\s+OVERWRITE)\s+workspace\.fraud\.fraud_alerts\b", sql)  # no other writes


def test_hourly_budget_and_tie_break():  # spec §5; Review Focus 2
    sql = code(GOLD)  # code only
    assert ALERT_BUDGET_DEFAULT == 50  # the SQL literal below must follow the model's budget
    assert "WHERE alert_rank <= 50" in sql  # top 50 per new hour
    assert sql.count("ORDER BY s.risk_score DESC, s.transaction_id") == 2  # new and late alerts: ties go to the smaller ID


def test_late_alerts_fill_short_hours_or_beat_the_lowest_alert():  # spec §5 late rule; Review Focus 1
    assert re.search(r"WHERE i\.alerts_issued < 50 OR s\.risk_score > i\.lowest_alert_score", code(GOLD))  # same rule as is_late_alert


def test_label_is_read_only_when_closing_cases():  # the label never reaches alerts or the export
    uses = [s for s in statements(code(GOLD)) if "fraud_label" in s]  # statements reading the label
    assert len(uses) == 1 and "SET status = 'closed'" in uses[0]  # only the closing MERGE
    assert "fraud_label" not in code(EXPORT)  # never exported


def test_cases_close_three_simulated_days_after_the_newest_scored_hour():  # spec §6
    assert CLOSE_DELAY_STEPS == 72  # 24 x LABEL_DELAY_DAYS_DEFAULT
    assert "(SELECT MAX(step) FROM workspace.fraud.transaction_risk_scores) - 72" in code(GOLD)  # data clock, not wall clock
    assert "WHEN MATCHED AND c.status = 'open' THEN UPDATE" in code(GOLD)  # a case closes once


def test_export_is_insert_only_and_carries_no_account_names():  # spec §10 data minimisation
    sql = code(EXPORT)  # code only
    assert "MERGE INTO workspace.fraud.closed_alerts_export" in sql and "WHEN NOT MATCHED THEN INSERT" in sql  # insert once
    assert "WHEN MATCHED" not in sql  # never rewritten
    assert not re.search(r"\b(sender_account|receiver_account)\b", sql)  # no customer identifiers leave Unity Catalog


def test_gold_sql_uses_the_bundle_location():  # Global Constraints: hard-coded location must match the bundle defaults
    variables = yaml.safe_load((ROOT / "databricks.yml").read_text(encoding="utf-8"))["variables"]  # bundle variables
    location = f"{variables['catalog']['default']}.{variables['schema']['default']}."  # "workspace.fraud."
    for path in (GOLD, EXPORT):  # both task files
        names = re.findall(r"\b(\w+\.\w+)\.\w+\b", code(path))  # catalog.schema prefixes of table names
        assert names and all(f"{n}." == location for n in names), path.name  # every table is in workspace.fraud


GOVERNANCE = ROOT / "sql" / "50_governance.sql"  # owner-run governance file
EXPORT_SETUP = ROOT / "sql" / "51_export_setup.sql"  # owner-run R2 table setup
TRUSTED = ("is_account_group_member('fraud_engineers')", "is_account_group_member('fraud_reviewers')")  # exempt groups


def function_body(sql: str, name: str) -> str:  # the statement that creates one function
    return next(s for s in statements(sql) if f"FUNCTION workspace.fraud.{name}(" in s)  # first match


def test_governance_functions_exempt_engineers_and_reviewers():  # premortem: the job (an engineer) must never see masked data; Review Focus 4
    sql = code(GOVERNANCE)  # code only
    for name in ("mask_account", "cases_visible"):  # both functions
        body = function_body(sql, name)  # its CREATE statement
        assert all(group in body for group in TRUSTED), name  # both trusted groups exempt
    assert "'REDACTED'" in function_body(sql, "mask_account")  # what everyone else sees


def test_row_filter_reads_only_its_own_row():  # premortem: MERGE fails on tables whose filter nests, aggregates or uses the clock
    body = function_body(code(GOVERNANCE), "cases_visible")  # the filter function
    assert not re.search(r"\bSELECT\b|\bFROM\b|current_|now\(|rand\(", body, re.I)  # own column + group checks only
    assert "status = 'closed'" in body  # managers see closed cases


def test_masks_cover_both_account_columns_on_both_tables():  # spec §8
    sql = code(GOVERNANCE)  # code only
    for table in ("fraud_alerts", "alert_cases"):  # both tables hold account names
        for column in ("sender_account", "receiver_account"):  # both account columns
            assert f"ALTER TABLE workspace.fraud.{table} ALTER COLUMN {column} SET MASK workspace.fraud.mask_account" in sql  # attached
    assert "ALTER TABLE workspace.fraud.alert_cases SET ROW FILTER workspace.fraud.cases_visible ON (status)" in sql  # filter attached


def test_reviewers_and_managers_get_per_table_grants_only():  # least privilege: new tables stay invisible to them
    sql = code(GOVERNANCE)  # code only
    assert "GRANT USE SCHEMA, SELECT, EXECUTE ON SCHEMA workspace.fraud TO `fraud_engineers`" in sql  # engineers: schema-wide
    for group in ("fraud_reviewers", "fraud_managers"):  # the other two groups
        schema_grants = re.findall(rf"GRANT ([A-Z ,]+) ON SCHEMA workspace\.fraud TO `{group}`", sql)  # their schema grants
        assert schema_grants == ["USE SCHEMA"], group  # only the right to enter the schema
    assert "TO `fraud_managers`" in sql and "fraud_alerts TO `fraud_managers`" not in sql  # managers never see the raw alert log


def test_no_real_storage_path_or_account_id_in_tracked_text():  # public repo: placeholders only (spec §10-11)
    import subprocess  # list tracked files
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()  # tracked paths
    for rel in tracked:  # every tracked file
        path = ROOT / rel  # absolute path
        if path.suffix not in {".sql", ".yml", ".yaml", ".md", ".py", ".txt"}:  # text files only
            continue  # skip binaries and others
        if path == Path(__file__).resolve():  # this guard's own pattern text contains "r2://"
            continue  # not a storage path
        text = path.read_text(encoding="utf-8", errors="ignore")  # file text
        for match in re.finditer(r"r2://[^\s'\"`)]*", text):  # every R2 URL
            assert match.group(0).startswith("r2://<bucket>@<account-id>."), f"{rel}: {match.group(0)}"  # placeholder only
        assert not re.search(r"[0-9a-f]{32}\.r2\.cloudflarestorage\.com", text), rel  # no real account ID host
    assert "LOCATION 'r2://<bucket>@<account-id>.r2.cloudflarestorage.com/closed_alerts_export'" in code(EXPORT_SETUP)  # the template
