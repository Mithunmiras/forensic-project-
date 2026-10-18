"""Validate the source CSV and print a data-quality summary (no database needed).

    python scripts/validate_data.py [--source raw|processed]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.etl.pipeline import EtlError, extract, validate  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["raw", "processed"], default="raw")
    args = parser.parse_args()
    try:
        df, path = extract(args.source)
        report = validate(df).report
    except EtlError as exc:
        print(f"Validation could not run: {exc}")
        return 2
    print(f"Source: {path}")
    print(f"Raw rows: {report['raw_rows']:,} | valid: {report['valid_rows']:,} | rejected: {report['rejected_rows']:,} | exact duplicate rows: {report['duplicate_rows']:,}")
    print(f"Order date range: {report['order_date_range']}")
    if report["rejected_by_reason"]:
        print("Rejected by reason:", report["rejected_by_reason"])
    if report["null_counts"]:
        print("Null counts:", report["null_counts"])
    print(f"Rows where the 'year' column disagrees with order_date: {report['year_column_mismatches']}")
    print("Distinct values:", report["distinct_counts"])
    return 0 if report["rejected_rows"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
