"""Logging configuration with secret redaction."""
from __future__ import annotations

import logging
import re

_URL_PASSWORD = re.compile(r"(postgres(?:ql)?(?:\+\w+)?://[^:/\s]+:)([^@\s]+)(@)")
_KV_SECRET = re.compile(r"(?i)\b(password|passwd|api[_-]?key|token|secret)\b(\s*[=:]\s*)([^\s,;&'\"]+)")


def redact(text: str) -> str:
    """Mask passwords/tokens in free text (URLs and key=value pairs)."""
    text = _URL_PASSWORD.sub(r"\1***\3", text)
    return _KV_SECRET.sub(r"\1\2***", text)


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact(record.getMessage())
            record.args = ()
        except Exception:  # never let logging break the app
            pass
        return True


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if not any(getattr(h, "_retailiq", False) for h in root.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
        handler.addFilter(RedactingFilter())
        handler._retailiq = True  # type: ignore[attr-defined]
        root.addHandler(handler)
    root.setLevel(level.upper())
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
