import matplotlib
matplotlib.use("Agg")  # headless: figures are saved, not shown
import matplotlib.pyplot as plt

from src.data import load_sales

df = load_sales().groupby("year", as_index=False)["sales"].sum().rename(columns={"sales": "total_sales"})

plt.figure(figsize=(8, 5))
plt.plot(df["year"], df["total_sales"], marker="o")
plt.title("Total Sales by Year")
plt.xlabel("Year")
plt.ylabel("Sales")
plt.xticks(df["year"])
plt.grid(True)
plt.savefig("reports/figures/sales_by_year.png")
plt.close()

print("Sales EDA completed successfully!")
