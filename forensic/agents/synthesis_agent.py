"""Synthesis / XAI agent - fuses the other agents' evidence into the four-layer answer.

It is the ONLY agent that writes prescriptive text. Every sentence is assembled from an
evidence object and carries a citation marker [n] that points at a specific table slice,
model or document, so no claim appears without a source.

Graceful degradation is an explicit rule table, not an afterthought:

  structured anomaly | matching document | case                | confidence
  -------------------+-------------------+---------------------+-----------
  yes                | yes (compatible)  | full                | high
  yes                | yes (conflicting) | conflict            | medium
  yes                | no                | structured_only     | medium
  no / no data       | yes               | unstructured_only   | medium
  no                 | no                | none                | high (that nothing happened)
  no data            | no docs           | no_data             | low
"""
from __future__ import annotations

import calendar
from typing import Optional

from forensic.catalog import CAUSES

CHECK_LABELS = {"supply": "a supply / stock-out problem", "returns": "a quality or returns problem",
                "discount": "a discount effect", "price": "a price change", "demand": "a demand shift"}
FAMILY_TO_CHECK = {"supply": "supply", "returns": "returns", "discount": "discount", "price": "price",
                   "demand_down": "demand", "demand_up": "demand"}


def month_label(month: Optional[str]) -> str:
    if not month or month.startswith("?"):
        return month or "the period"
    return f"{calendar.month_name[int(month[5:])]} {month[:4]}"


def pct(v: float) -> str:
    return f"{v:+.1f}%"


class Citations:
    def __init__(self) -> None:
        self.items = []
        self._index = {}

    def cite(self, key: str, kind: str, label: str, detail: str, path: Optional[str] = None) -> str:
        if key not in self._index:
            self.items.append({"id": len(self.items) + 1, "kind": kind, "label": label, "detail": detail, "path": path})
            self._index[key] = len(self.items)
        return f"[{self._index[key]}]"


