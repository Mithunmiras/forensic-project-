import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Badge, Card, ErrorState, PageHeader, Skeleton, Spinner } from "../components/ui";
import { useSystemStatus } from "../hooks";
import { api } from "../lib/api";
import { fmtDateTime, fmtInt } from "../lib/format";

function Row({ k, children }: { k: string; children: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 py-1.5 text-sm">
      <dt className="text-slate-500">{k}</dt>
      <dd className="text-right font-medium text-slate-800">{children}</dd>
    </div>
  );
}

const COMPONENT_LABEL: Record<string, string> = { database: "PostgreSQL", etl: "ETL", model: "Prediction model", vector_store: "Vector index", llm: "LLM" };

const yes = (b: boolean, ok = "yes", no = "no") => <Badge tone={b ? "green" : "red"}>{b ? ok : no}</Badge>;

function CopyCmd({ text }: { text: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      className="ml-2 rounded border border-slate-300 px-1.5 py-0.5 text-[11px] font-medium text-slate-600 hover:bg-slate-100"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setDone(true);
          setTimeout(() => setDone(false), 1500);
        } catch {
          /* clipboard unavailable */
        }
      }}
    >
      {done ? "copied" : "copy"}
    </button>
  );
}

/** Pull the shell command out of an instruction like "Index the documents: python scripts/index_rag.py". */
function commandOf(action: string): string | null {
  const m = action.match(/:\s*((?:python|\.\\|scripts\\|ollama)[^\n]+)$/);
  return m ? m[1].trim() : null;
}

function AdminActions() {
  const qc = useQueryClient();
  const [token, setToken] = useState("");
  const reindex = useMutation({ mutationFn: (force: boolean) => api.reindex(token, force), onSuccess: () => qc.invalidateQueries({ queryKey: ["system-status"] }) });
  const retrain = useMutation({ mutationFn: () => api.retrain(token), onSuccess: () => qc.invalidateQueries() });
  return (
    <Card title="Administrative actions" hint="Protected by ADMIN_TOKEN (set in .env). The token is kept only in this page's memory.">
      <div className="grid gap-3 sm:grid-cols-[1fr_auto_auto_auto] sm:items-end">
        <div>
          <label htmlFor="admin-token" className="label">Admin token</label>
          <input id="admin-token" type="password" autoComplete="off" className="input" value={token} onChange={(e) => setToken(e.target.value)} placeholder="X-Admin-Token" />
        </div>
        <button type="button" className="btn-secondary" disabled={!token || reindex.isPending} onClick={() => reindex.mutate(false)}>Re-index docs</button>
        <button type="button" className="btn-secondary" disabled={!token || reindex.isPending} onClick={() => reindex.mutate(true)}>Force rebuild</button>
        <button type="button" className="btn-secondary" disabled={!token || retrain.isPending} onClick={() => retrain.mutate()}>Retrain model</button>
      </div>
      <div className="mt-3 space-y-1 text-sm" aria-live="polite">
        {(reindex.isPending || retrain.isPending) && <Spinner label={retrain.isPending ? "Retraining (about 30 seconds)..." : "Indexing..."} />}
        {reindex.isSuccess && <p className="text-emerald-700">Index: {String(reindex.data.status).replace(/_/g, " ")} ({String(reindex.data.chunks)} passages).</p>}
        {retrain.isSuccess && <p className="text-emerald-700">Model retrained.</p>}
        {reindex.isError && <ErrorState error={reindex.error} />}
        {retrain.isError && <ErrorState error={retrain.error} />}
      </div>
    </Card>
  );
}

