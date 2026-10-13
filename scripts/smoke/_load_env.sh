#!/usr/bin/env bash
# Source from other smoke scripts. Sets SMOKE_DIR and loads smoke.local.env if present.
set -euo pipefail

SMOKE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export SMOKE_DIR

ENV_FILE="${SMOKE_ENV_FILE:-$SMOKE_DIR/smoke.local.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi
