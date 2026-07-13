#!/usr/bin/env bash
# Helper: print credential status + remind of the two setup steps.
# Does NOT steal browser cookies or run Spotify login for you.
set -euo pipefail
cd "$(dirname "$0")"

echo "========== credential status =========="
.venv/bin/python -c "from cred_status import get_credentials_status; print(get_credentials_status()[0])"
echo
echo "========== next steps =========="
echo "YouTube: see SETUP_CREDENTIALS.md §1 (export cookies or YTDLP_COOKIES_FROM_BROWSER=chrome)"
echo "Spotify: ./setup_spotify_creds.sh  (or SETUP_CREDENTIALS.md §2)"
echo
echo "After changes: sudo systemctl restart hiit-radio.service"
