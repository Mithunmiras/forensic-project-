-- RetailIQ analytical schema. Idempotent: safe to run any number of times,
-- never drops or alters existing data. Everything lives in its own schema so
-- an existing "public" schema (e.g. the legacy flat "superstore" table) is untouched.

CREATE SCHEMA IF NOT EXISTS retailiq;

-- One row per ETL execution (audit trail + data-quality record).
CREATE TABLE IF NOT EXISTS retailiq.etl_runs (
    run_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    status          TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
    source_file     TEXT NOT NULL,
    source_sha256   TEXT,
    raw_rows        INTEGER,
    duplicate_rows  INTEGER,
    rejected_rows   INTEGER,
    valid_rows      INTEGER,
    inserted_rows   INTEGER,
    updated_rows    INTEGER,
    skipped_rows    INTEGER,
    quality_report  JSONB,
    error_message   TEXT
);

CREATE TABLE IF NOT EXISTS retailiq.dim_customer (
    customer_key   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id    TEXT NOT NULL UNIQUE,
    customer_name  TEXT NOT NULL,
    segment        TEXT NOT NULL
);

-- product_id is NOT unique in the source data (the same id appears with
-- different names), so the natural key is the full descriptive tuple.
CREATE TABLE IF NOT EXISTS retailiq.dim_product (
    product_key   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_id    TEXT NOT NULL,
    product_name  TEXT NOT NULL,
    category      TEXT NOT NULL,
    sub_category  TEXT NOT NULL,
    UNIQUE (product_id, product_name, category, sub_category)
);

CREATE TABLE IF NOT EXISTS retailiq.dim_location (
    location_key  INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    city          TEXT NOT NULL,
    state         TEXT NOT NULL,
    country       TEXT NOT NULL,
    region        TEXT NOT NULL,
    market        TEXT NOT NULL,
    market2       TEXT NOT NULL,
    UNIQUE (city, state, country, region, market, market2)
);

-- Monetary/ratio columns keep the source precision (the export has 3-decimal
-- discounts and up to 5-decimal profit/shipping values) - nothing is rounded.
-- Grain: one order line. row_id is the source system's unique line id and is
-- the idempotency key for re-loading.
CREATE TABLE IF NOT EXISTS retailiq.fact_sales (
    row_id          INTEGER PRIMARY KEY,
    order_id        TEXT NOT NULL,
    customer_key    INTEGER NOT NULL REFERENCES retailiq.dim_customer (customer_key),
    product_key     INTEGER NOT NULL REFERENCES retailiq.dim_product (product_key),
    location_key    INTEGER NOT NULL REFERENCES retailiq.dim_location (location_key),
    order_date      DATE NOT NULL,
    ship_date       DATE NOT NULL,
    ship_mode       TEXT NOT NULL,
    order_priority  TEXT NOT NULL,
    quantity        INTEGER NOT NULL CHECK (quantity > 0),
    discount        NUMERIC(7, 4) NOT NULL CHECK (discount >= 0 AND discount <= 1),
    sales           NUMERIC(16, 4) NOT NULL,
    profit          NUMERIC(16, 5) NOT NULL,
    shipping_cost   NUMERIC(14, 5) NOT NULL CHECK (shipping_cost >= 0),
    shipping_days   INTEGER NOT NULL CHECK (shipping_days >= 0),
    etl_run_id      BIGINT REFERENCES retailiq.etl_runs (run_id),
    CHECK (ship_date >= order_date)
);

CREATE INDEX IF NOT EXISTS idx_fact_sales_order_date   ON retailiq.fact_sales (order_date);
CREATE INDEX IF NOT EXISTS idx_fact_sales_order_id     ON retailiq.fact_sales (order_id);
CREATE INDEX IF NOT EXISTS idx_fact_sales_customer     ON retailiq.fact_sales (customer_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_product      ON retailiq.fact_sales (product_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_location     ON retailiq.fact_sales (location_key);
CREATE INDEX IF NOT EXISTS idx_fact_sales_ship_mode    ON retailiq.fact_sales (ship_mode);
CREATE INDEX IF NOT EXISTS idx_dim_product_category    ON retailiq.dim_product (category, sub_category);
CREATE INDEX IF NOT EXISTS idx_dim_location_region     ON retailiq.dim_location (region);
CREATE INDEX IF NOT EXISTS idx_dim_location_market     ON retailiq.dim_location (market);
CREATE INDEX IF NOT EXISTS idx_dim_location_country    ON retailiq.dim_location (country);

-- Denormalised, read-only view. This is the ONLY relation the analytics
-- layer and the natural-language SQL agent are allowed to query.
CREATE OR REPLACE VIEW retailiq.v_sales AS
SELECT
    f.row_id,
    f.order_id,
    f.order_date,
    f.ship_date,
    EXTRACT(YEAR FROM f.order_date)::int      AS year,
    EXTRACT(QUARTER FROM f.order_date)::int   AS quarter,
    EXTRACT(MONTH FROM f.order_date)::int     AS month,
    to_char(f.order_date, 'YYYY-MM')          AS year_month,
    c.customer_id,
    c.customer_name,
    c.segment,
    p.product_id,
    p.product_name,
    p.category,
    p.sub_category,
    l.city,
    l.state,
    l.country,
    l.region,
    l.market,
    f.ship_mode,
    f.order_priority,
    f.quantity,
    f.discount,
    f.sales,
    f.profit,
    f.shipping_cost,
    f.shipping_days
FROM retailiq.fact_sales f
JOIN retailiq.dim_customer c ON c.customer_key = f.customer_key
JOIN retailiq.dim_product  p ON p.product_key  = f.product_key
JOIN retailiq.dim_location l ON l.location_key = f.location_key;
