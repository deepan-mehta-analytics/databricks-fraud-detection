# Databricks notebook source
# ── Setup: make src/ importable from this Git folder ──────────
import os   # path handling
import sys  # module search path

sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), "..", "src")))  # repo's src/ folder
from fraud_ingest.contract import volume_path          # volume paths
from fraud_ingest.ingest import start_bronze_ingest    # Auto Loader stream

# COMMAND ----------
# ── Parameters ────────────────────────────────────────────────
dbutils.widgets.text("catalog", "workspace")  # UC catalog
dbutils.widgets.text("schema", "fraud")       # project schema
catalog = dbutils.widgets.get("catalog")      # read catalog
schema = dbutils.widgets.get("schema")        # read schema
table = f"{catalog}.{schema}.bronze_transactions"  # Bronze table name

# COMMAND ----------
# ── Ingest (AvailableNow: loads new files, then stops) ────────
start_bronze_ingest(spark, volume_path(catalog, schema, "landing"), volume_path(catalog, schema, "pipeline_state"), table)  # run
print("Bronze rows now:", spark.table(table).count())  # evidence line for the run page
