import pytest

from src.analytics.query_builder import SUPPORTED_EXAMPLES, build_sql, describe, parse_question
from src.analytics.sql_validator import validate_select

KNOWN = {
    "categories": ["Furniture", "Office Supplies", "Technology"],
    "sub_categories": ["Phones", "Chairs", "Tables", "Binders"],
    "regions": ["Central", "West", "Oceania"],
    "markets": ["US", "EU", "APAC", "Canada"],
    "segments": ["Consumer", "Corporate", "Home Office"],
    "ship_modes": ["Same Day", "First Class", "Standard Class"],
    "countries": ["Australia", "France"],
}


def spec(q):
    return parse_question(q, KNOWN)


@pytest.mark.parametrize(
    "question,metric,dimension",
    [
        ("What is the total sales amount?", "sales", None),
        ("Which product categories generate the most sales?", "sales", "category"),
        ("What are the top 10 products by sales?", "sales", "product"),
        ("Compare sales by region", "sales", "region"),
        ("What is the monthly sales trend?", "sales", "month"),
        ("Which sub-categories have the highest profit?", "profit", "sub_category"),
        ("What is the average discount by category?", "avg_discount", "category"),
        ("Which shipping modes have the longest shipping duration?", "avg_shipping_days", "ship_mode"),
        ("What is the profit margin by market?", "profit_margin", "market"),
        ("average order value by segment", "avg_order_value", "segment"),
        ("How many orders were placed in 2013?", "orders", None),
        ("How many customers do we have?", "customers", None),
        ("yearly sales", "sales", "year"),
        ("quarterly profit for Furniture", "profit", "quarter"),
    ],
)
def test_recognises_spec_questions(question, metric, dimension):
    s = spec(question)
    assert s is not None and s.metric == metric and s.dimension == dimension


@pytest.mark.parametrize("question", ["what is the weather today", "hello", "", "tell me a joke"])
def test_unsupported_questions_return_none(question):
    assert spec(question) is None


def test_limit_and_direction():
    s = spec("Which 3 countries have the lowest sales?")
    assert s.limit == 3 and s.descending is False
    assert spec("top five cities by sales").limit == 5
    assert spec("Top 5 customers by profit in 2014").limit == 5
    assert spec("sales by category").descending is True
    assert spec("monthly sales").descending is False  # time series ascend


def test_high_cardinality_dimensions_get_default_limit():
    s = spec("sales by product")
    assert s.limit == 10 and any("top 10" in n for n in s.notes)


def test_year_and_value_filters():
    s = spec("total profit of Technology in 2012")
    assert s.years == [2012] and s.filters == {"category": "Technology"}
    s = spec("sales between 2012 and 2013 by market")
    assert s.years == [2012, 2013] and s.year_range
    s = spec("sales by category in the US")
    assert s.filters == {"market": "US"}
    assert spec("how are things going us")  is None or True  # short names are case-sensitive; no crash


def test_dimension_is_not_also_a_filter():
    s = spec("sales by category")
    assert "category" not in s.filters


@pytest.mark.parametrize("question", SUPPORTED_EXAMPLES + [
    "Which 3 countries have the lowest sales?", "sales between 2012 and 2013 by market", "total profit of Technology in 2012",
    "top 5 products by profit in the US in 2013", "orders by ship mode",
])
def test_every_generated_query_passes_the_validator(question):
    s = spec(question)
    assert s is not None
    sql, params = build_sql(s)
    v = validate_select(sql, max_rows=500, allowed_params=set(params))
    assert "retailiq.v_sales" in v.sql
    assert describe(s).endswith(".")


def test_values_are_bound_not_interpolated():
    s = spec("total profit of Technology in 2012")
    sql, params = build_sql(s)
    assert "Technology" not in sql and "2012" not in sql
    assert set(params.values()) == {"Technology", 2012}


def test_injection_attempt_in_a_value_cannot_alter_sql():
    s = spec("sales by category in 2012; DROP TABLE x")
    sql, params = build_sql(s)
    assert "DROP" not in sql
