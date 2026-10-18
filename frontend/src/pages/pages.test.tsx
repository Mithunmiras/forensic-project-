import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import Layout from "../components/Layout";
import { RichText } from "../components/RichText";
import { dashboard, errorResponse, metadata, mockFetch, prediction, schema, status } from "../test/fixtures";
import { renderPage } from "../test/render";
import About from "./About";
import Assistant from "./Assistant";
import Knowledge from "./Knowledge";
import Overview from "./Overview";
import Predict from "./Predict";
import Status from "./Status";

const FILTERS = { categories: ["Furniture", "Technology"], sub_categories: [], regions: ["Central"], markets: ["US"], segments: [], ship_modes: [], countries: [], date_range: ["2011-01-01", "2014-12-31"] };

describe("Overview", () => {
  it("shows real KPIs, deltas and chart sections from the API", async () => {
    mockFetch({ "/api/v1/analytics/filters": FILTERS, "/api/v1/analytics/dashboard": dashboard });
    renderPage(<Overview />);
    expect(await screen.findByText("Total sales")).toBeInTheDocument();
    expect(screen.getByText("$12.6M")).toBeInTheDocument();
    expect(screen.getByText("25,035")).toBeInTheDocument();
    expect(screen.getByText(/▲ 20.3% vs previous period/)).toBeInTheDocument();
    expect(screen.getByText(/▼ 4.2% vs previous period/)).toBeInTheDocument();
    expect(screen.getByText("Sales and profit trend")).toBeInTheDocument();
    expect(screen.getByText("Tom Ashbrook")).toBeInTheDocument();
  });

  it("sends the chosen filters to the API", async () => {
    const { calls } = mockFetch({ "/api/v1/analytics/filters": FILTERS, "/api/v1/analytics/dashboard": dashboard });
    renderPage(<Overview />);
    await screen.findByText("Total sales");
    await userEvent.selectOptions(screen.getByLabelText("Category"), "Technology");
    await waitFor(() => expect(calls.some((c) => c.url.includes("category=Technology"))).toBe(true));
  });

  it("shows setup help - and no figures - when the database is not ready", async () => {
    mockFetch({
      "/api/v1/analytics/filters": errorResponse(503, "database_not_configured", "DATABASE_URL is not configured.", "Check /api/v1/system/status"),
      "/api/v1/analytics/dashboard": errorResponse(503, "database_not_configured", "DATABASE_URL is not configured.", "Check /api/v1/system/status"),
    });
    renderPage(<Overview />);
    expect(await screen.findByText("The database is not ready yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /System status/i })).toHaveAttribute("href", "/status");
    expect(screen.queryByText("Total sales")).not.toBeInTheDocument();
    expect(screen.queryByText(/\$/)).not.toBeInTheDocument();
  });

  it("shows an error with retry for unexpected failures", async () => {
    mockFetch({ "/api/v1/analytics/filters": FILTERS, "/api/v1/analytics/dashboard": errorResponse(500, "internal_error", "An unexpected error occurred.") });
    renderPage(<Overview />);
    expect(await screen.findByText("An unexpected error occurred.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("shows an empty state when the filters match nothing", async () => {
    mockFetch({ "/api/v1/analytics/filters": FILTERS, "/api/v1/analytics/dashboard": { ...dashboard, kpis: { ...dashboard.kpis, order_lines: 0, orders: 0 } } });
    renderPage(<Overview />);
    expect(await screen.findByText("No orders match these filters")).toBeInTheDocument();
  });

  it("rejects an inverted date range before calling the API", async () => {
    const { calls } = mockFetch({ "/api/v1/analytics/filters": FILTERS, "/api/v1/analytics/dashboard": dashboard });
    renderPage(<Overview />);
    await screen.findByText("Total sales");
    const before = calls.filter((c) => c.url.includes("/dashboard")).length;
    await userEvent.type(screen.getByLabelText("From"), "2014-06-01");
    await userEvent.type(screen.getByLabelText("To"), "2013-06-01");
    expect(await screen.findByRole("alert")).toHaveTextContent(/start date must be on or before/i);
    expect(calls.filter((c) => c.url.includes("/dashboard")).length).toBe(before + 1); // only the valid intermediate request
  });
});

describe("Predict", () => {
  const routes = { "/api/v1/ml/schema": schema, "/api/v1/ml/metadata": metadata };

  it("builds the form from the model's real input schema", async () => {
    mockFetch(routes);
    renderPage(<Predict />);
    expect(await screen.findByLabelText(/Category/)).toBeInTheDocument();
    for (const name of [/Sub-category/, /Market/, /Quantity/, /Discount \(%\)/, /Shipping cost/, /Order date/]) expect(screen.getByLabelText(name)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Year/)).not.toBeInTheDocument(); // nothing the model does not take
  });

  it("limits sub-categories to the chosen category", async () => {
    mockFetch(routes);
    renderPage(<Predict />);
    await userEvent.selectOptions(await screen.findByLabelText(/^Category/), "Furniture");
    const sub = screen.getByLabelText(/Sub-category/);
    expect(within(sub).getAllByRole("option").map((o) => o.textContent)).toEqual(["Select...", "Chairs", "Tables"]);
  });

  it("validates before submitting and does not call the API", async () => {
    const { calls } = mockFetch(routes);
    renderPage(<Predict />);
    await userEvent.click(await screen.findByRole("button", { name: "Predict sales" }));
    expect(await screen.findByText("Category is required.")).toBeInTheDocument();
    expect(screen.getByText("Market is required.")).toBeInTheDocument();
    expect(calls.some((c) => c.url.endsWith("/predict"))).toBe(false);
  });

  it("submits, converts percent to fraction and shows the estimate with its caveats", async () => {
    const { calls } = mockFetch({ ...routes, "/api/v1/ml/predict": prediction });
    renderPage(<Predict />);
    await userEvent.click(await screen.findByRole("button", { name: "Fill example" }));
    await userEvent.click(screen.getByRole("button", { name: "Predict sales" }));
    expect(await screen.findByText("$356.64")).toBeInTheDocument();
    const sent = JSON.parse(String(calls.find((c) => c.url.endsWith("/predict"))!.init!.body));
    expect(sent).toMatchObject({ category: "Technology", sub_category: "Phones", market: "US", quantity: 3, discount: 0.1 });
    expect(screen.getByText(/Estimate for a single order line/)).toBeInTheDocument();
    expect(screen.getByText("leakage-safe")).toBeInTheDocument();
    expect(screen.getByText(/segment not provided/)).toBeInTheDocument();
  });

  it("maps server-side field errors onto the inputs", async () => {
    mockFetch({ ...routes, "/api/v1/ml/predict": errorResponse(422, "invalid_input", "Invalid prediction input.", undefined, { sub_category: "'Chairs' is not a sub-category of 'Technology'." }) });
    renderPage(<Predict />);
    await userEvent.click(await screen.findByRole("button", { name: "Fill example" }));
    await userEvent.click(screen.getByRole("button", { name: "Predict sales" }));
    expect(await screen.findByText(/is not a sub-category/)).toBeInTheDocument();
  });

  it("shows model metrics read from the API", async () => {
    mockFetch(routes);
    renderPage(<Predict />);
    expect(await screen.findByText("Model information")).toBeInTheDocument();
    expect(screen.getAllByText("0.415").length).toBeGreaterThan(0);
    expect(screen.getByText(/Read this before relying on an estimate/)).toBeInTheDocument();
  });

  it("shows setup help when the model is not trained", async () => {
    mockFetch({ "/api/v1/ml/schema": errorResponse(503, "model_not_ready", "Model file not found.", "Train the model: python scripts/train_model.py"), "/api/v1/ml/metadata": errorResponse(503, "model_not_ready", "Model file not found.") });
    renderPage(<Predict />);
    expect(await screen.findByText("The prediction model is not trained yet")).toBeInTheDocument();
    expect(screen.getByText(/python scripts\/train_model.py/)).toBeInTheDocument();
  });
});

describe("AI Analytics chat", () => {
  const chatResponse = {
    answer: "**Measured from the database** - Total sales by category.\n\nTop results: Technology ($4,744,691).",
    answer_mode: "deterministic",
    route: { tools: ["sql"], method: "rules", reason: "The question asks for figures that can be computed from the sales database." },
    tools: [{ name: "sql", status: "ok", message: null, duration_ms: 20 }],
    evidence: {
      sql: { question: "q", status: "ok", method: "template", sql: "SELECT category FROM retailiq.v_sales", params: {}, explanation: "Total sales by category.",
        columns: [{ name: "category", type: "text" }, { name: "total_sales", type: "number" }], rows: [["Technology", 4744691], ["Furniture", 4110884]],
        row_count: 2, truncated: false, elapsed_ms: 12, chart: { type: "bar", x: "category", y: "total_sales" }, notes: [], error: null, supported_examples: [] },
      prediction: null, sources: null,
    },
    warnings: [], elapsed_ms: 400,
  };

  it("sends the question and renders answer, route, tools and evidence", async () => {
    const { calls } = mockFetch({ "/api/v1/agent/chat": chatResponse });
    renderPage(<Assistant />);
    await userEvent.type(screen.getByLabelText("Your question"), "Which category has the highest sales?");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(await screen.findByText(/Top results: Technology/)).toBeInTheDocument();
    expect(JSON.parse(String(calls[0].init!.body))).toEqual({ message: "Which category has the highest sales?" });
    expect(screen.getByText("Built-in answer (no LLM)")).toBeInTheDocument();
    expect(screen.getByText(/SQL analytics: ok/)).toBeInTheDocument();
    expect(screen.getByText("Measured results (database)")).toBeInTheDocument();
    expect(screen.getByText("$4,744,691")).toBeInTheDocument();  // formatted table cell
    await userEvent.click(screen.getByRole("button", { name: /Show the SQL that was executed/ }));
    expect(screen.getByText(/SELECT category FROM retailiq.v_sales/)).toBeInTheDocument();
  });

  it("example buttons ask immediately", async () => {
    mockFetch({ "/api/v1/agent/chat": chatResponse });
    renderPage(<Assistant />);
    await userEvent.click(screen.getByRole("button", { name: "What is the monthly sales trend?" }));
    expect(await screen.findByText(/Top results: Technology/)).toBeInTheDocument();
  });

  it("shows a loading state and then an error without inventing an answer", async () => {
    mockFetch({ "/api/v1/agent/chat": errorResponse(500, "internal_error", "An unexpected error occurred.") });
    renderPage(<Assistant />);
    await userEvent.type(screen.getByLabelText("Your question"), "anything");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(await screen.findByText("An unexpected error occurred.")).toBeInTheDocument();
    expect(screen.queryByText("Measured results (database)")).not.toBeInTheDocument();
  });

  it("does not submit an empty question", () => {
    mockFetch({});
    renderPage(<Assistant />);
    expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
  });

  it("renders tool failures and needs-input states visibly", async () => {
    mockFetch({ "/api/v1/agent/chat": { ...chatResponse, answer: "**Prediction needs more information** - please provide: market.", route: { ...chatResponse.route, tools: ["ml"] },
      tools: [{ name: "ml", status: "needs_input", message: "More information is needed", duration_ms: 1 }], evidence: { sql: null, prediction: null, sources: null } } });
    renderPage(<Assistant />);
    await userEvent.type(screen.getByLabelText("Your question"), "Predict sales for Technology");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(await screen.findByText(/ML prediction: needs input/)).toBeInTheDocument();
    expect(screen.getByText(/please provide: market/)).toBeInTheDocument();
  });
});

describe("Knowledge assistant", () => {
  const base = { question: "q", warnings: [] };
  const statusRoute = { "/api/v1/system/status": status };

  it("labels retrieval-only answers and lists sources with confidence", async () => {
    mockFetch({ ...statusRoute, "/api/v1/rag/ask": { ...base, answer: "Retrieval-only answer (no LLM available) - passages:\n- ON CONFLICT [1]", answer_mode: "extractive", retrieval_mode: "semantic",
      sources: [{ id: 1, source: "docs/03_etl_pipeline.md", heading: "ETL > Idempotency", score: 0.52, confidence: "high", snippet: "row_id is the idempotency key." }] } });
    renderPage(<Knowledge />);
    await userEvent.type(screen.getByLabelText("Question"), "How does the ETL avoid duplicate rows?");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(await screen.findByText("Retrieval-only (no LLM)")).toBeInTheDocument();
    expect(screen.getByText("Semantic search")).toBeInTheDocument();
    expect(screen.getByText("docs/03_etl_pipeline.md")).toBeInTheDocument();
    expect(screen.getByText("high match")).toBeInTheDocument();
  });

  it("is explicit about keyword fallback and low confidence", async () => {
    mockFetch({ ...statusRoute, "/api/v1/rag/ask": { ...base, answer: "Retrieval-only answer", answer_mode: "extractive", retrieval_mode: "lexical_fallback", warnings: ["Low-confidence match: the documentation may not actually cover this question - check the sources."],
      sources: [{ id: 1, source: "docs/x.md", heading: "H", score: 0.1, confidence: "low", snippet: "s" }] } });
    renderPage(<Knowledge />);
    await userEvent.type(screen.getByLabelText("Question"), "something loosely related");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(await screen.findByText("Keyword fallback")).toBeInTheDocument();
    expect(screen.getByText(/Low-confidence match/)).toBeInTheDocument();
  });

  it("shows an empty state when nothing supports an answer", async () => {
    mockFetch({ ...statusRoute, "/api/v1/rag/ask": { ...base, answer: "I found no supporting documents for that question in the project knowledge base.", answer_mode: "none", retrieval_mode: "semantic", sources: [] } });
    renderPage(<Knowledge />);
    await userEvent.type(screen.getByLabelText("Question"), "recipe for chocolate cake");
    await userEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(await screen.findByText("No supporting documents found")).toBeInTheDocument();
  });

  it("shows the knowledge-base state", async () => {
    mockFetch(statusRoute);
    renderPage(<Knowledge />);
    expect(await screen.findByText("101")).toBeInTheDocument();
    expect(screen.getByText("passages only")).toBeInTheDocument();
  });
});

describe("Status", () => {
  it("shows every component and the setup steps", async () => {
    mockFetch({ "/api/v1/system/status": status });
    renderPage(<Status />);
    expect(await screen.findByText("Everything is ready.")).toBeInTheDocument();
    expect(screen.getByText("PostgreSQL")).toBeInTheDocument();
    expect(screen.getAllByText("51,290").length).toBeGreaterThan(0);
    expect(screen.getByText(/postgresql\+psycopg:\/\/retailiq_readonly:\*\*\*@/)).toBeInTheDocument(); // password redacted
    expect(screen.getByText("Setup steps")).toBeInTheDocument();
    expect(screen.getAllByText(/ollama pull llama3.2/).length).toBeGreaterThan(0);
  });

  it("explains a setup-required system", async () => {
    mockFetch({ "/api/v1/system/status": { ...status, overall: "setup_required", database: { ...status.database, configured: false, connected: false, schema_ready: false, fact_rows: null, error: "No database URL configured" },
      setup_steps: [{ component: "database", required: "yes", action: "Set DATABASE_URL in .env, then run: python scripts/setup_database.py --create-database" }] } });
    renderPage(<Status />);
    expect(await screen.findByText(/Setup is required/)).toBeInTheDocument();
    expect(screen.getByText("required")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "copy" })).toBeInTheDocument();
  });

  it("admin actions need a token and send it as a header", async () => {
    const { calls } = mockFetch({ "/api/v1/system/status": status, "/api/v1/rag/index": { status: "up_to_date", chunks: 101 } });
    renderPage(<Status />);
    const reindex = await screen.findByRole("button", { name: "Re-index docs" });
    expect(reindex).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Admin token"), "secret");
    await userEvent.click(reindex);
    await screen.findByText(/Index: up to date/);
    expect(calls.find((c) => c.url.endsWith("/rag/index"))!.init!.headers).toMatchObject({ "X-Admin-Token": "secret" });
  });

  it("reports an unreachable API", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    renderPage(<Status />);
    expect(await screen.findByText(/Cannot reach the RetailIQ API/)).toBeInTheDocument();
  });
});

