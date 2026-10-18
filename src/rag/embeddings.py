"""Embedding providers for semantic retrieval.

Providers (``EMBEDDING_PROVIDER``): ``chroma`` (local ONNX MiniLM, no server needed),
``ollama`` (an embedding model served by Ollama), ``lexical`` (no embeddings: TF-IDF
keyword retrieval only) or ``auto`` (try chroma, then ollama, else lexical).
"""
from __future__ import annotations

import logging
from typing import Protocol

from src.config import Settings
from src.llm.client import LLM, LLMUnavailable

log = logging.getLogger("retailiq.rag.embeddings")


class Embedder(Protocol):
    name: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class ChromaOnnxEmbedder:
    """all-MiniLM-L6-v2 via ONNX Runtime (downloaded once to the user cache)."""

    name = "chroma-onnx-all-MiniLM-L6-v2"

    def __init__(self) -> None:
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

        self._fn = DefaultEmbeddingFunction()
        self._fn(["warm-up"])  # forces model download/load now so failures surface here

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [list(map(float, v)) for v in self._fn(texts)]


class OllamaEmbedder:
    def __init__(self, llm: LLM, model: str) -> None:
        self._llm, self._model = llm, model
        self.name = f"ollama:{model}"
        self._llm.embed(["warm-up"], model)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._llm.embed(texts, self._model)


def select_embedder(settings: Settings, llm: LLM) -> tuple[Embedder | None, str]:
    """Return (embedder or None, human-readable reason/status)."""
    provider = settings.embedding_provider.lower()
    if provider == "lexical":
        return None, "EMBEDDING_PROVIDER=lexical: semantic embeddings disabled."
    errors: list[str] = []
    if provider in ("auto", "chroma"):
        try:
            return ChromaOnnxEmbedder(), "ok"
        except Exception as exc:  # noqa: BLE001 - offline, missing deps, ...
            errors.append(f"chroma-onnx unavailable ({exc.__class__.__name__}: {str(exc)[:120]})")
    if provider in ("auto", "ollama"):
        if llm.available:
            try:
                return OllamaEmbedder(llm, settings.embedding_model), "ok"
            except (LLMUnavailable, Exception) as exc:  # noqa: BLE001
                errors.append(f"ollama embeddings unavailable ({exc.__class__.__name__}); try: ollama pull {settings.embedding_model}")
        else:
            errors.append("ollama unavailable")
    return None, "; ".join(errors) or "no embedding provider available"
