import type {
  AskResponse,
  ChatResponse,
  Dashboard,
  FilterOptions,
  Filters,
  InputSchema,
  ModelMetadata,
  PredictionRequest,
  PredictionResponse,
  QueryResponse,
  SystemStatus,
} from "./types";

/** Base URL comes from VITE_API_BASE_URL; empty means "same origin" (dev proxy / FastAPI serving the build). */
export const API_BASE: string = ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "").replace(/\/$/, "");
const DEFAULT_TIMEOUT_MS = 20_000;

export class ApiError extends Error {
  status: number;
  code: string;
  hint?: string;
  fields?: Record<string, string>;

  constructor(status: number, code: string, message: string, hint?: string, fields?: Record<string, string>) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.hint = hint;
    this.fields = fields;
  }

  /** True when a backing service (database, model) is missing - the UI shows setup help instead of an error. */
  get isSetupProblem(): boolean {
    return ["database_not_configured", "database_unavailable", "model_not_ready"].includes(this.code);
  }

  get isNetwork(): boolean {
    return this.code === "network" || this.code === "timeout";
  }
}

interface RequestOptions {
  method?: "GET" | "POST";
  body?: unknown;
  headers?: Record<string, string>;
  timeoutMs?: number;
  signal?: AbortSignal;
}

export async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort("timeout"), opts.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  opts.signal?.addEventListener("abort", () => controller.abort(opts.signal?.reason));

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: opts.method ?? "GET",
      headers: { Accept: "application/json", ...(opts.body !== undefined ? { "Content-Type": "application/json" } : {}), ...opts.headers },
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      signal: controller.signal,
    });
  } catch (err) {
    if (controller.signal.reason === "timeout") {
      throw new ApiError(0, "timeout", "The request timed out. The server may be busy or unreachable.");
    }
    if (opts.signal?.aborted) throw err;
    throw new ApiError(0, "network", `Cannot reach the RetailIQ API${API_BASE ? ` at ${API_BASE}` : ""}. Is the backend running?`);
  } finally {
    clearTimeout(timeout);
  }

  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    /* non-JSON body */
  }
  if (!response.ok) {
    const e = (payload as { error?: { code?: string; message?: string; hint?: string; fields?: Record<string, string> } } | null)?.error;
    throw new ApiError(response.status, e?.code ?? `http_${response.status}`, e?.message ?? `Request failed (${response.status}).`, e?.hint, e?.fields);
  }
  return payload as T;
}

function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") sp.set(k, String(v));
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export const api = {
  status: (signal?: AbortSignal) => request<SystemStatus>("/api/v1/system/status", { signal, timeoutMs: 12_000 }),
  filters: () => request<FilterOptions>("/api/v1/analytics/filters"),
  dashboard: (f: Filters, grain: string, signal?: AbortSignal) =>
    request<Dashboard>(`/api/v1/analytics/dashboard${qs({ ...f, grain })}`, { signal }),
  query: (question: string) => request<QueryResponse>("/api/v1/analytics/query", { method: "POST", body: { question }, timeoutMs: 120_000 }),
  mlSchema: () => request<InputSchema>("/api/v1/ml/schema"),
  mlMetadata: () => request<ModelMetadata>("/api/v1/ml/metadata"),
  predict: (body: PredictionRequest) => request<PredictionResponse>("/api/v1/ml/predict", { method: "POST", body }),
  ask: (question: string) => request<AskResponse>("/api/v1/rag/ask", { method: "POST", body: { question }, timeoutMs: 120_000 }),
  chat: (message: string) => request<ChatResponse>("/api/v1/agent/chat", { method: "POST", body: { message }, timeoutMs: 180_000 }),
  reindex: (token: string, force: boolean) =>
    request<Record<string, unknown>>("/api/v1/rag/index", { method: "POST", body: { force }, headers: { "X-Admin-Token": token }, timeoutMs: 180_000 }),
  retrain: (token: string) =>
    request<Record<string, unknown>>("/api/v1/ml/retrain", { method: "POST", body: { source: "csv" }, headers: { "X-Admin-Token": token }, timeoutMs: 300_000 }),
};
