"""The bundle job matches spec §6-7: release -> ingest, one retry, paused 10-minute schedule."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
from pathlib import Path  # locate the YAML

import yaml               # PyYAML parser

from fraud_ingest.contract import ANCHOR_DEFAULT  # the pipeline's anchor must match the producer
from fraud_ingest.release import PARAM_NAMES  # parameters the release notebook reads

PIPELINE_FILE = Path(__file__).resolve().parents[1] / "resources" / "fraud_silver_pipeline.yml"  # pipeline definition path

BUNDLE_FILE = Path(__file__).resolve().parents[1] / "databricks.yml"  # bundle root (variables)

JOB_FILE = Path(__file__).resolve().parents[1] / "resources" / "fraud_ingest_job.yml"  # job definition path


def load_job() -> dict:  # load and return the fraud_ingest job block from the bundle YAML
    return yaml.safe_load(JOB_FILE.read_text(encoding="utf-8"))["resources"]["jobs"]["fraud_ingest"]  # the job block


def load_pipeline() -> dict:  # load and return the fraud_silver pipeline block from the bundle YAML
    return yaml.safe_load(PIPELINE_FILE.read_text(encoding="utf-8"))["resources"]["pipelines"]["fraud_silver"]  # the block


def test_tasks_run_release_then_ingest_then_silver():  # verify task graph and retry policy
    tasks = {t["task_key"]: t for t in load_job()["tasks"]}  # tasks by key
    assert set(tasks) == {"release", "ingest", "silver"}  # exactly three tasks
    assert tasks["ingest"]["depends_on"] == [{"task_key": "release"}]  # ingest waits for release
    assert tasks["silver"]["depends_on"] == [{"task_key": "ingest"}]  # Silver waits for Bronze
    assert tasks["ingest"]["max_retries"] == 1  # absorbs the designed schema-evolution restart
    assert tasks["release"]["notebook_task"]["notebook_path"] == "../notebooks/02_release.py"  # release notebook
    assert tasks["ingest"]["notebook_task"]["notebook_path"] == "../notebooks/03_ingest_bronze.py"  # ingest notebook
    assert tasks["silver"]["pipeline_task"] == {  # runs the bundle's pipeline, never a full refresh by default
        "pipeline_id": "${resources.pipelines.fraud_silver.id}", "full_refresh": False}  # exact reference


def test_pipeline_is_serverless_triggered_and_targets_the_project_schema():  # spec §4, §7
    pipeline = load_pipeline()  # the pipeline block
    assert pipeline["name"] == "fraud-silver"  # name shown in the workspace
    assert pipeline["serverless"] is True  # Free Edition is serverless-only
    assert pipeline["continuous"] is False  # triggered: active only while the job runs it
    assert (pipeline["catalog"], pipeline["schema"]) == ("${var.catalog}", "${var.schema}")  # same place as Bronze
    assert pipeline["configuration"] == {  # anchor matches the producer; source follows the shared location
        "anchor": ANCHOR_DEFAULT, "bronze_table": "${var.catalog}.${var.schema}.bronze_transactions"}  # exact values


def test_job_and_pipeline_share_one_location():  # security review S-1: Bronze and Silver can never split
    variables = yaml.safe_load(BUNDLE_FILE.read_text(encoding="utf-8"))["variables"]  # bundle variables
    assert {k: v["default"] for k, v in variables.items()} == {"catalog": "workspace", "schema": "fraud"}  # defaults
    defaults = {p["name"]: p["default"] for p in load_job()["parameters"]}  # job parameter defaults
    assert (defaults["catalog"], defaults["schema"]) == ("${var.catalog}", "${var.schema}")  # same variables
    sql = (PIPELINE_FILE.parents[1] / "pipelines" / "silver" / "01_checked_transactions.sql").read_text(encoding="utf-8")  # verdict view
    assert "FROM ${bronze_table}" in sql and "workspace.fraud" not in sql  # source comes from configuration only


def test_pipeline_lists_exactly_the_four_sql_files_in_order():  # spec §7
    paths = [lib["file"]["path"] for lib in load_pipeline()["libraries"]]  # library paths
    assert paths == [f"../pipelines/silver/{name}" for name in (  # relative to resources/
        "01_checked_transactions.sql", "02_transactions.sql",  # verdict view and clean table
        "03_rejected_transactions.sql", "04_transaction_features.sql")]  # rejected shelf and features


def test_schedule_is_defined_but_paused_and_runs_never_overlap():  # verify schedule and concurrency guard
    job = load_job()  # the job block
    assert job["schedule"]["pause_status"] == "PAUSED"  # enabled only for recorded demos
    assert job["schedule"]["quartz_cron_expression"] == "0 0/10 * * * ?"  # every 10 minutes
    assert job["max_concurrent_runs"] == 1  # release runs must not overlap


def test_job_exposes_every_release_parameter():  # verify job parameters cover catalog/schema plus every release option
    names = {p["name"] for p in load_job()["parameters"]}  # declared job parameters
    assert names == {"catalog", "schema", *PARAM_NAMES}  # location + every release option
