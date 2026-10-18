import type { InputField, PredictionRequest } from "./types";

export type Values = Record<string, string>;

// Client-side limits (the server enforces the same ones).
const LIMITS: Record<string, [number, number]> = { quantity: [1, 1000], discount: [0, 100], shipping_days: [0, 60], shipping_cost: [0, 100_000] };

export function fieldLabel(f: InputField): string {
  return f.name === "discount" ? "Discount (%)" : f.label;
}

export function validate(fields: InputField[], v: Values): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const f of fields) {
    const raw = (v[f.name] ?? "").trim();
    if (!raw) {
      if (f.required) errors[f.name] = `${fieldLabel(f)} is required.`;
      continue;
    }
    if (f.kind === "integer" || f.kind === "number") {
      const n = Number(raw);
      const [lo, hi] = LIMITS[f.name] ?? [-Infinity, Infinity];
      if (!Number.isFinite(n)) errors[f.name] = "Enter a number.";
      else if (f.kind === "integer" && !Number.isInteger(n)) errors[f.name] = "Enter a whole number.";
      else if (n < lo || n > hi) errors[f.name] = `Must be between ${lo} and ${hi}.`;
    }
    if (f.kind === "date" && Number.isNaN(Date.parse(raw))) errors[f.name] = "Enter a valid date.";
  }
  return errors;
}

export function toRequest(fields: InputField[], v: Values): PredictionRequest {
  const body: Record<string, string | number> = {};
  for (const f of fields) {
    const raw = (v[f.name] ?? "").trim();
    if (!raw) continue;
    if (f.kind === "integer") body[f.name] = parseInt(raw, 10);
    else if (f.kind === "number") body[f.name] = f.name === "discount" ? Number(raw) / 100 : Number(raw);
    else body[f.name] = raw;
  }
  return body as unknown as PredictionRequest;
}

