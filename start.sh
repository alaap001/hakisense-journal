#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python || ! -d node_modules ]]; then
  echo 'Run ./setup.sh first to install the local dependencies.'
  exit 1
fi
exec .venv/bin/python scripts/dev.py
