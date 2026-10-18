"""Extract -> validate -> load pipeline for the Superstore data.

    python scripts/run_etl.py [--source raw|processed] [--update-existing] [--dry-run]

Design goals
* **Idempotent** - ``fact_sales.row_id`` is the source line id; re-running never
  duplicates rows (``ON CONFLICT``), dimension rows are upserted on natural keys.
* **Transactional** - the whole load (dimensions, facts, run bookkeeping) is a single
  transaction; any failure rolls back and the failure is recorded in ``etl_runs``.
* **Honest** - rows that fail validation are rejected (and counted/reported), never
  silently repaired or dropped.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import Connection, Engine, text

from src.config import CLEAN_CSV, RAW_CSV, REPORTS_DIR
from src.etl.clean_data import clean_frame

log = logging.getLogger("retailiq.etl")

TEXT_COLUMNS = [
    "order_id", "customer_id", "customer_name", "segment", "product_id", "product_name",
    "category", "sub_category", "city", "state", "country", "region", "market", "market2",
    "ship_mode", "order_priority",
]
NUMERIC_COLUMNS = ["row_id", "quantity", "discount", "sales", "profit", "shipping_cost"]
DATE_COLUMNS = ["order_date", "ship_date"]
REQUIRED_COLUMNS = TEXT_COLUMNS + NUMERIC_COLUMNS + DATE_COLUMNS

CLEANING_DECISIONS = [
    "Non-ASCII helper column (the Chinese row-count column) is dropped; it is constant and carries no information.",
    "Column names are lower-cased, with spaces/dots replaced by underscores.",
    "order_date / ship_date are parsed; unparseable dates reject the row rather than being guessed.",
    "shipping_days = ship_date - order_date (days), derived only when both dates are valid.",
    "Text fields are whitespace-trimmed; no values are imputed or invented.",
    "Rows violating a business rule (see rejected_by_reason) are rejected and reported, not repaired.",
    "A repeated row_id keeps the first occurrence; later ones are rejected as duplicates.",
]


class EtlError(RuntimeError):
    """The pipeline cannot continue (bad schema, unreadable source, ...)."""


@dataclass
class ValidationResult:
    valid: pd.DataFrame
    rejected: pd.DataFrame
    report: dict[str, Any]


@dataclass
class EtlSummary:
    status: str
    source_file: str
    raw_rows: int
    duplicate_rows: int
    rejected_rows: int
    valid_rows: int
    inserted_rows: int = 0
    updated_rows: int = 0
    skipped_rows: int = 0
    run_id: int | None = None
    dry_run: bool = False
    quality_report: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("quality_report")
        return d


# --------------------------------------------------------------------------- extract / transform
def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def extract(source: str = "raw", path: Path | None = None) -> tuple[pd.DataFrame, Path]:
    """Read the raw export (and clean it) or the already-processed CSV."""
    if source not in {"raw", "processed"}:
        raise EtlError("source must be 'raw' or 'processed'")
    src_path = Path(path) if path else (RAW_CSV if source == "raw" else CLEAN_CSV)
    if not src_path.exists():
        raise EtlError(f"Source file not found: {src_path}")
    frame = pd.read_csv(src_path)
    try:
        df = clean_frame(frame)
    except ValueError as exc:
        raise EtlError(str(exc)) from exc
    return df, src_path


# --------------------------------------------------------------------------- validate
def validate(df: pd.DataFrame) -> ValidationResult:
    """Apply type coercion and business rules; split into valid / rejected rows."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise EtlError(f"Source is missing required columns: {missing}")

    raw_rows = len(df)
    data = df.copy()

    for col in TEXT_COLUMNS:
        data[col] = data[col].astype("string").str.strip().replace("", pd.NA)
    for col in NUMERIC_COLUMNS:
        data[col] = pd.to_numeric(data[col], errors="coerce")
    for col in DATE_COLUMNS:
        data[col] = pd.to_datetime(data[col], errors="coerce")

    duplicate_rows = int(df.duplicated().sum())

    reasons: dict[str, pd.Series] = {}
    for col in TEXT_COLUMNS:
        reasons[f"missing_{col}"] = data[col].isna()
    reasons["invalid_row_id"] = data["row_id"].isna() | (data["row_id"] != data["row_id"].round())
    reasons["invalid_order_date"] = data["order_date"].isna()
    reasons["invalid_ship_date"] = data["ship_date"].isna()
    reasons["ship_before_order"] = (data["ship_date"] < data["order_date"]).fillna(False)
    reasons["invalid_quantity"] = data["quantity"].isna() | (data["quantity"] <= 0) | (data["quantity"] != data["quantity"].round())
    reasons["invalid_discount"] = data["discount"].isna() | (data["discount"] < 0) | (data["discount"] > 1)
    reasons["invalid_sales"] = data["sales"].isna() | (data["sales"] < 0)
    reasons["invalid_profit"] = data["profit"].isna()
    reasons["invalid_shipping_cost"] = data["shipping_cost"].isna() | (data["shipping_cost"] < 0)
    reasons["duplicate_row_id"] = data["row_id"].notna() & data["row_id"].duplicated(keep="first")

    reason_frame = pd.DataFrame(reasons)
    bad = reason_frame.any(axis=1)
    rejected = df.loc[bad].copy()
    bad_reasons = reason_frame[bad]
    rejected["reject_reason"] = [",".join(bad_reasons.columns[row]) for row in bad_reasons.to_numpy()]
    valid = data.loc[~bad].copy()
    valid["row_id"] = valid["row_id"].astype(int)
    valid["quantity"] = valid["quantity"].astype(int)
    valid["shipping_days"] = (valid["ship_date"] - valid["order_date"]).dt.days.astype(int)

    year_mismatch = 0
    if "year" in valid.columns:
        year_mismatch = int((pd.to_numeric(valid["year"], errors="coerce") != valid["order_date"].dt.year).sum())

    report = {
        "raw_rows": raw_rows,
        "columns": list(df.columns),
        "duplicate_rows": duplicate_rows,
        "rejected_rows": int(bad.sum()),
        "valid_rows": int(len(valid)),
        "rejected_by_reason": {k: int(v.sum()) for k, v in reasons.items() if int(v.sum()) > 0},
        "null_counts": {c: int(n) for c, n in df.isna().sum().items() if n > 0},
        "order_date_range": (
            [valid["order_date"].min().strftime("%Y-%m-%d"), valid["order_date"].max().strftime("%Y-%m-%d")]
            if len(valid) else None
        ),
        "numeric_ranges": {
            c: [float(valid[c].min()), float(valid[c].max())] for c in ["quantity", "discount", "sales", "profit", "shipping_cost", "shipping_days"]
        } if len(valid) else {},
        "distinct_counts": {
            c: int(valid[c].nunique()) for c in ["customer_id", "product_id", "category", "sub_category", "region", "market", "country", "ship_mode"]
        } if len(valid) else {},
        "year_column_mismatches": year_mismatch,
        "cleaning_decisions": CLEANING_DECISIONS,
    }
    return ValidationResult(valid=valid, rejected=rejected, report=report)


