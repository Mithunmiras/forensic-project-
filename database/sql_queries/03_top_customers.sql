SELECT
    customer_name,
    SUM(sales) AS total_sales,
    SUM(profit) AS total_profit
FROM retailiq.v_sales
GROUP BY customer_name
ORDER BY total_sales DESC
LIMIT 10;