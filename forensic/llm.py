"""Optional LLM (Groq, OpenAI-compatible API) - stdlib only, so the serverless bundle stays small.

The LLM never decides a root cause or a number. It is used for two things, and both are
validated before anything reaches the user:
  * extract_entities - fills product/region/month the rule parser could not, restricted to
    allowed values (orchestrator);
  * summarize        - an executive briefing written ONLY from the synthesis agent's evidence,
    rejected unless every number and citation in it appears in that evidence.

Configuration: GROQ_API_KEY (environment variable, or a .env file in the project root),
optional GROQ_MODEL. FORENSIC_DISABLE_LLM=1 turns it off (tests, evaluation).
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from functools import lru_cache
from typing import Optional

from forensic.config import ROOT

API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-120b"
TIMEOUT_S = 20


class LLMUnavailable(Exception):
    pass


@lru_cache(maxsize=1)
def _dotenv() -> dict:
    values = {}
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip().strip('"').strip("'")
    return values


def _setting(name: str) -> Optional[str]:
    return os.environ.get(name) or _dotenv().get(name)


def model_name() -> str:
    return _setting("GROQ_MODEL") or DEFAULT_MODEL


def enabled() -> bool:
    return bool(_setting("GROQ_API_KEY")) and os.environ.get("FORENSIC_DISABLE_LLM") != "1"


def chat(messages: list, json_mode: bool = False, max_tokens: int = 700) -> str:
    if not enabled():
        raise LLMUnavailable("No GROQ_API_KEY configured")
    body = {"model": model_name(), "messages": messages, "temperature": 0, "max_tokens": max_tokens}
    if model_name().startswith("openai/gpt-oss"):
        body["reasoning_effort"] = "low"
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(API_URL, data=json.dumps(body).encode(), method="POST", headers={
        "Authorization": f"Bearer {_setting('GROQ_API_KEY')}", "Content-Type": "application/json",
        "User-Agent": "retailiq-forensic/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        raise LLMUnavailable(f"Groq API error {e.code}: {detail}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise LLMUnavailable(f"Groq API unreachable: {e}") from e
    content = (data.get("choices") or [{}])[0].get("message", {}).get("content")
    if not content:
        raise LLMUnavailable("Empty response from the model")
    # Normalise typographic spaces/hyphens the model likes to emit.
    for ch, rep in (("\u202f", " "), ("\u00a0", " "), ("\u2011", "-"), ("\u2010", "-"), ("\u2212", "-")):
        content = content.replace(ch, rep)
    return content.strip()


# --- orchestrator helper ---------------------------------------------------------------------
def extract_entities(question: str, products: list, regions: list, months: list) -> dict:
    """Ask the LLM for product/region/month; anything outside the allowed values is dropped."""
    catalog = ", ".join(f"{p['product_id']} ({p['product_name']})" for p in products)
    system = (
        "You extract filters from a retail analytics question. Reply with JSON only: "
        '{"product_id": string|null, "region": string|null, "month": "YYYY-MM"|null}. '
        f"product_id must be one of: {catalog}. region must be one of: {', '.join(regions)}. "
        f"month must be between {months[0]} and {months[-1]}; map seasons or holidays to a month "
        "(e.g. Christmas -> December, Black Friday -> November). Use null when the question does not say."
    )
    raw = chat([{"role": "system", "content": system}, {"role": "user", "content": question}], json_mode=True,
               max_tokens=300)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise LLMUnavailable("Model did not return JSON") from e
    ids = {p["product_id"] for p in products}
    return {
        "product_id": data.get("product_id") if data.get("product_id") in ids else None,
        "region": data.get("region") if data.get("region") in regions else None,
        "month": data.get("month") if data.get("month") in months else None,
    }


# --- synthesis helper ------------------------------------------------------------------------
_NUM = re.compile(r"(?<![\w.])[-+−]?\d[\d,]*(?:\.\d+)?")
_CITE = re.compile(r"\[(\d+)\]")


def _numbers(text: str) -> set:
    text = _CITE.sub(" ", text)
    out = set()
    for m in _NUM.findall(text):
        v = m.replace(",", "").replace("−", "-").lstrip("+")
        try:
            out.add(round(abs(float(v)), 2))
        except ValueError:
            pass
    return out


def grounding_check(summary: str, evidence: str, n_citations: int) -> list:
    """Problems found: numbers not present in the evidence, or citations that do not exist."""
    allowed = _numbers(evidence)
    problems = [f"number {n:g} is not in the evidence" for n in sorted(_numbers(summary) - allowed)]
    problems += [f"citation [{c}] does not exist" for c in _CITE.findall(summary) if not 1 <= int(c) <= n_citations]
    return problems


def summarize(question: str, answer: dict) -> dict:
    layers = answer["layers"]
    evidence = "\n".join([
        f"Headline: {answer['headline']}",
        f"Evidence case: {answer['case']}; confidence {answer['confidence']['label']} "
        f"({round(answer['confidence']['score'] * 100)}%)",
        f"Descriptive: {layers['descriptive']}",
        f"Diagnostic: {layers['diagnostic']}",
        f"Predictive: {layers['predictive']}",
        "Prescriptive: " + " ".join(answer["actions"]),
    ]).replace("**", "")
    system = (
        "You are a forensic retail analyst writing for a busy business manager. Rewrite the evidence below into "
        "an executive briefing of 4 to 6 short sentences: what happened, why, what happens next, what to do. "
        "Rules: use ONLY facts and numbers that appear in the evidence, written exactly as they appear; keep the "
        "citation markers like [1] after the claims they support; do not invent causes, numbers, dates or "
        "recommendations; if the evidence says nothing unusual happened, say so plainly; plain prose, no "
        "headings, no bullet points, no markdown."
    )
    start = time.perf_counter()
    text = chat([{"role": "system", "content": system},
                 {"role": "user", "content": f"Question: {question}\n\nEvidence:\n{evidence}"}])
    problems = grounding_check(text, evidence + " " + question, len(answer["citations"]))
    return {"text": text, "model": model_name(), "grounded": not problems, "problems": problems,
            "ms": round((time.perf_counter() - start) * 1000)}
