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
# 1. Sales by Market
# -------------------------------
market_sales = (
    df.groupby("market")["sales"]
    .sum()
    .sort_values(ascending=False)
)

plt.figure(figsize=(8,5))
market_sales.plot(kind="bar")
plt.title("Sales by Market")
plt.xlabel("Market")
plt.ylabel("Total Sales")
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig("reports/figures/regions/sales_by_market.png")
plt.show()

# -------------------------------
# 2. Profit by Region
# -------------------------------
region_profit = (
    df.groupby("region")["profit"]
    .sum()
    .sort_values(ascending=False)
)

plt.figure(figsize=(10,6))
region_profit.plot(kind="bar")
plt.title("Profit by Region")
plt.xlabel("Region")
plt.ylabel("Total Profit")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
plt.savefig("reports/figures/regions/profit_by_region.png")
plt.show()

# -------------------------------
# 3. Top 10 Countries by Sales
# -------------------------------
country_sales = (
    df.groupby("country")["sales"]
    .sum()
    .sort_values(ascending=False)
    .head(10)
)

plt.figure(figsize=(10,6))
country_sales.plot(kind="bar")
plt.title("Top 10 Countries by Sales")
plt.xlabel("Country")
plt.ylabel("Total Sales")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
plt.savefig("reports/figures/regions/top10_countries_sales.png")
plt.show()

# -------------------------------
# 4. Top 10 Cities by Sales
# -------------------------------
city_sales = (
    df.groupby("city")["sales"]
    .sum()
    .sort_values(ascending=False)
    .head(10)
)

plt.figure(figsize=(10,6))
city_sales.plot(kind="bar")
plt.title("Top 10 Cities by Sales")
plt.xlabel("City")
plt.ylabel("Total Sales")
plt.xticks(rotation=45, ha="right")
plt.tight_layout()
plt.savefig("reports/figures/regions/top10_cities_sales.png")
plt.show()

print("Region EDA completed successfully!")