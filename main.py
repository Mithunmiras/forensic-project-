"""RetailIQ command-line entry point.

    python main.py serve [--port 8000]   start the API + dashboard
    python main.py setup-db [...]        create the schema (and optionally database / read-only role)
    python main.py etl [--dry-run]       validate and load the dataset into PostgreSQL
    python main.py train                 train and evaluate the sales models
    python main.py index [--force]       build the RAG knowledge-base index
    python main.py docs                  regenerate data-driven docs from the database
    python main.py eda                   regenerate the exploratory figures
    python main.py status                print the same readiness report as /api/v1/system/status
    python main.py dev-db start|stop     project-local PostgreSQL for development

Everything after the command is passed to the underlying script (see scripts/).
"""
from __future__ import annotations

import json
import os
import runpy
import subprocess
import sys

from src.config import ROOT

SCRIPTS = {
    "setup-db": "setup_database.py",
    "etl": "run_etl.py",
    "train": "train_model.py",
    "index": "index_rag.py",
    "docs": "generate_docs.py",
    "validate": "validate_data.py",
    "dev-db": "dev_postgres.py",
}
EDA_SCRIPTS = ["sales_analysis", "product_analysis", "region_analysis", "customer_analysis", "correlation_analysis"]


def run_script(name: str, args: list[str]) -> int:
    return subprocess.call([sys.executable, str(ROOT / "scripts" / name), *args], cwd=ROOT)


def cmd_serve(args: list[str]) -> int:
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(prog="main.py serve")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="auto-reload on code changes (development)")
    ns = parser.parse_args(args)
    uvicorn.run("src.api.main:app", host=ns.host, port=ns.port, reload=ns.reload)
    return 0


def cmd_eda(_: list[str]) -> int:
    for name in EDA_SCRIPTS:
        print(f"Running {name} ...")
        runpy.run_module(f"src.eda.{name}", run_name="__main__")
    return 0


def cmd_status(_: list[str]) -> int:
    from src.api.routes.system import build_status
    from src.services import build_services

    services = build_services()
    services.startup()
    try:
        status = build_status(services)
    finally:
        services.shutdown()
    print(json.dumps(status, indent=2, default=str))
    return 0 if status["overall"] != "setup_required" else 1


def main() -> int:
    os.chdir(ROOT)
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    command, rest = argv[0], argv[1:]
    if command == "serve":
        return cmd_serve(rest)
    if command == "eda":
        return cmd_eda(rest)
    if command == "status":
        return cmd_status(rest)
    if command in SCRIPTS:
        return run_script(SCRIPTS[command], rest)
    print(f"Unknown command '{command}'.\n")
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
