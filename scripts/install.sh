#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [ ! -d "${PROJECT_DIR}/backend/venv" ]; then
    "${PYTHON_BIN}" -m venv "${PROJECT_DIR}/backend/venv"
fi

"${PROJECT_DIR}/backend/venv/bin/python" -m pip install --upgrade pip
"${PROJECT_DIR}/backend/venv/bin/python" -m pip install -r "${PROJECT_DIR}/backend/requirements.txt"

echo "Installation complete. Start the API with ${PROJECT_DIR}/scripts/start.sh"
