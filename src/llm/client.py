"""LLM access (Ollama, local) with graceful degradation.

The whole application works without an LLM. ``status()`` reports honestly
whether the server is reachable *and* the configured model is actually pulled.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Protocol

import httpx

from src.config import Settings, get_settings

log = logging.getLogger("retailiq.llm")


class LLMUnavailable(RuntimeError):
    """The LLM could not be used (not configured, not reachable, model missing, or it failed)."""


class LLM(Protocol):
    provider: str
    model: str | None

    def status(self, *, force: bool = False) -> dict[str, Any]: ...
    @property
    def available(self) -> bool: ...
    def chat(self, messages: list[dict[str, str]], *, json_mode: bool = False, temperature: float = 0.0) -> str: ...
    def embed(self, texts: list[str], model: str) -> list[list[float]]: ...


def model_matches(installed: str, wanted: str) -> bool:
    """'llama3.2' matches any installed tag of that model; 'llama3.2:3b' must match exactly."""
    if ":" in wanted:
        return installed == wanted
    return installed == wanted or installed.split(":")[0] == wanted


class NullLLM:
    """Used when LLM_PROVIDER=none."""

    provider = "none"
    model = None

    def status(self, *, force: bool = False) -> dict[str, Any]:
        return {"provider": "none", "available": False, "reachable": False, "model": None, "model_present": False,
                "error": "LLM disabled (LLM_PROVIDER=none).", "hint": None}

    @property
    def available(self) -> bool:
        return False

    def chat(self, messages, *, json_mode: bool = False, temperature: float = 0.0) -> str:
        raise LLMUnavailable("LLM disabled (LLM_PROVIDER=none).")

    def embed(self, texts, model):
        raise LLMUnavailable("LLM disabled (LLM_PROVIDER=none).")


class OllamaClient:
    provider = "ollama"
    _STATUS_TTL_S = 15.0

    def __init__(self, base_url: str, model: str, timeout_s: float = 90.0, transport: httpx.BaseTransport | None = None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s
        self._http = httpx.Client(base_url=self.base_url, timeout=httpx.Timeout(timeout_s, connect=3.0), transport=transport)
        self._cache: tuple[float, dict[str, Any]] | None = None
        self._lock = threading.Lock()

    # ---- status --------------------------------------------------------
    def status(self, *, force: bool = False) -> dict[str, Any]:
        with self._lock:
            if not force and self._cache and time.monotonic() - self._cache[0] < self._STATUS_TTL_S:
                return self._cache[1]
        info: dict[str, Any] = {
            "provider": "ollama", "base_url": self.base_url, "model": self.model, "reachable": False,
            "model_present": False, "available": False, "installed_models": [], "error": None, "hint": None,
        }
        try:
            resp = self._http.get("/api/tags", timeout=httpx.Timeout(3.0))
            resp.raise_for_status()
            names = [m.get("name", "") for m in resp.json().get("models", [])]
            info["reachable"] = True
            info["installed_models"] = names
            wanted = self.model
            info["model_present"] = any(model_matches(n, wanted) for n in names)
            info["available"] = info["model_present"]
            if not info["model_present"]:
                info["error"] = f"Ollama is running but model '{self.model}' is not installed."
                info["hint"] = f"Run: ollama pull {self.model}"
        except Exception as exc:  # noqa: BLE001
            info["error"] = f"Ollama not reachable at {self.base_url} ({exc.__class__.__name__})."
            info["hint"] = "Install Ollama from https://ollama.com, start it, then run: ollama pull " + self.model
        with self._lock:
            self._cache = (time.monotonic(), info)
        return info

    @property
    def available(self) -> bool:
        return bool(self.status()["available"])

    # ---- calls ---------------------------------------------------------
    def chat(self, messages: list[dict[str, str]], *, json_mode: bool = False, temperature: float = 0.0) -> str:
        if not self.available:
            raise LLMUnavailable(self.status().get("error") or "LLM unavailable.")
        payload: dict[str, Any] = {
            "model": self.model, "messages": messages, "stream": False, "options": {"temperature": temperature},
        }
        if json_mode:
            payload["format"] = "json"
        try:
            resp = self._http.post("/api/chat", json=payload)
            resp.raise_for_status()
            content = resp.json()["message"]["content"]
        except Exception as exc:  # noqa: BLE001
            self._cache = None  # force a fresh status check next time
            raise LLMUnavailable(f"LLM request failed: {exc.__class__.__name__}") from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMUnavailable("LLM returned an empty response.")
        return content

    def embed(self, texts: list[str], model: str) -> list[list[float]]:
        try:
            resp = self._http.post("/api/embed", json={"model": model, "input": texts})
            resp.raise_for_status()
            vectors = resp.json()["embeddings"]
        except Exception as exc:  # noqa: BLE001
            raise LLMUnavailable(f"Embedding request failed: {exc.__class__.__name__}") from exc
        if len(vectors) != len(texts):
            raise LLMUnavailable("Embedding response had an unexpected length.")
        return vectors


def build_llm(settings: Settings | None = None, transport: httpx.BaseTransport | None = None) -> LLM:
    settings = settings or get_settings()
    if settings.llm_provider.lower() == "ollama":
        return OllamaClient(settings.ollama_base_url, settings.ollama_model, settings.llm_timeout_s, transport=transport)
    return NullLLM()
