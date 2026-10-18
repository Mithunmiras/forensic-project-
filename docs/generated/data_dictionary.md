# Data Dictionary

_Generated from PostgreSQL on 2026-10-13. The analytics layer and the SQL agent read only the view `retailiq.v_sales` (one row per order line)._

| Column | Type | Meaning | Distinct values | Min | Max |
| --- | --- | --- | --- | --- | --- |
| `row_id` | integer | Unique id of the order line (source system) | 51,290 | 1 | 51290 |
| `order_id` | text | Order identifier; an order has one or more lines | 25,035 |  |  |
| `order_date` | date | Date the order was placed | 1,430 | 2011-01-01 | 2014-12-31 |
| `ship_date` | date | Date the order was shipped | 1,464 | 2011-01-03 | 2015-01-07 |
| `year` | integer | Calendar year of order_date | 4 | 2011 | 2014 |
| `quarter` | integer | Calendar quarter (1-4) of order_date | 4 | 1 | 4 |
| `month` | integer | Calendar month (1-12) of order_date | 12 | 1 | 12 |
| `year_month` | text | order_date formatted as YYYY-MM | 48 |  |  |
| `customer_id` | text | Customer identifier | 4,873 |  |  |
| `customer_name` | text | Customer name | 795 |  |  |
| `segment` | text | Customer segment: Consumer, Corporate or Home Office | 3 |  |  |
| `product_id` | text | Product identifier | 10,292 |  |  |
| `product_name` | text | Product name | 3,788 |  |  |
| `category` | text | Product category: Furniture, Office Supplies or Technology | 3 |  |  |
| `sub_category` | text | Product sub-category (17 values, e.g. Phones, Chairs, Binders) | 17 |  |  |
| `city` | text | Delivery city | 3,636 |  |  |
| `state` | text | Delivery state/province | 1,094 |  |  |
| `country` | text | Delivery country | 147 |  |  |
| `region` | text | Sales region (13 values, e.g. West, Central, Oceania) | 13 |  |  |
| `market` | text | Sales market (7 values: US, EU, APAC, LATAM, EMEA, Africa, Canada) | 7 |  |  |
| `ship_mode` | text | Shipping method: Same Day, First Class, Second Class or Standard Class | 4 |  |  |
| `order_priority` | text | Order priority: Low, Medium, High or Critical | 4 |  |  |
| `quantity` | integer | Units on the order line | 14 | 1 | 14 |
| `discount` | numeric | Discount fraction (0 = none, 0.2 = 20%) | 27 | 0 | 0.85 |
| `sales` | numeric | Sales amount of the order line | 2,246 | 0 | 22638 |
| `profit` | numeric | Profit of the order line (can be negative) | 24,575 | -6599.98 | 8399.98 |
| `shipping_cost` | numeric | Shipping cost of the order line | 16,877 | 0.002 | 933.57 |
| `shipping_days` | integer | Days between order_date and ship_date | 8 | 0 | 7 |

The view contains 51,290 order lines. An order (`order_id`) can have several lines; `row_id` identifies a single line. `shipping_days` = `ship_date` - `order_date`.

## Underlying tables (schema `retailiq`)
- `fact_sales` - one row per order line (grain), keyed by `row_id`; foreign keys to the three dimensions.
- `dim_customer` - customer id, name, segment.
- `dim_product` - product id, name, category, sub-category. `product_id` is not unique in the source data, so the natural key is the full tuple.
- `dim_location` - city, state, country, region, market, market2.
- `etl_runs` - audit record of every ETL execution with row counts and a data-quality report.

Money and discount columns keep the source precision; nothing is rounded during loading.
