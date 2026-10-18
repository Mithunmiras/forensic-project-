"""FastAPI dependencies."""
from __future__ import annotations

import secrets
from datetime import date

from fastapi import Depends, Header, HTTPException, Query, Request

from src.analytics.repository import Filters
from src.services import Services


def get_services(request: Request) -> Services:
    return request.app.state.services


def require_admin(
    services: Services = Depends(get_services),
    x_admin_token: str | None = Header(default=None),
) -> None:
    """Protect administrative actions (re-indexing, retraining) with ADMIN_TOKEN."""
    expected = services.settings.admin_token
    if not expected:
        raise HTTPException(
            status_code=403,
            detail="Administrative actions are disabled. Set ADMIN_TOKEN in .env to enable them.",
        )
    if not x_admin_token or not secrets.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=401, detail="Missing or invalid X-Admin-Token header.")


def get_filters(
    services: Services = Depends(get_services),
    date_from: date | None = Query(None, description="Inclusive start date (YYYY-MM-DD)"),
    date_to: date | None = Query(None, description="Inclusive end date (YYYY-MM-DD)"),
    category: str | None = Query(None, max_length=50),
    region: str | None = Query(None, max_length=50),
    market: str | None = Query(None, max_length=50),
) -> Filters:
    """Validated dashboard filters (values are checked against the data)."""
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "date_from must be on or before date_to.")
    options = services.repo.filter_options()  # raises DatabaseUnavailable -> 503 handler
    for name, value, allowed in (
        ("category", category, options["categories"]),
        ("region", region, options["regions"]),
        ("market", market, options["markets"]),
    ):
        if value and value not in allowed:
            raise HTTPException(422, f"Unknown {name} '{value}'. Expected one of: {', '.join(allowed)}")
    return Filters(date_from, date_to, category, region, market)
