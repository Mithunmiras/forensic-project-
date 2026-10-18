import { useState } from "react";
import { fmtCell, fmtMoney2, fmtMoney, titleCase } from "../lib/format";
import type { PredictionResponse, QueryResponse, Source } from "../lib/types";
import { ResultChart } from "./charts";
import { Badge, CodeBlock, DataTable } from "./ui";

export function ConfidenceBadge({ level }: { level: Source["confidence"] }) {
  const tone = level === "high" ? "green" : level === "medium" ? "amber" : "red";
  return <Badge tone={tone} title="How well the passage matches the question">{level} match</Badge>;
}

export function SourceList({ sources }: { sources: Source[] }) {
  return (
    <ol className="space-y-3">
      {sources.map((s) => (
        <li key={s.id} className="rounded-lg border border-slate-200 bg-slate-50/60 p-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="flex h-5 w-5 items-center justify-center rounded bg-brand-600 text-[11px] font-bold text-white">{s.id}</span>
            <span className="text-sm font-semibold text-slate-800">{s.source}</span>
            <ConfidenceBadge level={s.confidence} />
            <span className="text-xs text-slate-500">score {s.score.toFixed(2)}</span>
          </div>
          <p className="mt-1 text-xs text-slate-500">{s.heading}</p>
          <p className="mt-1.5 text-sm text-slate-700">{s.snippet}</p>
        </li>
      ))}
    </ol>
  );
}

export function SqlEvidence({ result }: { result: QueryResponse }) {
  const [showSql, setShowSql] = useState(false);
  if (result.status !== "ok") return null;
  const cols = result.columns.map((c) => c.name);
  const numeric = result.columns.map((c) => c.type === "number");
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
        <Badge tone={result.method === "llm" ? "indigo" : "teal"}>{result.method === "llm" ? "SQL written by LLM" : "Built-in query pattern"}</Badge>
        <span>{result.row_count} rows</span>
        {result.elapsed_ms != null && <span>{result.elapsed_ms.toFixed(0)} ms</span>}
        {result.truncated && <Badge tone="amber">truncated</Badge>}
      </div>
      {result.chart && <ResultChart {...result.chart} columns={result.columns} rows={result.rows} />}
      <DataTable
        columns={cols.map(titleCase)}
        align={numeric.map((n) => (n ? "right" : "left"))}
        rows={result.rows.slice(0, 50).map((r) => r.map((v, i) => fmtCell(cols[i], v)))}
      />
      {result.rows.length > 50 && <p className="text-xs text-slate-500">Showing the first 50 of {result.row_count} rows.</p>}
      {result.notes.map((n) => (
        <p key={n} className="text-xs text-slate-500">
          {n}
        </p>
      ))}
      {result.sql && (
        <div>
          <button type="button" className="text-xs font-semibold text-brand-700 underline" aria-expanded={showSql} onClick={() => setShowSql((s) => !s)}>
            {showSql ? "Hide" : "Show"} the SQL that was executed
          </button>
          {showSql && (
            <div className="mt-2 space-y-2">
              <CodeBlock>{result.sql}</CodeBlock>
              {Object.keys(result.params).length > 0 && <CodeBlock label="Bind parameters">{JSON.stringify(result.params)}</CodeBlock>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function PredictionSummary({ p }: { p: PredictionResponse }) {
  const span = p.upper_bound - p.lower_bound;
  const pos = span > 0 ? Math.min(97, Math.max(3, ((p.predicted_sales - p.lower_bound) / span) * 100)) : 50;
  return (
    <div>
      <p className="label">Estimated sales (one order line)</p>
      <p className="text-4xl font-bold tracking-tight text-slate-900 tabular-nums">{fmtMoney2(p.predicted_sales)}</p>
      <div className="mt-4" aria-hidden="true">
        <div className="relative h-2.5 rounded-full bg-slate-200">
          <div className="absolute inset-0 rounded-full bg-gradient-to-r from-indigo-200 to-brand-600" />
          <div className="absolute top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-4 border-brand-600 bg-white shadow" style={{ left: `${pos}%` }} />
        </div>
        <div className="mt-1.5 flex justify-between text-xs text-slate-500 tabular-nums">
          <span>{fmtMoney(p.lower_bound)}</span>
          <span>{fmtMoney(p.upper_bound)}</span>
        </div>
      </div>
      <p className="mt-2 text-sm text-slate-600">
        Likely range {fmtMoney(p.lower_bound)} to {fmtMoney(p.upper_bound)}: on held-out data this kind of interval contained the true value for{" "}
        <strong>{(p.interval_empirical_coverage * 100).toFixed(0)}%</strong> of orders (target {(p.interval_nominal_coverage * 100).toFixed(0)}%).
      </p>
    </div>
  );
}
