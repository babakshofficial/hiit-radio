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

# yt-dlp postprocessing needs ffmpeg/ffprobe (SoundCloud/YouTube extract+mux).
if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  echo "ERROR: ffmpeg/ffprobe not found — install with: sudo apt-get install -y ffmpeg" >&2
  exit 1
fi

# yt-dlp needs Deno for YouTube JS challenges — install once if missing.
if ! command -v deno >/dev/null 2>&1 && [[ ! -x "${HOME}/.deno/bin/deno" ]]; then
  echo "Deno not found — installing to ~/.deno ..."
  if ! curl -fsSL https://deno.land/install.sh | sh; then
    echo "ERROR: Deno install failed (needed for YouTube downloads)" >&2
    exit 1
  fi
fi
if [[ ! -x "${HOME}/.deno/bin/deno" ]] && ! command -v deno >/dev/null 2>&1; then
  echo "ERROR: Deno binary not found after install" >&2
  exit 1
fi

# Prefer nvm Node when present (Freestyle / headless VMs often lack /usr/bin/node).
if [[ -z "${NODE_BIN:-}" ]]; then
  if command -v node >/dev/null 2>&1; then
    NODE_BIN="$(command -v node)"
  elif [[ -x /usr/local/nvm/versions/node/v24.20.0/bin/node ]]; then
    NODE_BIN=/usr/local/nvm/versions/node/v24.20.0/bin/node
  else
    NODE_BIN="$(ls -1d /usr/local/nvm/versions/node/*/bin/node 2>/dev/null | sort -V | tail -1 || true)"
  fi
fi
if [[ -n "${NODE_BIN:-}" ]]; then
  export PATH="$(dirname "$NODE_BIN"):${HOME}/.deno/bin:${ROOT}/.venv/bin:/usr/local/bin:/usr/bin:/bin"
else
  export PATH="${HOME}/.deno/bin:${ROOT}/.venv/bin:/usr/local/bin:/usr/bin:/bin"
fi

pids=()
cleanup() {
  trap - EXIT INT TERM
  for pid in "${pids[@]+"${pids[@]}"}"; do
    kill "$pid" 2>/dev/null || true
  done
  # Next may leave a child on :3000 after the launcher exits.
  fuser -k 3000/tcp 8000/tcp 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

"$ROOT/.venv/bin/python" "$ROOT/main.py" &
pids+=("$!")

"$ROOT/.venv/bin/uvicorn" api.main:app --host 127.0.0.1 --port 8000 &
pids+=("$!")

NEXT_BIN="$ROOT/web/node_modules/next/dist/bin/next"
if [[ ! -f "$NEXT_BIN" ]]; then
  echo "ERROR: Next.js not installed — run: (cd web && npm install)" >&2
  exit 1
fi
if [[ -z "${NODE_BIN:-}" || ! -x "$NODE_BIN" ]]; then
  echo "ERROR: node binary not found (install Node or set NODE_BIN)" >&2
  exit 1
fi
# Prefer production server when a build exists; otherwise webpack-dev (more
# reliable than Turbopack on some VMs). Track the PID that owns :3000 — the
# next CLI can spawn start-server and exit.
if [[ -d "$ROOT/web/.next/BUILD_ID" ]] || [[ -f "$ROOT/web/.next/BUILD_ID" ]]; then
  (cd "$ROOT/web" && exec "$NODE_BIN" "$NEXT_BIN" start --hostname 127.0.0.1 --port 3000) &
else
  (cd "$ROOT/web" && exec "$NODE_BIN" "$NEXT_BIN" dev --hostname 127.0.0.1 --port 3000 --webpack) &
fi
NEXT_LAUNCHER=$!

port_pid() {
  # Print the first PID listening on TCP $1 (empty if none). Never non-zero:
  # under `set -e`/`pipefail`, a bare `fuser` miss would abort the stack and
  # kill the bot/API during Next startup.
  local port="$1" pid=""
  if command -v ss >/dev/null 2>&1; then
    pid="$(ss -ltnp 2>/dev/null | grep -E ":${port}\\b" | sed -n 's/.*pid=\([0-9]\+\).*/\1/p' | head -1 || true)"
  fi
  if [[ -z "$pid" ]] && command -v fuser >/dev/null 2>&1; then
    # "3000/tcp:  12345" — take the PID after the colon, not the port number.
    pid="$(fuser "${port}/tcp" 2>/dev/null | sed -n 's/.*://p' | tr -cs '0-9' ' ' | awk '{print $1; exit}' || true)"
  fi
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    echo "$pid"
  fi
}

NEXT_PID=""
for _ in $(seq 1 45); do
  NEXT_PID="$(port_pid 3000 || true)"
  if [[ -n "$NEXT_PID" ]]; then
    break
  fi
  # If the launcher died before binding, fail fast.
  if ! kill -0 "$NEXT_LAUNCHER" 2>/dev/null && [[ -z "$(port_pid 3000 || true)" ]]; then
    echo "ERROR: Next.js launcher exited before binding :3000" >&2
    exit 1
  fi
  sleep 1
done
if [[ -z "$NEXT_PID" ]]; then
  echo "ERROR: Next.js failed to bind 127.0.0.1:3000" >&2
  exit 1
fi
pids+=("$NEXT_PID")

# Stay up until a tracked child exits (then systemd restarts the unit).
while true; do
  for pid in "${pids[@]}"; do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "ERROR: child pid $pid exited — shutting down stack" >&2
      exit 1
    fi
  done
  sleep 2
done
