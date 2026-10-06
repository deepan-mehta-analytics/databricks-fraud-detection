"""Local reference for Silver: expected verdicts and features from the PaySim CSV, no Spark (spec §5-6, §8)."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
from __future__ import annotations  # modern type hints on 3.11

import csv                          # stream the CSV row by row
from array import array             # compact first-copy store for ps- IDs
from collections import Counter     # verdict totals
from dataclasses import dataclass   # immutable scenario description
from decimal import Decimal         # exact money values, like Bronze's DECIMAL(18,2)
from pathlib import Path            # filesystem paths
from typing import Any, Callable, Iterable, Iterator  # type hints

from fraud_ingest.contract import ANCHOR_DEFAULT, LAST_STEP, transaction_time_for_step  # shared contract
from fraud_ingest.split import csv_row_to_record  # the exact producer conversion

# ── Constants ─────────────────────────────────────────────────
KNOWN_TYPES = frozenset({"PAYMENT", "TRANSFER", "CASH_OUT", "CASH_IN", "DEBIT"})  # rule 5
CONTENT_FIELDS = (  # source fields compared between copies (metadata and channel excluded)
    "step", "transaction_time", "transaction_type", "amount", "sender_account", "receiver_account",  # payment
    "sender_balance_before", "sender_balance_after", "receiver_balance_before", "receiver_balance_after",  # balances
    "fraud_label", "flagged_by_old_rules",  # labels
)  # end CONTENT_FIELDS
MONEY_FIELDS = (  # fields held as Decimal, like DECIMAL(18,2) in Bronze
    "amount", "sender_balance_before", "sender_balance_after", "receiver_balance_before", "receiver_balance_after",  # all money
)  # end MONEY_FIELDS
CENT = Decimal("0.01")  # two decimal places


# ── Scenario ──────────────────────────────────────────────────
@dataclass(frozen=True)  # one immutable description of a Bronze state
class BronzeScenario:  # which steps and scenario copies Bronze holds
    last_step: int                    # highest released step
    held_steps: frozenset[int]        # held steps not yet released
    duplicate_steps: frozenset[int]   # steps whose file was re-dropped once
    malformed_step: int | None        # step whose first rows had broken amounts
    malformed_rows: int               # how many rows were broken


TODAY_SCENARIO = BronzeScenario(  # Bronze as measured on 2026-09-24 (the late step 345 has since arrived)
    last_step=408, held_steps=frozenset(), duplicate_steps=frozenset({340}),  # replay finished, step 340 twice
    malformed_step=350, malformed_rows=5,  # five broken amounts at step 350
)  # end TODAY_SCENARIO


# ── Bronze simulation ─────────────────────────────────────────
def _to_bronze(record: dict[str, Any]) -> dict[str, Any]:  # convert producer floats to Bronze-like Decimals
    out = dict(record)  # copy, never mutate the caller's dict
    for name in MONEY_FIELDS:  # every money column
        out[name] = Decimal(repr(out[name])).quantize(CENT)  # float -> exact 2-dp Decimal
    out["rescued"] = False  # parsed cleanly
    return out  # Bronze-like record


def iter_bronze_records(csv_path: str | Path, scenario: BronzeScenario,  # yield Bronze rows in arrival order
                        anchor: str = ANCHOR_DEFAULT) -> Iterator[dict[str, Any]]:  # anchor must match the outbox
    """Yield the rows Bronze would hold for `scenario`, in arrival order (re-dropped copies last)."""  # docstring
    copies: list[dict[str, Any]] = []  # duplicate-file rows, delivered after the originals
    broken_left = scenario.malformed_rows  # rows still to break in the malformed step
    with open(csv_path, newline="", encoding="utf-8") as handle:  # stream the CSV
        for row_number, row in enumerate(csv.DictReader(handle), start=1):  # 1-based data rows, like split.py
            step = int(row["step"])  # this row's step
            if step > scenario.last_step:  # the file is step-sorted, so nothing later is released
                break  # stop reading
            if step in scenario.held_steps:  # held files are not in Bronze yet
                continue  # skip
            record = _to_bronze(csv_row_to_record(row, row_number, anchor))  # producer record as Bronze sees it
            if step == scenario.malformed_step and broken_left > 0:  # malformed scenario covers this row
                record["amount"] = None  # text amount fails the DECIMAL hint
                record["rescued"] = True  # the text lands in _rescued_data
                broken_left -= 1  # one fewer to break
            yield record  # original delivery
            if step in scenario.duplicate_steps:  # this step's file was re-dropped
                copies.append(dict(record))  # identical copy, delivered later
    yield from copies  # re-dropped files arrive after the originals


# ── Rules 1-8 ─────────────────────────────────────────────────
def rule_verdict(record: dict[str, Any], anchor: str = ANCHOR_DEFAULT) -> str | None:  # first broken rule, or None
    """Return the first broken rule's verdict (spec §5 rules 1-8), or None if the row passes."""  # docstring
    if record.get("transaction_id") is None:  # rule 1
        return "missing_id"  # no ID
    if record.get("transaction_time") is None:  # rule 2
        return "missing_time"  # no event time
    step = record.get("step")  # step for rule 3
    if step is None or not 1 <= step <= LAST_STEP or record["transaction_time"] != transaction_time_for_step(step, anchor):  # rule 3
        return "time_step_mismatch"  # step missing, out of range or inconsistent with the time
    amount = record.get("amount")  # amount for rule 4
    if amount is None or amount < 0:  # rule 4: zero is allowed
        return "bad_amount"  # missing or negative
    if record.get("transaction_type") not in KNOWN_TYPES:  # rule 5
        return "unknown_type"  # unexpected type
    if record.get("sender_account") is None or record.get("receiver_account") is None:  # rule 6
        return "missing_account"  # an account is missing
    if record.get("fraud_label") not in (0, 1) or record.get("flagged_by_old_rules") not in (0, 1):  # rule 7
        return "bad_label"  # label not 0/1
    if record.get("rescued"):  # rule 8
        return "unparsed_value"  # some typed field failed to parse
    return None  # passes rules 1-8


