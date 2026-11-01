# Operations

## SQLite backup

- Stop the bot briefly or use SQLite online backup: `sqlite3 hiit_radio.db ".backup 'hiit_radio-$(date +%F).db'"`.
- Copy `user_music/` if you use community submissions.
- Restore: replace `hiit_radio.db` (or `DATABASE_PATH`) and restart `hiit-radio.service`.

## Command menu sync

- On startup the bot backfills up to 200 users per batch (loops until done).
- Admin: `/syncmenus` forces a full backfill for users where `commands_lang != language`.

## Health checks

- `scripts/check_smoke.py` — metadata, locales, DB init (no Telegram).
- `scripts/check_locales.py` — all locale key sets match English.
- `scripts/check_security.py` — URL allowlist, redirect, cookie and API auth checks.

## Channel gate

- Default: membership check errors **fail open** (users pass) so a misconfigured gate does not brick the bot.
- Set `CHANNEL_GATE_FAIL_CLOSED=1` after `validate_channel_gate` succeeds at startup to deny access when Telegram cannot verify membership.

## API secrets

- `JWT_SECRET` is required: 32+ characters, different from `BOT_TOKEN`. The API refuses to start otherwise. Generate one with `openssl rand -hex 32`. Changing it logs out web sessions.

## File permissions

- Secrets (`.env`, `cookies.txt`, `credentials.json`, `hiit_radio.db*`) should be mode 600, and the checkout closed to other users (`chmod -R g-w,o-rwx .`).

## Payments

- A Stars charge and what it delivers are saved in one database transaction.
- `reconcile_star_transactions` runs hourly and at startup. It compares the last 3 days of Telegram's transaction list with `payments`, and applies anything missed.
- `/payments` lists charges and `/refund <number>` refunds one. Refunding a gift returns the money to the buyer and removes the gift from whoever redeemed it.
- `/terms` and `/paysupport` are always available, even to users who haven't joined the required channel.

## Song recognition

- It uses `shazamio`, an unofficial client. If Shazam changes its API, users see "not available" and the rest of the bot keeps working.
- Clips go to Shazam and aren't kept. Audio files still start the `/submit` flow, so they aren't recognized.

## YouTube access

- Downloads run without cookies. A configured jar or browser is tried only after YouTube refuses a cookieless attempt (bot check, age or members-only, or no formats).
- If you do configure cookies, use a throwaway Google account, never a personal one.
- Exports and uploads keep only YouTube, Google and SoundCloud cookies and are written with mode 600.
