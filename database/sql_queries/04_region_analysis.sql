/*==========================================================
  REGION ANALYSIS
==========================================================*/

------------------------------------------------------------
-- 1. Sales by Market
------------------------------------------------------------
SELECT
    market,
    SUM(sales) AS total_sales,
    SUM(profit) AS total_profit
FROM superstore
GROUP BY market
ORDER BY total_sales DESC;


------------------------------------------------------------
-- 2. Sales by Region
------------------------------------------------------------
SELECT
    region,
    SUM(sales) AS total_sales,
    SUM(profit) AS total_profit
FROM superstore
GROUP BY region
ORDER BY total_sales DESC;


------------------------------------------------------------
-- 3. Top 10 Countries by Sales
------------------------------------------------------------
SELECT
    country,
    SUM(sales) AS total_sales,
    SUM(profit) AS total_profit
FROM superstore
GROUP BY country
ORDER BY total_sales DESC
LIMIT 10;


------------------------------------------------------------
-- 4. Top 10 States by Sales
------------------------------------------------------------
SELECT
    state,
    SUM(sales) AS total_sales
FROM superstore
GROUP BY state
ORDER BY total_sales DESC
LIMIT 10;


------------------------------------------------------------
-- 5. Top 10 Cities by Sales
------------------------------------------------------------
SELECT
    city,
    SUM(sales) AS total_sales
FROM superstore
GROUP BY city
ORDER BY total_sales DESC
LIMIT 10;


------------------------------------------------------------
-- 6. Most Profitable Markets
------------------------------------------------------------
SELECT
    market,
    SUM(profit) AS total_profit
FROM superstore
GROUP BY market
ORDER BY total_profit DESC;