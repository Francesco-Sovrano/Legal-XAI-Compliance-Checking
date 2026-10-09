#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PY="${VENV_PYTHON:-$ROOT/.venv/bin/python}"
[[ -x "$PY" ]] || { printf 'error: environment not set up; run ./setup.sh first\n' >&2; exit 1; }

PORT="${1:-${PORT:-8080}}"
[[ "$PORT" =~ ^[0-9]+$ ]] && (( PORT >= 1 && PORT <= 65535 )) || {
  printf 'usage: %s [PORT]\n' "$0" >&2
  exit 2
}

HOST="${HOST:-127.0.0.1}"
SERVER="${STUDY_SERVER:-wsgiref}"
[[ "$SERVER" == "wsgiref" || "$SERVER" == "waitress" ]] || { printf 'error: STUDY_SERVER must be wsgiref or waitress\n' >&2; exit 2; }
DB_PATH="${STUDY_DB:-$ROOT/user_study/ui/data/demo.sqlite3}"
mkdir -p "$(dirname "$DB_PATH")"

printf '[ui] Starting demo UI at http://%s:%s\n' "$HOST" "$PORT"
printf '[ui] Demo database: %s\n' "$DB_PATH"
printf '[ui] Server: %s\n' "$SERVER"
exec "$PY" "$ROOT/user_study/ui/app.py" \
  --mode demo \
  --server "$SERVER" \
  --host "$HOST" \
  --port "$PORT" \
  --db "$DB_PATH"
