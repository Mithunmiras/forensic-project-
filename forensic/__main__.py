"""Command line.

    python -m forensic generate              regenerate the synthetic data from scenarios.py
    python -m forensic ask "question"        run one investigation and print the answer
    python -m forensic evaluate              score the agents against the ground truth
    python -m forensic serve [--port 8000]   start the API + dashboard on localhost
"""
from __future__ import annotations

import argparse
import json
import socket
import threading
import webbrowser


def _free_port(host: str, start: int) -> int:
    for port in range(start, start + 20):
        with socket.socket() as s:
            if s.connect_ex((host, port)) != 0:
                return port
    raise SystemExit(f"No free port between {start} and {start + 19}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m forensic", description="RetailIQ Forensic")
    sub = parser.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate", help="regenerate the synthetic data")
    g.add_argument("--seed", type=int, default=42)
    a = sub.add_parser("ask", help="investigate one question")
    a.add_argument("question")
    a.add_argument("--json", action="store_true", help="print the full JSON result")
    sub.add_parser("evaluate", help="score the agents against scenarios.py")
    s = sub.add_parser("serve", help="start the API + dashboard on localhost")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    if args.cmd == "generate":
        from forensic.generate import generate
        print(json.dumps(generate(args.seed), indent=2))
    elif args.cmd == "ask":
        from forensic.pipeline import get_investigator
        res = get_investigator().investigate(args.question)
        if args.json:
            print(json.dumps(res, indent=2, default=str))
            return
        ans = res["answer"]
        print(ans["headline"])
        print(f"Confidence: {ans['confidence']['label']} ({ans['confidence']['score']})\n")
        for layer, text in ans["layers"].items():
            print(f"{layer.upper()}\n{text.replace('**', '')}\n")
        print("SOURCES")
        for c in ans["citations"]:
            print(f"  [{c['id']}] {c['label']}: {c['detail']}")
    elif args.cmd == "evaluate":
        from forensic.evaluate import evaluate, print_report
        print_report(evaluate())
    elif args.cmd == "serve":
        import uvicorn

        from forensic.config import UI_DIST
        port = _free_port(args.host, args.port)
        url = f"http://{args.host}:{port}"
        if not (UI_DIST / "index.html").exists():
            print("NOTE: dashboard not built yet - run: cd forensic_ui && npm install && npm run build")
        print(f"RetailIQ Forensic running at {url}  (API docs: {url}/docs)  - Ctrl+C to stop")
        if not args.no_browser:
            threading.Timer(2.0, lambda: webbrowser.open(url)).start()
        uvicorn.run("forensic.api:app", host=args.host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
