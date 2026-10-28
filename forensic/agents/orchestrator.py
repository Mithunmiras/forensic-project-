"""Orchestrator agent: question -> investigation plan (product, region, month, intent).

Entity extraction is rule-based first (aliases, region names, month expressions), so the plan
is reproducible and explainable. If the rules leave a field open and an LLM is configured, the
LLM is asked for it (restricted to allowed values, e.g. "around Christmas" -> December).
Anything still open is resolved by scanning the monthly metrics for the most anomalous
matching product / region / month. The plan records how every field was decided.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import List, Optional

from forensic import llm
from forensic.metrics import monthly_metrics
from forensic.store import DataStore

MONTHS = {"january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4,
          "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9,
          "sep": 9, "sept": 9, "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12}
_MONTH_NAME = "|".join(sorted(MONTHS, key=len, reverse=True))
_MONTH_RE = re.compile(rf"\b({_MONTH_NAME})\b\.?(?:\s*,?\s*(20\d\d))?", re.I)
_ISO_MONTH_RE = re.compile(r"\b(20\d\d)-(0[1-9]|1[0-2])\b")
_MAY_AS_MONTH = re.compile(r"(\b(in|during|for|of|since|until|by)\s+may\b|\bmay\s*,?\s*20\d\d\b)", re.I)

INTENT_PATTERNS = {
    "predictive": re.compile(r"\b(forecast|predict\w*|next month|will|outlook|expect\w*|going forward)\b", re.I),
    "prescriptive": re.compile(r"\b(should|recommend\w*|what to do|action|fix|mitigat\w*|prevent)\b", re.I),
    "diagnostic": re.compile(r"\b(why|cause[sd]?|reason|explain\w*|root|driver|behind|going on|problem|issue)\b", re.I),
    "descriptive": re.compile(r"\b(what happened|how (much|many)|show|summari[sz]e|performance)\b", re.I),
}
_DOWN = re.compile(r"\b(drop\w*|fall|fell|falling|declin\w*|dip\w*|down|decreas\w*|slump\w*|lower|slow\w*|weak\w*)\b", re.I)
_UP = re.compile(r"\b(ris\w*|rose|spike\w*|jump\w*|increas\w*|up|surg\w*|higher|grow\w*|high|boost\w*)\b", re.I)


@dataclass
class Plan:
    question: str
    product_id: Optional[str]
    product_name: Optional[str]
    region: Optional[str]
    month: Optional[str]
    intent: str
    direction: Optional[str]
    resolution: dict = field(default_factory=dict)  # field -> how it was decided
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _extract_product(q: str, products: list) -> Optional[dict]:
    ql = q.lower()
    best = None
    for p in products:
        for alias in p["aliases"] + [p["product_id"].lower()]:
            if re.search(rf"\b{re.escape(alias)}\b", ql) and (best is None or len(alias) > best[1]):
                best = (p, len(alias))
    return best[0] if best else None


def _extract_month(q: str, months: list) -> Optional[str]:
    m = _ISO_MONTH_RE.search(q)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    for m in _MONTH_RE.finditer(q):
        word = m.group(1).lower()
        if word == "may" and not _MAY_AS_MONTH.search(q):
            continue
        num = MONTHS[word]
        if m.group(2):
            return f"{m.group(2)}-{num:02d}"
        # No year: take the matching month inside the data range (latest if several).
        matches = [mo for mo in months if int(mo[5:]) == num]
        return matches[-1] if matches else f"????-{num:02d}"
    return None


def _intent(q: str) -> str:
    hits = [name for name, rx in INTENT_PATTERNS.items() if rx.search(q)]
    return hits[0] if len(hits) == 1 else "all"


class Orchestrator:
    name = "Orchestrator"

    def __init__(self, store: DataStore) -> None:
        self.store = store

    def plan(self, question: str, product_id: Optional[str] = None, region: Optional[str] = None,
             month: Optional[str] = None, use_llm: bool = True) -> Plan:
        q = question.strip()
        resolution, notes = {}, []

        product = None
        if product_id:
            product = next((p for p in self.store.products if p["product_id"] == product_id), None)
            resolution["product"] = "selected in the filters"
        else:
            product = _extract_product(q, self.store.products)
            if product:
                resolution["product"] = "extracted from the question"

        if region:
            resolution["region"] = "selected in the filters"
        else:
            region = next((name for rx, name in self.store.dataset.region_patterns if re.search(rx, q, re.I)), None)
            if region:
                resolution["region"] = "extracted from the question"

        if month:
            resolution["month"] = "selected in the filters"
        else:
            month = _extract_month(q, self.store.months)
            if month:
                resolution["month"] = "extracted from the question"
        if month and month not in self.store.months:
            notes.append(f"{month} is outside the data range ({self.store.months[0]} to {self.store.months[-1]}).")

        direction = None
        if _DOWN.search(q) and not _UP.search(q):
            direction = "down"
        elif _UP.search(q) and not _DOWN.search(q):
            direction = "up"

        plan = Plan(question=q, product_id=product["product_id"] if product else None,
                    product_name=product["product_name"] if product else None, region=region, month=month,
                    intent=_intent(q), direction=direction, resolution=resolution, notes=notes)
        if use_llm and llm.enabled() and not (plan.product_id and plan.region and plan.month):
            self._fill_by_llm(plan)
        if not (plan.product_id and plan.region and plan.month):
            self._fill_by_scan(plan)
        return plan

    def _fill_by_llm(self, plan: Plan) -> None:
        try:
            found = llm.extract_entities(plan.question, self.store.products, list(self.store.dataset.regions),
                                         self.store.months)
        except llm.LLMUnavailable as e:
            plan.notes.append(f"LLM entity extraction unavailable ({e}); used rules and scanning only.")
            return
        how = f"inferred by the LLM ({llm.model_name()}) and validated against allowed values"
        if not plan.product_id and found["product_id"]:
            plan.product_id = found["product_id"]
            plan.product_name = next(p["product_name"] for p in self.store.products if p["product_id"] == plan.product_id)
            plan.resolution["product"] = how
        if not plan.region and found["region"]:
            plan.region = found["region"]
            plan.resolution["region"] = how
        if not plan.month and found["month"]:
            plan.month = found["month"]
            plan.resolution["month"] = how

    def _fill_by_scan(self, plan: Plan) -> None:
        """Pick the most anomalous product/region/month that matches whatever the question fixed."""
        df = monthly_metrics(self.store)
        cand = df
        if plan.product_id:
            cand = cand[cand["product_id"] == plan.product_id]
        if plan.region:
            cand = cand[cand["region"] == plan.region]
        if plan.month:
            cand = cand[cand["month"] == plan.month]
        if cand.empty:
            # e.g. a product with documents but no sales: fall back to its most recent document.
            docs = [d for d in self.store.documents if d.product_id == plan.product_id
                    and (not plan.region or d.region in (plan.region, "ALL"))]
            incident = [d for d in docs if d.region != "ALL"] or docs
            if incident:
                latest = max(incident, key=lambda d: d.date)
                if not plan.month:
                    plan.month = latest.date[:7]
                    plan.resolution["month"] = f"no sales data - taken from the latest document ({latest.filename})"
                if not plan.region and latest.region != "ALL":
                    plan.region = latest.region
                    plan.resolution["region"] = f"no sales data - taken from the latest document ({latest.filename})"
            if not plan.product_id:
                plan.notes.append("No product could be identified in the question.")
            return
        ranked = cand.copy()
        if plan.direction == "down":
            ranked = ranked[ranked["units_per_day_pct"] < 0] if (ranked["units_per_day_pct"] < 0).any() else ranked
        elif plan.direction == "up":
            ranked = ranked[ranked["units_per_day_pct"] > 0] if (ranked["units_per_day_pct"] > 0).any() else ranked
        best = ranked.sort_values("anomaly_score", ascending=False).iloc[0]
        scope = len(cand)
        for key, col in (("product", "product_id"), ("region", "region"), ("month", "month")):
            current = getattr(plan, "product_id" if key == "product" else key)
            if current:
                continue
            value = best[col]
            if key == "product":
                plan.product_id = value
                plan.product_name = next(p["product_name"] for p in self.store.products if p["product_id"] == value)
            else:
                setattr(plan, key, value)
            plan.resolution[key] = (f"not in the question - scanned {scope} product/region/month combinations "
                                    f"and picked the most anomalous (score {best['anomaly_score']})")
