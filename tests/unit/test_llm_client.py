import json

import httpx
import pytest

from src.config import Settings
from src.llm.client import LLMUnavailable, NullLLM, OllamaClient, build_llm, model_matches


def client(handler, model="llama3.2"):
    return OllamaClient("http://ollama.test", model, timeout_s=5, transport=httpx.MockTransport(handler))


def tags(*names):
    return lambda request: httpx.Response(200, json={"models": [{"name": n} for n in names]})


def test_model_matching_rules():
    assert model_matches("llama3.2:latest", "llama3.2")
    assert model_matches("llama3.2:3b", "llama3.2")
    assert model_matches("llama3.2:3b", "llama3.2:3b")
    assert not model_matches("llama3.2:1b", "llama3.2:3b")
    assert not model_matches("llama3.1:8b", "llama3.2")


def test_status_available_when_model_is_pulled():
    s = client(tags("llama3.2:latest", "nomic-embed-text:latest")).status()
    assert s["reachable"] and s["model_present"] and s["available"] and s["error"] is None


def test_status_reachable_but_model_missing():
    s = client(tags("mistral:7b")).status()
    assert s["reachable"] and not s["available"]
    assert "not installed" in s["error"] and "ollama pull llama3.2" in s["hint"]


def test_status_unreachable_is_reported_not_raised():
    def refuse(request):
        raise httpx.ConnectError("connection refused")

    s = client(refuse).status()
    assert not s["reachable"] and not s["available"] and "not reachable" in s["error"] and "ollama pull" in s["hint"]


def test_chat_raises_llm_unavailable_when_not_ready():
    with pytest.raises(LLMUnavailable):
        client(tags()).chat([{"role": "user", "content": "hi"}])


def test_chat_sends_json_mode_and_returns_content():
    seen = {}

    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "llama3.2:latest"}]})
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": '{"ok": true}'}})

    out = client(handler).chat([{"role": "user", "content": "hi"}], json_mode=True, temperature=0.0)
    assert out == '{"ok": true}' and seen["format"] == "json" and seen["stream"] is False and seen["model"] == "llama3.2"


def test_chat_http_failure_and_empty_reply():
    def failing(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "llama3.2"}]})
        return httpx.Response(500, json={"error": "boom"})

    with pytest.raises(LLMUnavailable):
        client(failing).chat([{"role": "user", "content": "x"}])

    def empty(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "llama3.2"}]})
        return httpx.Response(200, json={"message": {"content": "  "}})

    with pytest.raises(LLMUnavailable):
        client(empty).chat([{"role": "user", "content": "x"}])


def test_embed():
    def handler(request):
        body = json.loads(request.content)
        return httpx.Response(200, json={"embeddings": [[0.1, 0.2] for _ in body["input"]]})

    assert client(handler).embed(["a", "b"], "nomic-embed-text") == [[0.1, 0.2], [0.1, 0.2]]
    with pytest.raises(LLMUnavailable):
        client(lambda r: httpx.Response(200, json={"embeddings": [[1.0]]})).embed(["a", "b"], "m")


def test_status_is_cached():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(200, json={"models": [{"name": "llama3.2"}]})

    c = client(handler)
    c.status(); c.status(); c.status()
    assert calls["n"] == 1
    c.status(force=True)
    assert calls["n"] == 2


def test_provider_none_and_factory():
    llm = build_llm(Settings(llm_provider="none", _env_file=None))
    assert isinstance(llm, NullLLM) and not llm.available and llm.status()["error"]
    with pytest.raises(LLMUnavailable):
        llm.chat([])
    assert isinstance(build_llm(Settings(llm_provider="ollama", _env_file=None)), OllamaClient)
