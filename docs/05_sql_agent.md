# Natural-Language SQL Analytics

The SQL agent (`src/analytics/sql_agent.py`) answers questions such as "Which product categories generate the most sales?" or "What is the monthly sales trend?" with real queries against PostgreSQL.

## How a question becomes SQL
1. **Built-in patterns (default strategy `template_first`).** A deterministic parser recognises a metric (sales, profit, orders, quantity, customers, average discount, profit margin, average order value, shipping days, shipping cost), an optional dimension (category, sub-category, region, market, country, state, city, segment, ship mode, order priority, product, customer, month, quarter, year), filters (a year or year range, and category/region/market values named in the question), ordering (highest/lowest) and a limit (for example "top 10"). The SQL is assembled from whitelisted fragments and all values are bind parameters.
2. **LLM (optional).** If the question is not recognised and an LLM is available, the model is given the schema and the known categorical values and asked for one SELECT statement as JSON. With `SQL_AGENT_STRATEGY=llm_first` the LLM is asked first and the patterns act as the fallback. If the model's SQL is rejected or fails, it gets one chance to correct it.
3. If neither path works, the answer says so and lists example questions that are supported. Nothing is invented.

## Safety layers
Every statement - whether built-in or written by an LLM - must pass the validator in `src/analytics/sql_validator.py`, which parses the SQL into a syntax tree rather than scanning for keywords:
- exactly one statement, and it must be a query (SELECT, a set operation, or WITH ... SELECT);
- no INSERT/UPDATE/DELETE/DDL/COPY/SET/GRANT or other utility statements anywhere (including inside a CTE), no `SELECT ... INTO`, no `FOR UPDATE`;
- only the view `retailiq.v_sales` (and CTEs defined in the same statement) may be referenced - no other tables, `information_schema` or `pg_catalog`, no table functions;
- only allow-listed functions (aggregates, rounding, date and text helpers, window functions) - `pg_sleep`, `set_config`, `lo_*`, `version()` and similar are rejected;
- only real columns of the view (or aliases) - system columns such as `ctid` are rejected;
- query parameters are refused unless the trusted built-in builder declared them;
- a hard row limit is injected and the statement that runs is regenerated from the validated syntax tree, not the original text.

At run time the query uses the read-only connection (a dedicated `retailiq_readonly` role when configured), a read-only transaction, a statement timeout and a row cap. Database errors and timeouts are returned as clear messages.

## Output
The response contains the SQL that was executed, the bind parameters, an explanation, the column names and types, the rows, whether the result was truncated, the elapsed time, a chart suggestion (line for time series, bar for rankings) and which method (template or LLM) produced it.
