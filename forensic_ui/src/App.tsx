import { useEffect, useState } from "react";
import { api, Meta } from "./api";
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

export default function App() {
  const [tab, setTab] = useState<Tab>("investigate");
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<InvestigateRequest | null>(null);
  const [theme, setTheme] = useTheme();

  useEffect(() => {
    api.meta().then(setMeta).catch((e) => setError(String(e)));
  }, []);

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
          <>
            <div hidden={tab !== "investigate"}>
              <Investigate meta={meta} pending={pending} />
            </div>
            {tab === "scan" && <Scan meta={meta} onInvestigate={investigate} />}
            {tab === "library" && <Library meta={meta} />}
            {tab === "evaluation" && <EvaluationPage onInvestigate={investigate} />}
            {tab === "architecture" && <Architecture meta={meta} />}
          </>
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
