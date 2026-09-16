#!/usr/bin/env bash
# Bootstrap every runtime dependency HiiT Radio needs on a fresh host.
#
# Usage:
#   scripts/install-deps.sh              # system (root/sudo) + user/project deps
#   scripts/install-deps.sh --system     # apt packages only (must be root)
#   scripts/install-deps.sh --user       # Deno, Node, venv, pip, npm (service user)
#
# Systemd: run --system via ExecStartPre=+… so apt works without passwordless sudo.
# The stack script runs --user on every start (idempotent / fast when already OK).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
MODE="all"
NODE_MAJOR="${HIIT_NODE_MAJOR:-24}"
NVM_VERSION="${HIIT_NVM_VERSION:-v0.40.3}"

for arg in "$@"; do
  case "$arg" in
    --system) MODE="system" ;;
    --user) MODE="user" ;;
    --all) MODE="all" ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 2
      ;;
  esac
done

if [[ "${HIIT_SKIP_DEPS:-}" == "1" ]]; then
  echo "HIIT_SKIP_DEPS=1 — skipping dependency bootstrap"
  exit 0
fi

log() { echo "[install-deps] $*"; }
die() { echo "[install-deps] ERROR: $*" >&2; exit 1; }

have_cmd() { command -v "$1" >/dev/null 2>&1; }

