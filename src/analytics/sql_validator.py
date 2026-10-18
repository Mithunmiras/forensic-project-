"""AST-based validation of SQL before it may touch the database.

This does NOT rely on keyword blacklists. The statement is parsed with sqlglot
(PostgreSQL dialect) and must satisfy ALL of these rules:

1. exactly one statement, and it is a query (SELECT / set operation / WITH ... SELECT);
2. no DML/DDL/utility nodes anywhere in the tree, no ``SELECT ... INTO``, no ``FOR UPDATE``;
3. every table is ``retailiq.v_sales`` (or a CTE defined in the same statement) -
   no catalog / information_schema / other tables, no table functions, no VALUES;
4. every function is on an allowlist (blocks ``pg_sleep``, ``set_config``, ``lo_*``, ...);
5. every column is a real ``v_sales`` column or an alias defined in the statement
   (blocks system columns such as ``ctid``);
6. no query parameters unless the caller declares them (used by trusted templates);
7. a hard row limit is injected into the executed SQL.

The SQL that is *executed* is regenerated from the validated AST (comments and
oddities are gone), never the raw input string.
"""
from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from src.analytics.schema_info import COLUMN_NAMES, SCHEMA, VIEW

MAX_SQL_CHARS = 4000
MAX_AST_NODES = 800


