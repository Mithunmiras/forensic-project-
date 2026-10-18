import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { ColumnBars, Donut, RankBars, TrendChart } from "../components/charts";
import { Badge, Card, DataTable, EmptyState, PageHeader, QueryError, Skeleton } from "../components/ui";
import { api } from "../lib/api";
import { fmtCompactMoney, fmtDate, fmtFraction, fmtInt, fmtMoney, fmtMoney2, fmtPct } from "../lib/format";
import type { Dashboard, Filters } from "../lib/types";

type Grain = "month" | "quarter" | "year";

function Delta({ value }: { value: number | null | undefined }) {
  if (value == null) return null;
  const up = value >= 0;
  return (
    <span className={`mt-2 inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${up ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"}`}>
      {up ? "▲" : "▼"} {Math.abs(value).toFixed(1)}% vs previous period
    </span>
  );
}

function Kpi({ label, value, sub, delta }: { label: string; value: string; sub?: string; delta?: number | null }) {
  return (
    <div className="card p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-bold tracking-tight text-slate-900 tabular-nums">{value}</p>
      {sub && <p className="mt-1 text-xs text-slate-500">{sub}</p>}
      <Delta value={delta} />
    </div>
  );
}

function Select({ id, label, value, options, onChange, all }: { id: string; label: string; value: string; options: string[]; onChange: (v: string) => void; all: string }) {
  return (
    <div>
      <label htmlFor={id} className="label">
        {label}
      </label>
      <select id={id} className="input" value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{all}</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </div>
  );
}

