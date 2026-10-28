"""Monthly metrics per product/region and the robust anomaly test the RCA agent and the scan share.

Baseline for a month = median of the same series' OTHER months (leave-one-out), scale = MAD
with a floor, so one incident in a series does not distort the baseline for the others.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from forensic import config as C
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

# metric -> (minimum robust scale, as a fraction of the baseline if relative else absolute, relative?)
_SCALE_FLOOR = {"units_per_day": (0.015, True), "returns_rate": (0.08, True),
                "avg_discount": (0.3, False), "price_index": (0.005, True)}


def _loo_baseline(values: np.ndarray, metric: str):
    base, scale = np.zeros(len(values)), np.zeros(len(values))
    floor, relative = _SCALE_FLOOR[metric]
    for i in range(len(values)):
        others = np.delete(values, i)
        med = float(np.median(others))
        mad = float(np.median(np.abs(others - med))) * 1.4826
        base[i] = med
        scale[i] = max(mad, floor * abs(med) if relative else floor)
    return base, scale


def enrich(monthly: pd.DataFrame) -> pd.DataFrame:
    df = monthly.copy()
    df["units_per_day"] = df["units"] / df["days"]
    df["revenue_per_day"] = df["revenue"] / df["days"]
    df["returns_rate"] = df["returns"] / df["units"].clip(lower=1) * 100
    df["price_index"] = df["revenue"] / df["net_units"].clip(lower=1) / df["unit_price"]
    out = []
    for _, g in df.groupby(["product_id", "region"], sort=False):
        g = g.sort_values("month").copy()
        for metric in _SCALE_FLOOR:
            base, scale = _loo_baseline(g[metric].to_numpy(float), metric)
            g[f"{metric}_base"] = base
            g[f"{metric}_z"] = (g[metric] - base) / scale
            g[f"{metric}_pct"] = (g[metric] - base) / np.where(base == 0, 1, base) * 100
        rev_base, _ = _loo_baseline(g["revenue_per_day"].to_numpy(float), "units_per_day")
        g["revenue_per_day_base"] = rev_base
        g["revenue_per_day_pct"] = (g["revenue_per_day"] - rev_base) / rev_base * 100
        g["units_prev_pct"] = g["units_per_day"].pct_change() * 100
        out.append(g)
    df = pd.concat(out, ignore_index=True)
    sig = df.apply(signals_for, axis=1)
    df["signals"] = sig
    df["is_anomaly"] = sig.apply(bool)
    df["anomaly_score"] = df.apply(_score, axis=1)
    return df


def signals_for(r) -> list:
    """Structured signature of a month: which anomaly families fire."""
    fam = []
    if r["stockout_days"] >= C.STOCKOUT_DAYS_THRESHOLD:
        fam.append("supply")
    if r["returns_rate_pct"] >= C.RETURNS_PCT_THRESHOLD and r["returns_rate_z"] >= C.Z_THRESHOLD:
        fam.append("returns")
    if r["avg_discount"] - r["avg_discount_base"] >= C.DISCOUNT_PP_THRESHOLD:
        fam.append("discount")
    if r["price_index_pct"] >= C.PRICE_PCT_THRESHOLD:
        fam.append("price")
    if abs(r["units_per_day_pct"]) >= C.UNITS_PCT_THRESHOLD and abs(r["units_per_day_z"]) >= C.Z_THRESHOLD:
        fam.append("demand_down" if r["units_per_day_pct"] < 0 else "demand_up")
    return fam


def _score(r) -> float:
    """Single number for ranking months - the strongest robust z among the metrics."""
    zs = [abs(r["units_per_day_z"]), r["returns_rate_z"], abs(r["avg_discount_z"]), abs(r["price_index_z"])]
    score = max(zs)
    if r["stockout_days"] >= C.STOCKOUT_DAYS_THRESHOLD:
        score = max(score, 3 + r["stockout_days"] / 2)
    return round(float(score), 2)


@lru_cache(maxsize=4)
def monthly_metrics(store: DataStore) -> pd.DataFrame:
    return enrich(store.query(MONTHLY_SQL))
