# Databricks notebook source
# ── Setup: make src/ importable from this Git folder ──────────
import os   # path handling
import sys  # module search path

sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), "..", "src")))  # repo's src/ folder
from fraud_ingest.contract import ANCHOR_DEFAULT, volume_path  # shared contract
from fraud_ingest.split import split_csv                       # one-time splitter

# COMMAND ----------
# ── Parameters ────────────────────────────────────────────────
dbutils.widgets.text("catalog", "workspace")      # UC catalog
dbutils.widgets.text("schema", "fraud")           # project schema
dbutils.widgets.text("anchor", ANCHOR_DEFAULT)    # synthetic date for step 1
catalog = dbutils.widgets.get("catalog")          # read catalog
schema = dbutils.widgets.get("schema")            # read schema
anchor = dbutils.widgets.get("anchor")            # read anchor

# COMMAND ----------
# ── Split (V1) ────────────────────────────────────────────────
outbox = volume_path(catalog, schema, "outbox")                                       # destination volume
totals = split_csv(f"{volume_path(catalog, schema, 'raw')}/paysim.csv", outbox, anchor)  # write 743 files
print(totals)                                                                         # show counts
assert totals == {"rows": 6362620, "fraud": 8213, "files": 743}, totals               # measured 2026-09-22/24
for segment, expected in {"backfill": 336, "replay": 72, "drift": 335}.items():      # per-segment file counts
    found = len(os.listdir(f"{outbox}/{segment}"))                                    # files written
    assert found == expected, (segment, found)                                        # must match G-10
print("V1 passed")                                                                    # evidence line
