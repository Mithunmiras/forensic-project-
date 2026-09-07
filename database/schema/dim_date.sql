CREATE TABLE dim_date (
    date_key SERIAL PRIMARY KEY,
    order_date DATE UNIQUE,
    year INTEGER,
    month INTEGER,
    quarter INTEGER,
    week INTEGER,
    day INTEGER
);