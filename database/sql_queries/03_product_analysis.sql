/*==========================================================
  PRODUCT ANALYSIS
==========================================================*/

------------------------------------------------------------
-- 1. Top 10 Products by Sales
------------------------------------------------------------
SELECT
    product_name,
    category,
    sub_category,
    SUM(sales) AS total_sales
FROM retailiq.v_sales
GROUP BY product_name, category, sub_category
ORDER BY total_sales DESC
LIMIT 10;


------------------------------------------------------------
-- 2. Top 10 Products by Profit
------------------------------------------------------------
SELECT
    product_name,
    category,
    SUM(profit) AS total_profit
FROM retailiq.v_sales
GROUP BY product_name, category
ORDER BY total_profit DESC
LIMIT 10;


------------------------------------------------------------
-- 3. Bottom 10 Products by Profit (Loss Making)
------------------------------------------------------------
SELECT
    product_name,
    category,
    SUM(profit) AS total_profit
FROM retailiq.v_sales
GROUP BY product_name, category
ORDER BY total_profit ASC
LIMIT 10;


------------------------------------------------------------
-- 4. Sales and Profit by Category
------------------------------------------------------------
SELECT
    category,
    SUM(sales) AS total_sales,
    SUM(profit) AS total_profit,
    ROUND(AVG(discount),2) AS avg_discount
FROM retailiq.v_sales
GROUP BY category
ORDER BY total_sales DESC;


------------------------------------------------------------
-- 5. Sales and Profit by Sub-Category
------------------------------------------------------------
SELECT
    sub_category,
    SUM(sales) AS total_sales,
    SUM(profit) AS total_profit
FROM retailiq.v_sales
GROUP BY sub_category
ORDER BY total_sales DESC;


------------------------------------------------------------
-- 6. Most Frequently Ordered Products
------------------------------------------------------------
SELECT
    product_name,
    COUNT(*) AS total_orders,
    SUM(quantity) AS total_quantity
FROM retailiq.v_sales
GROUP BY product_name
ORDER BY total_orders DESC
LIMIT 10;


------------------------------------------------------------
-- 7. Average Discount by Category
------------------------------------------------------------
SELECT
    category,
    ROUND(AVG(discount),2) AS average_discount
FROM retailiq.v_sales
GROUP BY category
ORDER BY average_discount DESC;