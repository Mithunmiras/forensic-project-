"""Privileged, non-destructive database administration helpers."""
from __future__ import annotations

import logging
from pathlib import Path

import psycopg
from psycopg import sql
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url

from src.config import DB_SCHEMA, ROOT

log = logging.getLogger("retailiq.db.admin")
SCHEMA_DIR = ROOT / "database" / "schema"


def create_database_if_missing(url: str) -> bool:
    """Create the target database when it does not exist. Never drops anything.

    Returns True if the database was created, False if it already existed.
    """
    target = make_url(url)
    dbname = target.database
    if not dbname:
        raise ValueError("DATABASE_URL has no database name.")
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": dbname}).scalar()
            if exists:
                return False
            quoted = psycopg.sql.Identifier(dbname).as_string(conn.connection.driver_connection)
            conn.exec_driver_sql(f"CREATE DATABASE {quoted}")
            log.info("Created database %s", dbname)
            return True
    finally:
        admin.dispose()


def apply_schema(engine: Engine, schema_dir: Path = SCHEMA_DIR) -> list[str]:
    """Run every ``database/schema/NNN_*.sql`` file in order (idempotent)."""
    applied: list[str] = []
    files = sorted(schema_dir.glob("[0-9][0-9][0-9]_*.sql"))
    if not files:
        raise FileNotFoundError(f"No schema files found in {schema_dir}")
    with engine.begin() as conn:
        for path in files:
            conn.exec_driver_sql(path.read_text(encoding="utf-8"))
            applied.append(path.name)
    return applied


def create_readonly_role(engine: Engine, role: str, password: str, *, reset_password: bool = False) -> str:
    """Create (or refresh the grants of) a SELECT-only login role for analytics.

    The role can read ``retailiq.v_sales`` and ``retailiq.etl_runs`` only and its
    sessions default to read-only. Returns "created" or "updated".
    """
    if not role.replace("_", "").isalnum():
        raise ValueError("Invalid role name.")
    if not password:
        raise ValueError("A password is required (set READONLY_DB_PASSWORD).")
    dbname = engine.url.database
    with engine.begin() as conn:
        raw: psycopg.Connection = conn.connection.driver_connection  # type: ignore[assignment]
        exists = raw.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone()
        ident = sql.Identifier(role)
        schema = sql.Identifier(DB_SCHEMA)
        if not exists:
            raw.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE").format(
                    ident, sql.Literal(password)
                )
            )
            outcome = "created"
        else:
            if reset_password:
                raw.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(ident, sql.Literal(password)))
            outcome = "updated"
        statements = [
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(dbname), ident),
            sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(schema, ident),
            sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA {} FROM {}").format(schema, ident),
            sql.SQL("GRANT SELECT ON {}.v_sales, {}.etl_runs TO {}").format(schema, schema, ident),
            sql.SQL("ALTER ROLE {} SET default_transaction_read_only = on").format(ident),
            sql.SQL("ALTER ROLE {} SET search_path = {}, public").format(ident, schema),
        ]
        for stmt in statements:
            raw.execute(stmt)
    return outcome
