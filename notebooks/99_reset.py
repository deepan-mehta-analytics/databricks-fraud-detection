# Databricks notebook source
# ── DESTRUCTIVE: clears Bronze, landing, pipeline state and the release log. User-run only. ──
dbutils.widgets.text("catalog", "workspace")  # UC catalog
dbutils.widgets.text("schema", "fraud")       # project schema
dbutils.widgets.text("confirm", "")           # must be exactly RESET
catalog = dbutils.widgets.get("catalog")      # read catalog
schema = dbutils.widgets.get("schema")        # read schema
if dbutils.widgets.get("confirm") != "RESET":  # safety gate
    raise ValueError("Set confirm=RESET to clear all ingest state. Nothing was changed.")  # stop here

# COMMAND ----------
# ── Reset (outbox and raw are never touched) ──────────────────
spark.sql(f"DROP TABLE IF EXISTS {catalog}.{schema}.bronze_transactions")  # drop Bronze
spark.sql(f"DELETE FROM {catalog}.{schema}.release_log")                   # empty the release log
for volume in ("landing", "pipeline_state"):                               # folders to clear
    for item in dbutils.fs.ls(f"/Volumes/{catalog}/{schema}/{volume}"):    # every file or folder inside
        dbutils.fs.rm(item.path, True)                                     # remove recursively
print("Reset done: rerun the job to start from the backfill.")             # next step
