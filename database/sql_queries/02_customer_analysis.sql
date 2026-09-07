-- 1. Top 10 Customers by Sales
SELECT
    customer_name,
    SUM(sales) AS total_sales,
    SUM(profit) AS total_profit
FROM superstore
GROUP BY customer_name
ORDER BY total_sales DESC
LIMIT 10;

------------------------------------------------

-- 2. Top 10 Customers by Profit
SELECT
    customer_name,
    SUM(profit) AS total_profit
FROM superstore
GROUP BY customer_name
ORDER BY total_profit DESC
LIMIT 10;

------------------------------------------------

-- 3. Sales by Customer Segment
SELECT
    segment,
    COUNT(DISTINCT customer_id) AS customers,
    SUM(sales) AS total_sales,
    SUM(profit) AS total_profit
FROM superstore
GROUP BY segment;

------------------------------------------------

-- 4. Average Sales per Customer
SELECT
    customer_name,
    ROUND(AVG(sales),2) AS average_sales
FROM superstore
GROUP BY customer_name
ORDER BY average_sales DESC
LIMIT 10;

------------------------------------------------

-- 5. Customers with More Than 10 Orders
SELECT
    customer_name,
    COUNT(DISTINCT order_id) AS total_orders
FROM superstore
GROUP BY customer_name
HAVING COUNT(DISTINCT order_id) > 10
ORDER BY total_orders DESC;