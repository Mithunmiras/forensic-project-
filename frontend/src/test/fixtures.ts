import type { Dashboard, InputSchema, ModelMetadata, PredictionResponse, SystemStatus } from "../lib/types";

export const kpis = {
  total_sales: 12642905, total_profit: 1467457.29, orders: 25035, order_lines: 51290, units: 178312, customers: 4873,
  avg_discount: 0.1429, avg_order_value: 505.01, profit_margin: 0.1161, first_date: "2011-01-01", last_date: "2014-12-31",
};

export const dashboard: Dashboard = {
  filters: {},
  kpis,
  previous: null,
  change_pct: { total_sales: 20.3, total_profit: -4.2, orders: 35.8, avg_order_value: null },
  trend: [{ period: "2011-01", sales: 98902, profit: 8321.8, orders: 100 }, { period: "2011-02", sales: 91000, profit: 7000, orders: 90 }],
  by_category: [
    { name: "Technology", sales: 4744691, profit: 663778.73, orders: 9000, margin_pct: 13.99 },
    { name: "Furniture", sales: 4110884, profit: 285204.72, orders: 8000, margin_pct: 6.94 },
  ],
  by_region: [{ name: "Central", sales: 2822399, profit: 311403.98, orders: 5000, margin_pct: 11.03 }],
  by_market: [{ name: "APAC", sales: 3585833, profit: 436000, orders: 6000, margin_pct: 12.16 }],
  by_sub_category: [{ name: "Copiers", sales: 1509439, profit: 258567.55, orders: 500, margin_pct: 17.1 }, { name: "Tables", sales: 757000, profit: -64083, orders: 400, margin_pct: -8.5 }],
  top_products: [{ name: "Apple Smart Phone, Full Size", category: "Technology", sub_category: "Phones", sales: 86936, profit: 5921.58, units: 300 }],
  top_customers: [{ name: "Tom Ashbrook", segment: "Corporate", sales: 40488, profit: 6000, orders: 20 }],
  discount_impact: [{ band: "0 none", sales: 1, profit: 1, order_lines: 29009, margin_pct: 25.3 }, { band: "5 over 50%", sales: 1, profit: -1, order_lines: 4172, margin_pct: -111 }],
  shipping: [{ ship_mode: "Same Day", orders: 1347, avg_days: 0.04, avg_cost: 42.94 }],
};

export const schema: InputSchema = {
  variant_rule: "shipping_cost provided -> with_shipping_cost model, otherwise the leakage-safe model.",
  fields: [
    { name: "category", kind: "categorical", required: true, label: "Category", options: ["Furniture", "Office Supplies", "Technology"] },
    { name: "sub_category", kind: "categorical", required: true, label: "Sub-category", options_by_category: { Technology: ["Phones", "Copiers"], Furniture: ["Chairs", "Tables"], "Office Supplies": ["Binders"] } },
    { name: "market", kind: "categorical", required: true, label: "Market", options: ["US", "EU"] },
    { name: "quantity", kind: "integer", required: true, label: "Quantity", training_range: [1, 14] },
    { name: "discount", kind: "number", required: true, label: "Discount (0-1)", training_range: [0, 0.85] },
    { name: "shipping_cost", kind: "number", required: false, label: "Shipping cost" },
    { name: "order_date", kind: "date", required: false, label: "Order date", default: "2014-12-31" },
  ],
};

const variant = (label: string, r2: number) => ({
  label,
  features: ["category", "quantity"],
  best_model: "Gradient Boosting",
  candidates: [
    { name: "Baseline (mean)", is_baseline: true, selected: false, cv_r2_mean: 0, cv_r2_std: 0, test_r2: 0, test_mae: 262.6, test_rmse: 522.3 },
    { name: "Gradient Boosting", is_baseline: false, selected: true, cv_r2_mean: 0.48, cv_r2_std: 0.02, test_r2: r2, test_mae: 151.2, test_rmse: 399.6 },
  ],
  test_metrics: { mae: 151.2, rmse: 399.6, r2, median_abs_error: 60 },
  baseline_test_metrics: { mae: 262.6, rmse: 522.3, r2: 0, median_abs_error: 150 },
  interval: { method: "quantile", nominal_coverage: 0.8, empirical_test_coverage: 0.79 },
  feature_importance: [{ feature: "quantity", importance: 0.2 }, { feature: "category", importance: 0.1 }],
  scatter: [],
  split: { train_rows: 41032, test_rows: 10258 },
});

