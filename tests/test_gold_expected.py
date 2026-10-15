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


def test_a_batch_of_late_payments_fills_only_the_room_left():  # final review M1: room first, then the bar
    from fraud_gold.expected import late_alerts_earned  # batch version of the late rule
    issued = [0.9] * 45 + [0.4]  # 46 alerts, lowest 0.4, room for 4
    late = [0.3, 0.2, 0.1, 0.05, 0.02, 0.01]  # 6 late payments, none beat 0.4
    assert late_alerts_earned(issued, late) == 4  # only the room is filled
    assert late_alerts_earned(issued, late + [0.5]) == 4  # 0.5 ranks first and takes one of the 4 places; it is not counted twice
    assert late_alerts_earned([0.9] * 50, [0.95, 0.91, 0.1]) == 2  # full hour: only those beating the lowest


# ── Monitoring printout (Phase 6a spec §5.5) ──────────────────
def test_silver_counts_split_payments_fraud_and_rejections():  # one pass gives every monitoring tally
    from fraud_gold.expected import silver_counts  # the one-pass counter
    judged = [  # (verdict, record) pairs like judge() yields
        ("ok", {"step": 337, "fraud_label": 1}),  # scored fraud
        ("ok", {"step": 337, "fraud_label": 0}),  # scored honest payment
        ("ok", {"step": 300, "fraud_label": 1}),  # training hour: not scored, not counted
        ("bad_amount", {"step": 350, "fraud_label": 0}),  # rejected
        ("duplicate_copy", {"step": 340, "fraud_label": 0}),  # identical copy: removed, not shelved
    ]  # end judged
    counts = silver_counts(judged)  # from hour 337 by default
    assert counts.payments == Counter({337: 2})  # clean scored payments per hour
    assert counts.fraud == Counter({337: 1})  # fraud per hour; no zero entries
    assert counts.rejected == Counter({"bad_amount": 1})  # copies are not rejections


def test_fraud_and_hours_with_verdicts_include_the_cutoff_hour():  # step <= cutoff has its verdicts
    from fraud_gold.expected import fraud_with_verdicts, hours_with_verdicts  # helpers
    assert fraud_with_verdicts({337: 3, 349: 2, 350: 9}, 349) == 5  # 337 and 349, not 350
    assert hours_with_verdicts({337: 50, 349: 40, 350: 50}, 349) == 2  # two hours have verdicts


def test_monitoring_printout_from_the_sample_csv(sample_csv):  # the script's --monitoring and --since lines
    import subprocess  # run the script as the owner would
    import sys  # this interpreter
    from pathlib import Path  # script path
    script = Path(__file__).resolve().parents[1] / "scripts" / "expected_gold.py"  # the calculator script
    out = subprocess.run([sys.executable, str(script), "--csv", str(sample_csv), "--last-step", "410",  # sample hours up to 410
                          "--monitoring", "--since", "408"], capture_output=True, text=True, check=True).stdout  # both printouts
    assert "closing_cutoff_step=338 closed_cases=10 open_cases=15" in out  # 410 - 72; hours 337-338 close
    assert "fraud_with_verdicts=1 hours_with_verdicts=2" in out  # one fraud row (index 20, hour 337)
    assert "newest_hour_at_every_stage=410" in out  # released = ingested = scored = flagged
    assert "rejected_rows={}" in out  # the sample has no broken rows
    assert "payments_after_step_408=10 fraud_after_step_408=1" in out  # hours 409-410, fraud at index 40
