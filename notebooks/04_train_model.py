# Databricks notebook source
# ── Setup: make src/ importable from this Git folder ──────────
import os   # path handling
import sys  # module search path

sys.path.insert(0, os.path.abspath(os.path.join(os.getcwd(), "..", "src")))  # repo's src/ folder
import mlflow                       # tracking and registry
import mlflow.sklearn               # scikit-learn flavour
import sklearn                      # version evidence
from mlflow import MlflowClient     # aliases and descriptions
from fraud_model.features import MODEL_FEATURES, build_feature_frame, input_select_expressions  # shared feature builder
from fraud_model.metrics import flatten_metrics  # MLflow-ready metric dicts
from fraud_model.runtime import runtime_problems  # environment guard
from fraud_model.training import MODEL_NAMES, build_models, compare_models, feature_importances  # model code
from fraud_model.windows import (    # defaults and window math
    ALERT_BUDGET_DEFAULT, COMPARISON_DAYS_DEFAULT, CUT_STEP_DEFAULT, LABEL_DELAY_DAYS_DEFAULT,  # window defaults
    NEGATIVE_SAMPLE_RATE_DEFAULT, SEED_DEFAULT, training_windows,  # sampling defaults and the window function
)  # end imports

print("versions", "mlflow", mlflow.__version__, "sklearn", sklearn.__version__)  # evidence line (M2: record it)
problems = runtime_problems(mlflow.__version__, sklearn.__version__)  # MLflow 3 needed for log_model(name=...)
if problems:                                                    # unsafe environment
    raise RuntimeError("; ".join(problems))                     # stop before any work
mlflow.autolog(disable=True)                                    # only the two planned runs per training job

# COMMAND ----------
# ── Parameters (job parameters override these widgets) ────────
dbutils.widgets.text("catalog", "workspace")                                    # UC catalog
dbutils.widgets.text("schema", "fraud")                                         # project schema
dbutils.widgets.text("cut_step", str(CUT_STEP_DEFAULT))                         # last backfill step
dbutils.widgets.text("label_delay_days", str(LABEL_DELAY_DAYS_DEFAULT))         # Q4 delay
dbutils.widgets.text("comparison_days", str(COMPARISON_DAYS_DEFAULT))           # held-out days
dbutils.widgets.text("negative_sample_rate", str(NEGATIVE_SAMPLE_RATE_DEFAULT)) # non-fraud share kept
dbutils.widgets.text("seed", str(SEED_DEFAULT))                                 # seed
catalog = dbutils.widgets.get("catalog")                                        # read catalog
schema = dbutils.widgets.get("schema")                                          # read schema
cut_step = int(dbutils.widgets.get("cut_step"))                                 # read cut step
delay = int(dbutils.widgets.get("label_delay_days"))                            # read delay
rate = float(dbutils.widgets.get("negative_sample_rate"))                       # read sampling rate
seed = int(dbutils.widgets.get("seed"))                                         # read seed
windows = training_windows(cut_step, delay, int(dbutils.widgets.get("comparison_days")))  # fit/compare steps
model_name = f"{catalog}.{schema}.fraud_model"                                  # UC model name
print("windows", windows)                                                       # evidence line

# COMMAND ----------
# ── Rows: Silver features joined to clean payments (labels come from the clean table) ──
features = spark.table(f"{catalog}.{schema}.silver_transaction_features")      # strict-past features
clean = spark.table(f"{catalog}.{schema}.silver_transactions").select(          # clean payments...
    "transaction_id", "transaction_type", "amount", "fraud_label")              # ...only what training needs
rows = features.join(clean, "transaction_id").selectExpr(*input_select_expressions(), "fraud_label")  # one row per payment, money as DOUBLE
fit_rows = rows.where(f"step BETWEEN {windows.fit_first} AND {windows.fit_last}")  # fit window
fit_set = fit_rows.where("fraud_label = 1").unionByName(                        # every fraud row...
    fit_rows.where("fraud_label = 0").sample(fraction=rate, seed=seed))         # ...plus sampled normal rows
