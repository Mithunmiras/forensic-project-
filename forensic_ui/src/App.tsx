import { useEffect, useState } from "react";
import { api, DatasetInfo, Meta, setDataset } from "./api";
import Icon from "./components/Icon";
import { Theme, useTheme } from "./hooks";
import Investigate, { InvestigateRequest } from "./pages/Investigate";
import Scan from "./pages/Scan";
import Library from "./pages/Library";
import EvaluationPage from "./pages/Evaluation";
import Architecture from "./pages/Architecture";

const TABS = [
  ["investigate", "Investigate", "Investigate", "search"],
  ["scan", "Anomaly scan", "Scan", "grid"],
  ["library", "Evidence library", "Evidence", "file"],
  ["evaluation", "Evaluation", "Evaluation", "check"],
  ["architecture", "How it works", "About", "info"],
] as const;
type Tab = (typeof TABS)[number][0];

const THEMES: [Theme, string, string][] = [
  ["light", "sun", "Light theme"],
  ["auto", "auto", "Match system"],
  ["dark", "moon", "Dark theme"],
];

function readDataset(): string {
  try {
    return localStorage.getItem("retailiq-dataset") || "synthetic";
  } catch {
    return "synthetic";
  }
}

export default function App() {
  const [tab, setTab] = useState<Tab>("investigate");
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<InvestigateRequest | null>(null);
  const [theme, setTheme] = useTheme();
  const [dataset, setDs] = useState(readDataset);
  const [known, setKnown] = useState<DatasetInfo[]>([]);

  useEffect(() => {
    setDataset(dataset);
    setMeta(null);
    setError(null);
    setPending(null);
    api.meta()
      .then((m) => {
        setMeta(m);
        setKnown(m.datasets.filter((d) => d.available));
      })
      .catch((e) => {
        if (dataset !== "synthetic") setDs("synthetic"); // e.g. the real dataset is not imported here
        else setError(String(e));
      });
    try {
      localStorage.setItem("retailiq-dataset", dataset);
    } catch {
      /* storage unavailable: the choice lasts for this visit */
    }
  }, [dataset]);

  const go = (t: Tab) => {
    setTab(t);
    window.scrollTo({ top: 0 });
  };
  const investigate = (req: InvestigateRequest) => {
    setPending({ ...req, nonce: Date.now() });
    go("investigate");
  };

  return (
    <>
      <header className="topbar">
        <div className="brand">
          <img src="/favicon.svg" width={26} height={26} alt="" />
          RetailIQ <small>Forensic Analytics</small>
        </div>
        <nav className="nav" aria-label="Main">
          {TABS.map(([key, label, , icon]) => (
            <button key={key} className={tab === key ? "active" : ""} onClick={() => go(key)}>
              <Icon name={icon} size={16} />
              {label}
            </button>
          ))}
        </nav>
        <span className="spacer" />
        {known.length > 1 && (
          <select className="ds-select" value={dataset} onChange={(e) => setDs(e.target.value)} aria-label="Dataset"
            title={meta?.dataset.description}>
            {known.map((d) => (
              <option key={d.key} value={d.key}>{d.key === "olist" ? "Real data · Olist" : "Synthetic · ground truth"}</option>
            ))}
          </select>
        )}
        <div className="theme-toggle" role="radiogroup" aria-label="Theme">
          {THEMES.map(([t, icon, label]) => (
            <button key={t} className={theme === t ? "on" : ""} onClick={() => setTheme(t)} title={label}
              aria-label={label} role="radio" aria-checked={theme === t}>
              <Icon name={icon} size={15} />
            </button>
          ))}
        </div>
      </header>

      <main>
        {error && (
          <div className="card">
            <b>Cannot reach the API.</b> Start the backend with <code>./run_forensic.sh</code>.
            <div className="muted small">{error}</div>
          </div>
        )}
        {meta && (
          <div key={meta.dataset.key}>
            {!meta.dataset.has_ground_truth && (
              <div className="ds-banner">
                <b>Real data:</b> {meta.dataset.description} <span className="muted">Source: {meta.dataset.source}.</span>
              </div>
            )}
            <div hidden={tab !== "investigate"}>
              <Investigate meta={meta} pending={pending} />
            </div>
            {tab === "scan" && <Scan meta={meta} onInvestigate={investigate} />}
            {tab === "library" && <Library meta={meta} />}
            {tab === "evaluation" && <EvaluationPage onInvestigate={investigate} />}
            {tab === "architecture" && <Architecture meta={meta} />}
          </div>
        )}
        {!meta && !error && <div className="empty"><span className="spinner" /> Loading…</div>}
      </main>

      <nav className="bottom-nav" aria-label="Main">
        {TABS.map(([key, , short, icon]) => (
          <button key={key} className={tab === key ? "active" : ""} onClick={() => go(key)}
            aria-current={tab === key ? "page" : undefined}>
            <Icon name={icon} size={21} />
            {short}
          </button>
        ))}
      </nav>
    </>
  );
}
