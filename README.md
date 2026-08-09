# HiiT Radio Bot

A Telegram bot that downloads full-length music tracks from Apple Music, Spotify, and plain-text searches. It resolves metadata from the source link, fetches audio via YouTube/SoundCloud, embeds artwork and lyrics, and delivers MP3 files in chat.

The user interface is in **Persian (Farsi)**. Admin tooling and this documentation are in **English**.

## Features

### Downloads
- **Apple Music links** — metadata from the page; audio via YouTube/SoundCloud matching
- **Spotify track links** — metadata from Spotify API/embed; audio via YouTube/SoundCloud
- **Text search** — song or artist name via iTunes lookup + YouTube/SoundCloud
- **Albums & playlists** — unlimited sequential processing with progress and `/cancel`
- **256 kbps MP3** — conversion via FFmpeg; ID3 tags, embedded artwork (HiiT Radio branding), and optional synced/plain lyrics (LRCLIB, Genius, Musixmatch)

### User experience
- Inline mode — search from any chat (`@YourBot song name`)
- Download history — `/history` with one-tap re-download buttons
- Favorites — ❤️ button after download; browse with `/liked`
- Charts — `/top` (`day` / `week` / `all`) from bot download stats
- Recommendations — “More by artist”, “Similar songs”, and lyrics after each track
- Discovery — `/discover` personalized picks via LLM from your download history
- Cancel — `/cancel` stops every background job the user has running (downloads, playlists, LLM calls)
- Rate limiting — daily per-tier quotas (free 10, premium 100, unlimited)
- Instant preview — if the full download takes more than a few seconds, a 30s voice note plays while you wait
- Artwork download — button under each track sends the watermarked cover as a JPEG file
- Subscriptions — free 10/day, premium 100/day, unlimited for admins; buy with Telegram Stars or earn +10 via 3 invites
- File cache — repeated requests served from disk without re-downloading

### Access & admin
- **Channel gate** — users must join a required Telegram channel before using the bot
- **VIP log channel** — every request, download event, startup/shutdown, and error logged to a private admin channel
- **SQLite analytics** — users, downloads, cache stats, platform breakdown
- **Admin broadcast** — `/broadcast` with optional confirmation token
- **Cookie self-service** — send a fresh `cookies.txt` to the bot as a file; it is validated before replacing the old jar

## Prerequisites

- Python 3.10+
- [FFmpeg](https://ffmpeg.org/) on `PATH`
- A Telegram bot token from [@BotFather](https://t.me/BotFather)
- **YouTube login cookies** (required for all downloads) — see [SETUP_CREDENTIALS.md](SETUP_CREDENTIALS.md)

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
| `MAX_ACTIVE_JOBS` | Concurrent background jobs allowed per user (default: 3) |
| `PREVIEW_ENABLED` / `PREVIEW_DELAY_SEC` | 30s preview voice note while a full track downloads |
| `QUOTA_TZ` / `FREE_DAILY_LIMIT` / `PREMIUM_DAILY_LIMIT` | Daily download quota timezone and caps |
| `TOPUP_AMOUNT` / `REFERRALS_PER_TOPUP` | Day-pass size and invites needed for a free top-up |
| `STARS_DAYPASS` / `STARS_WEEKLY` / `STARS_MONTHLY` | Telegram Stars prices |
| `TG_*_TIMEOUT` | Telegram API/upload timeouts for slow VPS links |
| `YTDLP_COOKIES_FROM_BROWSER` | e.g. `chrome` — read live browser cookies |
| `YTDLP_COOKIES` | Path to exported `cookies.txt` |
| `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` | Spotify Web API (metadata only) |
| `LLM_API_BASE` / `LLM_API_KEY` / `LLM_MODEL` | LLM for `/discover` recommendations |
| `DEVELOPER_NAME` / `DEVELOPER_USERNAME` | Developer info shown by `/aboutme` |
| `GENIUS_API_TOKEN` / `MUSIXMATCH_API_KEY` | Optional lyrics providers |

### Credentials

Full-track downloads require **YouTube** logged-in cookies for yt-dlp.

`SPOTIFY_CLIENT_ID` / `SECRET` are optional and only improve metadata on Spotify links; they do not download audio.

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

Restart the bot whenever you update cookies or environment variables.

## Commands

### User commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and quick guide |
| `/help` | Usage, inline mode, rate limits |
| `/history` | Recent downloads with re-download buttons |
| `/discover` | Personalized song recommendations (LLM + download history) |
| `/premium` | View tier/quota and buy day-pass or premium with Stars |
| `/invite` | Personal invite link (3 verified joins = +10 today) |
| `/liked` | Saved favorites |
| `/top` | Charts |
| `/aboutme` | About the bot and developer (Persian) |
| `/cancel` | Stop any background job |

Send a track link, album/playlist URL, or plain song name as a normal message to download.

### Admin commands

| Command | Description |
|---------|-------------|
| `/stats` | Users, downloads, cache hit rate, top artists/songs |
| `/analytics` | Alias for `/stats` |
| `/report` | Full admin dashboard with inline drill-down menus |
| `/users [page]` | Paginated user list |
| `/user <id>` | User profile, downloads, requests, LLM usage |
| `/export` | Download full database export as JSON |
| `/creds` | YouTube credential readiness report |
| `/cookies` | Cookie jar health; send a `cookies.txt` file to the bot to replace it |
| `/channelid` | Resolve chat ID for VIP log channel setup |
| `/viplogtest` | Test VIP log channel (admin) |
| `/grant <user_id> <premium\|unlimited> <days>` | Manually activate a subscription |
| `/topup <user_id> [amount]` | Manually add today's download bonus |
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
| `download_orchestrator.py` | Cache-aware unified download pipeline |
| `cache_manager.py` | Disk cache with TTL and Telegram `file_id` reuse |
| `playlist_handler.py` | Sequential album/playlist downloads |
| `lyrics_service.py` | LRCLIB / Genius / Musixmatch fetch |
| `database.py` | SQLite schema, analytics, download history |
| `user_manager.py` | Users, rate limits, download recording |
| `gates.py` | Required-channel membership check |
| `jobs.py` | Per-user registry of cancellable background work |
| `admin_logger.py` | VIP channel activity logging |
| `progress.py` | Throttled in-chat progress updates |
| `preview.py` | Delayed 30s preview voice notes during slow downloads |
| `entitlements.py` | Daily quotas, tiers, and day-pass bonuses |
| `payments.py` | Telegram Stars invoices and manual grants |
| `referrals.py` | Invite deep-links and top-up rewards |
| `recommendations.py` | Post-download inline keyboard |
| `llm_service.py` | LLM recommendations for `/discover` |
| `reporting.py` | Admin report formatters and pagination keyboards |
| `messages.py` | User-facing Persian copy and `/aboutme` text |
| `cred_status.py` | Credential health report for `/creds` |

Runtime directories (gitignored): `downloads/`, `cache/`, `hiit_radio.db`, `cookies.txt`.

## Migrating from users.json

If you have an older `users.json` deployment:

```bash
.venv/bin/python migrate_json_to_sqlite.py
```

## License

MIT
