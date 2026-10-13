#!/usr/bin/env bash
# Milestone 0: headless Pi, hostname, clock sync, and LAN address for the operator to verify.
set -euo pipefail

SMOKE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SMOKE_DIR/_load_env.sh"

echo "== Pi baseline =="

hostname_ok=0
if [[ "$(hostname)" == "newspaper" ]]; then
  echo "OK  hostname is newspaper"
  hostname_ok=1
else
  echo "WARN hostname is $(hostname) (expected newspaper)"
fi

echo "-- addresses (confirm the reserved LAN IP in your router) --"
ip -4 -o addr show scope global 2>/dev/null | awk '{print $2, $4}' || true
hostname -I 2>/dev/null | tr ' ' '\n' | sed '/^$/d' | while read -r ip; do echo "    $ip"; done

echo "-- NTP / clock --"
if command -v timedatectl >/dev/null 2>&1; then
  timedatectl status | sed -n '1,6p'
  if timedatectl show -p NTPSynchronized --value 2>/dev/null | grep -qi yes; then
    echo "OK  NTP synchronized"
  else
    echo "WARN NTP not synchronized yet (worker will refuse to build until sync)"
  fi
else
  date -u
  echo "WARN timedatectl not found; check clock manually"
fi

echo "-- SSH (expect key-only in production) --"
if systemctl is-active --quiet ssh 2>/dev/null || systemctl is-active --quiet sshd 2>/dev/null; then
  echo "OK  SSH service active"
else
  echo "WARN SSH service not reported active"
fi

if [[ "$hostname_ok" -eq 1 ]]; then
  echo "PASS check_pi_baseline (review LAN IP and NTP above)"
  exit 0
fi
echo "PASS with warnings check_pi_baseline"
exit 0
