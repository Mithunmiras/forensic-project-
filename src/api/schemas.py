"""Request/response models (Pydantic v2)."""
from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorBody(BaseModel):
    code: str
    message: str
    hint: str | None = None
    fields: dict[str, str] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


# ----------------------------------------------------------------------------- ML
class PredictionRequest(BaseModel):
    """An order described before it is placed. Calendar features come from ``order_date``."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "category": "Technology",
                "sub_category": "Phones",
                "market": "US",
                "quantity": 3,
                "discount": 0.1,
                "segment": "Consumer",
                "ship_mode": "Standard Class",
                "order_priority": "Medium",
                "shipping_days": 5,
                "order_date": "2014-06-15",
            }
        },
    )

    category: str = Field(min_length=1, max_length=50)
    sub_category: str = Field(min_length=1, max_length=50)
    market: str = Field(min_length=1, max_length=50)
    quantity: int = Field(ge=1, le=1000, description="Units on the order line")
    discount: float = Field(ge=0, le=1, description="Fraction, e.g. 0.1 = 10%")
    segment: str | None = Field(None, max_length=50)
    ship_mode: str | None = Field(None, max_length=50)
    order_priority: str | None = Field(None, max_length=20)
    shipping_days: int | None = Field(None, ge=0, le=60)
    shipping_cost: float | None = Field(
        None, ge=0, le=100_000,
        description="Optional. If given, the more accurate model that uses shipping cost is used (it is a proxy of sales).",
    )
    order_date: date | None = None


class PredictionResponse(BaseModel):
    predicted_sales: float
    lower_bound: float
    upper_bound: float
    interval_nominal_coverage: float
    interval_empirical_coverage: float
    variant: str
    model: str
    test_metrics: dict[str, float]
    typical_sub_category_sales: float
    inputs_used: dict[str, Any]
    assumptions: list[str]
    warnings: list[str]
    disclaimer: str


# ----------------------------------------------------------------------------- analytics / SQL agent
class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=500)


class QueryResponse(BaseModel):
    question: str
    status: str
    method: str | None = None
    sql: str | None = None
    params: dict[str, Any] = {}
    explanation: str | None = None
    columns: list[dict[str, str]] = []
    rows: list[list[Any]] = []
    row_count: int = 0
    truncated: bool = False
    elapsed_ms: float | None = None
    chart: dict[str, str] | None = None
    notes: list[str] = []
    error: str | None = None
    supported_examples: list[str] = []


# ----------------------------------------------------------------------------- RAG
class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=500)
    top_k: int | None = Field(None, ge=1, le=10)


class IndexRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    force: bool = False


# ----------------------------------------------------------------------------- agent
class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=1000)


class ChatResponse(BaseModel):
    answer: str
    answer_mode: str
    route: dict[str, Any]
    tools: list[dict[str, Any]]
    evidence: dict[str, Any]
    warnings: list[str]
    elapsed_ms: float


class RetrainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str = Field("csv", pattern="^(csv|postgres)$")
