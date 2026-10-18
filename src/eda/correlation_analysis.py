import matplotlib
matplotlib.use("Agg")  # headless: figures are saved, not shown
import matplotlib.pyplot as plt
import pandas as pd

from src.data import load_sales

# Load Data
df = load_sales()

# Numeric columns for correlation
numeric_df = df[
    [
        "sales",
        "profit",
        "discount",
        "quantity",
        "shipping_cost",
        "shipping_days",
    ]
]

# Correlation Matrix
corr = numeric_df.corr()

print("\nCorrelation Matrix:\n")
print(corr)

# Plot Correlation Matrix
plt.figure(figsize=(8, 6))

plt.imshow(corr, cmap="coolwarm", interpolation="nearest")

plt.colorbar()

plt.xticks(range(len(corr.columns)), corr.columns, rotation=45)
plt.yticks(range(len(corr.columns)), corr.columns)

plt.title("Correlation Matrix")

plt.tight_layout()

plt.savefig("reports/figures/correlations/correlation_matrix.png")

plt.close()

print("\nCorrelation analysis completed successfully!")