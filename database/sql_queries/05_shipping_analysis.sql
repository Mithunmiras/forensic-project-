/*==========================================================
  SHIPPING ANALYSIS
==========================================================*/

------------------------------------------------------------
-- 1. Average Shipping Days
------------------------------------------------------------
SELECT
    ROUND(AVG(shipping_days),2) AS avg_shipping_days
FROM retailiq.v_sales;


------------------------------------------------------------
-- 2. Average Shipping Days by Ship Mode
------------------------------------------------------------
SELECT
    ship_mode,
    ROUND(AVG(shipping_days),2) AS avg_shipping_days
FROM retailiq.v_sales
GROUP BY ship_mode
ORDER BY avg_shipping_days;


------------------------------------------------------------
-- 3. Total Shipping Cost by Ship Mode
------------------------------------------------------------
SELECT
    ship_mode,
    SUM(shipping_cost) AS total_shipping_cost
FROM retailiq.v_sales
GROUP BY ship_mode
ORDER BY total_shipping_cost DESC;


------------------------------------------------------------
-- 4. Orders by Ship Mode
------------------------------------------------------------
SELECT
    ship_mode,
    COUNT(*) AS total_orders
FROM retailiq.v_sales
GROUP BY ship_mode
ORDER BY total_orders DESC;


------------------------------------------------------------
-- 5. Average Shipping Cost per Order
------------------------------------------------------------
SELECT
    ROUND(AVG(shipping_cost),2) AS avg_shipping_cost
FROM retailiq.v_sales;


------------------------------------------------------------
-- 6. Highest Shipping Cost Orders
------------------------------------------------------------
SELECT
    order_id,
    customer_name,
    shipping_cost
FROM retailiq.v_sales
ORDER BY shipping_cost DESC
LIMIT 10;