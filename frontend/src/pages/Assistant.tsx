import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { PredictionSummary, SourceList, SqlEvidence } from "../components/Evidence";
import { RichText } from "../components/RichText";
import { Badge, Card, ErrorState, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import type { ChatResponse, ToolStatus } from "../lib/types";

const EXAMPLES = [
  "Which product categories generate the most sales?",
  "What are the top 10 products by sales?",
  "What is the monthly sales trend?",
  "Which sub-categories have the highest profit?",
  "What is the average discount by category?",
  "Which shipping modes have the longest shipping duration?",
  "Which region performs best, and what factors might explain it?",
  "Predict sales for 3 units of Phones in the US with a 10% discount",
  "Explain how the sales prediction model works",
];

type Turn = { id: number; question: string; response?: ChatResponse; error?: unknown };

const TOOL_LABEL: Record<string, string> = { sql: "SQL analytics", ml: "ML prediction", rag: "Knowledge base" };

function statusTone(s: ToolStatus["status"]) {
  return s === "ok" ? "green" : s === "needs_input" || s === "no_results" || s === "skipped" ? "amber" : "red";
}

function Answer({ r }: { r: ChatResponse }) {
  const { sql, prediction, sources } = r.evidence;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={r.answer_mode === "llm" ? "indigo" : "slate"} title={r.answer_mode === "llm" ? "Written by the local LLM from the evidence" : "Composed from the tool results without an LLM"}>
          {r.answer_mode === "llm" ? "LLM-written answer" : "Built-in answer (no LLM)"}
        </Badge>
        <span className="text-xs text-slate-500">routed by {r.route.method}</span>
        {r.tools.map((t) => (
          <Badge key={t.name} tone={statusTone(t.status)} title={t.message ?? undefined}>
            {TOOL_LABEL[t.name] ?? t.name}: {t.status.replace(/_/g, " ")}
          </Badge>
        ))}
        <span className="text-xs text-slate-400">{(r.elapsed_ms / 1000).toFixed(1)}s</span>
      </div>
      <RichText text={r.answer} />
      <p className="text-xs text-slate-500">Why these tools: {r.route.reason}</p>

      {sql && (
        <details open className="rounded-lg border border-slate-200 p-3">
          <summary className="cursor-pointer text-sm font-semibold text-slate-800">Measured results (database)</summary>
          <div className="mt-3"><SqlEvidence result={sql} /></div>
        </details>
      )}
      {prediction && (
        <details open className="rounded-lg border border-slate-200 p-3">
          <summary className="cursor-pointer text-sm font-semibold text-slate-800">Model estimate</summary>
          <div className="mt-3"><PredictionSummary p={prediction} /></div>
        </details>
      )}
      {sources && sources.length > 0 && (
        <details open className="rounded-lg border border-slate-200 p-3">
          <summary className="cursor-pointer text-sm font-semibold text-slate-800">Documentation sources ({sources.length})</summary>
          <div className="mt-3"><SourceList sources={sources} /></div>
        </details>
      )}
      {r.warnings.length > 0 && (
        <ul className="list-disc space-y-1 pl-5 text-xs text-amber-700">
          {r.warnings.map((w) => <li key={w}>{w}</li>)}
        </ul>
      )}
    </div>
  );
}

export default function Assistant() {
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const bottom = useRef<HTMLDivElement>(null);
  const nextId = useRef(1);

  const send = useMutation({
    mutationFn: (q: string) => api.chat(q),
  });

  useEffect(() => {
    bottom.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [turns, send.isPending]);

  function ask(question: string) {
    const q = question.trim();
    if (!q || send.isPending) return;
    const id = nextId.current++;
    setTurns((t) => [...t, { id, question: q }]);
    setInput("");
    send.mutate(q, {
      onSuccess: (response) => setTurns((t) => t.map((x) => (x.id === id ? { ...x, response } : x))),
      onError: (error) => setTurns((t) => t.map((x) => (x.id === id ? { ...x, error } : x))),
    });
  }

  return (
    <>
      <PageHeader title="AI Analytics" subtitle="Ask in plain English. The assistant picks SQL analytics, the prediction model and/or the documentation, and shows its evidence." />
      <div className="grid gap-6 xl:grid-cols-[1fr_20rem]">
        <div className="space-y-4">
          {turns.length === 0 && (
            <Card>
              <p className="text-sm text-slate-600">
                Every number comes from the PostgreSQL database or the trained model - never from the language model's memory. Try one of the examples, or type your own question below.
              </p>
            </Card>
          )}
          {turns.map((t) => (
            <div key={t.id} className="space-y-3">
              <div className="ml-auto max-w-2xl rounded-2xl rounded-tr-sm bg-brand-600 px-4 py-2.5 text-sm text-white">{t.question}</div>
              <div className="card p-5">
                {t.response && <Answer r={t.response} />}
                {t.error !== undefined && <ErrorState error={t.error} />}
                {!t.response && t.error === undefined && <Spinner label="Working on it - querying the database and tools..." />}
              </div>
            </div>
          ))}
          <div ref={bottom} />
          <form
            className="sticky bottom-4 flex gap-2 rounded-xl border border-slate-200 bg-white p-2 shadow-card"
            onSubmit={(e) => {
              e.preventDefault();
              ask(input);
            }}
          >
            <label htmlFor="chat-input" className="sr-only">Your question</label>
            <input id="chat-input" className="input border-0 shadow-none" placeholder="e.g. What is the total profit in 2013?" value={input} maxLength={1000} onChange={(e) => setInput(e.target.value)} autoComplete="off" />
            <button type="submit" className="btn-primary" disabled={!input.trim() || send.isPending}>
              {send.isPending ? "Thinking..." : "Ask"}
            </button>
          </form>
        </div>
        <aside aria-label="Example questions">
          <Card title="Try these">
            <ul className="space-y-2">
              {EXAMPLES.map((e) => (
                <li key={e}>
                  <button type="button" className="w-full rounded-lg border border-slate-200 px-3 py-2 text-left text-sm text-slate-700 hover:border-brand-500 hover:bg-brand-50 disabled:opacity-60" disabled={send.isPending} onClick={() => ask(e)}>
                    {e}
                  </button>
                </li>
              ))}
            </ul>
          </Card>
        </aside>
      </div>
    </>
  );
}
