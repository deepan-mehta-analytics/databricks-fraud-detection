# Databricks notebook source
# ── Setup: make src/ importable from this Git folder ──────────
import os   # path handling
import sys  # module search path

sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), "..", "src")))  # repo's src/ folder
import mlflow                       # tracking
import mlflow.sklearn               # scikit-learn flavour
import pandas as pd                 # frames
import sklearn                      # version evidence
from mlflow import MlflowClient     # read the model run's logged library version
from pyspark.sql import functions as F  # column helpers
from fraud_model.features import INPUT_COLUMNS, input_select_expressions  # what the model reads, money as DOUBLE
from fraud_model.metrics import budget_metrics, flag_metrics, flatten_metrics, pr_auc  # evaluation
from fraud_model.runtime import runtime_problems  # environment guard
from fraud_model.scoring import SCORE_CHUNK_STEPS  # same chunk size as the score task
from fraud_model.training import risk_scores, step_chunks  # shared scoring helper and chunking
from fraud_model.windows import ALERT_BUDGET_DEFAULT, CUT_STEP_DEFAULT  # defaults

print("versions", "mlflow", mlflow.__version__, "sklearn", sklearn.__version__)  # evidence line (M6: record it)
mlflow.autolog(disable=True)                                     # no extra runs from evaluation

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
run_id = mlflow.models.get_model_info(model_uri).run_id          # the run that produced this model
trained_with = MlflowClient().get_run(run_id).data.params.get("sklearn_version")  # logged by 04_train_model
problems = runtime_problems(mlflow.__version__, sklearn.__version__, trained_with)  # environment check
if problems:                                                     # unsafe to evaluate
    raise RuntimeError("; ".join(problems))                      # stop before scoring
model = mlflow.sklearn.load_model(model_uri)                     # the model under evaluation
features = spark.table(f"{catalog}.{schema}.silver_transaction_features")  # strict-past features
clean = spark.table(f"{catalog}.{schema}.silver_transactions").select(  # clean payments with the answers...
    "transaction_id", "transaction_type", "amount", "fraud_label", "flagged_by_old_rules")  # ...for evaluation only
rows = features.join(clean, "transaction_id").where(f"step BETWEEN {first_step} AND {last_step}").selectExpr(  # window rows
    *input_select_expressions(), "fraud_label", "flagged_by_old_rules")  # inputs (money as DOUBLE) plus answers
parts = []                                                       # scored chunks
steps = [r.step for r in rows.select("step").distinct().collect()]  # steps present
for chunk in step_chunks(steps, SCORE_CHUNK_STEPS):              # bounded memory, same chunks as scoring
    pdf = rows.where(F.col("step").isin(chunk)).toPandas()       # one chunk
    if pdf.empty:                                                # nothing in this chunk
        continue                                                 # predict_proba refuses zero rows
    pdf["risk_score"] = risk_scores(model, pdf[list(INPUT_COLUMNS)])  # model scores (inputs only)
    parts.append(pdf[["transaction_id", "step", "fraud_label", "flagged_by_old_rules", "amount", "risk_score"]])  # keep metric columns
if not parts:                                                    # empty window
    raise ValueError(f"No Silver payments in steps {first_step}-{last_step}: nothing to evaluate")  # explain
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
with mlflow.start_run(run_id=run_id):                            # append to the model's run
    mlflow.set_tags({"eval_first_step": first_step, "eval_last_step": last_step, "eval_budget": budget})  # tags, so a rerun can change them
    mlflow.log_metrics(flatten_metrics("eval", results))         # eval_model_..., eval_largest_amount_..., eval_old_rules_...
