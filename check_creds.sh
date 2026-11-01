#!/usr/bin/env bash
# Helper: print credential status + remind of the two setup steps.
# Does NOT steal browser cookies or run Spotify login for you.
set -euo pipefail
cd "$(dirname "$0")"

echo "========== credential status =========="
.venv/bin/python -c "from cred_status import get_credentials_status; print(get_credentials_status()[0])"
echo
echo "========== next steps =========="
echo "YouTube: no cookies needed; see SETUP_CREDENTIALS.md §1 if YouTube blocks this IP"
echo
echo "After changes: sudo systemctl restart hiit-radio.service"
