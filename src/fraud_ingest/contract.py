"""Record contract shared by the producer (split, release) and the consumer (ingest)."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
from datetime import datetime, timedelta, timezone  # UTC timestamp arithmetic

# ── Segment boundaries (docs/GAPS.md G-10, ADR 0007) ──────────
BACKFILL_LAST_STEP = 336  # end of day 14: history loaded on the first run (training)
REPLAY_LAST_STEP = 408    # end of day 17: released a few steps per run (scoring)
LAST_STEP = 743           # end of day 31: drift scenario only
SEGMENT_RANGES = {  # inclusive (first, last) step per segment, in release order
    "backfill": (1, BACKFILL_LAST_STEP),                    # days 1-14
    "replay": (BACKFILL_LAST_STEP + 1, REPLAY_LAST_STEP),   # days 15-17
    "drift": (REPLAY_LAST_STEP + 1, LAST_STEP),             # days 18-31
}  # end SEGMENT_RANGES

ANCHOR_DEFAULT = "2026-01-01T00:00:00Z"  # synthetic date for step 1 (PaySim has no real dates)
TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"       # ISO-8601 UTC, which Spark's JSON reader parses as TIMESTAMP

# ── PaySim column -> plain-language record field ──────────────
FIELD_MAP = {  # source header -> contract field (spec §5.2)
    "step": "step",                                   # simulated hour
    "type": "transaction_type",                       # PAYMENT, TRANSFER, ...
    "amount": "amount",                               # transaction value
    "nameOrig": "sender_account",                     # paying account
    "oldbalanceOrg": "sender_balance_before",         # leaks the label: never a feature (ADR 0006)
    "newbalanceOrig": "sender_balance_after",         # leaks the label: never a feature
    "nameDest": "receiver_account",                   # receiving account
    "oldbalanceDest": "receiver_balance_before",      # leaks the label: never a feature
    "newbalanceDest": "receiver_balance_after",       # leaks the label: never a feature
    "isFraud": "fraud_label",                         # ground truth; hidden from scoring by a view
    "isFlaggedFraud": "flagged_by_old_rules",         # PaySim's legacy rule flag
}  # end FIELD_MAP
INT_FIELDS = ("step", "fraud_label", "flagged_by_old_rules")  # written as JSON integers
DECIMAL_FIELDS = (  # written as JSON numbers, typed DECIMAL(18,2) in Bronze
    "amount", "sender_balance_before", "sender_balance_after",  # sender side
    "receiver_balance_before", "receiver_balance_after",        # receiver side
)  # end DECIMAL_FIELDS

# ── Auto Loader schema hints (typed fields send bad values to _rescued_data) ──
SCHEMA_HINTS = ", ".join(  # SQL schema syntax, one "name TYPE" per field
    ["transaction_id STRING", "step INT", "transaction_time TIMESTAMP", "transaction_type STRING"]  # identity and time
    + [f"{name} DECIMAL(18,2)" for name in DECIMAL_FIELDS]  # money columns
    + ["sender_account STRING", "receiver_account STRING", "fraud_label INT", "flagged_by_old_rules INT"]  # accounts and labels
)  # end SCHEMA_HINTS


# ── Helpers ───────────────────────────────────────────────────
def segment_for_step(step: int) -> str:  # returns segment name for a given step
    """Return the segment (backfill / replay / drift) a PaySim step belongs to."""  # docstring
    for name, (first, last) in SEGMENT_RANGES.items():  # check each segment in order
        if first <= step <= last:  # step falls inside this segment
            return name  # found it
    raise ValueError(f"step {step} is outside PaySim's range 1..{LAST_STEP}")  # no such step


def outbox_file_name(step: int, segment: str, suffix: str = "") -> str:  # format flat file name for outbox step file
    """Flat file name for one step; suffix marks scenario copies (_dup-01, _late, _malformed)."""  # docstring
    return f"paysim_step-{step:04d}_{segment}{suffix}.jsonl"  # no step= folders (Auto Loader would infer partitions)


def make_transaction_id(row_number: int) -> str:  # create transaction ID from row number
    """Deterministic ID from the 1-based data-row number in the original CSV."""  # docstring
    return f"ps-{row_number:07d}"  # 7 digits covers all 6,362,620 rows


def transaction_time_for_step(step: int, anchor: str = ANCHOR_DEFAULT) -> str:  # calculate ISO-8601 timestamp for step
    """Hourly event time: anchor + (step - 1) hours, as ISO-8601 UTC."""  # docstring
    start = datetime.strptime(anchor, TIME_FORMAT).replace(tzinfo=timezone.utc)  # parse the anchor as UTC
    return (start + timedelta(hours=step - 1)).strftime(TIME_FORMAT)  # step 1 = anchor itself


def volume_path(catalog: str, schema: str, volume: str) -> str:  # format Unity Catalog volume mount path
    """POSIX path of a Unity Catalog volume, as seen from Databricks compute."""  # docstring
    return f"/Volumes/{catalog}/{schema}/{volume}"  # standard UC volume mount
