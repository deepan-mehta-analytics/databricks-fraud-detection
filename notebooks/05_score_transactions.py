# Databricks notebook source
# ── Setup: make src/ importable from this Git folder ──────────
import os   # path handling
import sys  # module search path
from datetime import datetime, timezone  # one scoring time per run

sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), "..", "src")))  # repo's src/ folder
import mlflow.sklearn               # load the registered scikit-learn model
from mlflow import MlflowClient     # resolve the alias
from mlflow.exceptions import MlflowException  # alias or model missing
from pyspark.sql import functions as F  # column helpers
from fraud_model.features import INPUT_COLUMNS  # the only columns scoring reads (no answer column)
from fraud_model.scoring import SCORE_CHUNK_STEPS, decision_log_frame, score_schema, score_table_ddl  # decision log
from fraud_model.training import risk_scores, step_chunks  # shared scoring helper and chunking
from fraud_model.windows import SCORE_FROM_STEP_DEFAULT  # 337

# COMMAND ----------
# ── Parameters (job parameters override these widgets) ────────
dbutils.widgets.text("catalog", "workspace")                         # UC catalog
dbutils.widgets.text("schema", "fraud")                              # project schema
dbutils.widgets.text("score_from_step", str(SCORE_FROM_STEP_DEFAULT))  # first step to score
dbutils.widgets.text("model_alias", "champion")                      # which version scores
catalog = dbutils.widgets.get("catalog")                             # read catalog
schema = dbutils.widgets.get("schema")                               # read schema
score_from_step = int(dbutils.widgets.get("score_from_step"))        # read first step
model_alias = dbutils.widgets.get("model_alias").strip()             # read alias
model_name = f"{catalog}.{schema}.fraud_model"                       # UC model name
scores_table = f"{catalog}.{schema}.transaction_risk_scores"         # decision log
spark.sql(score_table_ddl(scores_table))                             # create once; never replaced

# COMMAND ----------
# ── Resolve the alias once, pin that exact version for the whole run ──
try:                                                                 # no model may exist yet
    model_version = MlflowClient().get_model_version_by_alias(model_name, model_alias).version  # current version
except MlflowException:                                              # nothing registered or promoted yet
    print(f"No {model_alias} model yet: nothing scored")             # evidence line
    dbutils.notebook.exit(f"No {model_alias} model yet: nothing scored")  # succeed without scoring
model = mlflow.sklearn.load_model(f"models:/{model_name}/{model_version}")  # pinned: an alias move mid-run can't mix versions

# COMMAND ----------
# ── New payments only: from score_from_step on, not yet in the decision log ──
features = spark.table(f"{catalog}.{schema}.silver_transaction_features")  # strict-past features
clean = spark.table(f"{catalog}.{schema}.silver_transactions").select("transaction_id", "transaction_type", "amount")  # no answer column
new_rows = (features.join(clean, "transaction_id")                    # one row per payment
            .where(F.col("step") >= score_from_step)                  # scoring period and later
            .select(*INPUT_COLUMNS)                                   # inputs only
            .join(spark.table(scores_table).select("transaction_id"), "transaction_id", "left_anti"))  # skip already scored
steps = [r.step for r in new_rows.select("step").distinct().collect()]  # steps with new payments (may be empty)
scored_at = datetime.now(timezone.utc)                                # one timestamp for this run
written = 0                                                           # rows appended
for chunk in step_chunks(steps, SCORE_CHUNK_STEPS):                   # bounded memory; no chunks when nothing is new
    pdf = new_rows.where(F.col("step").isin(chunk)).toPandas()       # one chunk of inputs
    log = decision_log_frame(pdf, risk_scores(model, pdf), model_name, model_version, model_alias, scored_at)  # decision rows
    spark.createDataFrame(log, schema=score_schema()).write.mode("append").saveAsTable(scores_table)  # append
    written += len(log)                                               # count
print(f"Scored {written} new payments with {model_name} version {model_version} (@{model_alias})")  # evidence line (M4/M5/M7)
