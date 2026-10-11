#!/usr/bin/env bash
set -eu

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "Python 3 no está instalado o no se encuentra en PATH." >&2
  exit 1
fi

"$PYTHON" -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

printf '\nInstalación completada. Ejecuta:\n  .venv/bin/python scripts/bago.py demo\n'
