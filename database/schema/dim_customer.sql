CREATE TABLE dim_customer (
    customer_key SERIAL PRIMARY KEY,
    customer_id VARCHAR(30) UNIQUE NOT NULL,
    customer_name VARCHAR(150),
    segment VARCHAR(50)
);