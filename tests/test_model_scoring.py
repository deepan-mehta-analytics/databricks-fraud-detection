"""The scoring decision log: schema, DDL and rows; the label never enters scoring (spec §6)."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
from datetime import datetime, timezone  # scoring time
from decimal import Decimal              # Silver money type
from pathlib import Path                 # read notebook/module text

import pandas as pd                      # frames

from fraud_model.features import INPUT_COLUMNS, SILVER_FEATURES  # shared columns
from fraud_model.scoring import (        # code under test
    SCORE_CHUNK_STEPS, SCORE_TABLE_COLUMNS, SCORING_PARAM_NAMES, decision_log_frame, score_schema, score_table_ddl,  # names
)

ROOT = Path(__file__).resolve().parents[1]  # repo root


def test_schema_lists_keys_model_and_features_but_no_label():  # P4 decision log
    names = [name for name, _ in SCORE_TABLE_COLUMNS]  # column names
    assert names[:9] == ["transaction_id", "step", "risk_score", "model_name", "model_version", "model_alias",  # keys and model
                         "scored_at", "transaction_type", "amount"]  # time and raw inputs
    assert names[9:] == list(SILVER_FEATURES)  # the 7 features as seen
    assert "fraud_label" not in names and "flagged_by_old_rules" not in names  # no answer stored with the decision
    assert score_schema().startswith("transaction_id STRING, step BIGINT, risk_score DOUBLE")  # Spark DDL order


def test_ddl_creates_once_and_names_the_table():  # idempotent setup inside the notebook
    ddl = score_table_ddl("workspace.fraud.transaction_risk_scores")  # build
    assert ddl.startswith("CREATE TABLE IF NOT EXISTS workspace.fraud.transaction_risk_scores (")  # never replaces
    assert score_schema() in ddl  # same columns as the writer


def test_decision_log_rows_keep_the_features_as_seen():  # one row per scored payment
    row = {"transaction_id": "ps-0000400", "step": 400, "transaction_type": "TRANSFER", "amount": Decimal("12.00")}  # keys
    row.update({name: None if name == "receiver_amount_last_24_hours" else 2 for name in SILVER_FEATURES})  # one missing
    when = datetime(2026, 10, 8, tzinfo=timezone.utc)  # fixed time
    out = decision_log_frame(pd.DataFrame([row]), [0.25], "workspace.fraud.fraud_model", "3", "champion", when)  # build
    assert list(out.columns) == [name for name, _ in SCORE_TABLE_COLUMNS]  # exact schema order
    first = out.iloc[0]  # the one row
    assert (first.transaction_id, first.step, first.risk_score, first.model_version) == ("ps-0000400", 400, 0.25, "3")  # values
    assert first.amount == 12.0 and pd.isna(first.receiver_amount_last_24_hours)  # floats as the model saw them


def test_scoring_reads_no_label_and_job_parameters_are_named():  # spec §6 guard
    for path in ("notebooks/05_score_transactions.py", "src/fraud_model/scoring.py"):  # scoring code
        assert "fraud_label" not in (ROOT / path).read_text(encoding="utf-8")  # not even in a comment
    assert "fraud_label" not in INPUT_COLUMNS  # nor in what scoring selects
    assert SCORING_PARAM_NAMES == ("score_from_step", "model_alias") and SCORE_CHUNK_STEPS == 6  # agreed names
