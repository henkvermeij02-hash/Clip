#!/usr/bin/env bash
# One-time setup for macOS / Linux. Run from the project folder:  ./scripts/setup.sh
set -euo pipefail
cd "$(dirname "$0")/.."

say() { printf '\n\033[1;35m==> %s\033[0m\n' "$1"; }
fail() { printf '\n\033[1;31mERROR: %s\033[0m\n' "$1"; exit 1; }

say "Checking required programs"
command -v python3 >/dev/null || fail "Python 3.11+ is not installed. See README → Installation."
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' || fail "Python 3.11 or newer is required (found $(python3 --version))."
command -v node >/dev/null || fail "Node.js 20+ is not installed. See README → Installation."
command -v ffmpeg >/dev/null || fail "FFmpeg is not installed. See README → Installation."
command -v ffprobe >/dev/null || fail "FFprobe (comes with FFmpeg) is not installed."
echo "Python $(python3 --version | cut -d' ' -f2), Node $(node --version), FFmpeg OK"

say "Installing backend (Python) packages"
python3 -m venv backend/.venv
backend/.venv/bin/pip install --upgrade pip -q
backend/.venv/bin/pip install -r backend/requirements.txt -q

say "Installing dashboard (Node.js) packages"
(cd frontend && npm install --no-fund --no-audit)

say "Setup complete. Start the studio with:  ./scripts/start.sh"
