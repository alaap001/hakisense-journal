#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if command -v uv >/dev/null 2>&1; then
  if [[ ! -x .venv/bin/python ]]; then uv venv --python 3.12 .venv; fi
  uv pip install --python .venv/bin/python -r backend/requirements.lock
else
  if [[ ! -x .venv/bin/python ]]; then
    if command -v python3.12 >/dev/null 2>&1; then python3.12 -m venv .venv; else python3 -m venv .venv; fi
  fi
  .venv/bin/python -m pip install -r backend/requirements.lock
fi
npm ci --no-audit --no-fund
if [[ ! -f backend/.env ]]; then cp backend/.env.example backend/.env; chmod 600 backend/.env; fi
echo 'Dependencies installed. Configure backend/.env and run migrations before ./start.sh.'
