import json
import time

import pytest

from src.agents.composer import compose, compose_deterministic, fmt
from src.agents.orchestrator import Orchestrator
from src.agents.router import route, route_by_rules
from src.agents.tools import ToolResult, extract_prediction_inputs
from src.config import Settings
from tests.helpers import FakeLLM

OPTIONS = {
    "categories": ["Furniture", "Office Supplies", "Technology"],
    "sub_categories": {"Furniture": ["Chairs", "Tables"], "Office Supplies": ["Binders"], "Technology": ["Phones", "Copiers"]},
    "markets": ["US", "EU", "APAC"], "segments": ["Consumer", "Corporate"], "ship_modes": ["Same Day", "Standard Class"],
}


# ------------------------------------------------------------------ routing
@pytest.mark.parametrize(
    "question,tools",
    [
        ("Which category has the highest sales?", ["sql"]),
        ("What is the total profit in 2013?", ["sql"]),
        ("Top 10 products by sales", ["sql"]),
        ("What is the average discount by category?", ["sql"]),
        ("Predict sales for 3 units of Phones in the US with a 10% discount", ["ml"]),
        ("estimate the sales of 5 chairs in EU", ["ml"]),
        ("Explain how the sales prediction model works", ["rag"]),
        ("How accurate is the model?", ["rag"]),
        ("What is leakage in the model", ["rag"]),
        ("How does the ETL pipeline handle duplicates?", ["rag"]),
        ("What does discount mean?", ["rag"]),
        ("Which region performs best, and what factors might explain it?", ["sql", "rag"]),
        ("compare sales by region and explain why", ["sql", "rag"]),
        ("hello", ["rag"]),
    ],
)
def test_rule_based_routing(question, tools):
    assert route_by_rules(question, {}).tools == tools


def test_llm_router_is_validated_and_falls_back():
    q = "Which category has the highest sales?"
    ok = FakeLLM(['{"tools": ["sql", "rag"], "reason": "needs both"}'])
    plan = route(q, ok, True)
    assert plan.method == "llm" and plan.tools == ["sql", "rag"] and plan.rules_tools == ["sql"]
    for bad in ('{"tools": ["shell"]}', '{"tools": []}', "not json", '{"tools": ["sql","ml","rag","sql","x"]}'):
        plan = route(q, FakeLLM([bad]), True)
        if bad.startswith('{"tools": ["sql","ml","rag"'):
            assert plan.tools == ["sql", "ml", "rag"]  # de-duplicated, unknown names dropped
        else:
            assert plan.method == "rules" and plan.tools == ["sql"]
    assert route(q, FakeLLM(available=False), True).method == "rules"
    assert route(q, FakeLLM(['{"tools": ["rag"]}']), False).method == "rules"  # routing disabled


# ------------------------------------------------------------------ prediction input extraction
def test_extracts_order_attributes_from_text():
    d = extract_prediction_inputs("Predict sales for 3 units of Phones in the US with a 10% discount, shipping cost $25, 4 days", OPTIONS)
    assert d == {"sub_category": "Phones", "category": "Technology", "market": "US", "quantity": 3,
                 "discount": 0.1, "shipping_cost": 25.0, "shipping_days": 4}


def test_extraction_variants():
    d = extract_prediction_inputs("estimate sales of quantity 5 chairs, EU market, consumer segment, high priority, same day, 2014-03-02", OPTIONS)
    assert d["sub_category"] == "Chairs" and d["category"] == "Furniture" and d["market"] == "EU"
    assert d["quantity"] == 5 and d["segment"] == "Consumer" and d["order_priority"] == "High"
    assert d["ship_mode"] == "Same Day" and d["order_date"] == "2014-03-02"
    assert extract_prediction_inputs("discount of 0.25 on 2 binders in apac", OPTIONS)["discount"] == 0.25
    assert extract_prediction_inputs("discount 30%", OPTIONS)["discount"] == 0.3


def test_extraction_does_not_invent_values():
    assert extract_prediction_inputs("predict something", OPTIONS) == {}
    d = extract_prediction_inputs("sales for Technology", OPTIONS)
    assert d == {"category": "Technology"}


# ------------------------------------------------------------------ composition
def sql_result(rows, cols, chart=None):
    return ToolResult("sql", "ok", {
        "explanation": "Total sales by category.", "columns": [{"name": c, "type": "text"} for c in cols], "rows": rows,
        "row_count": len(rows), "chart": chart})


def test_formatting_helpers():
    assert fmt("total_sales", 4744691.0) == "$4,744,691"
    assert fmt("avg_discount_pct", 16.81) == "16.81%"
    assert fmt("avg_shipping_days", 5.0) == "5"
    assert fmt("orders", 25035) == "25,035"
    assert fmt("x", None) == "n/a"


def test_deterministic_answer_uses_only_tool_values():
    r = sql_result([["Technology", 4744691.0], ["Furniture", 4110884.0]], ["category", "total_sales"], {"type": "bar"})
    text = compose_deterministic([r])
    assert "Technology ($4,744,691)" in text and "Furniture ($4,110,884)" in text
    assert "Measured from the database" in text


