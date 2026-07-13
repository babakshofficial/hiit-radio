#!/usr/bin/env bash
# One-time Spotify Premium login via zotify → credentials.json
# Run from the project directory on a machine with a browser (or copy credentials.json to VPS).
set -euo pipefail
cd "$(dirname "$0")"

CREDS="${SPOTIFY_CREDENTIALS:-$(pwd)/credentials.json}"
ZOTIFY=".venv/bin/zotify"
TEST_TRACK="https://open.spotify.com/track/0pwcqlr371jm1u0WCPtbx5"
DOWNLOADS="$(pwd)/downloads"

echo "========== Spotify full-download setup (zotify) =========="
echo

if [[ ! -x "$ZOTIFY" ]]; then
    echo "ERROR: zotify not found at $ZOTIFY"
    echo "Install deps: .venv/bin/pip install -r requirements.txt"
    exit 1
fi

if [[ -f "$CREDS" ]]; then
    echo "Found existing credentials: $CREDS"
    read -r -p "Overwrite with a fresh login? [y/N] " ans
    if [[ "${ans,,}" != "y" ]]; then
        echo "Keeping existing file."
        .venv/bin/python -c "from spotify_downloader import SpotifyFullDownloader; print('is_configured:', SpotifyFullDownloader().is_configured())"
        exit 0
    fi
    rm -f "$CREDS"
fi

echo "Requirements:"
echo "  • Spotify Premium account"
echo "  • Network access to Spotify (use proxychains if needed on your setup)"
echo
echo "Steps:"
echo "  1. zotify will print a login URL — open it in your browser"
echo "  2. Log in with Premium and approve access"
echo "  3. zotify downloads a short test track and writes credentials.json"
echo
read -r -p "Press Enter to start (Ctrl+C to cancel)..."

mkdir -p "$DOWNLOADS"

# If proxychains is available and Spotify is blocked direct, wrap the call.
if command -v proxychains4 >/dev/null 2>&1; then
    echo "(using proxychains4)"
    RUN=(proxychains4 -q "$ZOTIFY")
else
    RUN=("$ZOTIFY")
fi

"${RUN[@]}" "$TEST_TRACK" \
    --credentials-location "$CREDS" \
    --save-credentials True \
    --root-path "$DOWNLOADS" \
    --codec mp3 \
    --no-splash

echo
if [[ ! -f "$CREDS" ]]; then
    echo "ERROR: credentials.json was not created at $CREDS"
    exit 1
fi

echo "✓ credentials.json created: $CREDS"
echo
echo "Add to .env (if not already):"
echo "  SPOTIFY_CREDENTIALS=$CREDS"
echo "  SPOTIFY_USERNAME=your_spotify_username"
echo
echo "Verify:"
.venv/bin/python -c "from spotify_downloader import SpotifyFullDownloader; print('is_configured:', SpotifyFullDownloader().is_configured())"
echo
echo "Restart the bot:"
echo "  sudo systemctl restart hiit-radio.service"
echo
echo "Check in Telegram (admin): /creds"