# --------------------------------------------------------------------------- load
STAGE_COLUMNS = [
    ("row_id", "INTEGER"), ("order_id", "TEXT"), ("customer_id", "TEXT"), ("customer_name", "TEXT"),
    ("segment", "TEXT"), ("product_id", "TEXT"), ("product_name", "TEXT"), ("category", "TEXT"),
    ("sub_category", "TEXT"), ("city", "TEXT"), ("state", "TEXT"), ("country", "TEXT"),
    ("region", "TEXT"), ("market", "TEXT"), ("market2", "TEXT"), ("order_date", "DATE"),
    ("ship_date", "DATE"), ("ship_mode", "TEXT"), ("order_priority", "TEXT"), ("quantity", "INTEGER"),
    ("discount", "NUMERIC"), ("sales", "NUMERIC"), ("profit", "NUMERIC"), ("shipping_cost", "NUMERIC"),
    ("shipping_days", "INTEGER"),
]


def _stage_rows(df: pd.DataFrame):
    cols = [c for c, _ in STAGE_COLUMNS]
    frame = df[cols].copy()
    for c in DATE_COLUMNS:
        frame[c] = frame[c].dt.date
    for c in ("discount", "sales", "profit", "shipping_cost"):
        frame[c] = frame[c].astype(float)  # source precision is preserved (no rounding)
    for row in frame.astype(object).itertuples(index=False, name=None):
        yield tuple(None if (v is pd.NA or (isinstance(v, float) and v != v)) else v for v in row)


