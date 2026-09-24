# Databricks notebook source
# ── Setup: make src/ importable from this Git folder ──────────
import os   # path handling
import sys  # module search path

sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), "..", "src")))  # repo's src/ folder
from fraud_ingest.contract import volume_path                               # volume paths
from fraud_ingest.release import PARAM_NAMES, options_from_params, run_release  # release logic
from fraud_ingest.release_log import DeltaReleaseLog                        # Delta-backed log

# COMMAND ----------
# ── Parameters (job parameters override these widgets) ────────
dbutils.widgets.text("catalog", "workspace")  # UC catalog
dbutils.widgets.text("schema", "fraud")       # project schema
for name in PARAM_NAMES:                      # every release option
    dbutils.widgets.text(name, "")            # "" = unset / default
catalog = dbutils.widgets.get("catalog")      # read catalog
schema = dbutils.widgets.get("schema")        # read schema
options = options_from_params({name: dbutils.widgets.get(name) for name in PARAM_NAMES})  # parse options

# COMMAND ----------
# ── Release ───────────────────────────────────────────────────
log = DeltaReleaseLog(spark, f"{catalog}.{schema}.release_log")  # release history table
released = run_release(volume_path(catalog, schema, "outbox"), volume_path(catalog, schema, "landing"), log, options)  # copy + log
if not released:                                                 # nothing left in this segment
    hint = " Set segment=drift to continue." if options.segment == "replay" else " All segments are released."  # next step depends on segment
    print(f"Nothing to release: segment {options.segment!r} is finished.{hint}")  # explicit no-op
for entry in released:                                           # summary for the run page
    print(entry.step, entry.status, entry.scenario or "-", entry.file_name)  # one line per file
