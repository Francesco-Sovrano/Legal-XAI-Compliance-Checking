#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PY="${VENV_PYTHON:-$ROOT/.venv/bin/python}"
[[ -x "$PY" ]] || { printf 'error: environment not set up; run ./setup.sh first\n' >&2; exit 1; }

DRAWS="${DRAWS:-10000}"
SEED="${SEED:-20261005}"
OUTDIR="${SCORING_OUTDIR:-$ROOT/methods_scoring/analysis}"

printf '[scoring] Computing catalogue scores\n'
"$PY" "$ROOT/methods_scoring/assess_xai_compliance.py"

printf '[scoring] Running sensitivity analysis (draws=%s, seed=%s)\n' "$DRAWS" "$SEED"
"$PY" "$ROOT/methods_scoring/sensitivity_analysis.py" \
  --draws "$DRAWS" \
  --seed "$SEED" \
  --outdir "$OUTDIR"

"$PY" "$ROOT/methods_scoring/question_sensitivity.py" --outdir "$OUTDIR"
"$PY" "$ROOT/methods_scoring/legal_task_sensitivity.py" --outdir "$OUTDIR"

printf '[scoring] Results written to %s\n' "$OUTDIR"
