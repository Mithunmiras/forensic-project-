"""Scenario-first synthetic data generator.

1. Normal months get baseline demand + weekday pattern + noise only (the control group).
2. Each scenario in scenarios.py adds its structured signature (units, stock-outs, discount,
   price, returns) to exactly one product / region / month ...
3. ... and writes the document a person would have written about it, with a JSON sidecar.
4. Routine documents (policies, quarterly QC, supplier status, feedback summaries) are added
   so that the RAG agent has to ignore irrelevant text rather than retrieve everything.

Output: data/structured/*.csv, data/structured/catalog.json, data/forensic.sqlite and
data/unstructured/<PRODUCT>/*.txt (+ .json). Deterministic for a given seed.
"""
from __future__ import annotations

import json
import shutil
import sqlite3

import numpy as np
import pandas as pd

from forensic.catalog import PRODUCTS, REGION_WEIGHT, REGIONS, SUPPLIERS, WAREHOUSE
from forensic.config import (CATALOG_PATH, DB_PATH, END_DATE, SEED, START_DATE, STRUCTURED_DIR,
                             UNSTRUCTURED_DIR)
from forensic.scenarios import SCENARIOS

WEEKEND_FACTOR, WEEKDAY_FACTOR = 1.15, 0.94   # averages to 1.0 over a week
BASE_DISCOUNT = 5.0


def _sales_and_inventory(rng: np.random.Generator):
    effects = {(s["product_id"], s["region"], s["month"]): s["structured_effect"]
               for s in SCENARIOS if s.get("structured_effect")}
    dates = pd.date_range(START_DATE, END_DATE, freq="D")
    months = dates.strftime("%Y-%m")
    sales, inventory = [], []
    for p in PRODUCTS:
        if not p["base_daily_units"]:
            continue
        for region in REGIONS:
            base = p["base_daily_units"] * REGION_WEIGHT[region]
            warehouse = WAREHOUSE[region]
            reorder_point = int(round(base * 5, -1))
            phase0 = int(rng.integers(0, 10))
            for month in sorted(set(months)):
                mdates = dates[months == month]
                eff = effects.get((p["product_id"], region, month)) or {}
                pct = eff.get("units_sold_pct_change", 0) / 100
                out_days = set()
                if eff.get("stockout_days"):
                    start = eff["stockout_start_day"]
                    out_days = set(range(start, start + eff["stockout_days"]))
                # A stock-out concentrates the whole monthly loss into the days without stock
                # (some orders are still fulfilled from other warehouses, so not quite zero).
                m_out = max(0.0, 1 + pct * len(mdates) / len(out_days)) if out_days else 1.0
                m_in = 1.0 if out_days else 1 + pct
                discount = BASE_DISCOUNT + eff.get("discount_pct_change", 0)
                price = p["unit_price"] * (1 + eff.get("price_pct_change", 0) / 100)
                returns_mult = 1 + eff.get("returns_pct_change", 0) / 100
                for d in mdates:
                    wf = WEEKEND_FACTOR if d.weekday() >= 5 else WEEKDAY_FACTOR
                    mult = m_out if d.day in out_days else m_in
                    units = max(0, int(round(base * wf * (1 + rng.normal(0, 0.05)) * mult)))
                    rate = min(0.5, rng.uniform(0.009, 0.015) * returns_mult)
                    sales.append({
                        "date": d.strftime("%Y-%m-%d"), "product_id": p["product_id"], "region": region,
                        "units_sold": units, "revenue": round(units * price * (1 - discount / 100), 2),
                        "discount_pct": discount, "returns": int(rng.binomial(units, rate)),
                    })
                    # Sawtooth stock between ~5 and ~14 days of cover; runs down before a stock-out.
                    phase = (d.dayofyear + phase0) % 10
                    stock = base * (4 + 10 * (1 - phase / 10)) * rng.uniform(0.97, 1.03)
                    if d.day in out_days:
                        stock = 0
                    elif out_days and d.day in (min(out_days) - 2, min(out_days) - 1):
                        stock = base * (1.5 if d.day == min(out_days) - 2 else 0.6)
                    inventory.append({
                        "date": d.strftime("%Y-%m-%d"), "product_id": p["product_id"], "warehouse": warehouse,
                        "stock_level": int(stock), "reorder_point": reorder_point,
                    })
    return pd.DataFrame(sales), pd.DataFrame(inventory)


def _write_doc(product_id: str, name: str, meta: dict, paragraphs: list) -> None:
    folder = UNSTRUCTURED_DIR / product_id
    folder.mkdir(parents=True, exist_ok=True)
    product = next(p for p in PRODUCTS if p["product_id"] == product_id)
    header = [
        f"Title: {meta['title']}",
        f"Document type: {meta['doc_type']}",
        f"Product: {product['product_name']} ({product_id})",
        f"Region: {meta['region']}",
        f"Date: {meta['date']}",
        f"Author: {meta['author']}",
    ]
    (folder / f"{name}.txt").write_text("\n".join(header) + "\n\n" + "\n\n".join(paragraphs) + "\n", encoding="utf-8")
    sidecar = {"product_id": product_id, **meta}
    (folder / f"{name}.json").write_text(json.dumps(sidecar, indent=2) + "\n", encoding="utf-8")


