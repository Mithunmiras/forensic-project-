"""Feature definitions shared by training and serving.

The API accepts a raw order description (including an ``order_date``); calendar
features are derived here so training and serving can never drift apart.

Target leakage note
-------------------
* ``profit`` is excluded (it is computed from sales).
* ``shipping_cost`` is *kept in one variant only*: in this dataset shipping charges
  scale with order value (Spearman ~0.91 with sales), so it acts as a proxy for the
  target. The "without_shipping_cost" variant is the leakage-safe model.
* Identifiers (row_id, order_id, customer_id, product_id) are never features.
"""
from __future__ import annotations

import pandas as pd

CATEGORICAL = ["category", "sub_category", "market", "segment", "ship_mode", "order_priority"]
NUMERIC = [
    "quantity",
    "discount",
    "shipping_cost",
    "shipping_days",
    "year",
    "weeknum",
    "month",
    "quarter",
    "day_of_week",
]
FEATURES = CATEGORICAL + NUMERIC
TARGET = "sales"

VARIANT_FULL = "with_shipping_cost"
VARIANT_SAFE = "without_shipping_cost"
VARIANT_FEATURES = {
    VARIANT_FULL: FEATURES,
    VARIANT_SAFE: [f for f in FEATURES if f != "shipping_cost"],
}
VARIANT_LABELS = {
    VARIANT_FULL: "With shipping cost (highest accuracy, uses a proxy of the target)",
    VARIANT_SAFE: "Without shipping cost (leakage-safe)",
}

# Columns a caller must/may provide. Calendar features are derived from order_date.
INPUT_FIELDS = [
    {"name": "category", "kind": "categorical", "required": True, "label": "Category"},
    {"name": "sub_category", "kind": "categorical", "required": True, "label": "Sub-category"},
    {"name": "market", "kind": "categorical", "required": True, "label": "Market"},
    {"name": "segment", "kind": "categorical", "required": False, "label": "Customer segment", "default": "Consumer"},
    {"name": "ship_mode", "kind": "categorical", "required": False, "label": "Ship mode", "default": "Standard Class"},
    {"name": "order_priority", "kind": "categorical", "required": False, "label": "Order priority", "default": "Medium"},
    {"name": "quantity", "kind": "integer", "required": True, "label": "Quantity"},
    {"name": "discount", "kind": "number", "required": True, "label": "Discount (0-1)"},
    {"name": "shipping_days", "kind": "integer", "required": False, "label": "Shipping days"},
    {"name": "shipping_cost", "kind": "number", "required": False, "label": "Shipping cost"},
    {"name": "order_date", "kind": "date", "required": False, "label": "Order date"},
]


def tableau_week(dates: pd.Series) -> pd.Series:
    """Week number as used in the Superstore export.

    Weeks start on Sunday and week 1 is the week containing 1 January
    (Tableau's default).
    """
    jan1 = pd.to_datetime(dates.dt.year.astype(str) + "-01-01")
    jan1_offset = (jan1.dt.dayofweek + 1) % 7  # days since Sunday (Sun=0)
    return (dates.dt.dayofyear - 1 + jan1_offset) // 7 + 1


def add_date_features(df: pd.DataFrame) -> pd.DataFrame:
    """Derive year/week/month/quarter/day-of-week from ``order_date``."""
    out = df.copy()
    dates = pd.to_datetime(out["order_date"])
    out["year"] = dates.dt.year
    out["weeknum"] = tableau_week(dates)
    out["month"] = dates.dt.month
    out["quarter"] = dates.dt.quarter
    out["day_of_week"] = dates.dt.dayofweek
    return out


def build_frame(df: pd.DataFrame, features: list[str] | None = None) -> pd.DataFrame:
    """Return the model input frame from raw orders (default: all ``FEATURES``)."""
    return add_date_features(df)[features or FEATURES]
