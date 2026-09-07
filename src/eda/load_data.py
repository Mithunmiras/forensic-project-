import pandas as pd
from sqlalchemy import create_engine

engine = create_engine(
    "postgresql://postgres:yogesh123@localhost:5432/retailiq_db"
)

df = pd.read_sql("SELECT * FROM superstore", engine)

print(df.head())
print(df.shape)