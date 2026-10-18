import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { SourceList } from "../components/Evidence";
import { RichText } from "../components/RichText";
import { Badge, Card, EmptyState, ErrorState, PageHeader, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { fmtDateTime } from "../lib/format";
import type { AskResponse } from "../lib/types";
import { useSystemStatus } from "../hooks";

const EXAMPLES = [
  "How does the ETL avoid duplicate rows?",
  "What does target leakage mean for the prediction model?",
  "How is profit margin calculated?",
  "How does the SQL agent keep queries safe?",
  "What were the sales in each year?",
  "How does the router decide which tool to use?",
];

function ModeBadges({ a }: { a: AskResponse }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      {a.answer_mode === "llm" && <Badge tone="indigo" title="Written by the local LLM from the retrieved passages only">LLM answer</Badge>}
      {a.answer_mode === "extractive" && <Badge tone="amber" title="No LLM available: these are the most relevant passages, not a generated answer">Retrieval-only (no LLM)</Badge>}
      {a.answer_mode === "none" && <Badge>No answer</Badge>}
      {a.retrieval_mode === "semantic" && <Badge tone="teal" title="Passages found by meaning (embeddings) plus keyword boost">Semantic search</Badge>}
      {a.retrieval_mode === "lexical_fallback" && <Badge tone="red" title="Embeddings unavailable: matching on words only">Keyword fallback</Badge>}
    </div>
  );
}

export default function Knowledge() {
  const [question, setQuestion] = useState("");
  const [asked, setAsked] = useState<string | null>(null);
  const status = useSystemStatus(30_000);
  const kb = status.data?.vector_store;
  const ask = useMutation({ mutationFn: (q: string) => api.ask(q) });

  function submit(q: string) {
    const text = q.trim();
    if (text.length < 3 || ask.isPending) return;
    setAsked(text);
    ask.mutate(text);
  }

  const a = ask.data;
  return (
    <>
      <PageHeader title="Knowledge assistant" subtitle="Ask about the project, the data and the model. Answers come only from the project's own documentation, with sources." />
      <div className="grid gap-6 xl:grid-cols-[1fr_20rem]">
        <div className="space-y-6">
          <Card>
            <form onSubmit={(e) => { e.preventDefault(); submit(question); }} className="flex flex-col gap-2 sm:flex-row">
              <label htmlFor="kb-q" className="sr-only">Question</label>
              <input id="kb-q" className="input" value={question} maxLength={500} placeholder="e.g. How does the ETL avoid duplicate rows?" onChange={(e) => setQuestion(e.target.value)} />
              <button type="submit" className="btn-primary shrink-0" disabled={question.trim().length < 3 || ask.isPending}>Ask</button>
            </form>
            <div className="mt-3 flex flex-wrap gap-2">
              {EXAMPLES.map((e) => (
                <button key={e} type="button" className="rounded-full border border-slate-300 px-3 py-1 text-xs text-slate-600 hover:border-brand-500 hover:bg-brand-50" onClick={() => { setQuestion(e); submit(e); }}>
                  {e}
                </button>
              ))}
            </div>
          </Card>

          {ask.isPending && <Card><Spinner label="Searching the documentation..." /></Card>}
          {ask.isError && <ErrorState error={ask.error} onRetry={() => asked && ask.mutate(asked)} />}

          {a && (
            <div className="space-y-6" aria-live="polite">
              <Card title={asked ?? "Answer"} actions={<ModeBadges a={a} />}>
                {a.answer_mode === "none" ? (
                  <EmptyState title="No supporting documents found">{a.answer} Try rephrasing, or ask about the ETL, the model, the SQL agent, definitions or the verified findings.</EmptyState>
                ) : (
                  <RichText text={a.answer} />
                )}
                {a.warnings.length > 0 && (
                  <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-amber-700">{a.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
                )}
              </Card>
              {a.sources.length > 0 && <Card title={`Sources (${a.sources.length})`} hint="Passages the answer is based on, best match first"><SourceList sources={a.sources} /></Card>}
            </div>
          )}
        </div>

        <aside aria-label="Knowledge base status">
          <Card title="Knowledge base">
            {!kb && status.isLoading && <Spinner />}
            {status.isError && <p className="text-sm text-rose-600">Status unavailable (API offline).</p>}
            {kb && (
              <dl className="space-y-2 text-sm">
                <div className="flex justify-between"><dt className="text-slate-500">State</dt><dd><Badge tone={kb.state === "ready" ? "green" : kb.state === "degraded" ? "amber" : "red"}>{kb.state.replace(/_/g, " ")}</Badge></dd></div>
                <div className="flex justify-between"><dt className="text-slate-500">Documents</dt><dd className="font-semibold">{kb.documents}</dd></div>
                <div className="flex justify-between"><dt className="text-slate-500">Passages</dt><dd className="font-semibold">{kb.chunks}</dd></div>
                <div className="flex justify-between"><dt className="text-slate-500">Retrieval</dt><dd className="font-semibold">{kb.retrieval_mode.replace(/_/g, " ")}</dd></div>
                <div className="flex justify-between"><dt className="text-slate-500">Answers by</dt><dd className="font-semibold">{kb.llm_answers ? "LLM" : "passages only"}</dd></div>
                <div className="flex justify-between"><dt className="text-slate-500">Indexed</dt><dd className="text-right text-xs">{fmtDateTime(kb.indexed_at)}</dd></div>
                {kb.hint && <p className="rounded bg-amber-50 p-2 text-xs text-amber-800">{kb.hint}</p>}
              </dl>
            )}
          </Card>
        </aside>
      </div>
    </>
  );
}