export default function Overview() {
  const [filters, setFilters] = useState<Filters>({});
  const [grain, setGrain] = useState<Grain>("month");

  const options = useQuery({ queryKey: ["filter-options"], queryFn: api.filters, staleTime: 5 * 60_000, retry: false });
  const [min, max] = options.data?.date_range ?? ["", ""];

  const dateError = filters.date_from && filters.date_to && filters.date_from > filters.date_to ? "The start date must be on or before the end date." : null;
  const dash = useQuery({
    queryKey: ["dashboard", filters, grain],
    queryFn: ({ signal }) => api.dashboard(filters, grain, signal),
    enabled: !dateError,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
    retry: false,
  });

  const set = (patch: Partial<Filters>) => setFilters((f) => ({ ...f, ...patch }));
  const years = useMemo(() => (min && max ? Array.from({ length: Number(max.slice(0, 4)) - Number(min.slice(0, 4)) + 1 }, (_, i) => String(Number(min.slice(0, 4)) + i)) : []), [min, max]);
  const activeFilters = Object.values(filters).filter(Boolean).length;
  const d: Dashboard | undefined = dash.data;

  return (
    <>
      <PageHeader
        title="Sales performance"
        subtitle={
          d?.kpis.first_date ? (
            <>
              Global Superstore · {fmtDate(d.kpis.first_date)} to {fmtDate(d.kpis.last_date)} · live from PostgreSQL
            </>
          ) : (
            "Live from PostgreSQL"
          )
        }
      />

      <Card className="mb-6">
        <form className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6" aria-label="Dashboard filters" onSubmit={(e) => e.preventDefault()}>
          <div>
            <label htmlFor="f-from" className="label">From</label>
            <input id="f-from" type="date" className={`input ${dateError ? "input-error" : ""}`} min={min} max={max} value={filters.date_from ?? ""} onChange={(e) => set({ date_from: e.target.value || undefined })} />
          </div>
          <div>
            <label htmlFor="f-to" className="label">To</label>
            <input id="f-to" type="date" className={`input ${dateError ? "input-error" : ""}`} min={min} max={max} value={filters.date_to ?? ""} onChange={(e) => set({ date_to: e.target.value || undefined })} />
          </div>
          <Select id="f-cat" label="Category" all="All categories" value={filters.category ?? ""} options={options.data?.categories ?? []} onChange={(v) => set({ category: v || undefined })} />
          <Select id="f-reg" label="Region" all="All regions" value={filters.region ?? ""} options={options.data?.regions ?? []} onChange={(v) => set({ region: v || undefined })} />
          <Select id="f-mkt" label="Market" all="All markets" value={filters.market ?? ""} options={options.data?.markets ?? []} onChange={(v) => set({ market: v || undefined })} />
          <div className="flex items-end gap-2">
            <button type="button" className="btn-secondary w-full" disabled={activeFilters === 0} onClick={() => setFilters({})}>
              Reset
            </button>
          </div>
        </form>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          <span className="font-semibold uppercase tracking-wide text-slate-500">Quick range</span>
          {years.map((y) => (
            <button key={y} type="button" className="rounded-full border border-slate-300 px-2.5 py-1 font-medium text-slate-600 hover:bg-slate-50" onClick={() => set({ date_from: `${y}-01-01`, date_to: `${y}-12-31` })}>
              {y}
            </button>
          ))}
        </div>
        {dateError && <p role="alert" className="mt-3 text-sm text-rose-600">{dateError}</p>}
      </Card>

      {dash.isError && <QueryError error={dash.error} onRetry={() => dash.refetch()} />}

      {dash.isLoading && !dash.isError && (
        <div className="space-y-6" aria-busy="true" aria-label="Loading dashboard">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-24" />)}</div>
          <Skeleton className="h-80" />
        </div>
      )}

      {d && d.kpis.order_lines === 0 && <EmptyState title="No orders match these filters">Try widening the date range or clearing a filter.</EmptyState>}

      {d && d.kpis.order_lines > 0 && (
        <div className={`space-y-6 transition-opacity ${dash.isFetching ? "opacity-70" : ""}`} aria-live="polite">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
            <Kpi label="Total sales" value={fmtCompactMoney(d.kpis.total_sales)} sub={fmtMoney(d.kpis.total_sales)} delta={d.change_pct?.total_sales} />
            <Kpi label="Total profit" value={fmtCompactMoney(d.kpis.total_profit)} sub={`Margin ${fmtFraction(d.kpis.profit_margin)}`} delta={d.change_pct?.total_profit} />
            <Kpi label="Orders" value={fmtInt(d.kpis.orders)} sub={`${fmtInt(d.kpis.order_lines)} order lines`} delta={d.change_pct?.orders} />
            <Kpi label="Avg order value" value={fmtMoney2(d.kpis.avg_order_value)} delta={d.change_pct?.avg_order_value} />
            <Kpi label="Avg discount" value={fmtFraction(d.kpis.avg_discount)} sub="mean of line discounts" />
            <Kpi label="Customers" value={fmtInt(d.kpis.customers)} sub={`${fmtInt(d.kpis.units)} units sold`} />
          </div>

          <div className="grid gap-6 xl:grid-cols-3">
            <Card
              className="xl:col-span-2"
              title="Sales and profit trend"
              actions={
                <div role="group" aria-label="Time grain" className="inline-flex rounded-lg border border-slate-300 p-0.5">
                  {(["month", "quarter", "year"] as Grain[]).map((g) => (
                    <button key={g} type="button" aria-pressed={grain === g} onClick={() => setGrain(g)} className={`rounded-md px-2.5 py-1 text-xs font-semibold capitalize ${grain === g ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100"}`}>
                      {g}
                    </button>
                  ))}
                </div>
              }
            >
              <TrendChart data={d.trend} />
            </Card>
            <Card title="Sales by category" hint="Share of total sales">
              <Donut label="Sales by category" data={d.by_category.map((c) => ({ name: c.name, value: c.sales }))} />
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-2 xl:grid-cols-3">
            <Card title="Sales by region" hint="All regions, highest first">
              <RankBars data={d.by_region} valueKey="sales" label="Sales" height={360} />
            </Card>
            <Card title="Top 10 products by sales">
              <RankBars data={d.top_products} valueKey="sales" label="Sales" height={360} color="#0d9488" />
            </Card>
            <Card title="Profit by sub-category" hint="Red = loss-making">
              <RankBars data={d.by_sub_category} valueKey="profit" label="Profit" height={360} signed />
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card title="Profit margin by discount band" hint="Where discounting starts to destroy profit">
              <ColumnBars data={d.discount_impact.map((b) => ({ band: b.band.slice(2), margin: b.margin_pct }))} xKey="band" valueKey="margin" label="Margin" format={(v) => fmtPct(v)} signed />
            </Card>
            <Card title="Sales by market">
              <ColumnBars data={d.by_market.map((m) => ({ name: m.name, sales: m.sales }))} xKey="name" valueKey="sales" label="Sales" />
            </Card>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card title="Top customers" hint="By sales">
              <DataTable
                columns={["Customer", "Segment", "Sales", "Profit"]}
                align={["left", "left", "right", "right"]}
                rows={d.top_customers.map((c) => [c.name, <Badge key="s">{c.segment}</Badge>, fmtMoney(c.sales), <span key="p" className={c.profit < 0 ? "text-rose-600" : ""}>{fmtMoney(c.profit)}</span>])}
              />
            </Card>
            <Card title="Shipping by mode">
              <DataTable
                columns={["Ship mode", "Orders", "Avg days", "Avg cost"]}
                align={["left", "right", "right", "right"]}
                rows={d.shipping.map((s) => [s.ship_mode, fmtInt(s.orders), s.avg_days.toFixed(1), fmtMoney2(s.avg_cost)])}
              />
            </Card>
          </div>
        </div>
      )}
    </>
  );
}
