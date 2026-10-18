"""Shared fixtures.

* ``pg_url``      - a real PostgreSQL: ``RETAILIQ_TEST_DATABASE_URL`` if set, otherwise an
                    embedded PostgreSQL 16 (pip package ``pgserver``). Integration tests are
                    *skipped with a reason* (never reported as passed) if neither is available.
* ``loaded_db``   - schema applied + the real dataset loaded by the real ETL (once per session).
* ``trained_model`` - a model trained once per session into a temporary directory.
"""
from __future__ import annotations

import logging
import os
import warnings
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from src.config import Settings, normalize_db_url
from src.db.admin import apply_schema, create_readonly_role
from src.etl.pipeline import run_etl

warnings.filterwarnings("ignore")
logging.raiseExceptions = False  # pgserver logs from an atexit hook after pytest closed its streams
READONLY_ROLE, READONLY_PW = "retailiq_readonly", "test-readonly-pw"


@pytest.fixture(scope="session")
def pg_url(tmp_path_factory) -> str:
    explicit = os.environ.get("RETAILIQ_TEST_DATABASE_URL")
    if explicit:
        yield normalize_db_url(explicit)
        return
    try:
        import pgserver
    except ImportError:
        pytest.skip("No PostgreSQL available: set RETAILIQ_TEST_DATABASE_URL or `pip install pgserver`.")
    data_dir = tmp_path_factory.mktemp("pgdata")
    try:
        server = pgserver.get_server(data_dir, cleanup_mode="stop")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Embedded PostgreSQL could not start: {exc.__class__.__name__}: {exc}")
    yield normalize_db_url(server.get_uri())
    server.cleanup()


@pytest.fixture(scope="session")
def readonly_url(pg_url: str) -> str:
    return make_url(pg_url).set(username=READONLY_ROLE, password=READONLY_PW).render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def loaded_db(pg_url: str, readonly_url: str):
    """Real schema + real data, loaded with the production ETL."""
    engine = create_engine(pg_url)
    apply_schema(engine)
    summary = run_etl(engine, source="raw", write_report=False)
    create_readonly_role(engine, READONLY_ROLE, READONLY_PW)
    yield {"engine": engine, "summary": summary, "url": pg_url, "readonly_url": readonly_url}
    engine.dispose()


@pytest.fixture(scope="session")
def trained_model(tmp_path_factory):
    """Train once (about 30 s) into a temp dir; returns the Settings pointing at it."""
    from src.ml.train import train

    root = tmp_path_factory.mktemp("model")
    settings = Settings(model_path=root / "sales_model.joblib", metrics_path=root / "metrics.json", _env_file=None)
    train(source="csv", verbose=False, settings=settings, write_report=False)
    return settings


@pytest.fixture
def make_settings(tmp_path, loaded_db, trained_model):
    def _make(**overrides) -> Settings:
        base = dict(
            database_url=loaded_db["url"],
            database_readonly_url=loaded_db["readonly_url"],
            model_path=trained_model.model_path,
            metrics_path=trained_model.metrics_path,
            vector_store_path=tmp_path / "vs",
            llm_provider="none",
            embedding_provider="lexical",
            admin_token="test-token",
            frontend_origin="http://localhost:5173",
            query_timeout_ms=5000,
            _env_file=None,
        )
        base.update(overrides)
        return Settings(**base)

    return _make


@pytest.fixture
def order() -> dict:
    return {"category": "Technology", "sub_category": "Phones", "market": "US", "quantity": 3, "discount": 0.1}