def test_needs_input_and_failures_are_explicit():
    needs = ToolResult("ml", "needs_input", {"missing": ["market"], "example": "e.g.", "optional": ["segment"]})
    assert "market" in compose_deterministic([needs])
    down = ToolResult("sql", "unavailable", message="Database unavailable: refused")
    assert "unavailable" in compose_deterministic([down]).lower() and "refused" in compose_deterministic([down])


def test_measured_and_documented_sections_are_separate():
    rag = ToolResult("rag", "ok", {"answer": "Definitions...", "answer_mode": "extractive", "retrieval_mode": "semantic",
                                   "sources": [{"id": 1, "source": "docs/x.md", "snippet": "s"}]})
    text = compose_deterministic([sql_result([["West", 1.0]], ["region", "total_sales"]), rag])
    assert text.index("Measured from the database") < text.index("Context from project documentation")
    assert "does not prove why" in text


def test_llm_composition_gets_evidence_and_can_fail_over():
    r = sql_result([["West", 1.0]], ["region", "total_sales"])
    llm = FakeLLM(["Final LLM answer."])
    answer, mode, warnings = compose([r], "q", llm)
    assert (answer, mode) == ("Final LLM answer.", "llm") and "West" in llm.calls[0][1]["content"]
    answer, mode, warnings = compose([r], "q", FakeLLM(fail=True))
    assert mode == "deterministic" and warnings and "Measured from the database" in answer


# ------------------------------------------------------------------ orchestrator
class StubTool:
    def __init__(self, name, result=None, boom=False, delay=0.0):
        self.name, self.result, self.boom, self.delay, self.calls = name, result, boom, delay, 0

    def run(self, question):
        self.calls += 1
        time.sleep(self.delay)
        if self.boom:
            raise RuntimeError("tool exploded")
        return self.result or ToolResult(self.name, "ok", {"answer": "x", "sources": [], "answer_mode": "extractive", "retrieval_mode": "semantic"})


def make_orch(tools, llm=None, **settings):
    s = Settings(_env_file=None, llm_provider="none", **settings)
    return Orchestrator(tools["sql"], tools["ml"], tools["rag"], llm or FakeLLM(available=False), s)


def stubs(**over):
    base = {n: StubTool(n) for n in ("sql", "ml", "rag")}
    base.update(over)
    return base


def test_each_tool_runs_once_and_response_has_provenance():
    t = stubs(sql=StubTool("sql", sql_result([["a", 1.0]], ["category", "total_sales"])))
    out = make_orch(t).chat("Which region performs best, and what factors might explain it?")
    assert out["route"]["tools"] == ["sql", "rag"] and out["route"]["method"] == "rules"
    assert [x["name"] for x in out["tools"]] == ["sql", "rag"]
    assert t["sql"].calls == 1 and t["rag"].calls == 1 and t["ml"].calls == 0
    assert out["evidence"]["sql"] is not None and out["answer_mode"] == "deterministic"


def test_tool_crash_is_isolated():
    from src.agents.tools import _timed

    class Crashing:
        name = "sql"

        @_timed
        def run(self, question):
            raise RuntimeError("boom")

    t = stubs(sql=Crashing())
    out = make_orch(t).chat("Which region performs best, and what factors might explain it?")
    statuses = {x["name"]: x["status"] for x in out["tools"]}
    assert statuses == {"sql": "error", "rag": "ok"}
    assert "Database analytics unavailable" in out["answer"]


def test_malformed_tool_result_does_not_break_the_answer():
    bad = ToolResult("sql", "ok", {"answer": "wrong shape"})
    out = make_orch(stubs(sql=StubTool("sql", bad))).chat("Which category has the highest sales?")
    assert "could not be formatted" in out["answer"]


def test_tool_call_limit_and_time_budget():
    good = sql_result([["a", 1.0]], ["category", "total_sales"])
    t = stubs(sql=StubTool("sql", good), rag=StubTool("rag", delay=0.15))
    out = make_orch(t, agent_max_tool_calls=1).chat("compare sales by region and explain why")
    assert [x["status"] for x in out["tools"]] == ["ok", "skipped"]
    t = stubs(sql=StubTool("sql", good, delay=0.2))
    out = make_orch(t, agent_time_budget_s=0.05).chat("compare sales by region and explain why")
    assert [x["status"] for x in out["tools"]] == ["ok", "skipped"] and "Time budget" in out["tools"][1]["message"]


def test_question_is_truncated_and_empty_is_safe():
    t = stubs()
    out = make_orch(t).chat("x" * 5000)
    assert out["route"]["tools"] == ["rag"]
    assert make_orch(stubs()).chat("")["route"]["tools"] == ["rag"]


def test_llm_router_disagreement_is_reported():
    llm = FakeLLM(['{"tools": ["rag"], "reason": "docs"}', "Composed by the LLM."])
    out = make_orch(stubs(), llm=llm, llm_routing=True).chat("Which category has the highest sales?")
    assert out["route"]["method"] == "llm" and out["answer_mode"] == "llm"
    assert any("rule-based router would have chosen" in w for w in out["warnings"])


def test_response_is_json_serialisable():
    out = make_orch(stubs()).chat("hello")
    json.dumps(out)
