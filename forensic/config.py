"""Paths and constants shared by the generator, the agents and the API."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
STRUCTURED_DIR = DATA_DIR / "structured"
UNSTRUCTURED_DIR = DATA_DIR / "unstructured"
CATALOG_PATH = STRUCTURED_DIR / "catalog.json"   # NoSQL-style document store (product + supplier documents)
DB_PATH = DATA_DIR / "forensic.sqlite"           # SQL store built from the CSVs
UI_DIST = ROOT / "forensic_ui" / "dist"

START_DATE = "2025-10-01"
END_DATE = "2026-06-30"
SEED = 42

# Anomaly thresholds - a month must be both statistically unusual (robust z) and practically
# material (percentage change) before the RCA agent calls it an anomaly.
Z_THRESHOLD = 3.0
UNITS_PCT_THRESHOLD = 5.0
RETURNS_PCT_THRESHOLD = 40.0
DISCOUNT_PP_THRESHOLD = 3.0
PRICE_PCT_THRESHOLD = 3.0
STOCKOUT_DAYS_THRESHOLD = 3

# How far before the start of the month a document may be dated and still count as related.
DOC_LOOKBACK_DAYS = 21
