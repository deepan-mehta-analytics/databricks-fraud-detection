"""One-time producer step: PaySim CSV -> one JSON Lines file per step in the outbox."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
from __future__ import annotations  # modern type hints on 3.11

import csv                          # stream the CSV line by line (Spark would not guarantee row order)
import json                         # write one JSON object per line
from decimal import Decimal         # exact parsing of values like 2.369524933E7
from pathlib import Path            # filesystem paths
from typing import TextIO           # type of an open file handle

from fraud_ingest.contract import (  # shared contract
    ANCHOR_DEFAULT,                 # default synthetic date for step 1
    DECIMAL_FIELDS,                 # money fields
    FIELD_MAP,                      # PaySim -> plain names
    INT_FIELDS,                     # integer fields
    make_transaction_id,            # deterministic ID
    outbox_file_name,               # flat file names
    segment_for_step,               # step -> segment
    transaction_time_for_step,      # step -> hourly time
)  # end import from fraud_ingest.contract


# ── Row conversion ────────────────────────────────────────────
def csv_row_to_record(row: dict[str, str], row_number: int, anchor: str = ANCHOR_DEFAULT) -> dict:  # convert one CSV row into a contract record
    """Convert one CSV row (1-based data-row number) into a contract record."""  # docstring
    record: dict = {"transaction_id": make_transaction_id(row_number)}  # ID first
    for source, target in FIELD_MAP.items():  # every PaySim column
        text = row[source]  # raw CSV text
        if target in INT_FIELDS:  # integer columns
            record[target] = int(text)  # "1" -> 1
        elif target in DECIMAL_FIELDS:  # money columns (max 2 decimal places, verified 2026-09-24)
            record[target] = float(Decimal(text))  # "2.369524933E7" -> 23695249.33
        else:  # text columns
            record[target] = text  # keep as-is
    record["transaction_time"] = transaction_time_for_step(record["step"], anchor)  # hourly event time
    return record  # finished record


# ── Split ─────────────────────────────────────────────────────
def split_csv(csv_path: str | Path, outbox_dir: str | Path, anchor: str = ANCHOR_DEFAULT) -> dict[str, int]:  # write one .jsonl per step to outbox
    """Write <outbox>/<segment>/paysim_step-NNNN_<segment>.jsonl for every step; return totals."""  # docstring
    totals = {"rows": 0, "fraud": 0, "files": 0}  # running counts for the V1 check
    current_step: int | None = None  # step of the file currently open
    handle: TextIO | None = None  # currently open output file
    try:  # always close the last file, even on error
        with open(csv_path, newline="", encoding="utf-8") as source:  # open the CSV
            for row_number, row in enumerate(csv.DictReader(source), start=1):  # 1-based data rows
                record = csv_row_to_record(row, row_number, anchor)  # convert the row
                step = record["step"]  # this row's step
                if step != current_step:  # a new step starts
                    if current_step is not None and step < current_step:  # step went backwards
                        raise ValueError(f"CSV is not sorted by step (row {row_number})")  # refuse
                    if handle is not None:  # a previous file is open
                        handle.close()  # finish it
                    segment = segment_for_step(step)  # backfill / replay / drift
                    folder = Path(outbox_dir) / segment  # segment sub-folder
                    folder.mkdir(parents=True, exist_ok=True)  # create it if needed
                    handle = open(folder / outbox_file_name(step, segment), "w", encoding="utf-8")  # new file
                    current_step = step  # remember which step is open
                    totals["files"] += 1  # count the file
                handle.write(json.dumps(record) + "\n")  # one record per line
                totals["rows"] += 1  # count the row
                totals["fraud"] += record["fraud_label"]  # count fraud rows
    finally:  # runs on success and on error
        if handle is not None:  # a file is still open
            handle.close()  # close it
    return totals  # counts for the caller
