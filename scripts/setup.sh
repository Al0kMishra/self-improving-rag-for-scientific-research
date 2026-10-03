#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

fail() { echo "setup: $1" >&2; exit 1; }

PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then
    PYTHON="$candidate"
    break
  fi
done
command -v node >/dev/null 2>&1 || fail "Node.js 20+ is required, install it from https://nodejs.org"

echo "1/5 creating .env"
[ -f .env ] || cp .env.example .env

echo "2/5 creating the Python environment in .venv"
if [ -n "$PYTHON" ]; then
  "$PYTHON" -m venv .venv
  .venv/bin/python -m pip install -q --upgrade pip
  .venv/bin/python -m pip install -q -r backend/requirements-dev.txt
elif command -v uv >/dev/null 2>&1; then
  uv venv -q --allow-existing --python 3.11 .venv
  VIRTUAL_ENV=.venv uv pip install -q -r backend/requirements-dev.txt
else
  fail "Python 3.11+ is required, install it from https://www.python.org/downloads or install uv"
fi

echo "3/5 installing the dashboard"
(cd frontend && npm install --silent)

echo "4/5 downloading the embedding model (about 90 MB, once)"
.venv/bin/python scripts/download_models.py

echo "5/5 enabling the commit message hook"
git config core.hooksPath .githooks 2>/dev/null || true

echo
echo "Done. Next:"
echo "  1. open .env and fill in one LLM option (see README, step 3)"
echo "  2. run ./scripts/dev.sh and open http://localhost:5173"
