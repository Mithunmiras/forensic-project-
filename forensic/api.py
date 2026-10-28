"""FastAPI server: JSON API under /api and the built React dashboard at /."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from forensic.agents.rag_agent import classify
from forensic.catalog import CAUSES, PRODUCTS, REGIONS
from forensic.config import UI_DIST
from forensic.metrics import monthly_metrics
from forensic.pipeline import get_investigator
from forensic.scenarios import CONTROLS, SCENARIOS
from forensic.store import get_store

@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_investigator()  # loads data, builds the vector index, imports statsmodels
    yield


app = FastAPI(title="RetailIQ Forensic", version="1.0.0", lifespan=lifespan,
              description="Multi-agent forensic analytics for retail root-cause investigation")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])

_evaluation_cache: dict = {}


class InvestigateRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
    product_id: Optional[str] = None
    region: Optional[str] = None
    month: Optional[str] = None


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/meta")
def meta():
    store = get_store()
    examples = [{"id": s["id"], "question": s["question"], "case": s["expected"]["case"]} for s in SCENARIOS + CONTROLS]
    return {
        "products": [{"product_id": p["product_id"], "product_name": p["product_name"], "category": p["category"],
                      "has_sales": store.has_sales(p["product_id"]), "has_documents": store.has_documents(p["product_id"])}
                     for p in PRODUCTS],
        "regions": REGIONS,
        "months": store.months,
        "causes": {k: v["label"] for k, v in CAUSES.items()},
        "examples": examples,
        "stats": {
            "sales_rows": int(len(store.sales)),
            "documents": len(store.documents),
            "incident_documents": sum(1 for d in store.documents if classify(d)["role"] == "incident"),
            "scenarios": len(SCENARIOS), "controls": len(CONTROLS),
        },
    }


@app.post("/api/investigate")
def investigate(req: InvestigateRequest):
    return get_investigator().investigate(req.question, req.product_id or None, req.region or None, req.month or None)


@app.get("/api/scan")
def scan():
    df = monthly_metrics(get_store())
    cells = [{
        "product_id": r["product_id"], "region": r["region"], "month": r["month"],
        "units_per_day": round(r["units_per_day"], 1), "units_pct": round(r["units_per_day_pct"], 2),
        "returns_pct": round(r["returns_rate_pct"], 1), "stockout_days": int(r["stockout_days"]),
        "anomaly_score": r["anomaly_score"], "is_anomaly": bool(r["is_anomaly"]), "signals": r["signals"],
    } for _, r in df.iterrows()]
    return {"cells": cells}


@app.get("/api/documents")
def documents():
    store = get_store()
    return {"documents": [{
        "path": d.path, "filename": d.filename, "product_id": d.product_id, "doc_type": d.doc_type, "date": d.date,
        "region": d.region, "title": d.title, "author": d.author, **classify(d),
    } for d in store.documents]}


@app.get("/api/documents/{product_id}/{filename}")
def document(product_id: str, filename: str):
    for d in get_store().documents:
        if d.path == f"{product_id}/{filename}":
            return {"path": d.path, "title": d.title, "text": d.text, **classify(d)}
    raise HTTPException(404, "Document not found")


@app.get("/api/evaluation")
def evaluation(refresh: bool = False):
    from forensic.evaluate import evaluate
    if refresh or "result" not in _evaluation_cache:
        _evaluation_cache["result"] = evaluate()
    return _evaluation_cache["result"]


@app.get("/api/tables/{name}")
def table(name: str, product_id: Optional[str] = None, limit: int = 20):
    if name not in ("products", "sales", "inventory", "suppliers"):
        raise HTTPException(404, "Unknown table")
    store = get_store()
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
