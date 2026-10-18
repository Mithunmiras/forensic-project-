"""RetailIQ FastAPI application.

    uvicorn src.api.main:app --reload        # or: python main.py serve

The server starts even if PostgreSQL, the trained model, the vector index or the
LLM are missing; each reports its own readiness through /api/v1/system/status and
the features that depend on it answer with a clear 503 until it is set up.
"""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.api.routes import agent, analytics, ml, rag, system
from src.config import FRONTEND_DIST, Settings, get_settings
from src.db.session import DatabaseNotConfigured, DatabaseUnavailable, safe_error
from src.logging_setup import configure_logging
from src.ml.service import ModelNotReady
from src.services import Services, build_services

log = logging.getLogger("retailiq.api")

DB_HINT = "Check /api/v1/system/status for the exact setup step (python scripts/setup_database.py, then python scripts/run_etl.py)."


def _error(status: int, code: str, message: str, *, hint: str | None = None, fields: dict | None = None) -> JSONResponse:
    body: dict = {"code": code, "message": message}
    if hint:
        body["hint"] = hint
    if fields:
        body["fields"] = fields
    return JSONResponse(status_code=status, content={"error": body})


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        svc = services or build_services(settings)
        svc.startup()
        app.state.services = svc
        log.info("RetailIQ API started (model ready: %s)", svc.model.ready)
        yield
        svc.shutdown()

    app = FastAPI(
        title="RetailIQ API",
        description="Hybrid SQL-RAG multi-agent decision intelligence for retail analytics.",
        version=system.APP_VERSION,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Admin-Token"],
    )

    @app.middleware("http")
    async def request_log(request: Request, call_next):
        started = time.perf_counter()
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        log.info("%s %s -> %d (%.0f ms) rid=%s", request.method, request.url.path, response.status_code,
                 (time.perf_counter() - started) * 1000, rid)
        return response

    # ---- consistent error shape ---------------------------------------
    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        fields = {".".join(str(p) for p in e["loc"] if p not in ("body", "query")): e["msg"] for e in exc.errors()}
        return _error(422, "validation_error", "The request is invalid.", fields=fields)

    @app.exception_handler(StarletteHTTPException)  # also covers FastAPI's HTTPException and router 404s
    async def http_error(_: Request, exc: StarletteHTTPException):
        if isinstance(exc.detail, dict):
            return _error(exc.status_code, "invalid_input", exc.detail.get("message", "Invalid input."), fields=exc.detail.get("fields"))
        return _error(exc.status_code, f"http_{exc.status_code}", str(exc.detail))

    @app.exception_handler(DatabaseNotConfigured)
    async def db_not_configured(_: Request, exc: DatabaseNotConfigured):
        return _error(503, "database_not_configured", str(exc), hint=DB_HINT)

    @app.exception_handler(DatabaseUnavailable)
    async def db_unavailable(_: Request, exc: DatabaseUnavailable):
        return _error(503, "database_unavailable", f"The database could not be queried: {safe_error(exc)}", hint=DB_HINT)

    @app.exception_handler(ModelNotReady)
    async def model_not_ready(_: Request, exc: ModelNotReady):
        return _error(503, "model_not_ready", str(exc), hint="Train the model: python scripts/train_model.py")

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        return _error(500, "internal_error", "An unexpected error occurred.")

    # ---- routes --------------------------------------------------------
    for router in (system.router, analytics.router, ml.router, ml.legacy_router, rag.router, agent.router):
        app.include_router(router)

    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve the built React app (frontend/dist) when present."""
    if not (FRONTEND_DIST / "index.html").exists():
        @app.get("/", include_in_schema=False)
        def root():
            return {
                "name": "RetailIQ API", "docs": "/docs", "status": "/api/v1/system/status",
                "frontend": "not built - run `npm run build` in frontend/ or start the dev server (npm run dev).",
            }
        return

    if (FRONTEND_DIST / "assets").exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    reserved = ("api/", "docs", "redoc", "openapi.json", "health")  # POST /predict (legacy API) is a different method, so GET /predict is the UI page

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith(reserved):
            raise HTTPException(404, "Not found.")
        candidate = (FRONTEND_DIST / path).resolve()
        if path and candidate.is_file() and FRONTEND_DIST.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")


app = create_app()
