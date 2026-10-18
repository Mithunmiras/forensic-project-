# RetailIQ - Architecture

## Data flow
1. **ETL**: the raw CSV is read, cleaned, validated and loaded into PostgreSQL (`scripts/run_etl.py`).
2. **PostgreSQL** holds a small star schema in the schema `retailiq`: the fact table `fact_sales` and the dimensions `dim_customer`, `dim_product`, `dim_location`, plus the audit table `etl_runs`. The view `retailiq.v_sales` joins them into one denormalised relation, which is the only thing analytics queries may read.
3. **SQL analytics layer** (`src/analytics`): dashboard aggregations and the natural-language SQL agent, both using a read-only connection.
4. **ML layer** (`src/ml`): trains and compares models, persists the best one together with its evaluation metadata, and serves predictions.
5. **RAG layer** (`src/rag`): discovers project documents, chunks them, embeds the chunks into a persistent ChromaDB collection and retrieves the most relevant passages for a question.
6. **Orchestrator** (`src/agents`): routes a question to the SQL, ML and/or RAG tool, runs each at most once, and composes the answer with provenance.
7. **FastAPI** (`src/api`) exposes everything as a versioned REST API (`/api/v1/...`) and serves the built React frontend.
8. **React frontend** (`frontend/`) provides the dashboard, AI chat, prediction form, knowledge assistant and system-status pages.

## Components and their readiness
The server starts even when a component is missing. `GET /api/v1/system/status` reports, for each of these, whether it is ready and gives the exact command to fix it when it is not:
- **Backend** - always available while the process runs.
- **PostgreSQL** - configured, connected, schema present, data loaded, and whether a dedicated read-only role is in use.
- **ML model** - whether `models/sales_model.joblib` is loaded.
- **Vector store** - not indexed, ready (semantic search) or degraded (keyword fallback).
- **LLM** - optional; reachable and model installed, or not.

Overall status is `ready`, `degraded` (core works, semantic search missing) or `setup_required`.

## Orchestration
The router first uses deterministic rules: prediction requests go to the ML tool; questions about how the project, data or model works go to RAG; measurable questions (totals, rankings, trends) go to SQL; questions that need both figures and explanation (for example "which region performs best and what factors might explain it?") use SQL plus RAG. When an LLM is available it may choose the route instead, but its choice is validated and falls back to the rules. Each tool validates its own input and returns a structured result; a failing tool never stops the others. The orchestrator limits the number of tool calls and the total time, and tools cannot call other tools, so there is no recursion.

## Repository layout
- `src/config.py` - settings from environment variables.
- `src/db/` - engines, health checks, schema administration.
- `src/etl/` - cleaning, validation and loading.
- `src/analytics/` - repository, SQL validator, executor, question parser, SQL agent.
- `src/ml/` - features, training, inference service.
- `src/rag/` - documents, embeddings, vector store, knowledge-base service.
- `src/llm/` - Ollama client.
- `src/agents/` - router, tools, composer, orchestrator.
- `src/api/` - FastAPI app, routes, schemas.
- `database/schema/` - idempotent DDL. `database/sql_queries/` - example analytical SQL.
- `scripts/` - ETL, database setup, training, indexing and Windows PowerShell helpers.
- `tests/` and `frontend/src/**/*.test.tsx` - automated tests.
