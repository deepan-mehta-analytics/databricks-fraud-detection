"""Training windows follow the cut step and the label delay (spec §5, Q4)."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
import pytest                                       # assertions on raised errors

from fraud_model.windows import TrainingWindows, training_windows  # code under test


def test_default_delay_of_three_days_fits_1_216_and_compares_217_264():  # spec §5 D = 3
    assert training_windows() == TrainingWindows(1, 216, 217, 264)  # measured windows in the spec


def test_zero_delay_fits_1_288_and_compares_289_336():  # spec §5 D = 0 comparison run
    assert training_windows(label_delay_days=0) == TrainingWindows(1, 288, 289, 336)  # the whole backfill is "known"


def test_windows_raise_when_nothing_is_left_to_fit():  # a delay that eats the whole backfill
    with pytest.raises(ValueError, match="No fit steps left"):  # explicit error, not an empty fit
        training_windows(label_delay_days=13)  # 336 - 312 - 48 < 1


@pytest.mark.parametrize("delay, days", [(-1, 2), (3, 0)])  # negative delay; no comparison window
def test_windows_reject_impossible_settings(delay, days):  # guard the job parameters
    with pytest.raises(ValueError):  # refused before any arithmetic
        training_windows(label_delay_days=delay, comparison_days=days)  # bad settings
