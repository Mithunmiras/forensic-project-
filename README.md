# RetailIQ

**Hybrid SQL-RAG Multi-Agent Decision Intelligence Platform for Retail Analytics** - an M.Tech (Computer Science with Business Analytics) project built on the Global Superstore dataset (51,290 order lines, 2011-2014).

> **New: RetailIQ Forensic.** A multi-agent forensic analytics platform for retail root-cause investigation. It explains *why* sales moved using structured data and documents together, in four layers: descriptive, diagnostic, predictive, prescriptive. Run `./run_forensic.sh` and open http://127.0.0.1:8000. See [docs/FORENSIC.md](docs/FORENSIC.md).

RetailIQ combines three tools behind one web app and REST API, plus a router that decides which to use:

| Tool | What it does | Source of truth |
| --- | --- | --- |
| **SQL analytics** | dashboards and plain-English questions ("top 10 products by sales") | PostgreSQL (read-only, validated SQL) |
| **ML prediction** | estimate the sales value of one order line, with an 80% interval | trained scikit-learn model |
| **RAG knowledge base** | answers about the project, data and model, with cited sources | the project's own documentation (ChromaDB) |

Everything shown is computed from the database or the trained model. If a component is missing the app says so and shows the command to fix it - it never displays made-up numbers. An LLM is **optional**: without one, built-in question patterns, rule-based routing and retrieval-only answers are used and labelled as such.

