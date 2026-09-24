"""Core release rules: backfill first, K steps per run, no double release (spec §6)."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
from pathlib import Path  # filesystem paths

import pytest             # raises() helper

from fraud_ingest.release import ReleaseOptions, options_from_params, run_release  # names under test
from fraud_ingest.release_log import InMemoryReleaseLog, ReleaseEntry              # test log store


def fixed_clock() -> str:  # deterministic clock stub used by every test
    return "2026-09-24T00:00:00.000000Z"  # deterministic release time


def release(outbox: Path, landing: Path, log: InMemoryReleaseLog, **options) -> list[ReleaseEntry]:  # helper: run one release with the fixed clock
    return run_release(outbox, landing, log, ReleaseOptions(**options), clock=fixed_clock)  # one release run


def test_first_run_releases_all_backfill_and_nothing_else(full_outbox, tmp_path):  # first run must release only backfill
    log = InMemoryReleaseLog()  # empty log = first run ever
    out = release(full_outbox, tmp_path / "landing", log)  # run once
    assert [e.step for e in out] == list(range(1, 337))  # steps 1..336
    assert {e.segment for e in out} == {"backfill"}  # backfill only
    assert len(list((tmp_path / "landing").iterdir())) == 336  # one file per step


def test_later_runs_release_k_replay_steps(full_outbox, tmp_path):  # replay runs release K steps, honoring a custom K
    log = InMemoryReleaseLog()  # fresh log
    release(full_outbox, tmp_path / "landing", log)  # backfill run
    out = release(full_outbox, tmp_path / "landing", log)  # first replay run
    assert [e.step for e in out] == [337, 338, 339, 340, 341, 342]  # default K = 6
    out = release(full_outbox, tmp_path / "landing", log, steps_per_run=2)  # custom K
    assert [e.step for e in out] == [343, 344]  # continues from the pointer


def test_full_replay_takes_twelve_runs_then_stops(full_outbox, tmp_path):  # replay segment exhausts after 12 runs and then no-ops
    log = InMemoryReleaseLog()  # fresh log
    release(full_outbox, tmp_path / "landing", log)  # backfill run
    for _ in range(12):  # 72 replay steps / 6 per run
        release(full_outbox, tmp_path / "landing", log)  # replay run
    assert release(full_outbox, tmp_path / "landing", log) == []  # 13th run: nothing left, no-op
    names = [e.file_name for e in log.entries()]  # every released file
    assert len(names) == len(set(names)) == 336 + 72  # nothing released twice


def test_drift_needs_the_explicit_segment(full_outbox, tmp_path):  # drift never auto-starts once replay is exhausted
    log = InMemoryReleaseLog()  # fresh log
    for _ in range(13):  # backfill + all 12 replay runs
        release(full_outbox, tmp_path / "landing", log)  # release
    assert release(full_outbox, tmp_path / "landing", log) == []  # default segment stays on replay
    out = release(full_outbox, tmp_path / "landing", log, segment="drift")  # explicit drift
    assert [e.step for e in out] == [409, 410, 411, 412, 413, 414]  # drift starts at 409


def test_crash_between_copy_and_log_is_repaired(full_outbox, tmp_path):  # a copied-but-unlogged file gets overwritten cleanly and logged once
    landing = tmp_path / "landing"  # landing folder
    landing.mkdir()  # create it
    (landing / "paysim_step-0001_backfill.jsonl").write_text("partial", encoding="utf-8")  # copied, never logged
    log = InMemoryReleaseLog()  # the log never recorded it
    release(full_outbox, landing, log)  # rerun
    original = (full_outbox / "backfill" / "paysim_step-0001_backfill.jsonl").read_text(encoding="utf-8")  # true content
    assert (landing / "paysim_step-0001_backfill.jsonl").read_text(encoding="utf-8") == original  # overwritten cleanly
    assert [e.step for e in log.entries()].count(1) == 1  # logged exactly once


def test_interrupted_backfill_resumes_where_it_stopped(full_outbox, tmp_path):  # a partially logged backfill resumes at the first missing step
    log = InMemoryReleaseLog()  # simulate a first run that died after step 100
    for step in range(1, 101):  # steps already logged
        log.append(ReleaseEntry(step, "backfill", f"f{step}", "", "released", fixed_clock()))  # prior rows
    out = release(full_outbox, tmp_path / "landing", log)  # rerun
    assert [e.step for e in out] == list(range(101, 337))  # only the missing backfill steps


def test_options_from_params_defaults_and_parsing():  # widget-string params parse to the right typed options
    assert options_from_params({}) == ReleaseOptions()  # empty widgets -> defaults
    parsed = options_from_params({  # every parameter as a job would pass it (strings)
        "steps_per_run": "3", "segment": "drift", "duplicate_step": "340", "hold_steps": "345, 346",  # first four
        "release_held": "true", "schema_change_from_step": "360", "malformed_step": "350", "malformed_rows": "5",  # rest
    })  # end params dict
    assert parsed == ReleaseOptions(3, "drift", 340, frozenset({345, 346}), True, 360, 350, 5)  # all parsed


def test_options_reject_bad_values():  # invalid option combinations raise ValueError
    with pytest.raises(ValueError):  # only replay and drift can be released on demand
        ReleaseOptions(segment="backfill")  # backfill is automatic
    with pytest.raises(ValueError):  # at least one step per run
        ReleaseOptions(steps_per_run=0)  # zero
    with pytest.raises(ValueError):  # malformed rows need a target step
        ReleaseOptions(malformed_rows=5)  # step missing


def test_duplicate_redrop_keeps_channel_when_source_had_it(full_outbox, tmp_path):  # duplicate re-drops must be faithful re-deliveries, including any schema change
    log = InMemoryReleaseLog()  # fresh log
    release(full_outbox, tmp_path / "landing", log)  # backfill run
    release(full_outbox, tmp_path / "landing", log, schema_change_from_step=337)  # releases 337..342, each carrying channel
    out = release(full_outbox, tmp_path / "landing", log, duplicate_step=338)  # duplicate step 338, which has channel
    dup_entry = next(e for e in out if e.scenario == "duplicate")  # the duplicate row logged this run
    assert dup_entry.file_name == "paysim_step-0338_replay_dup-01.jsonl"  # expected duplicate file name
    dup_lines = (tmp_path / "landing" / dup_entry.file_name).read_text(encoding="utf-8").splitlines()  # every record in the duplicate file
    assert dup_lines and all('"channel"' in line for line in dup_lines)  # channel present on every record, matching the source


def test_options_from_params_zero_steps_per_run_is_rejected():  # "0" must not silently become the default 6
    with pytest.raises(ValueError):  # zero steps per run is invalid
        options_from_params({"steps_per_run": "0"})  # explicit zero
    assert options_from_params({"steps_per_run": ""}).steps_per_run == 6  # unset still defaults to 6
