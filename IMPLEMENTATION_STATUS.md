# RetailIQ - Implementation Status

_Last verified: 2026-10-13 on Windows 11, Python 3.11, Node 18, PostgreSQL 16.2. "Verified" means it was actually executed here._

## Result
All ten phases are implemented. Backend: **317 tests pass**. Frontend: TypeScript, ESLint, **43 tests** and the production build pass. `scripts\run_tests.ps1` reproduces this and prints a per-stage summary.

## Phase checklist
- [x] 1. Inspection - existing CSVs, ETL, flat Postgres loader, FastAPI `/predict`, three training scripts and a vanilla-JS page were reviewed; datasets and cleaned CSV preserved byte-for-byte (clean output re-verified identical).
- [x] 2. Configuration, database layer, schema - env-driven settings, idempotent `retailiq` schema (star schema + `v_sales` view + `etl_runs`), read-only role setup, secret redaction.
- [x] 3. ETL - validation, reject reporting, idempotent transactional load, audit table, data-quality report.
- [x] 4. ML - baseline + 4 models, CV selection, hold-out evaluation, two variants (leakage), quantile intervals, schema-driven inputs, protected retrain.
- [x] 5. SQL analytics + SQL agent - SQL aggregations, template parser, LLM path, AST validator, read-only execution.
- [x] 6. RAG - discovery, chunking, local embeddings, ChromaDB persistence, hybrid retrieval, citations, TF-IDF fallback.
- [x] 7. Orchestrator + API - rule/LLM router, three isolated tools, composer, versioned FastAPI API.
- [x] 8. Frontend - React/TS/Vite/Tailwind/Recharts, six pages, live API client.
- [x] 9. Tests / security - see below.
- [x] 10. Scripts, docs, final verification.

## Verified facts
| Item | Result |
| --- | --- |
| ETL (first run) | raw 51,290 / valid 51,290 / rejected 0 / duplicates 0 / inserted 51,290 |
| ETL (second run) | inserted 0, skipped 51,290 (idempotent) |
| DB vs CSV | sales 12,642,905 and profit 1,467,457.29128 match exactly; 25,035 orders; 4,873 customers; 10,768 products; 3,819 locations |
| Rollback | a simulated crash after insert leaves 0 rows and records `failed` in `etl_runs` |
| Read-only role | can SELECT `v_sales`; DELETE / UPDATE / INSERT / CREATE and direct table reads are refused |
| Model (leakage-safe, default) | Gradient Boosting - test R2 0.415, MAE 151.25, RMSE 399.58 (mean baseline R2 0.00, MAE 262.58) |
| Model (with shipping cost) | Gradient Boosting - test R2 0.652, MAE 73.34, RMSE 308.35 |
| 80% intervals | empirical hold-out coverage 79.0% (safe) / 77.2% (with shipping cost) |
| Unsafe SQL | 35 adversarial statements rejected by the AST validator; 7 hostile LLM-written statements rejected end to end and the data stayed untouched |
| Example SQL | all 39 queries in `database/sql_queries/` run on PostgreSQL (this found and fixed a real `GROUP BY month` ambiguity) |
| RAG | 13 documents / 115 passages indexed semantically; off-topic questions return no sources; re-index and restart both work |
| UI | Overview, AI Analytics (SQL + docs combined), Prediction, Status driven in a headless browser against the live API |
| Offline / not-set-up | server starts with nothing configured; status reports each gap; UI shows setup screens with no figures |

## Known limitations and blocked items
- **Ollama is not installed on this machine**, so no real local LLM was run. LLM paths (LLM-written SQL, LLM routing, LLM answers) are tested with a scripted stand-in and the Ollama client against a mocked HTTP server. The no-LLM mode (templates, rules, extractive answers) ran end to end. To enable: install Ollama, `ollama pull llama3.2`.
- **PostgreSQL is not installed system-wide.** Everything was verified on an embedded PostgreSQL 16.2 (`pgserver`, project-local on port 54329). The SQL is standard; run `scripts\setup_database.py` against your own server to confirm in your environment.
- The embedding model (~80 MB) downloads on first use; offline machines fall back to keyword retrieval, which is labelled as such.
- Prediction accuracy is moderate by nature of the data: shipping cost is a proxy of sales, so the leakage-safe model reaches R2 about 0.41.
- The original hardcoded database password still exists in git history. Rotate it.
- Nothing has been committed; all changes are in the working tree.
- `npm` prints engine warnings on Node 18 for two dev-only lint helper packages; lint, tests and build all run on Node 18.
