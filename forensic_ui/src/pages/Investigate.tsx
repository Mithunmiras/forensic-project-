import { useEffect, useRef, useState } from "react";
import { api, CASE_INFO, Investigation, Meta, monthLabel } from "../api";
import RichText from "../components/RichText";
import { DailyChart, MonthlyChart, StockChart } from "../components/Charts";

export interface InvestigateRequest {
  question: string;
  product_id?: string;
  region?: string;
  month?: string;
  nonce?: number;
}

const CASE_GROUPS: [string, string][] = [
  ["full", "Data + documents"],
  ["structured_only", "Data only (no document)"],
  ["unstructured_only", "Documents only"],
  ["none", "Controls (nothing happened)"],
];

export default function Investigate({ meta, pending }: { meta: Meta; pending: InvestigateRequest | null }) {
  const [question, setQuestion] = useState(meta.examples[0]?.question ?? "");
  const [product, setProduct] = useState("");
  const [region, setRegion] = useState("");
  const [month, setMonth] = useState("");
  const [result, setResult] = useState<Investigation | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  const run = (req: InvestigateRequest) => {
    setLoading(true);
    setError(null);
    api
      .investigate({
        question: req.question,
        product_id: req.product_id || undefined,
        region: req.region || undefined,
        month: req.month || undefined,
      })
      .then(setResult)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (!started.current && !pending) {
      started.current = true;
      run({ question });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!pending) return;
    started.current = true;
    setQuestion(pending.question);
    setProduct(pending.product_id ?? "");
    setRegion(pending.region ?? "");
    setMonth(pending.month ?? "");
    run(pending);
  }, [pending]);

  const submit = () => question.trim().length >= 3 && run({ question, product_id: product, region, month });

  return (
    <div className="layout-investigate">
      <aside className="stack">
        <div className="card stack">
          <h2 style={{ margin: 0 }}>Ask a business question</h2>
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder="Why did iPhone 15 sales drop in the North region in March 2026?"
          />
          <div className="grid-2" style={{ gap: 8 }}>
            <label className="field">
              Product
              <select value={product} onChange={(e) => setProduct(e.target.value)}>
                <option value="">From question</option>
                {meta.products.map((p) => (
                  <option key={p.product_id} value={p.product_id}>{p.product_name}</option>
                ))}
              </select>
            </label>
            <label className="field">
              Region
              <select value={region} onChange={(e) => setRegion(e.target.value)}>
                <option value="">From question</option>
                {meta.regions.map((r) => <option key={r}>{r}</option>)}
              </select>
            </label>
          </div>
          <label className="field">
            Month
            <select value={month} onChange={(e) => setMonth(e.target.value)}>
              <option value="">From question</option>
              {meta.months.map((m) => <option key={m} value={m}>{monthLabel(m)}</option>)}
            </select>
          </label>
          <button className="btn" onClick={submit} disabled={loading}>
            {loading ? "Investigating…" : "Investigate"}
          </button>
          <div className="muted small">
            Anything you leave out is found by scanning for the most anomalous match.
          </div>
        </div>
        <div className="card">
          <h3>Ground-truth scenarios</h3>
          <div className="examples">
            {CASE_GROUPS.map(([key, label]) => (
              <div key={key}>
                <div className="small muted" style={{ margin: "8px 8px 2px", fontWeight: 600 }}>{label}</div>
                {meta.examples
                  .filter((x) => x.case === key)
                  .map((x) => (
                    <button
                      key={x.id}
                      className="example"
                      onClick={() => {
                        setQuestion(x.question);
                        setProduct("");
                        setRegion("");
                        setMonth("");
                        run({ question: x.question });
                      }}
                    >
                      <code>{x.id}</code>
                      {x.question}
                    </button>
                  ))}
              </div>
            ))}
          </div>
        </div>
      </aside>
      <section className="stack">
        {error && <div className="card"><b>Request failed:</b> {error}</div>}
        {loading && !result && <div className="card empty"><span className="spinner" /> Running agents…</div>}
        {result && <Result inv={result} loading={loading} />}
      </section>
    </div>
  );
}

const LAYERS: { key: keyof Investigation["answer"]["layers"]; tag: string; title: string; color: string }[] = [
  { key: "descriptive", tag: "Descriptive", title: "What happened?", color: "var(--series-1)" },
  { key: "diagnostic", tag: "Diagnostic", title: "Why did it happen?", color: "var(--critical)" },
  { key: "predictive", tag: "Predictive", title: "What happens next?", color: "var(--series-2)" },
  { key: "prescriptive", tag: "Prescriptive", title: "What should we do?", color: "var(--good)" },
];

