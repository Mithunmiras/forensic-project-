import { useEffect, useRef, useState } from "react";
import { api, CASE_INFO, Investigation, Meta, monthLabel, Summary } from "../api";
import RichText from "../components/RichText";
import Icon from "../components/Icon";
import { DailyChart, MonthlyChart, StockChart } from "../components/Charts";
import { useMediaQuery } from "../hooks";

export interface InvestigateRequest {
  question: string;
  product_id?: string;
  region?: string;
  month?: string;
  nonce?: number;
}

const CASE_GROUPS: [string, string, string][] = [
  ["full", "Data + documents", "var(--good)"],
  ["structured_only", "Data only", "var(--warning)"],
  ["unstructured_only", "Documents only", "var(--accent)"],
  ["none", "Controls: nothing happened", "var(--muted)"],
];

export default function Investigate({ meta, pending }: { meta: Meta; pending: InvestigateRequest | null }) {
  const wide = useMediaQuery("(min-width: 1101px)");
  const [question, setQuestion] = useState(meta.examples[0]?.question ?? "");
  const [product, setProduct] = useState("");
  const [region, setRegion] = useState("");
  const [month, setMonth] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [showExamples, setShowExamples] = useState(wide);
  const [result, setResult] = useState<Investigation | null>(null);
  const [summary, setSummary] = useState<Summary | "loading" | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);
  const runId = useRef(0);
  const resultRef = useRef<HTMLDivElement>(null);

  useEffect(() => setShowExamples(wide), [wide]);

  const run = (req: InvestigateRequest, scroll = false) => {
    setLoading(true);
    setError(null);
    const body = {
      question: req.question,
      product_id: req.product_id || undefined,
      region: req.region || undefined,
      month: req.month || undefined,
    };
    const id = ++runId.current;
    api
      .investigate(body)
      .then((r) => {
        if (id !== runId.current) return;
        setResult(r);
        setSummary(null);
        if (meta.llm.enabled) {
          setSummary("loading");
          // Ask with the resolved plan so the briefing describes exactly this investigation.
          api.summary({ question: r.question, product_id: r.plan.product_id ?? undefined,
            region: r.plan.region ?? undefined, month: r.plan.month ?? undefined })
            .then((s) => id === runId.current && setSummary(s))
            .catch((e) => id === runId.current && setSummary({ available: false, reason: String(e) }));
        }
        if (scroll && !wide) resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      })
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
    if (pending.product_id || pending.region || pending.month) setShowFilters(true);
    run(pending);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pending]);

  const submit = () => {
    if (question.trim().length >= 3) run({ question, product_id: product, region, month }, true);
  };
  const pick = (q: string) => {
    setQuestion(q);
    setProduct("");
    setRegion("");
    setMonth("");
    run({ question: q }, true);
  };
  const activeFilters = [product, region, month].filter(Boolean).length;

  return (
    <div className="inv-layout">
      <aside className="inv-side stack">
        <div className="card stack" style={{ gap: 12 }}>
          <div>
            <h2 style={{ margin: 0 }}>Ask a business question</h2>
            <div className="small muted">Plain English. Anything you leave out is found by scanning for the most unusual match.</div>
          </div>
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
            aria-label="Question"
          />
          <div className="row" style={{ flexWrap: "nowrap" }}>
            <button className="btn" style={{ flex: 1 }} onClick={submit} disabled={loading}>
              {loading ? <span className="spinner" /> : <Icon name="search" size={16} />}
              {loading ? "Investigating…" : "Investigate"}
            </button>
            <button className="btn secondary" onClick={() => setShowFilters((s) => !s)} aria-expanded={showFilters}>
              <Icon name="filter" size={16} />
              {activeFilters ? `Filters (${activeFilters})` : "Filters"}
            </button>
          </div>
          {showFilters && (
            <div className="filters fade-in">
              <label className="field">
                Product
                <select value={product} onChange={(e) => setProduct(e.target.value)}>
                  <option value="">From question</option>
                  {meta.products.map((p) => <option key={p.product_id} value={p.product_id}>{p.product_name}</option>)}
                </select>
              </label>
              <label className="field">
                Region
                <select value={region} onChange={(e) => setRegion(e.target.value)}>
                  <option value="">From question</option>
                  {meta.regions.map((r) => <option key={r}>{r}</option>)}
                </select>
              </label>
              <label className="field full">
                Month
                <select value={month} onChange={(e) => setMonth(e.target.value)}>
                  <option value="">From question</option>
                  {meta.months.map((m) => <option key={m} value={m}>{monthLabel(m)}</option>)}
                </select>
              </label>
            </div>
          )}
        </div>

        <div className="card">
          <button className="disclosure" onClick={() => setShowExamples((s) => !s)} aria-expanded={showExamples}>
            Ground-truth scenarios <span className="badge">{meta.examples.length}</span>
            <span className="chev"><Icon name="chevron" size={18} /></span>
          </button>
          {!showExamples && (
            <div className="chips" style={{ marginTop: 12 }}>
              {meta.examples.filter((x) => ["SC01", "SC12", "SC13", "SC14", "CT03"].includes(x.id)).map((x) => (
                <button key={x.id} className={`chip ${question === x.question ? "on" : ""}`} onClick={() => pick(x.question)}>
                  {x.id}: {x.question.replace(/^(Why|What|Is|Explain)\s+/, "").slice(0, 42)}…
                </button>
              ))}
            </div>
          )}
          {showExamples && (
            <div className="examples fade-in">
              {CASE_GROUPS.map(([key, label, color]) => (
                <div key={key}>
                  <div className="group-label"><span className="dot" style={{ background: color }} />{label}</div>
                  {meta.examples.filter((x) => x.case === key).map((x) => (
                    <button key={x.id} className={`example ${question === x.question ? "on" : ""}`} onClick={() => pick(x.question)}>
                      <code>{x.id}</code>
                      {x.question}
                    </button>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>
      </aside>

      <section className="stack" ref={resultRef} style={{ scrollMarginTop: 76 }}>
        {error && <div className="card"><b>Request failed:</b> {error}</div>}
        {loading && !result && <Skeleton />}
        {result && <Result key={result.question + result.total_ms} inv={result} loading={loading} summary={summary} />}
      </section>
    </div>
  );
}

function Skeleton() {
  return (
    <div className="stack">
      <div className="card stack" style={{ gap: 12 }}>
        <div className="skeleton" style={{ height: 22, width: "40%" }} />
        <div className="skeleton" style={{ height: 26, width: "90%" }} />
        <div className="skeleton" style={{ height: 60 }} />
      </div>
      <div className="layers">
        {[0, 1, 2, 3].map((i) => <div key={i} className="card"><div className="skeleton" style={{ height: 120 }} /></div>)}
      </div>
    </div>
  );
}

function Ring({ score, tone }: { score: number; tone: string }) {
  const r = 30;
  const c = 2 * Math.PI * r;
  const color = tone === "good" ? "var(--good)" : tone === "warn" ? "var(--warning)" : "var(--critical)";
  return (
    <svg className="ring" width={76} height={76} viewBox="0 0 76 76" role="img" aria-label={`Confidence ${Math.round(score * 100)}%`}>
      <circle cx={38} cy={38} r={r} fill="none" stroke="var(--surface-2)" strokeWidth={8} />
      <circle cx={38} cy={38} r={r} fill="none" stroke={color} strokeWidth={8} strokeLinecap="round"
        strokeDasharray={`${c * score} ${c}`} transform="rotate(-90 38 38)" style={{ transition: "stroke-dasharray .6s" }} />
      <text x={38} y={43} textAnchor="middle" fontSize={17} fontWeight={750} fill="var(--text)">{Math.round(score * 100)}%</text>
    </svg>
  );
}

const LAYERS: { key: keyof Investigation["answer"]["layers"]; tag: string; title: string; color: string; icon: string }[] = [
  { key: "descriptive", tag: "Descriptive", title: "What happened?", color: "var(--series-1)", icon: "what" },
  { key: "diagnostic", tag: "Diagnostic", title: "Why did it happen?", color: "var(--critical)", icon: "why" },
  { key: "predictive", tag: "Predictive", title: "What happens next?", color: "var(--series-2)", icon: "next" },
  { key: "prescriptive", tag: "Prescriptive", title: "What should we do?", color: "var(--good)", icon: "todo" },
];

type EvTab = "charts" | "documents" | "checks" | "sources" | "trace";

function AISummary({ s, citations, onCite, active }: {
  s: Summary | "loading"; citations: Investigation["answer"]["citations"]; onCite: (id: number) => void; active: number | null;
}) {
  return (
    <div className="card ai-card fade-in">
      <div className="row" style={{ marginBottom: 8 }}>
        <span className="layer-icon ai-icon"><Icon name="spark" size={17} /></span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="tag">AI analyst briefing</div>
          <div className="small muted">
            {s === "loading" ? "Writing from the agents' evidence…" : s.available ? `${s.model} · ${s.ms} ms` : "Unavailable"}
          </div>
        </div>
        {s !== "loading" && s.available && (
          <span className={`badge ${s.grounded ? "good" : "bad"}`}
            title="Every number and citation in the briefing must appear in the agents' evidence">
            {s.grounded ? "✓ grounded in evidence" : "✗ failed grounding check"}
          </span>
        )}
      </div>
      {s === "loading" && (
        <div className="stack" style={{ gap: 8 }}>
          <div className="skeleton" style={{ height: 14 }} />
          <div className="skeleton" style={{ height: 14, width: "92%" }} />
          <div className="skeleton" style={{ height: 14, width: "70%" }} />
        </div>
      )}
      {s !== "loading" && s.available && s.grounded && (
        <p style={{ margin: 0 }}><RichText text={s.text ?? ""} active={active} onCite={onCite} citations={citations} /></p>
      )}
      {s !== "loading" && s.available && !s.grounded && (
        <p className="small" style={{ margin: 0 }}>
          The briefing was withheld because it stated things that are not in the evidence: {s.problems?.join("; ")}.
          The four layers below are unaffected.
        </p>
      )}
      {s !== "loading" && !s.available && <p className="small muted" style={{ margin: 0 }}>{s.reason}</p>}
    </div>
  );
}

function Result({ inv, loading, summary }: { inv: Investigation; loading: boolean; summary: Summary | "loading" | null }) {
  const [cite, setCite] = useState<number | null>(null);
  const [showReasons, setShowReasons] = useState(false);
  const a = inv.answer;
  const sql = inv.agents.sql;
  const rag = inv.agents.rag;
  const rca = inv.agents.rca;
  const [tab, setTab] = useState<EvTab>(sql.available ? "charts" : "documents");
  const evRef = useRef<HTMLDivElement>(null);
  const info = CASE_INFO[a.case];
  const conf = a.confidence;
  const tone = conf.label === "high" ? "good" : conf.label === "medium" ? "warn" : "bad";
  const es = a.evidence_status;

  const onCite = (id: number) => {
    setCite(id);
    setTab("sources");
    setTimeout(() => {
      const el = document.getElementById(`src-${id}`) ?? evRef.current;
      el?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 30);
  };

  const tiles: [boolean, string][] = [
    [es.structured_available, "Sales & inventory data"],
    [es.structured_anomaly, "Statistical anomaly"],
    [es.unstructured_available, "Documents on file"],
    [es.unstructured_match, "Incident document"],
  ];
  const tabs: [EvTab, string, string, number | null][] = [
    ["charts", "Charts", "chart", null],
    ["documents", "Documents", "doc", rag.results?.length ?? 0],
    ["checks", "Checks", "list", null],
    ["sources", "Sources", "link", a.citations.length],
    ["trace", "Agent trace", "trace", inv.trace.length],
  ];

  return (
    <div className="stack fade-in" style={{ opacity: loading ? 0.5 : 1, transition: "opacity .2s" }}>
      <div className="card">
        <div className="summary">
          <div className="ring-wrap">
            <div>
              <Ring score={conf.score} tone={tone} />
              <div className="ring-label">{conf.label} confidence</div>
            </div>
          </div>
          <div style={{ minWidth: 0 }}>
            <div className="row">
              <span className={`badge ${info.tone}`} title={info.text}>{info.label}</span>
              {a.cause.status !== "none" && <span className="badge">{a.cause.label} · {a.cause.status}</span>}
              <span className="spacer" />
              <span className="muted small">{inv.total_ms.toFixed(0)} ms · 5 agents</span>
            </div>
            <div className="headline">{a.headline}</div>
            <div className="row small">
              {(["product", "region", "month"] as const).map((k) => {
                const value = k === "product" ? inv.plan.product_name : k === "region" ? inv.plan.region : monthLabel(inv.plan.month);
                const how = inv.plan.resolution[k] ?? "";
                const scanned = how.startsWith("not in");
                const byLlm = how.startsWith("inferred by the LLM");
                return (
                  <span key={k} className={`badge ${scanned || byLlm ? "info" : ""}`} title={how || "not determined"}>
                    {value ?? `no ${k}`}{scanned ? " · scanned" : byLlm ? " · AI" : ""}
                  </span>
                );
              })}
              <span className="badge">intent: {inv.plan.intent}</span>
            </div>
          </div>
        </div>
        <div className="evidence-tiles">
          {tiles.map(([ok, label]) => (
            <div key={label} className={`tile ${ok ? "yes" : "no"}`}>
              <span className="ico" aria-hidden="true">{ok ? "✓" : "✗"}</span>
              <span><span className="sr-only">{ok ? "Yes: " : "No: "}</span>{label}</span>
            </div>
          ))}
        </div>
        <button className="btn ghost small" style={{ marginTop: 8, paddingLeft: 0 }} onClick={() => setShowReasons((s) => !s)}
          aria-expanded={showReasons}>
          Why this confidence? <Icon name="chevron" size={14} />
        </button>
        {showReasons && (
          <ul className="reasons fade-in">
            {conf.reasons.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        )}
        {inv.plan.notes.map((n, i) => <div key={i} className="small muted">{n}</div>)}
      </div>

      {summary && <AISummary s={summary} citations={a.citations} onCite={onCite} active={cite} />}

      <div className="layers">
        {LAYERS.map((l) => (
          <div key={l.key} className="card layer" style={{ ["--layer-color" as string]: l.color }}>
            <div className="layer-head">
              <span className="layer-icon"><Icon name={l.icon} size={17} /></span>
              <div>
                <div className="tag">{l.tag}</div>
                <h2>{l.title}</h2>
              </div>
            </div>
            {l.key === "prescriptive" ? (
              <ol>
                {a.actions.map((act, i) => (
                  <li key={i}><RichText text={act} active={cite} onCite={onCite} citations={a.citations} /></li>
                ))}
              </ol>
            ) : (
              <p><RichText text={a.layers[l.key]} active={cite} onCite={onCite} citations={a.citations} /></p>
            )}
          </div>
        ))}
      </div>

      <div className="card" ref={evRef} style={{ scrollMarginTop: 76 }}>
        <div className="tabs" role="tablist">
          {tabs.map(([key, label, icon, count]) => (
            <button key={key} role="tab" aria-selected={tab === key} className={tab === key ? "active" : ""} onClick={() => setTab(key)}>
              <Icon name={icon} size={15} />
              {label}
              {count !== null && <span className="count">{count}</span>}
            </button>
          ))}
        </div>

        {tab === "charts" && (
          sql.available ? (
            <div className="stack fade-in">
              <div>
                <h2>Daily units sold: {inv.plan.product_name}, {inv.plan.region}</h2>
                <DailyChart inv={inv} />
              </div>
              <div className="grid-2">
                <div>
                  <h2>Monthly units/day vs. baseline</h2>
                  <MonthlyChart inv={inv} />
                </div>
                <div>
                  <h2>Warehouse stock</h2>
                  <StockChart inv={inv} />
                </div>
              </div>
            </div>
          ) : <div className="empty">No structured data to chart. {sql.reason}</div>
        )}

        {tab === "documents" && (
          <div className="stack fade-in" style={{ gap: 10 }}>
            {rag.available ? (
              <>
                <div className="small muted">
                  {rag.index.method}. {rag.corpus_for_product} document(s) on file for this product
                  {rag.window ? `; period window ${rag.window.from} to ${rag.window.to}` : ""}.
                </div>
                {rag.results.length === 0 && <div className="empty">No document passed the product/region/period filter.</div>}
                {rag.results.map((d) => (
                  <div key={d.path} className={`doc ${d.role}`}>
                    <div className="row" style={{ alignItems: "flex-start" }}>
                      <span className="title" style={{ flex: 1, minWidth: 0 }}>{d.title}</span>
                      <span className={`badge ${d.role === "incident" ? "info" : ""}`}>{d.role === "incident" ? d.cause_label : d.role}</span>
                    </div>
                    <div className="small muted meta">
                      {d.filename} · {d.date} · region {d.region} · relevance{" "}
                      <span className="scorebar"><span style={{ width: `${Math.min(100, d.score * 100)}%` }} /></span> {d.score.toFixed(2)}
                    </div>
                    <blockquote>{d.quote}</blockquote>
                  </div>
                ))}
                {rag.excluded.length > 0 && (
                  <details>
                    <summary>{rag.excluded.length} near-miss document(s) excluded by the metadata filter</summary>
                    <div className="table-wrap">
                      <table style={{ marginTop: 6 }}>
                        <tbody>
                          {rag.excluded.map((e) => (
                            <tr key={e.path}><td style={{ overflowWrap: "anywhere" }}>{e.path}</td><td className="muted">{e.reason}</td></tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </details>
                )}
              </>
            ) : <div className="empty">{rag.reason}</div>}
          </div>
        )}

        {tab === "checks" && (
          <div className="stack fade-in" style={{ gap: 12 }}>
            {rca.available ? (
              <>
                <div className="row small">
                  <span className={`badge ${rca.is_anomaly ? "bad" : "good"}`}>{rca.is_anomaly ? "Anomaly" : "Normal"} · score {rca.anomaly_score?.toFixed(1)}</span>
                  <span className="badge">scope: {rca.scope}</span>
                  {rca.hypothesis && <span className="badge">data-only hypothesis: {rca.hypothesis.label}</span>}
                </div>
                <div className="checks">
                  {rca.checks?.map((c) => (
                    <div key={c.key} className="check">
                      <span className={`badge ${c.fired ? "bad" : ""}`}>{c.fired ? "▲ fired" : "normal"}</span>
                      <span><b>{c.key}</b> <span className="muted">· {c.detail}</span></span>
                    </div>
                  ))}
                </div>
                {rca.forecast && (
                  <div className="small">
                    <b>Forecast for {monthLabel(rca.forecast.next_month)}:</b> {rca.forecast.predicted_per_day.toLocaleString()} units/day (
                    {rca.forecast.predicted_pct_vs_baseline > 0 ? "+" : ""}{rca.forecast.predicted_pct_vs_baseline}% vs. baseline)
                    {rca.forecast.actual_per_day !== null && (
                      <span className="muted"> · back-test: held-out actual {rca.forecast.actual_per_day.toLocaleString()} (
                        {rca.forecast.actual_pct_vs_baseline! > 0 ? "+" : ""}{rca.forecast.actual_pct_vs_baseline}%)</span>
                    )}
                    <div className="muted">{rca.forecast.method}</div>
                  </div>
                )}
              </>
            ) : <div className="empty">{rca.reason}</div>}
          </div>
        )}

        {tab === "sources" && (
          <ul className="sources fade-in">
            {a.citations.map((c) => (
              <li key={c.id} id={`src-${c.id}`} className={cite === c.id ? "on" : ""}>
                <span className="num">[{c.id}]</span>
                <span className="kind">{c.kind}</span>
                <span className="detail"><b>{c.label}</b> <span className="muted">· {c.detail}</span></span>
              </li>
            ))}
          </ul>
        )}

        {tab === "trace" && (
          <div className="fade-in">
            <ul className="trace">
              {inv.trace.map((t, i) => (
                <li key={t.agent}>
                  <span className="step">{i + 1}</span>
                  <b>{t.agent}</b>
                  <span className="muted">{t.ms.toFixed(1)} ms{t.parallel ? " · parallel" : ""}</span>
                  <span style={{ overflowWrap: "anywhere" }}>{t.summary}</span>
                </li>
              ))}
            </ul>
            <details style={{ marginTop: 10 }}>
              <summary>Queries run by the SQL / NoSQL agent ({sql.queries.length})</summary>
              {sql.queries.map((q, i) => (
                <div key={i}>
                  <div className="small muted" style={{ marginTop: 8 }}>{q.purpose}{q.params ? ` · params ${JSON.stringify(q.params)}` : ""}</div>
                  <pre className="sql">{q.sql}</pre>
                </div>
              ))}
            </details>
          </div>
        )}
      </div>
    </div>
  );
}