export const metadata: ModelMetadata = {
  trained_at: "2026-10-13T16:50:25+00:00",
  sklearn_version: "1.9.1",
  target: { name: "sales", definition: "Sales value of a single order line." },
  dataset: { rows: 51290, source: "csv", order_date_range: ["2011-01-01", "2014-12-31"] },
  split: { strategy: "random", test_size: 0.2, random_state: 42, cv_folds: 5 },
  default_variant: "without_shipping_cost",
  variants: { without_shipping_cost: variant("Without shipping cost (leakage-safe)", 0.415), with_shipping_cost: variant("With shipping cost", 0.652) },
  limitations: ["Predictions are statistical estimates, not guarantees.", "Only 2011-2014 data was used."],
};

export const prediction: PredictionResponse = {
  predicted_sales: 356.64, lower_bound: 66.59, upper_bound: 697.63, interval_nominal_coverage: 0.8, interval_empirical_coverage: 0.79,
  variant: "without_shipping_cost", model: "Gradient Boosting", test_metrics: { r2: 0.415 }, typical_sub_category_sales: 120,
  inputs_used: { sub_category: "Phones" }, assumptions: ["segment not provided; assumed 'Consumer'."], warnings: [], disclaimer: "Estimate for a single order line.",
};

export const status: SystemStatus = {
  overall: "ready",
  backend: { available: true, version: "3.0.0", environment: "development", time: "2026-10-13T12:00:00+00:00" },
  database: { configured: true, connected: true, schema_ready: true, readonly_role: true, server_version: "16.2", fact_rows: 51290,
    last_etl_run: { run_id: 1, status: "succeeded", finished_at: "2026-10-13T12:00:00+00:00", raw_rows: 51290, valid_rows: 51290, rejected_rows: 0, inserted_rows: 51290, skipped_rows: 0 },
    url: "postgresql+psycopg://retailiq_readonly:***@127.0.0.1:54329/retailiq_db", error: null },
  model: { ready: true, trained_at: "2026-10-13T16:50:25+00:00", variants: { with_shipping_cost: "Gradient Boosting" }, default_variant: "without_shipping_cost", error: null },
  vector_store: { state: "ready", documents: 12, chunks: 101, retrieval_mode: "semantic", embedder: "chroma-onnx-all-MiniLM-L6-v2", embedder_status: "ok", indexed_at: "2026-10-13T12:00:00+00:00", stale: false, llm_answers: false, hint: null, sources: [] },
  llm: { provider: "ollama", available: false, reachable: false, model: "llama3.2", model_present: false, error: "Ollama not reachable.", hint: "Run: ollama pull llama3.2" },
  datasets: { raw_csv: { path: "data/raw/superstore.csv", exists: true } },
  setup_steps: [{ component: "llm", required: "no", action: "Install Ollama, then run: ollama pull llama3.2" }],
};

/** Install a fetch mock that routes by URL path. Unmatched paths fail loudly. */
export function mockFetch(routes: Record<string, unknown | ((init?: RequestInit) => unknown)>) {
  const calls: { url: string; init?: RequestInit }[] = [];
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, init });
    const path = url.split("?")[0];
    const entry = routes[path];
    if (entry === undefined) throw new Error(`Unmocked request: ${url}`);
    const value = typeof entry === "function" ? (entry as (i?: RequestInit) => unknown)(init) : entry;
    if (value instanceof Response) return value;
    return new Response(JSON.stringify(value), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fn);
  return { fn, calls };
}

export const errorResponse = (status: number, code: string, message: string, hint?: string, fields?: Record<string, string>) =>
  new Response(JSON.stringify({ error: { code, message, hint, fields } }), { status, headers: { "Content-Type": "application/json" } });
