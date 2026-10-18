"""Single-pass multi-tool orchestrator.

route -> run each selected tool once (bounded count + time budget) -> compose.
Tools cannot call other tools, so there is no recursion. Every tool failure is
reported in the response; nothing is invented to fill a gap.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from src.agents.composer import compose
from src.agents.router import RoutePlan, route
from src.agents.tools import MlTool, RagTool, SqlTool, Tool, ToolResult
from src.config import Settings
from src.llm.client import LLM

log = logging.getLogger("retailiq.agents")

MAX_QUESTION_CHARS = 1000


class Orchestrator:
    def __init__(self, sql: SqlTool, ml: MlTool, rag: RagTool, llm: LLM, settings: Settings, known_values_fn=None) -> None:
        self.tools: dict[str, Tool] = {"sql": sql, "ml": ml, "rag": rag}
        self.llm, self.settings = llm, settings
        self._known_values_fn = known_values_fn

    def _known_values(self) -> dict[str, list[str]]:
        try:
            return self._known_values_fn() if self._known_values_fn else {}
        except Exception:  # noqa: BLE001 - routing must work without the database
            return {}

    def chat(self, message: str) -> dict[str, Any]:
        started = time.perf_counter()
        question = (message or "").strip()[:MAX_QUESTION_CHARS]
        plan: RoutePlan = route(question, self.llm, self.settings.llm_routing, self._known_values())

        results: list[ToolResult] = []
        deadline = started + self.settings.agent_time_budget_s
        for i, name in enumerate(plan.tools):
            if i >= self.settings.agent_max_tool_calls:
                results.append(ToolResult(name, "skipped", message="Tool-call limit reached."))
                continue
            if time.perf_counter() > deadline:
                results.append(ToolResult(name, "skipped", message="Time budget exhausted."))
                continue
            results.append(self.tools[name].run(question))

        answer, mode, warnings = compose(results, question, self.llm)
        by = {r.name: r for r in results}
        evidence: dict[str, Any] = {"sql": None, "prediction": None, "sources": None}
        if "sql" in by and by["sql"].status == "ok":
            evidence["sql"] = by["sql"].data
        if "ml" in by and by["ml"].status == "ok":
            evidence["prediction"] = by["ml"].data
        if "rag" in by and by["rag"].data.get("sources"):
            evidence["sources"] = by["rag"].data["sources"]
            warnings += by["rag"].data.get("warnings", [])
        if plan.method == "llm" and plan.rules_tools and plan.rules_tools != plan.tools:
            warnings.append(f"The LLM router chose {plan.tools}; the rule-based router would have chosen {plan.rules_tools}.")

        elapsed = (time.perf_counter() - started) * 1000
        log.info("chat route=%s method=%s statuses=%s mode=%s %.0fms", plan.tools, plan.method,
                 {r.name: r.status for r in results}, mode, elapsed)
        return {
            "answer": answer,
            "answer_mode": mode,
            "route": {"tools": plan.tools, "method": plan.method, "reason": plan.reason},
            "tools": [r.public() for r in results],
            "evidence": evidence,
            "warnings": warnings,
            "elapsed_ms": round(elapsed, 1),
        }