## Pages
**Overview** (live KPIs, trend, breakdowns, filters) · **AI Analytics** (chat with evidence, SQL and charts) · **Sales Prediction** (form generated from the model's real inputs, with metrics) · **Knowledge Assistant** (cited answers) · **Data & Model Status** (readiness of every component) · **About**.

## One command
```powershell
.
un.cmd
```
Prepares whatever is missing (dependencies, local PostgreSQL, data load, model, knowledge-base index, dashboard build), starts the server on the first free port from 8000, prints the localhost URL and opens it in your browser. Re-running only does the work that is still missing. Ctrl+C stops it. Use `.
un.cmd -Port 8765` or `-NoBrowser` if needed. (Uses the project-local PostgreSQL unless `DATABASE_URL` in `.env` points to your own.)

## Step-by-step setup (Windows, VS Code, PowerShell)
Run from the project folder. Requirements: Python 3.11+, Node.js 18+, and a PostgreSQL database (your own, or the project-local one below).

```powershell
# 1. Python venv + dependencies + .env + frontend (one time)
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1

# 2. A PostgreSQL database  -- pick ONE:
#    (a) your own PostgreSQL: edit DATABASE_URL in .env, e.g. postgresql://postgres:PASSWORD@localhost:5432/retailiq_db
#    (b) project-local dev database (no install, no admin rights):
powershell -ExecutionPolicy Bypass -File scripts\start_local_postgres.ps1 -UpdateEnv

# 3. Create schema + read-only role, load the data (idempotent; prompts for a read-only password once)
powershell -ExecutionPolicy Bypass -File scripts\run_etl.ps1 -CreateDatabase -CreateReadonlyRole
#    then put the printed DATABASE_READONLY_URL line into .env

# 4. Train the model and build the knowledge-base index
.venv\Scripts\python.exe scripts\train_model.py
.venv\Scripts\python.exe scripts\index_rag.py

# 5. Check everything
powershell -ExecutionPolicy Bypass -File scripts\check_environment.ps1

# 6. Run -- Terminal 1 (API + built dashboard):
powershell -ExecutionPolicy Bypass -File scripts\start_backend.ps1
#    open http://127.0.0.1:8000      (API docs at /docs)
#    Terminal 2 (optional: hot-reload dev UI at http://localhost:5173):
powershell -ExecutionPolicy Bypass -File scripts\start_frontend.ps1
```
Port 8000 busy? `scripts\start_backend.ps1 -Port 8765` and `scripts\start_frontend.ps1 -ApiPort 8765`.
`scripts\dev.ps1` starts both servers and waits until each answers.

### Linux / macOS
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp -n .env.example .env            # then set DATABASE_URL
.venv/bin/python scripts/setup_database.py --create-database
.venv/bin/python scripts/run_etl.py
.venv/bin/python scripts/train_model.py && .venv/bin/python scripts/index_rag.py
(cd frontend && npm install && npm run build)
.venv/bin/python main.py serve --port 8000
```

## Optional: a local LLM (Ollama)
Install [Ollama](https://ollama.com), then `ollama pull llama3.2` (configurable with `OLLAMA_MODEL`). The status page confirms the model is really installed - Ollama being installed is not enough. With it, RetailIQ can write SQL for unusual questions, route with the LLM, and write answers from retrieved passages. Everything is validated the same way as without it.

## Commands
`python main.py <command>`: `serve`, `setup-db`, `etl`, `train`, `index`, `docs`, `eda`, `status`, `dev-db start|stop`. Each maps to a script in `scripts/` (also callable directly).

| Script | Purpose |
| --- | --- |
| `setup_database.py` | schema (+ `--create-database`, `--create-readonly-role`); never drops anything |
| `run_etl.py` | validate + load (idempotent; `--dry-run`, `--update-existing`) |
| `validate_data.py` | data-quality report without a database |
| `train_model.py` | compare models, evaluate, save model + `docs/generated/model_report.md` |
| `index_rag.py` | build/refresh the vector index (only re-embeds changed documents) |
| `generate_docs.py` | regenerate data dictionary + analytical findings from the database |
| `dev_postgres.py` | project-local PostgreSQL 16 on port 54329 (`.pgdata/`, localhost only) |

## Configuration
All settings are environment variables (or `.env`, git-ignored); see `.env.example` for the full documented list. Only `DATABASE_URL` is required. Frontend: `frontend/.env.example`.

| Variable | Default | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | - | privileged connection (schema + ETL) |
| `DATABASE_READONLY_URL` | - | SELECT-only connection for analytics (falls back to `DATABASE_URL`) |
| `FRONTEND_ORIGIN` | `http://localhost:5173` | allowed CORS origin(s) |
| `ADMIN_TOKEN` | - | enables protected re-index / retrain endpoints |
| `LLM_PROVIDER`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | `ollama`, `http://localhost:11434`, `llama3.2` | optional LLM |
| `EMBEDDING_PROVIDER`, `VECTOR_STORE_PATH` | `auto`, `vectorstore` | RAG embeddings / store |
| `MODEL_PATH` | `models/sales_model.joblib` | trained model |

## Models (verified on the held-out 20% test split)
`python scripts/train_model.py` compares a mean baseline, Ridge, Decision Tree, Random Forest and Gradient Boosting by 5-fold cross-validation and reports once on the untouched test set. Two variants are trained because **shipping cost is a proxy of the target** in this dataset (its charges scale with order value):

| Variant | Selected model | Test R² | Test MAE | Test RMSE |
| --- | --- | --- | --- | --- |
| without shipping cost (leakage-safe, **default**) | Gradient Boosting | 0.415 | 151.25 | 399.58 |
| with shipping cost (proxy) | Gradient Boosting | 0.652 | 73.34 | 308.35 |

A mean-only baseline scores R² 0.00 / MAE 262.58. The 80% prediction intervals covered 79% (leakage-safe) and 77% (with shipping cost) of held-out orders. The authoritative figures are regenerated into `docs/generated/model_report.md` on every training run and shown on the Prediction and About pages.

## Tests
```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_tests.ps1       # backend + frontend, honest summary
.venv\Scripts\python.exe -m pytest -q                                 # backend only (needs requirements-dev.txt)
cd frontend; npm run typecheck; npm run lint; npm test; npm run build
```
Integration tests run against a real PostgreSQL: set `RETAILIQ_TEST_DATABASE_URL`, or they use an embedded PostgreSQL 16 from the `pgserver` package. If neither is available they are **skipped with a reason**, not passed.

## Project layout
```
main.py                CLI            scripts/        ETL, DB setup, training, indexing, PowerShell helpers
src/config.py          settings       database/       schema DDL + example SQL
src/db/                engines, schema admin            docs/           knowledge base (+ docs/generated)
src/etl/               clean/validate/load              tests/          pytest (unit + integration)
src/analytics/         repository, SQL validator/agent  frontend/       React + TypeScript + Vite + Tailwind
src/ml/                features, training, serving      data/           raw + processed CSV
src/rag/               documents, embeddings, store     models/         trained model (generated, git-ignored)
src/llm/  src/agents/  Ollama client; router/tools/orchestrator
src/api/               FastAPI app, routes, schemas
```
See `docs/` for architecture, ETL, model methodology, the SQL agent, RAG/agents, metric definitions and security notes.

## Security in short
Read-only DB role + read-only sessions + statement timeout + row cap; SQL parsed and validated on its syntax tree (single SELECT, one view, allow-listed functions); secrets only in environment variables and redacted in logs/status; CORS limited to the configured origin; admin actions need `ADMIN_TOKEN`; indexing skips `.env`, keys, binaries and `.git`.

## Troubleshooting
- **"Setup required" / no figures** - open *Data & Model Status*; it lists the exact command for each missing piece.
- **Port in use** - pass `-Port` (backend) / `-ApiPort` (frontend) to the scripts.
- **Keyword fallback badge in the knowledge assistant** - the local embedding model could not be loaded (first use downloads ~80 MB; needs internet once). Retrieval still works by keywords and says so.
- **`npm` engine warnings on Node 18** - from dev-only lint helpers; the build, lint and tests run on Node 18.
- **Old Postgres password in git history** - earlier commits contained a hardcoded password; treat it as exposed and change it.