function Result({ inv, loading }: { inv: Investigation; loading: boolean }) {
  const [cite, setCite] = useState<number | null>(null);
  const a = inv.answer;
  const info = CASE_INFO[a.case];
  const conf = a.confidence;
  const confTone = conf.label === "high" ? "good" : conf.label === "medium" ? "warn" : "bad";
  const es = a.evidence_status;
  const sql = inv.agents.sql;
  const rag = inv.agents.rag;
  const rca = inv.agents.rca;

  useEffect(() => setCite(null), [inv]);

  const onCite = (id: number) => {
    setCite(id);
    document.getElementById(`src-${id}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  const prescriptive = (
    <ol>
      {a.actions.map((act, i) => (
        <li key={i}><RichText text={act} active={cite} onCite={onCite} /></li>
      ))}
    </ol>
  );

  return (
    <div className="stack" style={{ opacity: loading ? 0.55 : 1, transition: "opacity .2s" }}>
      <div className="card">
        <div className="row">
          <span className={`badge ${info.tone}`} title={info.text}>{info.label}</span>
          <span className={`badge ${confTone}`}>Confidence: {conf.label} ({Math.round(conf.score * 100)}%)</span>
          {a.cause.status !== "none" && (
            <span className="badge">Cause: {a.cause.label} · {a.cause.status}</span>
          )}
          <span className="spacer" />
          <span className="muted small">{inv.total_ms.toFixed(0)} ms · 5 agents</span>
        </div>
        <div className="headline">{a.headline}</div>
        <div className="grid-2">
          <div>
            <h3>Evidence available</h3>
            <ul className="status-list">
              <li><Mark ok={es.structured_available} /> Structured data (sales, inventory)</li>
              <li><Mark ok={es.structured_anomaly} /> Statistical anomaly in the numbers</li>
              <li><Mark ok={es.unstructured_available} /> Documents on file for this product</li>
              <li><Mark ok={es.unstructured_match} /> Document describing an incident</li>
            </ul>
          </div>
          <div>
            <h3>Confidence</h3>
            <div className="meter" style={{ marginBottom: 8 }}>
              <span style={{
                width: `${conf.score * 100}%`,
                background: confTone === "good" ? "var(--good)" : confTone === "warn" ? "var(--warning)" : "var(--critical)",
              }} />
            </div>
            <ul className="status-list small">
              {conf.reasons.map((r, i) => <li key={i}>• {r}</li>)}
            </ul>
          </div>
        </div>
        <div className="row small" style={{ marginTop: 12 }}>
          <span className="muted">Plan:</span>
          {(["product", "region", "month"] as const).map((k) => {
            const value = k === "product" ? inv.plan.product_name : k === "region" ? inv.plan.region : monthLabel(inv.plan.month);
            return (
              <span key={k} className="badge" title={inv.plan.resolution[k] ?? "not determined"}>
                {k}: {value ?? "—"}
                {inv.plan.resolution[k]?.startsWith("not in") ? " (scanned)" : ""}
              </span>
            );
          })}
          <span className="badge">intent: {inv.plan.intent}</span>
        </div>
        {inv.plan.notes.map((n, i) => <div key={i} className="small muted">{n}</div>)}
      </div>

      <div className="layers">
        {LAYERS.map((l) => (
          <div key={l.key} className="card layer" style={{ borderTopColor: l.color }}>
            <div className="tag">{l.tag}</div>
            <h2>{l.title}</h2>
            {l.key === "prescriptive" ? prescriptive : <p><RichText text={a.layers[l.key]} active={cite} onCite={onCite} /></p>}
          </div>
        ))}
      </div>

      <div className="card">
        <h2>Sources</h2>
        <ul className="sources">
          {a.citations.map((c) => (
            <li key={c.id} id={`src-${c.id}`} className={cite === c.id ? "on" : ""}>
              <span className="num">[{c.id}]</span>
              <span className="kind">{c.kind}</span>
              <span><b>{c.label}</b> <span className="muted">— {c.detail}</span></span>
            </li>
          ))}
        </ul>
      </div>

      {sql.available ? (
        <>
          <div className="card">
            <h2>Daily units sold: {inv.plan.product_name}, {inv.plan.region}</h2>
            <DailyChart inv={inv} />
          </div>
          <div className="grid-2">
            <div className="card">
              <h2>Monthly units/day vs. baseline</h2>
              <MonthlyChart inv={inv} />
            </div>
            <div className="card">
              <h2>Warehouse stock</h2>
              <StockChart inv={inv} />
            </div>
          </div>
        </>
      ) : (
        <div className="card muted">No structured data to chart: {sql.reason}</div>
      )}

      <div className="grid-2">
        <div className="card">
          <h2>RAG agent: retrieved documents</h2>
          {rag.available ? (
            <div className="stack" style={{ gap: 10 }}>
              <div className="small muted">
                {rag.index.method}. {rag.corpus_for_product} document(s) on file for this product
                {rag.window ? `; period window ${rag.window.from} to ${rag.window.to}` : ""}.
              </div>
              {rag.results.length === 0 && <div className="muted">No document passed the product/region/period filter.</div>}
              {rag.results.map((d) => (
                <div key={d.path} className={`doc ${d.role}`}>
                  <div className="row">
                    <b>{d.title}</b>
                    <span className="spacer" />
                    <span className={`badge ${d.role === "incident" ? "info" : ""}`}>
                      {d.role === "incident" ? d.cause_label : d.role}
                    </span>
                  </div>
                  <div className="small muted">
                    {d.filename} · {d.date} · region {d.region} · score{" "}
                    <span className="scorebar"><span style={{ width: `${Math.min(100, d.score * 100)}%` }} /></span>{" "}
                    {d.score.toFixed(2)}
                  </div>
                  <blockquote>{d.quote}</blockquote>
                </div>
              ))}
              {rag.excluded.length > 0 && (
                <details>
                  <summary>{rag.excluded.length} near-miss document(s) excluded by the metadata filter</summary>
                  <table style={{ marginTop: 6 }}>
                    <tbody>
                      {rag.excluded.map((e) => (
                        <tr key={e.path}>
                          <td>{e.path}</td>
                          <td className="muted">{e.reason}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </details>
              )}
            </div>
          ) : (
            <div className="muted">{rag.reason}</div>
          )}
        </div>
        <div className="card">
          <h2>RCA agent: structured checks</h2>
          {rca.available ? (
            <div className="stack" style={{ gap: 10 }}>
              <div className="small">
                Anomaly: <b>{rca.is_anomaly ? "yes" : "no"}</b> (score {rca.anomaly_score?.toFixed(1)}) · scope:{" "}
                <b>{rca.scope}</b>
                {rca.hypothesis && <> · data-only hypothesis: <b>{rca.hypothesis.label}</b></>}
              </div>
              <table>
                <tbody>
                  {rca.checks?.map((c) => (
                    <tr key={c.key}>
                      <td style={{ width: 90 }}>
                        <span className={`badge ${c.fired ? "bad" : ""}`}>{c.fired ? "▲ fired" : "normal"}</span>
                      </td>
                      <td><b>{c.key}</b> <span className="muted">{c.detail}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {rca.forecast && (
                <div className="small">
                  <b>Forecast ({rca.forecast.next_month}):</b> {rca.forecast.predicted_per_day.toLocaleString()} units/day (
                  {rca.forecast.predicted_pct_vs_baseline > 0 ? "+" : ""}
                  {rca.forecast.predicted_pct_vs_baseline}% vs. baseline)
                  {rca.forecast.actual_per_day !== null && (
                    <span className="muted">
                      {" "}· back-test: held-out actual {rca.forecast.actual_per_day.toLocaleString()} (
                      {rca.forecast.actual_pct_vs_baseline! > 0 ? "+" : ""}
                      {rca.forecast.actual_pct_vs_baseline}%)
                    </span>
                  )}
                  <div className="muted">{rca.forecast.method}</div>
                </div>
              )}
            </div>
          ) : (
            <div className="muted">{rca.reason}</div>
          )}
        </div>
      </div>

      <div className="card">
        <h2>Agent trace</h2>
        <ul className="trace">
          {inv.trace.map((t) => (
            <li key={t.agent}>
              <b>{t.agent}</b>
              <span className="muted">{t.ms.toFixed(1)} ms{t.parallel ? " ∥" : ""}</span>
              <span>{t.summary}</span>
            </li>
          ))}
        </ul>
        <details style={{ marginTop: 10 }}>
          <summary>Queries run by the SQL / NoSQL agent ({sql.queries.length})</summary>
          {sql.queries.map((q, i) => (
            <div key={i}>
              <div className="small muted" style={{ marginTop: 8 }}>
                {q.purpose}{q.params ? ` · params ${JSON.stringify(q.params)}` : ""}
              </div>
              <pre className="sql">{q.sql}</pre>
            </div>
          ))}
        </details>
      </div>
    </div>
  );
}

function Mark({ ok }: { ok: boolean }) {
  return <span className={ok ? "ok" : "no"} aria-label={ok ? "yes" : "no"}>{ok ? "✓" : "✗"}</span>;
}
