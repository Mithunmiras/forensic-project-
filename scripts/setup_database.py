"""Create the RetailIQ database objects (non-destructive, idempotent).

    python scripts/setup_database.py                      # apply schema
    python scripts/setup_database.py --create-database    # also create retailiq_db if missing
    python scripts/setup_database.py --create-readonly-role

The read-only role password is read from READONLY_DB_PASSWORD (never passed on
the command line, never printed). Nothing is ever dropped.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.engine import make_url  # noqa: E402

from src.config import get_settings, redact_url  # noqa: E402
from src.db.admin import apply_schema, create_database_if_missing, create_readonly_role  # noqa: E402
from src.db.session import Database, safe_error  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--create-database", action="store_true", help="create the database if it does not exist")
    parser.add_argument("--create-readonly-role", action="store_true", help="create/refresh the SELECT-only role")
    parser.add_argument("--readonly-role-name", default="retailiq_readonly")
    parser.add_argument("--reset-readonly-password", action="store_true", help="re-set the password of an existing role")
    args = parser.parse_args()

    settings = get_settings()
    url = settings.effective_database_url
    if not url:
        print("ERROR: DATABASE_URL is not set. Copy .env.example to .env and fill it in.")
        return 2
    print(f"Target: {redact_url(url)}")

    try:
        if args.create_database:
            created = create_database_if_missing(url)
            print(f"Database: {'created' if created else 'already exists'}")
        db = Database(settings)
        applied = apply_schema(db.admin_engine())
        print(f"Schema applied (idempotent): {', '.join(applied)}")

        if args.create_readonly_role:
            password = os.environ.get("READONLY_DB_PASSWORD") or settings.readonly_db_password or ""
            if not password:
                print("ERROR: set READONLY_DB_PASSWORD in the environment/.env to create the read-only role.")
                return 2
            outcome = create_readonly_role(
                db.admin_engine(), args.readonly_role_name, password, reset_password=args.reset_readonly_password
            )
            target = make_url(url)
            print(f"Read-only role '{args.readonly_role_name}': {outcome}")
            print(
                "Add to .env:  DATABASE_READONLY_URL="
                f"postgresql://{args.readonly_role_name}:<your READONLY_DB_PASSWORD>@{target.host}:{target.port}/{target.database}"
            )
        status = db.status()
        print(f"Connected: {status['connected']} | schema ready: {status['schema_ready']} | rows in v_sales: {status['fact_rows']}")
        db.dispose()
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {safe_error(exc)}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
