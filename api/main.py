"""FastAPI application for HIIT Radio web + Mini App."""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from api import auth, config
from api.auth import get_current_user, require_admin
from api.deps import get_bot, get_db, get_user_manager, ydl_opts_factory
from api.jobs import jobs
from metadata import TrackMetadata

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="HIIT Radio API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class WebAppAuthBody(BaseModel):
    initData: str


class LoginWidgetBody(BaseModel):
    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str


class ResolveBody(BaseModel):
    query: str = Field(min_length=1, max_length=2000)


class JobBody(BaseModel):
    query: str = Field(min_length=1, max_length=2000)


class FavBody(BaseModel):
    title: str
    artist: Optional[str] = None
    album: Optional[str] = None
    content_key: Optional[str] = None


class InvoiceBody(BaseModel):
    kind: str


class AdminGrantBody(BaseModel):
    user_id: str
    tier: str = "premium"
    days: int = 30


class AdminTopupBody(BaseModel):
    user_id: str
    amount: Optional[int] = None


class AdminBroadcastBody(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


def _touch(user: dict):
    get_user_manager().touch_user(
        user["id"],
        username=user.get("username"),
        first_name=user.get("first_name"),
    )


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/auth/telegram-webapp")
async def auth_webapp(body: WebAppAuthBody):
    parsed = auth.validate_webapp_init_data(body.initData)
    user = parsed["user"]
    um = get_user_manager()
    um.touch_user(user["id"], username=user.get("username"), first_name=user.get("first_name"))
    token = auth.issue_token(user)
    return {
        "token": token,
        "user": {
            "id": str(user["id"]),
            "username": user.get("username"),
            "first_name": user.get("first_name"),
            "last_name": user.get("last_name"),
            "photo_url": user.get("photo_url"),
            "is_admin": bool(config.ADMIN_ID) and str(user["id"]) == str(config.ADMIN_ID),
        },
    }


@app.post("/auth/telegram-login")
async def auth_login(body: LoginWidgetBody):
    parsed = auth.validate_login_widget(body.model_dump())
    user = parsed["user"]
    um = get_user_manager()
    um.touch_user(user["id"], username=user.get("username"), first_name=user.get("first_name"))
    token = auth.issue_token(user)
    return {
        "token": token,
        "user": {
            "id": str(user["id"]),
            "username": user.get("username"),
            "first_name": user.get("first_name"),
            "last_name": user.get("last_name"),
            "photo_url": user.get("photo_url"),
            "is_admin": bool(config.ADMIN_ID) and str(user["id"]) == str(config.ADMIN_ID),
        },
    }


@app.get("/me")
async def me(user=Depends(get_current_user)):
    import entitlements

    _touch(user)
    snap = entitlements.status_snapshot(get_db(), user["id"])
    return {
        "user": user,
        "quota": snap,
        "bot_username": config.BOT_USERNAME,
        "webapp_url": config.WEBAPP_URL,
    }


@app.get("/access")
async def access(user=Depends(get_current_user)):
    import gates

    _touch(user)
    bot = get_bot()
    channel = gates.REQUIRED_CHANNEL_RAW
    if not gates.REQUIRED_CHANNEL:
        return {"allowed": True, "channel": None, "join_url": None}
    if not bot:
        return {"allowed": True, "channel": channel, "join_url": f"https://t.me/{channel.lstrip('@')}", "warning": "no_bot"}
    ok = await gates.is_member(bot, int(user["id"]))
    if ok:
        try:
            import referrals

            referrals.maybe_credit_on_membership(get_db(), user["id"])
        except Exception:
            logger.debug("referral credit skipped", exc_info=True)
    return {
        "allowed": ok,
        "channel": channel,
        "join_url": f"https://t.me/{channel.lstrip('@')}",
    }


@app.post("/resolve")
async def resolve(body: ResolveBody, user=Depends(get_current_user)):
    _touch(user)
    text = body.query.strip()
    name, tracks = await TrackMetadata.create_collection(text, ydl_opts_factory)
    if tracks:
        return {
            "kind": "collection",
            "name": name,
            "tracks": [
                {
                    "title": t.title,
                    "artist": t.artist,
                    "album": t.album,
                    "artwork_url": t.artwork_url,
                    "url": t.url,
                }
                for t in tracks
            ],
        }
    meta = await TrackMetadata.create(text, ydl_opts_factory)
    if not meta.title:
        raise HTTPException(404, "Track not found")
    return {
        "kind": "track",
        "title": meta.title,
        "artist": meta.artist,
        "album": meta.album,
        "artwork_url": meta.artwork_url,
        "preview_url": meta.preview_url,
        "url": meta.url,
        "duration": meta.duration,
    }


@app.post("/jobs/download")
async def start_download(body: JobBody, user=Depends(get_current_user)):
    _touch(user)
    try:
        job = await jobs.create_download(user["id"], body.query)
    except RuntimeError as e:
        if str(e) == "too_many_jobs":
            raise HTTPException(429, "Too many active jobs") from e
        raise
    return job.to_dict()


@app.post("/jobs/playlist")
async def start_playlist(body: JobBody, user=Depends(get_current_user)):
    _touch(user)
    try:
        job = await jobs.create_playlist(user["id"], body.query)
    except RuntimeError as e:
        if str(e) == "too_many_jobs":
            raise HTTPException(429, "Too many active jobs") from e
        raise
    return job.to_dict()


@app.get("/jobs/{job_id}")
async def get_job(job_id: str, user=Depends(get_current_user)):
    job = jobs.get(job_id)
    if not job or job.user_id != user["id"]:
        raise HTTPException(404, "Job not found")
    return job.to_dict()


@app.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, user=Depends(get_current_user)):
    job = jobs.cancel(job_id, user["id"])
    if not job:
        raise HTTPException(404, "Job not found")
    return job.to_dict()


