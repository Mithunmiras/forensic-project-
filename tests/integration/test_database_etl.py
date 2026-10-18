import pandas as pd
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from src.config import CLEAN_CSV, Settings
from src.db.admin import apply_schema, create_database_if_missing
from src.db.session import Database
from src.etl import pipeline
from src.etl.pipeline import run_etl

pytestmark = pytest.mark.integration


def scalar(engine, sql):
    with engine.connect() as conn:
        return conn.execute(text(sql)).scalar()


@pytest.fixture(scope="module")
def csv():
    return pd.read_csv(CLEAN_CSV)


def test_first_load_inserted_every_row(loaded_db, csv):
    s = loaded_db["summary"]
    assert (s.raw_rows, s.valid_rows, s.rejected_rows, s.duplicate_rows) == (51290, 51290, 0, 0)
    assert s.inserted_rows == 51290 and s.skipped_rows == 0 and s.status == "succeeded"


def test_row_counts_and_dimensions(loaded_db, csv):
    e = loaded_db["engine"]
    assert scalar(e, "SELECT count(*) FROM retailiq.fact_sales") == 51290
    assert scalar(e, "SELECT count(*) FROM retailiq.dim_customer") == csv.customer_id.nunique() == 4873
    assert scalar(e, "SELECT count(*) FROM retailiq.dim_product") == len(csv[["product_id", "product_name", "category", "sub_category"]].drop_duplicates()) == 10768
    assert scalar(e, "SELECT count(*) FROM retailiq.dim_location") == len(csv[["city", "state", "country", "region", "market", "market2"]].drop_duplicates()) == 3819


def test_totals_match_the_csv_exactly(loaded_db, csv):
    e = loaded_db["engine"]
    sales, profit, qty, disc = None, None, None, None
    with e.connect() as c:
        sales, profit, qty, disc = c.execute(text("SELECT sum(sales), sum(profit), sum(quantity), avg(discount) FROM retailiq.v_sales")).one()
    assert float(sales) == pytest.approx(csv.sales.sum(), abs=1e-6)
    assert float(profit) == pytest.approx(csv.profit.sum(), abs=1e-4)  # full precision preserved
    assert qty == csv.quantity.sum()
    assert float(disc) == pytest.approx(csv.discount.mean(), abs=1e-6)
    assert scalar(e, "SELECT count(DISTINCT order_id) FROM retailiq.v_sales") == csv.order_id.nunique()


def test_precision_is_not_rounded(loaded_db, csv):
    e = loaded_db["engine"]
    odd = csv[(csv.discount * 1000 % 10 != 0)].iloc[0]  # a 3-decimal discount, e.g. 0.002
    stored = scalar(e, f"SELECT discount FROM retailiq.fact_sales WHERE row_id = {int(odd.row_id)}")
    assert float(stored) == pytest.approx(odd.discount, abs=1e-9)


def test_etl_is_idempotent(loaded_db):
    e = loaded_db["engine"]
    before = scalar(e, "SELECT count(*) FROM retailiq.fact_sales")
    again = run_etl(e, source="raw", write_report=False)
    assert again.inserted_rows == 0 and again.skipped_rows == 51290 and again.updated_rows == 0
    assert scalar(e, "SELECT count(*) FROM retailiq.fact_sales") == before
    assert scalar(e, "SELECT count(*) FROM retailiq.dim_customer") == 4873
    assert scalar(e, "SELECT count(*) FROM retailiq.etl_runs WHERE status = 'succeeded'") >= 2


def test_processed_csv_source_gives_the_same_result(loaded_db):
    again = run_etl(loaded_db["engine"], source="processed", write_report=False)
    assert again.inserted_rows == 0 and again.valid_rows == 51290


def test_update_existing_refreshes_only_changed_rows(loaded_db):
    e = loaded_db["engine"]
    original = scalar(e, "SELECT sales FROM retailiq.fact_sales WHERE row_id = 100")
    with e.begin() as c:
        c.execute(text("UPDATE retailiq.fact_sales SET sales = sales + 1 WHERE row_id = 100"))
    same = run_etl(e, source="raw", update_existing=False, write_report=False)
    assert same.updated_rows == 0  # default mode never overwrites
    fixed = run_etl(e, source="raw", update_existing=True, write_report=False)
    assert fixed.updated_rows == 1 and fixed.inserted_rows == 0
    assert scalar(e, "SELECT sales FROM retailiq.fact_sales WHERE row_id = 100") == original


