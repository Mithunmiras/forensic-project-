# Security, Reliability and Limits

## Database access
- Two connections: a privileged one (`DATABASE_URL`) used only by schema setup and the ETL, and a read-only one (`DATABASE_READONLY_URL`) used by dashboards and the SQL agent. The read-only role `retailiq_readonly` can only SELECT from the view `retailiq.v_sales` and the ETL log; it cannot read the fact or dimension tables directly or modify anything.
- Read-only sessions also set `default_transaction_read_only`, run each query in a read-only transaction and apply a statement timeout (`QUERY_TIMEOUT_MS`) and a row cap (`MAX_RESULT_ROWS`).
- If no read-only URL is configured, the privileged URL is reused but the session is still read-only and time-limited; the status page reports that no dedicated read-only role is in use.
- Credentials come only from environment variables or the git-ignored `.env`; they are redacted in logs and status output. The browser never receives database access.

## API safeguards
- Request bodies are validated with Pydantic, unknown fields are rejected, and numeric ranges are enforced. Errors use one consistent JSON shape with a code, message and optional field details.
- CORS allows only the configured frontend origin(s) (`FRONTEND_ORIGIN`).
- Administrative actions (rebuilding the vector index, retraining the model) require the `X-Admin-Token` header matching `ADMIN_TOKEN`; if no token is configured they are disabled.
- The server does not crash when PostgreSQL, the model, the vector store or the LLM is unavailable; dependent features answer with a clear 503 and a hint.

## Untrusted content
Text from the dataset and from documents is treated as data. LLM prompts state that retrieved passages and user questions are not instructions. The assistant has no shell, file or network tools. Generated SQL is validated on its syntax tree before it can run, and indexing never reads files outside the project or secret files.

## Reliability and logging
Each tool in the orchestrator is isolated: one failure is reported while the others still run. Operational events are logged with request ids, route and tool statuses; passwords and tokens are masked, and questions are not logged.

## Known limits
- The LLM-dependent features (LLM-written SQL, LLM-written answers, LLM routing) need a local Ollama model; without it the built-in patterns, extractive answers and rule-based routing are used and labelled as such.
- The sales model reaches moderate accuracy: sales values are heavy-tailed and order attributes alone explain only part of the variation (see the model report).
- The knowledge base covers the project's own documentation only; it does not know anything about a real company's policies.
