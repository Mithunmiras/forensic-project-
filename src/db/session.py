"""Database engines and connection health.

Two logical connections exist:

* **admin** (``DATABASE_URL``)   - privileged; used only for schema setup and the ETL.
* **readonly** (``DATABASE_READONLY_URL``) - used by the dashboard analytics and the
  natural-language SQL agent. It is forced read-only at the session level and has a
  statement timeout. If no read-only URL is configured the admin URL is reused, but
  the session is still read-only/time-limited and the status endpoint reports that
  no dedicated read-only role is in use.
"""
from __future__ import annotations

import logging
import threading
from typing import Any

from sqlalchemy import Engine, create_engine, text

from src.config import DB_SCHEMA, Settings, get_settings, redact_url
from src.logging_setup import redact

log = logging.getLogger("retailiq.db")


class DatabaseNotConfigured(RuntimeError):
    """No database URL has been configured."""


class DatabaseUnavailable(RuntimeError):
    """A database is configured but could not be reached / queried."""


def safe_error(exc: BaseException) -> str:
    """First line of an exception message with secrets removed."""
    message = str(exc).strip()
    first = message.splitlines()[0] if message else exc.__class__.__name__
    return redact(first)[:300]


class Database:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._admin: Engine | None = None
        self._readonly: Engine | None = None
        self._lock = threading.Lock()

    # ---- engines -------------------------------------------------------
    @property
    def configured(self) -> bool:
        return self.settings.effective_database_url is not None or self.settings.effective_readonly_url is not None

    @property
    def has_dedicated_readonly_url(self) -> bool:
        return self.settings.effective_readonly_url is not None

    def admin_engine(self) -> Engine:
        url = self.settings.effective_database_url
        if not url:
            raise DatabaseNotConfigured("DATABASE_URL is not configured.")
        with self._lock:
            if self._admin is None:
                self._admin = create_engine(
                    url,
                    pool_pre_ping=True,
                    connect_args={"connect_timeout": 5, "options": f"-c search_path={DB_SCHEMA},public"},
                )
            return self._admin

    def readonly_engine(self) -> Engine:
        url = self.settings.effective_readonly_url or self.settings.effective_database_url
        if not url:
            raise DatabaseNotConfigured("DATABASE_READONLY_URL / DATABASE_URL is not configured.")
        with self._lock:
            if self._readonly is None:
                options = (
                    f"-c search_path={DB_SCHEMA},public "
                    f"-c default_transaction_read_only=on "
                    f"-c statement_timeout={self.settings.query_timeout_ms}"
                )
                self._readonly = create_engine(
                    url,
                    pool_pre_ping=True,
                    pool_size=5,
                    max_overflow=5,
                    connect_args={"connect_timeout": 5, "options": options},
                )
            return self._readonly

    def dispose(self) -> None:
        for engine in (self._admin, self._readonly):
            if engine is not None:
                engine.dispose()
        self._admin = self._readonly = None

    # ---- health --------------------------------------------------------
    def status(self) -> dict[str, Any]:
        """Accurate, non-throwing description of database readiness."""
        info: dict[str, Any] = {
            "configured": self.configured,
            "connected": False,
            "schema_ready": False,
            "readonly_role": False,
            "server_version": None,
            "fact_rows": None,
            "last_etl_run": None,
            "url": redact_url(self.settings.effective_readonly_url or self.settings.effective_database_url),
            "error": None,
        }
        if not self.configured:
            info["error"] = "No database URL configured (set DATABASE_URL in .env)."
            return info
        try:
            with self.readonly_engine().connect() as conn:
                info["connected"] = True
                info["server_version"] = conn.execute(text("SHOW server_version")).scalar()
                info["schema_ready"] = bool(
                    conn.execute(text("SELECT to_regclass('retailiq.v_sales') IS NOT NULL")).scalar()
                )
                if info["schema_ready"]:
                    info["fact_rows"] = int(conn.execute(text("SELECT count(*) FROM retailiq.v_sales")).scalar() or 0)
                    can_write = conn.execute(
                        text("SELECT has_table_privilege(current_user, 'retailiq.fact_sales', 'INSERT')")
                    ).scalar()
                    info["readonly_role"] = not bool(can_write)
                    row = (
                        conn.execute(
                            text(
                                "SELECT run_id, status, finished_at, raw_rows, valid_rows, rejected_rows, "
                                "inserted_rows, skipped_rows FROM retailiq.etl_runs ORDER BY run_id DESC LIMIT 1"
                            )
                        )
                        .mappings()
                        .first()
                    )
                    if row:
                        info["last_etl_run"] = {
                            k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in row.items()
                        }
                conn.rollback()
        except Exception as exc:  # noqa: BLE001 - report, never raise
            info["error"] = safe_error(exc)
            log.warning("Database status check failed: %s", info["error"])
        return info
