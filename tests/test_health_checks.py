"""The two health checks (bundle SQL alerts) match Phase 6b spec §5.2-5.4: paused, quiet at zero, plain words, no identity."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
import re                 # word and identifier checks
from pathlib import Path  # locate the YAML

import yaml               # PyYAML parser

from fraud_monitoring import dashboards as d  # the shared jargon list (CI plain-language guard)

# ── Paths and fixed values ────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]                         # repository root
CHECKS_FILE = ROOT / "resources" / "fraud_health_checks.yml"        # the two health checks
RECIPIENT = "${workspace.current_user.userName}"                    # filled in at deploy; no address in the repo
OPENING = ("This email is about the data system that feeds the fraud checks, "  # fixed first sentence (owner 2026-11-02)...
           "not about any payment or customer. No payment needs review because of it.")  # ...word for word
STATUS_LINE = "Status {{ALERT_STATUS}}: TRIGGERED means it needs a look, OK means it is back to normal."  # translates the status word
PAGE = 'open the Platform health dashboard, page "Is the data fresh and clean?",'  # where to look (real page title)
EXPECTED_TEXT = {                                                    # spec §5.4, word for word
    "fraud_health_stages_behind": (                                  # stages check
        "System health check: stages behind",                        # display name
        "System health check: stages behind, status {{ALERT_STATUS}}",  # email subject
        f"{OPENING} {STATUS_LINE} The slowest stage is {{{{QUERY_RESULT_VALUE}}}} hours behind the newest hour released. "  # what happened
        f"What to do: {PAGE} find the stage that stopped, and check that task in the latest fraud-ingest run."),  # what to do
    "fraud_health_rejected_rows": (                                  # rejected-rows check
        "System health check: rejected rows",                        # display name
        "System health check: rejected rows, status {{ALERT_STATUS}}",  # email subject
        f"{OPENING} {STATUS_LINE} {{{{QUERY_RESULT_VALUE}}}} rows in the newest 24 hours were set aside because they failed a data check. "  # what happened
        f"What to do: {PAGE} to see the reason and hour."),          # what to do
}
SOURCE_COLUMN = {"fraud_health_stages_behind": "hours_behind",       # the number each check tests
                 "fraud_health_rejected_rows": "new_rejected_rows"}  # ...per check


def load_checks() -> dict:  # load and return the alerts block of the health-check file
    return yaml.safe_load(CHECKS_FILE.read_text(encoding="utf-8"))["resources"]["alerts"]  # alerts by resource key


# ── Names and schedule ────────────────────────────────────────
def test_two_health_checks_with_the_approved_names():  # owner-approved titles (2026-11-02)
    checks = load_checks()                                               # both alerts
    assert set(checks) == set(EXPECTED_TEXT)                             # exactly the two keys Task 3 references
    for key, check in checks.items():                                    # each check
        assert check["display_name"] == EXPECTED_TEXT[key][0]            # exact title


def test_health_checks_never_run_on_their_own():  # spec §5.4: schedule required but paused; only the job's tasks evaluate them
    for check in load_checks().values():                                 # each check
        assert check["schedule"] == {"quartz_cron_schedule": "0 0 6 * * ?",  # daily slot...
                                     "timezone_id": "UTC",              # ...in UTC...
                                     "pause_status": "PAUSED"}          # ...never active


# ── Conditions and notifications ──────────────────────────────
def test_conditions_fire_above_zero():  # spec §2 row 4: any gap, any rejected row
    for key, check in load_checks().items():                             # each check
        rule = check["evaluation"]                                       # the condition block
        assert rule["comparison_operator"] == "GREATER_THAN"             # value > threshold
        assert rule["threshold"] == {"value": {"double_value": 0}}       # threshold 0
        assert rule["source"] == {"name": SOURCE_COLUMN[key]}            # first row of this column (no aggregation)
        assert rule["empty_result_state"] == "TRIGGERED"                 # silence never hides a fault


def test_one_email_then_back_to_normal():  # spec §5.4: one email per problem, then one "back to normal"
    for check in load_checks().values():                                 # each check
        assert check["evaluation"]["notification"] == {"notify_on_ok": True,  # all-clear email
                                                       "retrigger_seconds": 0,  # no repeats while still wrong
                                                       "subscriptions": [{"user_email": RECIPIENT}]}  # need-to-know: the deploying engineer only
        assert check["warehouse_id"] == "${var.warehouse_id}"            # warehouse looked up by name


# ── Queries ───────────────────────────────────────────────────
def test_queries_are_read_only_and_use_the_project_schema():  # spec §5.2-5.3
    for check in load_checks().values():                                 # each check
        sql = check["query_text"]                                        # the question
        assert re.match(r"\s*(SELECT|WITH)\b", sql)                      # a read
        assert "workspace.fraud." in sql                                 # project location, like gold.sql
        assert not re.search(r"\b(INSERT|MERGE|UPDATE|DELETE|DROP|TRUNCATE|CREATE)\b", sql, re.I)  # nothing changes data


def test_stage_check_counts_released_hours_only():  # Review Focus 4: held hours must not look like a gap
    sql = load_checks()["fraud_health_stages_behind"]["query_text"]      # stages question
    assert "status = 'released'" in sql                                  # held hours excluded
    for table in ("bronze_transactions", "silver_transactions", "transaction_risk_scores"):  # the three stages compared
        assert f"workspace.fraud.{table}" in sql                         # each read
    assert "fraud_alerts" not in sql                                     # Gold left out (an hour may flag nothing)
    assert "AS hours_behind" in sql                                      # the column the condition tests


def test_rejected_check_looks_at_the_newest_24_released_hours():  # spec §5.3
    sql = load_checks()["fraud_health_rejected_rows"]["query_text"]      # rejected question
    assert "workspace.fraud.silver_rejected_transactions" in sql         # the rejected shelf
    assert "status = 'released'" in sql and "- 24" in sql                # window ends at the newest released hour
    assert "AS new_rejected_rows" in sql                                 # the column the condition tests


# ── Wording ───────────────────────────────────────────────────
def test_email_text_is_plain_words():  # owner 2026-11-02: subject says the kind of email; body opens with the fixed sentence
    jargon = re.compile(r"\b(" + "|".join(d.JARGON) + r")\b", re.I)      # whole words, any case
    for key, check in load_checks().items():                             # each check
        _, summary, description = EXPECTED_TEXT[key]                     # the approved text
        assert check["custom_summary"] == summary                        # subject, word for word
        assert check["custom_description"] == description                # body, word for word
        for text in (check["display_name"], summary, description):      # everything a reader sees
            assert text.startswith(("System health check:", OPENING))    # kind of email first
            assert not re.search(r"fraud alert", text, re.I)             # never confused with a flagged payment
            assert not jargon.search(text), text                         # plain words
            leftover = text.replace("the fraud checks", "").replace("fraud-ingest", "")  # the two allowed uses
            assert "fraud" not in leftover.lower(), text                 # no other mention of fraud
        assert description.startswith(OPENING) and "What to do:" in description  # opening first, an action last
        assert "{{QUERY_RESULT_VALUE}}" in description                   # the number is shown


# ── Public repo ───────────────────────────────────────────────
def test_health_check_files_hold_no_identity():  # Review Focus 3: no address, URL or ID in tracked files
    paths = [CHECKS_FILE, ROOT / "resources" / "fraud_ingest_job.yml", ROOT / "sql" / "62_verify_health_checks.sql"]  # 6b files
    for path in paths:                                                   # each
        text = path.read_text(encoding="utf-8")                          # contents
        assert not re.search(r"[0-9a-f]{16}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}", text), path.name  # warehouse IDs, UUIDs
        assert not re.search(r"databricks\.com|azuredatabricks|[\w.+-]+@[\w-]+\.\w+", text), path.name  # URLs, emails


def test_editor_checks_ask_the_deployed_questions():  # sheet V1a/V1b must test exactly what the job evaluates
    squash = lambda text: " ".join(text.split())                         # ignore spacing and line breaks
    sql_file = squash((ROOT / "sql" / "62_verify_health_checks.sql").read_text(encoding="utf-8"))  # editor checks
    for check in load_checks().values():                                 # each deployed question
        assert squash(check["query_text"]) in sql_file                   # appears word for word
