"""Runtime guards for the model notebooks: library versions and the 'no model yet' error (final review I1, I2)."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
from fraud_model.runtime import MISSING_MODEL_ERROR_CODES, is_missing_model, runtime_problems  # code under test


def test_only_not_found_codes_mean_no_model_yet():  # I1: a real failure must never look like "no champion yet"
    assert set(MISSING_MODEL_ERROR_CODES) == {"RESOURCE_DOES_NOT_EXIST", "NOT_FOUND"}  # the accepted codes
    assert is_missing_model("RESOURCE_DOES_NOT_EXIST") and is_missing_model("NOT_FOUND")  # nothing registered or promoted
    for code in ("PERMISSION_DENIED", "INTERNAL_ERROR", "TEMPORARILY_UNAVAILABLE", "", None):  # real failures
        assert not is_missing_model(code)  # re-raised by the notebook, so the task fails loudly


def test_matching_environment_has_no_problems():  # serverless environment 6
    assert runtime_problems("3.12.0", "1.7.2", "1.7.2") == []  # same scikit-learn as the logged model


def test_mlflow_2_is_refused():  # I2: log_model(name=...) needs MLflow 3
    problems = runtime_problems("2.21.3", "1.7.2")  # an older environment
    assert len(problems) == 1 and "MLflow 3" in problems[0]  # one clear message


def test_scikit_learn_minor_mismatch_is_refused():  # I2: a pickled model across minor versions only warns otherwise
    problems = runtime_problems("3.12.0", "1.8.0", "1.7.2")  # scoring env differs from training env
    assert len(problems) == 1 and "1.7" in problems[0] and "1.8" in problems[0]  # names both versions


def test_patch_differences_and_unknown_logged_version_are_fine():  # same major.minor is compatible
    assert runtime_problems("3.12.1rc0", "1.7.1", "1.7.2") == []  # patch and pre-release suffixes ignored
    assert runtime_problems("3.0.0", "1.7.2", None) == []  # training itself has no logged version to compare
