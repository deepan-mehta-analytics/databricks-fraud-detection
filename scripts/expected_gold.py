"""Print the expected Gold and monitoring numbers from the PaySim CSV (spec §12; Phase 6a spec §5.5).
Usage: python scripts/expected_gold.py --csv data/paysim.csv [--last-step 480] [--monitoring] [--since 421]"""  # module docstring

# ── Imports ───────────────────────────────────────────────────
import argparse  # command-line flags
import dataclasses  # copy the scenario with a different last step
import sys       # path setup
from pathlib import Path  # locate src/

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # import the packages without installing them

from fraud_gold.expected import (  # noqa: E402  Gold calculator
    GOLD_SCENARIO, alerts_per_step, closed_cases, closing_cutoff, fraud_with_verdicts, hours_with_verdicts,  # rules
    silver_counts,  # one-pass tallies
)  # end import
from fraud_silver.expected import iter_bronze_records, judge  # noqa: E402  Silver simulation


def main() -> None:  # read the CSV once and print the counts
    parser = argparse.ArgumentParser(description=__doc__)  # flags
    parser.add_argument("--csv", required=True, type=Path)  # data/paysim.csv
    parser.add_argument("--last-step", type=int, default=GOLD_SCENARIO.last_step)  # newest released hour
    parser.add_argument("--monitoring", action="store_true")  # also print the monitoring view numbers
    parser.add_argument("--since", type=int, default=None)  # also print payments and fraud after this hour
    args = parser.parse_args()  # read flags
    scenario = dataclasses.replace(GOLD_SCENARIO, last_step=args.last_step)  # same scenario, up to --last-step
    counts = silver_counts(judge(iter_bronze_records(args.csv, scenario)))  # one pass: payments, fraud, rejections
    payments = counts.payments  # Silver rows per scored hour
    alerts = alerts_per_step(payments)  # min(50, n) per hour
    newest = max(payments)  # newest scored hour
    cutoff = closing_cutoff(newest)  # 72 hours back
    closed = closed_cases(alerts, cutoff)  # cases closed now
    print(f"scored_payments={sum(payments.values())} hours={len(payments)} newest_scored_step={newest}")  # scoring totals
    print(f"alerts={sum(alerts.values())} short_hours={sum(1 for n in payments.values() if n < 50)}")  # alert totals
    print(f"closing_cutoff_step={cutoff} closed_cases={closed} open_cases={sum(alerts.values()) - closed}")  # case totals
    if args.monitoring:  # the monitoring view numbers
        print(f"fraud_with_verdicts={fraud_with_verdicts(counts.fraud, cutoff)} "  # model view: all fraud in ready hours
              f"hours_with_verdicts={hours_with_verdicts(payments, cutoff)}")  # and how many hours are ready
        print(f"newest_hour_at_every_stage={newest}")  # data_freshness: no held hours in this scenario
        print(f"rejected_rows={dict(sorted(counts.rejected.items()))}")  # rejected_rows_by_reason
    if args.since is not None:  # payments a run added after an hour
        after = [step for step in payments if step > args.since]  # the new hours
        print(f"payments_after_step_{args.since}={sum(payments[s] for s in after)} "  # new payments
              f"fraud_after_step_{args.since}={sum(counts.fraud[s] for s in after)}")  # new fraud


if __name__ == "__main__":  # run as a script
    main()  # entry point