class UnsafeSQL(ValueError):
    """The statement was rejected. ``code`` is a stable machine-readable reason."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# sqlglot node classes for permitted functions (name-based so dialect aliases map correctly).
_ALLOWED_FUNC_CLASS_NAMES = {
    # aggregates
    "Sum", "Avg", "Count", "Min", "Max", "Stddev", "StddevPop", "StddevSamp", "Variance", "VariancePop",
    "Median", "PercentileCont", "PercentileDisc", "ArrayAgg",
    # scalar / numeric
    "Round", "Ceil", "Floor", "Abs", "Sqrt", "Pow", "Power", "Ln", "Log", "Exp", "Sign", "Greatest", "Least",
    "Coalesce", "Nullif", "If", "Case", "Cast", "TryCast", "Extract",
    # text
    "Lower", "Upper", "Trim", "Substring", "Length", "Concat", "ConcatWs", "Initcap",
    # date/time
    "TimestampTrunc", "DateTrunc", "TimeToStr", "ToChar", "CurrentDate", "DateDiff", "DateAdd", "DateSub",
    # window
    "RowNumber", "Rank", "DenseRank", "Lag", "Lead", "FirstValue", "LastValue", "NthValue", "Ntile",
    "PercentRank", "CumeDist",
}
ALLOWED_FUNC_CLASSES = tuple(getattr(exp, n) for n in _ALLOWED_FUNC_CLASS_NAMES if hasattr(exp, n))
# Unknown ("anonymous") function names that are still safe.
ALLOWED_ANON_FUNCS = {"to_char", "date_trunc", "initcap", "round", "stddev", "variance", "ntile", "date_part", "age"}

_FORBIDDEN_NODE_NAMES = [
    "Insert", "Update", "Delete", "Merge", "Create", "Drop", "Alter", "AlterColumn", "Command", "TruncateTable",
    "Set", "SetItem", "Use", "Copy", "Grant", "Revoke", "Transaction", "Commit", "Rollback", "Pragma", "Describe",
    "Show", "Kill", "Analyze", "Refresh", "LoadData", "Declare", "Into", "Lock", "Comment", "Cache", "Uncache",
    "Attach", "Detach", "Export", "Values", "Unnest", "Lateral", "Pivot", "Table_",
]
FORBIDDEN_NODES = tuple(getattr(exp, n) for n in _FORBIDDEN_NODE_NAMES if hasattr(exp, n))


@dataclass
class ValidatedSQL:
    sql: str                 # executable, normalised, limited
    display_sql: str         # pretty-printed version for UI / audit
    effective_limit: int
    truncated_possible: bool  # True when the caller's own LIMIT was absent or above the cap
    tables: list[str]


def _alias_names(root: exp.Expression) -> set[str]:
    names: set[str] = set()
    for a in root.find_all(exp.Alias):
        if a.alias:
            names.add(a.alias.lower())
    for ta in root.find_all(exp.TableAlias):
        if ta.name:
            names.add(ta.name.lower())
        for col in ta.args.get("columns") or []:
            names.add(col.name.lower())
    return names


def validate_select(sql: str, *, max_rows: int, allowed_params: set[str] | None = None) -> ValidatedSQL:
    """Validate ``sql`` and return the executable, row-limited statement."""
    allowed_params = allowed_params or set()
    if not isinstance(sql, str) or not sql.strip():
        raise UnsafeSQL("empty", "The SQL statement is empty.")
    if len(sql) > MAX_SQL_CHARS:
        raise UnsafeSQL("too_long", f"The SQL statement is longer than {MAX_SQL_CHARS} characters.")

    try:
        statements = [s for s in sqlglot.parse(sql, read="postgres") if s is not None]
    except SqlglotError as exc:
        raise UnsafeSQL("parse_error", f"The SQL could not be parsed: {str(exc).splitlines()[0][:160]}") from exc
    if len(statements) != 1:
        raise UnsafeSQL("multiple_statements", "Exactly one SQL statement is allowed.")
    root = statements[0]
    if not isinstance(root, exp.Query):
        raise UnsafeSQL("not_a_query", f"Only SELECT queries are allowed (got {type(root).__name__.upper()}).")

    nodes = list(root.walk())
    if len(nodes) > MAX_AST_NODES:
        raise UnsafeSQL("too_complex", "The SQL statement is too complex.")

    for node in nodes:
        n = node[0] if isinstance(node, tuple) else node
        if isinstance(n, FORBIDDEN_NODES):
            raise UnsafeSQL("forbidden_construct", f"{type(n).__name__.upper()} is not allowed in analytics queries.")
        if isinstance(n, exp.Select):
            if n.args.get("into"):
                raise UnsafeSQL("forbidden_construct", "SELECT ... INTO is not allowed.")
            if n.args.get("locks"):
                raise UnsafeSQL("forbidden_construct", "Row locking (FOR UPDATE/SHARE) is not allowed.")

    # ---- tables -------------------------------------------------------
    cte_names = {c.alias.lower() for c in root.find_all(exp.CTE) if c.alias}
    tables: list[str] = []
    table_aliases: set[str] = set(cte_names)
    for t in root.find_all(exp.Table):
        if not isinstance(t.this, exp.Identifier):
            raise UnsafeSQL("forbidden_table", "Table functions are not allowed.")
        name, schema, catalog = t.name.lower(), (t.db or "").lower(), (t.catalog or "").lower()
        if t.alias:
            table_aliases.add(t.alias.lower())
        if name in cte_names and not schema and not catalog:
            continue
        if name != VIEW or schema not in ("", SCHEMA) or catalog:
            shown = ".".join(p for p in (catalog, schema, name) if p)
            raise UnsafeSQL("forbidden_table", f"Table '{shown}' is not allowed. Only {SCHEMA}.{VIEW} may be queried.")
        t.set("db", exp.to_identifier(SCHEMA))
        tables.append(f"{SCHEMA}.{VIEW}")
    table_aliases.add(VIEW)

    # ---- functions ----------------------------------------------------
    for fn in root.find_all(exp.Func):
        if isinstance(fn, (exp.Binary, exp.Unary, exp.Connector)):
            continue
        if isinstance(fn, exp.Anonymous):
            if fn.name.lower() not in ALLOWED_ANON_FUNCS:
                raise UnsafeSQL("forbidden_function", f"Function '{fn.name}' is not allowed.")
        elif not isinstance(fn, ALLOWED_FUNC_CLASSES):
            raise UnsafeSQL("forbidden_function", f"Function '{fn.sql_name()}' is not allowed.")

    # ---- parameters ---------------------------------------------------
    for ph in list(root.find_all(exp.Placeholder)) + list(root.find_all(exp.Parameter)):
        pname = (ph.name or "").lstrip(":@$")
        if pname not in allowed_params:
            raise UnsafeSQL("parameters_not_allowed", "Query parameters are not allowed in this context.")

    # ---- columns ------------------------------------------------------
    known_columns = set(COLUMN_NAMES) | _alias_names(root)
    for col in root.find_all(exp.Column):
        if isinstance(col.this, exp.Star):
            if col.table and col.table.lower() not in table_aliases:
                raise UnsafeSQL("unknown_table_alias", f"Unknown table alias '{col.table}'.")
            continue
        if col.table and col.table.lower() not in table_aliases:
            raise UnsafeSQL("unknown_table_alias", f"Unknown table alias '{col.table}'.")
        if col.name.lower() not in known_columns:
            raise UnsafeSQL("unknown_column", f"Column '{col.name}' does not exist in {VIEW}.")

    # ---- normalise: drop every comment so only validated structure is executed
    for node in root.walk():
        n = node[0] if isinstance(node, tuple) else node
        n.comments = None

    # ---- row limit ----------------------------------------------------
    user_limit = _literal_limit(root)
    cap = max_rows + 1  # one extra row lets callers detect truncation
    effective = cap if user_limit is None else min(user_limit, cap)
    limited = root.limit(effective, copy=False) if isinstance(root, (exp.Select, exp.SetOperation)) else root
    executable = limited.sql(dialect="postgres")
    display = limited.sql(dialect="postgres", pretty=True)
    return ValidatedSQL(
        sql=executable,
        display_sql=display,
        effective_limit=effective,
        truncated_possible=user_limit is None or user_limit > max_rows,
        tables=sorted(set(tables)),
    )


def _literal_limit(root: exp.Expression) -> int | None:
    limit = root.args.get("limit")
    if not limit:
        return None
    value = limit.expression
    if isinstance(value, exp.Literal) and value.is_int:
        return int(value.name)
    raise UnsafeSQL("unsupported_limit", "LIMIT must be an integer literal.")
