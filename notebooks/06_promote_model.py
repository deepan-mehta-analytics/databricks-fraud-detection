# Databricks notebook source
# ── Promote: point an alias (default champion) at a chosen model version. Owner-run. ──
from mlflow import MlflowClient                   # registry client
from mlflow.exceptions import MlflowException     # raised when an alias does not exist yet

dbutils.widgets.text("catalog", "workspace")      # UC catalog
dbutils.widgets.text("schema", "fraud")           # project schema
dbutils.widgets.text("version", "")               # required: the version to promote
dbutils.widgets.text("alias", "champion")         # alias to move
catalog = dbutils.widgets.get("catalog")          # read catalog
schema = dbutils.widgets.get("schema")            # read schema
version = dbutils.widgets.get("version").strip()  # read version
alias = dbutils.widgets.get("alias").strip()      # read alias
if not version.isdigit():                         # a version number is required
    raise ValueError("Set version to the model version number to promote. Nothing was changed.")  # stop

# COMMAND ----------
# ── Move the alias and show before -> after ───────────────────
name = f"{catalog}.{schema}.fraud_model"          # UC model name
client = MlflowClient()                           # registry client
try:                                              # the alias may not exist yet
    before = client.get_model_version_by_alias(name, alias).version  # current target
except MlflowException:                           # first promotion
    before = "none"                               # nothing promoted yet
client.set_registered_model_alias(name, alias, version)  # move the alias
print(f"{name} @{alias}: version {before} -> {version}")  # evidence line