def _routine_docs(rng: np.random.Generator) -> int:
    count = 0
    themes = ["battery life", "setup experience", "accessory compatibility", "delivery speed", "build quality",
              "software updates", "value for money"]
    for p in PRODUCTS:
        pid, name = p["product_id"], p["product_name"]
        if pid == "HOMEPOD":
            continue  # HomePod deliberately has no unstructured documents
        supplier = next(s for s in SUPPLIERS if s["supplier_id"] == p["supplier_id"])
        launched = p["launch_date"]

        def add(fname, doc_type, date, title, author, paragraphs):
            nonlocal count
            if date < launched and doc_type not in ("policy",):
                return
            _write_doc(pid, fname, {"doc_type": doc_type, "date": date, "region": "ALL", "title": title,
                                    "author": author}, paragraphs)
            count += 1

        add("policy_warranty", "policy", "2025-09-01", f"Warranty Policy: {name}", "Legal & Customer Experience", [
            f"{name} is covered by a one-year limited warranty against manufacturing defects from the date of purchase.",
            "The warranty does not cover accidental damage, unauthorised repairs or normal wear. Extended cover is "
            "available through the protection plan.",
            "Warranty claims are handled in store or through the support line and require proof of purchase.",
        ])
        add("policy_returns", "policy", "2025-09-01", f"Returns Policy: {name}", "Legal & Customer Experience", [
            f"Unopened {name} units may be returned within the standard 14-day return window for a refund to the "
            "original payment method.",
            "Opened units may be returned within the same period if they are complete and undamaged. A restocking "
            "fee does not apply.",
            "This policy applies uniformly to all regions unless a regional policy update states otherwise.",
        ])
        for date in ("2025-11-15", "2026-02-15", "2026-05-15"):
            base = round(float(rng.uniform(0.2, 0.4)), 1)
            add(f"quality_summary_{date}", "quality_summary", date, f"Quarterly Quality Summary: {name}",
                "Quality Engineering", [
                    f"Incoming inspection and field data for {name} across all regions show a defect rate of "
                    f"{base}% against the {base}% baseline, within normal tolerance.",
                    "No anomalies were found in the batches reviewed this quarter; no action required.",
                ])
        for date in ("2025-10-01", "2026-01-01", "2026-04-01"):
            add(f"supplier_status_{date}", "supplier_status", date, f"Supplier Status: {supplier['supplier_name']}",
                f"{supplier['supplier_name']} - Account Management", [
                    f"Shipments of {name} to all regional distribution centres are proceeding as planned. Average lead "
                    f"time this period was {supplier['avg_lead_time_days']} days, on schedule against contract.",
                    "No significant risks to report for the coming quarter.",
                ])
        for date in ("2025-12-28", "2026-03-25", "2026-06-25"):
            picked = rng.choice(themes, size=2, replace=False)
            add(f"customer_feedback_{date}", "customer_feedback", date, f"Customer Feedback Summary: {name}",
                "Customer Support Analytics", [
                    f"Sentiment for {name} across all regions remained stable at "
                    f"{round(float(rng.uniform(4.3, 4.7)), 1)} out of 5.",
                    f"The most common themes were {picked[0]} and {picked[1]}. There was no significant change in "
                    "complaint volumes versus the previous quarter.",
                ])
    return count


def _catalog_documents() -> list:
    """Semi-structured product documents with nested supplier data - the 'NoSQL' side."""
    docs = []
    for p in PRODUCTS:
        suppliers = [dict(s, product_ids=s["product_ids"].split(";")) for s in SUPPLIERS
                     if p["product_id"] in s["product_ids"].split(";")]
        docs.append({
            "_id": p["product_id"],
            "product_name": p["product_name"], "category": p["category"], "launch_date": p["launch_date"],
            "unit_price": p["unit_price"], "aliases": p["aliases"],
            "suppliers": {"primary": [s for s in suppliers if s["role"] == "primary"],
                          "backup": [s for s in suppliers if s["role"] == "backup"]},
            "warehouses": dict(WAREHOUSE),
        })
    return docs


def generate(seed: int = SEED) -> dict:
    rng = np.random.default_rng(seed)
    for folder in (STRUCTURED_DIR, UNSTRUCTURED_DIR):
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True)

    products = pd.DataFrame([{k: p[k] for k in ("product_id", "product_name", "category", "launch_date",
                                                 "unit_price", "supplier_id")} for p in PRODUCTS])
    suppliers = pd.DataFrame(SUPPLIERS)
    sales, inventory = _sales_and_inventory(rng)
    tables = {"products": products, "sales": sales, "inventory": inventory, "suppliers": suppliers}
    for name, df in tables.items():
        df.to_csv(STRUCTURED_DIR / f"{name}.csv", index=False)
    CATALOG_PATH.write_text(json.dumps(_catalog_documents(), indent=2) + "\n", encoding="utf-8")

    if DB_PATH.exists():
        DB_PATH.unlink()
    with sqlite3.connect(DB_PATH) as con:
        for name, df in tables.items():
            df.to_sql(name, con, index=False)
        con.execute("CREATE INDEX ix_sales ON sales(product_id, region, date)")
        con.execute("CREATE INDEX ix_inventory ON inventory(product_id, warehouse, date)")

    incident_docs = 0
    for sc in SCENARIOS:
        doc = sc.get("doc")
        if not doc:
            continue
        meta = {k: doc[k] for k in ("doc_type", "date", "title", "author")}
        meta["region"] = sc["region"]
        _write_doc(sc["product_id"], f"{doc['doc_type']}_{doc['date']}_{sc['region'].lower()}", meta, doc["paragraphs"])
        incident_docs += 1
    routine = _routine_docs(rng)
    return {"sales_rows": len(sales), "inventory_rows": len(inventory), "products": len(products),
            "suppliers": len(suppliers), "incident_documents": incident_docs, "routine_documents": routine}


def ensure_data() -> None:
    if not (DB_PATH.exists() and CATALOG_PATH.exists() and UNSTRUCTURED_DIR.exists()):
        generate()
