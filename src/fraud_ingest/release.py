"""Release task: copy the next PaySim steps from the outbox into the landing folder."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
from __future__ import annotations                       # modern type hints on 3.11

from dataclasses import dataclass, field                 # immutable options
from datetime import datetime, timezone                  # release timestamps
from pathlib import Path                                  # filesystem paths
from typing import Callable                               # clock type

from fraud_ingest.contract import SEGMENT_RANGES, outbox_file_name, segment_for_step  # shared contract
from fraud_ingest.release_log import ReleaseEntry, ReleaseLogStore                    # log row + interface
from fraud_ingest.scenarios import transform_lines                                     # scenario transforms

PARAM_NAMES = (  # job parameters the release notebook reads (strings; "" means unset)
    "steps_per_run", "segment", "duplicate_step", "hold_steps",                # pacing and first scenarios
    "release_held", "schema_change_from_step", "malformed_step", "malformed_rows",  # remaining scenarios
)


# ── Options ───────────────────────────────────────────────────
@dataclass(frozen=True)  # immutable options; every release run is fully described by one of these
class ReleaseOptions:  # everything one call to run_release needs, beyond the log and directories
    steps_per_run: int = 6                                  # K steps per run (72 replay steps = 12 runs)
    segment: str = "replay"                                 # "drift" must be chosen explicitly
    duplicate_step: int | None = None                       # re-drop this released step under a new name
    hold_steps: frozenset[int] = field(default_factory=frozenset)  # skip these steps when their turn comes
    release_held: bool = False                              # release previously held steps as _late files
    schema_change_from_step: int | None = None              # add `channel` from this step onward
    malformed_step: int | None = None                       # step whose file gets broken amounts
    malformed_rows: int = 0                                 # how many rows to break

    def __post_init__(self) -> None:  # validate the combination of options right after construction
        if self.segment not in ("replay", "drift"):  # backfill is released automatically
            raise ValueError(f"segment must be 'replay' or 'drift', got {self.segment!r}")  # reject
        if self.steps_per_run < 1:  # a run must release something
            raise ValueError("steps_per_run must be at least 1")  # reject
        if self.malformed_rows < 0 or (self.malformed_rows and self.malformed_step is None):  # need a target
            raise ValueError("malformed_rows needs malformed_step and must not be negative")  # reject


def options_from_params(params: dict[str, str]) -> ReleaseOptions:  # build typed options from string job parameters
    """Build options from job/widget parameters, where every value is a string."""  # docstring
    def text(key: str) -> str:  # read a parameter, defaulting missing keys to ""
        return params.get(key, "").strip()  # missing -> ""

    def optional_int(key: str) -> int | None:  # parse an optional integer parameter
        return int(text(key)) if text(key) else None  # "" -> None

    return ReleaseOptions(  # assemble options
        steps_per_run=optional_int("steps_per_run") or 6,  # default K
        segment=text("segment") or "replay",  # default segment
        duplicate_step=optional_int("duplicate_step"),  # optional
        hold_steps=frozenset(int(p) for p in text("hold_steps").split(",") if p.strip()),  # "345, 346" -> {345, 346}
        release_held=text("release_held").lower() == "true",  # only the exact word true enables it
        schema_change_from_step=optional_int("schema_change_from_step"),  # optional
        malformed_step=optional_int("malformed_step"),  # optional
        malformed_rows=optional_int("malformed_rows") or 0,  # default none
    )


def utc_now_iso() -> str:  # default clock used by run_release when the caller doesn't supply one
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")  # current UTC time as text


# ── File writing ──────────────────────────────────────────────
def _write_release(outbox_dir: str | Path, landing_dir: str | Path, step: int, segment: str,  # copy (and optionally transform) one step's file into landing
                   suffix: str, add_channel: bool, malformed_rows: int) -> str:  # remaining params: name suffix + scenario toggles
    """Copy one step's outbox file to landing (optionally transformed); return the landing name."""  # docstring
    source = Path(outbox_dir) / segment / outbox_file_name(step, segment)  # original file (never modified)
    lines = source.read_text(encoding="utf-8").splitlines()  # one record per line
    if add_channel or malformed_rows:  # a scenario changes this copy
        lines = transform_lines(lines, add_channel=add_channel, malformed_rows=malformed_rows)  # transform
    name = outbox_file_name(step, segment, suffix)  # landing name, with any scenario suffix
    Path(landing_dir).mkdir(parents=True, exist_ok=True)  # make sure landing exists
    (Path(landing_dir) / name).write_text("\n".join(lines) + "\n", encoding="utf-8")  # write (overwrite if re-run)
    return name  # name for the log


