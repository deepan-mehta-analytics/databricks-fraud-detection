"""Tests for the opt-in problem scenarios' line transforms (spec §9)."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
import json  # build and parse JSON lines

from fraud_ingest.scenarios import (  # names under test
    CHANNELS,            # allowed synthetic channel values
    MALFORMED_AMOUNT,    # text that cannot be a DECIMAL
    synthetic_channel,   # deterministic channel
    transform_lines,     # applies scenarios to a file's lines
)

# ── Test data ─────────────────────────────────────────────────
LINES = [json.dumps({"transaction_id": f"ps-000000{i}", "amount": 10.5}) for i in (1, 2, 3)]  # three records


# ── Tests ─────────────────────────────────────────────────────
def test_channel_is_deterministic_and_from_the_allowed_set():  # synthetic_channel returns consistent values from the allowed set
    assert synthetic_channel("ps-0000001") == synthetic_channel("ps-0000001")  # same ID -> same channel
    assert {synthetic_channel(f"ps-{i:07d}") for i in range(1, 200)} <= set(CHANNELS)  # only allowed values


def test_add_channel_sets_the_field_on_every_line():  # add_channel=True adds a channel field to all records
    out = [json.loads(line) for line in transform_lines(LINES, add_channel=True, malformed_rows=0)]  # transform
    assert all(record["channel"] in CHANNELS for record in out)  # every record has a channel
    assert all(record["amount"] == 10.5 for record in out)  # nothing else changed


def test_malformed_rows_break_only_the_first_n_amounts():  # malformed_rows=N breaks the first N amounts
    out = [json.loads(line) for line in transform_lines(LINES, add_channel=False, malformed_rows=2)]  # transform
    assert [r["amount"] for r in out] == [MALFORMED_AMOUNT, MALFORMED_AMOUNT, 10.5]  # first two broken
    assert all("channel" not in r for r in out)  # no channel unless asked


def test_no_flags_keeps_records_unchanged():  # add_channel=False and malformed_rows=0 leaves records untouched
    out = transform_lines(LINES, add_channel=False, malformed_rows=0)  # transform with nothing on
    assert [json.loads(line) for line in out] == [json.loads(line) for line in LINES]  # same records
