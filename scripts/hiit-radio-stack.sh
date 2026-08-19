#!/usr/bin/env bash
# systemd helper: bot + API + web in one process group.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PROXY=(proxychains4)
if ! command -v proxychains4 >/dev/null 2>&1; then
  PROXY=()
fi

pids=()
cleanup() {
  trap - EXIT INT TERM
  for pid in "${pids[@]+"${pids[@]}"}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

"${PROXY[@]}" "$ROOT/.venv/bin/python" "$ROOT/main.py" &
pids+=("$!")

"${PROXY[@]}" "$ROOT/.venv/bin/uvicorn" api.main:app --host 127.0.0.1 --port 8000 &
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
