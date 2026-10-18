import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../lib/api";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}

export function Card({ title, hint, children, className = "", actions }: { title?: string; hint?: ReactNode; children: ReactNode; className?: string; actions?: ReactNode }) {
  return (
    <section className={`card p-5 ${className}`}>
      {(title || actions) && (
        <header className="mb-3 flex items-start justify-between gap-3">
          <div>
            {title && <h2 className="text-sm font-semibold text-slate-900">{title}</h2>}
            {hint && <p className="mt-0.5 text-xs text-slate-500">{hint}</p>}
          </div>
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}

type Tone = "slate" | "green" | "amber" | "red" | "indigo" | "teal";
const TONES: Record<Tone, string> = {
  slate: "bg-slate-100 text-slate-700 ring-slate-200",
  green: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  amber: "bg-amber-50 text-amber-800 ring-amber-200",
  red: "bg-rose-50 text-rose-700 ring-rose-200",
  indigo: "bg-indigo-50 text-indigo-700 ring-indigo-200",
  teal: "bg-teal-50 text-teal-700 ring-teal-200",
};

export function Badge({ children, tone = "slate", title }: { children: ReactNode; tone?: Tone; title?: string }) {
  return (
    <span title={title} className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${TONES[tone]}`}>
      {children}
    </span>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <span role="status" className="inline-flex items-center gap-2 text-sm text-slate-500">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-brand-600" aria-hidden="true" />
      {label}
    </span>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden="true" className={`animate-pulse rounded-lg bg-slate-200/70 ${className}`} />;
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-slate-300 bg-slate-50/60 px-6 py-10 text-center">
      <p className="text-sm font-semibold text-slate-700">{title}</p>
      {children && <div className="mt-1 max-w-md text-sm text-slate-500">{children}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : "Something went wrong.";
  const hint = error instanceof ApiError ? error.hint : undefined;
  return (
    <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
      <p className="font-semibold">Could not load this data</p>
      <p className="mt-1">{message}</p>
      {hint && <p className="mt-1 text-rose-700">{hint}</p>}
      {onRetry && (
        <button type="button" className="btn-secondary mt-3" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

/** Shown instead of (never alongside) figures when a backing service has not been set up yet. */
export function SetupState({ error }: { error: ApiError }) {
  const what = error.code === "model_not_ready" ? "The prediction model is not trained yet" : "The database is not ready yet";
  return (
    <div role="status" className="rounded-xl border border-amber-200 bg-amber-50 p-6">
      <h2 className="text-base font-semibold text-amber-900">{what}</h2>
      <p className="mt-1 text-sm text-amber-800">{error.message}</p>
      {error.hint && <p className="mt-2 text-sm text-amber-800">{error.hint}</p>}
      <p className="mt-3 text-sm text-amber-900">
        No figures are shown until real data is available.{" "}
        <Link to="/status" className="font-semibold underline">
          Open System status
        </Link>{" "}
        for the exact setup commands.
      </p>
    </div>
  );
}

/** Picks the right state for a failed query. */
export function QueryError({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  if (error instanceof ApiError && error.isSetupProblem) return <SetupState error={error} />;
  return <ErrorState error={error} onRetry={onRetry} />;
}

export function CodeBlock({ children, label }: { children: string; label?: string }) {
  return (
    <div>
      {label && <p className="label">{label}</p>}
      <pre className="overflow-x-auto rounded-lg bg-slate-900 p-3 text-xs leading-relaxed text-slate-100">
        <code>{children}</code>
      </pre>
    </div>
  );
}

export function DataTable({ columns, rows, align }: { columns: string[]; rows: ReactNode[][]; align?: ("left" | "right")[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-200">
        <thead>
          <tr>
            {columns.map((c, i) => (
              <th key={c} scope="col" className={`th ${align?.[i] === "right" ? "text-right" : ""}`}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((r, i) => (
            <tr key={i} className="hover:bg-slate-50">
              {r.map((cell, j) => (
                <td key={j} className={`td ${align?.[j] === "right" ? "text-right tabular-nums" : ""}`}>
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
