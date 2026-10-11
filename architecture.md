# HIIT Radio — architecture

Telegram bot + optional FastAPI backend + Next.js Mini App. Single SQLite database (`hiit_radio.db` or `DATABASE_PATH`).

## Processes

| Process | Entry | Role |
|---------|--------|------|
| Bot | `main.py` | Commands, callbacks, downloads, admin, Stars payments |
| API | `api/main.py` (uvicorn) | Web/Mini App auth, jobs, file URLs |
| Web | `web/` (Next.js) | Mini App UI |

Set `MENU_BUTTON_MODE=commands` (default) or `webapp` with HTTPS `WEBAPP_URL`.

## Download path

1. User sends link or text → `TrackMetadata.create` (Apple/Spotify/Deezer/catalog/community).
2. `DownloadOrchestrator.get_or_download` → cache → `MusicDownloader.download_song` (YouTube/SoundCloud).
3. Artwork watermark, MP3 tags, Telegram send; history and quota in SQLite.

## Data

- **Users:** language, commands_lang, quota, subscriptions, favorites, follows.
- **Cache:** file paths + optional `telegram_file_id`.
- **Community:** `user_music_submissions` → approved tracks in catalog search.
- **Changelog:** pending file + `changelog_entries` for skipped broadcasts.

## Localization

- `locales/*.py` + `messages.py` contextvar; per-user Telegram command menus via `bot_commands.refresh_user_commands`.

## Security notes

- Channel gate (`gates.py`), JWT for API (`api/auth.py`), signed file URLs with path allowlist under `cache/`, `downloads/`, `user_music/`.
- Admin Telegram ID via `ADMIN_ID`; shared checks in `admin_guards.py`.
