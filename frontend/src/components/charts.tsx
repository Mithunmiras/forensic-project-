import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { COLORS } from "../lib/colors";
import { fmtCompactMoney, fmtInt, fmtMoney, fmtPct } from "../lib/format";

const SERIES = [COLORS.brand, COLORS.teal, COLORS.amber, COLORS.rose, COLORS.slate];
const AXIS = { fontSize: 12, fill: "#64748b" };

type Formatter = (v: number) => string;
const clip = (v: unknown, n = 22): string => { const t = String(v); return t.length > n ? `${t.slice(0, n - 1)}…` : t; };
const asNumber = (v: unknown): number => (typeof v === "number" ? v : Number(v));
// Recharts' tooltip formatter is loosely typed; keep one adapter so each chart stays readable.
const tip = (fmt: Formatter) => (value: unknown) => fmt(asNumber(value));

export function ChartFrame({ height = 260, label, children }: { height?: number; label: string; children: React.ReactElement }) {
  return (
    <div role="img" aria-label={label} style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        {children}
      </ResponsiveContainer>
    </div>
  );
}

export function TrendChart({ data }: { data: { period: string; sales: number; profit: number }[] }) {
  return (
    <ChartFrame height={300} label="Sales and profit over time">
      <AreaChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="gSales" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={COLORS.brand} stopOpacity={0.25} />
            <stop offset="100%" stopColor={COLORS.brand} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={COLORS.grid} vertical={false} />
        <XAxis dataKey="period" tick={AXIS} minTickGap={24} tickLine={false} />
        <YAxis tick={AXIS} tickFormatter={fmtCompactMoney} width={64} axisLine={false} tickLine={false} />
        <Tooltip formatter={tip(fmtMoney)} />
        <Legend />
        <Area isAnimationActive={false} type="monotone" dataKey="sales" name="Sales" stroke={COLORS.brand} strokeWidth={2} fill="url(#gSales)" dot={data.length < 20} />
        <Area isAnimationActive={false} type="monotone" dataKey="profit" name="Profit" stroke={COLORS.teal} strokeWidth={2} fill="none" dot={data.length < 20} />
      </AreaChart>
    </ChartFrame>
  );
}

/** Horizontal ranking bars. ``signed`` colours negative values red. */
export function RankBars({
  data, valueKey, label, format = fmtMoney, height = 280, signed = false, color = COLORS.brand,
}: {
  data: ReadonlyArray<{ name: string }>;
  valueKey: string;
  label: string;
  format?: Formatter;
  height?: number;
  signed?: boolean;
  color?: string;
}) {
  const valueOf = (d: object): number => Number((d as Record<string, unknown>)[valueKey]);
  return (
    <ChartFrame height={height} label={label}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 0 }}>
        <CartesianGrid stroke={COLORS.grid} horizontal={false} />
        <XAxis type="number" tick={AXIS} tickFormatter={(v: number) => (format === fmtMoney ? fmtCompactMoney(v) : format(v))} axisLine={false} tickLine={false} />
        <YAxis type="category" dataKey="name" tick={AXIS} tickFormatter={(v: unknown) => clip(v)} width={150} tickLine={false} axisLine={false} interval={0} />
        <Tooltip formatter={tip(format)} labelFormatter={(l: unknown) => String(l)} cursor={{ fill: "#f1f5f9" }} />
        <Bar isAnimationActive={false} dataKey={valueKey} name={label} radius={[0, 4, 4, 0]} maxBarSize={22}>
          {data.map((d, i) => (
            <Cell key={i} fill={signed && valueOf(d) < 0 ? COLORS.rose : color} />
          ))}
        </Bar>
      </BarChart>
    </ChartFrame>
  );
}

