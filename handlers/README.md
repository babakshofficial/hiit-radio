# Telegram handlers (planned split)

`main.py` currently registers all commands and callbacks (~4.5k lines). A future refactor (audit S8) can move:

- `handlers/menu.py` — start, help, language, inline main menu
- `handlers/download.py` — track jobs, playlists, search
- `handlers/admin.py` — admin panel, wizard entry points
- `bootstrap.py` — `Application` build and `post_init`

Until then, keep new handlers in dedicated modules and import them from `main.py` to limit growth.