def load_dataframe(conn: Connection, df: pd.DataFrame, run_id: int, update_existing: bool = False) -> dict[str, int]:
    """Load validated rows inside the caller's transaction. Returns row counts."""
    cols_ddl = ", ".join(f"{c} {t}" for c, t in STAGE_COLUMNS)
    conn.exec_driver_sql(f"CREATE TEMP TABLE stg_sales ({cols_ddl}) ON COMMIT DROP")

    raw = conn.connection.driver_connection
    col_list = ", ".join(c for c, _ in STAGE_COLUMNS)
    with raw.cursor() as cur, cur.copy(f"COPY stg_sales ({col_list}) FROM STDIN") as copy:
        for row in _stage_rows(df):
            copy.write_row(row)

    dim_action = (
        "DO UPDATE SET customer_name = EXCLUDED.customer_name, segment = EXCLUDED.segment"
        if update_existing else "DO NOTHING"
    )
    conn.exec_driver_sql(
        "INSERT INTO retailiq.dim_customer (customer_id, customer_name, segment) "
        "SELECT DISTINCT ON (customer_id) customer_id, customer_name, segment FROM stg_sales "
        f"ORDER BY customer_id, row_id ON CONFLICT (customer_id) {dim_action}"
    )
    conn.exec_driver_sql(
        "INSERT INTO retailiq.dim_product (product_id, product_name, category, sub_category) "
        "SELECT DISTINCT product_id, product_name, category, sub_category FROM stg_sales "
        "ON CONFLICT (product_id, product_name, category, sub_category) DO NOTHING"
    )
    conn.exec_driver_sql(
        "INSERT INTO retailiq.dim_location (city, state, country, region, market, market2) "
        "SELECT DISTINCT city, state, country, region, market, market2 FROM stg_sales "
        "ON CONFLICT (city, state, country, region, market, market2) DO NOTHING"
    )

    fact_cols = (
        "row_id, order_id, customer_key, product_key, location_key, order_date, ship_date, ship_mode, "
        "order_priority, quantity, discount, sales, profit, shipping_cost, shipping_days, etl_run_id"
    )
    select = (
        "SELECT s.row_id, s.order_id, c.customer_key, p.product_key, l.location_key, s.order_date, s.ship_date, "
        "s.ship_mode, s.order_priority, s.quantity, s.discount, s.sales, s.profit, s.shipping_cost, "
        "s.shipping_days, %(run)d "
        "FROM stg_sales s "
        "JOIN retailiq.dim_customer c ON c.customer_id = s.customer_id "
        "JOIN retailiq.dim_product p ON p.product_id = s.product_id AND p.product_name = s.product_name "
        "AND p.category = s.category AND p.sub_category = s.sub_category "
        "JOIN retailiq.dim_location l ON l.city = s.city AND l.state = s.state AND l.country = s.country "
        "AND l.region = s.region AND l.market = s.market AND l.market2 = s.market2"
    ) % {"run": int(run_id)}

    if update_existing:
        rows = conn.exec_driver_sql(
            f"INSERT INTO retailiq.fact_sales ({fact_cols}) {select} "
            "ON CONFLICT (row_id) DO UPDATE SET order_id = EXCLUDED.order_id, customer_key = EXCLUDED.customer_key, "
            "product_key = EXCLUDED.product_key, location_key = EXCLUDED.location_key, order_date = EXCLUDED.order_date, "
            "ship_date = EXCLUDED.ship_date, ship_mode = EXCLUDED.ship_mode, order_priority = EXCLUDED.order_priority, "
            "quantity = EXCLUDED.quantity, discount = EXCLUDED.discount, sales = EXCLUDED.sales, profit = EXCLUDED.profit, "
            "shipping_cost = EXCLUDED.shipping_cost, shipping_days = EXCLUDED.shipping_days, etl_run_id = EXCLUDED.etl_run_id "
            "WHERE (retailiq.fact_sales.sales, retailiq.fact_sales.profit, retailiq.fact_sales.quantity, "
            "retailiq.fact_sales.discount, retailiq.fact_sales.shipping_cost, retailiq.fact_sales.order_date, "
            "retailiq.fact_sales.ship_date, retailiq.fact_sales.customer_key, retailiq.fact_sales.product_key, "
            "retailiq.fact_sales.location_key) IS DISTINCT FROM "
            "(EXCLUDED.sales, EXCLUDED.profit, EXCLUDED.quantity, EXCLUDED.discount, EXCLUDED.shipping_cost, "
            "EXCLUDED.order_date, EXCLUDED.ship_date, EXCLUDED.customer_key, EXCLUDED.product_key, EXCLUDED.location_key) "
            "RETURNING (xmax = 0) AS inserted"
        ).fetchall()
        inserted = sum(1 for r in rows if r[0])
        updated = len(rows) - inserted
    else:
        result = conn.exec_driver_sql(
            f"INSERT INTO retailiq.fact_sales ({fact_cols}) {select} ON CONFLICT (row_id) DO NOTHING"
        )
        inserted, updated = result.rowcount, 0

    return {"inserted": inserted, "updated": updated, "skipped": len(df) - inserted - updated}


