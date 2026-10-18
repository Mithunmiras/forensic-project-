"""Test doubles shared across the suite."""
from __future__ import annotations

from typing import Any, Callable

from src.llm.client import LLMUnavailable


class FakeLLM:
    """Scriptable LLM. ``replies`` items are strings or callables(messages) -> str."""

    provider = "fake"
    model = "fake-model"

    def __init__(self, replies: list[str | Callable[[list[dict[str, str]]], str]] | None = None, available: bool = True,
                 fail: bool = False) -> None:
        self.replies = list(replies or [])
        self._available = available
        self.fail = fail
        self.calls: list[list[dict[str, str]]] = []

    def status(self, *, force: bool = False) -> dict[str, Any]:
        return {"provider": "fake", "available": self._available, "reachable": self._available, "model": self.model,
                "model_present": self._available, "error": None if self._available else "fake LLM unavailable", "hint": None}

    @property
    def available(self) -> bool:
        return self._available

    def chat(self, messages, *, json_mode: bool = False, temperature: float = 0.0) -> str:
        self.calls.append(messages)
        if not self._available or self.fail:
            raise LLMUnavailable("fake LLM unavailable")
        if not self.replies:
            raise LLMUnavailable("no scripted reply")
        reply = self.replies.pop(0)
        return reply(messages) if callable(reply) else reply

    def embed(self, texts, model):
        raise LLMUnavailable("fake LLM has no embeddings")
