# Business Metric Definitions

These are the exact definitions used by the dashboard and the SQL agent. They describe how RetailIQ computes each figure from the order-line data; they are not company policies.

- **Order line** - one product on one order. The data has 51,290 order lines belonging to 25,035 orders.
- **Total sales** - the sum of `sales` over the selected order lines.
- **Total profit** - the sum of `profit`. Profit can be negative for a line.
- **Profit margin** - total profit divided by total sales for the selected lines, shown as a percentage. It is not the average of line margins.
- **Orders** - the number of distinct `order_id` values (not the number of lines).
- **Average order value (AOV)** - total sales divided by the number of distinct orders.
- **Average discount** - the mean of the line-level `discount` fraction, shown as a percentage. It is not weighted by sales.
- **Units / quantity** - the sum of `quantity`.
- **Customers** - the number of distinct `customer_id` values.
- **Shipping days** - `ship_date` minus `order_date` in days. **Average shipping days** is the mean over the selected lines.
- **Shipping cost** - the shipping charge recorded for the order line.
- **Category and sub-category** - the product hierarchy: 3 categories (Furniture, Office Supplies, Technology) and 17 sub-categories.
- **Region, market and country** - the delivery geography: 13 regions, 7 markets (US, EU, APAC, LATAM, EMEA, Africa, Canada) and 147 countries.
- **Customer segment** - Consumer, Corporate or Home Office.
- **Order priority** - Low, Medium, High or Critical.
- **Discount bands** - profitability is analysed by line discount: none, up to 10%, 10-20%, 20-30%, 30-50% and over 50%.
- **Period comparison** - when a date range is selected, the dashboard can compare it with the immediately preceding period of the same length.
- **Year-over-year growth** - sales in a year divided by sales in the previous year, minus one.

Currency units are those of the dataset; the data does not state a currency, so figures are shown with a `$` sign for readability only.
