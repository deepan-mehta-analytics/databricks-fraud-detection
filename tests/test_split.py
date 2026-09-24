"""Tests for the one-time CSV -> outbox split (spec §5.1-5.2)."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
import json                 # parse written JSON lines
from pathlib import Path    # filesystem paths

import pytest               # raises() helper

from conftest import write_paysim_csv          # CSV builder from tests/conftest.py
from fraud_ingest.split import split_csv       # function under test

EXPECTED_FIELDS = {  # every field a record must carry (spec §5.2)
    "transaction_id", "step", "transaction_time", "transaction_type", "amount",  # identity, time, type, value
    "sender_account", "sender_balance_before", "sender_balance_after",           # sender side
    "receiver_account", "receiver_balance_before", "receiver_balance_after",     # receiver side
    "fraud_label", "flagged_by_old_rules",                                       # labels
}  # end EXPECTED_FIELDS


def read_lines(path: Path) -> list[dict]:  # read JSON Lines file and parse each line
    """Parse one JSON object per line from a .jsonl file."""  # docstring
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]  # one dict per JSON line


def test_one_file_per_step_in_segment_folders(sample_csv, tmp_path):  # verify folder structure and file counts per segment
    """One .jsonl file per distinct step, organized in segment folders."""  # docstring
    totals = split_csv(sample_csv, tmp_path / "outbox")  # split the 50-row sample
    assert totals == {"rows": 50, "fraud": 5, "files": 10}  # 10 distinct steps, every 10th row fraud
    assert sorted(p.name for p in (tmp_path / "outbox" / "backfill").iterdir()) == [  # steps 1, 2, 336
        "paysim_step-0001_backfill.jsonl", "paysim_step-0002_backfill.jsonl", "paysim_step-0336_backfill.jsonl",  # expected names
    ]  # end expected backfill files list
    assert len(list((tmp_path / "outbox" / "replay").iterdir())) == 3  # steps 337, 338, 408
    assert len(list((tmp_path / "outbox" / "drift").iterdir())) == 4   # steps 409, 410, 742, 743


def test_records_use_plain_names_and_real_types(sample_csv, tmp_path):  # verify field renaming and type conversion
    """Records use contract field names and correct JSON types."""  # docstring
    split_csv(sample_csv, tmp_path / "outbox")  # write the outbox
    first = read_lines(tmp_path / "outbox" / "backfill" / "paysim_step-0001_backfill.jsonl")[0]  # first record
    assert set(first) == EXPECTED_FIELDS                   # exactly the contract fields
    assert first["transaction_id"] == "ps-0000001"         # row-number ID
    assert first["transaction_time"] == "2026-01-01T00:00:00Z"  # anchor + 0 hours
    assert first["amount"] == 23695249.33                  # scientific notation converted to a plain number
    assert first["step"] == 1 and first["fraud_label"] == 0  # integers, not strings
    assert first["transaction_type"] == "TRANSFER"         # renamed from "type"


def test_ids_follow_original_row_numbers(sample_csv, tmp_path):  # verify transaction IDs track original data-row positions
    """Transaction IDs are deterministic from the 1-based data-row number."""  # docstring
    split_csv(sample_csv, tmp_path / "outbox")  # write the outbox
    last_file = tmp_path / "outbox" / "drift" / "paysim_step-0743_drift.jsonl"  # last step's file
    assert read_lines(last_file)[-1]["transaction_id"] == "ps-0000050"  # 50th data row


def test_split_is_deterministic(sample_csv, tmp_path):  # verify identical input produces identical output
    """Running split_csv twice on the same input produces byte-identical files."""  # docstring
    split_csv(sample_csv, tmp_path / "a")  # first run
    split_csv(sample_csv, tmp_path / "b")  # second run
    for file_a in (tmp_path / "a").rglob("*.jsonl"):  # every file from run 1
        file_b = tmp_path / "b" / file_a.relative_to(tmp_path / "a")  # matching file from run 2
        assert file_a.read_bytes() == file_b.read_bytes()  # byte-identical


def test_rejects_csv_not_sorted_by_step(tmp_path):  # verify split_csv rejects unsorted input
    """split_csv raises ValueError if the CSV's step column is not sorted ascending."""  # docstring
    csv_path = write_paysim_csv(tmp_path / "bad.csv", [2, 1])  # step goes backwards
    with pytest.raises(ValueError, match="not sorted"):  # the split relies on sorted input
        split_csv(csv_path, tmp_path / "outbox")  # should refuse
