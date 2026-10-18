"""Central configuration for RetailIQ.

Every setting comes from an environment variable (or the local, git-ignored
``.env`` file). Nothing secret is hardcoded. See ``.env.example`` for the full,
documented list.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent

# ---- fixed project paths (not user-configurable) --------------------------
RAW_CSV = ROOT / "data" / "raw" / "superstore.csv"
CLEAN_CSV = ROOT / "data" / "processed" / "superstore_cleaned.csv"
MODELS_DIR = ROOT / "models"
FIGURES_DIR = ROOT / "reports" / "figures"
REPORTS_DIR = ROOT / "reports"
DOCS_DIR = ROOT / "docs"
FRONTEND_DIST = ROOT / "frontend" / "dist"

DB_SCHEMA = "retailiq"


def normalize_db_url(url: str) -> str:
    """Use the psycopg 3 driver for any plain ``postgresql://`` URL."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def redact_url(url: str | None) -> str | None:
    """Hide the password in a database URL so it can be shown or logged."""
    if not url or "@" not in url:
        return url
    head, tail = url.rsplit("@", 1)
    if "://" in head and ":" in head.split("://", 1)[1]:
        scheme, creds = head.split("://", 1)
        user = creds.split(":", 1)[0]
        return f"{scheme}://{user}:***@{tail}"
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"), env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # --- application ---
    app_env: str = "development"
    log_level: str = "INFO"
    frontend_origin: str = "http://localhost:5173"  # comma-separated list allowed
    admin_token: str | None = None  # enables protected admin endpoints when set
    readonly_db_password: str | None = None  # only used by scripts/setup_database.py

    # --- database ---
    database_url: str | None = None            # privileged: schema setup + ETL
    database_readonly_url: str | None = None   # analytics / SQL agent (read-only role)
    # Legacy pieces, used only when DATABASE_URL is not set.
    db_user: str | None = None
    db_password: str | None = None
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "retailiq_db"
    query_timeout_ms: int = Field(8000, ge=500, le=120_000)
    max_result_rows: int = Field(500, ge=1, le=10_000)

    # --- ML ---
    model_path: Path = MODELS_DIR / "sales_model.joblib"
    metrics_path: Path = MODELS_DIR / "metrics.json"

    # --- LLM (optional; the app works without it) ---
    llm_provider: str = "ollama"               # "ollama" | "none"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    llm_timeout_s: float = Field(90.0, gt=0)
    sql_agent_strategy: str = "template_first"  # or "llm_first"
    llm_routing: bool = True                    # let the LLM route when it is available

    # --- RAG ---
    embedding_provider: str = "auto"           # auto | chroma | ollama | lexical
    embedding_model: str = "nomic-embed-text"  # used by the ollama provider
    vector_store_path: Path = ROOT / "vectorstore"
    rag_sources: str = "README.md,docs/**/*.md,docs/**/*.txt"
    rag_top_k: int = Field(4, ge=1, le=20)
    rag_min_similarity: float = Field(0.22, ge=0, le=1)
    rag_chunk_chars: int = Field(600, ge=200, le=4000)
    rag_chunk_overlap: int = Field(100, ge=0, le=1000)

    # --- orchestration ---
    agent_max_tool_calls: int = Field(3, ge=1, le=6)
    agent_time_budget_s: float = Field(120.0, gt=0)

    @field_validator("model_path", "metrics_path", "vector_store_path", mode="after")
    @classmethod
    def _absolute(cls, value: Path) -> Path:
        return value if value.is_absolute() else (ROOT / value)

    @property
    def effective_database_url(self) -> str | None:
        """Privileged URL; falls back to legacy DB_* variables."""
        if self.database_url:
            return normalize_db_url(self.database_url)
        if self.db_user:
            pw = f":{quote_plus(self.db_password)}" if self.db_password else ""
            return normalize_db_url(
                f"postgresql://{self.db_user}{pw}@{self.db_host}:{self.db_port}/{self.db_name}"
            )
        return None

    @property
    def effective_readonly_url(self) -> str | None:
        return normalize_db_url(self.database_readonly_url) if self.database_readonly_url else None

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.frontend_origin.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def database_url() -> str:
    """Backward-compatible helper used by older scripts."""
    url = get_settings().effective_database_url
    if not url:
        raise RuntimeError("DATABASE_URL is not configured. Copy .env.example to .env and set it.")
    return url
