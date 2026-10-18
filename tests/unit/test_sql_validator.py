import pytest

from src.analytics.sql_validator import UnsafeSQL, validate_select

GOOD = [
    "SELECT category, SUM(sales) AS s FROM retailiq.v_sales GROUP BY 1 ORDER BY 2 DESC LIMIT 5",
    "SELECT category, SUM(sales) FROM v_sales GROUP BY category",
    "WITH x AS (SELECT category, SUM(sales) AS s FROM v_sales GROUP BY 1) SELECT * FROM x ORDER BY s DESC",
    "SELECT EXTRACT(YEAR FROM order_date) AS y, date_trunc('month', order_date) m, to_char(order_date,'YYYY-MM') ym, "
    "CAST(sales AS INT), COALESCE(profit,0), ROUND(AVG(discount)*100,2), COUNT(DISTINCT order_id), "
    "CASE WHEN sales>1 THEN 1 ELSE 0 END FROM v_sales GROUP BY 1,2,3,4,5",
    "SELECT row_number() OVER (PARTITION BY category ORDER BY sales DESC) rn, LAG(sales) OVER (ORDER BY order_date) FROM v_sales",
    "SELECT category FROM v_sales UNION ALL SELECT sub_category FROM v_sales",
    "SELECT a.category, b.region FROM v_sales a JOIN v_sales b ON a.row_id = b.row_id",
    "SELECT (SELECT max(sales) FROM v_sales) AS m",
    "SELECT 1 /* harmless comment */",
    "SELECT * FROM v_sales WHERE product_name LIKE '%phone%'",
]

BAD = {
    "DROP TABLE retailiq.fact_sales": "not_a_query",
    "DELETE FROM v_sales": "not_a_query",
    "UPDATE v_sales SET sales = 0": "not_a_query",
    "INSERT INTO v_sales VALUES (1)": "not_a_query",
    "TRUNCATE v_sales": "not_a_query",
    "CREATE TABLE x AS SELECT 1": "not_a_query",
    "GRANT ALL ON v_sales TO public": "not_a_query",
    "COPY v_sales TO '/tmp/x'": "not_a_query",
    "SET ROLE postgres": "not_a_query",
    "EXPLAIN ANALYZE SELECT 1": "not_a_query",
    "SELECT 1; DROP TABLE x": "multiple_statements",
    "SELECT * FROM v_sales; SELECT 1": "multiple_statements",
    "WITH d AS (DELETE FROM v_sales RETURNING *) SELECT * FROM d": "forbidden_construct",
    "SELECT * INTO t FROM v_sales": "forbidden_construct",
    "SELECT * FROM v_sales FOR UPDATE": "forbidden_construct",
    "SELECT * FROM (VALUES (1)) AS t(x)": "forbidden_construct",
    "SELECT pg_sleep(5)": "forbidden_function",
    "SELECT set_config('a','b',false)": "forbidden_function",
    "SELECT lo_import('/etc/passwd')": "forbidden_function",
    "SELECT pg_read_file('x')": "forbidden_function",
    "SELECT version()": "forbidden_function",
    "SELECT current_user": "forbidden_function",
    "SELECT * FROM generate_series(1,10)": "forbidden_table",
    "SELECT * FROM retailiq.fact_sales": "forbidden_table",
    "SELECT * FROM retailiq.dim_customer": "forbidden_table",
    "SELECT * FROM information_schema.tables": "forbidden_table",
    "SELECT * FROM pg_catalog.pg_user": "forbidden_table",
    "SELECT * FROM v_sales UNION ALL SELECT * FROM pg_catalog.pg_user": "forbidden_table",
    "SELECT * FROM public.superstore": "forbidden_table",
    "SELECT * FROM other.v_sales": "forbidden_table",
    "SELECT ctid FROM v_sales": "unknown_column",
    "SELECT nonexistent FROM v_sales": "unknown_column",
    "SELECT x.category FROM v_sales": "unknown_table_alias",
    "SELECT * FROM v_sales WHERE category = :p0": "parameters_not_allowed",
    "SELECT * FROM v_sales LIMIT :n": "parameters_not_allowed",
    "": "empty",
    "   ": "empty",
}


@pytest.mark.parametrize("sql", GOOD)
def test_accepts_safe_queries(sql):
    v = validate_select(sql, max_rows=500)
    assert v.effective_limit <= 501
    assert "retailiq.v_sales" in v.sql or "v_sales" not in sql


@pytest.mark.parametrize("sql,code", list(BAD.items()))
def test_rejects_unsafe_queries(sql, code):
    with pytest.raises(UnsafeSQL) as exc:
        validate_select(sql, max_rows=500)
    assert exc.value.code == code


def test_limit_is_injected_and_capped():
    assert validate_select("SELECT * FROM v_sales", max_rows=100).effective_limit == 101
    assert validate_select("SELECT * FROM v_sales", max_rows=100).truncated_possible
    small = validate_select("SELECT * FROM v_sales LIMIT 5", max_rows=100)
    assert small.effective_limit == 5 and not small.truncated_possible
    assert validate_select("SELECT * FROM v_sales LIMIT 99999", max_rows=100).effective_limit == 101


def test_union_gets_a_limit_too():
    v = validate_select("SELECT category FROM v_sales UNION ALL SELECT sub_category FROM v_sales", max_rows=50)
    assert v.sql.rstrip().endswith("LIMIT 51")


def test_executed_sql_is_regenerated_without_comments():
    v = validate_select("SELECT category FROM v_sales -- sneaky\n /* more */", max_rows=10)
    assert "sneaky" not in v.sql and "more" not in v.sql


def test_declared_parameters_are_allowed():
    v = validate_select("SELECT * FROM v_sales WHERE category = :p0 LIMIT 3", max_rows=100, allowed_params={"p0"})
    assert "%(p0)s" in v.sql
    with pytest.raises(UnsafeSQL):
        validate_select("SELECT * FROM v_sales WHERE category = :other", max_rows=100, allowed_params={"p0"})


def test_overlong_and_complex_statements_rejected():
    with pytest.raises(UnsafeSQL) as exc:
        validate_select("SELECT 1 " + "+ 1 " * 3000, max_rows=10)
    assert exc.value.code in {"too_long", "too_complex"}


def test_non_integer_limit_rejected():
    with pytest.raises(UnsafeSQL):
        validate_select("SELECT * FROM v_sales LIMIT (SELECT 5)", max_rows=10)
