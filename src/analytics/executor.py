"""Execution of validated, read-only queries with timeout and row cap."""
from __future__ import annotations

import datetime as dt
import decimal
import re
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Engine
from sqlalchemy import exc as sa_exc

from src.analytics.sql_validator import ValidatedSQL
from src.db.session import DatabaseUnavailable, safe_error


class QueryFailed(RuntimeError):
    """The database rejected or aborted the query (syntax/semantic error, timeout, ...)."""

    def __init__(self, message: str, *, timed_out: bool = False) -> None:
        super().__init__(message)
        self.timed_out = timed_out


@dataclass
class QueryResult:
    columns: list[dict[str, str]]
    rows: list[list[Any]]
    row_count: int
    truncated: bool
    elapsed_ms: float

    def as_dicts(self) -> list[dict[str, Any]]:
        names = [c["name"] for c in self.columns]
        return [dict(zip(names, r)) for r in self.rows]


def to_jsonable(value: Any) -> Any:
    """Make a database value JSON-safe without losing meaning."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, float):
        return None if value != value or value in (float("inf"), float("-inf")) else value
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    return str(value)


def _type_name(values: list[Any]) -> str:
    for v in values:
        if v is None:
            continue
        if isinstance(v, bool):
            return "boolean"
        if isinstance(v, (int, float)):
            return "number"
        if isinstance(v, str) and len(v) in (7, 10) and v[:4].isdigit() and v[4] == "-":
            return "date"
        return "text"
    return "text"


_LITERAL_PERCENT = re.compile(r"%(?!\(\w+\)s)")


def escape_percent(sql: str) -> str:
    """The driver treats % as a placeholder marker; escape literal ones (LIKE '%x%')
    while keeping genuine named placeholders such as ``%(p0)s``."""
    return _LITERAL_PERCENT.sub("%%", sql)


def execute_readonly(
    engine: Engine,
    query: ValidatedSQL | str,
    params: dict[str, Any] | None = None,
    *,
    max_rows: int,
    timeout_ms: int,
) -> QueryResult:
    sql = escape_percent(query.sql if isinstance(query, ValidatedSQL) else query)
    started = time.perf_counter()
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            conn.exec_driver_sql(f"SET LOCAL statement_timeout = {int(timeout_ms)}")
            result = conn.exec_driver_sql(sql, params) if params else conn.exec_driver_sql(sql)
            keys = list(result.keys())
            raw_rows = result.fetchmany(max_rows + 1)
            conn.rollback()
    except sa_exc.DBAPIError as exc:
        orig = getattr(exc, "orig", None)
        name = orig.__class__.__name__ if orig else ""
        if name == "QueryCanceled":
            raise QueryFailed(f"The query exceeded the {timeout_ms} ms time limit.", timed_out=True) from exc
        if exc.connection_invalidated or name in ("OperationalError", "InterfaceError"):
            raise DatabaseUnavailable(safe_error(exc)) from exc
        raise QueryFailed(safe_error(orig or exc)) from exc
    elapsed = (time.perf_counter() - started) * 1000
    truncated = len(raw_rows) > max_rows
    rows = [[to_jsonable(v) for v in r] for r in raw_rows[:max_rows]]
    columns = [{"name": k, "type": _type_name([r[i] for r in rows])} for i, k in enumerate(keys)]
    return QueryResult(columns=columns, rows=rows, row_count=len(rows), truncated=truncated, elapsed_ms=round(elapsed, 1))