@app.get("/history")
async def history(limit: int = 30, user=Depends(get_current_user)):
    _touch(user)
    rows = get_user_manager().get_user_history(user["id"], limit=min(limit, 100))
    return {"items": rows}


@app.get("/liked")
async def liked(limit: int = 50, user=Depends(get_current_user)):
    _touch(user)
    rows = get_user_manager().list_favorites(user["id"], limit=min(limit, 100))
    return {"items": rows}


@app.post("/liked")
async def add_liked(body: FavBody, user=Depends(get_current_user)):
    from cache_manager import content_key

    _touch(user)
    key = body.content_key or content_key(body.title, body.artist or "", "")
    get_user_manager().add_favorite(user["id"], body.title, body.artist, body.album, key)
    return {"ok": True, "content_key": key}


@app.delete("/liked/{content_key}")
async def remove_liked(content_key: str, user=Depends(get_current_user)):
    _touch(user)
    get_user_manager().remove_favorite(user["id"], content_key)
    return {"ok": True}


@app.get("/top")
async def top(period: str = "week", limit: int = 20, user=Depends(get_current_user)):
    _touch(user)
    if period not in ("day", "week", "all"):
        period = "week"
    rows = get_db().get_top_songs(period=period, limit=min(limit, 50))
    return {"period": period, "items": rows}


@app.post("/discover")
async def discover(user=Depends(get_current_user)):
    import llm_service

    _touch(user)
    if not llm_service.is_configured():
        raise HTTPException(503, "Discover is not configured")
    history = get_user_manager().get_user_history(user["id"], limit=40)
    try:
        recs, _usage = await llm_service.recommend_songs(history, user_id=user["id"])
    except Exception as e:
        logger.exception("discover failed")
        raise HTTPException(500, str(e)[:200]) from e
    if not recs:
        raise HTTPException(502, "No recommendations")
    return {"items": recs}


@app.get("/files/{token}")
async def serve_file(token: str):
    claims = auth.decode_file_token(token)
    path = claims.get("path")
    if not path or not os.path.isfile(path):
        raise HTTPException(404, "File not found")
    filename = os.path.basename(path)
    media = "audio/mpeg" if path.endswith(".mp3") else "application/octet-stream"
    return FileResponse(path, media_type=media, filename=filename)


@app.get("/premium/catalog")
async def premium_catalog(user=Depends(get_current_user)):
    import payments

    _touch(user)
    return {
        "products": payments.product_catalog(),
        "bot_username": config.BOT_USERNAME,
        "checkout_deep_link": f"https://t.me/{config.BOT_USERNAME}?start=premium",
        "mini_app_pay": f"https://t.me/{config.BOT_USERNAME}/{os.getenv('WEBAPP_SHORT_NAME', 'app')}?startapp=pay",
    }


