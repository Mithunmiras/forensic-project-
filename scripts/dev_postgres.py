"""Project-local PostgreSQL for development (no installation or admin rights needed).

Uses the PostgreSQL 16 binaries bundled in the optional ``pgserver`` pip package.
Data lives in ``.pgdata/`` (git-ignored). The server listens on 127.0.0.1 only,
on a fixed port, with trust authentication - it is a *development convenience*;
for anything shared use a normally installed PostgreSQL with passwords.

    python scripts/dev_postgres.py start    # init (first time) + start + create retailiq_db
    python scripts/dev_postgres.py status
    python scripts/dev_postgres.py stop
    python scripts/dev_postgres.py url      # print the DATABASE_URL to put in .env
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PGDATA = ROOT / ".pgdata"
PORT = 54329
DBNAME = "retailiq_db"
URL = f"postgresql://postgres@127.0.0.1:{PORT}/{DBNAME}"


def _bin() -> Path:
    try:
        import pgserver
    except ImportError:
        sys.exit("pgserver is not installed. Run: pip install -r requirements-localdb.txt")
    path = Path(pgserver.__file__).parent / "pginstall" / "bin"
    if not path.exists():
        sys.exit(f"Bundled PostgreSQL binaries not found at {path}")
    return path


def _run(exe: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run([str(_bin() / exe), *args], capture_output=True, text=True, check=check)


def is_running() -> bool:
    return _run("pg_ctl.exe" if sys.platform == "win32" else "pg_ctl", "status", "-D", str(PGDATA), check=False).returncode == 0


def _exe(name: str) -> str:
    return f"{name}.exe" if sys.platform == "win32" else name


def start() -> None:
    if not (PGDATA / "PG_VERSION").exists():
        print("Initialising new local cluster in .pgdata ...")
        PGDATA.mkdir(exist_ok=True)
        _run(_exe("initdb"), "-D", str(PGDATA), "-U", "postgres", "--auth=trust", "-E", "UTF8", "--no-locale")
    if is_running():
        print(f"Already running on port {PORT}.")
    else:
        print(f"Starting PostgreSQL on 127.0.0.1:{PORT} ...")
        # The server inherits the child's stdio, so never attach pipes here (it would
        # make subprocess wait for the server to exit). Log to a file instead.
        code = subprocess.call(
            [
                str(_bin() / _exe("pg_ctl")), "start", "-w", "-t", "60", "-D", str(PGDATA),
                "-l", str(PGDATA / "server.log"), "-o", f"-p {PORT} -c listen_addresses=127.0.0.1",
            ],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if code != 0:
            sys.exit(f"Could not start PostgreSQL. See {PGDATA / 'server.log'}")
    from src.db.admin import create_database_if_missing

    created = create_database_if_missing(URL.replace("postgresql://", "postgresql+psycopg://"))
    print(f"Database '{DBNAME}': {'created' if created else 'already exists'}.")
    print(f"\nPut this in .env:\nDATABASE_URL={URL}")


def stop() -> None:
    if not is_running():
        print("Not running.")
        return
    _run(_exe("pg_ctl"), "stop", "-D", str(PGDATA), "-m", "fast", "-w")
    print("Stopped.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=["start", "stop", "status", "url"])
    action = parser.parse_args().action
    if action == "start":
        start()
    elif action == "stop":
        stop()
    elif action == "status":
        print("running" if (PGDATA / "PG_VERSION").exists() and is_running() else "stopped")
    else:
        print(URL)


if __name__ == "__main__":
    main()
