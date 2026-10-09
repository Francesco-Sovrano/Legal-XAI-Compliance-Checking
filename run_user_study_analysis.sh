#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PY="${VENV_PYTHON:-$ROOT/.venv/bin/python}"
[[ -x "$PY" ]] || { printf 'error: environment not set up; run ./setup.sh first\n' >&2; exit 1; }

DATABASE="${STUDY_DATABASE:-$ROOT/user_study/data/public-review.sqlite3}"
ANALYSIS_OUT="${STUDY_ANALYSIS_OUTDIR:-$ROOT/user_study/data/analysis}"
AUDIT_OUT="${STUDY_AUDIT_OUTDIR:-$ROOT/user_study/data/audit}"
DRAW_DIR="${SCORING_OUTDIR:-$ROOT/methods_scoring/analysis}"
DRAWS="${DRAWS:-10000}"
SEED="${SEED:-20261005}"

[[ -f "$DATABASE" ]] || { printf 'error: response database not found: %s\n' "$DATABASE" >&2; exit 1; }

# Expert validation consumes the joint sensitivity draws. Generate them if the
# scoring analysis has not been run yet.
if [[ ! -f "$DRAW_DIR/joint_draw_scores.npz" ]]; then
  printf '[user-study] Sensitivity draws not found; generating them first\n'
  "$PY" "$ROOT/methods_scoring/sensitivity_analysis.py" \
    --draws "$DRAWS" \
    --seed "$SEED" \
    --outdir "$DRAW_DIR"
fi

BEFORE="$($PY - "$DATABASE" <<'PY'
from pathlib import Path
import hashlib, sys
print(hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest())
PY
)"

printf '[user-study] Running legal-expert analysis\n'
"$PY" "$ROOT/user_study/data/legal_expert_validation.py" "$DATABASE" \
  --outdir "$ANALYSIS_OUT" \
  --drawdir "$DRAW_DIR"

printf '[user-study] Exporting data audit\n'
PYTHONPATH="$ROOT/user_study/data:$ROOT/user_study/ui${PYTHONPATH:+:$PYTHONPATH}" \
  "$PY" - "$ROOT" "$AUDIT_OUT" <<'PY'
from pathlib import Path
import sys
from data_audit import analyse
analyse(Path(sys.argv[1]), Path(sys.argv[2]))
PY

AFTER="$($PY - "$DATABASE" <<'PY'
from pathlib import Path
import hashlib, sys
print(hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest())
PY
)"

[[ "$BEFORE" == "$AFTER" ]] || {
  printf 'error: recorded response database changed during analysis\n' >&2
  exit 1
}

printf '[user-study] Analysis written to %s\n' "$ANALYSIS_OUT"
printf '[user-study] Audit written to %s\n' "$AUDIT_OUT"
printf '[user-study] Recorded response database hash unchanged\n'