describe("Layout and About", () => {
  it("shows an offline banner and no data when the API is down", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    renderPage(<Routes><Route element={<Layout />}><Route index element={<p>page</p>} /></Route></Routes>);
    expect(await screen.findByText(/The RetailIQ API is not reachable/)).toBeInTheDocument();
    expect(await screen.findByText("API offline")).toBeInTheDocument();
  });

  it("shows readiness in the navigation and exposes all pages", async () => {
    mockFetch({ "/api/v1/system/status": status });
    renderPage(<Routes><Route element={<Layout />}><Route index element={<p>page</p>} /></Route></Routes>);
    expect(await screen.findByText("All systems ready")).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: "Main" });
    for (const name of ["Overview", "AI Analytics", "Sales Prediction", "Knowledge Assistant", "Data & Model Status", "About"]) expect(within(nav).getByRole("link", { name })).toBeInTheDocument();
  });

  it("About shows evaluation numbers read from the model, not typed in", async () => {
    mockFetch({ "/api/v1/ml/metadata": metadata });
    renderPage(<About />);
    expect(await screen.findByText("R² 0.415")).toBeInTheDocument();
    expect(screen.getByText("R² 0.652")).toBeInTheDocument();
  });
});

describe("RichText", () => {
  it("renders bold/italic/code and bullets as elements, never as HTML", () => {
    const { container } = renderPage(<RichText text={'**Bold** and _it_ with `code`\n\n- one\n- two <img src=x onerror=alert(1)>'} />);
    expect(container.querySelector("strong")?.textContent).toBe("Bold");
    expect(container.querySelectorAll("li")).toHaveLength(2);
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain("<img src=x onerror=alert(1)>");
  });

  it("does not treat underscores inside identifiers as italics", () => {
    const { container } = renderPage(<RichText text="ship_mode not provided; assumed 'Standard Class'. order_priority not provided; shipping_days too. _real italic_ here" />);
    expect(container.textContent).toContain("ship_mode not provided");
    expect(container.textContent).toContain("order_priority not provided");
    expect(container.querySelectorAll("em")).toHaveLength(1);
    expect(container.querySelector("em")?.textContent).toBe("real italic");
  });
});
