#!/usr/bin/env bash
# Runs all automated checks.
set -euo pipefail
cd "$(dirname "$0")/.."
echo "== Backend tests"; (cd backend && .venv/bin/python -m pytest)
echo "== Dashboard type check"; (cd frontend && npx tsc --noEmit)
echo "All checks passed."
