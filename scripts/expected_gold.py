"""Print the expected Gold numbers from the PaySim CSV (spec §12). Usage: python scripts/expected_gold.py --csv data/paysim.csv"""  # module docstring

# ── Imports ───────────────────────────────────────────────────
import argparse  # command-line flags
import dataclasses  # copy the scenario with a different last step
import sys       # path setup
from pathlib import Path  # locate src/

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # import the packages without installing them

from fraud_gold.expected import (  # noqa: E402  Gold calculator
    GOLD_SCENARIO, alerts_per_step, closed_cases, closing_cutoff, silver_payments_per_step,  # rules
)  # end import
from fraud_silver.expected import iter_bronze_records, judge  # noqa: E402  Silver simulation


def main() -> None:  # read the CSV once and print the counts
    parser = argparse.ArgumentParser(description=__doc__)  # flags
    parser.add_argument("--csv", required=True, type=Path)  # data/paysim.csv
    parser.add_argument("--last-step", type=int, default=GOLD_SCENARIO.last_step)  # newest released hour
    args = parser.parse_args()  # read flags
    scenario = dataclasses.replace(GOLD_SCENARIO, last_step=args.last_step)  # same scenario, up to --last-step
    payments = silver_payments_per_step(judge(iter_bronze_records(args.csv, scenario)))  # Silver rows per scored hour
    alerts = alerts_per_step(payments)  # min(50, n) per hour
    newest = max(payments)  # newest scored hour
    cutoff = closing_cutoff(newest)  # 72 hours back
    closed = closed_cases(alerts, cutoff)  # cases closed now
    print(f"scored_payments={sum(payments.values())} hours={len(payments)} newest_scored_step={newest}")  # scoring totals
    print(f"alerts={sum(alerts.values())} short_hours={sum(1 for n in payments.values() if n < 50)}")  # alert totals
    print(f"closing_cutoff_step={cutoff} closed_cases={closed} open_cases={sum(alerts.values()) - closed}")  # case totals


if __name__ == "__main__":  # run as a script
    main()  # entry point
