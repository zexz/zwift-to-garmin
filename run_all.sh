#!/usr/bin/env bash
set -euo pipefail

python3 garmin_export.py
python3 fit_autofix.py
python3 garmin_import.py
