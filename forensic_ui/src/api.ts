export type Case = "full" | "structured_only" | "unstructured_only" | "conflict" | "none" | "no_data";

export interface Citation {
  id: number;
  kind: "table" | "document" | "model" | "store";
  label: string;
  detail: string;
  path: string | null;
}

export interface DocResult {
  path: string;
  filename: string;
  title: string;
  doc_type: string;
  date: string;
  region: string;
  author: string;
  score: number;
  similarity: number;
  metadata_score: number;
  role: "incident" | "routine" | "reference";
  cause: string | null;
  cause_label: string | null;
  matched_terms: string[];
  chunk: string;
  quote: string;
}

export interface Forecast {
  method: string;
  trained_through: string;
  next_month: string;
  baseline_per_day: number;
  predicted_per_day: number;
  predicted_pct_vs_baseline: number;
  if_cause_persists_per_day: number;
  if_cause_persists_pct: number;
  actual_per_day: number | null;
  actual_pct_vs_baseline: number | null;
  series: { date: string; forecast: number }[];
}

export interface Investigation {
  question: string;
  total_ms: number;
  plan: {
    product_id: string | null;
    product_name: string | null;
    region: string | null;
    month: string | null;
    intent: string;
    direction: string | null;
    resolution: Record<string, string>;
    notes: string[];
  };
  answer: {
    headline: string;
    case: Case;
    cause: { key: string; label: string; status: string };
    evidence_status: {
      structured_available: boolean;
      structured_anomaly: boolean;
      unstructured_available: boolean;
      unstructured_match: boolean;
    };
    layers: { descriptive: string; diagnostic: string; predictive: string; prescriptive: string };
    actions: string[];
    confidence: { score: number; label: string; reasons: string[]; missing_source: string | null };
    citations: Citation[];
  };
  agents: {
    sql: {
      available: boolean;
      reason: string;
      month?: string;
      queries: { purpose: string; sql: string; params?: unknown[] }[];
      target?: Record<string, number | boolean | string[]>;
      monthly?: { month: string; units_per_day: number; baseline: number; stockout_days: number; is_anomaly: boolean }[];
      other_regions?: { region: string; units_per_day_pct: number; is_anomaly: boolean }[];
      stockout?: { warehouse: string; days: number; first: string | null; last: string | null };
      daily?: { date: string; units: number; returns: number; discount: number; stock: number; reorder_point: number }[];
    };
    rag: {
      available: boolean;
      reason: string;
      index: { method: string; chunks: number; documents: number };
      window?: { from: string; to: string };
      results: DocResult[];
      excluded: { path: string; title: string; similarity: number; reason: string }[];
      corpus_for_product: number;
    };
    rca: {
      available: boolean;
      reason: string;
      is_anomaly?: boolean;
      anomaly_score?: number;
      signature?: string[];
      hypothesis?: { key: string; label: string } | null;
      compatible_causes?: string[];
      scope?: string;
      checks?: { key: string; fired: boolean; detail: string }[];
      forecast?: Forecast | null;
    };
  };
  trace: { agent: string; ms: number; summary: string; parallel?: boolean }[];
}

export interface Meta {
  products: { product_id: string; product_name: string; category: string; has_sales: boolean; has_documents: boolean }[];
  regions: string[];
  months: string[];
  causes: Record<string, string>;
  examples: { id: string; question: string; case: string }[];
  stats: { sales_rows: number; documents: number; incident_documents: number; scenarios: number; controls: number };
}

export interface ScanCell {
  product_id: string;
  region: string;
  month: string;
  units_per_day: number;
  units_pct: number;
  returns_pct: number;
  stockout_days: number;
  anomaly_score: number;
  is_anomaly: boolean;
  signals: string[];
}

export interface LibraryDoc {
  path: string;
  filename: string;
  product_id: string;
  doc_type: string;
  date: string;
  region: string;
  title: string;
  author: string;
  role: string;
  cause: string | null;
  matched_terms: string[];
}

export interface EvalRow {
  id: string;
  question: string;
  target: string;
  resolved: string;
  expected_cause: string;
  predicted_cause: string;
  expected_case: string;
  predicted_case: string;
  expected_confidence: string;
  predicted_confidence: string;
  confidence_score: number;
  expected_document: string | null;
  cause_ok: boolean;
  case_ok: boolean;
  confidence_ok: boolean;
  citation_ok: boolean;
  plan_ok: boolean;
  all_ok: boolean;
  headline: string;
}

export interface Evaluation {
  summary: Record<string, { correct: number; total: number }>;
  rows: EvalRow[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  meta: () => request<Meta>("/api/meta"),
  scan: () => request<{ cells: ScanCell[] }>("/api/scan"),
  documents: () => request<{ documents: LibraryDoc[] }>("/api/documents"),
  document: (path: string) => request<{ path: string; title: string; text: string }>(`/api/documents/${path}`),
  evaluation: (refresh = false) => request<Evaluation>(`/api/evaluation${refresh ? "?refresh=true" : ""}`),
  investigate: (body: { question: string; product_id?: string; region?: string; month?: string }) =>
    request<Investigation>("/api/investigate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
};

export function monthLabel(m: string | null | undefined): string {
  if (!m || m.startsWith("?")) return m ?? "";
  const d = new Date(`${m}-01T00:00:00`);
  return d.toLocaleString("en-US", { month: "short", year: "numeric" });
}

export const CASE_INFO: Record<Case, { label: string; tone: string; text: string }> = {
  full: { label: "Data + documents", tone: "good", text: "Structured anomaly confirmed by a matching document" },
  structured_only: { label: "Data only", tone: "warn", text: "Anomaly in the numbers, no explaining document" },
  unstructured_only: { label: "Documents only", tone: "info", text: "Document reports an issue, numbers do not show it" },
  conflict: { label: "Conflicting evidence", tone: "bad", text: "Document and data point to different causes" },
  none: { label: "Nothing unusual", tone: "neutral", text: "No anomaly and no incident document" },
  no_data: { label: "No data", tone: "bad", text: "Neither source is available" },
};
