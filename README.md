# RetailIQ Forensic: multi-agent root-cause investigation

RetailIQ Forensic answers retail business questions the way a forensic analyst would. It does not stop at "sales fell 17%". It explains **why**, using structured data (sales, inventory, suppliers) and unstructured documents (supplier reports, QC reports, memos, customer feedback) together. Every answer has four layers:

| Layer | Question | Produced by |
|---|---|---|
| Descriptive | What happened? | SQL / NoSQL agent → synthesis |
| Diagnostic | Why did it happen? | RAG agent + RCA agent → synthesis |
| Predictive | What happens next? | Forecast agent → synthesis |
| Prescriptive | What should we do? | Synthesis agent only |

Each claim carries a citation `[n]` pointing at a specific table slice, model or document file.

## Run it (localhost, no Streamlit)

```bash
./run_forensic.sh
```

The script creates `.venv`, installs `requirements-dev.txt`, builds the React dashboard (`forensic_ui/`, needs Node 18+), generates the synthetic data, and serves everything at **http://127.0.0.1:8000**. API docs are at `/docs`. Use `--port 8765` if port 8000 is busy. If it is, the server automatically picks the next free port.

Manual steps:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
(cd forensic_ui && npm install && npm run build)
.venv/bin/python -m forensic generate        # synthetic data from forensic/scenarios.py
.venv/bin/python -m forensic serve           # http://127.0.0.1:8000
```

Other commands:

```bash
.venv/bin/python -m forensic ask "Why did iPhone 15 sales drop in the North region in March 2026?"
.venv/bin/python -m forensic evaluate        # score against ground truth
.venv/bin/python -m pytest
```

UI development with hot reload: run `serve` in one terminal and `cd forensic_ui && npm run dev` in another. The UI is then at http://localhost:5173 and proxies `/api` to port 8000.

## Deploy to Vercel

The repo is ready for Vercel as is. `vercel.json` builds the React dashboard as static files, and `api/index.py` serves the FastAPI backend as a Python serverless function for every `/api/*` route.

1. Go to https://vercel.com/new and import this GitHub repository.
2. Leave all settings at their defaults (they come from `vercel.json`) and click **Deploy**.

Or deploy from the terminal with `npx vercel` (first time) and `npx vercel --prod`.

The backend is built for the serverless constraints:
* It writes nothing to disk. SQLite is built in memory from the committed CSVs on cold start (about 1 s).
* Runtime dependencies are only numpy, pandas, FastAPI and uvicorn, about 140 MB unpacked against Vercel's 250 MB function limit. TF-IDF retrieval and Holt-Winters forecasting are implemented in numpy rather than with scikit-learn and statsmodels, for this reason.

## Architecture

```
question → Orchestrator ─┬─ SQL / NoSQL Analytics Agent ─┐
                         ├─ RAG Agent           (parallel)├→ Forecast / RCA Agent → Synthesis / XAI Agent → answer
                         └───────────────────────────────┘
```

| Agent | File | What it does |
|---|---|---|
| Orchestrator | `forensic/agents/orchestrator.py` | Extracts product (aliases), region, month (`March 2026`, `2026-03`, `mar`), intent and direction. Anything missing is filled by scanning for the most anomalous matching product/region/month, and the plan records how each field was decided. |
| SQL / NoSQL Analytics | `forensic/agents/sql_agent.py` | Deterministic SQLite queries over `sales`, `inventory`, `products`, `suppliers`, plus a lookup in the catalog document store (`catalog.json`: nested product → primary/backup suppliers). Every query is returned for audit. No LLM. |
| RAG | `forensic/agents/rag_agent.py` | Paragraph chunks with a TF-IDF (1–2 gram) vector index, implemented in numpy (`forensic/textindex.py`). The metadata filter runs first (product, region or company-wide, and a date window from 21 days before the month to its end), then ranking blends similarity and metadata. Each document is classified as **incident** (with a cause), **routine** (status report that rules causes out) or **reference** (policy). Near misses that were filtered out are reported. |
| Forecast / RCA | `forensic/agents/rca_agent.py`, `forensic/metrics.py` | Robust z-score against a leave-one-out median baseline (MAD scale with a floor). Detects the structured signature: stock-out, returns spike, discount, price, demand up or down. Checks whether the change is local or market-wide. Forecasts the next month with Holt-Winters (damped trend, weekly seasonality; numpy implementation in `forensic/holtwinters.py`, parameters chosen by grid search), alongside "if the cause persists" and a held-out back-test. |
| Synthesis / XAI | `forensic/agents/synthesis_agent.py` | Fuses the evidence. A document only explains an anomaly if its cause is compatible with the structured signature (a stock-out fits a supplier delay or logistics disruption, not a discount). Writes all four layers with citations, computes confidence, and is the only agent that writes recommendations. |

The pipeline lives in `forensic/pipeline.py` and the API in `forensic/api.py`.

## Graceful degradation

| Situation | Behaviour | Confidence |
|---|---|---|
| Structured anomaly + compatible document | Full answer, both cited | High |
| Structured anomaly only | "No supporting unstructured evidence was found; the root cause is inferred from data patterns only." | Medium |
| Document only (numbers normal, or no sales data at all) | "Sales data for this period does not show a statistically significant deviation; this issue may not yet be materially affecting sales." | Medium |
| Neither | "No anomaly detected and no related documents found for this product/period." | High (that nothing happened) |
| Document conflicts with the data | Data-pattern cause; document flagged as unconfirmed | Medium |

The demo data covers every row: **HomePod mini** has sales but no documents, and **Vision Pro** has documents but no sales.

## Synthetic data (scenario-first)

`forensic/scenarios.py` defines 18 incident scenarios and 6 controls. From each scenario, `forensic/generate.py` derives both:

* the **structured signature**: units change, stock-out days (inventory goes to 0 and the monthly loss is concentrated on those days), discount, price and returns changes;
* the **unstructured artefact**: the document a person would have written, with a JSON sidecar (`product_id`, `doc_type`, `date`, `region`).

Both use the shared keys `product_id`, `region` and month. All other months are baseline demand plus a weekday pattern plus noise. Routine documents (quarterly QC summaries, supplier status, feedback summaries) and policy documents are added as distractors.

Output: `data/structured/{products,sales,inventory,suppliers}.csv`, `data/structured/catalog.json`, `data/forensic.sqlite` and `data/unstructured/<PRODUCT>/*.txt`. That is 6,552 daily sales rows, 6,552 inventory rows and 78 documents (16 incidents). Generation is deterministic (seed 42).

Cause types: supplier delay, logistics disruption, quality issue, return-policy change, promotion, price increase, competitor launch, marketing campaign. Also covered: an unexplained demand drop and an unexplained stock-out (no document), and an early supplier warning that has not yet affected sales.

## Evaluation (verified on this machine)

`python -m forensic evaluate` replays every scenario's question through the full pipeline:

| Metric | Result |
|---|---|
| Correct root cause (18 scenarios) | 18/18 |
| No invented cause (6 controls) | 6/6 |
| Correct document cited | 16/16 |
| Correct evidence case | 24/24 |
| Correct confidence label | 24/24 |
| Correct product/region/month extracted | 24/24 |

Across the whole grid (6 products × 4 regions × 9 months = 216 cells), the 16 injected anomalies are flagged and none of the 200 normal cells is. `tests/` (14 tests) checks all of this.

## Honest limitations

* The data is synthetic and the documents follow a fixed vocabulary. The keyword cause classifier and the TF-IDF retriever work well here, but real documents will need a sentence-transformer embedding (Chroma or FAISS slots in behind `RAGAgent._similarity`) and a learned or LLM classifier.
* Entity extraction and answer writing are deterministic templates, chosen for reproducibility and auditability. An LLM could rephrase the synthesis, but it must not be allowed to add uncited claims.
* Attribution between several simultaneous causes is by signature priority (supply > returns > discount > price > demand), not by a causal model.
* "Forecast if the cause persists" is a scenario (the month's deviation carried forward), not a fitted model.
