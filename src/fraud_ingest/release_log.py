"""Record of every released or held step: makes release runs repeatable and traceable."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
from __future__ import annotations         # modern type hints on 3.11

from dataclasses import asdict, dataclass  # immutable row type + dict conversion
from typing import Any, Protocol           # loose Spark type + interface

RELEASE_LOG_COLUMNS = (  # Delta column schema; must match sql/10_fraud_ingest_setup.sql
    "step INT, segment STRING, file_name STRING, scenario STRING, status STRING, released_at STRING"  # six columns
)  # end RELEASE_LOG_COLUMNS


# ── Row type and interface ────────────────────────────────────
@dataclass(frozen=True)  # immutable so a logged row can never be mutated after the fact
class ReleaseEntry:  # one row of the release log: a released or held PaySim step
    step: int          # PaySim step
    segment: str       # backfill / replay / drift
    file_name: str     # landing file name (for held steps: the future _late name)
    scenario: str      # "", "duplicate", "late", or "schema_change" / "malformed" joined with "+"
    status: str        # "released" or "held"
    released_at: str   # ISO-8601 UTC time of the log write


class ReleaseLogStore(Protocol):  # interface both log implementations satisfy
    def entries(self) -> list[ReleaseEntry]: ...                    # every row so far
    def append(self, entry: ReleaseEntry) -> None: ...              # add one row
    def append_many(self, entries: list[ReleaseEntry]) -> None: ...  # add many rows in one write (e.g. a backfill run)


# ── Implementations ───────────────────────────────────────────
class InMemoryReleaseLog:  # list-backed log store, used by local tests
    """List-backed log for local tests."""  # docstring

    def __init__(self) -> None:  # start with an empty log
        self._entries: list[ReleaseEntry] = []  # rows in append order

    def entries(self) -> list[ReleaseEntry]:  # return every row logged so far
        return list(self._entries)  # copy so callers cannot mutate the log

    def append(self, entry: ReleaseEntry) -> None:  # add one row to the log
        self._entries.append(entry)  # add the row

    def append_many(self, entries: list[ReleaseEntry]) -> None:  # add many rows in one call
        self._entries.extend(entries)  # list-backed, so a batch is just an extend


class DeltaReleaseLog:  # Delta-table-backed log store, used on Databricks
    """Delta-table log used in the workspace (verified by the V2-V4 runs, not locally)."""  # docstring

    def __init__(self, spark: Any, table: str) -> None:  # bind to a running SparkSession and a table name
        self._spark = spark  # active SparkSession
        self._table = table  # e.g. workspace.fraud.release_log

    def entries(self) -> list[ReleaseEntry]:  # read every row of the Delta table back as ReleaseEntry
        rows = self._spark.table(self._table).collect()  # at most ~800 rows, safe to collect
        return [ReleaseEntry(**row.asDict()) for row in rows]  # Spark Row -> ReleaseEntry

    def append(self, entry: ReleaseEntry) -> None:  # append one row to the Delta table
        frame = self._spark.createDataFrame([asdict(entry)], schema=RELEASE_LOG_COLUMNS)  # one-row DataFrame
        frame.write.mode("append").saveAsTable(self._table)  # append to the Delta table

    def append_many(self, entries: list[ReleaseEntry]) -> None:  # append every row as a single Delta write
        if not entries:  # nothing to write (e.g. an already-complete backfill)
            return  # avoid writing an empty DataFrame
        frame = self._spark.createDataFrame([asdict(e) for e in entries], schema=RELEASE_LOG_COLUMNS)  # one DataFrame for the whole batch
        frame.write.mode("append").saveAsTable(self._table)  # one append covering every row
