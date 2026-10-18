import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { RankBars } from "../components/charts";
import { PredictionSummary } from "../components/Evidence";
import { Badge, Card, DataTable, PageHeader, QueryError, Skeleton, Spinner } from "../components/ui";
import { ApiError, api } from "../lib/api";
import { fmtDate, fmtFixed, fmtMoney2, titleCase } from "../lib/format";
import { fieldLabel, toRequest, validate, type Values } from "../lib/predictForm";
import type { InputField, ModelMetadata, PredictionRequest, PredictionResponse } from "../lib/types";

function FieldControl({ f, values, set, error }: { f: InputField; values: Values; set: (name: string, value: string) => void; error?: string }) {
  const id = `p-${f.name}`;
  const value = values[f.name] ?? "";
  const options = f.name === "sub_category" ? f.options_by_category?.[values.category ?? ""] ?? [] : f.options;
  const placeholderDefault =
    f.name === "shipping_days" && values.ship_mode ? f.default_by_ship_mode?.[values.ship_mode] : f.name === "shipping_days" ? f.default_by_ship_mode?.["Standard Class"] : f.default;
  const hint = f.training_range && f.kind !== "date" ? `Seen in training: ${f.training_range[0]}–${f.training_range[1]}` : undefined;
  const common = { id, "aria-invalid": !!error, "aria-describedby": error ? `${id}-err` : hint ? `${id}-hint` : undefined };
  return (
    <div>
      <label htmlFor={id} className="label">
        {fieldLabel(f)} {f.required ? <span className="text-rose-500" aria-label="required">*</span> : <span className="font-normal normal-case text-slate-400">(optional)</span>}
      </label>
      {f.kind === "categorical" ? (
        <select {...common} className={`input ${error ? "input-error" : ""}`} value={value} onChange={(e) => set(f.name, e.target.value)}>
          <option value="">{f.required ? "Select..." : `Default${placeholderDefault ? ` (${placeholderDefault})` : ""}`}</option>
          {(options ?? []).map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
      ) : (
        <input
          {...common}
          className={`input ${error ? "input-error" : ""}`}
          type={f.kind === "date" ? "date" : "number"}
          inputMode={f.kind === "integer" ? "numeric" : f.kind === "number" ? "decimal" : undefined}
          step={f.kind === "integer" ? 1 : f.name === "discount" ? 1 : 0.01}
          value={value}
          placeholder={placeholderDefault != null ? `Default: ${placeholderDefault}` : undefined}
          onChange={(e) => set(f.name, e.target.value)}
        />
      )}
      {error ? <p id={`${id}-err`} role="alert" className="mt-1 text-xs text-rose-600">{error}</p> : hint && <p id={`${id}-hint`} className="mt-1 text-xs text-slate-500">{hint}</p>}
      {f.name === "shipping_cost" && !error && (
        <p className="mt-1 text-xs text-slate-500">If given, the more accurate model that uses shipping cost is used. It is a proxy of sales (see the notes below).</p>
      )}
    </div>
  );
}

function ModelInfo({ meta, used }: { meta: ModelMetadata; used?: string }) {
  const [variant, setVariant] = useState(used ?? meta.default_variant);
  const v = meta.variants[variant] ?? Object.values(meta.variants)[0];
  const importance = v.feature_importance.slice(0, 8).map((f) => ({ name: titleCase(f.feature), importance: Number(f.importance.toFixed(3)) }));
  return (
    <Card title="Model information" hint={`Trained ${fmtDate(meta.trained_at)} on ${meta.dataset.rows.toLocaleString()} order lines (${meta.dataset.order_date_range[0]} to ${meta.dataset.order_date_range[1]}); evaluated on an untouched ${(meta.split.test_size * 100).toFixed(0)}% hold-out.`}>
      <div role="tablist" aria-label="Model variant" className="mb-4 inline-flex rounded-lg border border-slate-300 p-0.5">
        {Object.entries(meta.variants).map(([name]) => (
          <button key={name} role="tab" aria-selected={variant === name} type="button" onClick={() => setVariant(name)} className={`rounded-md px-3 py-1.5 text-xs font-semibold ${variant === name ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>
            {name === "without_shipping_cost" ? "Without shipping cost (leakage-safe)" : "With shipping cost"}
          </button>
        ))}
      </div>
      <p className="mb-3 text-sm text-slate-600">{v.label}. Selected by cross-validation: <strong>{v.best_model}</strong>.</p>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          ["R²", v.test_metrics.r2.toFixed(3)],
          ["MAE", fmtMoney2(v.test_metrics.mae)],
          ["RMSE", fmtMoney2(v.test_metrics.rmse)],
          ["80% interval coverage", `${(v.interval.empirical_test_coverage * 100).toFixed(1)}%`],
        ].map(([k, val]) => (
          <div key={k} className="rounded-lg bg-slate-50 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{k}</p>
            <p className="text-lg font-bold text-slate-900 tabular-nums">{val}</p>
          </div>
        ))}
      </div>
      <p className="mt-2 text-xs text-slate-500">Hold-out test metrics. A model that always predicts the mean scores R² {fmtFixed(v.baseline_test_metrics.r2, 2)} and MAE {fmtMoney2(v.baseline_test_metrics.mae)}.</p>

      <div className="mt-5 grid gap-6 lg:grid-cols-2">
        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-800">Models compared (cross-validated)</h3>
          <DataTable
            columns={["Model", "CV R²", "Test R²", "Test MAE"]}
            align={["left", "right", "right", "right"]}
            rows={[...v.candidates].sort((a, b) => b.cv_r2_mean - a.cv_r2_mean).map((c) => [
              <span key="n">{c.name} {c.selected && <Badge tone="indigo">selected</Badge>} {c.is_baseline && <Badge>baseline</Badge>}</span>,
              fmtFixed(c.cv_r2_mean), fmtFixed(c.test_r2), fmtMoney2(c.test_mae),
            ])}
          />
        </div>
        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-800">What drives the estimate</h3>
          <RankBars data={importance} valueKey="importance" label="Permutation importance (R² drop)" format={(n) => n.toFixed(2)} height={250} />
        </div>
      </div>

      <div className="mt-5 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
        <p className="font-semibold">Read this before relying on an estimate</p>
        <ul className="mt-1 list-disc space-y-1 pl-5">
          {meta.limitations.map((l) => <li key={l}>{l}</li>)}
        </ul>
      </div>
    </Card>
  );
}

export default function Predict() {
  const schema = useQuery({ queryKey: ["ml-schema"], queryFn: api.mlSchema, retry: false, staleTime: 10 * 60_000 });
  const meta = useQuery({ queryKey: ["ml-metadata"], queryFn: api.mlMetadata, retry: false, staleTime: 10 * 60_000 });
  const [values, setValues] = useState<Values>({ quantity: "3", discount: "10" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [result, setResult] = useState<PredictionResponse | null>(null);

  const fields = schema.data?.fields ?? [];
  const run = useMutation({
    mutationFn: (body: PredictionRequest) => api.predict(body),
    onSuccess: (r) => { setResult(r); setErrors({}); },
    onError: (e) => { if (e instanceof ApiError && e.fields) setErrors(e.fields); },
  });

  const set = (name: string, value: string) =>
    setValues((v) => ({ ...v, [name]: value, ...(name === "category" ? { sub_category: "" } : {}) }));

  const example = () => setValues({ category: "Technology", sub_category: "Phones", market: "US", quantity: "3", discount: "10", segment: "Consumer", ship_mode: "Standard Class", order_priority: "Medium" });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const errs = validate(fields, values);
    setErrors(errs);
    if (Object.keys(errs).length === 0) run.mutate(toRequest(fields, values));
  }

  if (schema.isError) {
    return (<><PageHeader title="Sales prediction" /><QueryError error={schema.error} onRetry={() => schema.refetch()} /></>);
  }

  return (
    <>
      <PageHeader title="Sales prediction" subtitle="Estimate the sales value of one order line. The form below is generated from the trained model's actual inputs." />
      <div className="grid gap-6 xl:grid-cols-[1.2fr_1fr]">
        <Card title="Order details" actions={<button type="button" className="btn-secondary px-3 py-1.5 text-xs" onClick={example}>Fill example</button>}>
          {schema.isLoading ? (
            <div className="grid gap-4 sm:grid-cols-2">{Array.from({ length: 8 }, (_, i) => <Skeleton key={i} className="h-14" />)}</div>
          ) : (
            <form onSubmit={submit} noValidate className="space-y-5">
              <div className="grid gap-4 sm:grid-cols-2">
                {fields.map((f) => <FieldControl key={f.name} f={f} values={values} set={set} error={errors[f.name]} />)}
              </div>
              {run.isError && !(run.error instanceof ApiError && run.error.fields) && <QueryError error={run.error} />}
              <button type="submit" className="btn-primary w-full" disabled={run.isPending}>
                {run.isPending ? <Spinner label="Predicting..." /> : "Predict sales"}
              </button>
            </form>
          )}
        </Card>

        <div className="space-y-6">
          <Card title="Result" className="min-h-[18rem]">
            <div aria-live="polite">
              {!result && <p className="py-12 text-center text-sm text-slate-500">Fill in the order and press <strong>Predict sales</strong>.</p>}
              {result && (
                <div className="space-y-4">
                  <PredictionSummary p={result} />
                  <dl className="divide-y divide-slate-100 text-sm">
                    <div className="flex justify-between gap-4 py-2"><dt className="text-slate-500">Typical {String(result.inputs_used.sub_category)} line</dt><dd className="font-semibold tabular-nums">{fmtMoney2(result.typical_sub_category_sales)}</dd></div>
                    <div className="flex justify-between gap-4 py-2"><dt className="text-slate-500">Model</dt><dd className="font-semibold">{result.model}</dd></div>
                    <div className="flex justify-between gap-4 py-2"><dt className="text-slate-500">Variant</dt><dd><Badge tone={result.variant === "with_shipping_cost" ? "amber" : "teal"}>{result.variant === "with_shipping_cost" ? "uses shipping cost (proxy)" : "leakage-safe"}</Badge></dd></div>
                  </dl>
                  {result.assumptions.length > 0 && (
                    <div><p className="label">Defaults applied</p><ul className="list-disc space-y-0.5 pl-5 text-xs text-slate-600">{result.assumptions.map((a) => <li key={a}>{a}</li>)}</ul></div>
                  )}
                  {result.warnings.length > 0 && (
                    <div role="alert" className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900"><ul className="list-disc space-y-0.5 pl-4">{result.warnings.map((w) => <li key={w}>{w}</li>)}</ul></div>
                  )}
                  <p className="text-xs italic text-slate-500">{result.disclaimer}</p>
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>

      <div className="mt-6">
        {meta.isLoading && <Skeleton className="h-72" />}
        {meta.isError && <QueryError error={meta.error} onRetry={() => meta.refetch()} />}
        {meta.data && <ModelInfo meta={meta.data} used={result?.variant} />}
      </div>
    </>
  );
}
