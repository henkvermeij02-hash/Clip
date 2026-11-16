#!/usr/bin/env bash
# Starts the backend (port 8000) and dashboard (port 3000). Press Ctrl+C to stop both.
set -euo pipefail
cd "$(dirname "$0")/.."

[ -x backend/.venv/bin/uvicorn ] || { echo "Run ./scripts/setup.sh first."; exit 1; }
[ -d frontend/node_modules ] || { echo "Run ./scripts/setup.sh first."; exit 1; }

cleanup() { kill 0 2>/dev/null || true; }
trap cleanup EXIT INT TERM

(cd backend && .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000) &
(cd frontend && npm run dev --silent) &

echo
echo "  GTA Shorts AI Studio is starting…"
echo "  Open http://localhost:3000 in your browser (first load takes a few seconds)."
echo "  Press Ctrl+C here to stop."
echo
wait
