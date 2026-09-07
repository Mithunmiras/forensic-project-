# RetailIQ

End-to-end retail analytics and sales-prediction pipeline built on the Global
Superstore dataset (51,290 orders). Raw data is cleaned, loaded into
PostgreSQL, analyzed with SQL and Python (EDA), and used to train regression
models that predict an order's sales value. The best-performing model is
served through a FastAPI endpoint.

## Project layout

```
data/raw/                 Original Global Superstore export
data/processed/           Cleaned dataset (output of src/etl/clean_data.py)
database/schema/          Star-schema DDL (dimension tables; not yet wired to ETL)
database/sql_queries/     Analytical SQL run against the PostgreSQL "superstore" table
src/etl/                  Cleaning and PostgreSQL loading scripts
src/eda/                  matplotlib EDA scripts -> reports/figures/
src/ml/                   Model training scripts (Linear Regression, Decision Tree, Random Forest)
src/api/                  FastAPI app serving the trained Random Forest model
models/                   Trained model artifacts (.pkl) -- generated locally, not stored in git
reports/figures/          Charts produced by the EDA scripts
```

## Setup

```
pip install -r requirements.txt
```

The API additionally requires `fastapi`, `uvicorn`, and `pydantic`, which are
not yet listed in `requirements.txt`:

```
pip install fastapi uvicorn pydantic
```

A local PostgreSQL instance is required for the ETL, SQL analytics, and EDA
steps (the ML training and API steps below only need the CSV files already
committed under `data/`). Connection settings are currently hardcoded in the
individual scripts (`DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`,
`DB_NAME`) — update those in place if your local database differs.

## Reproducing the trained model

`models/*.pkl` is **not** committed to git — the trained Random Forest file
(~100.6 MiB) exceeds GitHub's 100 MiB per-file limit, and both artifacts are
fully reproducible from data and code already in this repository. To
generate them locally:

1. `data/processed/superstore_cleaned.csv` is already committed. If you need
   to regenerate it from the raw export, run from the repo root:
   ```
   python src/etl/clean_data.py
   ```
2. Train and save the model (also from the repo root, so the relative
   `models/` output path resolves correctly):
   ```
   python src/ml/random_forest.py
   ```
   This reads `data/processed/superstore_cleaned.csv`, trains a
   `RandomForestRegressor` (`random_state=42` for reproducible splits), prints
   evaluation metrics (MAE/MSE/RMSE/R²) and feature importances, and writes:
   - `models/random_forest_sales_model.pkl`
   - `models/random_forest_preprocessor.pkl`

   These are the exact two files `src/api/predictor.py` loads at import time.

## Running the API

```
uvicorn src.api.main:app --reload
```

Then `POST /predict` with a JSON body matching `src/api/schemas.py`
(`category`, `sub_category`, `quantity`, `discount`, `shipping_cost`,
`shipping_days`, `market`, `order_priority`, `year`, `weeknum`, `month`,
`quarter`, `day_of_week`) to get back `{"predicted_sales": <float>}`.
