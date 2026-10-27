"""Text guards on the monitoring SQL (Phase 6a spec §5.1, §7). CI has no Spark; the logic is proven by D3a and D5-D8."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
import re                 # pattern checks
from pathlib import Path  # locate the SQL files

import yaml               # job and pipeline names from the bundle

ROOT = Path(__file__).resolve().parents[1]  # repo root
MONITORING = ROOT / "sql" / "monitoring" / "monitoring.sql"  # SQL task `monitor`
VERIFY = ROOT / "sql" / "61_verify_monitoring.sql"  # owner-run checks
CUTOFF = "(SELECT MAX(step) FROM workspace.fraud.transaction_risk_scores) - 72"  # the 72-hour data clock, as in gold.sql
DEV_PREFIX = r"regexp_replace(name, '^\\[dev [^\\]]*\\] ', '')"  # strips a development-mode name prefix (ruling R2)
GROUPS = ("fraud_engineers", "fraud_reviewers", "fraud_managers")  # the three groups
VIEWS = {  # view -> its columns, in order (plan Task 2 Interfaces)
    "model_accuracy_by_hour": ["step", "model_version", "flagged_payments", "closed_cases", "confirmed_fraud",  # counts
                               "false_alarms", "share_flagged_that_were_fraud", "fraud_in_hour",  # shares and fraud
                               "share_of_fraud_caught", "verdicts_ready"],  # caught share and ready flag
    "hours_waiting_for_verdicts": ["newest_hour_scored", "newest_hour_with_verdicts", "hours_waiting"],  # one row
    "data_freshness": ["newest_hour_released", "newest_hour_ingested", "newest_hour_scored", "newest_hour_flagged",  # stages
                       "median_minutes_landing_to_scored", "slowest_minutes_landing_to_scored"],  # waits
    "rejected_rows_by_reason": ["reason", "rows_rejected", "first_hour", "last_hour"],  # shelf summary
    "job_run_times": ["job_name", "run_started_at", "run_finished_at", "minutes_taken", "outcome",  # run level
                      "task_name", "task_minutes", "task_outcome"],  # task level
    "pipeline_update_times": ["pipeline_name", "update_started_at", "update_finished_at", "minutes_taken",  # update
                              "outcome", "full_rebuild"],  # result
}  # end VIEWS
AUDIENCE = {name: ["fraud_engineers"] for name in VIEWS}  # engineers only by default (ruling R4)
AUDIENCE["model_accuracy_by_hour"] = list(GROUPS)  # the model page is for all three groups
AUDIENCE["hours_waiting_for_verdicts"] = list(GROUPS)  # its waiting counter too


def code(path: Path) -> str:  # SQL text with -- comments removed (comments may mention guarded words)
    return "\n".join(line.split("--", 1)[0] for line in path.read_text(encoding="utf-8").splitlines())  # strip comments


def statements(sql: str) -> list[str]:  # split code into statements on ';'
    return [" ".join(s.split()) for s in sql.split(";") if s.strip()]  # whitespace collapsed, non-empty


def view_statement(name: str) -> str:  # the statement that creates one view
    return next(s for s in statements(code(MONITORING)) if s.startswith(f"CREATE OR REPLACE VIEW workspace.fraud.{name} "))  # first match


def view_columns(name: str) -> list[str]:  # declared column names, in order
    head = view_statement(name).split(") COMMENT '", 1)[0]  # the column list ends where the view comment starts
    return re.findall(r"[(,] (\w+) COMMENT '", head)  # each "name COMMENT '...'" entry


def test_monitoring_folder_holds_exactly_the_task_file():  # the job runs this one file
    assert sorted(p.name for p in MONITORING.parent.glob("*.sql")) == ["monitoring.sql"]  # nothing else


def test_monitoring_only_creates_views_and_grants():  # spec §5.1: views store nothing, so reruns are always safe
    sql = code(MONITORING)  # code only
    assert all(s.startswith(("CREATE OR REPLACE VIEW workspace.fraud.", "GRANT SELECT ON TABLE workspace.fraud."))  # two kinds...
               for s in statements(sql))  # ...of statement, nothing else
    assert not re.search(r"\b(INSERT|MERGE|UPDATE|DELETE|DROP|TRUNCATE)\b", sql)  # no writes (upper case: comments say "update")


def test_the_six_views_have_plain_names_and_commented_columns():  # spec §5.1 table; Global Constraints
    created = re.findall(r"CREATE OR REPLACE VIEW workspace\.fraud\.(\w+) ", " ".join(statements(code(MONITORING))))  # in order
    assert created == list(VIEWS)  # the six views, in file order
    for name, columns in VIEWS.items():  # each view
        assert view_columns(name) == columns, name  # every column declared with a COMMENT, in order
        assert re.search(r"\) COMMENT '[^']{20,}' AS ", view_statement(name)), name  # a real view comment


def test_every_view_is_granted_right_after_it_is_created():  # Review Focus 5: a rebuild never drops access
    stmts = statements(code(MONITORING))  # in order
    for i, statement in enumerate(stmts):  # walk the file
        match = re.match(r"CREATE OR REPLACE VIEW workspace\.fraud\.(\w+) ", statement)  # a view
        if match:  # grants must follow at once
            name = match.group(1)  # which view
            expected = [f"GRANT SELECT ON TABLE workspace.fraud.{name} TO `{g}`" for g in AUDIENCE[name]]  # its grants
            assert stmts[i + 1:i + 1 + len(expected)] == expected, name  # immediately, in this order
    assert sum(1 for s in stmts if s.startswith("GRANT")) == 10  # 3 + 3 + 1 + 1 + 1 + 1


def test_label_is_read_in_exactly_two_job_statements_both_behind_the_cutoff():  # owner ruling 2026-10-15 (widened rule)
    job_sql = sorted((ROOT / "sql" / "gold").glob("*.sql")) + [MONITORING]  # every SQL file a job task runs (or was designed to)
    uses = [s for path in job_sql for s in statements(code(path)) if "fraud_label" in s]  # statements reading the label
    assert len(uses) == 2  # the case-closing MERGE and the model view, nothing else
    assert all(CUTOFF in s for s in uses)  # both only for hours at least 72 simulated hours old
    assert any("SET status = 'closed'" in s for s in uses)  # one is gold.sql's closing MERGE
    assert any(s.startswith("CREATE OR REPLACE VIEW workspace.fraud.model_accuracy_by_hour ") for s in uses)  # the other


def test_waiting_hours_show_empty_shares_never_zero():  # Review Focus 2
    view = view_statement("model_accuracy_by_hour")  # the model view
    assert view.count("CASE WHEN c.step <= k.last_ready_step THEN try_divide(") == 2  # both shares empty until ready
    assert "LEFT JOIN fraud AS f ON f.step = c.step" in view  # fraud_in_hour empty for hours the fraud CTE leaves out
    assert not re.search(r"\b(coalesce|nvl|ifnull|zeroifnull)\s*\(", view, re.I)  # nothing turns "waiting" into 0


READY_CLOCK = ("SELECT MAX(step) FROM workspace.fraud.alert_cases "  # newest hour with a verdict...
               f"WHERE status = 'closed' AND step <= {CUTOFF}")  # ...never past the 72-hour clock


def test_an_hour_is_ready_only_once_gold_has_closed_its_cases():  # review I3: gold may fail after score
    view = view_statement("model_accuracy_by_hour")  # the model view
    assert READY_CLOCK.replace("MAX(step)", "MAX(step) AS last_ready_step", 1) in view  # closed cases set the clock
    assert "(c.step <= k.last_ready_step) IS TRUE" in view  # no closed case yet reads false, not empty
    assert f"WHERE step <= {CUTOFF} AND step <= (SELECT last_ready_step FROM cutoff)" in view  # label waits for both


def test_waiting_hours_are_counted_from_scored_hours_not_cases():  # review I1: managers see no open cases
    view = view_statement("hours_waiting_for_verdicts")  # the waiting view
    assert "fraud_label" not in view  # no label here
    assert "scored AS (SELECT DISTINCT step FROM workspace.fraud.transaction_risk_scores)" in view  # every scored hour
    assert "COUNT_IF(k.last_ready_step IS NULL OR s.step > k.last_ready_step)" in view  # counts unless it has verdicts
    assert "model_accuracy_by_hour" not in view  # never from the reader's case rows
    assert READY_CLOCK in view  # the same clock as the model view (managers see closed cases, so it holds for them)


def test_fraud_is_summed_once_per_hour():  # review I2: fraud_in_hour repeats once per model version
    for path in (VERIFY, ROOT / "src" / "fraud_monitoring" / "dashboards.py"):  # every place that adds it up
        raw = code(path) if path.suffix == ".sql" else path.read_text(encoding="utf-8")  # SQL without comments, or Python
        text = " ".join(raw.split())  # whitespace collapsed
        sums = re.findall(r"SUM\(fraud_in_hour\) FROM (\w+)", text, re.I)  # what each sum reads
        assert sums, path.name  # there are sums to check
        assert set(sums) <= {"hours", "recent_hours"} and "hours" in sums, path.name  # always a one-row-per-hour CTE...
        for name in set(sums):  # each one used
            assert f" {name} AS (SELECT DISTINCT step, fraud_in_hour FROM" in text, (path.name, name)  # ...made once per hour
        assert not re.search(r"SUM\(\s*IF\([^)]*fraud_in_hour", text, re.I), path.name  # no per-row sum in disguise


def test_jobs_and_pipeline_are_matched_by_name_with_the_dev_prefix_stripped():  # Review Focus 3, ruling R2
    jobs, pipes = view_statement("job_run_times"), view_statement("pipeline_update_times")  # the two history views
    names = {yaml.safe_load((ROOT / "resources" / f).read_text(encoding="utf-8"))["resources"][kind][key]["name"]  # bundle names
             for f, kind, key in (("fraud_ingest_job.yml", "jobs", "fraud_ingest"), ("fraud_train_job.yml", "jobs", "fraud_train"),  # jobs
                                  ("fraud_silver_pipeline.yml", "pipelines", "fraud_silver"))}  # and the pipeline
    assert names == {"fraud-ingest", "fraud-train", "fraud-silver"}  # the names the views filter on
    assert DEV_PREFIX in jobs and DEV_PREFIX in pipes  # prefix stripped before matching and before display
    assert "n.job_name IN ('fraud-ingest', 'fraud-train')" in jobs  # jobs by name
    assert "n.pipeline_name = 'fraud-silver'" in pipes  # pipeline by name
    assert not re.search(r"\b(job_id|pipeline_id|run_id|update_id)\s*(=|IN)\s*['(]", jobs + pipes)  # never by an ID literal


def test_run_minutes_come_from_period_times_grouped_per_run():  # Review Focus 4: P1 measured *_duration_seconds as 0
    jobs, pipes = view_statement("job_run_times"), view_statement("pipeline_update_times")  # the two history views
    for view in (jobs, pipes):  # both
        assert "duration_seconds" not in view  # never the zero columns
        assert "MIN(period_start_time)" in view and "MAX(period_end_time)" in view  # earliest start, latest end
        assert "MAX_BY(result_state, period_end_time)" in view  # the last slice holds the final result
    assert "GROUP BY workspace_id, job_id, run_id)" in jobs  # one row per job run, however many hourly slices
    assert "GROUP BY workspace_id, job_id, job_run_id, task_key)" in jobs  # one row per task, a retry included
    assert "GROUP BY workspace_id, pipeline_id, update_id)" in pipes  # one row per pipeline update


def test_views_expose_no_identifier_columns():  # public repo + screenshots: no IDs on screen
    for name in VIEWS:  # every view
        assert not [c for c in view_columns(name) if c.endswith("_id")], name  # no *_id column
        assert "SELECT *" not in view_statement(name), name  # every output column is chosen by hand


def test_monitoring_sql_reads_only_the_project_schema_and_system_lakeflow():  # Global Constraints: location
    names = re.findall(r"\b(\w+)\.(\w+)\.(\w+)\b", code(MONITORING))  # catalog.schema.table references
    assert {(a, b) for a, b, _ in names} == {("workspace", "fraud"), ("system", "lakeflow")}  # nothing else
    assert {t for a, _, t in names if a == "system"} == {  # exactly the documented tables
        "jobs", "job_run_timeline", "job_task_run_timeline", "pipelines", "pipeline_update_timeline"}  # five


def test_landing_wait_uses_the_latest_scoring_run():  # ruling R6: back-filled hours would distort the wait
    view = view_statement("data_freshness")  # the freshness view
    assert "WHERE s.scored_at = (SELECT MAX(scored_at) FROM workspace.fraud.transaction_risk_scores)" in view  # newest run only
    assert "timestampdiff(SECOND, t.file_arrived_at, s.scored_at)" in view  # landing to scored
    assert "FROM workspace.fraud.release_log WHERE status = 'released'" in view  # held hours don't count as released


def test_verification_covers_every_check_and_reads_the_model_view_as_manager():  # spec §7; Review Focus 1
    text = VERIFY.read_text(encoding="utf-8")  # the owner-run checks
    for block in ("D3a", "D5", "D6", "D7", "D8"):  # every SQL check of the sheet
        assert f"-- ── {block}" in text, block  # has its own block
    manager = text.split("-- ── D8", 1)[1]  # the manager block
    assert "FROM workspace.fraud.model_accuracy_by_hour" in manager  # the filter must apply through the view
    assert "FROM workspace.fraud.job_run_times" in manager  # engineers-only view: must be refused


def block(name: str) -> list[str]:  # the statements of one verification block, comments removed
    body = VERIFY.read_text(encoding="utf-8").split(f"-- ── {name}:", 1)[1].split("\n-- ── ", 1)[0]  # up to the next block
    body = body.split("\n", 1)[1]  # drop the rest of the header line (no longer behind its --)
    return statements("\n".join(line.split("--", 1)[0] for line in body.splitlines()))  # code only


def test_after_run_checks_each_return_one_row_with_a_verdict():  # owner feedback 2026-10-15: one Run, one row
    for name in ("D5", "D6", "D7"):  # the checks after run E
        found = block(name)  # its statements
        assert len(found) == 1, name  # a single Run shows the whole check
        assert found[0].endswith("AS all_as_expected FROM result"), name  # last column says whether every value matched
    manager = block("D8")  # the test user's check
    assert len(manager) == 2, "D8"  # one row, then the statement that must be refused (an error stops a query)
    assert manager[0].endswith("AS all_as_expected FROM result"), "D8"  # the row has the verdict too
    assert "FROM workspace.fraud.job_run_times" in manager[1], "D8"  # the refused one stays on its own


D12_COLUMNS = ["confirmed_fraud_all_hours", "false_alarms_all_hours", "newest_24h_share_flagged_that_were_fraud",  # the totals...
               "newest_24h_share_of_fraud_caught", "stages_behind"]  # ...the new shares and freshness


def test_d12_check_is_one_row_ending_all_as_expected():  # dashboard beautify spec §5 D12: numbers unchanged
    found = block("D12")  # its statements
    assert len(found) == 1  # one Run, one row
    check = found[0]  # the statement
    positions = [check.index(f"AS {column}") for column in D12_COLUMNS]  # where each column is named
    assert positions == sorted(positions)  # in the sheet's order
    assert check.endswith("AS all_as_expected FROM result")  # the verdict is last
    verdict = check[check.rindex("SELECT *"):]  # the final select
    for expected in ("confirmed_fraud_all_hours = 405", "false_alarms_all_hours = 2511", "stages_behind = 0"):  # fixed values
        assert expected in verdict, expected  # required
    assert "FROM ready WHERE step > (SELECT MAX(step) FROM ready) - 24" in check  # same window as the dashboard
