#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="${NEWSPAPER_DATA_DIR:-$ROOT/data}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: sudo ./deploy/install.sh" >&2
  exit 1
fi
if [ -z "${SUDO_USER:-}" ]; then
  echo "Run with sudo from the operator account." >&2
  exit 1
fi
if [ ! -x "$ROOT/.venv/bin/newspaper-web" ] || [ ! -x "$ROOT/.venv/bin/newspaper-lan-sync" ]; then
  echo "Create the venv and install the app before this script." >&2
  exit 1
fi

APP_USER="$SUDO_USER"
install -d -o "$APP_USER" -g "$APP_USER" -m 0750 "$DATA"
install -d -o "$APP_USER" -g "$APP_USER" -m 0750 "$DATA/editions" "$DATA/cache"

apt-get update
apt-get install -y avahi-daemon nftables unattended-upgrades

install -m 0644 "$ROOT/deploy/apt/20auto-upgrades" /etc/apt/apt.conf.d/20auto-upgrades
install -m 0644 "$ROOT/deploy/apt/50unattended-upgrades" /etc/apt/apt.conf.d/50unattended-upgrades-newspaper
install -d /etc/avahi/services
install -m 0644 "$ROOT/deploy/avahi/newspaper.service" /etc/avahi/services/newspaper.service

sed \
  -e "s#__ROOT__#${ROOT}#g" \
  -e "s#__DATA__#${DATA}#g" \
  -e "s#__USER__#${APP_USER}#g" \
  "$ROOT/deploy/newspaper-web.service" > /etc/systemd/system/newspaper-web.service
sed \
  -e "s#__ROOT__#${ROOT}#g" \
  -e "s#__DATA__#${DATA}#g" \
  "$ROOT/deploy/newspaper-lan-sync.service" > /etc/systemd/system/newspaper-lan-sync.service
sed \
  -e "s#__DATA__#${DATA}#g" \
  "$ROOT/deploy/newspaper-lan-sync.path" > /etc/systemd/system/newspaper-lan-sync.path

if [ ! -e "$DATA/status-http.port" ]; then
  : > "$DATA/status-http.port"
  chown "$APP_USER:$APP_USER" "$DATA/status-http.port"
  chmod 0644 "$DATA/status-http.port"
fi

install -d /etc/caddy
systemctl daemon-reload
systemctl enable --now nftables
"$ROOT/.venv/bin/newspaper-lan-sync" --data-dir "$DATA" --caddy /etc/caddy/Caddyfile --nft /etc/nftables.conf

apt-get install -y caddy
"$ROOT/.venv/bin/newspaper-lan-sync" --data-dir "$DATA" --caddy /etc/caddy/Caddyfile --nft /etc/nftables.conf

systemctl enable --now avahi-daemon
systemctl enable --now unattended-upgrades
systemctl enable --now caddy
systemctl enable --now newspaper-lan-sync.service
systemctl enable --now newspaper-lan-sync.path
systemctl enable --now newspaper-web.service
