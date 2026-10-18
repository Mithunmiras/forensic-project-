"""Analytics endpoints - every figure is an SQL aggregation in PostgreSQL."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query

from src.analytics.repository import DIMENSIONS, Filters
from src.api.deps import get_filters, get_services
from src.api.schemas import QueryRequest, QueryResponse
from src.services import Services

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/filters")
def filters(services: Services = Depends(get_services)) -> dict[str, Any]:
    """Valid filter values and the data's date range."""
    return services.repo.filter_options()


@router.get("/summary")
def summary(
    compare: bool = Query(False, description="Also compare with the previous period of equal length"),
    f: Filters = Depends(get_filters),
    services: Services = Depends(get_services),
) -> dict[str, Any]:
    """Headline KPIs: sales, profit, orders, average discount, margin ..."""
    return services.repo.summary(f, compare=compare)


@router.get("/dashboard")
def dashboard(
    grain: Literal["month", "quarter", "year"] = "month",
    f: Filters = Depends(get_filters),
    services: Services = Depends(get_services),
) -> dict[str, Any]:
    """Everything the overview page needs in one call."""
    return services.repo.dashboard(f, grain=grain)


@router.get("/sales-trend")
def sales_trend(
    grain: Literal["month", "quarter", "year"] = "month",
    f: Filters = Depends(get_filters),
    services: Services = Depends(get_services),
) -> dict[str, Any]:
    return {"grain": grain, "points": services.repo.trend(f, grain)}


@router.get("/top-products")
def top_products(
    n: int = Query(10, ge=1, le=50),
    by: Literal["sales", "profit"] = "sales",
    f: Filters = Depends(get_filters),
    services: Services = Depends(get_services),
) -> dict[str, Any]:
    return {"by": by, "products": services.repo.top_products(f, n, by)}


@router.get("/by/{dimension}")
def by_dimension(
    dimension: Literal[tuple(sorted(DIMENSIONS))],  # type: ignore[valid-type]
    limit: int | None = Query(None, ge=1, le=100),
    order_by: Literal["sales", "profit", "orders"] = "sales",
    f: Filters = Depends(get_filters),
    services: Services = Depends(get_services),
) -> dict[str, Any]:
    return {"dimension": dimension, "rows": services.repo.by_dimension(dimension, f, limit=limit, order_by=order_by)}


@router.post("/query", response_model=QueryResponse)
def query(body: QueryRequest, services: Services = Depends(get_services)) -> dict[str, Any]:
    """Answer a natural-language question with a validated, read-only SQL query."""
    return services.sql_agent.answer(body.question).as_dict()
