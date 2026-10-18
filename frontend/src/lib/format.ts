const usd0 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const usd2 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const int = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });

export const fmtMoney = (v: number | null | undefined): string => (v == null ? "n/a" : usd0.format(v));
export const fmtMoney2 = (v: number | null | undefined): string => (v == null ? "n/a" : usd2.format(v));
export const fmtInt = (v: number | null | undefined): string => (v == null ? "n/a" : int.format(v));

/** $12.6M style for chart axes and KPI cards. */
export function fmtCompactMoney(v: number | null | undefined): string {
  if (v == null) return "n/a";
  const sign = v < 0 ? "-" : "";
  return `${sign}$${compact.format(Math.abs(v))}`;
}

export const fmtPct = (v: number | null | undefined, digits = 1): string => (v == null ? "n/a" : `${v.toFixed(digits)}%`);
/** For fractions such as 0.116 -> 11.6%. */
export const fmtFraction = (v: number | null | undefined, digits = 1): string => (v == null ? "n/a" : `${(v * 100).toFixed(digits)}%`);

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "n/a";
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "n/a";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" });
}

/** Fixed-decimal number that never prints "-0.00". */
export const fmtFixed = (v: number, digits = 3): string => {
  const t = v.toFixed(digits);
  return /^-0(\.0+)?$/.test(t) ? t.slice(1) : t;
};

export const titleCase = (s: string): string => s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

/** Format a result cell using its column name (money, percent, count ...). */
export function fmtCell(column: string, value: unknown): string {
  if (value === null || value === undefined) return "n/a";
  if (typeof value !== "number") return String(value);
  const name = column.toLowerCase();
  if (name.endsWith("_pct")) return fmtPct(value, 2);
  if (/(sales|profit|cost|value|revenue)/.test(name) && !name.includes("days")) return Math.abs(value) >= 1000 ? fmtMoney(value) : fmtMoney2(value);
  return Number.isInteger(value) ? fmtInt(value) : value.toFixed(2);
}
