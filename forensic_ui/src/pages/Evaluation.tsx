import { useEffect, useState } from "react";
import { api, Evaluation } from "../api";
import Icon from "../components/Icon";
import type { InvestigateRequest } from "./Investigate";

const METRICS: [string, string][] = [
  ["root_cause_accuracy", "Correct root cause (scenarios)"],
  ["no_false_cause_on_controls", "No invented cause (controls)"],
  ["correct_document_cited", "Correct document cited"],
  ["evidence_case_accuracy", "Correct evidence case"],
  ["confidence_label_accuracy", "Correct confidence label"],
  ["entity_extraction_accuracy", "Correct product/region/month"],
];

const Pass = ({ ok }: { ok: boolean }) =>
  ok ? <span className="badge good">✓ pass</span> : <span className="badge bad">✗ fail</span>;

export default function EvaluationPage({ onInvestigate }: { onInvestigate: (r: InvestigateRequest) => void }) {
  const [data, setData] = useState<Evaluation | null>(null);
  const [loading, setLoading] = useState(false);

  const load = (refresh = false) => {
    setLoading(true);
    api.evaluation(refresh).then(setData).finally(() => setLoading(false));
  };
  useEffect(() => load(), []);

  return (
    <div className="stack">
      <div className="page-head row" style={{ alignItems: "flex-end" }}>
        <div style={{ flex: "1 1 420px" }}>
          <h1>Evaluation against ground truth</h1>
          <p className="lede">
            Every question in <code>scenarios.py</code> runs through the full pipeline. A result passes only if the agents
            find the <i>injected</i> cause, cite the right document, and report the right evidence case and confidence.
            Controls are months with nothing injected, where the right answer is "nothing happened". Tap a row to open
            that investigation.
          </p>
        </div>
        <button className="btn secondary" onClick={() => load(true)} disabled={loading}>
          {loading ? <span className="spinner" /> : <Icon name="refresh" size={16} />}
          {loading ? "Running…" : "Re-run"}
        </button>
      </div>
      {data && !data.available ? (
        <div className="card stack" style={{ gap: 8 }}>
          <h2 style={{ margin: 0 }}>No answer key for real data</h2>
          <p style={{ margin: 0 }}>{data.reason}</p>
          <p className="small muted" style={{ margin: 0 }}>
            On real data, check the method by whether independent sources agree. For example, the late-delivery rate
            (from delivery timestamps) and the delivery complaints mined from review text both spike in Nov 2017 and
            Feb–Mar 2018. Switch the dataset to <b>Synthetic</b> (top right) to see the scored evaluation.
          </p>
        </div>
      ) : !data ? (
        <div className="grid-4">
          {[0, 1, 2, 3].map((i) => <div key={i} className="card"><div className="skeleton" style={{ height: 52 }} /></div>)}
        </div>
      ) : (
        <>
          <div className="grid-4" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))" }}>
            {METRICS.map(([k, label]) => {
              const m = data.summary[k];
              return (
                <div key={k} className={`card stat ${m.correct === m.total ? "good" : ""}`}>
                  <div className="value">{m.correct}/{m.total}</div>
                  <div className="label">{label}</div>
                </div>
              );
            })}
          </div>

          <div className="card table-wrap eval-table" style={{ padding: 0 }}>
            <table>
              <thead>
                <tr>
                  <th>ID</th><th>Question</th><th>Expected</th><th>Predicted</th><th>Case</th>
                  <th>Confidence</th><th>Doc</th><th>Result</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((r) => (
                  <tr key={r.id} className="clickable" onClick={() => onInvestigate({ question: r.question })}>
                    <td><code>{r.id}</code></td>
                    <td>{r.question}<div className="small muted">{r.target}</div></td>
                    <td>{r.expected_cause}</td>
                    <td className={r.cause_ok ? "" : "no"}>{r.predicted_cause}</td>
                    <td className={r.case_ok ? "" : "no"}>{r.predicted_case}</td>
                    <td className={r.confidence_ok ? "" : "no"}>{r.predicted_confidence} ({Math.round(r.confidence_score * 100)}%)</td>
                    <td>{r.expected_document ? (r.citation_ok ? "✓" : "✗") : <span className="muted">n/a</span>}</td>
                    <td><Pass ok={r.all_ok} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="eval-cards">
            {data.rows.map((r) => (
              <div key={r.id} className="card eval-card" role="button" tabIndex={0}
                onClick={() => onInvestigate({ question: r.question })}
                onKeyDown={(e) => e.key === "Enter" && onInvestigate({ question: r.question })}>
                <div className="row">
                  <code>{r.id}</code>
                  <span className="muted small">{r.target}</span>
                  <span className="spacer" />
                  <Pass ok={r.all_ok} />
                </div>
                <div className="q">{r.question}</div>
                <dl className="kv">
                  <dt>Expected</dt><dd>{r.expected_cause}</dd>
                  <dt>Predicted</dt><dd>{r.predicted_cause}</dd>
                  <dt>Case</dt><dd>{r.predicted_case}</dd>
                  <dt>Confidence</dt><dd>{r.predicted_confidence} ({Math.round(r.confidence_score * 100)}%)</dd>
                </dl>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
