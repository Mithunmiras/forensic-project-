CREATE TABLE dim_location (
    location_key SERIAL PRIMARY KEY,
    city VARCHAR(100),
    state VARCHAR(100),
    country VARCHAR(100),
    region VARCHAR(100),
    market VARCHAR(100),
    market2 VARCHAR(100)
);