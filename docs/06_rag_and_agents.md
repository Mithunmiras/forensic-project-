# Knowledge Base (RAG) and Multi-Agent Orchestration

## The knowledge base
RetailIQ answers questions about itself from its own documentation. The default sources are `README.md` and everything under `docs/` (project overview, architecture, ETL, model methodology, business definitions, the generated data dictionary, verified analytical findings and the generated model report).

### Indexing pipeline
1. **Discovery** - files matching `RAG_SOURCES` are collected. Only `.md`, `.txt`, `.rst` and `.sql` files inside the project are eligible. `.env` files, keys and certificates, model binaries, the virtual environment, `.git`, `node_modules`, caches and the vector store itself are never indexed.
2. **Extraction and cleaning** - text is normalised and anything that looks like a password, token or database URL with credentials is masked.
3. **Chunking** - documents are split at markdown headings, then packed into chunks of about 900 characters with about 150 characters of overlap, keeping the heading path as context.
4. **Embedding** - chunks are embedded with a local MiniLM model (ONNX, via ChromaDB) or an Ollama embedding model. Embeddings are computed once.
5. **Persistence** - vectors are stored in a local ChromaDB collection under `vectorstore/`, with a manifest of document hashes. Starting the server only opens the existing index; documents are re-embedded only when they change (the status page shows when the index is stale).

### Retrieval and answers
- A question is embedded and the most similar chunks are returned with similarity scores. Chunks below a similarity threshold are discarded, so an off-topic question honestly returns "no supporting documents".
- With an LLM available, the answer is written from the numbered passages only and must cite them as [1], [2]; the passages are treated as data, not instructions.
- Without an LLM the answer is **extractive**: the most relevant sentences are shown with their sources, labelled "retrieval-only".
- If embeddings are unavailable the system falls back to **keyword (TF-IDF) retrieval** and says so; keyword matching is never presented as semantic search.

## Multi-agent orchestration
The orchestrator exposes three tools: **SQL** (database analytics), **ML** (sales estimate) and **RAG** (documentation).
- **Routing:** deterministic rules decide which tools are needed; if an LLM is available it can route instead, but its choice is validated and the rule-based choice is reported when they differ.
- **Execution:** each selected tool runs at most once, with a limit on the number of tool calls and an overall time budget. Tools cannot call each other.
- **Failure handling:** each tool returns a status (ok, no results, needs input, unavailable, error, skipped). A failing tool is reported in the response and does not stop the others.
- **Prediction from chat:** order attributes are extracted from the text with deterministic rules (and optionally the LLM). If required information (sub-category, market, quantity) is missing, the answer asks for it instead of guessing; defaults that are applied are listed as assumptions.
- **Answer composition:** measured results (SQL, ML) and documented context (RAG) are written in separate labelled sections. When both are present the answer notes that documentation describes definitions and methodology and does not prove why the measured figures differ. The response lists the tools used, the SQL, the prediction and the document sources.
