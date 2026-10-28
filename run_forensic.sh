#!/usr/bin/env bash
# One command: set up whatever is missing, then start RetailIQ Forensic on http://127.0.0.1:8000
#   ./run_forensic.sh            (add --port 8765 or --no-browser if needed)
set -euo pipefail
cd "$(dirname "$0")"
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"

if [ ! -x .venv/bin/python ]; then
  echo "==> Creating Python virtual environment"
  python3 -m venv .venv
fi
if ! .venv/bin/python -c "import pandas, fastapi, uvicorn" 2>/dev/null; then
  echo "==> Installing Python dependencies"
  .venv/bin/pip install -q -r requirements-dev.txt
fi
if [ ! -f forensic_ui/dist/index.html ]; then
  command -v npm >/dev/null || { echo "Node.js (npm) is required to build the dashboard: https://nodejs.org"; exit 1; }
  echo "==> Building the React dashboard"
  (cd forensic_ui && npm install --no-audit --no-fund && npm run build)
fi
if [ ! -f data/forensic.sqlite ]; then
  echo "==> Generating synthetic data"
  .venv/bin/python -m forensic generate
fi
exec .venv/bin/python -m forensic serve "$@"
