"""Tests for the forensic multi-agent pipeline. Run: .venv/bin/python -m pytest"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from forensic.agents.orchestrator import Orchestrator
from forensic.agents.rag_agent import classify
from forensic.api import app
from forensic.evaluate import evaluate
from forensic.metrics import monthly_metrics
from forensic.pipeline import get_investigator
from forensic.scenarios import SCENARIOS
from forensic.store import get_store


@pytest.fixture(scope="module")
def store():
    return get_store()


def test_every_injected_anomaly_detected_and_no_false_positives(store):
    df = monthly_metrics(store)
    injected = {(s["product_id"], s["region"], s["month"]) for s in SCENARIOS if s.get("structured_effect")}
    flagged = {(r.product_id, r.region, r.month) for r in df.itertuples() if r.is_anomaly}
    assert flagged == injected


def test_rag_classifier_matches_ground_truth(store):
    by_path = {d.path: classify(d) for d in store.documents}
    for sc in SCENARIOS:
        if sc.get("doc"):
            path = f"{sc['product_id']}/{sc['doc']['doc_type']}_{sc['doc']['date']}_{sc['region'].lower()}.txt"
            assert by_path[path]["role"] == "incident", path
            assert by_path[path]["cause"] == sc["cause"], path
    incident_paths = {p for p, c in by_path.items() if c["role"] == "incident"}
    assert len(incident_paths) == sum(1 for s in SCENARIOS if s.get("doc"))


@pytest.mark.parametrize("question,expected", [
    ("Why did iPhone 15 sales drop in the North region in March 2026?", ("IPHONE15", "North", "2026-03")),
    ("ipad pro east jan 2026", ("IPADPRO", "East", "2026-01")),
    ("What happened to MacBook Air in the West in 2026-01?", ("MACBOOKAIR", "West", "2026-01")),
    ("What may happen to AirPods Pro in the southern region in May 2026?", ("AIRPODSPRO", "South", "2026-05")),
])
def test_orchestrator_extracts_entities(store, question, expected):
    plan = Orchestrator(store).plan(question)
    assert (plan.product_id, plan.region, plan.month) == expected


def test_orchestrator_scans_when_fields_missing(store):
    plan = Orchestrator(store).plan("Why did AirPods sales drop?")
    assert (plan.product_id, plan.region, plan.month) == ("AIRPODSPRO", "South", "2026-02")
    assert plan.resolution["month"].startswith("not in the question")


def test_full_evaluation_passes():
    result = evaluate()
    failed = [r["id"] for r in result["rows"] if not r["all_ok"]]
    assert failed == []


def test_every_claim_has_citations():
    res = get_investigator().investigate("Why did iPhone 15 sales drop in the North region in March 2026?")
    layers = res["answer"]["layers"]
    for name in ("descriptive", "diagnostic", "predictive", "prescriptive"):
        assert "[" in layers[name], name
    ids = {c["id"] for c in res["answer"]["citations"]}
    assert ids == set(range(1, len(ids) + 1))


@pytest.mark.parametrize("question", [
    "hello",
    "Why did Vision Pro sales drop in December 2025?",
    "Why did iPhone sales fall in August 2026?",
    "What about HomePod?",
])
def test_never_crashes(question):
    res = get_investigator().investigate(question)
    assert res["answer"]["headline"]
    assert res["answer"]["confidence"]["label"] in ("high", "medium", "low")


def test_api_endpoints():
    with TestClient(app) as c:
        assert c.get("/api/health").json() == {"status": "ok"}
        assert len(c.get("/api/meta").json()["products"]) == 7
        assert c.post("/api/investigate", json={"question": "Why did iPad Pro sales drop in North in May 2026?"}) \
            .json()["answer"]["cause"]["key"] == "supplier_delay"
        assert c.post("/api/investigate", json={"question": "x"}).status_code == 422
        assert c.get("/api/documents/IPHONE15/policy_warranty.txt").status_code == 200
        assert c.get("/api/documents/IPHONE15/nope.txt").status_code == 404
        assert c.get("/api/tables/secrets").status_code == 404
