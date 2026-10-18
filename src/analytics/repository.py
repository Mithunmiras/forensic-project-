"""Dashboard analytics computed with SQL aggregations in PostgreSQL.

Every figure shown in the UI comes from here; nothing is cached in pandas or
hardcoded. All filter values are bind parameters; identifiers come from fixed
whitelists, never from user input.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy import exc as sa_exc

from src.analytics.executor import to_jsonable
from src.db.session import Database, DatabaseUnavailable, safe_error

V = "retailiq.v_sales"

DIMENSIONS = {
    "category": "category",
    "sub_category": "sub_category",
    "region": "region",
    "market": "market",
    "segment": "segment",
    "country": "country",
    "ship_mode": "ship_mode",
    "order_priority": "order_priority",
}
GRAINS = {
    "month": "year_month",
    "quarter": "(year::text || '-Q' || quarter::text)",
    "year": "year::text",
}


@dataclass(frozen=True)
class Filters:
    date_from: date | None = None
    date_to: date | None = None
    category: str | None = None
    region: str | None = None
    market: str | None = None

    def where(self) -> tuple[str, dict[str, Any]]:
        clauses, params = [], {}
        if self.date_from:
            clauses.append("order_date >= :date_from")
            params["date_from"] = self.date_from
        if self.date_to:
            clauses.append("order_date <= :date_to")
            params["date_to"] = self.date_to
        for col in ("category", "region", "market"):
            value = getattr(self, col)
            if value:
                clauses.append(f"{col} = :{col}")
                params[col] = value
        return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


def _f(v: Any) -> Any:
    return to_jsonable(v)


class AnalyticsRepository:
    def __init__(self, db: Database) -> None:
        self.db = db
        self._options: tuple[float, dict[str, Any]] | None = None
        self._lock = threading.Lock()

    # ---- plumbing ------------------------------------------------------
    def _query(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        try:
            with self.db.readonly_engine().connect() as conn:
                rows = conn.execute(text(sql), params or {}).mappings().all()
                conn.rollback()
        except sa_exc.DBAPIError as exc:
            raise DatabaseUnavailable(safe_error(exc)) from exc
        return [{k: _f(v) for k, v in r.items()} for r in rows]

    # ---- queries -------------------------------------------------------
    def filter_options(self, *, max_age_s: float = 300.0) -> dict[str, Any]:
        with self._lock:
            if self._options and time.monotonic() - self._options[0] < max_age_s:
                return self._options[1]
        opts = {
            "categories": [r["v"] for r in self._query(f"SELECT DISTINCT category AS v FROM {V} ORDER BY 1")],
            "sub_categories": [r["v"] for r in self._query(f"SELECT DISTINCT sub_category AS v FROM {V} ORDER BY 1")],
            "regions": [r["v"] for r in self._query(f"SELECT DISTINCT region AS v FROM {V} ORDER BY 1")],
            "markets": [r["v"] for r in self._query(f"SELECT DISTINCT market AS v FROM {V} ORDER BY 1")],
            "segments": [r["v"] for r in self._query(f"SELECT DISTINCT segment AS v FROM {V} ORDER BY 1")],
            "ship_modes": [r["v"] for r in self._query(f"SELECT DISTINCT ship_mode AS v FROM {V} ORDER BY 1")],
            "countries": [r["v"] for r in self._query(f"SELECT DISTINCT country AS v FROM {V} ORDER BY 1")],
        }
        bounds = self._query(f"SELECT MIN(order_date) AS first, MAX(order_date) AS last FROM {V}")[0]
        opts["date_range"] = [bounds["first"], bounds["last"]]
        with self._lock:
            self._options = (time.monotonic(), opts)
        return opts

    def _summary_row(self, f: Filters) -> dict[str, Any]:
        where, params = f.where()
        row = self._query(
            f"""SELECT COALESCE(SUM(sales), 0) AS sales, COALESCE(SUM(profit), 0) AS profit,
                       COUNT(DISTINCT order_id) AS orders, COUNT(*) AS order_lines,
                       COALESCE(SUM(quantity), 0) AS units, COUNT(DISTINCT customer_id) AS customers,
                       COALESCE(AVG(discount), 0) AS avg_discount,
                       MIN(order_date) AS first_date, MAX(order_date) AS last_date
                FROM {V}{where}""",
            params,
        )[0]
        sales, profit, orders = row["sales"], row["profit"], row["orders"]
        return {
            "total_sales": round(sales, 2),
            "total_profit": round(profit, 2),
            "orders": orders,
            "order_lines": row["order_lines"],
            "units": row["units"],
            "customers": row["customers"],
            "avg_discount": round(row["avg_discount"], 4),
            "avg_order_value": round(sales / orders, 2) if orders else 0.0,
            "profit_margin": round(profit / sales, 4) if sales else 0.0,
            "first_date": row["first_date"],
            "last_date": row["last_date"],
        }

    def summary(self, f: Filters, *, compare: bool = False) -> dict[str, Any]:
        current = self._summary_row(f)
        out: dict[str, Any] = {"filters": _filters_dict(f), "kpis": current, "previous": None, "change_pct": None}
        if compare and f.date_from and f.date_to and f.date_to >= f.date_from:
            days = (f.date_to - f.date_from).days + 1
            prev_to = f.date_from - timedelta(days=1)
            prev_from = prev_to - timedelta(days=days - 1)
            prev = self._summary_row(Filters(prev_from, prev_to, f.category, f.region, f.market))
            out["previous"] = {"period": [prev_from.isoformat(), prev_to.isoformat()], "kpis": prev}
            out["change_pct"] = {
                k: (round((current[k] - prev[k]) / abs(prev[k]) * 100, 1) if prev[k] else None)
                for k in ("total_sales", "total_profit", "orders", "avg_order_value")
            }
        return out

    def trend(self, f: Filters, grain: str = "month") -> list[dict[str, Any]]:
        if grain not in GRAINS:
            raise ValueError(f"grain must be one of {sorted(GRAINS)}")
        where, params = f.where()
        expr = GRAINS[grain]
        return self._query(
            f"""SELECT {expr} AS period, ROUND(SUM(sales), 2) AS sales, ROUND(SUM(profit), 2) AS profit,
                       COUNT(DISTINCT order_id) AS orders
                FROM {V}{where} GROUP BY 1 ORDER BY 1""",
            params,
        )

    def by_dimension(self, dimension: str, f: Filters, *, limit: int | None = None, order_by: str = "sales") -> list[dict[str, Any]]:
        if dimension not in DIMENSIONS:
            raise ValueError(f"dimension must be one of {sorted(DIMENSIONS)}")
        if order_by not in ("sales", "profit", "orders"):
            raise ValueError("order_by must be sales, profit or orders")
        where, params = f.where()
        lim = f" LIMIT {int(limit)}" if limit else ""
        return self._query(
            f"""SELECT {DIMENSIONS[dimension]} AS name, ROUND(SUM(sales), 2) AS sales, ROUND(SUM(profit), 2) AS profit,
                       COUNT(DISTINCT order_id) AS orders, SUM(quantity) AS units,
                       ROUND(AVG(discount) * 100, 2) AS avg_discount_pct,
                       ROUND(100 * SUM(profit) / NULLIF(SUM(sales), 0), 2) AS margin_pct
                FROM {V}{where} GROUP BY 1 ORDER BY {order_by} DESC, name{lim}""",
            params,
        )

    def top_products(self, f: Filters, n: int = 10, by: str = "sales") -> list[dict[str, Any]]:
        if by not in ("sales", "profit"):
            raise ValueError("by must be 'sales' or 'profit'")
        where, params = f.where()
        return self._query(
            f"""SELECT product_name AS name, category, sub_category, ROUND(SUM(sales), 2) AS sales,
                       ROUND(SUM(profit), 2) AS profit, SUM(quantity) AS units
                FROM {V}{where} GROUP BY product_name, category, sub_category
                ORDER BY {by} DESC, name LIMIT {int(n)}""",
            params,
        )

    def top_customers(self, f: Filters, n: int = 10) -> list[dict[str, Any]]:
        where, params = f.where()
        return self._query(
            f"""SELECT customer_name AS name, segment, ROUND(SUM(sales), 2) AS sales, ROUND(SUM(profit), 2) AS profit,
                       COUNT(DISTINCT order_id) AS orders
                FROM {V}{where} GROUP BY customer_id, customer_name, segment
                ORDER BY sales DESC, name LIMIT {int(n)}""",
            params,
        )

    def discount_impact(self, f: Filters) -> list[dict[str, Any]]:
        where, params = f.where()
        return self._query(
            f"""SELECT band, ROUND(SUM(sales), 2) AS sales, ROUND(SUM(profit), 2) AS profit,
                       COUNT(*) AS order_lines, ROUND(100 * SUM(profit) / NULLIF(SUM(sales), 0), 2) AS margin_pct
                FROM (SELECT sales, profit, CASE
                          WHEN discount = 0 THEN '0 none'
                          WHEN discount <= 0.1 THEN '1 up to 10%'
                          WHEN discount <= 0.2 THEN '2 10-20%'
                          WHEN discount <= 0.3 THEN '3 20-30%'
                          WHEN discount <= 0.5 THEN '4 30-50%'
                          ELSE '5 over 50%' END AS band
                      FROM {V}{where}) d
                GROUP BY band ORDER BY band""",
            params,
        )

    def shipping(self, f: Filters) -> list[dict[str, Any]]:
        where, params = f.where()
        return self._query(
            f"""SELECT ship_mode, COUNT(DISTINCT order_id) AS orders, ROUND(AVG(shipping_days), 2) AS avg_days,
                       ROUND(AVG(shipping_cost), 2) AS avg_cost
                FROM {V}{where} GROUP BY ship_mode ORDER BY avg_days, ship_mode""",
            params,
        )

    def dashboard(self, f: Filters, *, grain: str = "month") -> dict[str, Any]:
        """Everything the overview page needs, in one round trip."""
        return {
            **self.summary(f, compare=True),
            "trend": self.trend(f, grain),
            "by_category": self.by_dimension("category", f),
            "by_region": self.by_dimension("region", f),
            "by_market": self.by_dimension("market", f),
            "by_sub_category": self.by_dimension("sub_category", f, order_by="profit"),
            "top_products": self.top_products(f, 10),
            "top_customers": self.top_customers(f, 10),
            "discount_impact": self.discount_impact(f),
            "shipping": self.shipping(f),
        }


def _filters_dict(f: Filters) -> dict[str, Any]:
    return {
        "date_from": f.date_from.isoformat() if f.date_from else None,
        "date_to": f.date_to.isoformat() if f.date_to else None,
        "category": f.category,
        "region": f.region,
        "market": f.market,
    }
