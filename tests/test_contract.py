"""Tests for the shared record contract (spec §5, G-10 boundaries)."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
import pytest  # raises() helper

from fraud_ingest.contract import (  # names under test
    SCHEMA_HINTS,               # Auto Loader type hints
    make_transaction_id,        # producer-stamped ID
    outbox_file_name,           # flat file naming
    segment_for_step,           # step -> segment
    transaction_time_for_step,  # step -> synthetic hourly timestamp
    volume_path,                # Unity Catalog volume path
)  # end import from fraud_ingest.contract


def test_segment_boundaries_match_g10():  # test segment boundary values
    assert segment_for_step(1) == "backfill"    # first PaySim step
    assert segment_for_step(336) == "backfill"  # last training step (end of day 14)
    assert segment_for_step(337) == "replay"    # first live-replay step
    assert segment_for_step(408) == "replay"    # last live-replay step (end of day 17)
    assert segment_for_step(409) == "drift"     # first drift step
    assert segment_for_step(743) == "drift"     # last PaySim step


def test_segment_rejects_steps_outside_paysim():  # test out-of-range steps raise ValueError
    with pytest.raises(ValueError):  # step 0 does not exist
        segment_for_step(0)          # below range
    with pytest.raises(ValueError):  # step 744 does not exist
        segment_for_step(744)        # above range


def test_file_names_are_flat_and_zero_padded():  # test file naming format
    assert outbox_file_name(7, "backfill") == "paysim_step-0007_backfill.jsonl"  # no step= folder, 4-digit step
    assert outbox_file_name(340, "replay", "_dup-01") == "paysim_step-0340_replay_dup-01.jsonl"  # scenario suffix


def test_transaction_id_is_seven_digit_row_number():  # test transaction ID format
    assert make_transaction_id(1) == "ps-0000001"        # first data row
    assert make_transaction_id(6362620) == "ps-6362620"  # last data row of the real file


def test_transaction_time_is_hourly_from_anchor():  # test transaction time calculation
    assert transaction_time_for_step(1) == "2026-01-01T00:00:00Z"    # step 1 = anchor
    assert transaction_time_for_step(337) == "2026-01-15T00:00:00Z"  # replay starts on day 15
    assert transaction_time_for_step(743) == "2026-01-31T22:00:00Z"  # last step
    assert transaction_time_for_step(2, "2025-06-01T00:00:00Z") == "2025-06-01T01:00:00Z"  # custom anchor


def test_schema_hints_pin_the_typed_fields():  # test schema hints contain all required fields
    for hint in (  # each typed field from spec §5.2
        "step INT", "transaction_time TIMESTAMP", "amount DECIMAL(18,2)",  # core fields
        "sender_balance_before DECIMAL(18,2)", "receiver_balance_after DECIMAL(18,2)",  # sample balance fields
        "fraud_label INT", "flagged_by_old_rules INT",  # labels
    ):  # end schema-hint fields tuple
        assert hint in SCHEMA_HINTS  # hint present


def test_volume_path():  # test Unity Catalog volume path format
    assert volume_path("workspace", "fraud", "landing") == "/Volumes/workspace/fraud/landing"  # UC volume path shape
