"""Train and evaluate the sales-prediction models.

    python scripts/train_model.py                 # from the cleaned CSV (reproducible)
    python scripts/train_model.py --source postgres
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.logging_setup import configure_logging  # noqa: E402
from src.ml.train import train  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", choices=["csv", "postgres"], default="csv")
    args = parser.parse_args()
    configure_logging("INFO")
    try:
        train(source=args.source)
    except Exception as exc:  # noqa: BLE001
        print(f"Training failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
