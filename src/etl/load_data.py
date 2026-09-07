import pandas as pd

# Load dataset
df = pd.read_csv("data/raw/superstore.csv")

print("Shape:", df.shape)

# Check missing values
print("\nMissing Values:")
print(df.isnull().sum())

# Check duplicate rows
print("\nDuplicate Rows:", df.duplicated().sum())

# Dataset information
print("\nDataset Info:")
df.info()

# Basic statistics
print("\nStatistics:")
print(df.describe())

# Unique values in each column
print("\nUnique Values:")
print(df.nunique())