# --------------------------------------------------------------------------- orchestration
def _start_run(engine: Engine, source_file: str, sha: str) -> int:
    with engine.begin() as conn:
        return int(
            conn.execute(
                text(
                    "INSERT INTO retailiq.etl_runs (status, source_file, source_sha256) "
                    "VALUES ('running', :f, :s) RETURNING run_id"
                ),
                {"f": source_file, "s": sha},
            ).scalar_one()
        )


def _fail_run(engine: Engine, run_id: int, message: str) -> None:
    from src.logging_setup import redact

    with engine.begin() as conn:
        conn.execute(
            text("UPDATE retailiq.etl_runs SET status='failed', finished_at=now(), error_message=:m WHERE run_id=:r"),
            {"m": redact(message)[:2000], "r": run_id},
        )


def write_reports(result: ValidationResult, summary: EtlSummary) -> None:
    REPORTS_DIR.mkdir(exist_ok=True)
    payload = {**summary.as_dict(), **result.report}
    (REPORTS_DIR / "data_quality_report.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    rejected_path = REPORTS_DIR / "etl_rejected_rows.csv"
    if len(result.rejected):
        result.rejected.to_csv(rejected_path, index=False)
    elif rejected_path.exists():
        rejected_path.unlink()


def run_etl(
    engine: Engine | None,
    *,
    source: str = "raw",
    path: Path | None = None,
    update_existing: bool = False,
    dry_run: bool = False,
    write_report: bool = True,
) -> EtlSummary:
    """Run the full pipeline. ``engine`` may be None only for ``dry_run``."""
    df, src_path = extract(source, path)
    result = validate(df)
    report = result.report
    summary = EtlSummary(
        status="dry_run" if dry_run else "running",
        source_file=str(src_path.name),
        raw_rows=report["raw_rows"],
        duplicate_rows=report["duplicate_rows"],
        rejected_rows=report["rejected_rows"],
        valid_rows=report["valid_rows"],
        dry_run=dry_run,
        quality_report=report,
    )
    log.info(
        "Validated %s: raw=%d valid=%d rejected=%d duplicates=%d",
        src_path.name, summary.raw_rows, summary.valid_rows, summary.rejected_rows, summary.duplicate_rows,
    )
    if dry_run:
        if write_report:
            write_reports(result, summary)
        return summary
    if engine is None:
        raise EtlError("A database engine is required unless --dry-run is used.")
    if summary.valid_rows == 0:
        raise EtlError("No valid rows to load; refusing to continue.")

    sha = sha256_of(src_path)
    run_id = _start_run(engine, src_path.name, sha)
    summary.run_id = run_id
    try:
        with engine.begin() as conn:
            counts = load_dataframe(conn, result.valid, run_id, update_existing=update_existing)
            summary.inserted_rows = counts["inserted"]
            summary.updated_rows = counts["updated"]
            summary.skipped_rows = counts["skipped"]
            summary.status = "succeeded"
            conn.execute(
                text(
                    "UPDATE retailiq.etl_runs SET status='succeeded', finished_at=now(), raw_rows=:raw, "
                    "duplicate_rows=:dup, rejected_rows=:rej, valid_rows=:val, inserted_rows=:ins, "
                    "updated_rows=:upd, skipped_rows=:skip, quality_report=CAST(:q AS JSONB) WHERE run_id=:r"
                ),
                {
                    "raw": summary.raw_rows, "dup": summary.duplicate_rows, "rej": summary.rejected_rows,
                    "val": summary.valid_rows, "ins": summary.inserted_rows, "upd": summary.updated_rows,
                    "skip": summary.skipped_rows, "q": json.dumps(report, default=str), "r": run_id,
                },
            )
    except Exception as exc:
        summary.status = "failed"
        _fail_run(engine, run_id, f"{exc.__class__.__name__}: {exc}")
        raise
    if write_report:
        write_reports(result, summary)
    log.info(
        "ETL run %d succeeded: inserted=%d updated=%d skipped=%d",
        run_id, summary.inserted_rows, summary.updated_rows, summary.skipped_rows,
    )
    return summary
