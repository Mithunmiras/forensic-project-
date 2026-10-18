"""Description of the analytics view exposed to dashboards and the SQL agent.

``v_sales`` is the ONLY relation the natural-language SQL agent may query.
"""
from __future__ import annotations

SCHEMA = "retailiq"
VIEW = "v_sales"
QUALIFIED_VIEW = f"{SCHEMA}.{VIEW}"

# (column, type, description)
V_SALES_COLUMNS: list[tuple[str, str, str]] = [
    ("row_id", "integer", "Unique id of the order line (source system)"),
    ("order_id", "text", "Order identifier; an order has one or more lines"),
    ("order_date", "date", "Date the order was placed"),
    ("ship_date", "date", "Date the order was shipped"),
    ("year", "integer", "Calendar year of order_date"),
    ("quarter", "integer", "Calendar quarter (1-4) of order_date"),
    ("month", "integer", "Calendar month (1-12) of order_date"),
    ("year_month", "text", "order_date formatted as YYYY-MM"),
    ("customer_id", "text", "Customer identifier"),
    ("customer_name", "text", "Customer name"),
    ("segment", "text", "Customer segment: Consumer, Corporate or Home Office"),
    ("product_id", "text", "Product identifier"),
    ("product_name", "text", "Product name"),
    ("category", "text", "Product category: Furniture, Office Supplies or Technology"),
    ("sub_category", "text", "Product sub-category (17 values, e.g. Phones, Chairs, Binders)"),
    ("city", "text", "Delivery city"),
    ("state", "text", "Delivery state/province"),
    ("country", "text", "Delivery country"),
    ("region", "text", "Sales region (13 values, e.g. West, Central, Oceania)"),
    ("market", "text", "Sales market (7 values: US, EU, APAC, LATAM, EMEA, Africa, Canada)"),
    ("ship_mode", "text", "Shipping method: Same Day, First Class, Second Class or Standard Class"),
    ("order_priority", "text", "Order priority: Low, Medium, High or Critical"),
    ("quantity", "integer", "Units on the order line"),
    ("discount", "numeric", "Discount fraction (0 = none, 0.2 = 20%)"),
    ("sales", "numeric", "Sales amount of the order line"),
    ("profit", "numeric", "Profit of the order line (can be negative)"),
    ("shipping_cost", "numeric", "Shipping cost of the order line"),
    ("shipping_days", "integer", "Days between order_date and ship_date"),
]
COLUMN_NAMES = [c for c, _, _ in V_SALES_COLUMNS]

# Columns whose distinct values are listed to the LLM so it filters with real spellings.
CATEGORICAL_COLUMNS = ["segment", "category", "sub_category", "region", "market", "ship_mode", "order_priority"]


def schema_prompt(values: dict[str, list[str]] | None = None) -> str:
    """Compact schema text for LLM prompts."""
    lines = [f"Relation: {QUALIFIED_VIEW}  (one row per order line)", "Columns:"]
    for name, typ, desc in V_SALES_COLUMNS:
        lines.append(f"  {name} {typ} - {desc}")
    if values:
        lines.append("Known values:")
        for col, vals in values.items():
            lines.append(f"  {col}: {', '.join(vals)}")
    return "\n".join(lines)
