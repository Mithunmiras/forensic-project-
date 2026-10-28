"""Monthly metrics per product/region and the robust anomaly test the RCA agent and the scan share.

Baseline for a month = median of the same series' OTHER months (leave-one-out), scale = MAD
with a floor, so one incident in a series does not distort the baseline for the others.
A dataset may restrict the baseline to the surrounding +/- N months (real data with a growth
trend), and sets its own thresholds; see forensic/datasets.py.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

import numpy as np
import pandas as pd

from forensic.datasets import Dataset
from forensic.store import DataStore

MONTHLY_SQL = """
SELECT s.product_id, s.region, substr(s.date, 1, 7) AS month,
       COUNT(*) AS days,
       SUM(s.units_sold) AS units,
       SUM(s.revenue) AS revenue,
       AVG(s.discount_pct) AS avg_discount,
       SUM(s.returns) AS returns,
       SUM(s.units_sold * (1 - s.discount_pct / 100.0)) AS net_units,
       SUM(CASE WHEN i.stock_level = 0 THEN 1 ELSE 0 END) AS stockout_days,
       p.unit_price
FROM sales s
JOIN products p ON p.product_id = s.product_id
LEFT JOIN inventory i ON i.product_id = s.product_id AND i.date = s.date
                     AND i.warehouse = 'WH_' || upper(s.region) || '_01'
GROUP BY s.product_id, s.region, month
ORDER BY s.product_id, s.region, month
"""

# Datasets without inventory: the supply-side signal is the late-delivery rate.
MONTHLY_SQL_DELIVERY = """
SELECT s.product_id, s.region, substr(s.date, 1, 7) AS month,
       COUNT(*) AS days,
       SUM(s.units_sold) AS units,
       SUM(s.revenue) AS revenue,
       AVG(s.discount_pct) AS avg_discount,
       SUM(s.returns) AS returns,
       SUM(s.units_sold * (1 - s.discount_pct / 100.0)) AS net_units,
       0 AS stockout_days,
       SUM(s.late_items) AS late_items,
       SUM(s.delivered_items) AS delivered_items,
       p.unit_price
FROM sales s
JOIN products p ON p.product_id = s.product_id
GROUP BY s.product_id, s.region, month
ORDER BY s.product_id, s.region, month
"""


def monthly_sql(ds: Dataset) -> str:
    return MONTHLY_SQL if ds.has_inventory else MONTHLY_SQL_DELIVERY


def _loo_baseline(values: np.ndarray, floor: tuple, window: Optional[int]):
    """Leave-one-out median and robust scale (1.4826 x MAD, with a floor) for every position."""
    base, scale = np.zeros(len(values)), np.zeros(len(values))
    min_rel, min_abs = floor
    for i in range(len(values)):
        lo, hi = (0, len(values)) if window is None else (max(0, i - window), i + window + 1)
        others = np.delete(values[lo:hi], i - lo)
        if len(others) == 0:
            others = np.delete(values, i)
        med = float(np.median(others))
        mad = float(np.median(np.abs(others - med))) * 1.4826
        base[i] = med
        scale[i] = max(mad, min_rel * abs(med), min_abs, 1e-9)
    return base, scale


def enrich(monthly: pd.DataFrame, ds: Dataset) -> pd.DataFrame:
    df = monthly.copy()
    df["units_per_day"] = df["units"] / df["days"]
    df["revenue_per_day"] = df["revenue"] / df["days"]
    df["returns_rate"] = df["returns"] / df["units"].clip(lower=1) * 100
    df["price_index"] = df["revenue"] / df["net_units"].clip(lower=1) / df["unit_price"]
    floors = dict(ds.floors)
    if not ds.has_inventory:
        df["late_rate"] = df["late_items"] / df["delivered_items"].clip(lower=1) * 100
    floors.setdefault("avg_discount", (0.0, 0.3))
    floors.setdefault("price_index", (0.005, 0.0))
    out = []
    for _, g in df.groupby(["product_id", "region"], sort=False):
        g = g.sort_values("month").copy()
        for metric, floor in floors.items():
            base, scale = _loo_baseline(g[metric].to_numpy(float), floor, ds.baseline_window)
            g[f"{metric}_base"] = base
            g[f"{metric}_z"] = (g[metric] - base) / scale
            g[f"{metric}_pct"] = (g[metric] - base) / np.where(base == 0, 1, base) * 100
        rev_base, _ = _loo_baseline(g["revenue_per_day"].to_numpy(float), floors["units_per_day"], ds.baseline_window)
        g["revenue_per_day_base"] = rev_base
        g["revenue_per_day_pct"] = (g["revenue_per_day"] - rev_base) / np.where(rev_base == 0, 1, rev_base) * 100
        g["units_prev_pct"] = g["units_per_day"].pct_change() * 100
        out.append(g)
    df = pd.concat(out, ignore_index=True)
    sig = df.apply(lambda r: signals_for(r, ds), axis=1)
    df["signals"] = sig
    df["is_anomaly"] = sig.apply(bool)
    df["anomaly_score"] = df.apply(lambda r: _score(r, ds), axis=1)
    return df


def _enough(r, ds: Dataset) -> tuple:
    """(units volume ok, delivery volume ok) - tiny cells cannot support a rate."""
    t = ds.thresholds
    units_ok = r["units"] >= t.get("min_units", 0)
    delivered_ok = ds.has_inventory or r["delivered_items"] >= t.get("min_delivered", 0)
    return units_ok, delivered_ok


def signals_for(r, ds: Dataset) -> list:
    """Structured signature of a month: which anomaly families fire."""
    t = ds.thresholds
    units_ok, delivered_ok = _enough(r, ds)
    fam = []
    if ds.has_inventory:
        if r["stockout_days"] >= t["stockout_days"]:
            fam.append("supply")
    elif (delivered_ok and r["late_rate_pct"] >= t["late_pct"] and r["late_rate_z"] >= t["z"]
          and r["late_rate"] >= t["late_min"]):
        fam.append("supply")
    if units_ok and r["returns_rate_pct"] >= t["returns_pct"] and r["returns_rate_z"] >= t["z"]:
        fam.append("returns")
    if ds.has_discount and r["avg_discount"] - r["avg_discount_base"] >= t["discount_pp"]:
        fam.append("discount")
    if ds.has_price and r["price_index_pct"] >= t["price_pct"]:
        fam.append("price")
    if units_ok and abs(r["units_per_day_pct"]) >= t["units_pct"] and abs(r["units_per_day_z"]) >= t["z"]:
        fam.append("demand_down" if r["units_per_day_pct"] < 0 else "demand_up")
    return fam


def _score(r, ds: Dataset) -> float:
    """Single number for ranking months - the strongest robust z among the metrics."""
    units_ok, delivered_ok = _enough(r, ds)
    zs = [abs(r["units_per_day_z"]) if units_ok else 0.0, r["returns_rate_z"] if units_ok else 0.0]
    if ds.has_discount:
        zs.append(abs(r["avg_discount_z"]))
    if ds.has_price:
        zs.append(abs(r["price_index_z"]))
    if not ds.has_inventory:
        zs.append(r["late_rate_z"] if delivered_ok else 0.0)
    score = max(zs)
    if ds.has_inventory and r["stockout_days"] >= ds.thresholds["stockout_days"]:
        score = max(score, 3 + r["stockout_days"] / 2)
    return round(float(score), 2)


@lru_cache(maxsize=4)
def monthly_metrics(store: DataStore) -> pd.DataFrame:
    return enrich(store.query(monthly_sql(store.dataset)), store.dataset)
