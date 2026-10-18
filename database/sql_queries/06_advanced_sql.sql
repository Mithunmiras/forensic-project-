/*==========================================================
  ADVANCED SQL  (window functions, CTEs)
==========================================================*/

------------------------------------------------------------
-- 1. Year-over-year sales growth
------------------------------------------------------------
WITH yearly AS (
    SELECT year, SUM(sales) AS total_sales
    FROM retailiq.v_sales
    GROUP BY year
)
SELECT
    year,
    total_sales,
    ROUND(100.0 * (total_sales - LAG(total_sales) OVER (ORDER BY year))
          / LAG(total_sales) OVER (ORDER BY year), 1) AS yoy_growth_pct
FROM yearly
ORDER BY year;


------------------------------------------------------------
-- 2. Cumulative (running) sales by month
------------------------------------------------------------
WITH monthly AS (
    SELECT DATE_TRUNC('month', order_date) AS month, SUM(sales) AS total_sales
    FROM retailiq.v_sales
    GROUP BY 1
)
SELECT
    month,
    total_sales,
    SUM(total_sales) OVER (ORDER BY month) AS running_total
FROM monthly
ORDER BY month;


------------------------------------------------------------
-- 3. Top 3 customers by profit within each segment
------------------------------------------------------------
WITH ranked AS (
    SELECT
        segment,
        customer_name,
        SUM(profit) AS total_profit,
        RANK() OVER (PARTITION BY segment ORDER BY SUM(profit) DESC) AS rnk
    FROM retailiq.v_sales
    GROUP BY segment, customer_name
)
SELECT segment, customer_name, total_profit, rnk
FROM ranked
WHERE rnk <= 3
ORDER BY segment, rnk;


------------------------------------------------------------
-- 4. Profit margin by category and discount band
------------------------------------------------------------
SELECT
    category,
    CASE
        WHEN discount = 0   THEN '0%'
        WHEN discount <= .2 THEN '1-20%'
        WHEN discount <= .5 THEN '21-50%'
        ELSE '50%+'
    END AS discount_band,
    ROUND(100.0 * SUM(profit) / SUM(sales), 1) AS profit_margin_pct,
    COUNT(*) AS order_lines
FROM retailiq.v_sales
GROUP BY category, discount_band
ORDER BY category, MIN(discount);


------------------------------------------------------------
-- 5. Each market's share of total sales
------------------------------------------------------------
SELECT
    market,
    SUM(sales) AS total_sales,
    ROUND(100.0 * SUM(sales) / SUM(SUM(sales)) OVER (), 1) AS share_pct
FROM retailiq.v_sales
GROUP BY market
ORDER BY total_sales DESC;
