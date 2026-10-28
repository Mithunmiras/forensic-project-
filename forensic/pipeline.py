"""Runs one investigation: orchestrator -> (SQL || RAG) -> forecast/RCA -> synthesis."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import Optional

from forensic.agents.orchestrator import Orchestrator
from forensic.agents.rag_agent import RAGAgent
from forensic.agents.rca_agent import ForecastRCAAgent
from forensic.agents.sql_agent import SQLAnalyticsAgent
from forensic.agents.synthesis_agent import SynthesisAgent
from forensic.store import DataStore, get_store


class Investigator:
    def __init__(self, store: DataStore) -> None:
        self.store = store
        self.orchestrator = Orchestrator(store)
        self.sql = SQLAnalyticsAgent(store)
        self.rag = RAGAgent(store)
        self.rca = ForecastRCAAgent()
        self.synthesis = SynthesisAgent()
        self._pool = ThreadPoolExecutor(max_workers=2)

    def investigate(self, question: str, product_id: Optional[str] = None, region: Optional[str] = None,
                    month: Optional[str] = None, use_llm: bool = True) -> dict:
        trace = []
        t0 = time.perf_counter()

        def timed(agent, fn, *args):
            start = time.perf_counter()
            result = fn(*args)
            return result, round((time.perf_counter() - start) * 1000, 1)

        plan, ms = timed(self.orchestrator, self.orchestrator.plan, question, product_id, region, month, use_llm)
        p = plan.to_dict()
        trace.append({"agent": self.orchestrator.name, "ms": ms,
                      "summary": f"product={p['product_id']}, region={p['region']}, month={p['month']}, "
                                 f"intent={p['intent']}"
                                 + ("; LLM filled missing fields" if any("LLM" in v for v in p["resolution"].values())
                                    else "")})

        # SQL and RAG agents are independent, so they fan out in parallel.
        sql_f = self._pool.submit(timed, self.sql, self.sql.run, plan.product_id, plan.region, plan.month)
        rag_f = self._pool.submit(timed, self.rag, self.rag.run, plan.question, plan.product_id, plan.region,
                                  plan.month)
        sql, sql_ms = sql_f.result()
        rag, rag_ms = rag_f.result()
        trace.append({"agent": self.sql.name, "ms": sql_ms, "parallel": True,
                      "summary": (f"{len(sql['queries'])} queries; units/day "
                                  f"{sql['target']['units_per_day_pct']:+.1f}% vs baseline, "
                                  f"{sql['stockout']['days']} stock-out day(s)") if sql["available"] else sql["reason"]})
        trace.append({"agent": self.rag.name, "ms": rag_ms, "parallel": True,
                      "summary": (f"{len(rag['results'])} document(s) passed the filters "
                                  f"({len(rag.get('incidents', []))} incident, {len(rag.get('routine', []))} routine); "
                                  f"{len(rag['excluded'])} near-miss(es) excluded") if rag["available"] else rag["reason"]})

        rca, ms = timed(self.rca, self.rca.run, sql)
        trace.append({"agent": self.rca.name, "ms": ms,
                      "summary": (f"anomaly={rca['is_anomaly']} (score {rca['anomaly_score']}), signature="
                                  f"{rca['signature'] or 'none'}, scope={rca['scope']}") if rca["available"] else rca["reason"]})

        answer, ms = timed(self.synthesis, self.synthesis.run, p, sql, rag, rca)
        trace.append({"agent": self.synthesis.name, "ms": ms,
                      "summary": f"case={answer['case']}, cause={answer['cause']['key']}, "
                                 f"confidence={answer['confidence']['label']} ({answer['confidence']['score']})"})

        return {"question": question, "plan": p, "answer": answer,
                "agents": {"sql": sql, "rag": rag, "rca": rca}, "trace": trace,
                "total_ms": round((time.perf_counter() - t0) * 1000, 1)}


@lru_cache(maxsize=4)
def get_investigator(dataset: str = "synthetic") -> Investigator:
    return Investigator(get_store(dataset))
