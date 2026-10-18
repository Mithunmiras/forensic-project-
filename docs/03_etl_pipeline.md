# ETL Pipeline

The ETL (`src/etl/pipeline.py`, run with `python scripts/run_etl.py`) moves the Superstore export into PostgreSQL. It is idempotent, transactional and strict about data quality.

## Steps
1. **Extract** - read `data/raw/superstore.csv` (or `--source processed` for the cleaned CSV).
2. **Clean** - drop the constant non-ASCII helper column (the Chinese row-count column), normalise column names to lower snake case, parse `order_date` and `ship_date`, and derive `shipping_days = ship_date - order_date`. Shipping days are only derived when both dates are valid.
3. **Validate** - coerce types and apply business rules. A row is **rejected** (reported, never silently repaired) when it has: a missing required text field; an invalid date; a ship date before the order date; a quantity that is not a positive integer; a discount outside 0 to 1; a negative sales or shipping cost; a missing profit; or a repeated `row_id`.
4. **Load** - validated rows are bulk-copied into a temporary staging table, then dimension rows are upserted on their natural keys and fact rows are inserted with `ON CONFLICT (row_id) DO NOTHING`. The option `--update-existing` also refreshes rows whose values changed.
5. **Record** - every run writes a row to `retailiq.etl_runs` (status, source file and SHA-256, raw / duplicate / rejected / valid / inserted / updated / skipped counts, and a JSON data-quality report). The same report is written to `reports/data_quality_report.json`; rejected rows go to `reports/etl_rejected_rows.csv`.

## Idempotency and safety
- `fact_sales.row_id` is the idempotency key, so running the ETL again inserts 0 new rows and skips all existing ones.
- The load runs in one transaction. If anything fails the transaction rolls back and the failure is recorded in `etl_runs`.
- `--dry-run` validates and reports without touching the database.
- Nothing is dropped or truncated by the ETL or by `setup_database.py`.

## Decisions worth knowing
- **Precision is preserved.** The source contains discounts with three decimals and profit/shipping values with up to five. Columns are `NUMERIC` with enough scale, so totals in PostgreSQL equal totals computed from the CSV exactly.
- **`product_id` is not unique** in the source (10,292 ids map to 10,768 distinct product descriptions), so `dim_product` is keyed on the full tuple (id, name, category, sub-category).
- **Duplicates**: no fully duplicated rows exist in this dataset; `row_id` is unique.
- **Weeks**: the export's `weeknum` follows Tableau's convention (weeks start on Sunday; week 1 contains 1 January). The ML feature code reproduces it exactly.

## Related commands
- `python scripts/validate_data.py` - data-quality summary without a database.
- `python scripts/setup_database.py --create-database --create-readonly-role` - create the database, schema and a SELECT-only role for analytics.
