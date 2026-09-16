#!/usr/bin/env bash
# Install/update the hiit-radio systemd unit for the current machine + user.
# Rewrites paths in deploy/hiit-radio.service to this checkout and $USER.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UNIT_SRC="$ROOT/deploy/hiit-radio.service"
UNIT_DST="/etc/systemd/system/hiit-radio.service"
RUN_USER="${SUDO_USER:-${USER:-$(id -un)}}"
RUN_GROUP="$(id -gn "$RUN_USER")"
HOME_DIR="$(getent passwd "$RUN_USER" | cut -d: -f6)"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Re-running with sudo…"
  exec sudo -E "$0" "$@"
fi

chmod +x "$ROOT/scripts/install-deps.sh" "$ROOT/scripts/hiit-radio-stack.sh"

tmp="$(mktemp)"
sed \
  -e "s|^User=.*|User=${RUN_USER}|" \
  -e "s|^Group=.*|Group=${RUN_GROUP}|" \
  -e "s|^WorkingDirectory=.*|WorkingDirectory=${ROOT}|" \
  -e "s|^EnvironmentFile=.*|EnvironmentFile=-${ROOT}/.env|" \
  -e "s|^Environment=PATH=.*|Environment=PATH=${HOME_DIR}/.deno/bin:${HOME_DIR}/.nvm/versions/node/v24.20.0/bin:${ROOT}/.venv/bin:/usr/local/nvm/versions/node/v24.20.0/bin:/usr/local/bin:/usr/bin:/bin|" \
  -e "s|^ExecStartPre=.*|ExecStartPre=+${ROOT}/scripts/install-deps.sh --system|" \
  -e "s|^ExecStart=.*|ExecStart=${ROOT}/scripts/hiit-radio-stack.sh|" \
  "$UNIT_SRC" >"$tmp"

install -m 0644 "$tmp" "$UNIT_DST"
rm -f "$tmp"

# Install system packages immediately (also runs again on every service start).
"$ROOT/scripts/install-deps.sh" --system

# User-level deps as the service account.
if [[ "$RUN_USER" != "root" ]]; then
  sudo -u "$RUN_USER" -H "$ROOT/scripts/install-deps.sh" --user
else
  "$ROOT/scripts/install-deps.sh" --user
fi

systemctl daemon-reload
systemctl enable hiit-radio.service
systemctl restart hiit-radio.service
systemctl --no-pager --full status hiit-radio.service | head -25
echo
echo "Installed ${UNIT_DST}"
echo "Follow logs: journalctl -u hiit-radio -f"
