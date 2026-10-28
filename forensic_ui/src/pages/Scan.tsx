import { useEffect, useMemo, useState } from "react";
import { api, Meta, monthLabel, ScanCell } from "../api";
import type { InvestigateRequest } from "./Investigate";

// Diverging scale: red = below baseline, blue = above, gray midpoint = normal.
const DOWN = ["#f9d4d3", "#f1a3a2", "#e66767", "#c03535"];
const UP = ["#cde2fb", "#9ec5f4", "#5598e7", "#256abf"];
const STEPS = [2.5, 7.5, 15, 22.5];

function cellColor(pct: number): { bg: string; ink: string } {
  const mag = Math.abs(pct);
  let step = -1;
  STEPS.forEach((s, i) => {
    if (mag >= s) step = i;
  });
  if (step < 0) return { bg: "var(--surface-2)", ink: "var(--text-2)" };
  return { bg: (pct < 0 ? DOWN : UP)[step], ink: step >= 2 ? "#fff" : "#0b0b0b" };
}

const SIGNAL_CODE: Record<string, string> = {
  supply: "stock-out", returns: "returns", discount: "discount", price: "price",
  demand_down: "demand ↓", demand_up: "demand ↑",
};

export default function Scan({ meta, onInvestigate }: { meta: Meta; onInvestigate: (r: InvestigateRequest) => void }) {
  const [cells, setCells] = useState<ScanCell[] | null>(null);
  useEffect(() => {
    api.scan().then((r) => setCells(r.cells));
  }, []);

  const byKey = useMemo(() => {
    const m = new Map<string, ScanCell>();
    cells?.forEach((c) => m.set(`${c.product_id}|${c.region}|${c.month}`, c));
    return m;
  }, [cells]);

  if (!cells) return <div className="empty"><span className="spinner" /> Scanning…</div>;
  const products = meta.products.filter((p) => p.has_sales);
  const anomalies = cells.filter((c) => c.is_anomaly);

  return (
    <div className="stack">
      <div>
        <h1>Anomaly scan</h1>
        <p className="lede">
          Every product × region × month, compared with the same series' other months (median baseline, robust z-score).
          Outlined cells are anomalies: |z| ≥ 3 and a material change, or a stock-out, returns spike, discount or price
          change. Click any cell to investigate it.
        </p>
      </div>
      <div className="grid-4">
        <Stat value={cells.length} label="product/region/months scanned" />
        <Stat value={anomalies.length} label="anomalies flagged" />
        <Stat value={anomalies.filter((c) => c.units_pct < 0).length} label="flagged as drops" />
        <Stat value={anomalies.filter((c) => c.units_pct > 0).length} label="flagged as rises" />
      </div>
      <div className="card">
        <div className="legend" style={{ marginBottom: 14 }}>
          <span>Units/day vs. baseline:</span>
          <span className="ramp">{[...DOWN].reverse().map((c) => <span key={c} style={{ background: c }} />)}</span>
          <span>below</span>
          <span className="swatch" style={{ background: "var(--surface-2)" }} /> normal (±2.5%)
          <span className="ramp">{UP.map((c) => <span key={c} style={{ background: c }} />)}</span>
          <span>above</span>
          <span style={{ marginLeft: 12 }}>
            <span className="swatch" style={{ boxShadow: "0 0 0 2px var(--text)", background: "transparent" }} /> anomaly
          </span>
        </div>
        <div className="stack" style={{ gap: 22 }}>
          {products.map((p) => (
            <div key={p.product_id} className="table-wrap">
              <h3 style={{ marginBottom: 4 }}>
                {p.product_name} {!p.has_documents && <span className="badge warn">no documents on file</span>}
              </h3>
              <table className="heat">
                <thead>
                  <tr>
                    <th />
                    {meta.months.map((m) => <th key={m}>{monthLabel(m)}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {meta.regions.map((r) => (
                    <tr key={r}>
                      <th className="rowhead">{r}</th>
                      {meta.months.map((m) => {
                        const c = byKey.get(`${p.product_id}|${r}|${m}`);
                        if (!c) return <td key={m} />;
                        const { bg, ink } = cellColor(c.units_pct);
                        const sig = c.signals.filter((s) => !s.startsWith("demand")).map((s) => SIGNAL_CODE[s]);
                        const sign = (v: number) => (v > 0 ? "+" : "");
                        const tip = [
                          `${p.product_name}, ${r}, ${monthLabel(m)}`,
                          `Units/day ${c.units_per_day.toLocaleString()} (${sign(c.units_pct)}${c.units_pct.toFixed(1)}%)`,
                          `Returns rate ${sign(c.returns_pct)}${c.returns_pct.toFixed(0)}% vs. baseline`,
                          `Stock-out days: ${c.stockout_days}`,
                          `Anomaly score: ${c.anomaly_score}`,
                          c.signals.length ? `Signals: ${c.signals.map((s) => SIGNAL_CODE[s]).join(", ")}` : "",
                        ].filter(Boolean).join("\n");
                        return (
                          <td key={m}>
                            <button
                              className={c.is_anomaly ? "anomaly" : ""}
                              style={{ background: bg, color: ink }}
                              title={tip}
                              onClick={() =>
                                onInvestigate({
                                  question: `What happened to ${p.product_name} in the ${r} region in ${monthLabel(m)}?`,
                                  product_id: p.product_id, region: r, month: m,
                                })
                              }
                            >
                              <span>{Math.round(c.units_pct) === 0 ? "0" : `${sign(c.units_pct)}${Math.round(c.units_pct)}`}%</span>
                              {sig.length > 0 && <span style={{ fontSize: 9, fontWeight: 500 }}>{sig[0]}</span>}
                            </button>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Stat({ value, label }: { value: number | string; label: string }) {
  return (
    <div className="card stat">
      <div className="value">{value}</div>
      <div className="label">{label}</div>
    </div>
  );
}
