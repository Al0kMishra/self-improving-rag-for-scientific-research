#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export BACKEND_PORT="${BACKEND_PORT:-8000}"
(cd backend && ../.venv/bin/uvicorn app.main:app --reload --port "$BACKEND_PORT") &
BACKEND_PID=$!
trap 'kill $BACKEND_PID' EXIT
cd frontend && npm run dev
