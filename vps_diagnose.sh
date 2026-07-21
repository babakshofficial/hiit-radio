#!/usr/bin/env bash
# Run on the VPS to find why downloads fail (credentials, ffmpeg, network).
set -euo pipefail
cd "$(dirname "$0")"

PY="${PY:-.venv/bin/python}"
YTDLP="${YTDLP:-.venv/bin/yt-dlp}"

echo "========== HiiT Radio VPS diagnose =========="
echo "Project: $(pwd)"
echo

echo "--- Python / venv ---"
if [[ -x "$PY" ]]; then
  "$PY" -c "import sys; print('Python:', sys.executable)"
else
  echo "FAIL: $PY not found — run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi
echo

echo "--- .env ---"
if [[ -f .env ]]; then
  echo "OK: .env exists"
  grep -E '^BOT_TOKEN=|^VIP_LOG|^YTDLP_|^SPOTIFY_' .env | sed 's/BOT_TOKEN=.*/BOT_TOKEN=***hidden***/' || true
  if ! grep -q '^VIP_LOG_CHANNEL_ID=.\+' .env 2>/dev/null; then
    echo "WARN: VIP_LOG_CHANNEL_ID not set — admin logs disabled"
  fi
else
  echo "FAIL: .env missing"
fi
echo

echo "--- FFmpeg (required for MP3 conversion) ---"
if command -v ffmpeg >/dev/null 2>&1; then
  ffmpeg -version | head -1
else
  echo "FAIL: ffmpeg not installed — run: sudo apt install ffmpeg"
fi
echo

echo "--- YouTube cookies ---"
COOKIES="${YTDLP_COOKIES:-$(pwd)/cookies.txt}"
if [[ -f "$COOKIES" ]]; then
  echo "OK: cookies file exists: $COOKIES ($(wc -c < "$COOKIES") bytes)"
  if grep -qE 'LOGIN_INFO|SAPISID|__Secure-1PSID' "$COOKIES"; then
    echo "OK: logged-in cookie names found"
  else
    echo "FAIL: no login cookies — export from PC while signed into youtube.com"
  fi
else
  echo "FAIL: cookies.txt missing at $COOKIES"
  echo "     Copy from your PC: scp cookies.txt babak@your-vps:/home/babak/hiit-radio/cookies.txt"
fi
if grep -q '^YTDLP_COOKIES_FROM_BROWSER=' .env 2>/dev/null; then
  echo "NOTE: YTDLP_COOKIES_FROM_BROWSER is set — ignored if authenticated cookies.txt exists"
  echo "      On VPS, rely on cookies.txt (no Chrome browser)"
fi
echo

echo "--- Credential status (bot /creds) ---"
"$PY" -c "from cred_status import get_credentials_status; print(get_credentials_status()[0])"
echo

echo "--- yt-dlp live test (search only, no download) ---"
if [[ -x "$YTDLP" ]]; then
  set +e
  COOKIE_ARG=()
  [[ -f "$COOKIES" ]] && COOKIE_ARG=(--cookies "$COOKIES")
  OUT=$("$YTDLP" "${COOKIE_ARG[@]}" --flat-playlist --print title "ytsearch1:rick astley never gonna give you up" 2>&1)
  RC=$?
  set -e
  if [[ $RC -eq 0 ]]; then
    echo "OK: YouTube search works"
    echo "$OUT" | head -3
  else
    echo "FAIL: YouTube search blocked or unreachable"
    echo "$OUT" | tail -8
    echo
    echo "Export fresh logged-in cookies.txt (non-empty SID/__Secure-*PSID) and restart the bot."
  fi
else
  echo "SKIP: yt-dlp not in venv"
fi
echo
echo "========== done =========="
