"""Load the cleaned dataset into PostgreSQL (optional).

    python -m src.etl.load_to_postgres      # or: python main.py load-db

Connection settings come from DB_* environment variables or a local .env
file (see .env.example). The ``superstore`` table is replaced on each run, so
the script is safe to re-run.
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy import create_engine, text

from src.config import CLEAN_CSV, database_url


def load(csv_path=CLEAN_CSV, table: str = "superstore") -> int:
    engine = create_engine(database_url())
    df = pd.read_csv(csv_path)
    with engine.begin() as conn:
        df.to_sql(table, conn, if_exists="replace", index=False, method="multi", chunksize=5000)
        conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{table}_order_date ON {table} (order_date)"))
    return len(df)


if __name__ == "__main__":
    print(f"Successfully loaded {load()} rows into PostgreSQL!")
