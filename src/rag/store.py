"""Retrieval backends: ChromaDB (semantic) and TF-IDF (lexical fallback)."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np

from src.rag.documents import Chunk
from src.rag.embeddings import Embedder

log = logging.getLogger("retailiq.rag.store")
COLLECTION = "retailiq_kb"


@dataclass
class Hit:
    chunk_id: str
    source: str
    heading: str
    text: str
    score: float  # similarity in [0, 1]; NOT comparable between backends


class ChromaBackend:
    """Persistent semantic index. Embeddings are computed by our ``Embedder``."""

    mode = "semantic"

    def __init__(self, base_path: Path, embedder: Embedder) -> None:
        import chromadb

        self.path = base_path / "chroma"
        self.path.mkdir(parents=True, exist_ok=True)
        self.embedder = embedder
        self._client = chromadb.PersistentClient(path=str(self.path))

    def _collection(self, create: bool = False):
        if create:
            try:
                self._client.delete_collection(COLLECTION)
            except Exception:  # noqa: BLE001 - did not exist
                pass
            return self._client.create_collection(
                COLLECTION, metadata={"hnsw:space": "cosine", "embedder": self.embedder.name}
            )
        return self._client.get_collection(COLLECTION)

    def rebuild(self, chunks: list[Chunk]) -> None:
        col = self._collection(create=True)
        batch = 48
        for i in range(0, len(chunks), batch):
            part = chunks[i : i + batch]
            texts = [f"{c.heading}\n{c.text}" for c in part]
            col.add(
                ids=[c.id for c in part],
                documents=[c.text for c in part],
                embeddings=self.embedder.embed(texts),
                metadatas=[{"source": c.source, "heading": c.heading, "index": c.index} for c in part],
            )

    def stored_embedder(self) -> str | None:
        try:
            return (self._collection().metadata or {}).get("embedder")
        except Exception:  # noqa: BLE001
            return None

    def count(self) -> int:
        try:
            return int(self._collection().count())
        except Exception:  # noqa: BLE001
            return 0

    def query(self, text: str, k: int) -> list[Hit]:
        col = self._collection()
        res = col.query(query_embeddings=self.embedder.embed([text]), n_results=min(k, max(col.count(), 1)))
        hits = []
        for cid, doc, meta, dist in zip(res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]):
            hits.append(Hit(cid, meta["source"], meta["heading"], doc, round(max(0.0, 1.0 - float(dist)), 4)))
        return hits

    def close(self) -> None:
        """Release the sqlite handles (needed on Windows) and Chroma's per-path cache so
        a new client for the same path can be created afterwards."""
        try:
            from chromadb.api.shared_system_client import SharedSystemClient

            self._client._system.stop()
            SharedSystemClient.clear_system_cache()
        except Exception:  # noqa: BLE001
            pass


class LexicalBackend:
    """TF-IDF keyword retrieval. Honest fallback: it matches words, not meaning."""

    mode = "lexical_fallback"
    MIN_SCORE = 0.08

    def __init__(self, base_path: Path) -> None:
        self.file = base_path / "lexical.joblib"
        self._data: dict | None = None

    def load(self) -> bool:
        if not self.file.exists():
            return False
        try:
            self._data = joblib.load(self.file)
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not load lexical index: %s", exc.__class__.__name__)
            self._data = None
            return False

    def rebuild(self, chunks: list[Chunk]) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer

        vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english", min_df=1)
        matrix = vec.fit_transform([f"{c.heading} {c.text}" for c in chunks])
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self._data = {
            "vectorizer": vec,
            "matrix": matrix,
            "chunks": [(c.id, c.source, c.heading, c.text) for c in chunks],
        }
        joblib.dump(self._data, self.file, compress=3)

    def count(self) -> int:
        return len(self._data["chunks"]) if self._data else 0

    def query(self, text: str, k: int) -> list[Hit]:
        if not self._data:
            return []
        q = self._data["vectorizer"].transform([text])
        scores = (self._data["matrix"] @ q.T).toarray().ravel()
        order = np.argsort(-scores)[:k]
        out = []
        for i in order:
            cid, source, heading, body = self._data["chunks"][int(i)]
            out.append(Hit(cid, source, heading, body, round(float(scores[i]), 4)))
        return out

