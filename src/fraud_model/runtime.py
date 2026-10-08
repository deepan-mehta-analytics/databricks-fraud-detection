"""Runtime guards for the model notebooks: library versions and the 'no model yet' error (final review I1, I2)."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
from __future__ import annotations  # modern type hints on 3.11

import re                           # leading digits of a version string

# ── Constants ─────────────────────────────────────────────────
MISSING_MODEL_ERROR_CODES = ("RESOURCE_DOES_NOT_EXIST", "NOT_FOUND")  # registry codes that mean "nothing registered or promoted yet"


# ── 'No model yet' versus a real failure ──────────────────────
def is_missing_model(error_code: str | None) -> bool:  # I1: only a not-found error may skip scoring
    """True only for the not-found codes; permission, outage and every other error must fail the task."""  # docstring
    return error_code in MISSING_MODEL_ERROR_CODES  # anything else is a real failure


# ── Library versions ──────────────────────────────────────────
def _major_minor(version: str) -> tuple[int, int]:  # "3.12.1rc0" -> (3, 12)
    numbers = [int(re.match(r"\d+", part).group()) for part in version.split(".")[:2]]  # leading digits of the first two parts
    return numbers[0], numbers[1] if len(numbers) > 1 else 0  # a missing minor counts as 0


def runtime_problems(mlflow_version: str, sklearn_version: str,  # running libraries
                     model_sklearn_version: str | None = None) -> list[str]:  # the version the model was trained with
    """Problems that make the notebook unsafe to run: MLflow older than 3, or a scikit-learn minor-version mismatch."""  # docstring
    problems = []  # collected messages
    if _major_minor(mlflow_version)[0] < 3:  # log_model(name=...) and the registry defaults need MLflow 3
        problems.append(f"MLflow 3 is required, found {mlflow_version}: pick serverless environment 4 or later")  # how to fix
    if model_sklearn_version and _major_minor(model_sklearn_version) != _major_minor(sklearn_version):  # pickles differ across minors
        problems.append(f"Model was trained with scikit-learn {model_sklearn_version} but this run has {sklearn_version}: "  # what...
                        "run training and scoring in the same serverless environment version")  # ...and how to fix
    return problems  # empty means safe
