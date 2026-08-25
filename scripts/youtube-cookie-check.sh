#!/usr/bin/env bash
# Quick check: can yt-dlp read Chrome cookies the same way the bot does?
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RUNTIME_DIR="/run/user/$(id -u)"
export XDG_RUNTIME_DIR="$RUNTIME_DIR"
export DBUS_SESSION_BUS_ADDRESS="unix:path=${RUNTIME_DIR}/bus"
[[ -S "${RUNTIME_DIR}/keyring/ssh" ]] && export SSH_AUTH_SOCK="${RUNTIME_DIR}/keyring/ssh"
export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-${HOME}/.Xauthority}"
export XDG_CURRENT_DESKTOP="${XDG_CURRENT_DESKTOP:-ubuntu:GNOME}"
export LANG="${LANG:-en_US.UTF-8}"
export PATH="${HOME}/.deno/bin:${ROOT}/.venv/bin:/usr/bin:/bin"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

echo "DBUS=$DBUS_SESSION_BUS_ADDRESS"
echo "SSH_AUTH_SOCK=${SSH_AUTH_SOCK:-unset}"
echo "DISPLAY=$DISPLAY"
echo "XDG_CURRENT_DESKTOP=$XDG_CURRENT_DESKTOP"
echo

echo "--- yt-dlp probe (formats) ---"
"$ROOT/.venv/bin/python" -c "
from downloader import MusicDownloader
d = MusicDownloader()
ok, detail = d.probe_youtube_auth(force=True)
print('probe:', ok, detail)
exit(0 if ok else 1)
"
