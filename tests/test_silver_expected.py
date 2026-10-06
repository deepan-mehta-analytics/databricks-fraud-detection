"""The local Silver reference: verdict rules, duplicates and strict-past features (spec §5-6)."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
from decimal import Decimal  # exact money values

import pytest  # assertion helpers

from conftest import write_paysim_csv  # PaySim-shaped CSV builder shared with the ingest tests
from fraud_ingest.contract import transaction_time_for_step  # hourly event time
from fraud_silver.expected import (  # module under test
    BronzeScenario,          # which Bronze state to simulate
    count_verdicts,          # verdict -> count
    features_for_receiver,   # strict-past features for one receiver
    iter_bronze_records,     # CSV + scenario -> Bronze-like records
    judge,                   # records -> (verdict, record)
    rule_verdict,            # rules 1-8 for one record
    suggest_receiver,        # pick a busy receiver for the spot check
)  # end import from fraud_silver.expected


# ── Helpers ───────────────────────────────────────────────────
def record(**overrides) -> dict:  # build one valid Bronze-like record, then apply overrides
    base = {  # a record that passes every rule
        "transaction_id": "ps-0000001", "step": 1, "transaction_time": transaction_time_for_step(1),  # identity and time
        "transaction_type": "TRANSFER", "amount": Decimal("10.00"),  # type and money
        "sender_account": "C1", "receiver_account": "M1",  # accounts
        "sender_balance_before": Decimal("0"), "sender_balance_after": Decimal("0"),  # sender balances
        "receiver_balance_before": Decimal("0"), "receiver_balance_after": Decimal("0"),  # receiver balances
        "fraud_label": 0, "flagged_by_old_rules": 0, "rescued": False,  # labels and parse flag
    }  # end base record
    base.update(overrides)  # apply the test's changes
    return base  # finished record


# ── Rules 1-8 ─────────────────────────────────────────────────
@pytest.mark.parametrize(("overrides", "expected"), [  # one case per rule, in precedence order
    ({}, None),                                                        # valid record passes
    ({"transaction_id": None}, "missing_id"),                          # rule 1
    ({"transaction_time": None}, "missing_time"),                      # rule 2
    ({"step": None}, "time_step_mismatch"),                            # rule 3: no step
    ({"step": 744}, "time_step_mismatch"),                             # rule 3: out of range
    ({"step": 2}, "time_step_mismatch"),                               # rule 3: time does not match step
    ({"amount": None}, "bad_amount"),                                  # rule 4: missing
    ({"amount": Decimal("-0.01")}, "bad_amount"),                      # rule 4: negative
    ({"amount": Decimal("0")}, None),                                  # zero is allowed (all 4 real zero rows are fraud)
    ({"transaction_type": "REFUND"}, "unknown_type"),                  # rule 5
    ({"receiver_account": None}, "missing_account"),                   # rule 6
    ({"fraud_label": 2}, "bad_label"),                                 # rule 7
    ({"flagged_by_old_rules": None}, "bad_label"),                     # rule 7: missing label
    ({"rescued": True}, "unparsed_value"),                             # rule 8
    ({"transaction_id": None, "amount": None}, "missing_id"),          # first broken rule wins
])  # end parametrize
def test_rule_verdict_returns_first_broken_rule(overrides, expected):  # each rule fires in precedence order
    assert rule_verdict(record(**overrides)) == expected  # verdict matches the spec table


# ── Rule 9: duplicates ────────────────────────────────────────
def test_identical_later_copy_is_a_duplicate_copy():  # same content twice
    judged = list(judge([record(), record()]))  # arrival order = list order
    assert [v for v, _ in judged] == ["ok", "duplicate_copy"]  # first kept, second removed


def test_different_later_copy_is_a_conflicting_duplicate():  # same ID, different amount
    judged = list(judge([record(), record(amount=Decimal("99.00"))]))  # second copy disagrees
    assert [v for v, _ in judged] == ["ok", "conflicting_duplicate"]  # second goes to the rejected shelf


def test_bad_first_copy_lets_a_good_later_copy_through():  # ranking only counts valid rows
    judged = list(judge([record(amount=None), record()]))  # broken copy arrives first
    assert [v for v, _ in judged] == ["bad_amount", "ok"]  # the good copy becomes Silver


def test_content_ignores_delivery_details():  # metadata never makes copies differ
    first = record(source_file="a.jsonl", file_arrived_at=1, ingested_at=1, channel=None)  # original delivery
    second = record(source_file="a_dup-01.jsonl", file_arrived_at=2, ingested_at=2, channel="app")  # re-delivery
    assert [v for v, _ in judge([first, second])] == ["ok", "duplicate_copy"]  # still identical


# ── Bronze simulation from the CSV ────────────────────────────
def test_simulation_reproduces_duplicate_and_malformed_scenarios(tmp_path):  # mirrors the Phase 2 scenarios
    csv_path = write_paysim_csv(tmp_path / "p.csv", [1, 1, 2, 2, 2, 3])  # 6 rows over 3 steps
    scenario = BronzeScenario(last_step=3, held_steps=frozenset(), duplicate_steps=frozenset({1}),  # step 1 twice
                              malformed_step=2, malformed_rows=2)  # first 2 rows of step 2 broken
    counts = count_verdicts(judge(iter_bronze_records(csv_path, scenario)))  # verdict totals
    assert counts == {"ok": 4, "bad_amount": 2, "duplicate_copy": 2}  # 6 + 2 copies = 8 rows


def test_simulation_skips_held_and_later_steps(tmp_path):  # held steps and steps past last_step are absent
    csv_path = write_paysim_csv(tmp_path / "p.csv", [1, 2, 3, 4])  # one row per step
    scenario = BronzeScenario(last_step=3, held_steps=frozenset({2}), duplicate_steps=frozenset(),  # hold 2, stop at 3
                              malformed_step=None, malformed_rows=0)  # no broken rows
    steps = [r["step"] for r in iter_bronze_records(csv_path, scenario)]  # simulated Bronze steps
    assert steps == [1, 3]  # 2 held, 4 not released yet


# ── Strict-past features ──────────────────────────────────────
def history() -> list[dict]:  # receiver M9 gets 4 payments; one same-step, one outside 24 h
    return [  # arrival order
        record(transaction_id="t1", step=1, transaction_time=transaction_time_for_step(1), sender_account="A",  # 26 h before t4
               receiver_account="M9", amount=Decimal("100.00")),  # outside the 24-step frame of t4
        record(transaction_id="t2", step=10, transaction_time=transaction_time_for_step(10), sender_account="B",  # inside the frame
               receiver_account="M9", amount=Decimal("0.00")),  # zero amount stays clean
        record(transaction_id="t3", step=26, transaction_time=transaction_time_for_step(26), sender_account="B",  # previous hour of t4
               receiver_account="M9", amount=Decimal("40.00")),  # same sender as t2
        record(transaction_id="t4", step=27, transaction_time=transaction_time_for_step(27), sender_account="A",  # the payment we judge
               receiver_account="M9", amount=Decimal("60.00")),  # its features come from t2 and t3 only
        record(transaction_id="t5", step=27, transaction_time=transaction_time_for_step(27), sender_account="C",  # same step as t4
               receiver_account="M9", amount=Decimal("5.00")),  # must not be counted for t4
    ]  # end history


def test_features_count_only_earlier_steps_within_24():  # strict past, RANGE 24..1 PRECEDING
    rows = {f["transaction_id"]: f for f in features_for_receiver(history, "M9")}  # features by ID
    t4 = rows["t4"]  # the judged payment
    assert t4["receiver_payments_previous_hour"] == 1  # only t3 (step 26)
    assert t4["receiver_payments_last_24_hours"] == 2  # t2 and t3 (steps 3..26); t1 too old, t5 same step
    assert t4["receiver_amount_last_24_hours"] == Decimal("40.00")  # 0 + 40
    assert t4["receiver_largest_amount_last_24_hours"] == Decimal("40.00")  # max of 0 and 40
    assert t4["receiver_distinct_senders_last_24_hours"] == 1  # B twice
    assert t4["amount_vs_receiver_average_24_hours"] == pytest.approx(3.0)  # 60 / (40 / 2)
    assert t4["sender_earlier_payments"] == 1  # A paid once before (t1)
    assert rows["t5"]["receiver_payments_last_24_hours"] == 2  # same frame as t4: t4 is not counted for t5 either


def test_empty_history_gives_zero_counts_and_null_values():  # a receiver's first payment
    first = features_for_receiver(history, "M9")[0]  # t1 has no earlier payment
    assert first["receiver_payments_last_24_hours"] == 0  # count of an empty frame is 0
    assert first["receiver_distinct_senders_last_24_hours"] == 0  # size of an empty set is 0
    assert first["receiver_amount_last_24_hours"] is None  # sum of an empty frame is null
    assert first["receiver_largest_amount_last_24_hours"] is None  # max of an empty frame is null
    assert first["amount_vs_receiver_average_24_hours"] is None  # no average -> no ratio, no error


def test_zero_average_gives_null_ratio():  # history amounts sum to zero
    rows = [  # zero-amount payment then a normal one
        record(transaction_id="z1", step=5, transaction_time=transaction_time_for_step(5), amount=Decimal("0.00")),  # zero
        record(transaction_id="z2", step=6, transaction_time=transaction_time_for_step(6), amount=Decimal("10.00")),  # judged
    ]  # end rows
    z2 = features_for_receiver(lambda: rows, "M1")[1]  # features of the second payment
    assert z2["amount_vs_receiver_average_24_hours"] is None  # division by a zero average is null, not an error


def test_suggest_receiver_prefers_the_busiest_in_range():  # spot-check helper
    assert suggest_receiver(history(), 1, 30) == "M9"  # M9 is the only receiver
    assert suggest_receiver(history(), 100, 200) is None  # nothing in range


# ── Command-line tool ─────────────────────────────────────────
def test_cli_one_pass_matches_the_library(tmp_path):  # the one-pass CLI must agree with the multi-pass helpers
    import subprocess, sys  # run the script as the owner would
    from pathlib import Path  # locate the script
    csv_path = write_paysim_csv(tmp_path / "p.csv", [1, 1, 2, 2, 2, 3, 3, 3, 3, 3])  # 10 rows, row 10 is fraud
    scenario = BronzeScenario(last_step=3, held_steps=frozenset(), duplicate_steps=frozenset({1}),  # step 1 twice
                              malformed_step=2, malformed_rows=1)  # first row of step 2 broken
    counts = count_verdicts(judge(iter_bronze_records(csv_path, scenario)))  # library totals
    ok = [r for v, r in judge(iter_bronze_records(csv_path, scenario)) if v == "ok"]  # library Silver rows
    script = Path(__file__).resolve().parents[1] / "scripts" / "expected_silver.py"  # CLI path
    out = subprocess.run([sys.executable, str(script), "--csv", str(csv_path), "--last-step", "3",  # same scenario...
                          "--held-steps", "", "--duplicate-steps", "1", "--malformed-step", "2",  # ...flag by flag
                          "--malformed-rows", "1", "--suggest-from", "2", "--suggest-to", "3"],  # suggestion window
                         capture_output=True, text=True, check=True).stdout.splitlines()  # printed lines
    assert out[0] == (f"bronze_rows={sum(counts.values())} silver_rows={counts['ok']} rejected_rows=1 "  # accounting
                      f"duplicate_copies_removed={counts['duplicate_copy']}")  # 2 copies of step 1
    assert out[2] == f"silver_fraud={sum(r['fraud_label'] for r in ok)}"  # fraud total
    assert out[3] == f"suggested_receiver={suggest_receiver(ok, 2, 3)}"  # same pick rule
    assert sum(line.startswith("{") for line in out) == 1  # one feature row for the suggested receiver
