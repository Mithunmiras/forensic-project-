SELECT
    product_name,
    SUM(sales) AS total_sales
FROM retailiq.v_sales
GROUP BY product_name
ORDER BY total_sales DESC
LIMIT 10;