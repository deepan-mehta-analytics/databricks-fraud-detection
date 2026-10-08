"""Training and comparison windows from the cut step and the label delay (spec §5, Q4)."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
from __future__ import annotations  # modern type hints on 3.11

from dataclasses import dataclass   # immutable window description

# ── Defaults (job YAML defaults must equal these; tests pin it) ──
STEPS_PER_DAY = 24                  # one PaySim step = one simulated hour
CUT_STEP_DEFAULT = 336              # last backfill step (G-10): training never looks past it
LABEL_DELAY_DAYS_DEFAULT = 3        # Q4: the last 3 days' fraud answers "aren't known yet"
COMPARISON_DAYS_DEFAULT = 2         # days held out at the end of training to compare models
NEGATIVE_SAMPLE_RATE_DEFAULT = 0.1  # share of non-fraud rows kept in the fit set
SEED_DEFAULT = 42                   # one seed for sampling and models
SCORE_FROM_STEP_DEFAULT = 337       # first replay step: scoring starts where training data ends
ALERT_BUDGET_DEFAULT = 50           # Q2: alerts per simulated hour


@dataclass(frozen=True)  # values never change after creation
class TrainingWindows:  # inclusive step ranges for fitting and comparing
    """Fit on steps fit_first..fit_last, compare models on compare_first..compare_last (inclusive)."""  # docstring
    fit_first: int      # first fit step (always 1)
    fit_last: int       # last fit step
    compare_first: int  # first comparison step
    compare_last: int   # last comparison step = cut_step minus the label delay


def training_windows(cut_step: int = CUT_STEP_DEFAULT, label_delay_days: int = LABEL_DELAY_DAYS_DEFAULT,  # cut and delay
                     comparison_days: int = COMPARISON_DAYS_DEFAULT) -> TrainingWindows:  # comparison length
    """Return the fit and comparison windows; raise ValueError if the settings leave nothing to fit."""  # docstring
    if label_delay_days < 0 or comparison_days < 1:  # a negative delay or no comparison window is meaningless
        raise ValueError("label_delay_days must be >= 0 and comparison_days must be >= 1")  # refuse early
    compare_last = cut_step - STEPS_PER_DAY * label_delay_days  # newest step whose label counts as known
    fit_last = compare_last - STEPS_PER_DAY * comparison_days   # fitting ends where comparison begins
    if fit_last < 1:  # the delay and comparison window swallowed the whole backfill
        raise ValueError(f"No fit steps left: cut_step={cut_step}, label_delay_days={label_delay_days}, "  # explain...
                         f"comparison_days={comparison_days}")  # ...with the offending values
    return TrainingWindows(1, fit_last, fit_last + 1, compare_last)  # inclusive ranges
