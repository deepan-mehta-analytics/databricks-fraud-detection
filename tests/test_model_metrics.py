"""Evaluation at a fixed hourly review budget (spec §7, Q2)."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
import math                          # NaN in a score column
import pandas as pd                  # frames

from fraud_model.metrics import budget_metrics, flag_metrics, flatten_metrics, pr_auc  # code under test


def frame(rows):  # rows: (step, transaction_id, fraud_label, score)
    return pd.DataFrame(rows, columns=["step", "transaction_id", "fraud_label", "score"])  # evaluation frame


def test_budget_counts_per_hour_with_short_hours():  # an hour with fewer rows than the budget alerts all of them
    data = frame([(1, "a", 1, 0.9), (1, "b", 0, 0.8), (1, "c", 1, 0.1), (2, "d", 0, 0.7)])  # 3 rows, then 1 row
    result = budget_metrics(data, "score", budget=2)  # top 2 per hour
    assert result == {"hours": 2, "alerts": 3, "fraud_caught": 1, "fraud_total": 2,  # a, b, d alerted; only a is fraud
                      "precision_at_budget": 1 / 3, "recall_at_budget": 0.5}  # hand-checked


def test_budget_ties_break_by_id_and_missing_scores_rank_last():  # Review Focus 2
    data = frame([(1, "b", 0, 0.5), (1, "a", 1, 0.5), (1, "c", 1, math.nan)])  # tie at 0.5; c has no score
    result = budget_metrics(data, "score", budget=1)  # one alert
    assert result["fraud_caught"] == 1  # "a" wins the tie (lower ID), never the unscored "c"


def test_no_fraud_and_no_alerts_give_none():  # Review Focus 5
    assert budget_metrics(frame([(1, "a", 0, 0.2)]), "score", budget=5)["recall_at_budget"] is None  # no fraud in the window
    empty = flag_metrics(pd.DataFrame({"fraud_label": [1, 0], "flagged_by_old_rules": [0, 0]}))  # nothing flagged
    assert empty["alerts"] == 0 and empty["precision_at_budget"] is None and empty["recall_at_budget"] == 0.0  # no ZeroDivision


def test_budget_must_be_positive():  # a zero budget is a configuration error
    try:  # expect ValueError
        budget_metrics(frame([(1, "a", 1, 0.9)]), "score", budget=0)  # bad budget
    except ValueError:  # expected
        return  # pass
    raise AssertionError("budget 0 was accepted")  # fail


def test_flag_metrics_use_the_flag_as_the_alert_list():  # PaySim's legacy rule baseline
    data = pd.DataFrame({"fraud_label": [1, 1, 0, 1], "flagged_by_old_rules": [1, 0, 1, 0]})  # 2 flagged, 1 of them fraud
    assert flag_metrics(data) == {"alerts": 2, "fraud_caught": 1, "fraud_total": 3,  # counts
                                  "precision_at_budget": 0.5, "recall_at_budget": 1 / 3}  # hand-checked


def test_pr_auc_and_its_empty_case():  # average precision; None when there is no fraud
    assert pr_auc([0, 1, 1], [0.1, 0.9, 0.8]) == 1.0  # perfect ranking
    assert pr_auc([0, 0], [0.1, 0.2]) is None  # undefined without positives


def test_flatten_skips_none():  # Review Focus 5: MLflow never receives None
    flat = flatten_metrics("eval", {"model": {"alerts": 3, "recall_at_budget": None}})  # one None
    assert flat == {"eval_model_alerts": 3.0}  # None dropped, value float
