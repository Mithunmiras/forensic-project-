import { useQuery } from "@tanstack/react-query";
import { Badge, Card, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { fmtInt } from "../lib/format";

const FLOW = [
  ["Retail CSV", "51,290 order lines"],
  ["ETL", "validate · clean · load"],
  ["PostgreSQL", "star schema + read-only role"],
  ["Tools", "SQL · ML · RAG"],
  ["Orchestrator", "route · combine · cite"],
  ["FastAPI", "versioned REST API"],
  ["React UI", "dashboard · chat · predict"],
];

const STACK: [string, string][] = [
  ["Backend", "Python, FastAPI, Pydantic, SQLAlchemy 2, psycopg 3"],
  ["Database", "PostgreSQL (schema retailiq, read-only analytics role)"],
  ["ML", "scikit-learn: Ridge, Decision Tree, Random Forest, Gradient Boosting"],
  ["RAG", "ChromaDB + local ONNX MiniLM embeddings, TF-IDF fallback"],
  ["LLM", "Optional local model via Ollama (the app works without it)"],
  ["Frontend", "React, TypeScript, Vite, Tailwind CSS, Recharts"],
];

export default function About() {
  const meta = useQuery({ queryKey: ["ml-metadata"], queryFn: api.mlMetadata, retry: false, staleTime: 10 * 60_000 });
  const v = meta.data?.variants[meta.data.default_variant];
  const full = meta.data?.variants["with_shipping_cost"];
  return (
    <>
      <PageHeader title="About RetailIQ" subtitle="Hybrid SQL-RAG multi-agent decision intelligence platform for retail analytics - M.Tech Computer Science with Business Analytics." />
      <div className="space-y-6">
        <Card title="Architecture">
          <ol className="flex flex-wrap items-stretch gap-2" aria-label="Data flow">
            {FLOW.map(([title, sub], i) => (
              <li key={title} className="flex items-center gap-2">
                <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                  <p className="text-sm font-semibold text-slate-900">{title}</p>
                  <p className="text-xs text-slate-500">{sub}</p>
                </div>
                {i < FLOW.length - 1 && <span aria-hidden="true" className="text-slate-400">→</span>}
              </li>
            ))}
          </ol>
          <p className="mt-4 text-sm text-slate-600">
            A router decides whether a question needs measured figures from the database (SQL), an estimate from the trained model (ML), or an answer from the project documentation (RAG) - or a combination. Measured results and documented context are always shown separately, with their evidence.
          </p>
        </Card>

        <div className="grid gap-6 lg:grid-cols-2">
          <Card title="Methodology">
            <ul className="list-disc space-y-2 pl-5 text-sm text-slate-700">
              <li><strong>ETL</strong> validates every row, rejects (never silently repairs) invalid ones, and loads idempotently in one transaction.</li>
              <li><strong>SQL agent</strong> turns questions into parameterised SQL, validates it on its syntax tree, and runs it read-only with a timeout.</li>
              <li><strong>ML</strong> compares a mean baseline, Ridge, Decision Tree, Random Forest and Gradient Boosting by 5-fold cross-validation, then reports once on a held-out 20%.</li>
              <li><strong>Leakage</strong>: shipping cost scales with order value, so two variants exist and the leakage-safe one is the default.</li>
              <li><strong>RAG</strong> chunks the project documents, embeds them locally, retrieves by meaning plus keywords, and cites sources.</li>
            </ul>
          </Card>
          <Card title="Technology stack">
            <dl className="divide-y divide-slate-100">
              {STACK.map(([k, val]) => (
                <div key={k} className="flex gap-4 py-2 text-sm"><dt className="w-24 shrink-0 font-semibold text-slate-800">{k}</dt><dd className="text-slate-600">{val}</dd></div>
              ))}
            </dl>
          </Card>
        </div>

        <Card title="Verified model evaluation" hint="Read live from the trained model's metadata - not typed in.">
          {meta.isLoading && <p className="text-sm text-slate-500">Loading...</p>}
          {meta.isError && <p className="text-sm text-slate-600">The model is not available, so no evaluation can be shown. See System status.</p>}
          {meta.data && v && full && (
            <div className="space-y-3 text-sm text-slate-700">
              <p>
                Target: <strong>{meta.data.target.name}</strong> - {meta.data.target.definition} Trained on {fmtInt(meta.data.dataset.rows)} order lines; random {Math.round((1 - meta.data.split.test_size) * 100)}/{Math.round(meta.data.split.test_size * 100)} split (seed {meta.data.split.random_state}); {meta.data.split.cv_folds}-fold cross-validation for model selection.
              </p>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-lg bg-slate-50 p-4"><Badge tone="teal">default · leakage-safe</Badge><p className="mt-2 text-2xl font-bold">R² {v.test_metrics.r2.toFixed(3)}</p><p className="text-xs text-slate-500">{v.best_model} · MAE {v.test_metrics.mae.toFixed(2)} · RMSE {v.test_metrics.rmse.toFixed(2)}</p></div>
                <div className="rounded-lg bg-slate-50 p-4"><Badge tone="amber">with shipping cost (proxy)</Badge><p className="mt-2 text-2xl font-bold">R² {full.test_metrics.r2.toFixed(3)}</p><p className="text-xs text-slate-500">{full.best_model} · MAE {full.test_metrics.mae.toFixed(2)} · RMSE {full.test_metrics.rmse.toFixed(2)}</p></div>
              </div>
              <p className="text-xs text-slate-500">Hold-out test metrics. The with-shipping-cost accuracy is higher because shipping charges scale with order value in this dataset, not because the model understands demand better.</p>
            </div>
          )}
        </Card>

        <p className="text-xs text-slate-500">
          API reference: <a className="font-semibold text-brand-700 underline" href="/docs">/docs</a> (OpenAPI).
        </p>
      </div>
    </>
  );
}
