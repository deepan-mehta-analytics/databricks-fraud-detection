"""Scoring decision log: table schema, DDL and rows (spec §6). This module never refers to the answer column."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
from __future__ import annotations  # modern type hints on 3.11

from datetime import datetime       # scoring time type
from typing import Iterable         # loose sequence type

import pandas as pd                 # frames

from fraud_model.features import SILVER_FEATURES, build_feature_frame  # features as the model sees them

# ── Constants ─────────────────────────────────────────────────
SCORING_PARAM_NAMES = ("score_from_step", "model_alias")  # job parameters the score notebook reads
SCORE_CHUNK_STEPS = 6  # steps per toPandas() chunk (~100k rows in the replay)
SCORE_TABLE_COLUMNS = (  # transaction_risk_scores, in order
    ("transaction_id", "STRING"), ("step", "BIGINT"), ("risk_score", "DOUBLE"),  # what was scored, and the score
    ("model_name", "STRING"), ("model_version", "STRING"), ("model_alias", "STRING"),  # which model decided
    ("scored_at", "TIMESTAMP"), ("transaction_type", "STRING"), ("amount", "DOUBLE"),  # when, plus raw inputs
    *((name, "DOUBLE") for name in SILVER_FEATURES),  # the 7 features exactly as the model saw them
)  # end SCORE_TABLE_COLUMNS


# ── Schema text ───────────────────────────────────────────────
def score_schema() -> str:  # Spark DDL column list, used by both CREATE TABLE and createDataFrame
    return ", ".join(f"{name} {kind}" for name, kind in SCORE_TABLE_COLUMNS)  # "transaction_id STRING, ..."


def score_table_ddl(table: str) -> str:  # idempotent create statement
    return (f"CREATE TABLE IF NOT EXISTS {table} ({score_schema()}) "  # never replaces existing rows
            "COMMENT 'Append-only decision log: one fraud risk score per payment, with the model and the features it saw.'")  # table comment


# ── Rows ──────────────────────────────────────────────────────
def decision_log_frame(input_frame: pd.DataFrame, scores: Iterable[float], model_name: str, model_version: str,  # inputs and model
                       model_alias: str, scored_at: datetime) -> pd.DataFrame:  # alias and time
    """One decision-log row per input row, columns in SCORE_TABLE_COLUMNS order."""  # docstring
    seen = build_feature_frame(input_frame)  # features as floats, exactly what the model received
    out = pd.DataFrame({  # build column by column
        "transaction_id": input_frame["transaction_id"].astype(str).values,  # payment key
        "step": input_frame["step"].astype("int64").values,  # simulated hour
        "risk_score": pd.Series(list(scores), dtype="float64").values,  # model output
        "model_name": model_name, "model_version": str(model_version), "model_alias": model_alias,  # model identity
        "scored_at": scored_at,  # one timestamp per run
        "transaction_type": input_frame["transaction_type"].values,  # raw type
        "amount": seen["amount"].values,  # amount as a float
    })  # end frame
    for name in SILVER_FEATURES:  # features as seen
        out[name] = seen[name].values  # NaN where there was no history
    return out[[name for name, _ in SCORE_TABLE_COLUMNS]]  # exact order
