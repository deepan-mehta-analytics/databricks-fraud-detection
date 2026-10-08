"""Evaluation metrics at a fixed hourly review budget, plus PR-AUC (spec §7, Q2)."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
from __future__ import annotations       # modern type hints on 3.11

from typing import Iterable               # loose sequence type

import pandas as pd                       # frames
from sklearn.metrics import average_precision_score  # PR-AUC (average precision)

from fraud_model.windows import ALERT_BUDGET_DEFAULT  # Q2 default budget


# ── Shared ratio helper ───────────────────────────────────────
def _ratio(numerator: int, denominator: int) -> float | None:  # None instead of dividing by zero
    return numerator / denominator if denominator else None  # undefined when nothing to divide by


# ── Budget metrics ────────────────────────────────────────────
def budget_metrics(frame: pd.DataFrame, score_column: str, budget: int = ALERT_BUDGET_DEFAULT) -> dict:  # top-N per hour
    """Alert the `budget` highest scores in each step (ties: lower transaction_id first; missing scores last)."""  # docstring
    if budget < 1:  # zero or negative budget is a configuration error
        raise ValueError("budget must be at least 1")  # refuse
    ranked = frame.sort_values(["step", score_column, "transaction_id"], ascending=[True, False, True],  # riskiest first
                               na_position="last")  # an unscored row never beats a scored one
    alerts = ranked.groupby("step", sort=False).head(budget)  # the alert list for every hour
    caught = int(alerts["fraud_label"].sum())  # fraud among the alerts
    total = int(frame["fraud_label"].sum())  # all fraud in the window
    return {"hours": int(frame["step"].nunique()), "alerts": len(alerts), "fraud_caught": caught,  # counts
            "fraud_total": total, "precision_at_budget": _ratio(caught, len(alerts)),  # share of alerts that were fraud
            "recall_at_budget": _ratio(caught, total)}  # share of fraud that was alerted


def flag_metrics(frame: pd.DataFrame, flag_column: str = "flagged_by_old_rules") -> dict:  # legacy-rule baseline
    """Treat every flagged row as an alert (the legacy rule can't fill an hourly budget)."""  # docstring
    alerts = frame[frame[flag_column] == 1]  # flagged rows
    caught = int(alerts["fraud_label"].sum())  # fraud among them
    total = int(frame["fraud_label"].sum())  # all fraud
    return {"alerts": len(alerts), "fraud_caught": caught, "fraud_total": total,  # counts
            "precision_at_budget": _ratio(caught, len(alerts)), "recall_at_budget": _ratio(caught, total)}  # ratios


def pr_auc(labels: Iterable[int], scores: Iterable[float]) -> float | None:  # area under the precision-recall curve
    """Average precision; None when the window has no fraud."""  # docstring
    labels = list(labels)  # materialise once
    if sum(labels) == 0:  # undefined without positives
        return None  # report as missing
    return float(average_precision_score(labels, list(scores)))  # scikit-learn's definition


def flatten_metrics(prefix: str, results: dict[str, dict]) -> dict[str, float]:  # MLflow-ready flat dict
    """{"model": {"alerts": 3}} -> {"<prefix>_model_alerts": 3.0}; None values are skipped."""  # docstring
    return {f"{prefix}_{name}_{key}": float(value)  # one flat key per metric
            for name, metrics in results.items() for key, value in metrics.items() if value is not None}  # skip None