ensure_system() {
  if [[ "$(id -u)" -ne 0 ]]; then
    die "--system must run as root (systemd ExecStartPre=+… or: sudo $SELF --system)"
  fi
  have_cmd apt-get || die "apt-get not found — install ffmpeg/python3/curl manually"

  local -a pkgs=(
    ca-certificates
    curl
    ffmpeg
    python3
    python3-venv
    python3-pip
    python3-dev
    build-essential
    pkg-config
    git
    psmisc
    procps
    iproute2
  )
  local -a missing=()
  local p
  for p in "${pkgs[@]}"; do
    if ! dpkg -s "$p" >/dev/null 2>&1; then
      missing+=("$p")
    fi
  done
  if [[ ${#missing[@]} -gt 0 ]]; then
    log "installing apt packages: ${missing[*]}"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq "${missing[@]}"
  else
    log "apt packages already installed"
  fi

  have_cmd ffmpeg || die "ffmpeg missing after install"
  have_cmd ffprobe || die "ffprobe missing after install"
  have_cmd python3 || die "python3 missing after install"
  have_cmd curl || die "curl missing after install"
  log "system deps OK (ffmpeg $(ffmpeg -version 2>/dev/null | head -1 | awk '{print $3}'), $(python3 -V 2>&1))"
}

resolve_node() {
  if [[ -n "${NODE_BIN:-}" && -x "${NODE_BIN}" ]]; then
    echo "$NODE_BIN"
    return 0
  fi
  if have_cmd node; then
    command -v node
    return 0
  fi
  local candidate
  # Prefer newest nvm node under HOME, then system nvm.
  local newest=""
  newest="$(ls -1d "${HOME}/.nvm/versions/node"/v*/bin/node 2>/dev/null | sort -V | tail -1 || true)"
  if [[ -n "$newest" && -x "$newest" ]]; then
    echo "$newest"
    return 0
  fi
  newest="$(ls -1d /usr/local/nvm/versions/node/*/bin/node 2>/dev/null | sort -V | tail -1 || true)"
  if [[ -n "$newest" && -x "$newest" ]]; then
    echo "$newest"
    return 0
  fi
  if [[ -x /usr/local/bin/node ]]; then
    echo /usr/local/bin/node
    return 0
  fi
  return 1
}

install_node_via_nvm() {
  local nvm_dir="${NVM_DIR:-${HOME}/.nvm}"
  export NVM_DIR="$nvm_dir"
  if [[ ! -s "${NVM_DIR}/nvm.sh" ]]; then
    log "installing nvm ${NVM_VERSION} → ${NVM_DIR}"
    curl -fsSL "https://raw.githubusercontent.com/nvm-sh/nvm/${NVM_VERSION}/install.sh" | bash
  fi
  # shellcheck disable=SC1091
  source "${NVM_DIR}/nvm.sh"
  if ! nvm ls "${NODE_MAJOR}" >/dev/null 2>&1; then
    log "installing Node.js ${NODE_MAJOR} via nvm"
    nvm install "${NODE_MAJOR}"
  fi
  nvm use "${NODE_MAJOR}" >/dev/null
  have_cmd node || die "node still missing after nvm install"
  log "Node OK ($(node -v), npm $(npm -v))"
}

ensure_deno() {
  export DENO_INSTALL="${DENO_INSTALL:-${HOME}/.deno}"
  local deno_bin=""
  if have_cmd deno; then
    deno_bin="$(command -v deno)"
  elif [[ -x "${DENO_INSTALL}/bin/deno" ]]; then
    deno_bin="${DENO_INSTALL}/bin/deno"
  fi
  if [[ -n "$deno_bin" ]]; then
    log "Deno OK ($("$deno_bin" -V 2>/dev/null || echo present))"
    return 0
  fi
  log "installing Deno → ${DENO_INSTALL}"
  curl -fsSL https://deno.land/install.sh | sh
  [[ -x "${DENO_INSTALL}/bin/deno" ]] || die "Deno install failed"
  log "Deno OK ($("${DENO_INSTALL}/bin/deno" -V))"
}

ensure_python_venv() {
  cd "$ROOT"
  have_cmd python3 || die "python3 required"
  if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
    log "creating Python venv at $ROOT/.venv"
    python3 -m venv "$ROOT/.venv"
  fi
  local pip="$ROOT/.venv/bin/pip"
  local py="$ROOT/.venv/bin/python"
  local stamp="$ROOT/.venv/.hiit-reqs.sha256"
  local req_hash
  req_hash="$(sha256sum "$ROOT/requirements.txt" | awk '{print $1}')"
  local need_pip=0
  if [[ ! -f "$stamp" ]] || [[ "$(cat "$stamp" 2>/dev/null || true)" != "$req_hash" ]]; then
    need_pip=1
  elif ! "$py" -c "import telegram, yt_dlp, fastapi, uvicorn, dotenv" >/dev/null 2>&1; then
    need_pip=1
  fi
  if [[ "$need_pip" -eq 1 ]]; then
    log "installing Python packages from requirements.txt"
    "$pip" install --upgrade pip wheel setuptools
    "$pip" install -r "$ROOT/requirements.txt"
    echo "$req_hash" >"$stamp"
  else
    log "Python venv OK"
  fi
  "$py" -c "import telegram, yt_dlp, fastapi, uvicorn, dotenv" \
    || die "Python imports failed after pip install"
}

ensure_web_npm() {
  cd "$ROOT/web"
  local node_bin
  if ! node_bin="$(resolve_node)"; then
    install_node_via_nvm
    node_bin="$(resolve_node)" || die "node not found after install"
  fi
  local npm_bin
  npm_bin="$(dirname "$node_bin")/npm"
  [[ -x "$npm_bin" ]] || npm_bin="$(command -v npm || true)"
  [[ -n "$npm_bin" && -x "$npm_bin" ]] || die "npm not found next to $node_bin"

  export PATH="$(dirname "$node_bin"):${PATH}"

  local stamp="$ROOT/web/node_modules/.hiit-npm.sha256"
  local lock_hash=""
  if [[ -f "$ROOT/web/package-lock.json" ]]; then
    lock_hash="$(sha256sum "$ROOT/web/package-lock.json" | awk '{print $1}')"
  else
    lock_hash="$(sha256sum "$ROOT/web/package.json" | awk '{print $1}')"
  fi
  local need_npm=0
  if [[ ! -f "$ROOT/web/node_modules/next/dist/bin/next" ]]; then
    need_npm=1
  elif [[ ! -f "$stamp" ]] || [[ "$(cat "$stamp" 2>/dev/null || true)" != "$lock_hash" ]]; then
    need_npm=1
  fi
  if [[ "$need_npm" -eq 1 ]]; then
    log "installing web npm packages (Node $($node_bin -v))"
    if [[ -f "$ROOT/web/package-lock.json" ]]; then
      "$npm_bin" ci
    else
      "$npm_bin" install
    fi
    if ! "$node_bin" -e "require('next/package.json')" >/dev/null 2>&1; then
      die "next package broken after npm install"
    fi
    mkdir -p "$ROOT/web/node_modules"
    echo "$lock_hash" >"$stamp"
  else
    log "web node_modules OK"
  fi
  [[ -f "$ROOT/web/node_modules/next/dist/bin/next" ]] || die "Next.js binary missing"
}

ensure_user() {
  cd "$ROOT"
  mkdir -p "$ROOT/downloads" "$ROOT/cache" 2>/dev/null || true
  export PATH="${HOME}/.deno/bin:${PATH}"
  local node_hint=""
  node_hint="$(ls -1d "${HOME}/.nvm/versions/node"/v*/bin /usr/local/nvm/versions/node/*/bin 2>/dev/null | sort -V | tail -1 || true)"
  if [[ -n "$node_hint" ]]; then
    export PATH="${node_hint}:${PATH}"
  fi
  ensure_deno
  ensure_python_venv
  ensure_web_npm
  log "user/project deps OK"
}

case "$MODE" in
  system) ensure_system ;;
  user) ensure_user ;;
  all)
    if [[ "$(id -u)" -eq 0 ]]; then
      ensure_system
      log "running as root — system deps done; run as the service user for --user"
      exit 0
    fi
    if ! have_cmd ffmpeg || ! have_cmd ffprobe || ! have_cmd python3; then
      if have_cmd sudo && sudo -n true 2>/dev/null; then
        log "elevating for system packages"
        sudo -n "$SELF" --system
      else
        log "WARN: missing ffmpeg/python3 and no passwordless sudo"
        log "WARN: install once with: sudo $SELF --system"
        log "WARN: (systemd units should use ExecStartPre=+…/install-deps.sh --system)"
      fi
    else
      # Still ensure the full apt set when we can (idempotent).
      if have_cmd sudo && sudo -n true 2>/dev/null; then
        sudo -n "$SELF" --system
      fi
    fi
    ensure_user
    ;;
esac
