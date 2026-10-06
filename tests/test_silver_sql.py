"""Text-level guards on the Silver pipeline SQL (spec §5-6). CI has no Spark, so logic is proven in S1-S6."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
import re                 # pattern checks
from pathlib import Path  # locate the SQL files

SQL_DIR = Path(__file__).resolve().parents[1] / "pipelines" / "silver"  # pipeline source folder
FILES = ["01_checked_transactions.sql", "02_transactions.sql",  # verdict view and clean table
         "03_rejected_transactions.sql", "04_transaction_features.sql"]  # rejected shelf and features
VERDICTS = ["missing_id", "missing_time", "time_step_mismatch", "bad_amount", "unknown_type",  # rules 1-5
            "missing_account", "bad_label", "unparsed_value", "duplicate_copy", "conflicting_duplicate"]  # rules 6-9
EXPECTATIONS = ["has_id", "has_time", "time_matches_step", "amount_valid", "type_known",  # rules 1-5
                "accounts_present", "labels_valid", "fully_parsed", "first_copy"]  # rules 6-9
CLEAN_COLUMNS = ["transaction_id", "step", "transaction_time", "transaction_type", "amount",  # payment
                 "sender_account", "receiver_account", "fraud_label", "flagged_by_old_rules",  # parties + labels
                 "source_file", "file_arrived_at", "ingested_at"]  # lineage (12 columns, spec §6 ②)
FORBIDDEN = ["channel", "sender_balance_before", "sender_balance_after",  # synthetic field and...
             "receiver_balance_before", "receiver_balance_after"]  # ...label-leaking balances (ADR 0006)


def code(name: str) -> str:  # SQL text with -- comments removed (comments may name forbidden columns)
    text = (SQL_DIR / name).read_text(encoding="utf-8")  # raw file
    return "\n".join(line.split("--", 1)[0] for line in text.splitlines())  # strip comments


def test_all_four_files_exist():  # the pipeline lists exactly these
    assert sorted(p.name for p in SQL_DIR.glob("*.sql")) == FILES  # no extra or missing files


def test_checked_view_is_private_and_names_every_verdict_and_expectation():  # spec §5
    sql = code(FILES[0])  # verdict view
    assert "CREATE OR REFRESH PRIVATE MATERIALIZED VIEW silver_checked_transactions" in sql  # not published
    for verdict in VERDICTS:  # every verdict
        assert f"'{verdict}'" in sql, verdict  # appears as a literal
    for name in EXPECTATIONS:  # every expectation
        assert re.search(rf"CONSTRAINT {name} EXPECT", sql), name  # declared


def test_clean_table_has_fail_guards_and_takes_only_ok_rows():  # spec §6 ②
    sql = code(FILES[1])  # clean table
    for guard in ("transaction_id", "transaction_time", "amount"):  # guarded columns
        assert re.search(rf"EXPECT \({guard} IS NOT NULL\) ON VIOLATION FAIL UPDATE", sql), guard  # fail loudly
    assert "verdict = 'ok'" in sql  # only clean rows
    selected = re.search(r"AS SELECT(.+?)FROM", sql, re.S).group(1)  # the column list
    assert [c.strip() for c in selected.split(",")] == CLEAN_COLUMNS  # fixed list, in order (Q6)
    assert "*" not in selected  # never a wildcard: new Bronze columns must not leak in


def test_rejected_shelf_excludes_ok_and_removed_copies():  # spec §6 ③
    sql = code(FILES[2])  # rejected shelf
    assert "verdict NOT IN ('ok', 'duplicate_copy')" in sql  # everything else is shelved
    assert "AS rejection_reason" in sql  # reason column


def test_no_file_names_channel_or_balances_in_code():  # Q6 + Review Focus 4
    for name in FILES:  # every SQL file
        sql = code(name)  # code only
        for column in FORBIDDEN:  # forbidden names
            if name == FILES[0] and column != "channel":  # the content hash must compare balances between copies
                continue  # allowed in the verdict view only
            assert not re.search(rf"\b{column}\b", sql), f"{column} in {name}"  # never selected


def test_every_feature_frame_ends_one_step_back():  # Q3 strict past
    sql = code(FILES[3])  # features
    frames = re.findall(r"RANGE BETWEEN (.+?) AND (.+?)\)", sql)  # (start, end) of each frame
    assert len(frames) == 8  # previous hour, count, sum, max, collect_set, ratio sum, ratio count, sender history
    assert sql.count("OVER (") == len(frames)  # every window has an explicit strict-past frame (none default)
    assert all(end.strip() == "1 PRECEDING" for _, end in frames)  # never the current step
    assert "try_divide" in sql  # ratio never raises divide-by-zero (Review Focus 1-2)
