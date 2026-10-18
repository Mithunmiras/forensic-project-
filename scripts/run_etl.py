"""Run the RetailIQ ETL: raw CSV -> validate -> PostgreSQL (idempotent).

    python scripts/run_etl.py                    # load into PostgreSQL
    python scripts/run_etl.py --dry-run          # validate only, no database needed
    python scripts/run_etl.py --update-existing  # also refresh rows whose values changed
    python scripts/run_etl.py --source processed # use data/processed/superstore_cleaned.csv
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import get_settings  # noqa: E402
from src.db.session import Database, safe_error  # noqa: E402
from src.etl.pipeline import EtlError, run_etl  # noqa: E402
from src.logging_setup import configure_logging  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", choices=["raw", "processed"], default="raw")
    parser.add_argument("--path", type=Path, help="override the CSV path")
    parser.add_argument("--update-existing", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="validate and report, do not touch the database")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    db = Database(settings)
    try:
        engine = None if args.dry_run else db.admin_engine()
        summary = run_etl(
            engine, source=args.source, path=args.path,
            update_existing=args.update_existing, dry_run=args.dry_run,
        )
    except EtlError as exc:
        print(f"ETL cannot run: {exc}")
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"ETL FAILED (transaction rolled back): {safe_error(exc)}")
        return 1
    finally:
        db.dispose()

    print(json.dumps(summary.as_dict(), indent=2))
    if summary.rejected_rows:
        print(f"{summary.rejected_rows} rows rejected - see reports/etl_rejected_rows.csv")
    print("Data-quality report: reports/data_quality_report.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
