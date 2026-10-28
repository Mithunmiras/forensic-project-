import { useEffect, useState } from "react";
import { api, LibraryDoc, Meta } from "../api";

export default function Library({ meta }: { meta: Meta }) {
  const [docs, setDocs] = useState<LibraryDoc[] | null>(null);
  const [product, setProduct] = useState("");
  const [role, setRole] = useState("");
  const [open, setOpen] = useState<{ path: string; title: string; text: string } | null>(null);

  useEffect(() => {
    api.documents().then((r) => setDocs(r.documents));
  }, []);

  if (!docs) return <div className="empty"><span className="spinner" /> Loading documents…</div>;
  const shown = docs
    .filter((d) => (!product || d.product_id === product) && (!role || d.role === role))
    .sort((a, b) => (a.date < b.date ? 1 : -1));

  return (
    <div className="stack">
      <div>
        <h1>Evidence library</h1>
        <p className="lede">
          The unstructured corpus the RAG agent searches: {docs.length} documents. Incident documents were generated from
          the same scenarios as the sales anomalies. Routine reports and standing policies are there as distractors, so
          the agent has to tell them apart. The role and cause shown here come from the RAG agent's own classifier, not
          from the generator.
        </p>
      </div>
      <div className="row">
        <select value={product} onChange={(e) => setProduct(e.target.value)} style={{ width: 200 }}>
          <option value="">All products</option>
          {meta.products.map((p) => <option key={p.product_id} value={p.product_id}>{p.product_name}</option>)}
        </select>
        <select value={role} onChange={(e) => setRole(e.target.value)} style={{ width: 200 }}>
          <option value="">All roles</option>
          <option value="incident">Incident</option>
          <option value="routine">Routine</option>
          <option value="reference">Reference (policy)</option>
        </select>
        <span className="muted small">{shown.length} shown</span>
      </div>
      <div className="grid-2" style={{ alignItems: "start" }}>
        <div className="card table-wrap" style={{ padding: 0 }}>
          <table>
            <thead>
              <tr><th>Date</th><th>Document</th><th>Region</th><th>Role</th></tr>
            </thead>
            <tbody>
              {shown.map((d) => (
                <tr key={d.path} className="clickable" onClick={() => api.document(d.path).then(setOpen)}
                  style={open?.path === d.path ? { background: "var(--surface-2)" } : undefined}>
                  <td className="muted" style={{ whiteSpace: "nowrap" }}>{d.date}</td>
                  <td>
                    <b>{d.title}</b>
                    <div className="small muted">{d.path}</div>
                  </td>
                  <td>{d.region}</td>
                  <td>
                    <span className={`badge ${d.role === "incident" ? "info" : ""}`}>
                      {d.role === "incident" ? meta.causes[d.cause ?? ""] ?? d.cause : d.role}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card" style={{ position: "sticky", top: 76 }}>
          {open ? (
            <>
              <h2>{open.title}</h2>
              <pre className="doctext">{open.text}</pre>
            </>
          ) : (
            <div className="empty">Select a document to read it.</div>
          )}
        </div>
      </div>
    </div>
  );
}
