"""LLM paths with a stubbed model: validation must hold whatever the model says."""
from __future__ import annotations

import json

import pytest

from forensic import llm
from forensic.agents.orchestrator import Orchestrator
from forensic.pipeline import get_investigator
from forensic.store import get_store


@pytest.fixture
def stub(monkeypatch):
    replies = []
    monkeypatch.setattr(llm, "enabled", lambda: True)
    monkeypatch.setattr(llm, "chat", lambda messages, **kw: replies.pop(0))
    return replies


def test_llm_fills_only_missing_fields_with_allowed_values(stub):
    stub.append(json.dumps({"product_id": "APPLEWATCH", "region": "North", "month": "2025-12"}))
    plan = Orchestrator(get_store()).plan("how did the watch do up north around christmas?")
    assert (plan.product_id, plan.region, plan.month) == ("APPLEWATCH", "North", "2025-12")
    assert plan.resolution["month"].startswith("inferred by the LLM")
    assert plan.resolution["region"] == "extracted from the question"


def test_llm_invalid_values_are_dropped(stub):
    stub.append(json.dumps({"product_id": "PIXEL9", "region": "Mars", "month": "2031-01"}))
    plan = Orchestrator(get_store()).plan("how are things going?")
    assert plan.product_id != "PIXEL9" and plan.region in ("North", "South", "East", "West")
    assert not any("LLM" in v for v in plan.resolution.values())


def test_llm_failure_falls_back_to_rules(monkeypatch):
    monkeypatch.setattr(llm, "enabled", lambda: True)

    def boom(*a, **k):
        raise llm.LLMUnavailable("down")
    monkeypatch.setattr(llm, "chat", boom)
    plan = Orchestrator(get_store()).plan("Why did AirPods sales drop?")
    assert (plan.product_id, plan.region, plan.month) == ("AIRPODSPRO", "South", "2026-02")
    assert any("unavailable" in n for n in plan.notes)


def test_grounding_check_rejects_invented_numbers_and_citations():
    evidence = "Sales fell 16.9% to 1,164 units/day [1]. Stock-out of 9 days [2]."
    assert llm.grounding_check("Sales fell 16.9% to 1,164 units [1].", evidence, 2) == []
    problems = llm.grounding_check("Sales fell 25% [1] and will recover by 40% [5].", evidence, 2)
    assert any("25" in p for p in problems) and any("40" in p for p in problems) and any("[5]" in p for p in problems)


def test_summary_marks_ungrounded_text(stub):
    ans = get_investigator().investigate("Why did iPhone 15 sales drop in the North region in March 2026?",
                                         use_llm=False)["answer"]
    stub.append("Sales fell 99% because of aliens [1].")
    out = llm.summarize("q", ans)
    assert out["grounded"] is False and out["problems"]
