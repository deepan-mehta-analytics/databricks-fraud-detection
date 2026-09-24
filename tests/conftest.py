"""Shared fixtures: small PaySim-shaped CSVs and a full 743-step outbox."""  # module docstring

# ── Imports ───────────────────────────────────────────────────
import csv                  # write CSV fixtures exactly like the PaySim file
from pathlib import Path    # filesystem paths

import pytest               # fixture decorator

# ── PaySim header, in the real file's column order ────────────
PAYSIM_HEADER = [  # header row of data/paysim.csv
    "step", "type", "amount", "nameOrig", "oldbalanceOrg", "newbalanceOrig",  # first six columns
    "nameDest", "oldbalanceDest", "newbalanceDest", "isFraud", "isFlaggedFraud",  # last five columns
]


# ── CSV builder ───────────────────────────────────────────────
def write_paysim_csv(path: Path, steps: list[int]) -> Path:
    """Write one PaySim-shaped row per entry in `steps` (steps must be sorted)."""  # docstring
    with open(path, "w", newline="", encoding="utf-8") as handle:  # create the CSV file
        writer = csv.writer(handle)  # standard CSV writer
        writer.writerow(PAYSIM_HEADER)  # header first, like the real file
        for index, step in enumerate(steps, start=1):  # index = 1-based data-row number
            amount = "2.369524933E7" if index == 1 else f"{index}.50"  # row 1 uses scientific notation, as ~518k real cells do
            fraud = 1 if index % 10 == 0 else 0  # every 10th row is fraud
            writer.writerow([  # one data row
                step, "TRANSFER", amount, f"C{index}", "1000.0", "0.0",  # step, type, amount, sender, sender balances
                f"M{index}", "0.0", "0.0", fraud, 0,  # receiver, receiver balances, labels
            ])
    return path  # hand the path back to the caller


# ── Fixtures ──────────────────────────────────────────────────
@pytest.fixture  # marks this function as a pytest fixture
def sample_csv(tmp_path: Path) -> Path:
    """50 rows, 5 per step, spanning every segment boundary; 5 of them fraud."""  # docstring
    steps = [s for s in (1, 2, 336, 337, 338, 408, 409, 410, 742, 743) for _ in range(5)]  # sorted, 10 steps x 5 rows
    return write_paysim_csv(tmp_path / "paysim.csv", steps)  # write and return the CSV path


@pytest.fixture  # marks this function as a pytest fixture
def full_outbox(tmp_path: Path) -> Path:
    """An outbox holding every step 1..743, two rows per step, built by split_csv."""  # docstring
    from fraud_ingest.split import split_csv  # imported here so Task 1 tests run before split.py exists
    csv_path = write_paysim_csv(tmp_path / "full.csv", [s for s in range(1, 744) for _ in range(2)])  # 1,486 rows
    outbox = tmp_path / "outbox"  # destination folder
    split_csv(csv_path, outbox)  # write the 743 step files
    return outbox  # hand the outbox path to the test
