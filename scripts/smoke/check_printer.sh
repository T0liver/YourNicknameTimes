#!/usr/bin/env bash
# Milestone 0: CUPS sees the USB printer and lp prints a test page.
set -euo pipefail

SMOKE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SMOKE_DIR/_load_env.sh"

echo "== CUPS printer =="

if ! command -v lpstat >/dev/null 2>&1; then
  echo "FAIL lpstat not found; install CUPS"
  exit 1
fi

if ! lpstat -r >/dev/null 2>&1; then
  echo "FAIL CUPS scheduler not running"
  exit 1
fi
echo "OK  CUPS scheduler running"

echo "-- USB devices (look for Brother) --"
if command -v lsusb >/dev/null 2>&1; then
  lsusb | grep -i brother || lsusb | head -20
else
  echo "(lsusb not installed)"
fi

if [[ -n "${BROTHER_MODEL:-}" ]]; then
  echo "Recorded BROTHER_MODEL from env: $BROTHER_MODEL"
else
  echo "Tip: set BROTHER_MODEL in smoke.local.env and copy to keys-for-1.3.local.md"
fi

echo "-- printers --"
lpstat -p -d 2>/dev/null || true

PRINTER="${PRINTER_NAME:-}"
if [[ -z "$PRINTER" ]]; then
  PRINTER="$(lpstat -d 2>/dev/null | awk '{print $NF}' || true)"
fi
if [[ -z "$PRINTER" || "$PRINTER" == "no" ]]; then
  PRINTER="$(lpstat -p 2>/dev/null | awk '/printer/ {print $2; exit}' || true)"
fi
if [[ -z "$PRINTER" ]]; then
  echo "FAIL no printer found; add one with lpadmin or the CUPS web UI"
  exit 1
fi
echo "Using printer: $PRINTER"

TEST_FILE=""
for candidate in \
  /usr/share/cups/data/testprint \
  /usr/share/cups/data/default-testpage.ps \
  /etc/cups/testprint; do
  if [[ -f "$candidate" ]]; then
    TEST_FILE="$candidate"
    break
  fi
done
if [[ -z "$TEST_FILE" ]]; then
  TMP="$(mktemp /tmp/smoke-print.XXXXXX)"
  printf 'Your Nickname Times — CUPS smoke test\n' >"$TMP"
  TEST_FILE="$TMP"
  trap 'rm -f "$TMP"' EXIT
fi

echo "Sending test page: $TEST_FILE"
JOB="$(lp -d "$PRINTER" "$TEST_FILE" 2>&1)" || {
  echo "FAIL lp failed: $JOB"
  exit 1
}
echo "$JOB"

if command -v lpq >/dev/null 2>&1; then
  sleep 2
  lpq -P "$PRINTER" 2>/dev/null || true
fi

echo "PASS check_printer — confirm paper printed on the Brother"