def test_schema_application_is_idempotent_and_non_destructive(loaded_db):
    e = loaded_db["engine"]
    apply_schema(e)
    apply_schema(e)
    assert scalar(e, "SELECT count(*) FROM retailiq.fact_sales") == 51290


def test_dry_run_needs_no_database_and_writes_nothing(tmp_path):
    s = run_etl(None, source="raw", dry_run=True, write_report=False)
    assert s.dry_run and s.status == "dry_run" and s.valid_rows == 51290 and s.inserted_rows == 0


def test_database_is_required_unless_dry_run():
    with pytest.raises(pipeline.EtlError):
        run_etl(None, source="raw", write_report=False)


def test_failed_load_rolls_back_and_is_recorded(loaded_db, monkeypatch):
    url = make_url(loaded_db["url"]).set(database="retailiq_rollback_test").render_as_string(hide_password=False)
    assert create_database_if_missing(url) is True
    assert create_database_if_missing(url) is False  # second call: already exists
    engine = create_engine(url)
    try:
        apply_schema(engine)
        real = pipeline.load_dataframe

        def load_then_fail(conn, df, run_id, update_existing=False):
            real(conn, df, run_id, update_existing)  # rows really are inserted inside the transaction...
            raise RuntimeError("simulated crash after insert, password=hunter2")

        monkeypatch.setattr(pipeline, "load_dataframe", load_then_fail)
        with pytest.raises(RuntimeError):
            run_etl(engine, source="raw", write_report=False)

        assert scalar(engine, "SELECT count(*) FROM retailiq.fact_sales") == 0       # ...and are rolled back
        assert scalar(engine, "SELECT count(*) FROM retailiq.dim_customer") == 0
        row = engine.connect().execute(text("SELECT status, error_message FROM retailiq.etl_runs")).one()
        assert row.status == "failed" and "simulated crash" in row.error_message
        assert "hunter2" not in row.error_message  # secrets are redacted in the audit log

        monkeypatch.setattr(pipeline, "load_dataframe", real)  # and a later retry succeeds cleanly
        ok = run_etl(engine, source="raw", write_report=False)
        assert ok.inserted_rows == 51290
    finally:
        engine.dispose()


# ----------------------------------------------------------------------------- read-only role + status
def test_readonly_role_can_read_the_view_only(loaded_db):
    ro = create_engine(loaded_db["readonly_url"])
    try:
        with ro.connect() as c:
            assert c.execute(text("SELECT count(*) FROM retailiq.v_sales")).scalar() == 51290
        for sql in (
            "DELETE FROM retailiq.fact_sales",
            "UPDATE retailiq.fact_sales SET sales = 0",
            "INSERT INTO retailiq.etl_runs (status, source_file) VALUES ('succeeded', 'x')",
            "CREATE TABLE public.hack (i int)",
            "SELECT * FROM retailiq.fact_sales",     # no direct table access, only the view
            "SELECT * FROM retailiq.dim_customer",
        ):
            with ro.connect() as c, pytest.raises(Exception):
                c.execute(text(sql))
    finally:
        ro.dispose()
    assert scalar(loaded_db["engine"], "SELECT count(*) FROM retailiq.fact_sales") == 51290


def test_status_reports_dedicated_readonly_role(loaded_db):
    db = Database(Settings(database_url=loaded_db["url"], database_readonly_url=loaded_db["readonly_url"], _env_file=None))
    st = db.status()
    assert st["connected"] and st["schema_ready"] and st["readonly_role"] is True
    assert st["fact_rows"] == 51290 and st["last_etl_run"]["status"] == "succeeded"
    assert "test-readonly-pw" not in str(st) and "***" in st["url"]
    db.dispose()


def test_status_without_dedicated_role_is_honest(loaded_db):
    db = Database(Settings(database_url=loaded_db["url"], _env_file=None))
    st = db.status()
    assert st["connected"] and st["readonly_role"] is False  # privileged account reused; not claimed read-only
    db.dispose()


def test_status_when_not_configured_or_unreachable():
    st = Database(Settings(_env_file=None)).status()
    assert st["configured"] is False and st["connected"] is False and "DATABASE_URL" in st["error"]
    bad = Database(Settings(database_url="postgresql://u:topsecret@127.0.0.1:1/none", _env_file=None))
    st = bad.status()
    assert st["configured"] and st["connected"] is False and st["error"]
    assert "topsecret" not in str(st)
    bad.dispose()
