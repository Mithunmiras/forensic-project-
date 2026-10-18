// Types mirror the FastAPI response models (src/api/schemas.py and the route handlers).

export interface Filters {
  date_from?: string;
  date_to?: string;
  category?: string;
  region?: string;
  market?: string;
}

export interface FilterOptions {
  categories: string[];
  sub_categories: string[];
  regions: string[];
  markets: string[];
  segments: string[];
  ship_modes: string[];
  countries: string[];
  date_range: [string, string];
}

export interface Kpis {
  total_sales: number;
  total_profit: number;
  orders: number;
  order_lines: number;
  units: number;
  customers: number;
  avg_discount: number; // fraction
  avg_order_value: number;
  profit_margin: number; // fraction
  first_date: string | null;
  last_date: string | null;
}

export interface TrendPoint {
  period: string;
  sales: number;
  profit: number;
  orders: number;
}

export interface DimRow {
  name: string;
  sales: number;
  profit: number;
  orders: number;
  units?: number;
  avg_discount_pct?: number;
  margin_pct: number | null;
}

export interface ProductRow {
  name: string;
  category: string;
  sub_category: string;
  sales: number;
  profit: number;
  units: number;
}

export interface CustomerRow {
  name: string;
  segment: string;
  sales: number;
  profit: number;
  orders: number;
}

export interface DiscountBand {
  band: string;
  sales: number;
  profit: number;
  order_lines: number;
  margin_pct: number | null;
}

export interface ShippingRow {
  ship_mode: string;
  orders: number;
  avg_days: number;
  avg_cost: number;
}

export interface Dashboard {
  filters: Filters;
  kpis: Kpis;
  previous: { period: [string, string]; kpis: Kpis } | null;
  change_pct: Record<"total_sales" | "total_profit" | "orders" | "avg_order_value", number | null> | null;
  trend: TrendPoint[];
  by_category: DimRow[];
  by_region: DimRow[];
  by_market: DimRow[];
  by_sub_category: DimRow[];
  top_products: ProductRow[];
  top_customers: CustomerRow[];
  discount_impact: DiscountBand[];
  shipping: ShippingRow[];
}

// ---- SQL agent --------------------------------------------------------------
export interface QueryResponse {
  question: string;
  status: "ok" | "unsupported" | "error" | "unavailable";
  method: "template" | "llm" | null;
  sql: string | null;
  params: Record<string, unknown>;
  explanation: string | null;
  columns: { name: string; type: string }[];
  rows: unknown[][];
  row_count: number;
  truncated: boolean;
  elapsed_ms: number | null;
  chart: { type: "bar" | "line"; x: string; y: string } | null;
  notes: string[];
  error: string | null;
  supported_examples: string[];
}

// ---- ML ---------------------------------------------------------------------
export interface InputField {
  name: string;
  kind: "categorical" | "integer" | "number" | "date";
  required: boolean;
  label: string;
  default?: string;
  options?: string[];
  options_by_category?: Record<string, string[]>;
  training_range?: [number | string, number | string];
  default_by_ship_mode?: Record<string, number>;
}

export interface InputSchema {
  fields: InputField[];
  variant_rule: string;
}

export interface Metrics {
  mae: number;
  rmse: number;
  r2: number;
  median_abs_error: number;
}

export interface Candidate {
  name: string;
  is_baseline: boolean;
  selected: boolean;
  cv_r2_mean: number;
  cv_r2_std: number;
  test_r2: number;
  test_mae: number;
  test_rmse: number;
}

export interface VariantMeta {
  label: string;
  features: string[];
  best_model: string;
  candidates: Candidate[];
  test_metrics: Metrics;
  baseline_test_metrics: Metrics;
  interval: { method: string; nominal_coverage: number; empirical_test_coverage: number };
  feature_importance: { feature: string; importance: number }[];
  scatter: { actual: number; predicted: number }[];
  split: { train_rows: number; test_rows: number };
}

export interface ModelMetadata {
  trained_at: string;
  sklearn_version: string;
  target: { name: string; definition: string };
  dataset: { rows: number; source: string; order_date_range: [string, string] };
  split: { strategy: string; test_size: number; random_state: number; cv_folds: number };
  default_variant: string;
  variants: Record<string, VariantMeta>;
  limitations: string[];
}

export interface PredictionRequest {
  category: string;
  sub_category: string;
  market: string;
  quantity: number;
  discount: number;
  segment?: string;
  ship_mode?: string;
  order_priority?: string;
  shipping_days?: number;
  shipping_cost?: number;
  order_date?: string;
}

export interface PredictionResponse {
  predicted_sales: number;
  lower_bound: number;
  upper_bound: number;
  interval_nominal_coverage: number;
  interval_empirical_coverage: number;
  variant: string;
  model: string;
  test_metrics: Partial<Metrics>;
  typical_sub_category_sales: number;
  inputs_used: Record<string, unknown>;
  assumptions: string[];
  warnings: string[];
  disclaimer: string;
}

// ---- RAG / agent ------------------------------------------------------------
export interface Source {
  id: number;
  source: string;
  heading: string;
  score: number;
  confidence: "high" | "medium" | "low";
  snippet: string;
}

export interface AskResponse {
  question: string;
  answer: string;
  answer_mode: "llm" | "extractive" | "none";
  retrieval_mode: "semantic" | "lexical_fallback" | "none";
  sources: Source[];
  warnings: string[];
}

export interface ToolStatus {
  name: "sql" | "ml" | "rag";
  status: "ok" | "no_results" | "error" | "unavailable" | "needs_input" | "skipped";
  message: string | null;
  duration_ms: number;
}

export interface ChatResponse {
  answer: string;
  answer_mode: "llm" | "deterministic";
  route: { tools: string[]; method: "rules" | "llm"; reason: string };
  tools: ToolStatus[];
  evidence: { sql: QueryResponse | null; prediction: PredictionResponse | null; sources: Source[] | null };
  warnings: string[];
  elapsed_ms: number;
}

// ---- system -----------------------------------------------------------------
export interface SystemStatus {
  overall: "ready" | "degraded" | "setup_required";
  backend: { available: boolean; version: string; environment: string; time: string };
  database: {
    configured: boolean;
    connected: boolean;
    schema_ready: boolean;
    readonly_role: boolean;
    server_version: string | null;
    fact_rows: number | null;
    last_etl_run: {
      run_id: number;
      status: string;
      finished_at: string | null;
      raw_rows: number;
      valid_rows: number;
      rejected_rows: number;
      inserted_rows: number;
      skipped_rows: number;
    } | null;
    url: string | null;
    error: string | null;
  };
  model: {
    ready: boolean;
    trained_at?: string;
    variants?: Record<string, string>;
    default_variant?: string;
    error: string | null;
    hint?: string;
  };
  vector_store: {
    state: "ready" | "degraded" | "not_indexed";
    documents: number;
    chunks: number;
    retrieval_mode: string;
    embedder: string | null;
    embedder_status: string;
    indexed_at: string | null;
    stale: boolean;
    llm_answers: boolean;
    hint: string | null;
    sources: string[];
  };
  llm: {
    provider: string;
    available: boolean;
    reachable: boolean;
    model: string | null;
    model_present: boolean;
    error: string | null;
    hint: string | null;
  };
  datasets: Record<string, { path: string; exists: boolean }>;
  setup_steps: { component: string; required: "yes" | "no"; action: string }[];
}
