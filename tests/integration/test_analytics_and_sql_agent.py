import datetime as dt
import json

import pandas as pd
import pytest
from sqlalchemy import text

from src.analytics.executor import QueryFailed, execute_readonly
from src.analytics.query_builder import SUPPORTED_EXAMPLES
from src.analytics.repository import AnalyticsRepository, Filters
from src.analytics.sql_agent import SqlAgent
from src.config import CLEAN_CSV
from src.db.session import Database
from tests.helpers import FakeLLM

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def df():
    return pd.read_csv(CLEAN_CSV, parse_dates=["order_date"])


@pytest.fixture
def db(make_settings):
    d = Database(make_settings())
    yield d
    d.dispose()


@pytest.fixture
def repo(db):
    return AnalyticsRepository(db)


def agent(make_settings, llm=None, **overrides):
    s = make_settings(**overrides)
    d = Database(s)
    return SqlAgent(d, AnalyticsRepository(d), llm or FakeLLM(available=False), s), d


# ============================================================================ repository vs pandas
def test_summary_matches_pandas(repo, df):
    k = repo.summary(Filters())["kpis"]
    assert k["total_sales"] == pytest.approx(df.sales.sum())
    assert k["total_profit"] == pytest.approx(df.profit.sum(), abs=0.01)
    assert k["orders"] == df.order_id.nunique() and k["customers"] == df.customer_id.nunique()
    assert k["units"] == df.quantity.sum() and k["order_lines"] == len(df)
    assert k["avg_discount"] == pytest.approx(df.discount.mean(), abs=1e-4)
    assert k["avg_order_value"] == pytest.approx(df.sales.sum() / df.order_id.nunique(), abs=0.01)
    assert k["profit_margin"] == pytest.approx(df.profit.sum() / df.sales.sum(), abs=1e-4)
    assert (k["first_date"], k["last_date"]) == ("2011-01-01", "2014-12-31")


def test_filters_are_applied(repo, df):
    f = Filters(dt.date(2013, 1, 1), dt.date(2013, 12, 31), category="Technology", market="US")
    sub = df[(df.year == 2013) & (df.category == "Technology") & (df.market == "US")]
    k = repo.summary(f)["kpis"]
    assert k["total_sales"] == pytest.approx(sub.sales.sum()) and k["orders"] == sub.order_id.nunique()
    only_region = repo.summary(Filters(region="Central"))["kpis"]["total_sales"]
    assert only_region == pytest.approx(df[df.region == "Central"].sales.sum())
    assert repo.summary(Filters(category="Nope"))["kpis"]["total_sales"] == 0  # unknown value -> empty, not an error


def test_period_comparison(repo, df):
    f = Filters(dt.date(2014, 1, 1), dt.date(2014, 12, 31))
    r = repo.summary(f, compare=True)
    assert r["previous"]["period"] == ["2013-01-01", "2013-12-31"]
    cur, prev = df[df.year == 2014].sales.sum(), df[df.year == 2013].sales.sum()
    assert r["change_pct"]["total_sales"] == pytest.approx((cur - prev) / prev * 100, abs=0.06)
    assert repo.summary(Filters(), compare=True)["change_pct"] is None  # needs a date range


def test_breakdowns_match_pandas(repo, df):
    for dim in ("category", "region", "market", "segment", "ship_mode"):
        got = {r["name"]: r["sales"] for r in repo.by_dimension(dim, Filters())}
        expect = df.groupby(dim).sales.sum()
        assert got == pytest.approx(expect.to_dict()), dim
    ordered = repo.by_dimension("sub_category", Filters(), order_by="profit")
    profits = [r["profit"] for r in ordered]
    assert profits == sorted(profits, reverse=True) and ordered[-1]["name"] == "Tables" and ordered[-1]["profit"] < 0


def test_trend_grains(repo, df):
    monthly = repo.trend(Filters(), "month")
    assert len(monthly) == 48 and monthly[0]["period"] == "2011-01"
    assert sum(p["sales"] for p in monthly) == pytest.approx(df.sales.sum())
    assert [p["period"] for p in repo.trend(Filters(), "year")] == ["2011", "2012", "2013", "2014"]
    assert len(repo.trend(Filters(), "quarter")) == 16
    with pytest.raises(ValueError):
        repo.trend(Filters(), "decade")


