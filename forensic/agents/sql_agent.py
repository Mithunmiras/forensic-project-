"""SQL / NoSQL analytics agent - deterministic, no LLM.

SQL (SQLite tables sales / inventory / products / suppliers) answers the numeric questions;
the catalog document store (catalog.json: one nested document per product, with its primary
and backup suppliers) supplies the semi-structured master data. Every query that ran is
returned so the answer can be audited.
"""
from __future__ import annotations

import numpy as np

from forensic.catalog import WAREHOUSE
from forensic.metrics import MONTHLY_SQL, monthly_metrics
from forensic.store import DataStore

DAILY_SQL = """
SELECT s.date, s.units_sold AS units, s.returns, s.discount_pct AS discount, s.revenue,
       i.stock_level AS stock, i.reorder_point
FROM sales s
LEFT JOIN inventory i ON i.product_id = s.product_id AND i.date = s.date AND i.warehouse = ?
WHERE s.product_id = ? AND s.region = ?
ORDER BY s.date
"""

STOCKOUT_SQL = """
SELECT date, stock_level, reorder_point FROM inventory
WHERE product_id = ? AND warehouse = ? AND substr(date, 1, 7) = ? AND stock_level = 0
ORDER BY date
"""

_TARGET_FIELDS = [
    "days", "units", "revenue", "returns", "units_per_day", "units_per_day_base", "units_per_day_pct",
    "units_per_day_z", "units_prev_pct", "revenue_per_day", "revenue_per_day_base", "revenue_per_day_pct",
    "returns_rate", "returns_rate_base", "returns_rate_pct", "returns_rate_z", "avg_discount",
    "avg_discount_base", "price_index", "price_index_base", "price_index_pct", "stockout_days",
    "anomaly_score", "is_anomaly", "signals",
]


def _clean(row) -> dict:
    out = {}
    for k in _TARGET_FIELDS:
        v = row[k]
        if isinstance(v, list):
            out[k] = v
        elif isinstance(v, (bool, np.bool_)):
            out[k] = bool(v)
        else:
            out[k] = None if v != v else round(float(v), 4)  # NaN -> None
    return out


class SQLAnalyticsAgent:
    name = "SQL / NoSQL Analytics Agent"

    def __init__(self, store: DataStore) -> None:
        self.store = store

    def run(self, product_id, region, month) -> dict:
        queries = [{"purpose": "monthly metrics per product/region (baseline source)", "sql": MONTHLY_SQL.strip()}]
        catalog_doc = self.store.catalog.get(product_id) if product_id else None
        out = {"agent": self.name, "available": False, "reason": "", "queries": queries,
               "product": None, "suppliers": {"primary": [], "backup": []}}
        if catalog_doc:
            out["product"] = {k: catalog_doc[k] for k in ("product_name", "category", "launch_date", "unit_price")}
            out["product"]["product_id"] = product_id
            out["suppliers"] = catalog_doc["suppliers"]
            queries.append({"purpose": "catalog document store lookup",
                            "sql": f'catalog.find_one({{"_id": "{product_id}"}})'})
        if not product_id:
            out["reason"] = "No product identified."
            return out
        if not self.store.has_sales(product_id):
            out["reason"] = f"No sales or inventory records exist for {product_id}."
            return out
        if not region or not month:
            out["reason"] = "Region or month could not be determined."
            return out

        df = monthly_metrics(self.store)
        series = df[(df["product_id"] == product_id) & (df["region"] == region)].sort_values("month")
        target = series[series["month"] == month]
        if target.empty:
            out["reason"] = f"No sales records for {product_id} in {region} during {month}."
            return out

        t = target.iloc[0]
        prev = series[series["month"] < month].tail(1)
        warehouse = WAREHOUSE[region]

        daily = self.store.query(DAILY_SQL, (warehouse, product_id, region))
        queries.append({"purpose": "daily sales joined to warehouse stock", "sql": DAILY_SQL.strip(),
                        "params": [warehouse, product_id, region]})
        stockouts = self.store.query(STOCKOUT_SQL, (product_id, warehouse, month))
        queries.append({"purpose": "stock-out days in the month", "sql": STOCKOUT_SQL.strip(),
                        "params": [product_id, warehouse, month]})

        same_month = df[df["month"] == month]
        other_regions = same_month[(same_month["product_id"] == product_id) & (same_month["region"] != region)]
        other_products = same_month[(same_month["region"] == region) & (same_month["product_id"] != product_id)]

        out.update({
            "available": True,
            "month": month,
            "previous_month": prev.iloc[0]["month"] if not prev.empty else None,
            "target": _clean(t),
            "monthly": [{"month": r["month"], "units_per_day": round(r["units_per_day"], 1),
                         "baseline": round(r["units_per_day_base"], 1), "returns_rate": round(r["returns_rate"], 3),
                         "avg_discount": round(r["avg_discount"], 2), "stockout_days": int(r["stockout_days"]),
                         "is_anomaly": bool(r["is_anomaly"])} for _, r in series.iterrows()],
            "other_regions": [{"region": r["region"], "units_per_day_pct": round(r["units_per_day_pct"], 2),
                               "is_anomaly": bool(r["is_anomaly"])} for _, r in other_regions.iterrows()],
            "other_products": [{"product_id": r["product_id"], "units_per_day_pct": round(r["units_per_day_pct"], 2),
                                "stockout_days": int(r["stockout_days"])} for _, r in other_products.iterrows()],
            "stockout": {
                "warehouse": warehouse, "days": len(stockouts),
                "first": stockouts["date"].iloc[0] if len(stockouts) else None,
                "last": stockouts["date"].iloc[-1] if len(stockouts) else None,
                "reorder_point": int(daily["reorder_point"].dropna().iloc[0]) if daily["reorder_point"].notna().any() else None,
            },
            "daily": daily[["date", "units", "returns", "discount", "stock", "reorder_point"]]
                .fillna(0).to_dict(orient="records"),
        })
        return out
