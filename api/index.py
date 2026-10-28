"""Vercel serverless entry point: every /api/* request is routed here (see vercel.json)."""
from forensic.api import app  # noqa: F401