export default function Status() {
  const { data: s, isLoading, isError, error, refetch, isFetching } = useSystemStatus(15_000);

  return (
    <>
      <PageHeader
        title="Data & model status"
        subtitle="Live readiness of every component. Missing pieces never crash the app - the features that need them say what to do."
        actions={<button type="button" className="btn-secondary" onClick={() => refetch()} disabled={isFetching}>{isFetching ? "Checking..." : "Refresh"}</button>}
      />
      {isLoading && <div className="grid gap-4 md:grid-cols-2">{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-48" />)}</div>}
      {isError && <ErrorState error={error} onRetry={() => refetch()} />}
      {s && (
        <div className="space-y-6">
          <div
            role="status"
            className={`rounded-xl border p-4 text-sm font-semibold ${s.overall === "ready" ? "border-emerald-200 bg-emerald-50 text-emerald-800" : s.overall === "degraded" ? "border-amber-200 bg-amber-50 text-amber-900" : "border-rose-200 bg-rose-50 text-rose-800"}`}
          >
            {s.overall === "ready" && "Everything is ready."}
            {s.overall === "degraded" && "The core is running; semantic search is unavailable so keyword fallback is in use."}
            {s.overall === "setup_required" && "Setup is required before the dashboard can show data - follow the steps below."}
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card title="PostgreSQL" actions={yes(s.database.connected, "connected", "not connected")}>
              <dl className="divide-y divide-slate-100">
                <Row k="Configured">{yes(s.database.configured)}</Row>
                <Row k="Schema ready">{yes(s.database.schema_ready)}</Row>
                <Row k="Rows in sales view">{fmtInt(s.database.fact_rows)}</Row>
                <Row k="Read-only role in use">{yes(s.database.readonly_role)}</Row>
                <Row k="Server">{s.database.server_version ? `PostgreSQL ${s.database.server_version}` : "n/a"}</Row>
                <Row k="Connection"><span className="break-all text-xs">{s.database.url ?? "not configured"}</span></Row>
              </dl>
              {s.database.error && <p className="mt-2 rounded bg-rose-50 p-2 text-xs text-rose-700">{s.database.error}</p>}
            </Card>

            <Card title="Last ETL run" actions={s.database.last_etl_run ? <Badge tone={s.database.last_etl_run.status === "succeeded" ? "green" : "red"}>{s.database.last_etl_run.status}</Badge> : <Badge>none</Badge>}>
              {s.database.last_etl_run ? (
                <dl className="divide-y divide-slate-100">
                  <Row k="Finished">{fmtDateTime(s.database.last_etl_run.finished_at)}</Row>
                  <Row k="Raw rows">{fmtInt(s.database.last_etl_run.raw_rows)}</Row>
                  <Row k="Valid rows">{fmtInt(s.database.last_etl_run.valid_rows)}</Row>
                  <Row k="Rejected rows">{fmtInt(s.database.last_etl_run.rejected_rows)}</Row>
                  <Row k="Inserted / skipped">{fmtInt(s.database.last_etl_run.inserted_rows)} / {fmtInt(s.database.last_etl_run.skipped_rows)}</Row>
                </dl>
              ) : (
                <p className="text-sm text-slate-500">No ETL run recorded yet.</p>
              )}
              <div className="mt-3 border-t border-slate-100 pt-3 text-xs text-slate-500">
                {Object.entries(s.datasets).map(([k, d]) => (
                  <p key={k}>{d.exists ? "✓" : "✗"} {d.path}</p>
                ))}
              </div>
            </Card>

            <Card title="Prediction model" actions={yes(s.model.ready, "loaded", "not loaded")}>
              <dl className="divide-y divide-slate-100">
                <Row k="Trained">{fmtDateTime(s.model.trained_at)}</Row>
                <Row k="Default variant">{s.model.default_variant?.replace(/_/g, " ") ?? "n/a"}</Row>
                {s.model.variants && Object.entries(s.model.variants).map(([v, m]) => <Row key={v} k={v.replace(/_/g, " ")}>{m}</Row>)}
              </dl>
              {s.model.error && <p className="mt-2 rounded bg-rose-50 p-2 text-xs text-rose-700">{s.model.error}</p>}
            </Card>

            <Card title="Vector index (RAG)" actions={<Badge tone={s.vector_store.state === "ready" ? "green" : s.vector_store.state === "degraded" ? "amber" : "red"}>{s.vector_store.state.replace(/_/g, " ")}</Badge>}>
              <dl className="divide-y divide-slate-100">
                <Row k="Documents / passages">{s.vector_store.documents} / {s.vector_store.chunks}</Row>
                <Row k="Retrieval mode">{s.vector_store.retrieval_mode.replace(/_/g, " ")}</Row>
                <Row k="Embedding model">{s.vector_store.embedder ?? "none"}</Row>
                <Row k="Indexed">{fmtDateTime(s.vector_store.indexed_at)}</Row>
                <Row k="Up to date">{yes(!s.vector_store.stale, "yes", "stale - re-index")}</Row>
              </dl>
              {s.vector_store.hint && <p className="mt-2 rounded bg-amber-50 p-2 text-xs text-amber-800">{s.vector_store.hint}</p>}
            </Card>

            <Card title="LLM (optional)" actions={yes(s.llm.available, "available", "not available")}>
              <dl className="divide-y divide-slate-100">
                <Row k="Provider">{s.llm.provider}</Row>
                <Row k="Model">{s.llm.model ?? "n/a"}</Row>
                <Row k="Server reachable">{yes(s.llm.reachable)}</Row>
                <Row k="Model installed">{yes(s.llm.model_present)}</Row>
              </dl>
              {!s.llm.available && <p className="mt-2 rounded bg-slate-50 p-2 text-xs text-slate-600">{s.llm.error} {s.llm.hint} Without an LLM the app uses built-in question patterns, rule-based routing and retrieval-only answers.</p>}
            </Card>

            <Card title="Backend">
              <dl className="divide-y divide-slate-100">
                <Row k="API">{yes(s.backend.available, "available")}</Row>
                <Row k="Version">{s.backend.version}</Row>
                <Row k="Environment">{s.backend.environment}</Row>
                <Row k="Server time">{fmtDateTime(s.backend.time)}</Row>
              </dl>
            </Card>
          </div>

          {s.setup_steps.length > 0 && (
            <Card title="Setup steps" hint="Run these in a terminal from the project folder, then Refresh.">
              <ol className="space-y-3">
                {s.setup_steps.map((step) => {
                  const cmd = commandOf(step.action);
                  return (
                    <li key={step.component + step.action} className="flex flex-wrap items-start gap-2 text-sm">
                      <Badge tone={step.required === "yes" ? "red" : "slate"}>{step.required === "yes" ? "required" : "optional"}</Badge>
                      <span className="font-semibold">{COMPONENT_LABEL[step.component] ?? step.component.replace(/_/g, " ")}</span>
                      <span className="text-slate-600">{step.action}{cmd && <CopyCmd text={cmd} />}</span>
                    </li>
                  );
                })}
              </ol>
            </Card>
          )}
          <AdminActions />
        </div>
      )}
    </>
  );
}
