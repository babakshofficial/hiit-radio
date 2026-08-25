#!/usr/bin/env bash
# systemd helper: bot + API + web in one process group.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Load .env into the process environment (systemd EnvironmentFile is not always enough
# for vars added after the unit was last daemon-reloaded).
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

# Chrome cookie decryption (secretstorage) needs the logged-in user's DBUS session
# and GNOME keyring (SSH_AUTH_SOCK). Without these, yt-dlp cannot decrypt v11 cookies.
RUNTIME_DIR="/run/user/$(id -u)"
if [[ -d "$RUNTIME_DIR" ]]; then
  export XDG_RUNTIME_DIR="$RUNTIME_DIR"
  if [[ -S "${RUNTIME_DIR}/bus" ]]; then
    export DBUS_SESSION_BUS_ADDRESS="unix:path=${RUNTIME_DIR}/bus"
  fi
  if [[ -S "${RUNTIME_DIR}/keyring/ssh" ]]; then
    export SSH_AUTH_SOCK="${RUNTIME_DIR}/keyring/ssh"
  elif [[ -S "${RUNTIME_DIR}/keyring/control" ]]; then
    # Some GNOME builds expose control but not ssh; secretstorage still needs the bus.
    :
  fi
fi
# System systemd units don't inherit the graphical session; default for local X11 login.
export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-${HOME}/.Xauthority}"
export XDG_CURRENT_DESKTOP="${XDG_CURRENT_DESKTOP:-ubuntu:GNOME}"
export LANG="${LANG:-en_US.UTF-8}"

export PATH="${HOME}/.deno/bin:${ROOT}/.venv/bin:/usr/local/bin:/usr/bin:/bin"

pids=()
cleanup() {
  trap - EXIT INT TERM
  for pid in "${pids[@]+"${pids[@]}"}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

"$ROOT/.venv/bin/python" "$ROOT/main.py" &
pids+=("$!")

"$ROOT/.venv/bin/uvicorn" api.main:app --host 127.0.0.1 --port 8000 &
pids+=("$!")

if [[ -d "$ROOT/web/.next" ]]; then
  (cd "$ROOT/web" && exec /usr/bin/npx next start --hostname 127.0.0.1 --port 3000) &
else
  (cd "$ROOT/web" && exec /usr/bin/npx next dev --hostname 127.0.0.1 --port 3000) &
fi
pids+=("$!")

# If any child dies, stop the rest so systemd can restart the unit.
wait -n
exit 1
