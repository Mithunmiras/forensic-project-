"""Clean the raw Global Superstore export.

    python -m src.etl.clean_data      # or: python main.py etl --clean-only

``clean_frame`` is a pure DataFrame -> DataFrame function so it can be unit
tested; ``clean`` adds the file I/O.
"""
from __future__ import annotations

import pandas as pd

from src.config import CLEAN_CSV, RAW_CSV

REQUIRED = {"sales", "profit", "quantity", "discount", "order_date", "ship_date", "order_id"}


def clean_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """Normalise column names, drop non-ASCII helper columns, parse dates,
    and derive ``shipping_days`` from the order/ship dates."""
    df = raw.copy()

    # The export carries a Chinese-language row-count column ("记录数"); it is always 1.
    df = df.drop(columns=[c for c in df.columns if not str(c).isascii()])

    df.columns = df.columns.str.strip().str.lower().str.replace(".", "_", regex=False).str.replace(" ", "_")

    missing = REQUIRED - set(df.columns)
    if missing:
        raise ValueError(f"Raw file is missing expected columns: {sorted(missing)}")

    # Unparseable dates become NaT here and are rejected (not silently kept) by validation.
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    df["ship_date"] = pd.to_datetime(df["ship_date"], errors="coerce")
    df["shipping_days"] = (df["ship_date"] - df["order_date"]).dt.days
    return df


def clean(raw_path=RAW_CSV, out_path=CLEAN_CSV) -> pd.DataFrame:
    df = clean_frame(pd.read_csv(raw_path))

    if (df["shipping_days"] < 0).any():
        raise ValueError("Found orders shipped before they were placed")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return df


if __name__ == "__main__":
    result = clean()
    print("Cleaning completed successfully!")
    print(result.head())
    print("\nShape:", result.shape)
    print("\nColumns:")
    print(result.columns.tolist())
