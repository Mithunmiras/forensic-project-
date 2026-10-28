"""RAG agent - retrieves the "why" from unstructured documents.

Documents are chunked by paragraph and embedded as TF-IDF vectors (word 1-2 grams) in an
in-memory numpy vector index (forensic/textindex.py) - local, free and deterministic. A sentence-transformer + Chroma/FAISS
would slot in behind the same `_similarity` call.

Retrieval is metadata-first: a chunk must match the product, the region (or be company-wide)
and fall in the date window before semantic similarity is even considered - a generic policy
document can be semantically close without being relevant. Near misses that were filtered out
are reported, so the user can see what was ignored and why.

Each document is also classified: "incident" (describes a cause from the taxonomy), "routine"
(status report saying nothing unusual - useful to rule causes out) or "reference" (standing
policy text).
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Optional

import numpy as np

from forensic.catalog import CAUSES
from forensic.store import DataStore, Document
from forensic.textindex import TfidfIndex

CAUSE_LEXICON = {
    "supplier_delay": ["shipment", "delayed", "delay", "port congestion", "component shortage", "shortage",
                       "backlog", "sub-supplier"],
    "logistics_disruption": ["strike", "trucking", "flood", "warehouse is closed", "road transport",
                             "inbound transport", "carrier", "deliveries", "late deliveries", "delivery delay",
                             "not received"],
    "quality_issue": ["defect", "faulty", "fault", "failure rate", "qc", "quality control", "recall", "quarantine",
                      "damaged item", "wrong item"],
    "promotion": ["discount", "promotion", "promotional", "markdown", "clearance", "black friday"],
    "competitor_launch": ["competitor", "rival", "launched", "switching", "market share"],
    "marketing_campaign": ["campaign", "holiday", "gifting", "advertising", "demand surge"],
    "price_increase": ["price increase", "price revision", "levy", "tariff", "price-sensitive"],
    "return_policy_change": ["return window", "extended from", "full refund", "no questions asked"],
}
ROUTINE_PHRASES = ["within normal", "no anomalies", "no action required", "no significant", "proceeding as planned",
                   "on schedule", "remained stable", "in line with"]
REFERENCE_TYPES = {"policy"}
# Which routine document types can rule out which cause families.
ROUTINE_RULES_OUT = {"quality_summary": "quality_issue", "supplier_status": "supplier_delay",
                     "customer_feedback": "competitor_launch"}

QUERY_EXPANSION = ("shipment delay shortage stock strike transport defect faulty returns discount promotion "
                   "competitor launched price increase campaign return window late deliveries not received")


def _hits(text: str, terms) -> list:
    tl = text.lower()
    return [t for t in terms if re.search(rf"(?<![a-z]){re.escape(t)}", tl)]


def classify(doc: Document) -> dict:
    body = " ".join(doc.paragraphs) + " " + doc.title
    scores = {cause: _hits(body, terms) for cause, terms in CAUSE_LEXICON.items()}
    best = max(scores, key=lambda c: len(scores[c]))
    routine = _hits(body, ROUTINE_PHRASES)
    if doc.doc_type in REFERENCE_TYPES:
        return {"role": "reference", "cause": None, "matched_terms": [], "routine_phrases": routine}
    if routine and len(scores[best]) < 3:
        return {"role": "routine", "cause": None, "matched_terms": scores[best], "routine_phrases": routine}
    if len(scores[best]) >= 2:
        return {"role": "incident", "cause": best, "matched_terms": scores[best], "routine_phrases": routine}
    return {"role": "routine", "cause": None, "matched_terms": scores[best], "routine_phrases": routine}


def _month_window(month: str, lookback_days: int):
    start = date.fromisoformat(f"{month}-01")
    nxt = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    return start - timedelta(days=lookback_days), nxt - timedelta(days=1), start


def best_sentence(text: str, cause: Optional[str]) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    if not cause:
        return sentences[0]
    return max(sentences, key=lambda s: len(_hits(s, CAUSE_LEXICON[cause])))


class RAGAgent:
    name = "RAG Agent"

    def __init__(self, store: DataStore) -> None:
        self.store = store
        self.chunks = []  # (doc, paragraph_index, text)
        for d in store.documents:
            for i, p in enumerate(d.paragraphs):
                self.chunks.append((d, i, p))
        self.index = TfidfIndex([f"{d.title}. {t}" for d, _, t in self.chunks])
        self.classes = {d.path: classify(d) for d in store.documents}

    def _similarity(self, query: str) -> np.ndarray:
        return self.index.similarity(query)

    def run(self, question: str, product_id: Optional[str], region: Optional[str], month: Optional[str],
            top_k: int = 5) -> dict:
        out = {"agent": self.name, "available": False, "reason": "", "index": {
            "method": "TF-IDF (1-2 gram) cosine similarity + metadata filter", "chunks": len(self.chunks),
            "documents": len(self.store.documents)}, "results": [], "excluded": [], "corpus_for_product": 0}
        if not product_id:
            out["reason"] = "No product identified."
            return out
        product_docs = [d for d in self.store.documents if d.product_id == product_id]
        out["corpus_for_product"] = len(product_docs)
        if not product_docs:
            out["reason"] = f"No unstructured documents exist for {product_id}."
            return out
        out["available"] = True

        sims = self._similarity(f"{question} {QUERY_EXPANSION}")
        window = (_month_window(month, self.store.dataset.doc_lookback_days)
                  if month and not month.startswith("?") else None)
        if window:
            out["window"] = {"from": window[0].isoformat(), "to": window[1].isoformat()}
        per_doc, excluded = {}, {}
        for (doc, idx, text), sim in zip(self.chunks, sims):
            reason = self._filter_reason(doc, product_id, region, window)
            if reason:
                if doc.product_id == product_id or sim > 0.15:
                    prev = excluded.get(doc.path)
                    if prev is None or sim > prev["similarity"]:
                        excluded[doc.path] = {"path": doc.path, "title": doc.title, "similarity": round(float(sim), 3),
                                              "reason": reason}
                continue
            meta = self._metadata_score(doc, region, window)
            score = 0.5 * float(sim) + 0.5 * meta
            current = per_doc.get(doc.path)
            if current is None or score > current["score"]:
                per_doc[doc.path] = {"doc": doc, "score": score, "similarity": float(sim), "metadata_score": meta,
                                     "chunk_index": idx, "chunk": text}
        ranked = sorted(per_doc.values(), key=lambda r: r["score"], reverse=True)[:top_k]
        for r in ranked:
            doc, cls = r["doc"], self.classes[r["doc"].path]
            text = " ".join(doc.paragraphs)
            out["results"].append({
                "path": doc.path, "filename": doc.filename, "title": doc.title, "doc_type": doc.doc_type,
                "date": doc.date, "region": doc.region, "author": doc.author,
                "score": round(r["score"], 3), "similarity": round(r["similarity"], 3),
                "metadata_score": round(r["metadata_score"], 3),
                "role": cls["role"], "cause": cls["cause"],
                "cause_label": CAUSES[cls["cause"]]["label"] if cls["cause"] else None,
                "matched_terms": cls["matched_terms"], "routine_phrases": cls["routine_phrases"],
                "chunk": r["chunk"],
                "quote": best_sentence(text, cls["cause"]) if cls["role"] == "incident" else best_sentence(r["chunk"], None),
            })
        out["excluded"] = sorted(excluded.values(), key=lambda e: e["similarity"], reverse=True)[:6]
        out["incidents"] = [r for r in out["results"] if r["role"] == "incident"]
        out["routine"] = [r for r in out["results"] if r["role"] == "routine"]
        if not out["results"]:
            out["reason"] = "No document for this product matches the region and period."
        return out

    @staticmethod
    def _filter_reason(doc: Document, product_id, region, window) -> Optional[str]:
        if doc.product_id != product_id:
            return f"different product ({doc.product_id})"
        if region and doc.region not in (region, "ALL"):
            return f"different region ({doc.region})"
        if window:
            d = date.fromisoformat(doc.date)
            if d < window[0] or d > window[1]:
                return f"outside the period ({doc.date})"
        return None

    @staticmethod
    def _metadata_score(doc: Document, region, window) -> float:
        region_score = 1.0 if region and doc.region == region else 0.5
        if not window:
            return region_score
        d = date.fromisoformat(doc.date)
        days_from_start = abs((d - window[2]).days)
        date_score = max(0.0, 1 - days_from_start / 45)
        return 0.5 * region_score + 0.5 * date_score
