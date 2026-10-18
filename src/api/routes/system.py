"""Health and system-status endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends

from src.api.deps import get_services
from src.config import CLEAN_CSV, RAW_CSV, ROOT
from src.services import Services

router = APIRouter(tags=["system"])
APP_VERSION = "3.0.0"


@router.get("/health")
@router.get("/api/v1/health")
def health() -> dict[str, Any]:
    """Liveness only: the process is up. Use /api/v1/system/status for dependencies."""
    return {"status": "ok", "service": "retailiq-api", "version": APP_VERSION}


def _rel(path) -> str:
    return path.relative_to(ROOT).as_posix()


def build_status(services: Services) -> dict[str, Any]:
    db = services.db.status()
    model = services.model.health()
    kb = services.kb.status()
    llm = services.llm.status()
    datasets = {
        "raw_csv": {"path": _rel(RAW_CSV), "exists": RAW_CSV.exists()},
        "processed_csv": {"path": _rel(CLEAN_CSV), "exists": CLEAN_CSV.exists()},
    }

    steps: list[dict[str, str]] = []
    if not db["configured"]:
        steps.append({"component": "database", "required": "yes",
                      "action": "Set DATABASE_URL in .env (see .env.example), then run: python scripts/setup_database.py --create-database"})
    elif not db["connected"]:
        steps.append({"component": "database", "required": "yes",
                      "action": "PostgreSQL is not reachable. Start your PostgreSQL service, or for a local dev database run: python scripts/dev_postgres.py start"})
    elif not db["schema_ready"]:
        steps.append({"component": "database", "required": "yes", "action": "Create the schema: python scripts/setup_database.py"})
    elif not db["fact_rows"]:
        steps.append({"component": "etl", "required": "yes", "action": "Load the data: python scripts/run_etl.py"})
    if not model["ready"]:
        steps.append({"component": "model", "required": "yes", "action": "Train the model: python scripts/train_model.py"})
    if kb["state"] == "not_indexed":
        steps.append({"component": "vector_store", "required": "yes", "action": "Index the documents: python scripts/index_rag.py"})
    elif kb["state"] == "degraded":
        steps.append({"component": "vector_store", "required": "no",
                      "action": "Semantic search is unavailable (keyword fallback in use). " + (kb.get("embedder_status") or "")})
    if not llm["available"]:
        steps.append({"component": "llm", "required": "no",
                      "action": "The app works without it (built-in question patterns and extractive answers). To enable it: "
                      + (llm.get("hint") or llm.get("error") or "set LLM_PROVIDER=ollama in .env")})

    db_ready = bool(db["connected"] and db["schema_ready"] and db["fact_rows"])
    core_ready = db_ready and model["ready"] and kb["state"] in ("ready", "degraded")
    overall = "ready" if core_ready and kb["state"] == "ready" else ("degraded" if core_ready else "setup_required")
    return {
        "overall": overall,
        "backend": {"available": True, "version": APP_VERSION, "environment": services.settings.app_env,
                    "time": datetime.now(timezone.utc).isoformat(timespec="seconds")},
        "database": db,
        "model": model,
        "vector_store": kb,
        "llm": llm,
        "datasets": datasets,
        "setup_steps": steps,
    }


@router.get("/api/v1/system/status")
def system_status(services: Services = Depends(get_services)) -> dict[str, Any]:
    """Accurate readiness of every dependency, with the exact command to fix anything missing."""
    return build_status(services)
