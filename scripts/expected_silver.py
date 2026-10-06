"""Print the expected Silver numbers for a Bronze scenario (spec §8). Usage: see --help."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
import argparse  # command-line flags
import sys       # path setup
from pathlib import Path  # locate src/

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # import the package without installing it

from fraud_silver.expected import (  # noqa: E402  reference model
    BronzeScenario, TODAY_SCENARIO, count_verdicts, features_for_receiver,  # scenario + counting + features
    iter_bronze_records, judge, suggest_receiver,  # simulation + verdicts + spot-check pick
)  # end import


def steps(text: str) -> frozenset[int]:  # "340, 341" -> {340, 341}
    return frozenset(int(p) for p in text.split(",") if p.strip())  # ignore blanks


def main() -> None:  # parse flags, simulate Bronze, print the numbers
    parser = argparse.ArgumentParser(description=__doc__)  # flags
    parser.add_argument("--csv", required=True, type=Path)  # data/paysim.csv
    parser.add_argument("--last-step", type=int, default=TODAY_SCENARIO.last_step)  # highest released step
    parser.add_argument("--held-steps", type=steps, default=TODAY_SCENARIO.held_steps)  # not yet released
    parser.add_argument("--duplicate-steps", type=steps, default=TODAY_SCENARIO.duplicate_steps)  # re-dropped once
    parser.add_argument("--malformed-step", type=int, default=TODAY_SCENARIO.malformed_step)  # broken-amount step
    parser.add_argument("--malformed-rows", type=int, default=TODAY_SCENARIO.malformed_rows)  # broken rows
    parser.add_argument("--receiver", default=None)  # spot-check this receiver
    parser.add_argument("--suggest-from", type=int, default=None)  # or suggest one from this step...
    parser.add_argument("--suggest-to", type=int, default=None)  # ...to this step
    args = parser.parse_args()  # read flags
    scenario = BronzeScenario(args.last_step, args.held_steps, args.duplicate_steps,  # the Bronze state
                              args.malformed_step, args.malformed_rows)  # scenario copies

    def ok_records():  # re-iterable source of ok rows (re-reads the CSV each call)
        return (r for v, r in judge(iter_bronze_records(args.csv, scenario)) if v == "ok")  # ok only

    counts = count_verdicts(judge(iter_bronze_records(args.csv, scenario)))  # verdict totals
    bronze = sum(counts.values())  # all Bronze rows
    rejected = bronze - counts["ok"] - counts["duplicate_copy"]  # rejected shelf rows
    print(f"bronze_rows={bronze} silver_rows={counts['ok']} rejected_rows={rejected} "  # accounting line
          f"duplicate_copies_removed={counts['duplicate_copy']}")  # removed copies
    print("verdicts=" + ", ".join(f"{k}:{counts[k]}" for k in sorted(counts)))  # every verdict
    print(f"silver_fraud={sum(r['fraud_label'] for r in ok_records())}")  # fraud rows in Silver
    receiver = args.receiver  # explicit choice first
    if receiver is None and args.suggest_from is not None:  # otherwise suggest
        receiver = suggest_receiver(ok_records(), args.suggest_from, args.suggest_to or args.suggest_from)  # busiest
        print(f"suggested_receiver={receiver}")  # show the pick
    if receiver:  # spot-check requested
        for row in features_for_receiver(ok_records, receiver):  # one line per payment
            print(row)  # feature row


if __name__ == "__main__":  # run as a script
    main()  # entry point
