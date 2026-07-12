# HiiT Radio Bot

A Telegram bot that downloads full-length music tracks from Apple Music, Spotify, and plain-text searches. It resolves metadata from the source link, fetches audio via YouTube/SoundCloud (with optional direct Spotify downloads), embeds artwork and lyrics, and delivers MP3 files in chat.

The user interface is in **Persian (Farsi)**. Admin tooling and this documentation are in **English**.

## Features

### Downloads
- **Apple Music links** — metadata from the page; audio via YouTube/SoundCloud matching
- **Spotify track links** — full download via [zotify](https://github.com/Googolplexed0/zotify) when Premium credentials are configured; otherwise YouTube/SoundCloud fallback
- **Text search** — song or artist name via iTunes lookup + YouTube/SoundCloud
- **Albums & playlists** — unlimited sequential processing with progress and `/cancel`
- **256 kbps MP3** — conversion via FFmpeg; ID3 tags, embedded artwork (HiiT Radio branding), and optional synced/plain lyrics (LRCLIB, Genius, Musixmatch)

### User experience
- Inline mode — search from any chat (`@YourBot song name`)
- Download history — `/history` with one-tap re-download buttons
- Recommendations — “More by artist” / “Similar songs” after each track
- Discovery — `/discover` based on listening history
- Curated search — `/search genre:lofi mood:chill` (see `search_mappings.json`)
- Rate limiting — 10 downloads per hour per user (each playlist track counts separately)
- File cache — repeated requests served from disk without re-downloading

### Access & admin
- **Channel gate** — users must join a required Telegram channel before using the bot
- **VIP log channel** — every request, download event, startup/shutdown, and error logged to a private admin channel
- **SQLite analytics** — users, downloads, cache stats, platform breakdown
- **Admin broadcast** — `/broadcast` with optional confirmation token

## Prerequisites

- Python 3.10+
- [FFmpeg](https://ffmpeg.org/) on `PATH`
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- **YouTube login cookies** (required for Apple Music links and most searches) — see [SETUP_CREDENTIALS.md](SETUP_CREDENTIALS.md)
- **Spotify Premium + zotify credentials** (optional, for direct Spotify full tracks) — see [SETUP_CREDENTIALS.md](SETUP_CREDENTIALS.md)

Enable **inline mode** in BotFather if you want inline search.

For private channels (membership gate or VIP logging), add the bot as a **channel administrator**.

## Installation

```bash
git clone <repository-url>
cd hiit-radio-bot

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

Copy the environment template and fill in your values:

```bash
cp .env.example .env
```

## Configuration

All settings live in `.env`. See `.env.example` for the full list.

| Variable | Description |
|----------|-------------|
| `BOT_TOKEN` | Telegram bot token (required) |
| `ADMIN_ID` | Your Telegram user ID (required for admin commands) |
| `REQUIRED_CHANNEL` | Channel users must join (`@username` or numeric ID) |
| `VIP_LOG_CHANNEL_ID` | Private channel ID for admin logs (empty = disabled) |
| `DATABASE_PATH` | SQLite database file (default: `hiit_radio.db`) |
| `CACHE_DIR` / `CACHE_TTL_HOURS` | On-disk download cache |
| `YTDLP_COOKIES_FROM_BROWSER` | e.g. `chrome` — read live browser cookies |
| `YTDLP_COOKIES` | Path to exported `cookies.txt` |
| `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` | Spotify Web API (metadata only) |
| `SPOTIFY_CREDENTIALS` | Path to zotify `credentials.json` (full Spotify downloads) |
| `SPOTIFY_USERNAME` | Spotify username for zotify |
| `GENIUS_API_TOKEN` / `MUSIXMATCH_API_KEY` | Optional lyrics providers |

### Credentials

Full-track downloads depend on two separate credential systems:

1. **YouTube** — logged-in cookies for yt-dlp (Apple Music, search, fallbacks)
2. **Spotify (zotify)** — one-time OAuth `credentials.json` for Premium full tracks

`SPOTIFY_CLIENT_ID` / `SECRET` alone only resolve metadata; they do not download audio.

Follow **[SETUP_CREDENTIALS.md](SETUP_CREDENTIALS.md)** for step-by-step setup.

Check status anytime (admin):

```text
/creds
```

Or from the shell:

```bash
.venv/bin/python -c "from cred_status import get_credentials_status; print(get_credentials_status()[0])"
```

### VIP log channel ID

As admin, run `/channelid` in the VIP channel (or forward a channel post to the bot) to get the numeric chat ID for `VIP_LOG_CHANNEL_ID`.

## Running the bot

Development:

```bash
source .venv/bin/activate
python main.py
```

### VPS / systemd deployment

Your service unit must use the **virtualenv interpreter**, and **all** dependencies must be installed **into that venv** — not with system `pip` or `pip3`.

```bash
cd /home/babak/hiit-radio

# Create venv if missing
python3 -m venv .venv

# Install into the SAME Python systemd runs
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# Verify (must print a path under .venv and no error)
.venv/bin/python -c "from dotenv import load_dotenv; print('OK')"
```

Example `/etc/systemd/system/hiit-radio-bot.service`:

```ini
[Service]
User=babak
WorkingDirectory=/home/babak/hiit-radio
EnvironmentFile=/home/babak/hiit-radio/.env
ExecStart=/home/babak/hiit-radio/.venv/bin/python /home/babak/hiit-radio/main.py
Restart=on-failure
RestartSec=10
```

Ensure `.env` exists on the VPS (it is gitignored — copy it manually):

```bash
ls -la /home/babak/hiit-radio/.env
grep BOT_TOKEN /home/babak/hiit-radio/.env   # must show BOT_TOKEN=123456:ABC...
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable hiit-radio-bot.service
sudo systemctl restart hiit-radio-bot.service
sudo journalctl -u hiit-radio-bot.service -f
```

**Common mistake:** running `pip install python-dotenv` or `pip3 install -r requirements.txt` without activating the venv (or without using `.venv/bin/pip`). That installs packages for system Python while systemd runs `.venv/bin/python`, which causes `ModuleNotFoundError: No module named 'dotenv'`.

Production (example systemd unit):

```bash
sudo systemctl start hiit-radio.service
sudo systemctl restart hiit-radio.service   # after .env or credential changes
```

Restart the bot whenever you update cookies, Spotify credentials, or environment variables.

## Commands

### User commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and quick guide |
| `/help` | Usage, inline mode, rate limits, search syntax |
| `/history` | Recent downloads with re-download buttons |
| `/discover` | Personalized suggestions from your history |
| `/search` | Curated genre/mood/decade search (e.g. `/search genre:lofi`) |
| `/cancel` | Stop an in-progress playlist download |

Send a track link, album/playlist URL, or plain song name as a normal message to download.

### Admin commands

| Command | Description |
|---------|-------------|
| `/stats` | Users, downloads, cache hit rate, top artists/songs |
| `/analytics` | Alias for `/stats` |
| `/creds` | YouTube + Spotify credential readiness report |
| `/channelid` | Resolve chat ID for VIP log channel setup |
| `/broadcast <message>` | Send a message to all known users (confirmation step) |

## Download flow

```text
User message (link / search / playlist)
        │
        ▼
  Channel membership gate
        │
        ▼
  Metadata resolution (Apple / Spotify API or embed / iTunes)
        │
        ▼
  Cache lookup ──hit──► send cached MP3
        │
       miss
        │
        ▼
  Spotify link + zotify configured? ──yes──► zotify full download
        │
        no / failed
        │
        ▼
  YouTube match (yt-dlp + cookies) ──► SoundCloud fallback
        │
        ▼
  Embed lyrics, write cache, send MP3 + recommendation buttons
```

Users only see simple result messages. Technical details (credential status, backend errors) are written to the VIP log channel, not shown in chat.

## Project structure

| File | Role |
|------|------|
| `main.py` | Bot entry point, handlers, startup/shutdown hooks |
| `metadata.py` | Apple Music, Spotify, iTunes metadata and playlist expansion |
| `downloader.py` | yt-dlp download, FFmpeg conversion, ID3/artwork/lyrics |
| `spotify_downloader.py` | Full Spotify tracks via zotify |
| `download_orchestrator.py` | Cache-aware unified download pipeline |
| `cache_manager.py` | Disk cache with TTL and Telegram `file_id` reuse |
| `playlist_handler.py` | Sequential album/playlist downloads |
| `lyrics_service.py` | LRCLIB / Genius / Musixmatch fetch |
| `database.py` | SQLite schema, analytics, download history |
| `user_manager.py` | Users, rate limits, download recording |
| `gates.py` | Required-channel membership check |
| `admin_logger.py` | VIP channel activity logging |
| `progress.py` | Throttled in-chat progress updates |
| `recommendations.py` | Post-download inline keyboard |
| `search_parser.py` | `/search` command parsing |
| `cred_status.py` | Credential health report for `/creds` |
| `search_mappings.json` | Genre/mood/decade → iTunes query map |

Runtime directories (gitignored): `downloads/`, `cache/`, `hiit_radio.db`, `cookies.txt`, `credentials.json`.

## Migrating from users.json

If you have an older `users.json` deployment:

```bash
.venv/bin/python migrate_json_to_sqlite.py
```

## License

MIT