class SynthesisAgent:
    name = "Synthesis / XAI Agent"

    def run(self, plan: dict, sql: dict, rag: dict, rca: dict) -> dict:
        c = Citations()
        name = plan.get("product_name") or plan.get("product_id") or "the product"
        region, month = plan.get("region"), plan.get("month")
        ctx = {"name": name, "region": region, "month": month, "c": c, "plan": plan, "sql": sql, "rag": rag, "rca": rca}

        structured_ok = bool(sql.get("available"))
        anomaly = bool(rca.get("available") and rca.get("is_anomaly"))
        incidents = rag.get("incidents") or []
        compatible = [d for d in incidents if d["cause"] in (rca.get("compatible_causes") or [])]

        doc, cause = None, None
        if anomaly and compatible:
            case, doc = "full", compatible[0]
            cause = {"key": doc["cause"], "label": CAUSES[doc["cause"]]["label"], "status": "confirmed"}
        elif anomaly and incidents:
            case, doc = "conflict", incidents[0]
            cause = dict(rca["hypothesis"], status="inferred")
        elif anomaly:
            case = "structured_only"
            cause = dict(rca["hypothesis"], status="inferred")
        elif incidents:
            case, doc = "unstructured_only", incidents[0]
            cause = {"key": doc["cause"], "label": CAUSES[doc["cause"]]["label"], "status": "reported"}
        elif structured_ok or rag.get("available"):
            case = "none"
            cause = {"key": "none", "label": "No incident", "status": "none"}
        else:
            case = "no_data"
            cause = {"key": "unknown", "label": "Insufficient data", "status": "none"}
        ctx.update(case=case, doc=doc, cause=cause)

        descriptive = self._descriptive(ctx)
        diagnostic = self._diagnostic(ctx)
        predictive = self._predictive(ctx)
        actions = self._prescriptive(ctx)
        confidence = self._confidence(ctx)

        return {
            "agent": self.name,
            "headline": self._headline(ctx),
            "case": case,
            "cause": cause,
            "evidence_status": {
                "structured_available": structured_ok,
                "structured_anomaly": anomaly,
                "unstructured_available": bool(rag.get("available")),
                "unstructured_match": bool(incidents),
                "documents_compatible": bool(compatible),
            },
            "layers": {
                "descriptive": descriptive,
                "diagnostic": diagnostic,
                "predictive": predictive,
                "prescriptive": " ".join(f"{i + 1}. {a}" for i, a in enumerate(actions)),
            },
            "actions": actions,
            "confidence": confidence,
            "citations": c.items,
        }

    # -- citation helpers -----------------------------------------------------------------
    @staticmethod
    def _c_sales(ctx) -> str:
        p = ctx["plan"]
        return ctx["c"].cite("sales", "table", "sales.csv",
                             f"{p['product_id']} / {ctx['region']}: {month_label(ctx['month'])} vs. the other months "
                             "of the same series (robust baseline)")

    @staticmethod
    def _c_inventory(ctx) -> str:
        s = ctx["sql"]["stockout"]
        detail = f"{s['warehouse']}, {ctx['plan']['product_id']}"
        if s["first"]:
            detail += f": stock_level = 0 from {s['first']} to {s['last']}"
        return ctx["c"].cite("inventory", "table", "inventory.csv", detail)

    @staticmethod
    def _c_regions(ctx) -> str:
        return ctx["c"].cite("regions", "table", "sales.csv",
                             f"{ctx['plan']['product_id']}: other regions, {month_label(ctx['month'])}")

    @staticmethod
    def _c_doc(ctx, d) -> str:
        return ctx["c"].cite(d["path"], "document", d["filename"], f"{d['title']} ({d['doc_type']}, {d['date']}, "
                             f"region {d['region']})", path=d["path"])

    @staticmethod
    def _c_catalog(ctx) -> str:
        return ctx["c"].cite("catalog", "store", "catalog.json",
                             f"product document {ctx['plan']['product_id']} with primary/backup suppliers")

    @staticmethod
    def _c_forecast(ctx, fc) -> str:
        return ctx["c"].cite("forecast", "model", "Forecast model",
                             f"{fc['method']}, trained on sales.csv through {fc['trained_through']}")

    # -- layers ---------------------------------------------------------------------------
    def _descriptive(self, ctx) -> str:
        sql, name, region = ctx["sql"], ctx["name"], ctx["region"]
        if not sql.get("available"):
            return (f"No structured figures are available for {name}: {sql.get('reason') or 'no data'} "
                    "The descriptive layer cannot be quantified.")
        t = sql["target"]
        cs = self._c_sales(ctx)
        text = (f"{name} in the {region} region sold {t['units_per_day']:,.0f} units/day in {month_label(ctx['month'])} "
                f"({pct(t['units_per_day_pct'])} vs. a baseline of {t['units_per_day_base']:,.0f}")
        if sql.get("previous_month") and t.get("units_prev_pct") is not None:
            text += f"; {pct(t['units_prev_pct'])} vs. {month_label(sql['previous_month'])}"
        text += f") {cs}. Revenue was ${t['revenue']:,.0f} ({pct(t['revenue_per_day_pct'])} per day vs. baseline). "
        text += (f"Returns rate {t['returns_rate']:.2f}% (baseline {t['returns_rate_base']:.2f}%), average discount "
                 f"{t['avg_discount']:.1f}% (baseline {t['avg_discount_base']:.1f}%).")
        s = sql["stockout"]
        if s["days"]:
            text += f" {s['warehouse']} had zero stock on {s['days']} day(s), {s['first']} to {s['last']} {self._c_inventory(ctx)}."
        if t["is_anomaly"]:
            text += f" This month is statistically unusual for the series (anomaly score {t['anomaly_score']:.1f})."
        else:
            text += (f" This is within normal variation (units z = {t['units_per_day_z']:.1f}; RetailIQ needs |z| >= 3 "
                     "and a change of at least 5%).")
        return text

    def _signal_sentences(self, ctx) -> list:
        sql, rca = ctx["sql"], ctx["rca"]
        t, s = sql["target"], sql["stockout"]
        parts = []
        for fam in rca["signature"]:
            if fam == "supply":
                parts.append(f"a {s['days']}-day stock-out at {s['warehouse']} ({s['first']} to {s['last']}) "
                             f"{self._c_inventory(ctx)}")
            elif fam == "returns":
                parts.append(f"the returns rate rose to {t['returns_rate']:.2f}% from a {t['returns_rate_base']:.2f}% "
                             f"baseline ({pct(t['returns_rate_pct'])}, z = {t['returns_rate_z']:.1f}) {self._c_sales(ctx)}")
            elif fam == "discount":
                parts.append(f"the average discount rose to {t['avg_discount']:.1f}% from {t['avg_discount_base']:.1f}% "
                             f"{self._c_sales(ctx)}")
            elif fam == "price":
                parts.append(f"the realised list price was {pct(t['price_index_pct'])} above baseline {self._c_sales(ctx)}")
            elif fam in ("demand_down", "demand_up"):
                parts.append(f"units/day moved {pct(t['units_per_day_pct'])} (z = {t['units_per_day_z']:.1f}) "
                             f"{self._c_sales(ctx)}")
        return parts

    def _scope_sentence(self, ctx) -> str:
        rca, sql = ctx["rca"], ctx["sql"]
        moves = ", ".join(f"{o['region']} {pct(o['units_per_day_pct'])}" for o in sql["other_regions"])
        cr = self._c_regions(ctx)
        if rca["scope"] == "localized":
            return f"The change is local to {ctx['region']}: other regions stayed normal ({moves}) {cr}."
        if rca["scope"] == "market-wide":
            return f"Other regions moved too ({moves}) {cr}, which points to a product-wide driver."
        if rca["scope"] == "partly shared":
            return f"Some other regions also moved ({moves}) {cr}."
        return ""

    def _ruled_out(self, ctx) -> str:
        rca, rag = ctx["rca"], ctx["rag"]
        fired = {FAMILY_TO_CHECK[f] for f in rca["signature"]}
        parts = [f"{CHECK_LABELS[ch['key']]} ({ch['detail']})" for ch in rca["checks"]
                 if ch["key"] not in fired and ch["key"] != "demand"]
        text = ""
        if parts:
            text = f"Ruled out from the tables: {'; '.join(parts)} {self._c_sales(ctx)}."
        routine = rag.get("routine") or []
        if routine:
            refs = ", ".join(f"{r['title']} {self._c_doc(ctx, r)}" for r in routine[:2])
            text += f" Routine documents for the period report nothing unusual: {refs}."
        return text

    def _diagnostic(self, ctx) -> str:
        case, cause, doc, name = ctx["case"], ctx["cause"], ctx["doc"], ctx["name"]
        rca, sql, rag = ctx["rca"], ctx["sql"], ctx["rag"]
        if case == "full":
            text = f"**Root cause: {cause['label']}**, confirmed by both the structured data and a document. "
            text += f"Structured evidence: {'; '.join(self._signal_sentences(ctx))}. "
            text += f"Documentary evidence: “{doc['quote']}” ({doc['title']}, {doc['date']}) {self._c_doc(ctx, doc)}. "
            text += self._scope_sentence(ctx) + " " + self._ruled_out(ctx)
            return text.strip()
        if case == "conflict":
            text = (f"**Most likely: {cause['label']}** (inferred from data patterns). Structured evidence: "
                    f"{'; '.join(self._signal_sentences(ctx))}. A document was found describing "
                    f"{CAUSES[doc['cause']]['label'].lower()} {self._c_doc(ctx, doc)}, but that does not match the structured "
                    "signature, so the documentary explanation is treated as unconfirmed. ")
            return (text + self._scope_sentence(ctx)).strip()
        if case == "structured_only":
            text = (f"**Statistical diagnosis: {cause['label']}.** Structured evidence: "
                    f"{'; '.join(self._signal_sentences(ctx))} (anomaly score {rca['anomaly_score']:.1f}). ")
            text += self._scope_sentence(ctx) + " " + self._ruled_out(ctx) + " "
            text += "No supporting unstructured evidence was found; the root cause is inferred from data patterns only."
            if not rag.get("available"):
                text += f" (There are no documents on file for {name}.)"
            return text.strip()
        if case == "unstructured_only":
            text = (f"**Reported issue: {cause['label']}.** “{doc['quote']}” ({doc['title']}, {doc['date']}) "
                    f"{self._c_doc(ctx, doc)}. ")
            if sql.get("available"):
                t = sql["target"]
                text += ("Sales data for this period does not show a statistically significant deviation; this issue may "
                         f"not yet be materially affecting sales (units/day {pct(t['units_per_day_pct'])}, "
                         f"z = {t['units_per_day_z']:.1f}) {self._c_sales(ctx)}.")
            else:
                text += (f"No sales or inventory records exist for {name}, so the impact cannot be quantified or "
                         "verified. The cause is taken from documents only.")
            return text
        if case == "none":
            text = "No anomaly detected and no related documents found for this product/period."
            if sql.get("available"):
                t = sql["target"]
                text += (f" Units/day moved {pct(t['units_per_day_pct'])} (z = {t['units_per_day_z']:.1f}), which is "
                         f"ordinary noise {self._c_sales(ctx)}.")
            routine = rag.get("routine") or []
            if routine:
                refs = ", ".join(f"{r['filename']} {self._c_doc(ctx, r)}" for r in routine[:3])
                text += f" {len(routine)} routine document(s) for the period were reviewed and report nothing unusual: {refs}."
            if not rag.get("available"):
                text += f" (There are no documents on file for {name}, so only the tables were checked.)"
            return text
        return ("Neither structured data nor documents are available for this request, so RetailIQ cannot investigate it. "
                + " ".join(x for x in (sql.get("reason"), rag.get("reason")) if x))

    def _predictive(self, ctx) -> str:
        rca, case, cause, name = ctx["rca"], ctx["case"], ctx["cause"], ctx["name"]
        fc = rca.get("forecast") if rca.get("available") else None
        if not fc:
            return f"No forecast is possible: there is no sales history for {name}."
        cf = self._c_forecast(ctx, fc)
        text = (f"Model forecast for {month_label(fc['next_month'])}: about {fc['predicted_per_day']:,.0f} units/day "
                f"({pct(fc['predicted_pct_vs_baseline'])} vs. baseline) {cf}.")
        if case in ("full", "structured_only", "conflict"):
            label = cause["label"].lower()
            text += (f" If the {label} persists at {month_label(ctx['month'])} intensity, expect about "
                     f"{fc['if_cause_persists_per_day']:,.0f} units/day ({pct(fc['if_cause_persists_pct'])}).")
            if abs(fc["predicted_pct_vs_baseline"]) < abs(fc["if_cause_persists_pct"]) / 2:
                text += (" The model already expects a return towards baseline because the last weeks of the month were "
                         f"close to normal. That holds only if the {label} is resolved.")
        elif case == "unstructured_only":
            text += (" The reported issue is not visible in the numbers yet. If it materialises, re-run this investigation "
                     "next month; the forecast assumes it does not.")
        else:
            text += " This is consistent with normal variation."
        return text

    def _prescriptive(self, ctx) -> list:
        case, cause, sql, name, region = ctx["case"], ctx["cause"], ctx["sql"], ctx["name"], ctx["region"]
        key = cause["key"]
        suppliers = sql.get("suppliers") or {"primary": [], "backup": []}
        primary = suppliers["primary"][0] if suppliers["primary"] else None
        backup = suppliers["backup"][0] if suppliers["backup"] else None
        t = sql.get("target") or {}
        st = sql.get("stockout") or {}
        wh = st.get("warehouse") or f"the {region} warehouse"
        def cc():
            return self._c_catalog(ctx)

        acts = []

        if case == "none":
            return ["No action required. Keep monitoring: RetailIQ flags the series automatically if it moves beyond 3 "
                    "robust standard deviations and 5%."]
        if case == "no_data":
            return ["Load sales/inventory records or documents for this product so it can be investigated."]

        if key in ("supplier_delay", "supply_disruption", "logistics_disruption"):
            if key == "supply_disruption":
                acts.append(f"Find out why {wh} ran out of stock: no document explains it. Ask "
                            f"{primary['supplier_name'] if primary else 'the supplier'} and the warehouse team for "
                            "shipment and receiving logs for the stock-out dates.")
            elif key == "supplier_delay" and primary and case == "unstructured_only":
                acts.append(f"Confirm with {primary['supplier_name']} whether the delay will materialise and secure "
                            f"allocation for {wh} now {cc()}.")
            elif key == "supplier_delay" and primary:
                acts.append(f"Expedite the delayed shipment with {primary['supplier_name']} and get a firm arrival date "
                            f"for {wh} {cc()}.")
            else:
                acts.append(f"Re-route stock to {region} from neighbouring regional warehouses and book a contingency "
                            "carrier until normal deliveries resume.")
            if backup:
                acts.append(f"Qualify {backup['supplier_name']} (lead time {backup['avg_lead_time_days']} days, reliability "
                            f"{backup['reliability_score']:.2f}) as a secondary source for the {region} region to reduce "
                            f"single-source risk {cc()}.")
            if st.get("reorder_point") and t.get("units_per_day_base") and st.get("days"):
                extra = int(round(t["units_per_day_base"] * st["days"], -1))
                acts.append(f"Raise the reorder point at {wh} from {st['reorder_point']:,} to "
                            f"{st['reorder_point'] + extra:,} units ({st['days']} extra days of cover) "
                            f"{self._c_inventory(ctx)}.")
        elif key in ("quality_issue", "quality_or_returns_issue"):
            acts.append(f"Hold the affected batches of {name} for {region} and run root-cause analysis with the "
                        "component vendor before releasing more stock.")
            acts.append("Proactively contact affected customers with a fast replacement path to protect satisfaction.")
            if t.get("returns_rate_base") is not None:
                acts.append(f"Track the {region} returns rate daily until it is back near the "
                            f"{t['returns_rate_base']:.2f}% baseline {self._c_sales(ctx)}.")
        elif key == "return_policy_change":
            extra = (t["returns_rate"] - t["returns_rate_base"]) / 100 * t["units"] if t else 0
            if t:
                acts.append(f"Quantify the cost of the pilot: about {extra:,.0f} extra returns this month "
                            f"{self._c_sales(ctx)}. Compare it with any lift in units and satisfaction at the quarterly review.")
            acts.append("Check how many returned units can be resold as new or refurbished; that decides whether the pilot pays off.")
            acts.append("If the net effect is negative, keep the longer window only for unopened units.")
        elif key == "promotion":
            if t:
                acts.append(f"Review the margin: units rose {pct(t['units_per_day_pct'])} but revenue only "
                            f"{pct(t['revenue_per_day_pct'])} per day {self._c_sales(ctx)}. Do not extend the discount "
                            "unless the volume clears inventory that would otherwise be written down.")
            acts.append("Plan for a post-promotion dip and check neighbouring regions for cross-border cannibalisation.")
            acts.append("Keep inventory cover high until the promotion ends to avoid stock-outs during peak demand.")
        elif key == "price_increase":
            if t and t.get("price_index_pct"):
                elasticity = t["units_per_day_pct"] / t["price_index_pct"]
                acts.append(f"Implied price elasticity is about {elasticity:.1f} {self._c_sales(ctx)}. "
                            "Check whether the margin gain outweighs the lost volume.")
            acts.append("Consider targeted trade-in or financing offers for price-sensitive segments instead of a list-price cut.")
        elif key in ("competitor_launch", "demand_decline"):
            if key == "demand_decline":
                acts.append(f"Collect field evidence before acting: no document explains the decline. Ask {region} store "
                            "managers about competitor activity, local pricing and foot traffic for the month.")
            acts.append(f"Respond in {region} with a targeted bundle or trade-in offer, rather than a national price cut.")
            acts.append("Brief sales associates on head-to-head comparisons and track weekly share in the region.")
        elif key in ("marketing_campaign", "demand_surge"):
            if key == "demand_surge":
                acts.append("Identify the source of the extra demand (campaigns, channel partners, competitor stock-outs); "
                            "no document explains it.")
            acts.append(f"Keep inventory cover at {wh} above the reorder point for the rest of the uplift.")
            acts.append("Measure campaign ROI against the baseline and plan for demand to normalise afterwards.")
        if case == "unstructured_only" and sql.get("available"):
            acts.append("The issue is not in the sales numbers yet: treat these as preventive actions and re-check next month.")
        elif case == "unstructured_only":
            acts.append(f"Start capturing sales and inventory data for {name} so the impact can be measured.")
        if case == "conflict":
            acts.insert(0, "Reconcile the document with the data before acting: they point to different causes.")
        return acts

    def _confidence(self, ctx) -> dict:
        case, rca, doc, sql, rag = ctx["case"], ctx["rca"], ctx["doc"], ctx["sql"], ctx["rag"]
        reasons, missing = [], None
        if sql.get("available"):
            if rca.get("is_anomaly"):
                reasons.append(f"Structured anomaly found (score {rca['anomaly_score']:.1f}, signature: "
                               f"{', '.join(rca['signature'])}).")
            else:
                reasons.append("Structured data checked: no statistically significant deviation.")
        else:
            missing = "structured"
            reasons.append("Structured data missing: " + (sql.get("reason") or ""))
        if rag.get("available"):
            if doc:
                reasons.append(f"Document found: {doc['filename']} ({doc['cause_label']}).")
            else:
                reasons.append("Documents searched: none describes an incident for this product/region/period.")
        else:
            missing = "both" if missing else "unstructured"
            reasons.append("Unstructured evidence missing: " + (rag.get("reason") or ""))

        if case == "full":
            score = 0.75 + 0.1 * min(1.0, rca["anomaly_score"] / 10) + 0.1 * min(1.0, doc["score"])
            reasons.append("Document cause is compatible with the structured signature.")
        elif case == "conflict":
            score = 0.5
            reasons.append("Document cause conflicts with the structured signature.")
        elif case == "structured_only":
            score = 0.45 + 0.2 * min(1.0, max(0.0, rca["anomaly_score"] - 3) / 7)
        elif case == "unstructured_only":
            score = 0.5 if sql.get("available") else 0.45
        elif case == "none":
            score = 0.85 if rag.get("available") else 0.75
        else:
            score = 0.1
        score = round(min(score, 0.95), 2)
        label = "high" if score >= 0.7 else "medium" if score >= 0.4 else "low"
        return {"score": score, "label": label, "reasons": reasons, "missing_source": missing}

    def _headline(self, ctx) -> str:
        case, cause, name, region, sql = ctx["case"], ctx["cause"], ctx["name"], ctx["region"], ctx["sql"]
        where = f"{name}, {region or 'all regions'}, {month_label(ctx['month'])}"
        change = f"{pct(sql['target']['units_per_day_pct'])} units/day vs. baseline" if sql.get("available") else ""
        if case == "full":
            return f"{where}: {change}, caused by {cause['label'].lower()} (confirmed by data and documents)."
        if case == "conflict":
            return f"{where}: {change}. Most likely {cause['label'].lower()}, but the documents disagree."
        if case == "structured_only":
            return f"{where}: {change}. Likely {cause['label'].lower()} (inferred from data only, no document found)."
        if case == "unstructured_only":
            tail = "not yet visible in sales" if sql.get("available") else "no sales data to verify impact"
            return f"{where}: documents report {cause['label'].lower()} ({tail})."
        if case == "none":
            return f"{where}: no anomaly and no related incident documents. Nothing unusual happened."
        return f"{where}: not enough data to investigate."

