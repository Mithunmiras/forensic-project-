# Running RetailIQ

The step-by-step commands are in the top-level README. This page records what the project was verified against and what each component needs.

## Verified environment
- Windows 11, Python 3.11, Node.js 18, PostgreSQL 16.2 (embedded build used for testing), scikit-learn 1.9, SQLAlchemy 2.1, psycopg 3.3, FastAPI 0.143, ChromaDB 1.5, React 18, Vite 5, Tailwind CSS 3, Recharts 3.
- Ollama was not installed on the verification machine, so every LLM-dependent path was tested with a scripted stand-in model and the real Ollama integration was tested against a mocked HTTP server. The no-LLM mode is what ran end to end.

## What each component needs
| Component | Needs | If missing |
| --- | --- | --- |
| Dashboard / SQL analytics | PostgreSQL with the ETL loaded | the pages show a setup screen with the exact commands, never figures |
| Sales prediction | `models/sales_model.joblib` (`python scripts/train_model.py`) | the Prediction page shows a setup screen |
| Knowledge assistant | the vector index (`python scripts/index_rag.py`); the first run downloads the ~80 MB embedding model | keyword (TF-IDF) fallback, labelled as such |
| LLM features | Ollama and `ollama pull llama3.2` | built-in question patterns, rule-based routing, retrieval-only answers |

Re-run `python scripts/index_rag.py` after editing any document under `docs/` or the README; the status page shows when the index is stale.
