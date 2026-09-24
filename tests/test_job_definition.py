"""The bundle job matches spec §6-7: release -> ingest, one retry, paused 10-minute schedule."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
from pathlib import Path  # locate the YAML

import yaml               # PyYAML parser

from fraud_ingest.release import PARAM_NAMES  # parameters the release notebook reads

JOB_FILE = Path(__file__).resolve().parents[1] / "resources" / "fraud_ingest_job.yml"  # job definition path


def load_job() -> dict:  # load and return the fraud_ingest job block from the bundle YAML
    return yaml.safe_load(JOB_FILE.read_text(encoding="utf-8"))["resources"]["jobs"]["fraud_ingest"]  # the job block


def test_tasks_run_release_then_ingest_with_one_retry():  # verify task graph and retry policy
    tasks = {t["task_key"]: t for t in load_job()["tasks"]}  # tasks by key
    assert set(tasks) == {"release", "ingest"}  # exactly two tasks
    assert tasks["ingest"]["depends_on"] == [{"task_key": "release"}]  # ingest waits for release
    assert tasks["ingest"]["max_retries"] == 1  # absorbs the designed schema-evolution restart
    assert tasks["release"]["notebook_task"]["notebook_path"] == "../notebooks/02_release.py"  # release notebook
    assert tasks["ingest"]["notebook_task"]["notebook_path"] == "../notebooks/03_ingest_bronze.py"  # ingest notebook


def test_schedule_is_defined_but_paused_and_runs_never_overlap():  # verify schedule and concurrency guard
    job = load_job()  # the job block
    assert job["schedule"]["pause_status"] == "PAUSED"  # enabled only for recorded demos
    assert job["schedule"]["quartz_cron_expression"] == "0 0/10 * * * ?"  # every 10 minutes
    assert job["max_concurrent_runs"] == 1  # release runs must not overlap


def test_job_exposes_every_release_parameter():  # verify job parameters cover catalog/schema plus every release option
    names = {p["name"] for p in load_job()["parameters"]}  # declared job parameters
    assert names == {"catalog", "schema", *PARAM_NAMES}  # location + every release option
