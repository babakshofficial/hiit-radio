# Full-download credentials setup (YouTube + Spotify)

You need **two** credential systems. `SPOTIFY_CLIENT_ID` / `SECRET` alone are **not** enough for full audio.

| Path | Used for | Credential |
|------|----------|------------|
| YouTube | Apple Music links, text search, most non-Spotify | Logged-in `cookies.txt` **or** `YTDLP_COOKIES_FROM_BROWSER` |
| Spotify full | Spotify track links → real file via zotify | `credentials.json` from Premium OAuth |
| Spotify API | Title/artist/artwork only (optional) | `SPOTIFY_CLIENT_ID` / `SPOTIFY_CLIENT_SECRET` |

Check anytime with Telegram admin command:

```text
/creds
```

Or in the project folder:

```bash
.venv/bin/python -c "from cred_status import get_credentials_status; print(get_credentials_status()[0])"
```

---

## 1) YouTube (required for Apple Music / search)

### Option A — browser cookies (recommended on desktop)

1. Open Chrome, go to https://www.youtube.com and **sign in**.
2. Fully quit Chrome (cookies DB may be locked while Chrome runs).
3. From the project directory:

```bash
cd /home/babak/Desktop/Projects/hiit-radio-bot
.venv/bin/yt-dlp --cookies-from-browser chrome --cookies cookies.txt "ytsearch1:test" --skip-download
```

4. Confirm login cookies exist:

```bash
grep -E 'LOGIN_INFO|SAPISID' cookies.txt
```

5. Restart the bot:

```bash
sudo systemctl restart hiit-radio.service
```

Or put this in `.env` and restart (yt-dlp reads Chrome each time):

```bash
YTDLP_COOKIES_FROM_BROWSER=chrome
```

### Option B — browser extension

1. Sign into YouTube in the browser.
2. Use an extension such as **Get cookies.txt LOCALLY**.
3. Export Netscape cookies for `youtube.com`.
4. Replace project `cookies.txt` with that file.
5. Restart `hiit-radio.service`.

A **valid** file must include names like `LOGIN_INFO`, `SAPISID`, or `__Secure-1PSID`.  
Anonymous-only cookies (`PREF`, `SOCS`, `YSC`, …) will still get **“Sign in to confirm you’re not a bot”**.

---

## 2) Spotify full track (zotify + Premium)

Do this once. Requires a **Spotify Premium** account.

**Quick setup (recommended):**

```bash
cd /home/babak/Desktop/Projects/hiit-radio-bot
./setup_spotify_creds.sh
```

The script opens zotify's browser login, writes `credentials.json`, and prints what to add to `.env`.

**Manual setup** (same result):

```bash
cd /home/babak/Desktop/Projects/hiit-radio-bot
.venv/bin/zotify "https://open.spotify.com/track/0pwcqlr371jm1u0WCPtbx5" \
  --credentials-location ./credentials.json \
  --save-credentials True \
  --root-path ./downloads \
  --codec mp3 \
  --no-splash
```

1. Open the URL zotify prints and log in with Premium.
2. When it finishes writing `credentials.json`, optionally add to `.env`:

```bash
SPOTIFY_CREDENTIALS=/home/babak/Desktop/Projects/hiit-radio-bot/credentials.json
SPOTIFY_USERNAME=your_spotify_username
```

3. Restart:

```bash
sudo systemctl restart hiit-radio.service
```

4. Verify:

```bash
.venv/bin/python -c "from spotify_downloader import SpotifyFullDownloader; print(SpotifyFullDownloader().is_configured())"
```

Must print `True`.

Free accounts cannot download full tracks (audio key errors). Credentials can expire; re-run the zotify login if downloads start failing.

---

## 3) Spotify Web API (metadata only — already in your `.env`)

```bash
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...
```

- Used only to resolve track title/artist/artwork when possible.
- **Premium required** on the Developer Dashboard account (since Feb 2026) for Web API access in Development Mode. Without Premium, API calls return **403** even when the token is acquired successfully.
- If Spotify returns **403** (or API is otherwise unavailable), the bot falls back to the public embed page for **tracks, albums, and playlists** — no token needed.
- This never downloads the full song. Full Spotify downloads still require zotify Premium credentials (section 2), separate from the Web API.

---

## Flow after both are set

1. **Spotify link** → try zotify full download first → else YouTube/SoundCloud.  
2. **Apple Music / text** → YouTube (needs cookies) → SoundCloud.  
3. No 30-second preview fallback — failure means full track not found.

Restart after any credential change:

```bash
sudo systemctl restart hiit-radio.service
```

---

## VPS migration (PC works, server does not)

Git does **not** copy `cookies.txt`, `credentials.json`, or `.env`. You must deploy them manually.

### Checklist

1. **Copy secrets to the VPS**
   ```bash
   scp .env cookies.txt credentials.json babak@your-vps:/home/babak/hiit-radio/
   ```

2. **Use `cookies.txt`, not browser cookies**
   - `YTDLP_COOKIES_FROM_BROWSER=chrome` only works on your PC (Chrome installed + logged in).
   - On the VPS, set:
     ```env
     YTDLP_COOKIES=/home/babak/hiit-radio/cookies.txt
     ```
   - Comment out or remove `YTDLP_COOKIES_FROM_BROWSER` in `.env`.
   - The bot now prefers authenticated `cookies.txt` over the browser setting when both exist.

3. **Install FFmpeg on the VPS**
   ```bash
   sudo apt update && sudo apt install -y ffmpeg
   ```

4. **Proxy (if your PC uses proxychains)**
   - If the bot on your PC runs behind `proxychains4`, the VPS needs the same reachability.
   - Either add to `.env`:
     ```env
     YTDLP_PROXY=socks5://127.0.0.1:1080
     ```
   - Or change systemd `ExecStart` to use proxychains like on your desktop.

5. **Run the diagnostic script on the VPS**
   ```bash
   cd /home/babak/hiit-radio
   chmod +x vps_diagnose.sh
   ./vps_diagnose.sh
   ```

6. **Re-run Spotify login on VPS** (if `credentials.json` was never copied)
   - See section 2 above; zotify OAuth must be done once per server.

7. **Verify in Telegram (admin)**
   ```text
   /creds
   ```
   YouTube must show ✓ for `cookies.txt`, not only browser.

### Refresh cookies periodically

YouTube cookies expire. When downloads start failing everywhere, re-export `cookies.txt` on your PC and `scp` it to the VPS again.