# ── Rule 9: duplicates ────────────────────────────────────────
class _FirstCopies:  # remembers the content of each ID's first valid copy
    """Content hash per ID: an array for ps-NNNNNNN IDs (6.4M x 8 bytes), a dict for anything else."""  # docstring

    def __init__(self) -> None:  # empty store
        self._numbered = array("q")  # index = row number, value = content hash (0 = unseen)
        self._other: dict[str, int] = {}  # IDs that are not ps-NNNNNNN

    def get_or_set(self, transaction_id: str, content: int) -> int | None:  # return the earlier hash, or store this one
        content = content or 1  # 0 is the "unseen" marker
        if transaction_id.startswith("ps-") and transaction_id[3:].isdigit():  # producer-style ID
            index = int(transaction_id[3:])  # row number
            if index >= len(self._numbered):  # grow the array to reach this index
                self._numbered.extend([0] * (index + 1 - len(self._numbered)))  # pad with "unseen"
            earlier = self._numbered[index]  # stored hash, or 0
            if earlier:  # seen before
                return earlier  # hand back the first copy's hash
            self._numbered[index] = content  # remember this first copy
            return None  # this is the first copy
        earlier = self._other.get(transaction_id)  # other ID styles
        if earlier is None:  # first time
            self._other[transaction_id] = content  # remember it
        return earlier  # None for a first copy


def _content(record: dict[str, Any]) -> int:  # hash of the payment's own fields
    return hash(tuple(record.get(name) for name in CONTENT_FIELDS))  # metadata and channel excluded


