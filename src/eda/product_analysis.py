import matplotlib
matplotlib.use("Agg")  # headless: figures are saved, not shown
import matplotlib.pyplot as plt
import pandas as pd

from src.data import load_sales

# Load Data
df = load_sales()

# -------------------------------
# 1. Sales by Category
# -------------------------------
category_sales = (
    df.groupby("category")["sales"]
    .sum()
    .sort_values(ascending=False)
)

plt.figure(figsize=(8,5))
category_sales.plot(kind="bar")
plt.title("Sales by Category")
plt.xlabel("Category")
plt.ylabel("Total Sales")
plt.xticks(rotation=0)
plt.tight_layout()
plt.savefig("reports/figures/products/sales_by_category.png")
plt.close()

# -------------------------------
# 2. Profit by Category
# -------------------------------
category_profit = (
    df.groupby("category")["profit"]
    .sum()
    .sort_values(ascending=False)
)

plt.figure(figsize=(8,5))
category_profit.plot(kind="bar")
plt.title("Profit by Category")
plt.xlabel("Category")
plt.ylabel("Total Profit")
plt.xticks(rotation=0)
plt.tight_layout()
plt.savefig("reports/figures/products/profit_by_category.png")
plt.close()

# -------------------------------
# 3. Top 10 Products by Sales
# -------------------------------
top_products = (
    df.groupby("product_name")["sales"]
    .sum()
    .sort_values(ascending=False)
    .head(10)
)

plt.figure(figsize=(10,6))
top_products.plot(kind="bar")
plt.title("Top 10 Products by Sales")
plt.xlabel("Product")
plt.ylabel("Total Sales")
plt.xticks(rotation=60, ha="right")
plt.tight_layout()
plt.savefig("reports/figures/products/top10_products_sales.png")
plt.close()

# -------------------------------
# 4. Sales by Sub-Category
# -------------------------------
subcategory_sales = (
    df.groupby("sub_category")["sales"]
    .sum()
    .sort_values(ascending=False)
)

plt.figure(figsize=(10,6))
subcategory_sales.plot(kind="bar")
plt.title("Sales by Sub-Category")
plt.xlabel("Sub-Category")
plt.ylabel("Total Sales")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
plt.savefig("reports/figures/products/sales_by_subcategory.png")
plt.close()

print("Product EDA completed successfully!")