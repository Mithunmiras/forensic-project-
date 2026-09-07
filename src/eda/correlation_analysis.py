import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import create_engine

# Database Connection
engine = create_engine(
    "postgresql://postgres:yogesh123@localhost:5432/retailiq_db"
)

# Load Data
df = pd.read_sql("SELECT * FROM superstore", engine)

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

plt.show()

print("\nCorrelation analysis completed successfully!")