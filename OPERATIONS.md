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

## Channel gate

- Default: membership check errors **fail open** (users pass) so a misconfigured gate does not brick the bot.
- Set `CHANNEL_GATE_FAIL_CLOSED=1` after `validate_channel_gate` succeeds at startup to deny access when Telegram cannot verify membership.

## API secrets

- Set a dedicated `JWT_SECRET` (24+ chars). Use `API_STRICT_SECRETS=1` to refuse startup with a weak secret.
