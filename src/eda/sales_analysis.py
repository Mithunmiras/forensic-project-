import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import create_engine

engine = create_engine(
    "postgresql://postgres:yogesh123@localhost:5432/retailiq_db"
)

query = """
SELECT
    year,
    SUM(sales) AS total_sales
FROM superstore
GROUP BY year
ORDER BY year;
"""

df = pd.read_sql(query, engine)

plt.figure(figsize=(8,5))
plt.plot(df["year"], df["total_sales"], marker="o")
plt.title("Total Sales by Year")
plt.xlabel("Year")
plt.ylabel("Sales")
plt.grid(True)

plt.savefig("reports/figures/sales_by_year.png")

plt.show()