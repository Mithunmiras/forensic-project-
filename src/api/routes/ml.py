"""Sales-prediction endpoints."""
from __future__ import annotations

import threading
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_services, require_admin
from src.api.schemas import PredictionRequest, PredictionResponse, RetrainRequest
from src.ml.service import InvalidPrediction
from src.services import Services

router = APIRouter(prefix="/api/v1/ml", tags=["ml"])
legacy_router = APIRouter(tags=["ml"])
_retrain_lock = threading.Lock()


@router.get("/health")
def ml_health(services: Services = Depends(get_services)) -> dict[str, Any]:
    """Whether a trained model is loaded."""
    return services.model.health()


@router.get("/metadata")
def ml_metadata(services: Services = Depends(get_services)) -> dict[str, Any]:
    """Target definition, split, per-variant metrics, feature importance, limitations."""
    return services.model.metadata()


@router.get("/schema")
def ml_schema(services: Services = Depends(get_services)) -> dict[str, Any]:
    """The exact inputs the model accepts (drives the dynamic prediction form)."""
    services.model.metadata()  # raises ModelNotReady -> 503 when absent
    return services.model.input_schema()


def _predict(body: PredictionRequest, services: Services) -> dict[str, Any]:
    data = body.model_dump()
    if data["order_date"] is not None:
        data["order_date"] = data["order_date"].isoformat()
    try:
        return services.model.predict(data)
    except InvalidPrediction as exc:
        raise HTTPException(status_code=422, detail={"message": "Invalid prediction input.", "fields": exc.errors}) from exc


@router.post("/predict", response_model=PredictionResponse)
def predict(body: PredictionRequest, services: Services = Depends(get_services)) -> dict[str, Any]:
    """Estimate the sales value of one order line (with an 80% prediction interval)."""
    return _predict(body, services)


@legacy_router.post("/predict", response_model=PredictionResponse, deprecated=True)
def predict_legacy(body: PredictionRequest, services: Services = Depends(get_services)) -> dict[str, Any]:
    """Backward-compatible alias of POST /api/v1/ml/predict."""
    return _predict(body, services)


@router.post("/retrain", dependencies=[Depends(require_admin)])
def retrain(body: RetrainRequest, services: Services = Depends(get_services)) -> dict[str, Any]:
    """Retrain from the chosen source (admin only; ~30 s). Requires the X-Admin-Token header."""
    if not _retrain_lock.acquire(blocking=False):
        raise HTTPException(409, "A retraining run is already in progress.")
    try:
        meta = services.model.retrain(source=body.source)
    finally:
        _retrain_lock.release()
    return {"status": "retrained", "trained_at": meta["trained_at"],
            "variants": {n: v["best_model"] for n, v in meta["variants"].items()}}
