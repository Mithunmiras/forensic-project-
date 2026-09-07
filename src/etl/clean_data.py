import pandas as pd

# Load data
df = pd.read_csv("data/raw/superstore.csv")

# Remove unnecessary column
df.drop(columns=["记录数"], inplace=True)

# Rename columns
df.columns = (
    df.columns
    .str.lower()
    .str.replace(".", "_", regex=False)
    .str.replace(" ", "_")
)

# Convert date columns
df["order_date"] = pd.to_datetime(df["order_date"])
df["ship_date"] = pd.to_datetime(df["ship_date"])

# Create a new feature: shipping days
df["shipping_days"] = (df["ship_date"] - df["order_date"]).dt.days

# Save cleaned dataset
df.to_csv("data/processed/superstore_cleaned.csv", index=False)

print("Cleaning completed successfully!")
print(df.head())
print("\nShape:", df.shape)
print("\nColumns:")
print(df.columns.tolist())