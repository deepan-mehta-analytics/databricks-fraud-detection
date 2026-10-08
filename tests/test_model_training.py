"""Model builders, comparison, scoring helper, importances and chunking (spec §5-6)."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
import numpy as np                    # random fixture data
import pandas as pd                   # frames

from fraud_model.features import INPUT_COLUMNS, MODEL_FEATURES, SILVER_FEATURES, build_feature_frame  # shared builder
from fraud_model.training import (    # code under test
    MODEL_NAMES, build_models, compare_models, feature_importances, risk_scores, step_chunks,  # names
)


def synthetic_inputs(rows: int, seed: int) -> tuple[pd.DataFrame, pd.Series]:  # Silver-shaped rows with a learnable signal
    rng = np.random.default_rng(seed)  # deterministic
    frame = pd.DataFrame({"transaction_id": [f"ps-{i:07d}" for i in range(rows)],  # IDs
                          "step": rng.integers(1, 49, rows), "transaction_type": rng.choice(["TRANSFER", "PAYMENT"], rows),  # keys
                          "amount": rng.uniform(1, 1000, rows)})  # money
    for name in SILVER_FEATURES:  # features
        frame[name] = rng.integers(0, 5, rows).astype(float)  # small counts
    frame.loc[frame.index % 9 == 0, "amount_vs_receiver_average_24_hours"] = None  # some "no history" rows
    label = ((frame["receiver_payments_last_24_hours"] >= 3) & (frame["transaction_type"] == "TRANSFER")).astype(int)  # signal
    return frame[list(INPUT_COLUMNS)], label  # inputs only, plus labels


def test_both_models_train_on_missing_values_and_compare():  # NaN-safe pipelines; winner by PR-AUC
    fit_in, fit_y = synthetic_inputs(600, 1)  # fit set
    compare_in, compare_y = synthetic_inputs(300, 2)  # comparison set
    meta = compare_in[["transaction_id", "step"]].assign(fraud_label=compare_y.values)  # evaluation keys
    models = build_models(seed=42)  # untrained pipelines
    winner, results = compare_models(models, build_feature_frame(fit_in), fit_y, build_feature_frame(compare_in), meta, 5)  # fit
    assert set(results) == set(MODEL_NAMES) and winner in MODEL_NAMES  # both evaluated
    assert results[winner]["pr_auc"] == max(r["pr_auc"] for r in results.values())  # best PR-AUC wins
    assert results[winner]["pr_auc"] > 0.9  # the planted signal is learnable


def test_risk_scores_are_probabilities_in_input_order():  # scoring helper uses the shared builder
    fit_in, fit_y = synthetic_inputs(400, 3)  # data
    model = build_models(seed=42)["gradient_boosted_trees"].fit(build_feature_frame(fit_in), fit_y)  # one model
    scores = risk_scores(model, fit_in.iloc[:10])  # raw Silver-shaped input
    assert scores.shape == (10,) and ((scores >= 0) & (scores <= 1)).all()  # one probability per row


def test_logistic_keeps_an_all_missing_column():  # ruling P3: column list stable between fit and score
    fit_in, fit_y = synthetic_inputs(200, 4)  # data
    fit_in["amount_vs_receiver_average_24_hours"] = None  # entirely missing in this fit
    model = build_models(seed=42)["logistic_regression"].fit(build_feature_frame(fit_in), fit_y)  # must not drop it
    assert model.n_features_in_ == len(MODEL_FEATURES)  # all 14 accepted
    assert risk_scores(model, synthetic_inputs(5, 5)[0]).shape == (5,)  # later data with values still scores


def test_feature_importances_name_every_feature():  # README Model Summary input
    fit_in, fit_y = synthetic_inputs(300, 6)  # data
    features = build_feature_frame(fit_in)  # inputs
    model = build_models(seed=42)["gradient_boosted_trees"].fit(features, fit_y)  # fitted model
    importances = feature_importances(model, features, fit_y, seed=42, max_samples=200)  # permutation importance
    assert set(importances) == set(MODEL_FEATURES)  # one value per feature
    assert max(importances, key=importances.get) in ("receiver_payments_last_24_hours", "type_TRANSFER", "type_PAYMENT")  # signal found


def test_step_chunks_empty_and_partial():  # Review Focus 1
    assert step_chunks([], 6) == []  # nothing to score: no chunks, no error
    assert step_chunks([5, 3, 3, 9, 1, 2, 4, 6, 8, 7], 4) == [[1, 2, 3, 4], [5, 6, 7, 8], [9]]  # sorted, unique, last chunk short
