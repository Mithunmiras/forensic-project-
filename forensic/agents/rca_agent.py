"""Forecast / RCA agent.

RCA half: is the month actually unusual for this series (robust z vs. leave-one-out baseline),
which structured signature fired (stock-out, returns, discount, price, demand), is it local to
the region or market-wide, and which causes are compatible with that signature.

Forecast half: Holt-Winters (damped additive trend, weekly seasonality) trained on daily units
up to the end of the investigated month, projected over the next month. Also reports the
"cause persists" scenario and, when the data has it, the held-out actual for that month.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from forensic import holtwinters
from forensic.catalog import CAUSES, STRUCTURED_HYPOTHESES

FAMILY_ORDER = ["supply", "returns", "discount", "price", "demand_down", "demand_up"]


def compatible_causes(families: list) -> list:
    return [c for c, spec in CAUSES.items() if set(spec["families"]) & set(families)]


class ForecastRCAAgent:
    name = "Forecast / RCA Agent"

    def run(self, sql: dict) -> dict:
        out = {"agent": self.name, "available": False, "reason": ""}
        if not sql.get("available"):
            out["reason"] = "Needs structured data, which is unavailable: " + (sql.get("reason") or "")
            return out
        t = sql["target"]
        families = [f for f in FAMILY_ORDER if f in t["signals"]]
        primary = families[0] if families else None
        hypothesis = STRUCTURED_HYPOTHESES[primary] if primary else None

        others = sql["other_regions"]
        others_moved = [o for o in others if abs(o["units_per_day_pct"]) >= 5]
        if not others:
            scope = "unknown"
        elif not others_moved:
            scope = "localized"
        elif len(others_moved) == len(others):
            scope = "market-wide"
        else:
            scope = "partly shared"

        out.update({
            "available": True,
            "is_anomaly": bool(t["is_anomaly"]),
            "anomaly_score": t["anomaly_score"],
            "units_z": round(t["units_per_day_z"], 2),
            "returns_z": round(t["returns_rate_z"], 2),
            "signature": families,
            "hypothesis": {"key": hypothesis[0], "label": hypothesis[1]} if hypothesis else None,
            "compatible_causes": compatible_causes(families),
            "scope": scope,
            "checks": self._checks(sql),
            "forecast": self._forecast(sql),
        })
        return out

    @staticmethod
    def _checks(sql: dict) -> list:
        """Each structured test, pass/fail, so the synthesis can say what was ruled out."""
        t = sql["target"]
        return [
            {"key": "supply", "fired": t["stockout_days"] >= 3,
             "detail": f"{int(t['stockout_days'])} stock-out day(s) at {sql['stockout']['warehouse']}"},
            {"key": "returns", "fired": "returns" in t["signals"],
             "detail": f"returns rate {t['returns_rate']:.2f}% vs. {t['returns_rate_base']:.2f}% baseline, "
                       f"z = {t['returns_rate_z']:.1f}"},
            {"key": "discount", "fired": "discount" in t["signals"],
             "detail": f"average discount {t['avg_discount']:.1f}% vs. {t['avg_discount_base']:.1f}% baseline"},
            {"key": "price", "fired": "price" in t["signals"],
             "detail": f"realised list price {t['price_index_pct']:+.1f}% vs. baseline"},
            {"key": "demand", "fired": any(f in t["signals"] for f in ("demand_down", "demand_up")),
             "detail": f"units/day {t['units_per_day_pct']:+.1f}% vs. baseline, z = {t['units_per_day_z']:.1f}"},
        ]

    @staticmethod
    def _forecast(sql: dict) -> Optional[dict]:
        daily = pd.DataFrame(sql["daily"])
        daily["date"] = pd.to_datetime(daily["date"])
        series = daily.set_index("date")["units"].astype(float).asfreq("D")
        month_end = pd.Period(sql["month"]).end_time.normalize()
        history = series[:month_end]
        next_period = pd.Period(sql["month"]) + 1
        horizon = pd.date_range(next_period.start_time, next_period.end_time.normalize(), freq="D")
        if len(history) < 28:
            return None
        fc = holtwinters.forecast(history.to_numpy(), len(horizon), season=7)
        t = sql["target"]
        base = t["units_per_day_base"]
        predicted = float(np.mean(fc))
        persists = base * (1 + t["units_per_day_pct"] / 100)
        actual_slice = series[horizon[0]:horizon[-1]]
        actual = float(actual_slice.mean()) if len(actual_slice) == len(horizon) else None
        return {
            "method": "Holt-Winters exponential smoothing (damped additive trend, weekly seasonality)",
            "trained_through": month_end.strftime("%Y-%m-%d"),
            "next_month": str(next_period),
            "baseline_per_day": round(base, 1),
            "predicted_per_day": round(predicted, 1),
            "predicted_pct_vs_baseline": round((predicted - base) / base * 100, 1),
            "if_cause_persists_per_day": round(persists, 1),
            "if_cause_persists_pct": round(t["units_per_day_pct"], 1),
            "actual_per_day": round(actual, 1) if actual is not None else None,
            "actual_pct_vs_baseline": round((actual - base) / base * 100, 1) if actual is not None else None,
            "series": [{"date": d.strftime("%Y-%m-%d"), "forecast": round(float(v), 1)} for d, v in zip(horizon, fc)],
        }
