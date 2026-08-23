# HiiT Radio Web + Mini App

Persian RTL web app and Telegram Mini App sharing the bot’s users, quotas, and downloads.

## Architecture

| Process | Command | Port |
|---------|---------|------|
| Telegram bot | `.venv/bin/python main.py` | — (polling) |
| HTTP API | `.venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000` | 8000 |
| Frontend | `cd web && npm run dev` | 3000 |

Set in root `.env`:

- `WEBAPP_URL` — URL of the Next.js app (Mini App URL). Local dev: `http://127.0.0.1:3000`
- `API_PUBLIC_URL` — public URL of FastAPI for signed MP3 links. Leave empty for same-origin `/backend`
- `JWT_SECRET` — dedicated secret in production
- `CORS_ORIGINS` — include your web origin
- `BOT_USERNAME` — without `@` (Login Widget + invite links)

Frontend: copy `web/.env.local.example` → `web/.env.local`. Default `NEXT_PUBLIC_API_URL=/backend` (Next.js rewrites that path to FastAPI on port 8000).

## Local development

```bash
.venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000
cd web && npm run dev
```

Open http://127.0.0.1:3000. The API is at http://127.0.0.1:3000/backend/… via the Next.js rewrite.

For local `.env`:

```env
WEBAPP_URL=http://127.0.0.1:3000
CORS_ORIGINS=http://127.0.0.1:3000,http://localhost:3000
API_PUBLIC_URL=
```

## Public HTTPS (production Mini App)

Telegram Mini Apps and the Login Widget need a public **HTTPS** URL. Run the stack on a VPS (or any host with a real domain) and put **nginx** or **Caddy** in front:

- `https://your-domain.com` → `http://127.0.0.1:3000` (Next.js)
- API stays same-origin at `/backend` (no separate public API hostname required)

Then set:

```env
WEBAPP_URL=https://your-domain.com
CORS_ORIGINS=https://your-domain.com
API_PUBLIC_URL=
```

Restart the bot/API after changing `.env`.

## BotFather / Telegram setup

1. **Mini App:** BotFather → Bot Settings → Menu Button / Configure Mini App → URL = `WEBAPP_URL`
2. On bot startup, if `WEBAPP_URL` is set, the bot also calls `setChatMenuButton` automatically
3. **Login Widget (browser):** BotFather → Bot Settings → Domain → add your web domain (hostname only, no `https://`)
4. Stars checkout works inside the Mini App via `openInvoice`; on the standalone web app, premium deep-links into the bot

## systemd (bot + API + web)

One unit starts the Telegram bot, FastAPI (`127.0.0.1:8000`), and Next.js (`127.0.0.1:3000`) via `scripts/hiit-radio-stack.sh`.

Build the frontend once (or after UI changes):

```bash
cd /home/babak/Desktop/Projects/hiit-radio-bot/web && npm run build
```

Install and start:

```bash
sudo cp /home/babak/Desktop/Projects/hiit-radio-bot/deploy/hiit-radio.service /etc/systemd/system/hiit-radio.service
sudo systemctl daemon-reload
sudo systemctl enable --now hiit-radio.service
sudo journalctl -u hiit-radio.service -f
```

## Auth

- Inside Telegram: validates WebApp `initData`, issues JWT
- Outside: Telegram Login Widget → JWT
- Never expose `BOT_TOKEN` to the browser
