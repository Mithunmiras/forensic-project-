"""Quick data-quality report on the raw export.

    python -m src.etl.load_data
"""
import pandas as pd

from src.config import RAW_CSV

df = pd.read_csv(RAW_CSV)

print("Shape:", df.shape)

print("\nMissing Values:")
print(df.isnull().sum())

print("\nDuplicate Rows:", df.duplicated().sum())

print("\nDataset Info:")
df.info()

print("\nStatistics:")
print(df.describe())

print("\nUnique Values:")
print(df.nunique())
