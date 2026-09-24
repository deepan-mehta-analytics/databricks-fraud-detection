"""The four opt-in problem scenarios produce exactly the files the spec's proofs rely on (spec §9)."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
import json                 # parse released lines
from pathlib import Path    # filesystem paths

import pytest               # raises() helper

from fraud_ingest.release import ReleaseOptions, run_release  # release run
from fraud_ingest.release_log import InMemoryReleaseLog        # test log store
from fraud_ingest.scenarios import CHANNELS, MALFORMED_AMOUNT  # scenario constants


def fixed_clock() -> str:  # deterministic clock so released_at never varies between runs
    return "2026-09-24T00:00:00.000000Z"  # deterministic release time


def release(outbox, landing, log, **options):  # convenience wrapper: build options and run one release
    return run_release(outbox, landing, log, ReleaseOptions(**options), clock=fixed_clock)  # one release run


def records(path: Path) -> list[dict]:  # read a released JSONL file back into a list of dicts
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]  # parse a released file


@pytest.fixture  # marks this function as a pytest fixture
def after_first_replay(full_outbox, tmp_path):  # state after backfill + the first replay run (steps 337..342)
    log = InMemoryReleaseLog()  # fresh log
    landing = tmp_path / "landing"  # landing folder
    release(full_outbox, landing, log)  # backfill run
    release(full_outbox, landing, log)  # replay run: steps 337..342
    return full_outbox, landing, log  # state for the scenario


def test_duplicate_redrops_a_released_step_under_new_names(after_first_replay):  # duplicate scenario numbers copies and matches the original bytes
    outbox, landing, log = after_first_replay  # state after 337..342
    out = release(outbox, landing, log, duplicate_step=340)  # releases 343..348 plus the duplicate
    dup = [e for e in out if e.scenario == "duplicate"]  # the duplicate row
    assert [(e.step, e.file_name) for e in dup] == [(340, "paysim_step-0340_replay_dup-01.jsonl")]  # first copy
    original = (outbox / "replay" / "paysim_step-0340_replay.jsonl").read_text(encoding="utf-8")  # outbox content
    assert (landing / "paysim_step-0340_replay_dup-01.jsonl").read_text(encoding="utf-8") == original  # identical rows
    out = release(outbox, landing, log, duplicate_step=340)  # duplicate again
    assert "paysim_step-0340_replay_dup-02.jsonl" in [e.file_name for e in out]  # numbered copy


def test_duplicate_of_unreleased_step_is_refused_before_copying(after_first_replay):  # a not-yet-released step cannot be duplicated, and nothing is copied
    outbox, landing, log = after_first_replay  # 400 is not released yet
    before = len(log.entries())  # log size before the bad run
    with pytest.raises(ValueError, match="not been released"):  # cannot duplicate the future
        release(outbox, landing, log, duplicate_step=400)  # refused
    assert len(log.entries()) == before  # nothing released or logged by the refused run
    assert not list(landing.glob("paysim_step-0343_*"))  # the normal next step was not copied either


def test_held_step_is_skipped_then_released_late_once(after_first_replay):  # hold_steps skips a step, release_held releases it once, later
    outbox, landing, log = after_first_replay  # state after 337..342
    out = release(outbox, landing, log, hold_steps=frozenset({345}))  # run covering 343..348
    assert [(e.step, e.status) for e in out if e.step == 345] == [(345, "held")]  # logged as held
    assert not list(landing.glob("paysim_step-0345_*"))  # no file yet
    assert [e.step for e in out if e.status == "released"] == [343, 344, 346, 347, 348]  # neighbours released
    out = release(outbox, landing, log, release_held=True)  # later run: 349..354 + the held step
    late = [e for e in out if e.scenario == "late"]  # late rows
    assert [(e.step, e.file_name, e.status) for e in late] == [(345, "paysim_step-0345_replay_late.jsonl", "released")]  # released late
    out = release(outbox, landing, log, release_held=True)  # asking again
    assert not [e for e in out if e.scenario == "late"]  # never released twice


def test_schema_change_adds_channel_from_the_step_onward_and_persists(after_first_replay):  # channel field appears from the flagged step and stays on in later runs
    outbox, landing, log = after_first_replay  # state after 337..342
    release(outbox, landing, log, schema_change_from_step=345)  # run covering 343..348
    assert "channel" not in records(landing / "paysim_step-0344_replay.jsonl")[0]  # before the change
    assert records(landing / "paysim_step-0345_replay.jsonl")[0]["channel"] in CHANNELS  # from the change on
    release(outbox, landing, log)  # next run without the flag: 349..354
    assert records(landing / "paysim_step-0349_replay.jsonl")[0]["channel"] in CHANNELS  # producer stays upgraded
    assert all("schema_change" in e.scenario for e in log.entries() if e.step >= 345 and e.segment == "replay")  # tagged


def test_malformed_rows_break_amounts_in_one_named_file(after_first_replay):  # malformed scenario breaks only the requested row count, in a distinctly named file
    outbox, landing, log = after_first_replay  # state after 337..342
    out = release(outbox, landing, log, malformed_step=344, malformed_rows=1)  # run covering 343..348
    assert [e.file_name for e in out if e.step == 344] == ["paysim_step-0344_replay_malformed.jsonl"]  # visible suffix
    rows = records(landing / "paysim_step-0344_replay_malformed.jsonl")  # the broken file
    assert rows[0]["amount"] == MALFORMED_AMOUNT and isinstance(rows[1]["amount"], float)  # only the first row broken
    assert [e.scenario for e in out if e.step == 344] == ["malformed"]  # tagged
