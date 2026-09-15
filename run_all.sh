#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

python_bin="python3"
if [[ -x .venv/bin/python ]]; then
    python_bin=".venv/bin/python"
fi
echo "[FIX] Running Garmin workflow with ${python_bin}"

"$python_bin" garmin_export.py
"$python_bin" fit_autofix.py
"$python_bin" garmin_import.py
