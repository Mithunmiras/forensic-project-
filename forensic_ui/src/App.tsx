import { useEffect, useState } from "react";
import { api, Meta } from "./api";
import Investigate, { InvestigateRequest } from "./pages/Investigate";
import Scan from "./pages/Scan";
import Library from "./pages/Library";
import EvaluationPage from "./pages/Evaluation";
import Architecture from "./pages/Architecture";

const TABS = [
  ["investigate", "Investigate"],
  ["scan", "Anomaly scan"],
  ["library", "Evidence library"],
  ["evaluation", "Evaluation"],
  ["architecture", "How it works"],
] as const;
type Tab = (typeof TABS)[number][0];

export default function App() {
  const [tab, setTab] = useState<Tab>("investigate");
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<InvestigateRequest | null>(null);

  useEffect(() => {
    api.meta().then(setMeta).catch((e) => setError(String(e)));
  }, []);

  const investigate = (req: InvestigateRequest) => {
    setPending({ ...req, nonce: Date.now() });
    setTab("investigate");
    window.scrollTo({ top: 0 });
  };

  return (
    <>
      <header className="topbar">
        <div className="brand">
          <img src="/favicon.svg" width={24} height={24} alt="" />
          RetailIQ <small>Forensic Analytics</small>
        </div>
        <nav className="nav">
          {TABS.map(([key, label]) => (
            <button key={key} className={tab === key ? "active" : ""} onClick={() => setTab(key)}>
              {label}
            </button>
          ))}
        </nav>
      </header>
      <main>
        {error && (
          <div className="card">
            <b>Cannot reach the API.</b> Start the backend with <code>.venv/bin/python -m forensic serve</code>.
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
        {!meta && !error && (
          <div className="empty">
            <span className="spinner" /> Loading…
          </div>
        )}
      </main>
    </>
  );
}
