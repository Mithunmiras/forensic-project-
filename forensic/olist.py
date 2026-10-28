"""Import the real Olist Brazilian E-Commerce dataset into RetailIQ's schema.

Source: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce (CC BY-NC-SA 4.0, Olist).
Run:    python -m forensic import-olist --src ~/Downloads/archive

Mapping (everything below is computed from the real data; nothing is invented):
  product   -> one of the 8 largest product categories
  region    -> Brazil's 5 IBGE macro-regions (customer state)
  sales     -> items purchased per day, revenue = item prices (BRL)
  returns   -> items in orders that received a 1-2 star review (Olist has no returns data)
  late      -> items delivered after the date promised to the customer (supply-side signal)
  documents -> one review digest per category / region / month: complaint statistics mined from the
               real review text, plus real customer comments quoted in the original Portuguese
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from forensic.config import DATA_DIR

OUT = DATA_DIR / "olist"
FIRST_MONTH, LAST_MONTH = "2017-03", "2018-08"   # before/after this Olist is too small to judge (launch months)
TOP_CATEGORIES = 8
WINDOW = 3                                        # months either side used as the baseline for digests

MACRO_REGION = {
    **dict.fromkeys(["AC", "AP", "AM", "PA", "RO", "RR", "TO"], "North"),
    **dict.fromkeys(["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"], "Northeast"),
    **dict.fromkeys(["DF", "GO", "MT", "MS"], "Center-West"),
    **dict.fromkeys(["ES", "MG", "RJ", "SP"], "Southeast"),
    **dict.fromkeys(["PR", "RS", "SC"], "South"),
}
REGIONS = ["North", "Northeast", "Center-West", "Southeast", "South"]

PRETTY = {
    "bed_bath_table": ("Bed, bath & table", ["bed bath", "bed", "bath", "bedding", "towels"]),
    "health_beauty": ("Health & beauty", ["health and beauty", "health", "beauty", "cosmetics"]),
    "sports_leisure": ("Sports & leisure", ["sports and leisure", "sports", "sport", "leisure"]),
    "furniture_decor": ("Furniture & decor", ["furniture and decor", "furniture", "decor"]),
    "computers_accessories": ("Computer accessories", ["computer accessories", "computers", "computer", "pc"]),
    "housewares": ("Housewares", ["housewares", "household", "kitchen"]),
    "watches_gifts": ("Watches & gifts", ["watches and gifts", "watches", "watch", "gifts"]),
    "telephony": ("Telephony", ["telephony", "phones", "phone", "mobile"]),
    "garden_tools": ("Garden tools", ["garden tools", "garden"]),
    "auto": ("Auto", ["auto", "car", "automotive"]),
}

# Praise that mentions the deadline ("arrived on time") - never quoted as a complaint.
POSITIVE_RX = re.compile(r"dentro do prazo|antes do prazo|no prazo certo|chegou r[aá]pido|super r[aá]pid", re.I)
# Complaint themes, matched on the Portuguese review title + message of 1-2 star reviews.
DELIVERY_RX = re.compile(r"atras|n[aã]o (?:recebi|chegou|foi entregue|entreg)|ainda n[aã]o|prazo|demor|cad[eê] (?:o|meu)", re.I)
QUALITY_RX = re.compile(r"defeito|quebrad|danific|errad|diferente d|falsific|n[aã]o funciona|parou de funcionar|"
                        r"qualidade (?:ruim|p[eé]ssima|baixa)|veio (?:outro|sem)", re.I)


def _read(src: Path, name: str, **kw) -> pd.DataFrame:
    return pd.read_csv(src / f"olist_{name}_dataset.csv", **kw)


def _load(src: Path):
    orders = _read(src, "orders", parse_dates=["order_purchase_timestamp", "order_delivered_customer_date",
                                                "order_estimated_delivery_date"])
    items = _read(src, "order_items")
    products = _read(src, "products", usecols=["product_id", "product_category_name"])
    customers = _read(src, "customers", usecols=["customer_id", "customer_state"])
    reviews = _read(src, "order_reviews")
    names = pd.read_csv(src / "product_category_name_translation.csv")

    orders["month"] = orders["order_purchase_timestamp"].dt.strftime("%Y-%m")
    orders = orders[(orders["month"] >= FIRST_MONTH) & (orders["month"] <= LAST_MONTH)].copy()
    orders["date"] = orders["order_purchase_timestamp"].dt.strftime("%Y-%m-%d")
    orders = orders.merge(customers, on="customer_id")
    orders["region"] = orders["customer_state"].map(MACRO_REGION)
    delivered = orders["order_delivered_customer_date"].notna()
    orders["delivered"] = delivered
    orders["late"] = delivered & (orders["order_delivered_customer_date"].dt.normalize()
                                  > orders["order_estimated_delivery_date"])
    # One review per order (keep the latest if duplicated).
    rev = reviews.sort_values("review_creation_date").drop_duplicates("order_id", keep="last")
    orders = orders.merge(rev[["order_id", "review_score", "review_comment_title", "review_comment_message"]],
                          on="order_id", how="left")

    items = items.merge(products, on="product_id", how="left").merge(names, on="product_category_name", how="left")
    items = items.rename(columns={"product_category_name_english": "category"}).dropna(subset=["category"])
    top = items[items["order_id"].isin(orders["order_id"])]["category"].value_counts().head(TOP_CATEGORIES).index
    items = items[items["category"].isin(top)]
    lines = items.merge(orders, on="order_id")
    return orders, lines, list(top)


def _sales(lines: pd.DataFrame, categories: list) -> pd.DataFrame:
    lines = lines.assign(low_review=(lines["review_score"] <= 2).astype(int),
                         late_i=lines["late"].astype(int), delivered_i=lines["delivered"].astype(int))
    daily = lines.groupby(["date", "category", "region"]).agg(
        units_sold=("order_item_id", "size"), revenue=("price", "sum"), returns=("low_review", "sum"),
        late_items=("late_i", "sum"), delivered_items=("delivered_i", "sum")).reset_index()
    grid = pd.MultiIndex.from_product([
        pd.date_range(f"{FIRST_MONTH}-01", pd.Period(LAST_MONTH).end_time.normalize()).strftime("%Y-%m-%d"),
        categories, REGIONS], names=["date", "category", "region"]).to_frame(index=False)
    daily = grid.merge(daily, how="left").fillna(0)
    for col in ("units_sold", "returns", "late_items", "delivered_items"):
        daily[col] = daily[col].astype(int)
    daily["revenue"] = daily["revenue"].round(2)
    daily["discount_pct"] = 0.0          # Olist has no discount data
    daily["product_id"] = daily["category"].str.upper()
    return daily[["date", "product_id", "region", "units_sold", "revenue", "discount_pct", "returns",
                  "late_items", "delivered_items"]]


def _clip(text: str, n: int = 170) -> str:
    text = re.sub(r"\s+", " ", str(text)).strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _digests(lines: pd.DataFrame, categories: list) -> int:
    """One review digest per category/region/month, built from the real review text."""
    rv = lines.dropna(subset=["review_score"]).drop_duplicates(["order_id", "category"]).copy()
    rv["text"] = (rv["review_comment_title"].fillna("") + " " + rv["review_comment_message"].fillna("")).str.strip()
    low = rv["review_score"] <= 2
    rv["delivery"] = low & rv["text"].str.contains(DELIVERY_RX)
    rv["quality"] = low & rv["text"].str.contains(QUALITY_RX)
    cells = rv.groupby(["category", "region", "month"]).agg(
        n=("review_score", "size"), score=("review_score", "mean"),
        delivery=("delivery", "sum"), quality=("quality", "sum")).reset_index()
    cells["delivery_share"] = cells["delivery"] / cells["n"] * 100
    cells["quality_share"] = cells["quality"] / cells["n"] * 100

    months = sorted(cells["month"].unique())
    count = 0
    for (cat, region), g in cells.groupby(["category", "region"]):
        g = g.set_index("month")
        for month in g.index:
            row = g.loc[month]
            if row["n"] < 10:
                continue  # too few reviews to say anything
            idx = months.index(month)
            near = [m for m in months[max(0, idx - WINDOW): idx + WINDOW + 1] if m != month and m in g.index]
            base = g.loc[near] if near else g.drop(index=month)
            themes = []
            for theme in ("delivery", "quality"):
                share, typical = row[f"{theme}_share"], float(np.median(base[f"{theme}_share"])) if len(base) else 0.0
                if row[theme] >= 5 and share >= 2 * typical and share - typical >= 5:
                    themes.append((share - typical, theme, share, typical))
            name = PRETTY.get(cat, (cat.replace("_", " ").title(), []))[0]
            title = f"Customer review digest: {name}, {region}, {month}"
            score_base = float(np.mean(base["score"])) if len(base) else row["score"]
            subset = rv[(rv["category"] == cat) & (rv["region"] == region) & (rv["month"] == month)]
            if themes:
                _, theme, share, typical = max(themes)
                n = int(row[theme])
                if theme == "delivery":
                    lead = (f"Late deliveries dominate customer complaints this month: {n} of {int(row['n'])} reviews "
                            f"({share:.0f}%) report a delivery delay or an order not received, versus {typical:.0f}% in "
                            "the surrounding months.")
                else:
                    lead = (f"Product defects dominate customer complaints this month: {n} of {int(row['n'])} reviews "
                            f"({share:.0f}%) report a defect, a damaged item or a wrong item, versus {typical:.0f}% in the "
                            "surrounding months.")
                ok = subset[theme] & (subset["text"].str.len() > 25) & ~subset["text"].str.contains(POSITIVE_RX)
                quotes = subset[ok]["text"].head(4).map(_clip)
                paragraphs = [lead,
                              "Representative customer comments (original Portuguese): "
                              + " / ".join(f"“{q}”" for q in quotes),
                              f"Average review score {row['score']:.2f} versus {score_base:.2f} in the surrounding months."]
            else:
                paragraphs = [
                    f"Complaint mix is in line with the surrounding months: {row['delivery_share']:.0f}% of "
                    f"{int(row['n'])} reviews mention delivery problems and {row['quality_share']:.0f}% mention product "
                    "problems. No significant change.",
                    f"Average review score {row['score']:.2f} versus {score_base:.2f} in the surrounding months.",
                ]
            meta = {"product_id": cat.upper(), "doc_type": "review_digest", "date": f"{month}-01", "region": region,
                    "title": title, "author": "Generated from real Olist customer reviews"}
            folder = OUT / "unstructured" / cat.upper()
            folder.mkdir(parents=True, exist_ok=True)
            fname = f"review_digest_{month}_{region.lower().replace('-', '_')}"
            header = [f"Title: {title}", "Document type: review_digest", f"Product: {name} ({cat.upper()})",
                      f"Region: {region}", f"Date: {month}-01", f"Author: {meta['author']}"]
            (folder / f"{fname}.txt").write_text("\n".join(header) + "\n\n" + "\n\n".join(paragraphs) + "\n",
                                                 encoding="utf-8")
            (folder / f"{fname}.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
            count += 1
    return count


def import_olist(src: Path) -> dict:
    src = Path(src).expanduser()
    if not (src / "olist_orders_dataset.csv").exists():
        raise SystemExit(f"Olist CSV files not found in {src}")
    orders, lines, categories = _load(src)
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "structured").mkdir(parents=True)

    sales = _sales(lines, categories)
    sales.to_csv(OUT / "structured" / "sales.csv", index=False)
    first_sale = lines.groupby("category")["date"].min()
    median_price = lines.groupby("category")["price"].median()
    products, catalog = [], []
    for cat in categories:
        name, aliases = PRETTY.get(cat, (cat.replace("_", " ").title(), [cat.replace("_", " ")]))
        pid = cat.upper()
        products.append({"product_id": pid, "product_name": name, "category": cat, "launch_date": first_sale[cat],
                         "unit_price": round(float(median_price[cat]), 2), "supplier_id": ""})
        catalog.append({"_id": pid, "product_name": name, "category": cat, "launch_date": first_sale[cat],
                        "unit_price": round(float(median_price[cat]), 2), "aliases": aliases,
                        "suppliers": {"primary": [], "backup": []}, "warehouses": {}})
    pd.DataFrame(products).to_csv(OUT / "structured" / "products.csv", index=False)
    (OUT / "structured" / "catalog.json").write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    docs = _digests(lines, categories)
    (OUT / "SOURCE.md").write_text(
        "Derived from the Olist Brazilian E-Commerce Public Dataset (Kaggle: olistbr/brazilian-ecommerce),\n"
        "licensed CC BY-NC-SA 4.0 by Olist. Regenerate with `python -m forensic import-olist --src <folder>`.\n",
        encoding="utf-8")
    return {"orders": int(len(orders)), "item_lines_top_categories": int(len(lines)), "categories": categories,
            "daily_rows": int(len(sales)), "review_digests": docs}
