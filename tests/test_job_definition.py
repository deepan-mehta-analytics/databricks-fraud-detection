"""The bundle job matches spec §6-7: release -> ingest, one retry, paused 10-minute schedule."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
from pathlib import Path  # locate the YAML

import yaml               # PyYAML parser

from fraud_ingest.contract import ANCHOR_DEFAULT  # the pipeline's anchor must match the producer
from fraud_ingest.release import PARAM_NAMES  # parameters the release notebook reads
from fraud_model.scoring import SCORING_PARAM_NAMES  # parameters the score notebook reads

PIPELINE_FILE = Path(__file__).resolve().parents[1] / "resources" / "fraud_silver_pipeline.yml"  # pipeline definition path

BUNDLE_FILE = Path(__file__).resolve().parents[1] / "databricks.yml"  # bundle root (variables)

JOB_FILE = Path(__file__).resolve().parents[1] / "resources" / "fraud_ingest_job.yml"  # job definition path


def load_job() -> dict:  # load and return the fraud_ingest job block from the bundle YAML
    return yaml.safe_load(JOB_FILE.read_text(encoding="utf-8"))["resources"]["jobs"]["fraud_ingest"]  # the job block


def load_pipeline() -> dict:  # load and return the fraud_silver pipeline block from the bundle YAML
    return yaml.safe_load(PIPELINE_FILE.read_text(encoding="utf-8"))["resources"]["pipelines"]["fraud_silver"]  # the block


def test_tasks_run_release_ingest_silver_then_score():  # verify task graph and retry policy
    tasks = {t["task_key"]: t for t in load_job()["tasks"]}  # tasks by key
    assert set(tasks) == {"release", "ingest", "silver", "score"}  # exactly four tasks
    assert tasks["ingest"]["depends_on"] == [{"task_key": "release"}]  # ingest waits for release
    assert tasks["silver"]["depends_on"] == [{"task_key": "ingest"}]  # Silver waits for Bronze
    assert tasks["score"]["depends_on"] == [{"task_key": "silver"}]  # scoring waits for features
    assert tasks["ingest"]["max_retries"] == 1  # absorbs the designed schema-evolution restart
    assert "max_retries" not in tasks["score"]  # a scoring failure must be loud, not retried
    assert tasks["release"]["notebook_task"]["notebook_path"] == "../notebooks/02_release.py"  # release notebook
    assert tasks["ingest"]["notebook_task"]["notebook_path"] == "../notebooks/03_ingest_bronze.py"  # ingest notebook
    assert tasks["score"]["notebook_task"]["notebook_path"] == "../notebooks/05_score_transactions.py"  # score notebook
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


def test_job_exposes_every_release_and_scoring_parameter():  # location + release options + scoring options
    from fraud_model.windows import SCORE_FROM_STEP_DEFAULT  # module default
    params = {p["name"]: p["default"] for p in load_job()["parameters"]}  # declared job parameters
    assert set(params) == {"catalog", "schema", *PARAM_NAMES, *SCORING_PARAM_NAMES}  # nothing missing, nothing extra
    assert params["score_from_step"] == str(SCORE_FROM_STEP_DEFAULT) and params["model_alias"] == "champion"  # agreed defaults


TRAIN_JOB_FILE = Path(__file__).resolve().parents[1] / "resources" / "fraud_train_job.yml"  # training job definition


def test_train_job_is_on_demand_and_its_defaults_match_the_module():  # spec §5, Q3
    from fraud_model import windows  # module constants
    job = yaml.safe_load(TRAIN_JOB_FILE.read_text(encoding="utf-8"))["resources"]["jobs"]["fraud_train"]  # the job block
    assert job["name"] == "fraud-train" and "schedule" not in job and job["max_concurrent_runs"] == 1  # by hand, one at a time
    assert [t["task_key"] for t in job["tasks"]] == ["train"]  # one task
    assert job["tasks"][0]["notebook_task"]["notebook_path"] == "../notebooks/04_train_model.py"  # the training notebook
    defaults = {p["name"]: p["default"] for p in job["parameters"]}  # parameter defaults
    assert defaults == {"catalog": "${var.catalog}", "schema": "${var.schema}",  # shared location
                        "cut_step": str(windows.CUT_STEP_DEFAULT), "label_delay_days": str(windows.LABEL_DELAY_DAYS_DEFAULT),  # windows
                        "comparison_days": str(windows.COMPARISON_DAYS_DEFAULT),  # comparison length
                        "negative_sample_rate": str(windows.NEGATIVE_SAMPLE_RATE_DEFAULT), "seed": str(windows.SEED_DEFAULT)}  # sampling


MODEL_ENVIRONMENT_VERSION = "6"  # serverless environment 6: scikit-learn 1.7.2, mlflow 3.12.0 (measured in M1/M2)


def task_environment_version(job: dict, task_key: str) -> str:  # the pinned serverless environment version of one task
    task = next(t for t in job["tasks"] if t["task_key"] == task_key)  # the task block
    environments = {e["environment_key"]: e["spec"] for e in job.get("environments", [])}  # job-level environments by key
    return environments[task["environment_key"]]["environment_version"]  # KeyError if the task is not pinned


def test_training_and_scoring_run_in_the_same_pinned_environment():  # a model pickled on one scikit-learn minor must load on the same one
    train_job = yaml.safe_load(TRAIN_JOB_FILE.read_text(encoding="utf-8"))["resources"]["jobs"]["fraud_train"]  # the training job
    assert task_environment_version(train_job, "train") == MODEL_ENVIRONMENT_VERSION  # training is pinned
    assert task_environment_version(load_job(), "score") == MODEL_ENVIRONMENT_VERSION  # scoring is pinned to the same version
