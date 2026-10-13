#!/usr/bin/env bash
# Run all milestone 0 smoke checks in order.
set -euo pipefail

SMOKE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SMOKE_DIR/_load_env.sh"

VENV="${SMOKE_VENV:-$SMOKE_DIR/.venv}"
if [[ ! -x "$VENV/bin/python" ]]; then
  echo "Creating venv at $VENV"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q -r "$SMOKE_DIR/requirements.txt"
fi
PY="$VENV/bin/python"

ENV_FILE="${SMOKE_ENV_FILE:-$SMOKE_DIR/smoke.local.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Copy smoke.env.example to smoke.local.env and fill credentials."
  exit 1
fi

failures=0
run() {
  local name="$1"
  shift
  echo ""
  if "$@"; then
    echo ">>> $name succeeded"
  else
    echo ">>> $name FAILED"
    failures=$((failures + 1))
  fi
}

run "check_pi_baseline" bash "$SMOKE_DIR/check_pi_baseline.sh"
run "check_printer" bash "$SMOKE_DIR/check_printer.sh"
run "check_baikal" "$PY" "$SMOKE_DIR/check_baikal.py"
run "check_openrouter" "$PY" "$SMOKE_DIR/check_openrouter.py"
run "check_dropbox" "$PY" "$SMOKE_DIR/check_dropbox.py"

echo ""
if [[ "$failures" -gt 0 ]]; then
  echo "SMOKE FAILED ($failures check(s))"
  exit 1
fi

echo "SMOKE PASSED"
echo "Copy keys-for-1.3.local.md.example to keys-for-1.3.local.md and record working values for story 1.3."
exit 0
