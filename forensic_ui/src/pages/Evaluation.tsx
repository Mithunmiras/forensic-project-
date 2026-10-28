import { useEffect, useState } from "react";
import { api, Evaluation } from "../api";
import type { InvestigateRequest } from "./Investigate";

const METRICS: [string, string][] = [
  ["root_cause_accuracy", "Correct root cause (scenarios)"],
  ["no_false_cause_on_controls", "No invented cause (controls)"],
  ["correct_document_cited", "Correct document cited"],
  ["evidence_case_accuracy", "Correct evidence case"],
  ["confidence_label_accuracy", "Correct confidence label"],
  ["entity_extraction_accuracy", "Correct product/region/month"],
];

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
      <div className="row">
        <div>
          <h1>Evaluation against ground truth</h1>
          <p className="lede">
            Each scenario's question from <code>scenarios.py</code> is run through the full pipeline. The answer counts
            only if the agents find the <i>injected</i> cause, cite the right document, and report the right evidence
            case and confidence. Controls are months with no injected cause, where the correct answer is "nothing
            happened".
          </p>
        </div>
        <span className="spacer" />
        <button className="btn secondary" onClick={() => load(true)} disabled={loading}>
          {loading ? "Running…" : "Re-run evaluation"}
        </button>
      </div>
      {!data ? (
        <div className="empty"><span className="spinner" /> Running all investigations…</div>
      ) : (
        <>
          <div className="grid-4" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))" }}>
            {METRICS.map(([k, label]) => {
              const m = data.summary[k];
              return (
                <div key={k} className="card stat">
                  <div className="value">{m.correct}/{m.total}</div>
                  <div className="label">{label}</div>
                </div>
              );
            })}
          </div>
          <div className="card table-wrap" style={{ padding: 0 }}>
            <table>
              <thead>
                <tr>
                  <th>ID</th><th>Question</th><th>Expected cause</th><th>Predicted</th><th>Case</th>
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
                    <td className={r.confidence_ok ? "" : "no"}>
                      {r.predicted_confidence} ({Math.round(r.confidence_score * 100)}%)
                    </td>
                    <td>
                      {r.expected_document
                        ? (r.citation_ok ? <span className="ok">✓</span> : <span className="no">✗</span>)
                        : <span className="muted">n/a</span>}
                    </td>
                    <td>{r.all_ok ? <span className="badge good">✓ pass</span> : <span className="badge bad">✗ fail</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
