"""Model builders, comparison on a time-based window, scoring helper, importances, step chunking (spec §5-6)."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
from __future__ import annotations  # modern type hints on 3.11

from typing import Iterable         # loose sequence type

import numpy as np                  # score arrays
import pandas as pd                 # frames
from sklearn.ensemble import HistGradientBoostingClassifier  # gradient-boosted trees, NaN-aware
from sklearn.impute import SimpleImputer  # fills NaN for the linear baseline
from sklearn.inspection import permutation_importance  # model-agnostic importances
from sklearn.linear_model import LogisticRegression  # baseline
from sklearn.pipeline import Pipeline  # steps bundled into one logged model
from sklearn.preprocessing import StandardScaler  # scales inputs for the linear model

from fraud_model.features import MODEL_FEATURES, build_feature_frame  # shared builder
from fraud_model.metrics import budget_metrics, pr_auc  # evaluation

MODEL_NAMES = ("gradient_boosted_trees", "logistic_regression")  # comparison order (ties go to the first)


# ── Builders ──────────────────────────────────────────────────
def build_models(seed: int) -> dict[str, Pipeline]:  # fresh, untrained pipelines
    """Gradient-boosted trees (NaN-aware) and a logistic baseline (impute 0 + missing flags + scaling)."""  # docstring
    return {  # one entry per MODEL_NAMES
        "gradient_boosted_trees": Pipeline([  # the main model
            ("model", HistGradientBoostingClassifier(class_weight="balanced", random_state=seed)),  # balanced classes
        ]),  # end trees
        "logistic_regression": Pipeline([  # the baseline
            ("impute", SimpleImputer(strategy="constant", fill_value=0.0, add_indicator=True,  # 0 plus "was missing" flags
                                     keep_empty_features=True)),  # ruling P3: never drop an all-missing column
            ("scale", StandardScaler()),  # comparable coefficients
            ("model", LogisticRegression(class_weight="balanced", max_iter=1000)),  # balanced classes
        ]),  # end logistic
    }  # end models


# ── Comparison ────────────────────────────────────────────────
def compare_models(models: dict[str, Pipeline], fit_x: pd.DataFrame, fit_y: pd.Series,  # training data
                   compare_x: pd.DataFrame, compare_meta: pd.DataFrame, budget: int) -> tuple[str, dict[str, dict]]:  # held-out window
    """Fit every model in place, score the comparison window, and pick the highest PR-AUC (ties: MODEL_NAMES order)."""  # docstring
    results: dict[str, dict] = {}  # metrics per model
    for name in MODEL_NAMES:  # fixed order
        models[name].fit(fit_x, fit_y)  # train
        scored = compare_meta.assign(score=models[name].predict_proba(compare_x)[:, 1])  # probability of fraud
        results[name] = {**budget_metrics(scored, "score", budget), "pr_auc": pr_auc(scored["fraud_label"], scored["score"])}  # metrics
    winner = max(MODEL_NAMES, key=lambda n: (results[n]["pr_auc"] if results[n]["pr_auc"] is not None else -1.0,  # best PR-AUC...
                                            -MODEL_NAMES.index(n)))  # ...ties to the earlier name
    return winner, results  # name and all metrics


# ── Scoring helper ────────────────────────────────────────────
def risk_scores(model: Pipeline, input_frame: pd.DataFrame) -> np.ndarray:  # Silver-shaped rows in, scores out
    """Fraud probability per row, built through the same feature builder as training."""  # docstring
    return model.predict_proba(build_feature_frame(input_frame))[:, 1]  # class-1 probability


# ── Importances ───────────────────────────────────────────────
def feature_importances(model: Pipeline, x: pd.DataFrame, y: pd.Series, seed: int,  # fitted model and data
                        max_samples: int = 200_000) -> dict[str, float]:  # sample cap keeps it fast
    """Mean drop in average precision when each feature is shuffled (3 repeats)."""  # docstring
    result = permutation_importance(model, x, y, scoring="average_precision", n_repeats=3, random_state=seed,  # shuffle test
                                    max_samples=min(max_samples, len(x)))  # never more rows than exist
    return {name: float(value) for name, value in zip(MODEL_FEATURES, result.importances_mean)}  # by feature name


# ── Chunking ──────────────────────────────────────────────────
def step_chunks(steps: Iterable[int], size: int) -> list[list[int]]:  # bounded memory per toPandas()
    """Sorted unique steps cut into lists of at most `size`; empty input gives no chunks."""  # docstring
    ordered = sorted(set(steps))  # unique, ascending
    return [ordered[i:i + size] for i in range(0, len(ordered), size)]  # consecutive slices
