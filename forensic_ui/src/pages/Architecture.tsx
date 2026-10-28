import { Meta } from "../api";

const CASES = [
  ["Structured anomaly + matching document", "Full answer, both cited", "High", "good"],
  ["Structured anomaly only", "“No supporting unstructured evidence was found; the root cause is inferred from data patterns only.”", "Medium", "warn"],
  ["Document only, no anomaly", "“Sales data for this period does not show a statistically significant deviation; this issue may not yet be materially affecting sales.”", "Medium", "warn"],
  ["Neither", "“No anomaly detected and no related documents found for this product/period.” A valid answer; no story is forced.", "High (nothing happened)", "good"],
  ["Document and data disagree", "Data-pattern cause reported, document flagged as unconfirmed", "Medium", "warn"],
];

export default function Architecture({ meta }: { meta: Meta }) {
  return (
    <div className="stack">
      <div>
        <h1>How RetailIQ investigates</h1>
        <p className="lede">
          A question goes to an orchestrator, which fans out to specialist agents. A single synthesis agent then fuses
          their evidence into a four-layer answer (descriptive, diagnostic, predictive, prescriptive), where every claim
          is tied to a specific table slice, model or document.
        </p>
      </div>
      <div className="card">
        <div className="arch">
          <div className="node"><b>User question</b><span>"Why did iPhone 15 sales drop in North in March?"</span></div>
          <div className="arrow" />
          <div className="node key"><b>Orchestrator</b><span>extracts product, region, month, intent; scans for whatever the question leaves open</span></div>
          <div className="arrow" />
          <div className="fan">
            <div className="node"><b>SQL / NoSQL Analytics Agent</b><span>SQLite queries over sales, inventory, products, suppliers + catalog document store. Deterministic, no LLM.</span></div>
            <div className="node"><b>RAG Agent</b><span>paragraph chunks, TF-IDF vector index, metadata filter on product/region/date, incident vs. routine classifier</span></div>
            <div className="node"><b>Forecast / RCA Agent</b><span>robust z-score vs. leave-one-out baseline, structured signature, scope check, Holt-Winters forecast</span></div>
          </div>
          <div className="arrow" />
          <div className="node key"><b>Synthesis / XAI Agent</b><span>fuses evidence, applies the degradation rules, writes the only prescriptive text, attaches citations + confidence</span></div>
          <div className="arrow" />
          <div className="node"><b>Explained answer</b><span>4 layers · sources · confidence · agent trace</span></div>
        </div>
      </div>
      <div className="card table-wrap">
        <h2>Graceful degradation: the system never crashes or refuses</h2>
        <table>
          <thead><tr><th>Situation</th><th>Behaviour</th><th>Confidence</th></tr></thead>
          <tbody>
            {CASES.map(([s, b, c, tone]) => (
              <tr key={s}><td><b>{s}</b></td><td>{b}</td><td><span className={`badge ${tone}`}>{c}</span></td></tr>
            ))}
          </tbody>
        </table>
        <p className="small muted" style={{ marginBottom: 0 }}>
          Demo coverage: HomePod mini has sales data but no documents; Vision Pro has documents but no sales data.
        </p>
      </div>
      <div className="grid-2">
        <div className="card">
          <h2>Synthetic data, generated scenario-first</h2>
          <p style={{ marginTop: 0 }}>
            {meta.stats.scenarios} incident scenarios and {meta.stats.controls} controls in <code>forensic/scenarios.py</code>.
            Each scenario produces both its structured signature (sales, stock-outs, discounts, prices, returns) and the
            document someone would have written about it, linked by <code>product_id</code>, <code>region</code> and
            month. All other months are noise only, which is the control group.
          </p>
          <ul className="status-list">
            <li>• {meta.stats.sales_rows.toLocaleString()} daily sales rows, the same number of inventory rows</li>
            <li>• {meta.stats.documents} documents ({meta.stats.incident_documents} incidents, the rest routine or policy distractors)</li>
            <li>• {meta.products.length} products × {meta.regions.length} regions × {meta.months.length} months</li>
          </ul>
        </div>
        <div className="card">
          <h2>Why every step is deterministic</h2>
          <p style={{ marginTop: 0 }}>
            Numbers come from SQL, never from a language model. Causes come from the documents' own wording, checked
            against the structured signature. A document only counts as an explanation if its cause is compatible with
            what the numbers show; for example, a stock-out is compatible with a supplier delay or a logistics
            disruption, but not with a discount. The result is reproducible and auditable, and it is scored against
            ground truth on the Evaluation page.
          </p>
        </div>
      </div>
    </div>
  );
}
