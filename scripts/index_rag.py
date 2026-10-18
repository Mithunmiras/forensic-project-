"""Build (or refresh) the knowledge-base vector index.

    python scripts/index_rag.py            # only re-embeds when documents changed
    python scripts/index_rag.py --force    # rebuild from scratch
    python scripts/index_rag.py --status
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import get_settings  # noqa: E402
from src.llm.client import build_llm  # noqa: E402
from src.logging_setup import configure_logging  # noqa: E402
from src.rag.service import KnowledgeBase  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="rebuild even if nothing changed")
    parser.add_argument("--status", action="store_true", help="only print the index status")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)
    kb = KnowledgeBase(settings, build_llm(settings))
    kb.init()
    try:
        if args.status:
            print(json.dumps(kb.status(), indent=2))
            return 0
        result = kb.index(force=args.force)
        print(json.dumps(result, indent=2))
        status = kb.status()
        if status["state"] == "degraded":
            print(f"NOTE: semantic search is unavailable - {status['embedder_status']}")
            print("      Keyword (TF-IDF) retrieval was indexed instead and is labelled as such in answers.")
        return 0 if result["status"] in ("indexed", "up_to_date") else 1
    except Exception as exc:  # noqa: BLE001
        print(f"Indexing failed: {exc.__class__.__name__}: {exc}")
        return 1
    finally:
        kb.close()


if __name__ == "__main__":
    raise SystemExit(main())
