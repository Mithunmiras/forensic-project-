import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Investigation, monthLabel } from "../api";

const AXIS = { fontSize: 11, fill: "var(--muted)" };
const fmt = (v: number) => v.toLocaleString("en-US", { maximumFractionDigits: 0 });
const shortMonth = (m: string) =>
  `${new Date(`${m}-01T00:00:00`).toLocaleString("en-US", { month: "short" })} '${m.slice(2, 4)}`;
const shortDate = (d: string) =>
  new Date(`${d}T00:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric" });

interface TipProps {
  active?: boolean;
  label?: string;
  payload?: { name: string; value: number; color: string }[];
}

function Tip({ active, label, payload }: TipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className="tooltip">
      <b>{label && /^\d{4}-\d{2}-\d{2}$/.test(label) ? shortDate(label) : monthLabel(label)}</b>
      {payload
        .filter((p) => p.value !== undefined && p.value !== null)
        .map((p) => (
          <div key={p.name}>
            <span style={{ color: p.color }}>●</span> {p.name}: {fmt(p.value)}
          </div>
        ))}
    </div>
  );
}

function windowed(inv: Investigation) {
  const sql = inv.agents.sql;
  const month = sql.month!;
  const start = new Date(`${month}-01T00:00:00`);
  start.setMonth(start.getMonth() - 3);
  const from = start.toISOString().slice(0, 10);
  const fc = inv.agents.rca.forecast;
  const rows = new Map<string, { date: string; units?: number; stock?: number; reorder?: number; forecast?: number }>();
  for (const d of sql.daily ?? []) {
    if (d.date < from) continue;
    rows.set(d.date, { date: d.date, units: d.units, stock: d.stock, reorder: d.reorder_point });
  }
  const end = fc?.series.length ? fc.series[fc.series.length - 1].date : null;
  for (const f of fc?.series ?? []) {
    rows.set(f.date, { ...(rows.get(f.date) ?? { date: f.date }), forecast: f.forecast });
  }
  const data = [...rows.values()].filter((r) => !end || r.date <= end).sort((a, b) => (a.date < b.date ? -1 : 1));
  const inMonth = data.filter((r) => r.date.startsWith(month));
  return { data, monthStart: inMonth[0]?.date, monthEnd: inMonth[inMonth.length - 1]?.date };
}

export function DailyChart({ inv }: { inv: Investigation }) {
  const { data, monthStart, monthEnd } = windowed(inv);
  const st = inv.agents.sql.stockout;
  const base = inv.agents.sql.target?.units_per_day_base as number | undefined;
  const fc = inv.agents.rca.forecast;
  return (
    <div>
      <div className="chart-legend">
        <span><i style={{ borderColor: "var(--series-1)" }} />Units sold per day</span>
        {fc && <span><i className="dash" style={{ borderColor: "var(--series-2)" }} />Forecast ({fc.next_month})</span>}
        <span><i className="dash" style={{ borderColor: "var(--muted)" }} />Baseline</span>
        <span><i className="box" style={{ background: "var(--surface-2)" }} />{monthLabel(inv.agents.sql.month)}</span>
        {st && st.days > 0 && <span><i className="box" style={{ background: "var(--critical-soft)" }} />Stock-out days</span>}
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          {monthStart && <ReferenceArea x1={monthStart} x2={monthEnd} fill="var(--surface-2)" fillOpacity={1} />}
          {st?.first && <ReferenceArea x1={st.first} x2={st.last!} fill="var(--critical-soft)" fillOpacity={1} />}
          <XAxis dataKey="date" tickFormatter={shortDate} tick={AXIS} minTickGap={40} tickLine={false}
            axisLine={{ stroke: "var(--border)" }} />
          <YAxis tick={AXIS} tickFormatter={fmt} width={48} tickLine={false} axisLine={false} />
          {base && <ReferenceLine y={base} stroke="var(--muted)" strokeDasharray="4 4" />}
          <Tooltip content={<Tip />} />
          <Line name="Units sold" dataKey="units" stroke="var(--series-1)" strokeWidth={2} dot={false}
            activeDot={{ r: 4 }} isAnimationActive={false} />
          <Line name="Forecast" dataKey="forecast" stroke="var(--series-2)" strokeWidth={2} strokeDasharray="5 4"
            dot={false} activeDot={{ r: 4 }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function StockChart({ inv }: { inv: Investigation }) {
  const { data, monthStart, monthEnd } = windowed(inv);
  const st = inv.agents.sql.stockout;
  const rows = data.filter((r) => r.stock !== undefined);
  return (
    <div>
      <div className="chart-legend">
        <span><i style={{ borderColor: "var(--series-1)" }} />Stock level ({st?.warehouse})</span>
        <span><i className="dash" style={{ borderColor: "var(--critical)" }} />Reorder point</span>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          {monthStart && <ReferenceArea x1={monthStart} x2={monthEnd} fill="var(--surface-2)" fillOpacity={1} />}
          {st?.first && <ReferenceArea x1={st.first} x2={st.last!} fill="var(--critical-soft)" fillOpacity={1} />}
          <XAxis dataKey="date" tickFormatter={shortDate} tick={AXIS} minTickGap={40} tickLine={false}
            axisLine={{ stroke: "var(--border)" }} />
          <YAxis tick={AXIS} tickFormatter={fmt} width={48} tickLine={false} axisLine={false} />
          <Tooltip content={<Tip />} />
          <Line name="Stock" dataKey="stock" stroke="var(--series-1)" strokeWidth={2} dot={false}
            isAnimationActive={false} type="stepAfter" />
          <Line name="Reorder point" dataKey="reorder" stroke="var(--critical)" strokeWidth={1.5}
            strokeDasharray="4 4" dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function MonthlyChart({ inv }: { inv: Investigation }) {
  const sql = inv.agents.sql;
  const data = (sql.monthly ?? []).map((m) => ({ ...m, label: m.month }));
  const base = sql.target?.units_per_day_base as number | undefined;
  return (
    <div>
      <div className="chart-legend">
        <span><i className="box" style={{ background: "var(--series-1)" }} />{monthLabel(sql.month)}</span>
        <span><i className="box" style={{ background: "var(--series-1-soft)" }} />Other months</span>
        <span><i className="dash" style={{ borderColor: "var(--muted)" }} />Baseline (median of other months)</span>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }} barCategoryGap={6}>
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          <XAxis dataKey="label" tickFormatter={shortMonth} tick={AXIS} tickLine={false}
            axisLine={{ stroke: "var(--border)" }} interval={0} />
          <YAxis tick={AXIS} tickFormatter={fmt} width={48} tickLine={false} axisLine={false} />
          <Tooltip content={<Tip />} cursor={{ fill: "var(--surface-2)" }} />
          {base && <ReferenceLine y={base} stroke="var(--muted)" strokeDasharray="4 4" />}
          <Bar name="Units/day" dataKey="units_per_day" radius={[4, 4, 0, 0]} isAnimationActive={false}>
            {data.map((m) => (
              <Cell key={m.month} fill={m.month === sql.month ? "var(--series-1)" : "var(--series-1-soft)"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