@app.post("/premium/invoice")
async def premium_invoice(body: InvoiceBody, user=Depends(get_current_user)):
    """Create Stars invoice link for Mini App openInvoice."""
    import payments
    from telegram import LabeledPrice
    import json

    _touch(user)
    bot = get_bot()
    if not bot:
        raise HTTPException(503, "Bot not configured")

    meta = payments._PRODUCTS.get(body.kind)
    if not meta:
        raise HTTPException(400, "Unknown product")

    # Outside Mini App, client should use deep link instead
    payload = json.dumps({"uid": str(user["id"]), **meta["payload"]}, separators=(",", ":"))
    try:
        link = await bot.create_invoice_link(
            title=meta["title"],
            description=meta["description"],
            payload=payload,
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label=meta["title"], amount=meta["stars"])],
        )
    except Exception as e:
        logger.exception("create_invoice_link failed")
        raise HTTPException(500, f"Invoice failed: {e}") from e
    return {"invoice_url": link, "kind": body.kind, "stars": meta["stars"]}


@app.get("/invite")
async def invite(user=Depends(get_current_user)):
    import referrals

    _touch(user)
    db = get_db()
    credited = db.count_credited_referrals(user["id"]) if hasattr(db, "count_credited_referrals") else 0
    return {
        "link": referrals.invite_link(user["id"]),
        "credited": credited,
        "per_topup": referrals.REFERRALS_PER_TOPUP,
        "topup_amount": __import__("entitlements").TOPUP_AMOUNT,
    }


# --- Admin ---


@app.get("/admin/stats")
async def admin_stats(_admin=Depends(require_admin)):
    users, downloads = get_user_manager().get_stats()
    return {"users": users, "downloads": downloads}


@app.get("/admin/users")
async def admin_users(limit: int = 50, _admin=Depends(require_admin)):
    db = get_db()
    with db._conn() as conn:
        rows = conn.execute(
            "SELECT user_id, username, first_name, total_downloads, last_seen "
            "FROM users ORDER BY last_seen DESC LIMIT ?",
            (min(limit, 200),),
        ).fetchall()
    return {
        "items": [
            {
                "user_id": r[0],
                "username": r[1],
                "first_name": r[2],
                "total_downloads": r[3],
                "last_seen": r[4],
            }
            for r in rows
        ]
    }


@app.post("/admin/grant")
async def admin_grant(body: AdminGrantBody, admin=Depends(require_admin)):
    import payments

    sub = payments.apply_manual_grant(
        get_db(), body.user_id, body.tier, body.days, admin_id=admin["id"]
    )
    return {"ok": True, "subscription": sub}


@app.post("/admin/topup")
async def admin_topup(body: AdminTopupBody, admin=Depends(require_admin)):
    import payments

    amount, day = payments.apply_manual_topup(
        get_db(), body.user_id, amount=body.amount, admin_id=admin["id"]
    )
    return {"ok": True, "amount": amount, "day": day}


@app.post("/admin/broadcast")
async def admin_broadcast(body: AdminBroadcastBody, admin=Depends(require_admin)):
    bot = get_bot()
    if not bot:
        raise HTTPException(503, "Bot not configured")
    ids = get_user_manager().get_all_user_ids()
    sent = 0
    failed = 0
    for uid in ids:
        try:
            await bot.send_message(chat_id=int(uid), text=body.message)
            sent += 1
        except Exception:
            failed += 1
    return {"ok": True, "sent": sent, "failed": failed, "total": len(ids)}


@app.post("/admin/cookies")
async def admin_cookies(file: UploadFile = File(...), _admin=Depends(require_admin)):
    dest = os.getenv("YTDLP_COOKIES", "").strip() or str(
        __import__("pathlib").Path(config.DATABASE_PATH).resolve().parent / "cookies.txt"
    )
    content = await file.read()
    text = content.decode("utf-8", errors="replace")
    if "# Netscape HTTP Cookie File" not in text and "netscape" not in text.lower()[:200]:
        # soft check — still allow if looks like cookies
        if "youtube.com" not in text and ".youtube.com" not in text:
            raise HTTPException(400, "File does not look like a Netscape cookies.txt")
    with open(dest, "wb") as f:
        f.write(content)
    return {"ok": True, "path": dest, "bytes": len(content)}


@app.get("/admin/creds")
async def admin_creds(_admin=Depends(require_admin)):
    try:
        from cred_status import get_credentials_status

        text, ok = get_credentials_status()
        return {"ok": ok, "status": text}
    except Exception as e:
        return {"ok": False, "status": str(e)}


@app.get("/admin/export")
async def admin_export(_admin=Depends(require_admin)):
    import csv
    import io

    db = get_db()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["user_id", "username", "first_name", "total_downloads", "last_seen"])
    with db._conn() as conn:
        for r in conn.execute(
            "SELECT user_id, username, first_name, total_downloads, last_seen FROM users"
        ):
            writer.writerow(r)
    from fastapi.responses import Response

    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=users.csv"},
    )
