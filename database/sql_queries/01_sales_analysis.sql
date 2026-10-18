-- 1. Total Sales, Profit and Orders
SELECT
    COUNT(DISTINCT order_id) AS total_orders,
    SUM(sales) AS total_sales,
    SUM(profit) AS total_profit,
    ROUND(AVG(discount),2) AS average_discount
FROM retailiq.v_sales;

-- 2. Average Order Value
SELECT
    ROUND(SUM(sales) / COUNT(DISTINCT order_id),2) AS average_order_value
FROM retailiq.v_sales;

-- 3. Sales by Year
SELECT
    year,
    SUM(sales) AS total_sales,
    SUM(profit) AS total_profit
FROM retailiq.v_sales
GROUP BY year
ORDER BY year;

-- 4. Top 10 Highest Sales Orders
SELECT
    order_id,
    SUM(sales) AS order_sales
FROM retailiq.v_sales
GROUP BY order_id
ORDER BY order_sales DESC
LIMIT 10;

-- 5. Monthly Sales Trend
SELECT
    DATE_TRUNC('month', order_date) AS month,
    SUM(sales) AS total_sales,
    SUM(profit) AS total_profit
FROM retailiq.v_sales
GROUP BY 1
ORDER BY 1;