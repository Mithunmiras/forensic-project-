SELECT
    DATE_TRUNC('month', order_date) AS month,
    SUM(sales) AS total_sales
FROM retailiq.v_sales
GROUP BY 1
ORDER BY 1;