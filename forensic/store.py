"""Read-only access to the generated data: SQL tables, the catalog document store, and the documents."""
from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass, field
from functools import lru_cache

import pandas as pd

from forensic.config import CATALOG_PATH, STRUCTURED_DIR, UNSTRUCTURED_DIR
from forensic.generate import ensure_data


@dataclass
class Document:
    path: str            # relative to data/unstructured, e.g. "IPHONE15/supplier_report_2026-03-02_north.txt"
    product_id: str
    doc_type: str
    date: str
    region: str
    title: str
    author: str
    text: str
    paragraphs: list = field(default_factory=list)

    @property
    def filename(self) -> str:
        return self.path.split("/")[-1]


class DataStore:
    def __init__(self) -> None:
        ensure_data()
        self._con = self._load_sql()
        self._lock = threading.Lock()
        self.catalog = {d["_id"]: d for d in json.loads(CATALOG_PATH.read_text(encoding="utf-8"))}
        self.documents = self._load_documents()
        self.sales = self.query("SELECT * FROM sales")
        self.months = sorted(self.sales["date"].str[:7].unique().tolist())

    @staticmethod
    def _load_sql() -> sqlite3.Connection:
        """In-memory SQLite built from the CSVs: nothing is written to disk (serverless-safe)."""
        con = sqlite3.connect(":memory:", check_same_thread=False)
        for name in ("products", "sales", "inventory", "suppliers"):
            pd.read_csv(STRUCTURED_DIR / f"{name}.csv").to_sql(name, con, index=False)
        con.execute("CREATE INDEX ix_sales ON sales(product_id, region, date)")
        con.execute("CREATE INDEX ix_inventory ON inventory(product_id, warehouse, date)")
        con.execute("PRAGMA query_only = ON")
        return con

    def query(self, sql: str, params: tuple = ()) -> pd.DataFrame:
        with self._lock:
            return pd.read_sql_query(sql, self._con, params=params)

    def _load_documents(self) -> list:
        docs = []
        for txt in sorted(UNSTRUCTURED_DIR.glob("*/*.txt")):
            sidecar = txt.with_suffix(".json")
            meta = json.loads(sidecar.read_text(encoding="utf-8")) if sidecar.exists() else {}
            raw = txt.read_text(encoding="utf-8")
            body = raw.split("\n\n", 1)[1] if "\n\n" in raw else raw
            docs.append(Document(
                path=f"{txt.parent.name}/{txt.name}", product_id=meta.get("product_id", txt.parent.name),
                doc_type=meta.get("doc_type", "unknown"), date=meta.get("date", ""), region=meta.get("region", "ALL"),
                title=meta.get("title", txt.stem), author=meta.get("author", ""), text=raw,
                paragraphs=[p.strip() for p in body.split("\n\n") if p.strip()],
            ))
        return docs

    def has_sales(self, product_id: str) -> bool:
        return bool((self.sales["product_id"] == product_id).any())

    def has_documents(self, product_id: str) -> bool:
        return any(d.product_id == product_id for d in self.documents)


@lru_cache(maxsize=1)
def get_store() -> DataStore:
    return DataStore()
