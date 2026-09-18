#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PROJECT_DIR}/backend/venv/bin/python"

if [ ! -x "${PYTHON}" ]; then
    echo "Python environment not found. Run ${PROJECT_DIR}/scripts/install.sh first." >&2
    exit 1
fi

cd "${PROJECT_DIR}/backend"
exec "${PYTHON}" main.py
