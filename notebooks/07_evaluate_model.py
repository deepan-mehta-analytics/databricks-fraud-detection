# Databricks notebook source
# ── Setup: make src/ importable from this Git folder ──────────
import os   # path handling
import sys  # module search path

sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), "..", "src")))  # repo's src/ folder
import mlflow                       # tracking
import mlflow.sklearn               # scikit-learn flavour
import pandas as pd                 # frames
from pyspark.sql import functions as F  # column helpers
from fraud_model.features import INPUT_COLUMNS  # what the model reads
from fraud_model.metrics import budget_metrics, flag_metrics, flatten_metrics, pr_auc  # evaluation
from fraud_model.training import risk_scores, step_chunks  # shared scoring helper and chunking
from fraud_model.windows import ALERT_BUDGET_DEFAULT, CUT_STEP_DEFAULT  # defaults

# COMMAND ----------
# ── Parameters: AFTER-THE-FACT evaluation (reads labels); never writes scores ──
dbutils.widgets.text("catalog", "workspace")                     # UC catalog
dbutils.widgets.text("schema", "fraud")                          # project schema
dbutils.widgets.text("model_uri", "")                            # required: models:/<name>/<version> or runs:/<run id>/model
dbutils.widgets.text("first_step", str(CUT_STEP_DEFAULT + 1))    # 337: first scoring-period step
dbutils.widgets.text("last_step", "408")                         # last replay step
dbutils.widgets.text("budget", str(ALERT_BUDGET_DEFAULT))        # alerts per hour
catalog = dbutils.widgets.get("catalog")                         # read catalog
schema = dbutils.widgets.get("schema")                           # read schema
model_uri = dbutils.widgets.get("model_uri").strip()             # read model URI (typed in the workspace only)
first_step = int(dbutils.widgets.get("first_step"))              # read first step
last_step = int(dbutils.widgets.get("last_step"))                # read last step
budget = int(dbutils.widgets.get("budget"))                      # read budget
if not model_uri:                                                # required
    raise ValueError("Set model_uri, for example models:/workspace.fraud.fraud_model/1")  # stop

# COMMAND ----------
# ── Score the window in step chunks, keep only what the metrics need ──
model = mlflow.sklearn.load_model(model_uri)                     # the model under evaluation
features = spark.table(f"{catalog}.{schema}.silver_transaction_features")  # strict-past features
clean = spark.table(f"{catalog}.{schema}.silver_transactions").select(  # clean payments with the answers...
    "transaction_id", "transaction_type", "amount", "fraud_label", "flagged_by_old_rules")  # ...for evaluation only
rows = features.join(clean, "transaction_id").where(f"step BETWEEN {first_step} AND {last_step}").select(  # window rows
    *INPUT_COLUMNS, "fraud_label", "flagged_by_old_rules")       # inputs plus answers
parts = []                                                       # scored chunks
steps = [r.step for r in rows.select("step").distinct().collect()]  # steps present
for chunk in step_chunks(steps, 6):                              # bounded memory
    pdf = rows.where(F.col("step").isin(chunk)).toPandas()       # one chunk
    pdf["risk_score"] = risk_scores(model, pdf[list(INPUT_COLUMNS)])  # model scores (inputs only)
    pdf["amount"] = pdf["amount"].astype(float)                  # largest-amount baseline needs floats
    parts.append(pdf[["transaction_id", "step", "fraud_label", "flagged_by_old_rules", "amount", "risk_score"]])  # keep metric columns
scored = pd.concat(parts, ignore_index=True)                     # whole window

# COMMAND ----------
# ── Metrics: model vs baselines at the same budget ────────────
results = {                                                      # one block per contender
    "model": {**budget_metrics(scored, "risk_score", budget), "pr_auc": pr_auc(scored["fraud_label"], scored["risk_score"])},  # the model
    "largest_amount": {**budget_metrics(scored, "amount", budget), "pr_auc": pr_auc(scored["fraud_label"], scored["amount"])},  # naive rule
    "old_rules": flag_metrics(scored),                           # PaySim's legacy flag
}  # end results
for name, metrics in results.items():                            # readable evidence
    print(name, metrics)                                         # evidence lines (M6)
run_id = mlflow.models.get_model_info(model_uri).run_id          # the run that produced this model
with mlflow.start_run(run_id=run_id):                            # append to that run
    mlflow.log_params({"eval_first_step": first_step, "eval_last_step": last_step, "eval_budget": budget})  # window
    mlflow.log_metrics(flatten_metrics("eval", results))         # eval_model_..., eval_largest_amount_..., eval_old_rules_...
