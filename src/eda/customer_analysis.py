import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import create_engine

# Database Connection
engine = create_engine(
    "postgresql://postgres:yogesh123@localhost:5432/retailiq_db"
)

# Load Data
df = pd.read_sql("SELECT * FROM superstore", engine)

# -------------------------------
# 1. Top 10 Customers by Sales
# -------------------------------
top_customers = (
    df.groupby("customer_name")["sales"]
    .sum()
    .sort_values(ascending=False)
    .head(10)
)

plt.figure(figsize=(10, 6))
top_customers.plot(kind="bar")
plt.title("Top 10 Customers by Sales")
plt.xlabel("Customer Name")
plt.ylabel("Total Sales")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
plt.savefig("reports/figures/customers/top10_customers_sales.png")
plt.show()

# -------------------------------
# 2. Sales by Customer Segment
# -------------------------------
segment_sales = df.groupby("segment")["sales"].sum()

plt.figure(figsize=(6, 6))
segment_sales.plot(kind="pie", autopct="%1.1f%%")
plt.ylabel("")
plt.title("Sales Distribution by Customer Segment")
plt.tight_layout()
plt.savefig("reports/figures/customers/customer_segment_sales.png")
plt.show()

# -------------------------------
# 3. Top 10 Customers by Profit
# -------------------------------
top_profit = (
    df.groupby("customer_name")["profit"]
    .sum()
    .sort_values(ascending=False)
    .head(10)
)

plt.figure(figsize=(10, 6))
top_profit.plot(kind="bar")
plt.title("Top 10 Customers by Profit")
plt.xlabel("Customer Name")
plt.ylabel("Total Profit")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
plt.savefig("reports/figures/customers/top10_customers_profit.png")
plt.show()

print("Customer EDA completed successfully!")