"""Dependency container: builds every service once and wires them together.

Constructing the container never fails because a dependency is missing - the
database, model, vector index and LLM each report their own readiness.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from src.agents.orchestrator import Orchestrator
from src.agents.tools import MlTool, RagTool, SqlTool
from src.analytics.repository import AnalyticsRepository
from src.analytics.sql_agent import SqlAgent
from src.config import Settings, get_settings
from src.db.session import Database
from src.llm.client import LLM, build_llm
from src.ml.service import ModelService
from src.rag.service import KnowledgeBase

log = logging.getLogger("retailiq.services")


@dataclass
class Services:
    settings: Settings
    db: Database
    repo: AnalyticsRepository
    llm: LLM
    model: ModelService
    kb: KnowledgeBase
    sql_agent: SqlAgent
    orchestrator: Orchestrator

    def startup(self) -> None:
        """Load the model and open the persisted vector index. Never raises."""
        self.model.load()
        try:
            self.kb.init()
        except Exception as exc:  # noqa: BLE001
            log.error("Knowledge base init failed: %s", exc.__class__.__name__)

    def shutdown(self) -> None:
        self.kb.close()
        self.db.dispose()


def build_services(settings: Settings | None = None, llm: LLM | None = None) -> Services:
    settings = settings or get_settings()
    llm = llm or build_llm(settings)
    db = Database(settings)
    repo = AnalyticsRepository(db)
    model = ModelService(settings)
    kb = KnowledgeBase(settings, llm)
    sql_agent = SqlAgent(db, repo, llm, settings)
    orchestrator = Orchestrator(
        SqlTool(sql_agent), MlTool(model, llm), RagTool(kb), llm, settings, known_values_fn=repo.filter_options
    )
    return Services(settings, db, repo, llm, model, kb, sql_agent, orchestrator)