def test_top_lists_and_discount_bands(repo, df):
    top = repo.top_products(Filters(), 5)
    assert len(top) == 5 and top[0]["sales"] == df.groupby("product_name").sales.sum().max()
    assert repo.top_customers(Filters(), 3)[0]["sales"] == df.groupby("customer_id").sales.sum().max()
    bands = repo.discount_impact(Filters())
    assert sum(b["order_lines"] for b in bands) == len(df)
    assert bands[0]["margin_pct"] > 0 > bands[-1]["margin_pct"]  # discounts erode profit
    ship = {s["ship_mode"]: s["avg_days"] for s in repo.shipping(Filters())}
    assert ship["Same Day"] < ship["First Class"] < ship["Second Class"] < ship["Standard Class"]


def test_identifiers_cannot_be_injected(repo):
    with pytest.raises(ValueError):
        repo.by_dimension("category; DROP TABLE x", Filters())
    with pytest.raises(ValueError):
        repo.by_dimension("category", Filters(), order_by="sales; DROP")
    evil = Filters(category="Technology' OR '1'='1")
    assert repo.summary(evil)["kpis"]["total_sales"] == 0  # bound as a plain string


def test_filter_options_cached(repo):
    a = repo.filter_options()
    assert repo.filter_options() is a
    assert a["date_range"] == ["2011-01-01", "2014-12-31"] and len(a["regions"]) == 13 and len(a["markets"]) == 7


# ============================================================================ SQL agent: templates
@pytest.mark.parametrize("question", SUPPORTED_EXAMPLES)
def test_supported_examples_answer_from_the_database(make_settings, question):
    a, d = agent(make_settings)
    ans = a.answer(question)
    assert ans.status == "ok" and ans.method == "template" and ans.row_count > 0, ans.error
    assert ans.sql.startswith("SELECT") and "retailiq.v_sales" in ans.sql and ans.explanation
    d.dispose()


def test_answers_equal_independent_pandas_numbers(make_settings, df):
    a, d = agent(make_settings)
    ans = a.answer("Which product categories generate the most sales?")
    got = {r[0]: r[1] for r in ans.rows}
    assert got == pytest.approx(df.groupby("category").sales.sum().to_dict())
    assert [r[0] for r in ans.rows][0] == "Technology" and ans.chart == {"type": "bar", "x": "category", "y": "total_sales"}
    ans = a.answer("What is the monthly sales trend?")
    assert ans.chart["type"] == "line" and ans.row_count == 48
    ans = a.answer("Top 5 customers by profit in 2014")
    top = df[df.year == 2014].groupby("customer_name").profit.sum().nlargest(5)
    assert [r[0] for r in ans.rows] == top.index.tolist() and ans.params == {"y0": 2014}
    ans = a.answer("What is the total profit in 2013?")
    assert ans.rows[0][0] == pytest.approx(df[df.year == 2013].profit.sum(), abs=0.01)
    d.dispose()


def test_unsupported_question_without_llm_is_explicit(make_settings):
    a, d = agent(make_settings)
    ans = a.answer("what is the weather today")
    assert ans.status == "unsupported" and not ans.rows and ans.supported_examples
    assert "No LLM" in ans.error
    assert a.answer("").status == "error"
    d.dispose()


def test_database_down_is_reported_not_fabricated(make_settings):
    s = make_settings(database_readonly_url="postgresql://u:secretpw@127.0.0.1:1/none", database_url=None)
    d = Database(s)
    ans = SqlAgent(d, AnalyticsRepository(d), FakeLLM(available=False), s).answer("total sales")
    assert ans.status == "unavailable" and ans.rows == [] and "secretpw" not in str(ans.as_dict())
    d.dispose()


# ============================================================================ SQL agent: LLM path
def llm_json(sql, expl="Test query."):
    return json.dumps({"sql": sql, "explanation": expl})


def test_llm_sql_is_used_for_unrecognised_questions(make_settings):
    llm = FakeLLM([llm_json("SELECT year, ROUND(SUM(sales)) AS s FROM retailiq.v_sales WHERE sub_category = 'Phones' GROUP BY year ORDER BY year")])
    a, d = agent(make_settings, llm)
    ans = a.answer("Show me the single largest order line and who bought it")  # no template pattern matches
    assert ans.status == "ok" and ans.method == "llm" and ans.row_count == 4
    assert "Known values" in llm.calls[0][0]["content"] and "Phones" in llm.calls[0][0]["content"]
    d.dispose()


