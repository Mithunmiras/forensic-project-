import { ApiError, request } from "./api";
import { fmtCell, fmtCompactMoney, fmtDate, fmtFraction, fmtMoney, fmtMoney2, fmtPct, titleCase } from "./format";
import { toRequest, validate } from "./predictForm";
import { errorResponse, mockFetch, schema } from "../test/fixtures";

describe("formatting", () => {
  it("formats money, compact money, percentages and dates", () => {
    expect(fmtMoney(4744691)).toBe("$4,744,691");
    expect(fmtMoney2(356.6)).toBe("$356.60");
    expect(fmtCompactMoney(12642905)).toBe("$12.6M");
    expect(fmtCompactMoney(-64083)).toBe("-$64.1K");
    expect(fmtPct(12.345)).toBe("12.3%");
    expect(fmtFraction(0.1429)).toBe("14.3%");
    expect(fmtDate("2014-12-31")).toBe("Dec 31, 2014");
    expect(titleCase("sub_category")).toBe("Sub Category");
  });

  it("never renders missing values as numbers", () => {
    for (const f of [fmtMoney, fmtMoney2, fmtCompactMoney, fmtPct, fmtFraction, fmtDate]) expect(f(null)).toBe("n/a");
  });

  it("formats result cells by column name", () => {
    expect(fmtCell("total_sales", 4744691)).toBe("$4,744,691");
    expect(fmtCell("avg_discount_pct", 16.81)).toBe("16.81%");
    expect(fmtCell("avg_shipping_days", 5)).toBe("5");
    expect(fmtCell("orders", 25035)).toBe("25,035");
    expect(fmtCell("category", "Technology")).toBe("Technology");
    expect(fmtCell("x", null)).toBe("n/a");
  });
});

describe("API client", () => {
  it("returns parsed JSON", async () => {
    mockFetch({ "/api/v1/health": { status: "ok" } });
    await expect(request("/api/v1/health")).resolves.toEqual({ status: "ok" });
  });

  it("normalises the backend error shape", async () => {
    mockFetch({ "/x": errorResponse(422, "invalid_input", "Invalid prediction input.", "check it", { quantity: "must be positive" }) });
    const err = await request("/x").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 422, code: "invalid_input", hint: "check it", fields: { quantity: "must be positive" } });
  });

  it("flags setup problems so the UI can show setup help instead of an error", async () => {
    mockFetch({ "/x": errorResponse(503, "database_not_configured", "DATABASE_URL is not configured.") });
    const err = (await request("/x").catch((e) => e)) as ApiError;
    expect(err.isSetupProblem).toBe(true);
    expect(new ApiError(500, "internal_error", "x").isSetupProblem).toBe(false);
  });

  it("turns network failures into a clear message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const err = (await request("/x").catch((e) => e)) as ApiError;
    expect(err.isNetwork).toBe(true);
    expect(err.message).toMatch(/Cannot reach the RetailIQ API/);
  });

  it("times out instead of hanging", async () => {
    vi.stubGlobal("fetch", vi.fn((_u: string, init: RequestInit) => new Promise((_res, rej) => {
      init.signal?.addEventListener("abort", () => rej(new DOMException("aborted", "AbortError")));
    })));
    const err = (await request("/slow", { timeoutMs: 30 }).catch((e) => e)) as ApiError;
    expect(err.code).toBe("timeout");
  });

  it("copes with non-JSON error bodies", async () => {
    mockFetch({ "/x": new Response("Bad gateway", { status: 502 }) });
    const err = (await request("/x").catch((e) => e)) as ApiError;
    expect(err.status).toBe(502);
    expect(err.message).toMatch(/502/);
  });

  it("sends JSON bodies and custom headers", async () => {
    const { calls } = mockFetch({ "/p": { ok: true } });
    await request("/p", { method: "POST", body: { a: 1 }, headers: { "X-Admin-Token": "t" } });
    const init = calls[0].init!;
    expect(init.method).toBe("POST");
    expect(init.body).toBe('{"a":1}');
    expect(init.headers).toMatchObject({ "Content-Type": "application/json", "X-Admin-Token": "t" });
  });
});

describe("prediction form helpers", () => {
  const fields = schema.fields;

  it("requires the required fields only", () => {
    const errs = validate(fields, {});
    expect(Object.keys(errs).sort()).toEqual(["category", "discount", "market", "quantity", "sub_category"]);
  });

  it("checks types and ranges", () => {
    const base = { category: "Technology", sub_category: "Phones", market: "US", quantity: "3", discount: "10" };
    expect(validate(fields, base)).toEqual({});
    expect(validate(fields, { ...base, quantity: "0" }).quantity).toMatch(/between 1 and 1000/);
    expect(validate(fields, { ...base, quantity: "2.5" }).quantity).toMatch(/whole number/);
    expect(validate(fields, { ...base, quantity: "abc" }).quantity).toBeDefined();
    expect(validate(fields, { ...base, discount: "150" }).discount).toMatch(/0 and 100/);
    expect(validate(fields, { ...base, shipping_cost: "-5" }).shipping_cost).toBeDefined();
  });

  it("converts the percent field to the API fraction and drops blanks", () => {
    const body = toRequest(fields, { category: "Technology", sub_category: "Phones", market: "US", quantity: "3", discount: "10", shipping_cost: "", order_date: "2014-06-15" });
    expect(body).toEqual({ category: "Technology", sub_category: "Phones", market: "US", quantity: 3, discount: 0.1, order_date: "2014-06-15" });
  });
});
