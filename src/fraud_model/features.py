"""Feature columns and the one feature builder shared by training, scoring and evaluation (spec §5-6)."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
from __future__ import annotations  # modern type hints on 3.11

import math                         # NaN constant
from typing import Any              # loose cell type

import pandas as pd                 # frames

# ── Column lists ──────────────────────────────────────────────
SILVER_FEATURES = (  # the 7 strict-past features in silver_transaction_features (ADR 0008)
    "receiver_payments_previous_hour", "receiver_payments_last_24_hours", "receiver_amount_last_24_hours",  # receiver counts and sum
    "receiver_largest_amount_last_24_hours", "receiver_distinct_senders_last_24_hours",  # receiver max and distinct payers
    "amount_vs_receiver_average_24_hours", "sender_earlier_payments",  # ratio and sender history
)  # end SILVER_FEATURES
TRANSACTION_TYPES = ("CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER")  # PaySim's five types, one-hot in this order
INPUT_COLUMNS = ("transaction_id", "step", "transaction_type", "amount", *SILVER_FEATURES)  # all that scoring reads: no label
FORBIDDEN_INPUTS = (  # columns that must never be read for scoring or used as features
    "fraud_label", "flagged_by_old_rules",  # the answer and the legacy rule flag (a baseline, not a feature)
    "sender_account", "receiver_account",  # raw identifiers
    "sender_balance_before", "sender_balance_after", "receiver_balance_before", "receiver_balance_after",  # leak the label (ADR 0006)
    "channel",  # synthetic scenario column
)  # end FORBIDDEN_INPUTS
MODEL_FEATURES = ("amount", "hour_of_day", *SILVER_FEATURES, *(f"type_{name}" for name in TRANSACTION_TYPES))  # 14 inputs, fixed order
DECIMAL_COLUMNS = ("amount", "receiver_amount_last_24_hours", "receiver_largest_amount_last_24_hours")  # Silver money columns (DECIMAL)


# ── Spark side ────────────────────────────────────────────────
def input_select_expressions() -> tuple[str, ...]:  # selectExpr arguments, in INPUT_COLUMNS order
    """Cast the money columns to DOUBLE in Spark, so toPandas() yields floats, not Python Decimal objects (final review I3)."""  # docstring
    return tuple(f"CAST({name} AS DOUBLE) AS {name}" if name in DECIMAL_COLUMNS else name for name in INPUT_COLUMNS)  # money cast, rest as is


# ── Helpers ───────────────────────────────────────────────────
def _to_float(value: Any) -> float:  # one cell to float; None and NaN become NaN
    if value is None or (isinstance(value, float) and math.isnan(value)):  # missing value
        return math.nan  # HistGradientBoosting handles NaN natively
    return float(value)  # Decimal, int or float to float


# ── Builder ───────────────────────────────────────────────────
def build_feature_frame(frame: pd.DataFrame) -> pd.DataFrame:  # INPUT_COLUMNS in, MODEL_FEATURES out
    """Turn Silver input rows into the model's 14 float columns, in MODEL_FEATURES order, keeping the index."""  # docstring
    missing = [name for name in INPUT_COLUMNS if name not in frame.columns]  # schema check
    if missing:  # a column did not arrive
        raise KeyError(f"Missing input columns: {missing}")  # name them
    out = pd.DataFrame(index=frame.index)  # same rows, same order
    out["amount"] = frame["amount"].map(_to_float).astype("float64")  # Decimal money to float
    out["hour_of_day"] = ((frame["step"].astype("int64") - 1) % 24).astype("float64")  # simulated hour of the day, 0-23
    for name in SILVER_FEATURES:  # strict-past features
        out[name] = frame[name].map(_to_float).astype("float64")  # None (no history) to NaN
    for name in TRANSACTION_TYPES:  # one column per known type
        out[f"type_{name}"] = (frame["transaction_type"] == name).astype("float64")  # unknown or missing type: all zero
    return out[list(MODEL_FEATURES)]  # fixed order for the model
