CREATE TABLE dim_product (
    product_key SERIAL PRIMARY KEY,
    product_id VARCHAR(50),
    product_name TEXT,
    category VARCHAR(50),
    sub_category VARCHAR(50)
);