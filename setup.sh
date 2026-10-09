#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-$ROOT/.venv}"
VENV_PY="$VENV_DIR/bin/python"

log() { printf '[setup] %s\n' "$*"; }
fail() { printf '[setup] ERROR: %s\n' "$*" >&2; exit 1; }

command -v "$PYTHON_BIN" >/dev/null 2>&1 || fail "$PYTHON_BIN was not found. Install Python 3.12 and rerun ./setup.sh."

"$PYTHON_BIN" - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit(f"Python 3.11+ is required; found {sys.version.split()[0]}")
print(f"Using Python {sys.version.split()[0]}")
PY

if [[ ! -x "$VENV_PY" ]]; then
  log "Creating virtual environment at $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR" || fail "Could not create the virtual environment. Install the venv package for your Python distribution and retry."
else
  log "Using existing virtual environment at $VENV_DIR"
fi

log "Upgrading pip"
"$VENV_PY" -m pip install --disable-pip-version-check --upgrade pip

log "Installing scoring and user-study analysis dependencies"
"$VENV_PY" -m pip install --disable-pip-version-check \
  -r "$ROOT/methods_scoring/requirements.txt" \
  -r "$ROOT/user_study/data/requirements.txt"

log "Installing UI runtime dependencies"
"$VENV_PY" -m pip install --disable-pip-version-check \
  -r "$ROOT/user_study/ui/requirements-runtime.txt"

log "Checking imports"
"$VENV_PY" - <<'PY'
import matplotlib
import numpy
import pandas
import scipy
import PIL
import fitz
import waitress
print("Dependency import check: PASS")
PY

chmod +x "$ROOT/run_scoring.sh" "$ROOT/run_ui.sh" "$ROOT/run_user_study_analysis.sh"

printf '\nSetup complete. No shell activation is required.\n'
printf 'Run scoring + sensitivity: ./run_scoring.sh\n'
printf 'Run the local study UI:      ./run_ui.sh\n'
printf 'Run user-study analysis:     ./run_user_study_analysis.sh\n'
