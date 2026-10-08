"""One feature builder for training, scoring and evaluation; forbidden columns never become inputs (spec §5-6)."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
from decimal import Decimal          # Spark DECIMAL arrives as Decimal in toPandas()

import math                          # NaN checks
import pandas as pd                  # frames

from fraud_model.features import (   # code under test
    FORBIDDEN_INPUTS, INPUT_COLUMNS, MODEL_FEATURES, SILVER_FEATURES, TRANSACTION_TYPES, build_feature_frame,  # names
)


def make_input(**overrides) -> pd.DataFrame:  # one-row input frame shaped like the Silver join
    row = {"transaction_id": "ps-0000001", "step": 25, "transaction_type": "TRANSFER", "amount": Decimal("10.50")}  # keys
    row.update({name: 1 for name in SILVER_FEATURES})  # every feature present
    row.update(overrides)  # test-specific values
    return pd.DataFrame([row])  # single-row frame


def test_feature_lists_have_the_agreed_shape():  # spec §5 feature list
    assert len(SILVER_FEATURES) == 7 and TRANSACTION_TYPES == ("CASH_IN", "CASH_OUT", "DEBIT", "PAYMENT", "TRANSFER")  # sizes
    assert MODEL_FEATURES == ("amount", "hour_of_day", *SILVER_FEATURES, *(f"type_{t}" for t in TRANSACTION_TYPES))  # order
    assert INPUT_COLUMNS == ("transaction_id", "step", "transaction_type", "amount", *SILVER_FEATURES)  # what is read


def test_no_forbidden_column_is_ever_an_input_or_a_feature():  # label, IDs, accounts, balances, channel, raw step
    assert {"fraud_label", "flagged_by_old_rules", "sender_account", "receiver_account", "channel"} <= set(FORBIDDEN_INPUTS)  # listed
    assert not set(FORBIDDEN_INPUTS) & set(INPUT_COLUMNS)  # never read for scoring
    assert not ({*FORBIDDEN_INPUTS, "transaction_id", "step"} & set(MODEL_FEATURES))  # never a model input


def test_output_columns_types_and_hour_of_day():  # one float column per model feature
    out = build_feature_frame(make_input(step=25))  # step 25 is hour 0 of day 2
    assert tuple(out.columns) == MODEL_FEATURES  # exact order
    assert all(str(dtype) == "float64" for dtype in out.dtypes)  # scikit-learn friendly
    assert out.loc[0, "hour_of_day"] == 0.0 and build_feature_frame(make_input(step=24)).loc[0, "hour_of_day"] == 23.0  # wrap


def test_decimal_and_none_become_float_and_nan():  # Review Focus 4
    out = build_feature_frame(make_input(amount=Decimal("10.50"), receiver_amount_last_24_hours=None,  # Decimal and None
                                         amount_vs_receiver_average_24_hours=float("nan")))  # and an existing NaN
    assert out.loc[0, "amount"] == 10.5  # Decimal converted exactly
    assert math.isnan(out.loc[0, "receiver_amount_last_24_hours"])  # None -> NaN (HistGradientBoosting handles it)
    assert math.isnan(out.loc[0, "amount_vs_receiver_average_24_hours"])  # NaN stays NaN


def test_type_is_one_hot():  # TRANSFER sets only its own column
    out = build_feature_frame(make_input(transaction_type="TRANSFER"))  # a transfer
    assert [out.loc[0, f"type_{t}"] for t in TRANSACTION_TYPES] == [0.0, 0.0, 0.0, 0.0, 1.0]  # one hot


def test_unknown_or_missing_type_gives_zero_type_columns():  # Review Focus 3
    for value in ("CRYPTO", None):  # a type never seen in training; a missing type
        out = build_feature_frame(make_input(transaction_type=value))  # build
        assert tuple(out.columns) == MODEL_FEATURES  # no new column appears
        assert sum(out.loc[0, f"type_{t}"] for t in TRANSACTION_TYPES) == 0.0  # all zero


def test_missing_input_column_is_named():  # a schema slip fails loudly with the column name
    frame = make_input().drop(columns=["sender_earlier_payments"])  # one feature missing
    try:  # expect a KeyError
        build_feature_frame(frame)  # build
    except KeyError as error:  # the expected failure
        assert "sender_earlier_payments" in str(error)  # names the column
    else:  # no error is a bug
        raise AssertionError("build_feature_frame accepted a frame with a missing column")  # fail
