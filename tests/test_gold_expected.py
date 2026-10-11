"""Local Gold calculator (spec §5-6, §12): alert budget, closing cutoff, late-alert rule, Silver counts."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
from collections import Counter  # expected tallies

import pytest  # raises helper

from fraud_gold.expected import (  # the calculator under test
    CLOSE_DELAY_STEPS, alerts_per_step, closed_cases, closing_cutoff, is_late_alert, silver_payments_per_step,  # rules
)  # end import
from fraud_silver.expected import BronzeScenario, iter_bronze_records, judge  # Silver simulation


def test_alerts_cap_at_the_budget_and_keep_short_hours():  # min(50, payments) per hour
    assert alerts_per_step({337: 16000, 339: 10, 340: 0}) == {337: 50, 339: 10}  # full hour capped, short hour kept, empty dropped


def test_alerts_reject_a_budget_below_one():  # a zero budget would silently alert nothing
    with pytest.raises(ValueError):  # refuse
        alerts_per_step({337: 5}, budget=0)  # nonsense budget


def test_closing_cutoff_is_three_simulated_days_back():  # 24 x LABEL_DELAY_DAYS_DEFAULT
    assert CLOSE_DELAY_STEPS == 72  # three simulated days
    assert closing_cutoff(418) == 346  # today's newest scored hour


def test_closed_cases_include_the_cutoff_hour():  # step <= cutoff closes
    alerts = {345: 50, 346: 50, 347: 50}  # three hours
    assert closed_cases(alerts, 346) == 100  # 345 and 346, not 347


def test_late_payment_must_beat_the_lowest_alert_in_a_full_hour():  # the hour's budget is used up
    issued = [0.9] * 49 + [0.4]  # 50 alerts, lowest 0.4
    assert is_late_alert(issued, 0.5) is True  # would have made the top 50
    assert is_late_alert(issued, 0.4) is False  # a tie loses (it would not have displaced the 50th)
    assert is_late_alert(issued, 0.1) is False  # below the bar


def test_late_payment_always_alerts_in_a_short_hour():  # Review Focus 1: budget left over
    assert is_late_alert([0.9, 0.8], 0.01) is True  # 2 alerts < 50: room for one more


def test_late_rule_needs_an_alerted_hour():  # a never-alerted hour is ranked fresh, not treated as late
    with pytest.raises(ValueError):  # refuse
        is_late_alert([], 0.5)  # no alerts yet


def test_silver_payments_per_step_counts_ok_rows_from_the_first_step(sample_csv):  # conftest: 5 rows per step
    scenario = BronzeScenario(last_step=410, held_steps=frozenset(), duplicate_steps=frozenset(),  # Bronze up to 410...
                              malformed_step=None, malformed_rows=0)  # ...with no scenarios
    counts = silver_payments_per_step(judge(iter_bronze_records(sample_csv, scenario)))  # from 337 by default
    assert counts == Counter({337: 5, 338: 5, 408: 5, 409: 5, 410: 5})  # hours 1, 2 and 336 are training data
