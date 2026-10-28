"""FastAPI server: JSON API under /api and the built React dashboard at /.

Every data endpoint takes a `dataset` (query parameter, or a field in the POST body):
"synthetic" (default, with ground truth) or "olist" (real data).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from forensic import llm
from forensic.agents.rag_agent import classify
from forensic.catalog import CAUSES
from forensic.config import UI_DIST
from forensic.datasets import DATASETS, DEFAULT, get_dataset
from forensic.metrics import monthly_metrics
from forensic.pipeline import get_investigator
from forensic.scenarios import CONTROLS, SCENARIOS
from forensic.store import get_store


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_investigator(DEFAULT)  # loads data and builds the vector index
    yield


app = FastAPI(title="RetailIQ Forensic", version="1.1.0", lifespan=lifespan,
              description="Multi-agent forensic analytics for retail root-cause investigation")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])

_evaluation_cache: dict = {}


class InvestigateRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
    product_id: Optional[str] = None
    region: Optional[str] = None
    month: Optional[str] = None
    dataset: str = DEFAULT


def _store(dataset: str):
    try:
        ds = get_dataset(dataset)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    if not ds.is_available():
        raise HTTPException(404, f"Dataset {dataset!r} has not been imported")
    return get_store(dataset)


@lru_cache(maxsize=4)
def _real_examples(dataset: str) -> tuple:
    """For data without an answer key: questions about the strongest real anomalies, plus quiet months."""
    store = get_store(dataset)
    df = monthly_metrics(store)
    names = {p["product_id"]: p["product_name"] for p in store.products}
    # Prefer well-populated cells: a story about 2 items a day convinces nobody.
    picks = df[df["is_anomaly"]].assign(big=lambda d: d["units"] >= 150).sort_values(
        ["big", "anomaly_score"], ascending=False)
    seen, chosen = set(), []
    for r in picks.itertuples():
        key = (r.month, r.product_id, tuple(r.signals))
        if key in seen:
            continue
        seen.add(key)
        chosen.append(r)
        if len(chosen) == 10:
            break
    quiet = df[(~df["is_anomaly"]) & (df["units"] >= 300)].sort_values("anomaly_score").head(2)
    inv = get_investigator(dataset)
    rows = []
    for r in list(chosen) + list(quiet.itertuples()):
        verb = "drop" if r.units_per_day_pct < 0 else "change"
        question = f"Why did {names[r.product_id]} sales {verb} in the {r.region} region in {r.month}?"
        case = inv.investigate(question, r.product_id, r.region, r.month, use_llm=False)["answer"]["case"]
        rows.append({"question": question, "case": case, "product_id": r.product_id, "region": r.region,
                     "month": r.month})
    order = {"full": 0, "unstructured_only": 1, "structured_only": 2, "conflict": 3, "none": 4}
    rows.sort(key=lambda x: order.get(x["case"], 5))
    return tuple(dict(x, id=f"R{i + 1:02d}") for i, x in enumerate(rows))


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/datasets")
def datasets():
    return {"datasets": [d.public() for d in DATASETS.values()], "default": DEFAULT}


@app.get("/api/meta")
def meta(dataset: str = DEFAULT):
    store = _store(dataset)
    ds = store.dataset
    if ds.has_ground_truth:
        examples = [{"id": s["id"], "question": s["question"], "case": s["expected"]["case"]}
                    for s in SCENARIOS + CONTROLS]
    else:
        examples = list(_real_examples(dataset))
    return {
        "dataset": ds.public(),
        "datasets": [d.public() for d in DATASETS.values()],
        "products": [{"product_id": p["product_id"], "product_name": p["product_name"],
                      "category": store.catalog[p["product_id"]].get("category", ""),
                      "has_sales": store.has_sales(p["product_id"]), "has_documents": store.has_documents(p["product_id"])}
                     for p in store.products],
        "regions": list(ds.regions),
        "months": store.months,
        "causes": {k: v["label"] for k, v in CAUSES.items()},
        "examples": examples,
        "llm": {"enabled": llm.enabled(), "model": llm.model_name() if llm.enabled() else None},
        "stats": {
            "sales_rows": int(len(store.sales)),
            "documents": len(store.documents),
            "incident_documents": sum(1 for d in store.documents if classify(d)["role"] == "incident"),
            "scenarios": len(SCENARIOS) if ds.has_ground_truth else 0,
            "controls": len(CONTROLS) if ds.has_ground_truth else 0,
        },
    }


@app.post("/api/investigate")
def investigate(req: InvestigateRequest):
    _store(req.dataset)
    return get_investigator(req.dataset).investigate(req.question, req.product_id or None, req.region or None,
                                                     req.month or None)


@app.post("/api/summary")
def summary(req: InvestigateRequest):
    """AI analyst briefing for an investigation. Separate from /api/investigate so the
    deterministic answer renders immediately and the LLM text arrives after it."""
    if not llm.enabled():
        return {"available": False, "reason": "No GROQ_API_KEY configured"}
    _store(req.dataset)
    res = get_investigator(req.dataset).investigate(req.question, req.product_id or None, req.region or None,
                                                    req.month or None)
    try:
        return {"available": True, **llm.summarize(req.question, res["answer"])}
    except llm.LLMUnavailable as e:
        return {"available": False, "reason": str(e)}


@app.get("/api/scan")
def scan(dataset: str = DEFAULT):
    df = monthly_metrics(_store(dataset))
    has_late = "late_rate" in df.columns
    cells = [{
        "product_id": r["product_id"], "region": r["region"], "month": r["month"],
        "units_per_day": round(r["units_per_day"], 1), "units_pct": round(r["units_per_day_pct"], 2),
        "returns_pct": round(r["returns_rate_pct"], 1), "stockout_days": int(r["stockout_days"]),
        "late_rate": round(float(r["late_rate"]), 1) if has_late else None,
        "anomaly_score": r["anomaly_score"], "is_anomaly": bool(r["is_anomaly"]), "signals": r["signals"],
    } for _, r in df.iterrows()]
    return {"cells": cells}


@app.get("/api/documents")
def documents(dataset: str = DEFAULT):
    return {"documents": [{
        "path": d.path, "filename": d.filename, "product_id": d.product_id, "doc_type": d.doc_type, "date": d.date,
        "region": d.region, "title": d.title, "author": d.author, **classify(d),
    } for d in _store(dataset).documents]}


@app.get("/api/documents/{product_id}/{filename}")
def document(product_id: str, filename: str, dataset: str = DEFAULT):
    for d in _store(dataset).documents:
        if d.path == f"{product_id}/{filename}":
            return {"path": d.path, "title": d.title, "text": d.text, **classify(d)}
    raise HTTPException(404, "Document not found")


@app.get("/api/evaluation")
def evaluation(refresh: bool = False, dataset: str = DEFAULT):
    if not get_dataset(dataset).has_ground_truth:
        return {"available": False,
                "reason": "Real data has no answer key: nobody recorded the true cause of each change, so accuracy "
                          "cannot be scored. The synthetic dataset is used for evaluation."}
    from forensic.evaluate import evaluate
    if refresh or "result" not in _evaluation_cache:
        _evaluation_cache["result"] = evaluate()
    return {"available": True, **_evaluation_cache["result"]}


@app.get("/api/tables/{name}")
def table(name: str, product_id: Optional[str] = None, limit: int = 20, dataset: str = DEFAULT):
    store = _store(dataset)
    allowed = {"products", "sales", "inventory", "suppliers"} if store.dataset.has_inventory else {"products", "sales"}
    if name not in allowed:
        raise HTTPException(404, "Unknown table")
    sql, params = f"SELECT * FROM {name}", ()
    if product_id and name in ("sales", "inventory", "products"):
        sql, params = sql + " WHERE product_id = ?", (product_id,)
    count = int(store.query(f"SELECT COUNT(*) AS n FROM ({sql})", params)["n"][0])
    rows = store.query(sql + f" LIMIT {max(1, min(limit, 200))}", params)
    return {"table": name, "total_rows": count, "columns": list(rows.columns), "rows": rows.to_dict(orient="records")}


# --- the React dashboard -----------------------------------------------------------------
if (UI_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=UI_DIST / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    target = UI_DIST / path
    if path and target.is_file() and UI_DIST in target.resolve().parents:
        return FileResponse(target)
    index = UI_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return HTMLResponse("<h1>RetailIQ Forensic API is running</h1><p>The dashboard has not been built yet. Run "
                        "<code>cd forensic_ui &amp;&amp; npm install &amp;&amp; npm run build</code>, then reload. "
                        "API docs: <a href='/docs'>/docs</a></p>")
