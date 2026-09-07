import pandas as pd
from sqlalchemy import create_engine

# Database configuration
DB_USER = "postgres"
DB_PASSWORD = "yogesh123"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "retailiq_db"

# Create connection
engine = create_engine(
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# Load cleaned CSV
df = pd.read_csv("data/processed/superstore_cleaned.csv")

# Insert into PostgreSQL
df.to_sql(
    "superstore",
    engine,
    if_exists="append",
    index=False,
    method="multi"
)

print(f"Successfully inserted {len(df)} rows into PostgreSQL!")