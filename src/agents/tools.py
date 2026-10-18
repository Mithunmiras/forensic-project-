"""The three tools the orchestrator can call: SQL analytics, ML prediction, RAG.

Each tool has the same tiny interface (``run(question) -> ToolResult``), validates
its own input, and converts every failure into a ``ToolResult`` - a tool never
raises into the orchestrator and never fabricates output.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from src.analytics.sql_agent import SqlAgent
from src.llm.client import LLM, LLMUnavailable
from src.ml.service import InvalidPrediction, ModelNotReady, ModelService
from src.rag.service import KnowledgeBase

log = logging.getLogger("retailiq.agents.tools")


@dataclass
class ToolResult:
    name: str                     # sql | ml | rag
    status: str                   # ok | no_results | error | unavailable | needs_input | skipped
    data: dict[str, Any] = field(default_factory=dict)
    message: str | None = None    # human-readable reason when status != ok
    duration_ms: float = 0.0

    def public(self) -> dict[str, Any]:
        return {"name": self.name, "status": self.status, "message": self.message, "duration_ms": round(self.duration_ms, 1)}


class Tool(Protocol):
    name: str

    def run(self, question: str) -> ToolResult: ...


def _timed(fn):
    def wrapper(self, question: str) -> ToolResult:
        started = time.perf_counter()
        try:
            result = fn(self, question)
        except Exception as exc:  # noqa: BLE001 - the contract: tools never raise
            log.exception("Tool %s crashed", getattr(self, "name", "?"))
            result = ToolResult(getattr(self, "name", "?"), "error", message=f"Unexpected {exc.__class__.__name__} in tool.")
        result.duration_ms = (time.perf_counter() - started) * 1000
        return result

    return wrapper


class SqlTool:
    name = "sql"

    def __init__(self, agent: SqlAgent) -> None:
        self.agent = agent

    @_timed
    def run(self, question: str) -> ToolResult:
        ans = self.agent.answer(question)
        data = ans.as_dict()
        if ans.status == "ok":
            return ToolResult(self.name, "ok", data)
        status = "unavailable" if ans.status == "unavailable" else "error"
        return ToolResult(self.name, status, data, message=ans.error)


# ----------------------------------------------------------------------------- ML extraction
_QTY = re.compile(r"(\d+)\s*(?:units?|pcs|pieces|items|qty)\b|\b(?:quantity|qty)\s*(?:of|=|:|is)?\s*(\d+)", re.I)
_DISC_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*%\s*(?:discount|off)?|discount\s*(?:of|=|:|at|is)?\s*(\d+(?:\.\d+)?)\s*(%)?", re.I)
_SHIPCOST = re.compile(r"shipping\s*cost\s*(?:of|=|:|is)?\s*\$?\s*(\d+(?:\.\d+)?)", re.I)
_SHIPDAYS = re.compile(r"(\d+)\s*(?:shipping\s*)?days?\b", re.I)
_DATE = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
_ALLOWED_LLM_KEYS = {"category", "sub_category", "market", "segment", "ship_mode", "order_priority",
                     "quantity", "discount", "shipping_cost", "shipping_days", "order_date"}


def _match_value(text: str, values: list[str]) -> str | None:
    lower = text.lower()
    for v in sorted(values, key=len, reverse=True):
        if len(v) <= 3:
            if re.search(rf"\b{re.escape(v)}\b", text):
                return v
        elif re.search(rf"\b{re.escape(v.lower())}(?:s|es)?\b", lower) or (
            v.lower().endswith("s") and re.search(rf"\b{re.escape(v.lower()[:-1])}\b", lower)
        ):
            return v
    return None


def extract_prediction_inputs(question: str, options: dict[str, Any]) -> dict[str, Any]:
    """Pull model inputs out of free text with deterministic rules."""
    data: dict[str, Any] = {}
    all_subs = [s for subs in options["sub_categories"].values() for s in subs]
    sub = _match_value(question, all_subs)
    if sub:
        data["sub_category"] = sub
        data["category"] = next(c for c, subs in options["sub_categories"].items() if sub in subs)
    cat = _match_value(question, options["categories"])
    if cat and "category" not in data:
        data["category"] = cat
    for field_name, key in (("market", "markets"), ("segment", "segments"), ("ship_mode", "ship_modes")):
        v = _match_value(question, options[key])
        if v:
            data[field_name] = v
    m = re.search(r"\b(low|medium|high|critical)\s+priority\b", question, re.I)
    if m:
        data["order_priority"] = m.group(1).capitalize()
    if m := _QTY.search(question):
        data["quantity"] = int(m.group(1) or m.group(2))
    if m := _SHIPCOST.search(question):
        data["shipping_cost"] = float(m.group(1))
    if m := _SHIPDAYS.search(question):
        data["shipping_days"] = int(m.group(1))
    if m := _DATE.search(question):
        data["order_date"] = m.group(1)
    if m := _DISC_PCT.search(question):
        raw = float(m.group(1) or m.group(2))
        pct = "%" in m.group(0) or raw > 1
        data["discount"] = round(raw / 100 if pct else raw, 4)
    return data


class MlTool:
    name = "ml"
    REQUIRED = ("sub_category", "market", "quantity")

    def __init__(self, model: ModelService, llm: LLM) -> None:
        self.model, self.llm = model, llm

    def _llm_extract(self, question: str, options: dict[str, Any]) -> dict[str, Any]:
        prompt = (
            "Extract order attributes from the text as JSON. Allowed keys: category, sub_category, market, segment, "
            "ship_mode, order_priority, quantity (int), discount (0-1 fraction), shipping_cost (number), "
            "shipping_days (int), order_date (YYYY-MM-DD). Omit anything not stated. Do not invent values. "
            f"Valid categories: {options['categories']}; sub-categories: {options['sub_categories']}; markets: {options['markets']}."
        )
        try:
            raw = self.llm.chat([{"role": "system", "content": prompt}, {"role": "user", "content": question}], json_mode=True)
            parsed = json.loads(re.search(r"\{.*\}", raw, re.S).group(0))  # type: ignore[union-attr]
        except (LLMUnavailable, AttributeError, json.JSONDecodeError):
            return {}
        return {k: v for k, v in parsed.items() if k in _ALLOWED_LLM_KEYS and v not in (None, "")} if isinstance(parsed, dict) else {}

    @_timed
    def run(self, question: str) -> ToolResult:
        if not self.model.ready:
            return ToolResult(self.name, "unavailable", message=self.model.error or "Model is not loaded.",
                              data={"hint": "python scripts/train_model.py"})
        options = self.model.metadata()["options"]
        data = extract_prediction_inputs(question, options)
        if any(f not in data for f in self.REQUIRED) and self.llm.available:
            for k, v in self._llm_extract(question, options).items():
                data.setdefault(k, v)
        missing = [f for f in self.REQUIRED if f not in data]
        if missing:
            return ToolResult(
                self.name, "needs_input", message="More information is needed to estimate sales.",
                data={
                    "missing": missing, "understood": data,
                    "example": "Predict sales for 3 units of Phones in the US with a 10% discount",
                    "optional": ["segment", "ship mode", "order priority", "shipping cost", "shipping days", "order date"],
                },
            )
        assumptions: list[str] = []
        if "discount" not in data:
            data["discount"] = 0.0
            assumptions.append("No discount was mentioned; assumed 0%.")
        try:
            result = self.model.predict(dict(data))
        except InvalidPrediction as exc:
            return ToolResult(self.name, "error", message=f"Invalid input: {exc}", data={"errors": exc.errors, "understood": data})
        except ModelNotReady as exc:
            return ToolResult(self.name, "unavailable", message=str(exc))
        result["assumptions"] = assumptions + result["assumptions"]
        return ToolResult(self.name, "ok", result)


class RagTool:
    name = "rag"

    def __init__(self, kb: KnowledgeBase) -> None:
        self.kb = kb

    @_timed
    def run(self, question: str) -> ToolResult:
        answer = self.kb.ask(question)
        if answer["retrieval_mode"] == "none":
            return ToolResult(self.name, "unavailable", answer, message=answer["answer"])
        status = "ok" if answer["sources"] else "no_results"
        return ToolResult(self.name, status, answer)
