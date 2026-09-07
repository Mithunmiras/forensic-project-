from sqlalchemy import create_engine

DB_USER = "postgres"
DB_PASSWORD = "yogesh123"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "retailiq_db"

engine = create_engine(
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

try:
    with engine.connect() as conn:
        print("Connected successfully!")
except Exception as e:
    print(e)