def _channel_from(entries: list[ReleaseEntry], options: ReleaseOptions) -> int | None:  # earliest step that should carry the `channel` field
    """First step carrying `channel`: once the producer upgrades, it stays upgraded."""  # docstring
    logged = [e.step for e in entries if "schema_change" in e.scenario]  # steps already released with channel
    candidates = logged + ([options.schema_change_from_step] if options.schema_change_from_step else [])  # plus flag
    return min(candidates) if candidates else None  # earliest wins


# ── Release run ───────────────────────────────────────────────
def run_release(outbox_dir: str | Path, landing_dir: str | Path, log: ReleaseLogStore,  # release the next batch of files, following backfill-first, K-per-run, no-double-release rules
                options: ReleaseOptions, clock: Callable[[], str] = utc_now_iso) -> list[ReleaseEntry]:  # remaining params: options for this run + injectable clock
    """Release the next files. Copy first, then log, so a retried run never double-releases."""  # docstring
    entries = log.entries()  # history before this run
    released: list[ReleaseEntry] = []  # rows written by this run

    def record(step: int, segment: str, file_name: str, scenario: str, status: str) -> None:  # write one row to both the log and this run's result list
        entry = ReleaseEntry(step, segment, file_name, scenario, status, clock())  # build the row
        log.append(entry)  # persist it
        released.append(entry)  # return it to the caller

    # ── Backfill first; also finishes an interrupted first run ──
    first, last = SEGMENT_RANGES["backfill"]  # steps 1..336
    done = {e.step for e in entries if e.segment == "backfill"}  # already released backfill steps
    if len(done) < last - first + 1:  # backfill not complete yet
        for step in range(first, last + 1):  # every backfill step
            if step not in done:  # skip steps already released
                record(step, "backfill", _write_release(outbox_dir, landing_dir, step, "backfill", "", False, 0), "", "released")  # copy + log
        return released  # a backfill run releases nothing else

    # ── Validate the duplicate request before copying anything ──
    if options.duplicate_step is not None and not any(  # flag set but...
        e.step == options.duplicate_step and e.status == "released" and e.scenario not in ("duplicate", "late")  # ...no earlier normal release
        for e in entries  # only earlier runs count
    ):
        raise ValueError(f"step {options.duplicate_step} has not been released yet, so it cannot be duplicated")  # refuse; nothing copied

    # ── Next K steps of the chosen segment ──
    channel_from = _channel_from(entries, options)  # schema-change start, if any
    first, last = SEGMENT_RANGES[options.segment]  # segment bounds
    seen = [e.step for e in entries if e.segment == options.segment]  # includes held, duplicate and late rows
    start = max(seen) + 1 if seen else first  # pointer; duplicates and late rows are never above it
    for step in range(start, min(start + options.steps_per_run - 1, last) + 1):  # next K steps
        if step in options.hold_steps:  # late-file scenario: skip now
            record(step, options.segment, outbox_file_name(step, options.segment, "_late"), "late", "held")  # log the hold
            continue  # no file this run
        add_channel = channel_from is not None and step >= channel_from  # schema change applies
        malformed = options.malformed_rows if step == options.malformed_step else 0  # malformed applies
        name = _write_release(outbox_dir, landing_dir, step, options.segment,  # copy the step
                              "_malformed" if malformed else "", add_channel, malformed)  # suffix + transforms
        tags = [tag for tag, on in (("schema_change", add_channel), ("malformed", malformed > 0)) if on]  # active scenarios
        record(step, options.segment, name, "+".join(tags), "released")  # log it

    # ── Duplicate file scenario ──
    if options.duplicate_step is not None:  # flag set
        step = options.duplicate_step  # step to re-drop (validated above)
        count = sum(1 for e in entries if e.step == step and e.scenario == "duplicate")  # earlier duplicates
        segment = segment_for_step(step)  # the step's own segment
        record(step, segment, _write_release(outbox_dir, landing_dir, step, segment, f"_dup-{count + 1:02d}", False, 0), "duplicate", "released")  # plain re-drop

    # ── Late file scenario ──
    if options.release_held:  # flag set
        already_late = {e.step for e in entries if e.scenario == "late" and e.status == "released"}  # released before
        held = sorted({e.step for e in entries if e.status == "held"} - already_late)  # held in earlier runs only
        for step in held:  # each outstanding held step
            segment = segment_for_step(step)  # its segment
            add_channel = channel_from is not None and step >= channel_from  # keep the schema consistent
            record(step, segment, _write_release(outbox_dir, landing_dir, step, segment, "_late", add_channel, 0), "late", "released")  # release late

    return released  # rows written this run ([] means nothing to release)
