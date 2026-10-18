"""Data access shared by EDA, training and the API.

The cleaned CSV is the source of truth, so everything works without a
database. Pass ``source="postgres"`` to read the ``superstore`` table instead.
"""
from __future__ import annotations

import pandas as pd

from src.config import CLEAN_CSV, database_url


def load_sales(source: str = "csv") -> pd.DataFrame:
    """Load the cleaned Global Superstore dataset with parsed dates."""
    if source == "postgres":
        from sqlalchemy import create_engine

        df = pd.read_sql("SELECT * FROM superstore", create_engine(database_url()))
    elif source == "csv":
        if not CLEAN_CSV.exists():
            raise FileNotFoundError(
                f"{CLEAN_CSV} not found. Run `python main.py etl` to generate it."
            )
        df = pd.read_csv(CLEAN_CSV)
    else:
        raise ValueError(f"Unknown source: {source!r}")

    df["order_date"] = pd.to_datetime(df["order_date"])
    df["ship_date"] = pd.to_datetime(df["ship_date"])
    return df
