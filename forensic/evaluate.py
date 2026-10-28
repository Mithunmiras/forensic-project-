"""Scores the agents against the ground truth in scenarios.py.

For every scenario and control the scenario's question is replayed through the full pipeline
and four things are checked:
  * cause       - the right root cause (or "none" for controls), not just a plausible one
  * case        - the right evidence situation (full / structured_only / unstructured_only / none)
  * confidence  - the expected confidence label
  * citation    - when a scenario document exists, the answer cites exactly that file
"""
from __future__ import annotations

from forensic.pipeline import get_investigator
from forensic.scenarios import CONTROLS, SCENARIOS


def _expected_doc(sc: dict):
    doc = sc.get("doc")
    if not doc:
        return None
    return f"{sc['product_id']}/{doc['doc_type']}_{doc['date']}_{sc['region'].lower()}.txt"


def evaluate() -> dict:
    inv = get_investigator()
    rows = []
    for sc in SCENARIOS + CONTROLS:
        res = inv.investigate(sc["question"])
        ans, plan = res["answer"], res["plan"]
        exp = sc["expected"]
        cited = [c["path"] for c in ans["citations"] if c["kind"] == "document"]
        incident_cited = ans["cause"]["status"] in ("confirmed", "reported", "inferred") and any(
            p == _expected_doc(sc) for p in cited)
        expected_doc = _expected_doc(sc)
        row = {
            "id": sc["id"], "question": sc["question"],
            "target": f"{sc['product_id']} / {sc['region']} / {sc['month']}",
            "resolved": f"{plan['product_id']} / {plan['region']} / {plan['month']}",
            "expected_cause": exp["cause"], "predicted_cause": ans["cause"]["key"],
            "expected_case": exp["case"], "predicted_case": ans["case"],
            "expected_confidence": exp["confidence"], "predicted_confidence": ans["confidence"]["label"],
            "confidence_score": ans["confidence"]["score"],
            "expected_document": expected_doc,
            "cause_ok": ans["cause"]["key"] == exp["cause"],
            "case_ok": ans["case"] == exp["case"],
            "confidence_ok": ans["confidence"]["label"] == exp["confidence"],
            "citation_ok": incident_cited if expected_doc else True,
            "plan_ok": (plan["product_id"], plan["region"], plan["month"]) == (sc["product_id"], sc["region"], sc["month"]),
            "headline": ans["headline"],
        }
        row["all_ok"] = all(row[k] for k in ("cause_ok", "case_ok", "confidence_ok", "citation_ok", "plan_ok"))
        rows.append(row)

    def acc(key, subset=None):
        sel = [r for r in rows if subset is None or subset(r)]
        return {"correct": sum(r[key] for r in sel), "total": len(sel)}

    is_control = lambda r: r["id"].startswith("CT")  # noqa: E731
    summary = {
        "root_cause_accuracy": acc("cause_ok", lambda r: not is_control(r)),
        "no_false_cause_on_controls": acc("cause_ok", is_control),
        "evidence_case_accuracy": acc("case_ok"),
        "confidence_label_accuracy": acc("confidence_ok"),
        "correct_document_cited": acc("citation_ok", lambda r: r["expected_document"] is not None),
        "entity_extraction_accuracy": acc("plan_ok"),
        "fully_correct": acc("all_ok"),
    }
    return {"summary": summary, "rows": rows}


def print_report(result: dict) -> None:
    print(f"{'id':5} {'expected cause':24} {'predicted':24} {'case':18} {'conf':7} ok")
    for r in result["rows"]:
        print(f"{r['id']:5} {r['expected_cause']:24} {r['predicted_cause']:24} {r['predicted_case']:18} "
              f"{r['predicted_confidence']:7} {'yes' if r['all_ok'] else 'NO'}")
    print()
    for k, v in result["summary"].items():
        print(f"{k:32} {v['correct']}/{v['total']}")