export function ColumnBars({
  data, xKey, valueKey, label, format = fmtMoney, signed = false, height = 260,
}: {
  data: Record<string, string | number | null>[];
  xKey: string;
  valueKey: string;
  label: string;
  format?: Formatter;
  signed?: boolean;
  height?: number;
}) {
  return (
    <ChartFrame height={height} label={label}>
      <BarChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={COLORS.grid} vertical={false} />
        <XAxis dataKey={xKey} tick={AXIS} tickLine={false} interval={0} />
        <YAxis tick={AXIS} tickFormatter={(v: number) => (format === fmtMoney ? fmtCompactMoney(v) : format(v))} width={64} axisLine={false} tickLine={false} />
        <Tooltip formatter={tip(format)} cursor={{ fill: "#f1f5f9" }} />
        <Bar isAnimationActive={false} dataKey={valueKey} name={label} radius={[4, 4, 0, 0]} maxBarSize={46}>
          {data.map((d, i) => (
            <Cell key={i} fill={signed && Number(d[valueKey]) < 0 ? COLORS.rose : COLORS.brand} />
          ))}
        </Bar>
      </BarChart>
    </ChartFrame>
  );
}

export function Donut({ data, label }: { data: { name: string; value: number }[]; label: string }) {
  const total = data.reduce((a, b) => a + b.value, 0);
  return (
    <ChartFrame height={260} label={label}>
      <PieChart>
        <Pie isAnimationActive={false} data={data} dataKey="value" nameKey="name" innerRadius={62} outerRadius={96} paddingAngle={2} stroke="none">
          {data.map((_, i) => (
            <Cell key={i} fill={SERIES[i % SERIES.length]} />
          ))}
        </Pie>
        <Tooltip formatter={(v: unknown) => `${fmtMoney(asNumber(v))} (${fmtPct((asNumber(v) / total) * 100)})`} />
        <Legend verticalAlign="bottom" />
      </PieChart>
    </ChartFrame>
  );
}

/** Chart for a natural-language result, driven by the backend's chart hint. */
export function ResultChart({ type, x, y, columns, rows }: { type: "bar" | "line"; x: string; y: string; columns: { name: string }[]; rows: unknown[][] }) {
  const xi = columns.findIndex((c) => c.name === x);
  const yi = columns.findIndex((c) => c.name === y);
  if (xi < 0 || yi < 0) return null;
  const data = rows.map((r) => ({ x: String(r[xi]), y: Number(r[yi]) }));
  const fmt: Formatter = /(sales|profit|cost|value)/i.test(y) ? fmtMoney : (v) => (Number.isInteger(v) ? fmtInt(v) : v.toFixed(2));
  const axisFmt = (v: number) => (fmt === fmtMoney ? fmtCompactMoney(v) : fmt(v));
  return (
    <ChartFrame height={240} label={`${y} by ${x}`}>
      {type === "line" ? (
        <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={COLORS.grid} vertical={false} />
          <XAxis dataKey="x" tick={AXIS} minTickGap={24} tickLine={false} />
          <YAxis tick={AXIS} tickFormatter={axisFmt} width={64} axisLine={false} tickLine={false} />
          <Tooltip formatter={tip(fmt)} />
          <Line isAnimationActive={false} type="monotone" dataKey="y" name={y} stroke={COLORS.brand} strokeWidth={2} dot={data.length < 20} />
        </LineChart>
      ) : (
        <BarChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={COLORS.grid} vertical={false} />
          <XAxis dataKey="x" tick={AXIS} tickLine={false} interval={0} angle={data.length > 6 ? -25 : 0} textAnchor={data.length > 6 ? "end" : "middle"} height={data.length > 6 ? 70 : 30} />
          <YAxis tick={AXIS} tickFormatter={axisFmt} width={64} axisLine={false} tickLine={false} />
          <Tooltip formatter={tip(fmt)} cursor={{ fill: "#f1f5f9" }} />
          <Bar isAnimationActive={false} dataKey="y" name={y} fill={COLORS.brand} radius={[4, 4, 0, 0]} maxBarSize={46} />
        </BarChart>
      )}
    </ChartFrame>
  );
}
