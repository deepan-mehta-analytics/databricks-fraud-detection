"""Write dashboards/*.lvdash.json from src/fraud_monitoring/dashboards.py (ruling R7). Usage: python scripts/build_dashboards.py"""  # module docstring

# ── Imports ───────────────────────────────────────────────────
import sys                # path setup
from pathlib import Path  # output folder

ROOT = Path(__file__).resolve().parents[1]  # repo root
sys.path.insert(0, str(ROOT / "src"))  # import the package without installing it

from fraud_monitoring.dashboards import DASHBOARDS, render  # noqa: E402  the dashboard definitions


def main() -> None:  # write both files
    (ROOT / "dashboards").mkdir(exist_ok=True)  # the output folder
    for key, build in DASHBOARDS.items():  # resource key -> builder
        path = ROOT / "dashboards" / f"{key}.lvdash.json"  # output file
        with open(path, "w", encoding="utf-8", newline="\n") as handle:  # LF endings on every OS
            handle.write(render(build()))  # the JSON text
        print("wrote", path.relative_to(ROOT))  # report


if __name__ == "__main__":  # run as a script
    main()  # entry point