def judge(records: Iterable[dict[str, Any]], anchor: str = ANCHOR_DEFAULT) -> Iterator[tuple[str, dict[str, Any]]]:  # verdict per row
    """Yield (verdict, record) in arrival order; duplicates are ranked among valid rows only."""  # docstring
    first_copies = _FirstCopies()  # content of each ID's first valid copy
    for record in records:  # arrival order = iteration order
        broken = rule_verdict(record, anchor)  # rules 1-8
        if broken is not None:  # failed a rule
            yield broken, record  # rejected under that rule
            continue  # not ranked as a copy
        content = _content(record)  # payment content
        earlier = first_copies.get_or_set(record["transaction_id"], content)  # first copy's content, if any
        if earlier is None:  # first valid copy
            yield "ok", record  # becomes the Silver row
        elif earlier == (content or 1):  # same content as the first copy
            yield "duplicate_copy", record  # removed and counted
        else:  # same ID, different content
            yield "conflicting_duplicate", record  # rejected


def count_verdicts(judged: Iterable[tuple[str, dict[str, Any]]]) -> Counter[str]:  # verdict -> rows
    return Counter(verdict for verdict, _ in judged)  # tally


# ── Strict-past features ──────────────────────────────────────
def features_for_receiver(ok_records_factory: Callable[[], Iterable[dict[str, Any]]],  # re-iterable source of ok rows
                          receiver_account: str) -> list[dict[str, Any]]:  # one feature row per payment to this receiver
    """Features (spec §6) for every ok payment to one receiver; reads the source twice."""  # docstring
    mine = [r for r in ok_records_factory() if r["receiver_account"] == receiver_account]  # pass 1: this receiver's payments
    senders = {r["sender_account"] for r in mine}  # senders whose history we need
    sender_steps: dict[str, list[int]] = {s: [] for s in senders}  # pass 2: their payment steps
    for r in ok_records_factory():  # every ok payment
        if r["sender_account"] in sender_steps:  # one of our senders
            sender_steps[r["sender_account"]].append(r["step"])  # remember the step
    out: list[dict[str, Any]] = []  # results
    for r in sorted(mine, key=lambda x: (x["step"], x["transaction_id"])):  # stable order
        frame = [h for h in mine if r["step"] - 24 <= h["step"] <= r["step"] - 1]  # RANGE 24..1 PRECEDING
        amounts = [h["amount"] for h in frame]  # money in the frame
        total = sum(amounts, Decimal("0")) if amounts else None  # SUM over an empty frame is null
        average = float(total) / len(amounts) if amounts else None  # average incoming amount
        out.append({  # one feature row
            "transaction_id": r["transaction_id"], "step": r["step"],  # keys
            "sender_account": r["sender_account"], "receiver_account": receiver_account,  # accounts
            "receiver_payments_previous_hour": sum(1 for h in mine if h["step"] == r["step"] - 1),  # RANGE 1..1 PRECEDING
            "receiver_payments_last_24_hours": len(frame),  # count, 0 when empty
            "receiver_amount_last_24_hours": total,  # sum, null when empty
            "receiver_largest_amount_last_24_hours": max(amounts) if amounts else None,  # max, null when empty
            "receiver_distinct_senders_last_24_hours": len({h["sender_account"] for h in frame}),  # size(collect_set)
            "amount_vs_receiver_average_24_hours": (float(r["amount"]) / average) if average else None,  # try_divide: null on 0/none
            "sender_earlier_payments": sum(1 for s in sender_steps[r["sender_account"]] if s < r["step"]),  # UNBOUNDED..1 PRECEDING
        })  # end feature row
    return out  # feature rows


def suggest_receiver(ok_records: Iterable[dict[str, Any]], first_step: int, last_step: int) -> str | None:  # spot-check pick
    """The receiver with the most ok payments in [first_step, last_step]; ties go to the smallest ID."""  # docstring
    counts = Counter(r["receiver_account"] for r in ok_records if first_step <= r["step"] <= last_step)  # payments per receiver
    if not counts:  # nothing in range
        return None  # no suggestion
    return min(counts, key=lambda k: (-counts[k], k))  # busiest, then alphabetical
