# Databricks notebook source
# ── DESTRUCTIVE: clears Bronze, landing, pipeline state, the release log and the risk scores. User-run only. ──
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
spark.sql(f"DROP TABLE IF EXISTS {catalog}.{schema}.transaction_risk_scores")  # drop the decision log (IDs repeat after a reset)
spark.sql(f"DELETE FROM {catalog}.{schema}.release_log")                   # empty the release log
for volume in ("landing", "pipeline_state"):                               # folders to clear
    for item in dbutils.fs.ls(f"/Volumes/{catalog}/{schema}/{volume}"):    # every file or folder inside
        dbutils.fs.rm(item.path, True)                                     # remove recursively
print("Reset done. Rebuild in this order: "                                  # Bronze is recreated, so Silver must rebuild
      "1) run the fraud-ingest job once (backfill recreates Bronze; its silver task result does not matter yet); "  # step 1
      "2) run sql/30_silver_setup.sql (turns incremental-refresh support back on for the new Bronze table); "  # step 2
      "3) open the fraud-silver pipeline and click 'Full refresh all'. Later job runs are incremental again.")  # step 3