compare_set = rows.where(f"step BETWEEN {windows.compare_first} AND {windows.compare_last}")  # unsampled comparison window
fit_pdf = fit_set.toPandas()                                                    # ~0.28M rows into memory
compare_pdf = compare_set.toPandas()                                            # ~0.81M rows into memory
counts = {"fit_window_rows": fit_rows.count(), "fit_rows_sampled": len(fit_pdf),  # row counts
          "fit_fraud": int(fit_pdf["fraud_label"].sum()), "compare_rows": len(compare_pdf),  # fraud in fit; comparison size
          "compare_fraud": int(compare_pdf["fraud_label"].sum())}               # fraud in comparison
print("counts", counts)                                                         # evidence line (M2/M3)

# COMMAND ----------
# ── Fit and compare ───────────────────────────────────────────
fit_x = build_feature_frame(fit_pdf)                                            # model inputs
fit_y = fit_pdf["fraud_label"].astype(int)                                      # answers
compare_x = build_feature_frame(compare_pdf)                                    # comparison inputs
compare_meta = compare_pdf[["transaction_id", "step", "fraud_label"]]           # keys for budget metrics
models = build_models(seed)                                                     # untrained pipelines
winner, results = compare_models(models, fit_x, fit_y, compare_x, compare_meta, ALERT_BUDGET_DEFAULT)  # fit both
importances = feature_importances(models[winner], compare_x, compare_meta["fraud_label"], seed)  # winner's importances
print("winner", winner, results)                                                # evidence line

# COMMAND ----------
# ── Log both runs, register the winner as @challenger ─────────
user = spark.sql("SELECT current_user()").first()[0]                            # read at run time, never stored in the repo
mlflow.set_experiment(f"/Users/{user}/fraud-model-training")                    # one experiment for all training runs
params = {"cut_step": cut_step, "label_delay_days": delay, "fit_first": windows.fit_first,  # window...
          "fit_last": windows.fit_last, "compare_first": windows.compare_first, "compare_last": windows.compare_last,  # ...settings
          "negative_sample_rate": rate, "seed": seed, "alert_budget": ALERT_BUDGET_DEFAULT,  # sampling and budget
          "features": ",".join(MODEL_FEATURES), "sklearn_version": sklearn.__version__}  # inputs and library
run_ids = {}                                                                    # run per model
for name in MODEL_NAMES:                                                        # both models
    with mlflow.start_run(run_name=f"{name} delay={delay}d") as run:            # one run each
        mlflow.log_params({**params, "model": name})                            # settings
        mlflow.log_metrics({**{k: float(v) for k, v in counts.items()},         # row counts...
                            **flatten_metrics("compare", {"model": results[name]})})  # ...and comparison metrics
        mlflow.sklearn.log_model(models[name], name="model", input_example=fit_x.head(5))  # model + signature (M1-confirmed call)
        run_ids[name] = run.info.run_id                                         # remember the run
with mlflow.start_run(run_id=run_ids[winner]):                                  # back into the winner's run
    mlflow.log_dict(importances, "feature_importances.json")                    # README Model Summary input
    mlflow.log_metrics({f"importance_{k}": v for k, v in importances.items()})  # also as metrics
version = mlflow.register_model(f"runs:/{run_ids[winner]}/model", model_name).version  # new UC version
client = MlflowClient()                                                         # registry client
client.set_registered_model_alias(model_name, "challenger", version)            # never champion: promotion is explicit
client.update_model_version(model_name, version, description=(                  # what this version is
    f"{winner}; label delay {delay} days; fit steps {windows.fit_first}-{windows.fit_last}; "  # model and window
    f"compared on {windows.compare_first}-{windows.compare_last}; sample rate {rate}; seed {seed}"))  # comparison and sampling
print(f"Registered {model_name} version {version} as @challenger ({winner})")   # evidence line
