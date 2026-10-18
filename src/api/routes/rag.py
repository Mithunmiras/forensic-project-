"""Knowledge-base endpoints."""
from __future__ import annotations

import threading
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_services, require_admin
from src.api.schemas import AskRequest, IndexRequest
from src.services import Services

router = APIRouter(prefix="/api/v1/rag", tags=["rag"])
_index_lock = threading.Lock()


@router.get("/status")
def status(services: Services = Depends(get_services)) -> dict[str, Any]:
    """Index state, retrieval mode (semantic vs keyword fallback) and whether answers use an LLM."""
    return services.kb.status()


@router.post("/ask")
def ask(body: AskRequest, services: Services = Depends(get_services)) -> dict[str, Any]:
    """Answer a question from the project documentation, with cited sources."""
    return services.kb.ask(body.question, body.top_k)


@router.post("/index", dependencies=[Depends(require_admin)])
def index(body: IndexRequest, services: Services = Depends(get_services)) -> dict[str, Any]:
    """(Re)build the vector index (admin only). Requires the X-Admin-Token header."""
    if not _index_lock.acquire(blocking=False):
        raise HTTPException(409, "Indexing is already in progress.")
    try:
        return services.kb.index(force=body.force)
    finally:
        _index_lock.release()
