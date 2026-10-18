# RetailIQ - Project Overview

RetailIQ is a decision-intelligence platform for retail analytics, built as an M.Tech (Computer Science with Business Analytics) project. Its full name is *RetailIQ - Hybrid SQL-RAG Multi-Agent Decision Intelligence Platform for Retail Analytics*.

## What it does
RetailIQ combines three capabilities behind one web application and REST API:

1. **SQL analytics** - dashboards and natural-language questions answered by aggregating the sales data in PostgreSQL.
2. **Machine-learning prediction** - an estimate of the sales value of a single order line, with a prediction interval.
3. **Retrieval-augmented generation (RAG)** - questions about the project, data and model answered from the project's own documentation, with cited sources.

A router (the "multi-agent" layer) decides which of the three tools a question needs, calls them, and combines the evidence. Measured results from the database are always kept separate from explanatory text from the documentation.

## The dataset
The project uses the Global Superstore retail dataset: 51,290 order lines (25,035 orders) from 1 January 2011 to 31 December 2014, covering 4,873 customers, 3 product categories, 17 sub-categories, 7 markets and 147 countries. The raw export is kept in `data/raw/superstore.csv`; the cleaned copy is `data/processed/superstore_cleaned.csv`. No data is generated or replaced - everything shown in the application is computed from this dataset.

## Technology stack
- **Backend:** Python, FastAPI, Uvicorn, Pydantic, SQLAlchemy 2, psycopg 3.
- **Database:** PostgreSQL (schema `retailiq`, read-only role for analytics).
- **ML:** scikit-learn (Gradient Boosting, Random Forest, Decision Tree, Ridge), joblib.
- **RAG:** ChromaDB with a local ONNX MiniLM embedding model; TF-IDF as a labelled fallback.
- **LLM (optional):** a local model served by Ollama. The application works without it.
- **Frontend:** React, TypeScript, Vite, Tailwind CSS, Recharts.

## Design principles
- *No fabricated results*: if a dependency is missing, the application says so and shows how to fix it.
- *Leakage awareness*: the prediction model is offered in two variants because shipping cost is a proxy of the target.
- *Safety*: analytics SQL is validated on its syntax tree and runs read-only with a timeout.
- *Runs locally*: no paid API and no Docker requirement.
