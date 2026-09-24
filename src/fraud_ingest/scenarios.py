"""Opt-in problem scenarios applied to released copies (never to outbox files)."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
import hashlib  # stable hash for the synthetic channel
import json     # parse and re-serialise records

# ── Constants ─────────────────────────────────────────────────
CHANNELS = ("app", "ussd", "agent")  # SYNTHETIC values: PaySim has no channel; never a model feature
MALFORMED_AMOUNT = "not-a-number"    # text that cannot parse as DECIMAL(18,2), so it lands in _rescued_data


# ── Transforms ────────────────────────────────────────────────
def synthetic_channel(transaction_id: str) -> str:  # deterministic, signal-free channel derived from the transaction ID
    """Deterministic, signal-free channel derived from the transaction ID."""  # docstring
    digest = hashlib.sha256(transaction_id.encode("utf-8")).digest()  # stable across runs and machines
    return CHANNELS[digest[0] % len(CHANNELS)]  # pick one of the three values


def transform_lines(lines: list[str], *, add_channel: bool, malformed_rows: int) -> list[str]:  # apply scenarios to JSON lines: add channel and/or break amounts
    """Return new JSON lines with a channel added and/or the first N amounts broken."""  # docstring
    out: list[str] = []  # transformed lines
    for index, line in enumerate(lines):  # each record, in file order
        record = json.loads(line)  # parse the record
        if add_channel:  # schema-change scenario is on for this file
            record["channel"] = synthetic_channel(record["transaction_id"])  # new field
        if index < malformed_rows:  # malformed scenario covers this row
            record["amount"] = MALFORMED_AMOUNT  # type mismatch on a typed field
        out.append(json.dumps(record))  # re-serialise without a trailing newline
    return out  # caller joins with newlines