@pytest.mark.parametrize(
    "evil",
    [
        "DROP TABLE retailiq.fact_sales",
        "DELETE FROM retailiq.fact_sales",
        "SELECT pg_sleep(60)",
        "SELECT * FROM retailiq.fact_sales",
        "SELECT * FROM pg_catalog.pg_shadow",
        "SELECT 1; DELETE FROM retailiq.fact_sales",
        "WITH d AS (DELETE FROM retailiq.fact_sales RETURNING 1) SELECT * FROM d",
    ],
)
def test_unsafe_llm_sql_is_rejected_and_data_is_untouched(make_settings, loaded_db, evil):
    llm = FakeLLM([llm_json(evil), llm_json(evil)])  # first attempt and the correction attempt both unsafe
    a, d = agent(make_settings, llm)
    ans = a.answer("Please wipe everything and then show me something exotic")
    assert ans.status == "error" and not ans.rows and ans.error
    with loaded_db["engine"].connect() as c:
        assert c.execute(text("SELECT count(*) FROM retailiq.fact_sales")).scalar() == 51290
    d.dispose()


def test_llm_gets_one_chance_to_correct_its_sql(make_settings):
    llm = FakeLLM([llm_json("DROP TABLE x"), lambda msgs: llm_json("SELECT COUNT(*) AS n FROM retailiq.v_sales")])
    a, d = agent(make_settings, llm)
    ans = a.answer("an exotic question that no template understands")
    assert ans.status == "ok" and ans.method == "llm" and ans.rows == [[51290]]
    assert "rejected" in " ".join(ans.notes) and "not allowed" in llm.calls[1][-1]["content"].lower() or "rejected" in llm.calls[1][-1]["content"]
    d.dispose()


def test_non_json_llm_reply_is_handled(make_settings):
    a, d = agent(make_settings, FakeLLM(["I think the answer is 42", "still not json"]))
    ans = a.answer("an exotic question that no template understands")
    assert ans.status == "error" and "valid" in ans.error
    d.dispose()


def test_llm_first_strategy_and_template_fallback(make_settings):
    llm = FakeLLM([llm_json("SELECT category, ROUND(SUM(sales)) AS s FROM retailiq.v_sales GROUP BY 1 ORDER BY 2 DESC")])
    a, d = agent(make_settings, llm, sql_agent_strategy="llm_first")
    assert a.answer("sales by category").method == "llm"
    a2, d2 = agent(make_settings, FakeLLM(fail=True), sql_agent_strategy="llm_first")
    assert a2.answer("sales by category").method == "template"  # LLM failed -> deterministic fallback
    d.dispose(); d2.dispose()


def test_template_first_does_not_call_the_llm_for_known_questions(make_settings):
    llm = FakeLLM()
    a, d = agent(make_settings, llm)
    assert a.answer("total sales").method == "template" and llm.calls == []
    d.dispose()


def test_result_truncation_and_timeout(make_settings):
    llm = FakeLLM([llm_json("SELECT order_id, sales FROM retailiq.v_sales")])
    a, d = agent(make_settings, llm, max_result_rows=10)
    ans = a.answer("an exotic question that no template understands")
    assert ans.status == "ok" and ans.row_count == 10 and ans.truncated and any("truncated" in n for n in ans.notes)
    d.dispose()
    slow = llm_json("SELECT COUNT(*) FROM retailiq.v_sales a, retailiq.v_sales b, retailiq.v_sales c")
    a, d = agent(make_settings, FakeLLM([slow, slow]), query_timeout_ms=500)
    ans = a.answer("an exotic question that no template understands")
    assert ans.status == "error" and "time limit" in ans.error
    d.dispose()


def test_database_layer_refuses_writes_even_if_validation_were_bypassed(db):
    """Defence in depth: the session itself is read-only."""
    with pytest.raises(QueryFailed):
        execute_readonly(db.readonly_engine(), "DELETE FROM retailiq.fact_sales", max_rows=5, timeout_ms=2000)
    with pytest.raises(QueryFailed):
        execute_readonly(db.readonly_engine(), "SELECT * FROM retailiq.fact_sales LIMIT 1", max_rows=5, timeout_ms=2000)
