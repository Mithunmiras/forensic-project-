import { useEffect, useState } from "react";
import { api, LibraryDoc, Meta } from "../api";
import Icon from "../components/Icon";
import { useMediaQuery } from "../hooks";

type Opened = { path: string; title: string; text: string };

export default function Library({ meta }: { meta: Meta }) {
  const wide = useMediaQuery("(min-width: 1001px)");
  const [docs, setDocs] = useState<LibraryDoc[] | null>(null);
  const [product, setProduct] = useState("");
  const [role, setRole] = useState("");
  const [open, setOpen] = useState<Opened | null>(null);

  useEffect(() => {
    api.documents().then((r) => setDocs(r.documents));
  }, []);

  useEffect(() => {
    if (wide || !open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(null);
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, wide]);

  if (!docs) return <div className="empty"><span className="spinner" /> Loading documents…</div>;
  const shown = docs
    .filter((d) => (!product || d.product_id === product) && (!role || d.role === role))
    .sort((a, b) => (a.date < b.date ? 1 : -1));
  const counts = { incident: 0, routine: 0, reference: 0 } as Record<string, number>;
  docs.forEach((d) => (counts[d.role] = (counts[d.role] ?? 0) + 1));

  const viewer = open && (
    <>
      <div className="row" style={{ alignItems: "flex-start", marginBottom: 10 }}>
        <h2 style={{ margin: 0, flex: 1 }}>{open.title}</h2>
        {!wide && (
          <button className="btn ghost" onClick={() => setOpen(null)} aria-label="Close"><Icon name="close" /></button>
        )}
      </div>
      <pre className="doctext">{open.text}</pre>
    </>
  );

  return (
    <div className="stack">
      <div className="page-head">
        <h1>Evidence library</h1>
        <p className="lede">
          The {docs.length} documents the RAG agent searches. Incident documents were generated from the same scenarios as
          the sales anomalies. Routine reports and policies are distractors the agent has to tell apart. Roles and causes
          come from the agent's own classifier, not from the generator.
        </p>
      </div>

      <div className="chips">
        {[["", `All · ${docs.length}`], ["incident", `Incident · ${counts.incident}`], ["routine", `Routine · ${counts.routine}`],
          ["reference", `Policy · ${counts.reference}`]].map(([key, label]) => (
          <button key={key} className={`chip ${role === key ? "on" : ""}`} onClick={() => setRole(key)}>{label}</button>
        ))}
      </div>
      <div className="row">
        <select value={product} onChange={(e) => setProduct(e.target.value)} style={{ maxWidth: 260 }} aria-label="Product">
          <option value="">All products</option>
          {meta.products.map((p) => <option key={p.product_id} value={p.product_id}>{p.product_name}</option>)}
        </select>
        <span className="muted small">{shown.length} shown</span>
      </div>

      {!wide && (
        <div className="card" style={{ padding: 0 }}>
          <ul className="doc-list">
            {shown.map((d) => (
              <li key={d.path}>
                <button onClick={() => api.document(d.path).then(setOpen)}>
                  <span className="t">{d.title}</span>
                  <span className={`badge ${d.role === "incident" ? "info" : ""}`}>
                    {d.role === "incident" ? meta.causes[d.cause ?? ""] ?? d.cause : d.role}
                  </span>
                  <span className="m">{d.date} · region {d.region} · {d.path}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {wide && <div className="grid-2" style={{ alignItems: "start" }}>
        <div className="card table-wrap" style={{ padding: 0 }}>
          <table>
            <thead>
              <tr><th>Document</th><th>Region</th><th>Role</th></tr>
            </thead>
            <tbody>
              {shown.map((d) => (
                <tr key={d.path} className={`clickable ${open?.path === d.path ? "selected" : ""}`}
                  onClick={() => api.document(d.path).then(setOpen)}>
                  <td>
                    <b>{d.title}</b>
                    <div className="small muted" style={{ overflowWrap: "anywhere" }}>{d.date} · {d.path}</div>
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
        <div className="card" style={{ position: "sticky", top: 80 }}>
          {viewer ?? <div className="empty">Select a document to read it.</div>}
        </div>
      </div>}

      {!wide && open && (
        <>
          <div className="drawer-backdrop" onClick={() => setOpen(null)} />
          <div className="drawer" role="dialog" aria-modal="true" aria-label={open.title}>
            <div className="grab" />
            {viewer}
          </div>
        </>
      )}
    </div>
  );
}
