"""Multi-agent chat endpoint."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from src.api.deps import get_services
from src.api.schemas import ChatRequest, ChatResponse
from src.services import Services

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, services: Services = Depends(get_services)) -> dict[str, Any]:
    """Route a question to SQL analytics, the ML model and/or the knowledge base and combine the evidence."""
    return services.orchestrator.chat(body.message)
