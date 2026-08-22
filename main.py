import asyncio
import json
import logging
import os
import secrets
import shutil
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

_BASE_DIR = Path(__file__).resolve().parent
load_dotenv(_BASE_DIR / ".env")

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InlineQueryResultCachedAudio,
    InputTextMessageContent,
    MessageOriginChannel,
    MessageOriginChat,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    InlineQueryHandler,
    TypeHandler,
    filters,
    ContextTypes,
)

from metadata import TrackMetadata, AppleMusicMetadata
from downloader import MusicDownloader, QUALITIES, DEFAULT_QUALITY
import catalog
from user_manager import UserManager
from cred_status import get_credentials_status
from gates import ensure_access, validate_channel_gate
from admin_logger import (
    log_download,
    log_error,
    log_incoming_update,
    log_rate_limit,
    log_broadcast,
    log_shutdown,
    log_startup,
    log_system,
    notify_admin_vip_issue,
    send_test_message,
    validate_vip_log_channel,
    vip_status_text,
    report_cookie_health_transition,
    maybe_alert_cookie_issue,
)
import admin_logger
from progress import ProgressReporter
from download_orchestrator import DownloadOrchestrator
from playlist_handler import process_playlist
from recommendations import recommendation_keyboard, resolve_lyrics_ref, resolve_track_ref
from lyrics_service import fetch_lyrics
from llm_service import (
    is_configured as llm_configured,
    recommend_songs,
    recommend_similar,
    get_cached_recommendations,
    set_cached_recommendations,
)
from cache_manager import content_key
from downloader import cookie_jar_status
from preview import PreviewSender
import entitlements
import jobs
import messages as msg
import payments
import referrals
import reporting as rpt

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
TG_CONNECT_TIMEOUT = float(os.getenv("TG_CONNECT_TIMEOUT", "30"))
TG_READ_TIMEOUT = float(os.getenv("TG_READ_TIMEOUT", "300"))
TG_WRITE_TIMEOUT = float(os.getenv("TG_WRITE_TIMEOUT", "300"))
TG_MEDIA_WRITE_TIMEOUT = float(os.getenv("TG_MEDIA_WRITE_TIMEOUT", "600"))
TG_POOL_TIMEOUT = float(os.getenv("TG_POOL_TIMEOUT", "30"))

_ADMIN_COMMANDS = {
    "/stats", "/analytics", "/creds", "/channelid", "/viplogtest",
    "/broadcast", "/report", "/users", "/user", "/export", "/cookies",
    "/grant", "/topup",
}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

downloader = MusicDownloader()
user_manager = UserManager()
orchestrator = DownloadOrchestrator(
    downloader, user_manager.database, download_dir=downloader.download_dir
)


def _ydl_opts_factory():
    return downloader._build_search_opts()


def _is_admin(user_id):
    return str(user_id) == str(ADMIN_ID)


def _platform_fa(platform):
    return msg.platform_fa(platform)


def _unknown_artist(artist):
    return msg.unknown_artist(artist)


def _favorite_content_key(title, artist):
    return content_key(title, artist, "")


def _track_keyboard(user_id, title, artist):
    favorited = user_manager.is_favorite(
        user_id, _favorite_content_key(title, artist),
    )
    return recommendation_keyboard(artist, title, favorited=favorited)


def _start_job(context, kind):
    return jobs.start(context, kind)


def _end_job(context, job):
    jobs.end(context, job)


def _cancel_check(job):
    return jobs.cancelled(job)


async def _reject_if_busy(message, context):
    """Guard against a user piling up more concurrent work than we allow."""
    if jobs.has_slot(context):
        return False
    await message.reply_text(msg.too_many_jobs(jobs.MAX_ACTIVE_JOBS))
    return True


async def _await_with_progress(coro, reporter, cancel_check, pct_lo, pct_hi, detail):
    """Await ``coro`` while pulsing a percent progress bar; cancel if requested.

    Returns ``(result, cancelled)``. On cancel, the task is cancelled and
    ``(None, True)`` is returned.
    """
    task = asyncio.create_task(coro)
    pct = int(pct_lo)
    hi = max(int(pct_hi) - 1, pct)
    try:
        while True:
            if cancel_check and cancel_check():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                return None, True
            done, _pending = await asyncio.wait({task}, timeout=2.0)
            if done:
                exc = task.exception()
                if exc:
                    raise exc
                return task.result(), False
            if reporter:
                pct = min(pct + 3, hi)
                await reporter.update(pct, detail, force=True)
    except asyncio.CancelledError:
        return None, True


def _lyrics_from_cache(title, artist):
    """Prefer lyrics already embedded in a cached MP3."""
    try:
        from mutagen.mp3 import MP3
        from mutagen.id3 import ID3
        for source in ("youtube", "spotify", "apple"):
            path = orchestrator.cache.get(title, artist, source)
            if not path:
                continue
            audio = MP3(path, ID3=ID3)
            if not audio.tags:
                continue
            for frame in audio.tags.getall("USLT"):
                text = str(getattr(frame, "text", "") or "").strip()
                if text:
                    return text
    except Exception:
        return None
    return None


def _cover_from_cache(title, artist):
    """Return watermarked JPEG bytes from a cached MP3's APIC frame."""
    for source in ("youtube", "spotify", "apple"):
        path = orchestrator.cache.get(title, artist, source)
        if not path:
            continue
        data = downloader.extract_cover(path)
        if data:
            return data
    return None


async def _build_watermarked_artwork(title, artist):
    """Fallback: resolve cover via iTunes and apply the HiiT watermark."""
    query = f"{title} {artist}".strip() if artist else (title or "")
    if not query:
        return None
    resolved = await AppleMusicMetadata.search_by_query(query)
    url = getattr(resolved, "artwork_url", None) if resolved else None
    if not url:
        return None
    try:
        response = await asyncio.to_thread(
            lambda: __import__("requests").get(
                url,
                timeout=15,
                headers={"User-Agent": "Mozilla/5.0"},
            )
        )
        if response.status_code != 200 or not response.content:
            return None
        return downloader._process_itunes_query_artwork(response.content)
    except Exception as e:
        logger.debug("Artwork fallback failed: %s", e)
        return None


async def _reply_lyrics(message, title, artist, text):
    header = msg.lyrics_header(title, artist)
    body = (text or "").strip()
    # Telegram message limit is 4096 characters.
    limit = 4000
    first = header + body
    if len(first) <= limit:
        await message.reply_text(first)
        return
    await message.reply_text(header + body[: limit - len(header)])
    rest = body[limit - len(header) :]
    while rest:
        chunk, rest = rest[:limit], rest[limit:]
        await message.reply_text(chunk)


def _vip_failure_detail(context=""):
    """Technical detail for VIP admin logs only — never show to users."""
    _, yt_ok = get_credentials_status()
    parts = []
    if context:
        parts.append(str(context)[:300])
    parts.append(f"youtube={'OK' if yt_ok else 'FAIL'}")
    return " | ".join(parts)


def _btn_redownload(title):
    return msg.btn_redownload(title)


def _btn_download(title, index=None):
    return msg.btn_download(title, index)


async def _touch_user(update):
    u = update.effective_user
    if u:
        user_manager.touch_user(u.id, u.username, u.first_name)


async def _deny_quota(message, bot, user):
    allowed, used, limit, tier = entitlements.check_quota(
        user_manager.database, user.id,
    )
    if allowed:
        return False
    await log_rate_limit(bot, user, 0)
    await message.reply_text(
        msg.quota_exceeded(used, limit, tier),
        reply_markup=payments.quota_upsell_keyboard(),
    )
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    inviter = referrals.parse_start_payload(context.args)
    existed = user_manager.database.user_exists(user.id) if user else True
    await _touch_user(update)
    if inviter and user and not existed:
        status = referrals.record_pending(
            user_manager.database, inviter, user.id, is_new_user=True,
        )
        logger.info("Referral pending inviter=%s invited=%s status=%s", inviter, user.id, status)
    # If channel gate is disabled, credit immediately on start.
    from gates import REQUIRED_CHANNEL
    if user and not REQUIRED_CHANNEL:
        referrals.maybe_credit_on_membership(user_manager.database, user.id)
    args = context.args or []
    if args and str(args[0]).lower().startswith("premium"):
        if await ensure_access(update, context):
            snap = entitlements.status_snapshot(
                user_manager.database, update.effective_user.id,
            )
            await update.message.reply_text(
                msg.premium_status(snap),
                reply_markup=payments.premium_keyboard(),
            )
        return
    first_name = user.first_name if user else ""
    await update.message.reply_text(
        msg.start_text(first_name), reply_markup=_start_menu_keyboard(),
    )


def _start_menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔎 جستجوی آهنگ", callback_data="menu:search"),
            InlineKeyboardButton("🎙 مرور هنرمند", callback_data="menu:artist"),
        ],
        [
            InlineKeyboardButton("🎛 کیفیت صدا", callback_data="menu:quality"),
            InlineKeyboardButton("📚 راهنمای کامل", callback_data="menu:help"),
        ],
        [
            InlineKeyboardButton("🕐 تاریخچه دانلود", callback_data="menu:history"),
            InlineKeyboardButton("💖 علاقه‌مندی‌ها", callback_data="menu:liked"),
        ],
        [
            InlineKeyboardButton("🔥 محبوب‌ترین‌ها", callback_data="menu:top"),
            InlineKeyboardButton("🎯 پیشنهاد شخصی", callback_data="menu:discover"),
        ],
        [
            InlineKeyboardButton("🔔 هنرمندان من", callback_data="menu:following"),
            InlineKeyboardButton("🎁 دعوت دوست", callback_data="menu:invite"),
        ],
        [
            InlineKeyboardButton("💠 پریمیوم", callback_data="menu:premium"),
            InlineKeyboardButton("🤖 درباره ربات", callback_data="menu:aboutme"),
        ],
        [
            InlineKeyboardButton("⛔ لغو کار جاری", callback_data="menu:cancel"),
        ],
    ])


def _back_button():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="menu:back")],
    ])


def _back_row():
    return [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="menu:back")]


async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_access(update, context):
        return
    await _touch_user(update)
    snap = entitlements.status_snapshot(
        user_manager.database, update.effective_user.id,
    )
    await update.message.reply_text(
        msg.premium_status(snap),
        reply_markup=payments.premium_keyboard(),
    )


async def invite_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_access(update, context):
        return
    await _touch_user(update)
    prog = referrals.progress(user_manager.database, update.effective_user.id)
    await update.message.reply_text(msg.invite_status(prog))


async def grant_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    # /grant <user_id> <premium|unlimited> <days>
    args = context.args or []
    if len(args) < 3:
        await update.message.reply_text("نحوه استفاده: /grant <user_id> <premium|unlimited> <days>")
        return
    target, tier, days_s = args[0], args[1].lower(), args[2]
    if tier not in ("premium", "unlimited"):
        await update.message.reply_text("tier باید premium یا unlimited باشد.")
        return
    try:
        days = int(days_s)
    except ValueError:
        await update.message.reply_text("days باید عدد باشد.")
        return
    user_manager.touch_user(target)
    sub = payments.apply_manual_grant(
        user_manager.database, target, tier, days, admin_id=update.effective_user.id,
    )
    await update.message.reply_text(msg.grant_ok(target, tier, sub["expires_at"]))


async def topup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    # /topup <user_id> [amount]
    args = context.args or []
    if not args:
        await update.message.reply_text("نحوه استفاده: /topup <user_id> [amount]")
        return
    target = args[0]
    amount = None
    if len(args) > 1:
        try:
            amount = int(args[1])
        except ValueError:
            await update.message.reply_text("amount باید عدد باشد.")
            return
    user_manager.touch_user(target)
    granted, day = payments.apply_manual_topup(
        user_manager.database, target, amount=amount, admin_id=update.effective_user.id,
    )
    await update.message.reply_text(msg.topup_ok(target, granted, day))


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_access(update, context):
        return
    await update.message.reply_text(msg.help_text())


async def aboutme_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_access(update, context):
        return
    await _touch_user(update)
    await update.message.reply_text(msg.aboutme_text())


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    db = user_manager.database
    total_users, total_downloads = user_manager.get_stats()
    cached, total = db.cache_hit_rate()
    hit_pct = f"{100 * cached / total:.1f}٪" if total else "—"
    lines = [
        f"کاربران: {total_users}",
        f"دانلودها: {total_downloads}",
        f"نرخ برخورد کش: {hit_pct} ({cached}/{total})",
        "",
        "پربازدیدترین هنرمندان:",
    ]
    for row in db.top_artists(5):
        lines.append(f"  • {row['artist']} ({row['cnt']})")
    lines.append("")
    lines.append("پربازدیدترین آهنگ‌ها:")
    for row in db.top_songs(5):
        lines.append(f"  • {row['title']} — {row['artist']} ({row['cnt']})")
    lines.append("")
    lines.append("پلتفرم‌ها:")
    for row in db.platform_breakdown():
        lines.append(f"  • {_platform_fa(row['platform'])}: {row['cnt']}")
    lines.append("")
    lines.append("گزارش کامل: /report")
    await update.message.reply_text("\n".join(lines))


async def analytics_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Alias extended stats for admins."""
    await stats_command(update, context)


async def creds_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    status_text, _ = get_credentials_status()
    await update.message.reply_text(status_text)


async def channelid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: resolve chat ID from a forwarded channel message or current chat."""
    msg = update.effective_message
    if not msg:
        return

    if msg.chat and msg.chat.type == "channel":
        await msg.reply_text(
            f"شناسه چت: `{msg.chat.id}`\n\nدر .env:\nVIP_LOG_CHANNEL_ID={msg.chat.id}",
            parse_mode="Markdown",
        )
        return

    if not _is_admin(update.effective_user.id):
        return

    chat = None
    origin = msg.forward_origin
    if isinstance(origin, MessageOriginChannel):
        chat = origin.chat
    elif isinstance(origin, MessageOriginChat):
        chat = origin.sender_chat
    elif msg.forward_from_chat:
        chat = msg.forward_from_chat
    elif msg.sender_chat:
        chat = msg.sender_chat

    if chat:
        lines = [
            f"شناسه چت: `{chat.id}`",
            f"نوع: {chat.type}",
        ]
        if chat.title:
            lines.append(f"عنوان: {chat.title}")
        if chat.username:
            lines.append(f"یوزرنیم: @{chat.username}")
        lines.append("\nدر .env قرار بده:\nVIP_LOG_CHANNEL_ID=" + str(chat.id))
        await msg.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    await msg.reply_text(
        "یک پیام از کانال VIP را به این چت **فوروارد** کن (با حفظ نام فرستنده).\n"
        "یا در خود کانال یک پیام بفرست و همانجا /channelid را بزن."
    )


async def viplogtest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    status = vip_status_text()
    ok, detail = await send_test_message(context.bot)
    if ok:
        await update.message.reply_text(f"✅ {detail}\n\n{status}")
    else:
        await update.message.reply_text(f"❌ {detail}\n\n{status}")


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_access(update, context):
        return
    await _touch_user(update)
    rows = user_manager.get_user_history(update.effective_user.id, limit=10)
    if not rows:
        await update.message.reply_text(msg.history_empty())
        return
    lines = [msg.history_header()]
    buttons = []
    for row in rows:
        ts = time.strftime("%m/%d %H:%M", time.localtime(row["created_at"]))
        lines.append(
            f"• {row['title']} — {row['artist']} ({_platform_fa(row['platform'])}) [{ts}]"
        )
        buttons.append([
            InlineKeyboardButton(
                _btn_redownload(row["title"]),
                callback_data=f"redownload:{row['id']}",
            )
        ])
    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def liked_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_access(update, context):
        return
    await _touch_user(update)
    rows = user_manager.list_favorites(update.effective_user.id, limit=30)
    if not rows:
        await update.message.reply_text(msg.liked_empty())
        return
    lines = [msg.liked_header()]
    buttons = []
    for row in rows:
        artist = row.get("artist") or msg.UNKNOWN
        lines.append(f"• {row['title']} — {artist}")
        buttons.append([
            InlineKeyboardButton(
                msg.btn_download(row["title"]),
                callback_data=f"liked:{row['id']}",
            )
        ])
    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_access(update, context):
        return
    await _touch_user(update)
    period = "week"
    if context.args:
        arg = (context.args[0] or "").strip().lower()
        if arg in ("day", "week", "all"):
            period = arg
    songs = user_manager.database.get_top_songs(period=period, limit=10)
    if not songs:
        await update.message.reply_text(msg.top_empty())
        return
    lines = [msg.top_header(msg.top_period_label(period))]
    buttons = []
    context.user_data["top_cache"] = {}
    for i, row in enumerate(songs, 1):
        title = row.get("title") or msg.UNKNOWN
        artist = row.get("artist") or msg.UNKNOWN
        cnt = row.get("cnt") or 0
        lines.append(f"{i}. {title} — {artist} ({cnt})")
        meta = TrackMetadata()
        meta.title = title
        meta.artist = artist if artist != msg.UNKNOWN else ""
        meta.id = str(abs(hash(f"{meta.title}{meta.artist}top{i}")))
        meta.type = "top"
        context.user_data["top_cache"][str(i)] = meta
        buttons.append([
            InlineKeyboardButton(
                msg.btn_download(title, i),
                callback_data=f"toppick:{i}",
            )
        ])
    await update.message.reply_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def discover_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_access(update, context):
        return
    await _touch_user(update)
    user_id = update.effective_user.id
    db = user_manager.database
    history = db.get_user_history(user_id, limit=40)
    if not history:
        await update.message.reply_text(msg.discover_empty_history())
        return

    if not llm_configured():
        await update.message.reply_text(msg.discover_not_configured())
        return

    if await _reject_if_busy(update.message, context):
        return

    job = _start_job(context, "discover")
    status = await update.message.reply_text(msg.discover_preparing())
    reporter = ProgressReporter(
        status,
        100,
        "پیشنهاد",
        bot=context.bot,
        user=update.effective_user,
        progress_mode="percent",
    )
    try:
        await reporter.update(8, msg.discover_llm_phase(), force=True)

        recs = get_cached_recommendations(user_id)
        if recs is not None:
            db.log_llm_usage(
                user_id,
                model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
                cached=True,
                success=True,
                recommendations_count=len(recs),
            )
            await reporter.update(45, msg.discover_llm_phase(), force=True)
        else:
            if _cancel_check(job):
                await reporter.fail(msg.work_cancelled())
                return
            result, cancelled = await _await_with_progress(
                recommend_songs(history, user_id=user_id, limit=10),
                reporter,
                lambda: _cancel_check(job),
                12,
                50,
                msg.discover_llm_phase(),
            )
            if cancelled:
                await reporter.fail(msg.work_cancelled())
                return
            recs, usage = result
            db.log_llm_usage(
                user_id,
                model=usage.get("model"),
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                cached=False,
                success=bool(usage.get("success") and recs is not None),
                recommendations_count=usage.get("recommendations_count", 0),
            )
            if recs is None:
                await reporter.fail(msg.discover_llm_error())
                return
            set_cached_recommendations(user_id, recs)

        suggestions = []
        seen = set()
        history_keys = {
            ((r.get("title") or "").strip().lower(), (r.get("artist") or "").strip().lower())
            for r in history if r.get("title")
        }
        candidates = [r for r in (recs or []) if (r.get("title") or "").strip()]
        total_cands = max(len(candidates), 1)

        for idx, rec in enumerate(candidates):
            if _cancel_check(job):
                await reporter.fail(msg.work_cancelled())
                return
            title = rec.get("title", "").strip()
            artist = rec.get("artist", "").strip()
            key = (title.lower(), artist.lower())
            if key in seen or key in history_keys:
                continue

            pct = 50 + int(40 * (idx + 1) / total_cands)
            await reporter.update(
                min(pct, 90),
                msg.discover_resolve_phase(len(suggestions) + 1, 10),
                force=True,
            )

            query = f"{title} {artist}".strip() if artist else title
            resolved = await AppleMusicMetadata.search_by_query(query)
            if not resolved or not resolved.title:
                resolved = await AppleMusicMetadata.search_by_query(title)
            if not resolved or not resolved.title:
                continue

            res_key = (
                resolved.title.strip().lower(),
                (resolved.artist or "").strip().lower(),
            )
            if res_key in seen or res_key in history_keys:
                continue
            seen.add(res_key)
            suggestions.append(TrackMetadata()._copy_from(resolved))
            if len(suggestions) >= 10:
                break

        if _cancel_check(job):
            await reporter.fail(msg.work_cancelled())
            return

        if not suggestions:
            await reporter.fail(msg.discover_no_results())
            return

        lines = [msg.discover_header()]
        buttons = []
        for i, s in enumerate(suggestions[:10], 1):
            lines.append(f"{i}. {s.title} — {_unknown_artist(s.artist)}")
            buttons.append([
                InlineKeyboardButton(
                    _btn_download(s.title, i),
                    callback_data=f"discoverpick:{i}",
                )
            ])
        context.user_data["discover_cache"] = {
            str(i): s for i, s in enumerate(suggestions[:10], 1)
        }
        await reporter.update(100, "آماده شد", force=True)
        await status.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"Discover failed: {e}", exc_info=True)
        await reporter.fail(msg.discover_llm_error())
    finally:
        _end_job(context, job)


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    text = update.message.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await update.message.reply_text("نحوه استفاده: /broadcast <پیام>")
        return
    msg_body = parts[1].strip()
    if msg_body.startswith("confirm "):
        token = msg_body.split(maxsplit=1)[1]
        confirmed = user_manager.database.pop_broadcast_pending(token)
        if not confirmed:
            await update.message.reply_text("توکن نامعتبر یا منقضی.")
            return
        msg_body = confirmed
    else:
        token = secrets.token_hex(4)
        user_manager.database.save_broadcast_pending(token, msg_body)
        await update.message.reply_text(
            f"برای تأیید:\n/broadcast confirm {token}"
        )
        return

    user_ids = user_manager.get_all_user_ids()
    sent = failed = 0
    for uid in user_ids:
        try:
            await context.bot.send_message(chat_id=int(uid), text=msg_body)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
    await update.message.reply_text(f"پیام همگانی: ارسال‌شده={sent}، ناموفق={failed}")
    await log_broadcast(context.bot, update.effective_user, sent, failed)


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cancelled = jobs.cancel_all(context)
    if not cancelled:
        await update.message.reply_text(msg.cancel_no_job())
        return
    kinds = ", ".join(sorted({j.get("kind") or "work" for j in cancelled}))
    await log_system(
        context.bot,
        "لغو کار کاربر",
        user=update.effective_user,
        kind=kinds,
        count=len(cancelled),
    )
    await update.message.reply_text(msg.cancel_ok(len(cancelled)))


def _source_label(metadata):
    if getattr(metadata, "source_url", None):
        url = metadata.source_url.lower()
        if "soundcloud" in url:
            return "soundcloud"
        if "youtube" in url or "youtu.be" in url:
            return "youtube"
    if metadata.url:
        url = metadata.url.lower()
        if "spotify.com" in url:
            return "spotify"
        if "music.apple.com" in url:
            return "apple"
        if "deezer.com" in url:
            return "deezer"
        if "soundcloud.com" in url:
            return "soundcloud"
        if "youtube.com" in url or "youtu.be" in url:
            return "youtube"
    return "youtube"


def _catalog_pick_label(hit):
    kind_fa = {"track": "🎵", "album": "💿", "playlist": "📋", "artist": "🎤"}.get(hit.kind, "•")
    name = (hit.name or "")[:28]
    return f"{kind_fa} {name}"


async def _show_search_results(message, query, hits, context):
    lines = [msg.search_header(query)]
    buttons = []
    context.user_data["search_cache"] = {}
    for i, hit in enumerate(hits, 1):
        lines.append(msg.search_hit_line(i, hit.name, hit.subtitle, hit.kind, hit.source))
        context.user_data["search_cache"][str(i)] = hit
        buttons.append([
            InlineKeyboardButton(
                _catalog_pick_label(hit),
                callback_data=f"catpick:{i}",
            )
        ])
    await message.reply_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons))


async def _show_artist_page(message, artist_id, context, edit=False, user_id=None):
    try:
        data = await catalog.fetch_artist(artist_id)
    except catalog.CatalogError as exc:
        text = str(exc)
        if edit:
            await message.edit_text(text)
        else:
            await message.reply_text(text)
        return
    name = data.get("name") or msg.UNKNOWN
    lines = [msg.artist_header(name), "", msg.artist_top_header()]
    buttons = []
    context.user_data["artist_cache"] = {"id": artist_id, "tracks": {}, "albums": {}}

    following = False
    if user_id:
        following = user_manager.is_following(user_id, str(artist_id))
    safe_name = (name or "")[:40]
    if following:
        buttons.append([InlineKeyboardButton(
            f"🔕 لغو دنبال‌کردن {safe_name[:20]}",
            callback_data=f"unfollow:{artist_id}",
        )])
    else:
        buttons.append([InlineKeyboardButton(
            f"🔔 دنبال‌کردن {safe_name[:20]}",
            callback_data=f"follow:{artist_id}:{safe_name}",
        )])

    for i, track in enumerate(data.get("top") or [], 1):
        lines.append(f"{i}. {track.title} — {track.artist or name}")
        context.user_data["artist_cache"]["tracks"][str(i)] = track
        buttons.append([
            InlineKeyboardButton(
                _btn_download(track.title, i),
                callback_data=f"artistpick:track:{i}",
            )
        ])
    albums = data.get("albums") or []
    if albums:
        lines.extend(["", msg.artist_albums_header()])
        for j, album in enumerate(albums[:8], 1):
            title = album.get("title") or msg.UNKNOWN
            year = (album.get("release_date") or "")[:4]
            sub = f" ({year})" if year else ""
            lines.append(f"{j}. {title}{sub}")
            link = album.get("link") or f"https://www.deezer.com/album/{album.get('id')}"
            context.user_data["artist_cache"]["albums"][str(j)] = link
            buttons.append([
                InlineKeyboardButton(
                    f"💿 {title[:26]}",
                    callback_data=f"artistpick:album:{j}",
                )
            ])
    text = "\n".join(lines)
    markup = InlineKeyboardMarkup(buttons) if buttons else None
    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.reply_text(text, reply_markup=markup)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_access(update, context):
        return
    query = " ".join(context.args or []).strip()
    if len(query) < 2:
        await update.message.reply_text(msg.search_usage())
        return
    status = await update.message.reply_text(msg.searching())
    hits = await catalog.search_all(query, limit=10)
    await status.delete()
    if not hits:
        await update.message.reply_text(msg.search_empty())
        return
    await _show_search_results(update.message, query, hits, context)


async def quality_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_access(update, context):
        return
    user_id = update.effective_user.id
    if context.args:
        value = context.args[0].strip().lower()
        if value not in QUALITIES:
            await update.message.reply_text(msg.quality_invalid())
            return
        user_manager.set_audio_quality(user_id, value)
        await update.message.reply_text(msg.quality_set(value))
        return
    current = user_manager.get_audio_quality(user_id)
    buttons = [
        [
            InlineKeyboardButton(
                f"{'✓ ' if q == current else ''}{q}",
                callback_data=f"qual:{q}",
            )
            for q in ("128", "192", "256", "320")
        ],
        [InlineKeyboardButton(
            f"{'✓ ' if current == 'original' else ''}original",
            callback_data="qual:original",
        )],
    ]
    await update.message.reply_text(
        msg.quality_status(current),
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def artist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_access(update, context):
        return
    query = " ".join(context.args or []).strip()
    if len(query) < 2:
        await update.message.reply_text(msg.artist_usage())
        return
    status = await update.message.reply_text(msg.searching())
    hits = await catalog.search_all(query, limit=8)
    artists = [h for h in hits if h.kind == "artist"]
    await status.delete()
    if not artists:
        await update.message.reply_text(msg.artist_not_found(query))
        return
    if len(artists) == 1:
        await _show_artist_page(update.message, artists[0].id, context, user_id=update.effective_user.id)
        return
    lines = [msg.search_header(query)]
    buttons = []
    context.user_data["artist_search_cache"] = {}
    for i, hit in enumerate(artists[:6], 1):
        lines.append(msg.search_hit_line(i, hit.name, hit.subtitle, hit.kind, hit.source))
        context.user_data["artist_search_cache"][str(i)] = hit.id
        buttons.append([
            InlineKeyboardButton(hit.name[:30], callback_data=f"artistpick:profile:{i}")
        ])
    await update.message.reply_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons))


async def follow_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_access(update, context):
        return
    query = " ".join(context.args or []).strip()
    if len(query) < 2:
        await update.message.reply_text(msg.follow_usage())
        return
    status = await update.message.reply_text(msg.searching())
    hits = await catalog.search_all(query, limit=8)
    artists = [h for h in hits if h.kind == "artist"]
    await status.delete()
    if not artists:
        await update.message.reply_text(msg.artist_not_found(query))
        return
    if len(artists) == 1:
        a = artists[0]
        ok = user_manager.follow_artist(
            update.effective_user.id, a.name, a.id, a.cover_url,
        )
        if ok:
            await update.message.reply_text(msg.follow_success(a.name))
        else:
            await update.message.reply_text(msg.already_following(a.name))
        return
    lines = [msg.search_header(query)]
    buttons = []
    for i, hit in enumerate(artists[:5], 1):
        lines.append(msg.search_hit_line(i, hit.name, hit.subtitle, hit.kind, hit.source))
        safe_name = (hit.name or "")[:40]
        buttons.append([
            InlineKeyboardButton(
                f"🔔 دنبال‌کردن {safe_name[:22]}",
                callback_data=f"follow:{hit.id}:{safe_name}",
            )
        ])
    await update.message.reply_text(
        "\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons),
    )


async def unfollow_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_access(update, context):
        return
    await _show_following_list(update.message, update.effective_user.id, context)


async def following_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_access(update, context):
        return
    await _show_following_list(update.message, update.effective_user.id, context)


async def _show_following_list(message, user_id, context, reply_markup_extra=None):
    rows = user_manager.list_followed_artists(user_id)
    if not rows:
        kb = _back_button() if reply_markup_extra else None
        await message.reply_text(msg.not_following(), reply_markup=kb)
        return
    lines = [msg.following_header()]
    buttons = []
    for r in rows:
        lines.append(f"• {r['artist_name']}")
        safe_name = (r["artist_name"] or "")[:20]
        buttons.append([
            InlineKeyboardButton(
                f"🔕 لغو {safe_name}",
                callback_data=f"unfollow:{r['deezer_artist_id']}",
            ),
            InlineKeyboardButton(
                f"🎙 {safe_name}",
                callback_data=f"artistpick:profile:follow:{r['deezer_artist_id']}",
            ),
        ])
    if reply_markup_extra:
        buttons.append(_back_row())
    await message.reply_text(
        "\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons),
    )


def _store_audio_file_id(metadata, platform, msg):
    if not msg or not msg.audio:
        return
    source = _source_label(metadata)
    if platform and platform.endswith("_cache"):
        source = platform.replace("_cache", "")
    if platform and platform.endswith("_cache_id"):
        source = platform.replace("_cache_id", "")
    orchestrator.cache.save_telegram_file_id(
        metadata.title, metadata.artist, source, msg.audio.file_id,
    )


async def _send_track_audio(message, metadata, file_path, platform, reply_markup=None):
    """Send by Telegram file_id when possible; otherwise upload the local MP3."""
    kwargs = {
        "title": metadata.title,
        "performer": metadata.artist,
        "reply_markup": reply_markup,
        "connect_timeout": TG_CONNECT_TIMEOUT,
        "read_timeout": TG_READ_TIMEOUT,
        "write_timeout": TG_WRITE_TIMEOUT,
        "pool_timeout": TG_POOL_TIMEOUT,
    }
    if platform and str(platform).endswith("_cache_id"):
        return await message.reply_audio(audio=file_path, **kwargs)
    with open(file_path, "rb") as audio:
        return await message.reply_audio(audio=audio, **kwargs)


async def inline_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = (update.inline_query.query or "").strip()
    if len(query) < 2:
        return
    if not await ensure_access(update, context):
        return

    hits = await catalog.search_all(query, limit=8)
    inline_results = []
    for i, hit in enumerate(hits):
        if hit.kind != "track":
            continue
        meta = catalog.hit_to_track_metadata(hit)
        if hit.source == "apple" and hit.url:
            try:
                resolved = await TrackMetadata.create(hit.url, _ydl_opts_factory)
                if resolved and resolved.title:
                    meta = resolved
            except Exception:
                pass
        source = _source_label(meta)
        file_id = orchestrator.cache.get_telegram_file_id(meta.title, meta.artist, f"{source}:{DEFAULT_QUALITY}")
        if not file_id:
            file_id = orchestrator.cache.get_telegram_file_id(meta.title, meta.artist, source)
        if file_id:
            inline_results.append(
                InlineQueryResultCachedAudio(
                    id=f"cached_{meta.id}_{i}",
                    audio_file_id=file_id,
                    title=meta.title or query,
                    performer=meta.artist,
                )
            )
            continue
        desc = msg.inline_description(meta.artist)
        if hit.source:
            desc = f"{msg.platform_fa(hit.source)} · {desc}"
        inline_results.append(
            InlineQueryResultArticle(
                id=f"{meta.id}_{i}",
                title=meta.title or query,
                description=desc,
                input_message_content=InputTextMessageContent(
                    f"{meta.title} {meta.artist}".strip()
                ),
            )
        )
    if inline_results:
        await update.inline_query.answer(inline_results, cache_time=30)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await ensure_access(update, context):
        return
    data = query.data or ""

    if data.startswith("menu:"):
        action = data.split(":", 1)[1]
        user = update.effective_user
        chat_id = query.message.chat_id

        if action == "back":
            try:
                await query.message.delete()
            except Exception:
                pass
            first_name = user.first_name if user else ""
            await context.bot.send_message(
                chat_id, msg.start_text(first_name),
                reply_markup=_start_menu_keyboard(),
            )
            return

        try:
            await query.message.delete()
        except Exception:
            pass

        if action == "search":
            await context.bot.send_message(
                chat_id, msg.search_usage(), reply_markup=_back_button(),
            )
        elif action == "artist":
            await context.bot.send_message(
                chat_id, msg.artist_usage(), reply_markup=_back_button(),
            )
        elif action == "quality":
            current = user_manager.get_audio_quality(user.id)
            buttons = [
                [
                    InlineKeyboardButton(
                        f"{'✅ ' if q == current else '🔘 '}{q} kbps",
                        callback_data=f"qual:{q}",
                    )
                    for q in ("128", "192")
                ],
                [
                    InlineKeyboardButton(
                        f"{'✅ ' if q == current else '🔘 '}{q} kbps",
                        callback_data=f"qual:{q}",
                    )
                    for q in ("256", "320")
                ],
                [InlineKeyboardButton(
                    f"{'✅ ' if current == 'original' else '🔘 '}original (بدون تبدیل)",
                    callback_data="qual:original",
                )],
                _back_row(),
            ]
            await context.bot.send_message(
                chat_id, msg.quality_status(current),
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        elif action == "help":
            await context.bot.send_message(
                chat_id, msg.help_text(), reply_markup=_back_button(),
            )
        elif action == "history":
            rows = user_manager.get_user_history(user.id, limit=10)
            if not rows:
                await context.bot.send_message(
                    chat_id, msg.history_empty(), reply_markup=_back_button(),
                )
            else:
                lines = [msg.history_header()]
                buttons = []
                for row in rows:
                    ts = time.strftime("%m/%d %H:%M", time.localtime(row["created_at"]))
                    lines.append(
                        f"• {row['title']} — {row['artist']} "
                        f"({_platform_fa(row['platform'])}) [{ts}]"
                    )
                    buttons.append([
                        InlineKeyboardButton(
                            _btn_redownload(row["title"]),
                            callback_data=f"redownload:{row['id']}",
                        )
                    ])
                buttons.append(_back_row())
                await context.bot.send_message(
                    chat_id, "\n".join(lines),
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
        elif action == "liked":
            rows = user_manager.list_favorites(user.id, limit=30)
            if not rows:
                await context.bot.send_message(
                    chat_id, msg.liked_empty(), reply_markup=_back_button(),
                )
            else:
                lines = [msg.liked_header()]
                buttons = []
                for row in rows:
                    artist = row.get("artist") or msg.UNKNOWN
                    lines.append(f"• {row['title']} — {artist}")
                    buttons.append([
                        InlineKeyboardButton(
                            msg.btn_download(row["title"]),
                            callback_data=f"liked:{row['id']}",
                        )
                    ])
                buttons.append(_back_row())
                await context.bot.send_message(
                    chat_id, "\n".join(lines),
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
        elif action == "top":
            context.args = []
            await top_command(update, context)
        elif action == "discover":
            context.args = []
            await discover_command(update, context)
        elif action == "premium":
            snap = entitlements.status_snapshot(user_manager.database, user.id)
            kb = payments.premium_keyboard()
            rows = list(kb.inline_keyboard) if kb else []
            rows.append(_back_row())
            await context.bot.send_message(
                chat_id, msg.premium_status(snap),
                reply_markup=InlineKeyboardMarkup(rows),
            )
        elif action == "invite":
            prog = referrals.progress(user_manager.database, user.id)
            await context.bot.send_message(
                chat_id, msg.invite_status(prog), reply_markup=_back_button(),
            )
        elif action == "aboutme":
            await context.bot.send_message(
                chat_id, msg.aboutme_text(), reply_markup=_back_button(),
            )
        elif action == "following":
            rows = user_manager.list_followed_artists(user.id)
            if not rows:
                await context.bot.send_message(
                    chat_id, msg.not_following(), reply_markup=_back_button(),
                )
            else:
                lines = [msg.following_header()]
                buttons = []
                for r in rows:
                    lines.append(f"• {r['artist_name']}")
                    safe_name = (r["artist_name"] or "")[:20]
                    buttons.append([
                        InlineKeyboardButton(
                            f"🔕 لغو {safe_name}",
                            callback_data=f"unfollow:{r['deezer_artist_id']}",
                        ),
                        InlineKeyboardButton(
                            f"🎙 {safe_name}",
                            callback_data=f"artistpick:profile:follow:{r['deezer_artist_id']}",
                        ),
                    ])
                buttons.append(_back_row())
                await context.bot.send_message(
                    chat_id, "\n".join(lines),
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
        elif action == "cancel":
            cancelled = jobs.cancel_all(context)
            text = msg.cancel_ok(len(cancelled)) if cancelled else msg.cancel_no_job()
            await context.bot.send_message(
                chat_id, text, reply_markup=_back_button(),
            )
        return

    if data.startswith("pay:"):
        action = data.split(":", 1)[1]
        if action == "invite":
            prog = referrals.progress(user_manager.database, update.effective_user.id)
            await query.message.reply_text(msg.invite_status(prog))
            return
        try:
            await payments.send_stars_invoice(
                context.bot,
                query.message.chat_id,
                update.effective_user.id,
                action,
            )
        except Exception as e:
            logger.error("Invoice failed: %s", e, exc_info=True)
            await query.message.reply_text(msg.payment_failed())
        return

    if data.startswith("redownload:"):
        hist_id = int(data.split(":", 1)[1])
        row = user_manager.get_history_by_id(hist_id)
        if not row:
            await query.message.reply_text(msg.record_not_found())
            return
        meta = TrackMetadata()
        meta.title = row["title"]
        meta.artist = row["artist"]
        meta.id = str(abs(hash(f"{meta.title}{meta.artist}")))
        meta.type = "history"
        await _download_and_send(query.message, update.effective_user, meta, context)
        return

    if data.startswith("liked:"):
        fav_id = int(data.split(":", 1)[1])
        row = user_manager.get_favorite_by_id(fav_id, update.effective_user.id)
        if not row:
            await query.message.reply_text(msg.favorite_missing())
            return
        meta = TrackMetadata()
        meta.title = row["title"]
        meta.artist = row.get("artist") or ""
        meta.album = row.get("album")
        meta.id = str(abs(hash(f"{meta.title}{meta.artist}liked")))
        meta.type = "favorite"
        await _download_and_send(query.message, update.effective_user, meta, context)
        return

    if data.startswith("fav:add:") or data.startswith("fav:del:"):
        action, token = data.split(":", 2)[1], data.split(":", 2)[2]
        ref = resolve_track_ref(token)
        if not ref:
            await query.message.reply_text(msg.pick_expired_short())
            return
        title, artist = ref
        key = _favorite_content_key(title, artist)
        user_id = update.effective_user.id
        if action == "add":
            user_manager.add_favorite(user_id, title, artist, content_key=key)
            await query.message.reply_text(msg.favorite_added(title))
            try:
                await query.edit_message_reply_markup(
                    reply_markup=_track_keyboard(user_id, title, artist)
                )
            except Exception:
                pass
        else:
            user_manager.remove_favorite(user_id, key)
            await query.message.reply_text(msg.favorite_removed(title))
            try:
                await query.edit_message_reply_markup(
                    reply_markup=_track_keyboard(user_id, title, artist)
                )
            except Exception:
                pass
        return

    if data.startswith("reco:artist:"):
        artist = data.split(":", 2)[2]
        results = await AppleMusicMetadata.search_many(artist, limit=5)
        if not results:
            await query.message.reply_text(msg.songs_not_found())
            return
        lines = [msg.more_by_artist(artist)]
        buttons = []
        context.user_data["reco_cache"] = {}
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. {r.title} — {r.artist}")
            context.user_data["reco_cache"][str(i)] = TrackMetadata()._copy_from(r)
            buttons.append([
                InlineKeyboardButton(
                    _btn_download(r.title, i),
                    callback_data=f"searchpick:{i}",
                )
            ])
        await query.message.reply_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons))
        return

    if data.startswith("reco:similar:"):
        token = data.split(":", 2)[2]
        ref = resolve_track_ref(token)
        if not ref:
            await query.message.reply_text(msg.pick_expired_short())
            return
        title, artist = ref
        if await _reject_if_busy(query.message, context):
            return
        job = _start_job(context, "similar")
        status = await query.message.reply_text(msg.similar_preparing())
        reporter = ProgressReporter(
            status,
            100,
            "مشابه",
            bot=context.bot,
            user=update.effective_user,
            progress_mode="percent",
        )
        try:
            await reporter.update(10, msg.similar_llm_phase(), force=True)
            suggestions = await _resolve_similar_tracks(
                title,
                artist,
                update.effective_user.id,
                reporter=reporter,
                cancel_check=lambda: _cancel_check(job),
            )
            if _cancel_check(job):
                await reporter.fail(msg.work_cancelled())
                return
            if suggestions is None:
                await reporter.fail(msg.work_cancelled())
                return
            if not suggestions:
                await reporter.fail(msg.similar_not_found())
                return
            lines = [msg.similar_header(title, artist)]
            buttons = []
            context.user_data["reco_cache"] = {}
            for i, meta in enumerate(suggestions, 1):
                lines.append(f"{i}. {meta.title} — {meta.artist}")
                context.user_data["reco_cache"][str(i)] = meta
                buttons.append([
                    InlineKeyboardButton(
                        _btn_download(meta.title, i),
                        callback_data=f"searchpick:{i}",
                    )
                ])
            await reporter.update(100, "آماده شد", force=True)
            await status.edit_text(
                "\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons)
            )
        except Exception as e:
            logger.error(f"Similar tracks failed: {e}", exc_info=True)
            await reporter.fail(msg.similar_not_found())
        finally:
            _end_job(context, job)
        return

    if data.startswith("reco:lyrics:"):
        token = data.split(":", 2)[2]
        ref = resolve_lyrics_ref(token)
        if not ref:
            await query.message.reply_text(msg.pick_expired_short())
            return
        title, artist = ref
        if await _reject_if_busy(query.message, context):
            return
        job = _start_job(context, "lyrics")
        status = await query.message.reply_text(msg.searching())
        reporter = ProgressReporter(
            status,
            100,
            "متن آهنگ",
            bot=context.bot,
            user=update.effective_user,
            progress_mode="percent",
        )
        try:
            await reporter.update(20, f"{title} — {artist or msg.UNKNOWN}", force=True)
            text = _lyrics_from_cache(title, artist)
            if not text:
                if _cancel_check(job):
                    await reporter.fail(msg.work_cancelled())
                    return
                result, cancelled = await _await_with_progress(
                    fetch_lyrics(title, artist),
                    reporter,
                    lambda: _cancel_check(job),
                    25,
                    85,
                    "در حال دریافت متن آهنگ...",
                )
                if cancelled:
                    await reporter.fail(msg.work_cancelled())
                    return
                text = (result or {}).get("text") if result else None
            if _cancel_check(job):
                await reporter.fail(msg.work_cancelled())
                return
            if not text:
                await reporter.fail(msg.lyrics_not_found())
                return
            await status.delete()
            await _reply_lyrics(query.message, title, artist, text)
        except Exception as e:
            logger.error(f"Lyrics failed: {e}", exc_info=True)
            await reporter.fail(msg.lyrics_not_found())
        finally:
            _end_job(context, job)
        return

    if data.startswith("reco:art:"):
        token = data.split(":", 2)[2]
        ref = resolve_track_ref(token)
        if not ref:
            await query.message.reply_text(msg.pick_expired_short())
            return
        title, artist = ref
        if await _reject_if_busy(query.message, context):
            return
        job = _start_job(context, "artwork")
        status = await query.message.reply_text(msg.artwork_sending())
        try:
            cover = _cover_from_cache(title, artist)
            if not cover:
                if _cancel_check(job):
                    await status.edit_text(msg.work_cancelled())
                    return
                cover = await _build_watermarked_artwork(title, artist)
            if _cancel_check(job):
                await status.edit_text(msg.work_cancelled())
                return
            if not cover:
                await status.edit_text(msg.artwork_not_found())
                return
            safe_artist = (artist or msg.UNKNOWN).replace("/", "-").strip()
            safe_title = (title or msg.UNKNOWN).replace("/", "-").strip()
            filename = f"{safe_artist} - {safe_title}.jpg"[:180]
            from io import BytesIO
            bio = BytesIO(cover)
            bio.name = filename
            await query.message.reply_document(
                document=bio,
                filename=filename,
                caption=f"🖼 {title} — {_unknown_artist(artist)}",
            )
            try:
                await status.delete()
            except Exception:
                pass
        except Exception as e:
            logger.error(f"Artwork send failed: {e}", exc_info=True)
            try:
                await status.edit_text(msg.artwork_not_found())
            except Exception:
                pass
        finally:
            _end_job(context, job)
        return

    if data.startswith("qual:"):
        value = data.split(":", 1)[1]
        if value not in QUALITIES:
            await query.message.reply_text(msg.quality_invalid())
            return
        user_manager.set_audio_quality(update.effective_user.id, value)
        current = value
        buttons = [
            [
                InlineKeyboardButton(
                    f"{'✅ ' if q == current else '🔘 '}{q} kbps",
                    callback_data=f"qual:{q}",
                )
                for q in ("128", "192")
            ],
            [
                InlineKeyboardButton(
                    f"{'✅ ' if q == current else '🔘 '}{q} kbps",
                    callback_data=f"qual:{q}",
                )
                for q in ("256", "320")
            ],
            [InlineKeyboardButton(
                f"{'✅ ' if current == 'original' else '🔘 '}original (بدون تبدیل)",
                callback_data="qual:original",
            )],
            _back_row(),
        ]
        try:
            await query.message.edit_text(
                msg.quality_set(value) + "\n\n" + msg.quality_status(current),
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        except Exception:
            await query.message.reply_text(msg.quality_set(value))
        return

    if data.startswith("follow:"):
        parts = data.split(":", 2)
        deezer_id = parts[1] if len(parts) > 1 else ""
        artist_name = parts[2] if len(parts) > 2 else ""
        if not deezer_id:
            return
        ok = user_manager.follow_artist(
            update.effective_user.id, artist_name, deezer_id,
        )
        if ok:
            await query.message.reply_text(msg.follow_success(artist_name))
        else:
            await query.message.reply_text(msg.already_following(artist_name))
        return

    if data.startswith("unfollow:"):
        deezer_id = data.split(":", 1)[1]
        rows = user_manager.list_followed_artists(update.effective_user.id)
        name = ""
        for r in rows:
            if r["deezer_artist_id"] == deezer_id:
                name = r["artist_name"]
                break
        removed = user_manager.unfollow_artist(update.effective_user.id, deezer_id)
        if removed:
            await query.message.reply_text(msg.unfollow_success(name or "هنرمند"))
        else:
            await query.message.reply_text(msg.not_following())
        return

    if data.startswith("newrel:"):
        url = data.split(":", 1)[1]
        if not url:
            return
        name, tracks = await TrackMetadata.create_collection(url, _ydl_opts_factory)
        if not tracks:
            await query.message.reply_text(msg.collection_not_found())
            return
        await process_playlist(
            update, context, tracks, name, orchestrator,
            user_manager, admin_logger,
        )
        return

    if data.startswith("catpick:"):
        idx = data.split(":", 1)[1]
        hit = context.user_data.get("search_cache", {}).get(idx)
        if not hit:
            await query.message.reply_text(msg.pick_expired())
            return
        if hit.kind == "track":
            if hit.source == "apple" and hit.url:
                meta = await TrackMetadata.create(hit.url, ydl_opts_factory=_ydl_opts_factory)
            else:
                meta = catalog.hit_to_track_metadata(hit)
            await _download_and_send(query.message, update.effective_user, meta, context)
            return
        if hit.kind in ("album", "playlist"):
            try:
                name, tracks = await catalog.resolve_url(hit.url, _ydl_opts_factory)
            except catalog.CatalogError as exc:
                await query.message.reply_text(str(exc))
                return
            if not tracks:
                await query.message.reply_text(msg.collection_not_found())
                return
            await process_playlist(
                update, context, tracks, name or hit.name, orchestrator,
                user_manager, admin_logger,
            )
            return
        if hit.kind == "artist":
            await _show_artist_page(query.message, hit.id, context, user_id=update.effective_user.id)
            return
        return

    if data.startswith("artistpick:"):
        parts = data.split(":")
        action = parts[1] if len(parts) > 1 else ""
        idx = parts[2] if len(parts) > 2 else ""
        if action == "profile":
            if idx == "follow" and len(parts) > 3:
                artist_id = parts[3]
            else:
                artist_id = context.user_data.get("artist_search_cache", {}).get(idx)
            if not artist_id:
                await query.message.reply_text(msg.pick_expired())
                return
            await _show_artist_page(query.message, artist_id, context, user_id=update.effective_user.id)
            return
        cache = context.user_data.get("artist_cache") or {}
        if action == "track":
            meta = cache.get("tracks", {}).get(idx)
            if not meta:
                await query.message.reply_text(msg.pick_expired())
                return
            await _download_and_send(query.message, update.effective_user, meta, context)
            return
        if action == "album":
            url = cache.get("albums", {}).get(idx)
            if not url:
                await query.message.reply_text(msg.pick_expired())
                return
            name, tracks = await TrackMetadata.create_collection(url, _ydl_opts_factory)
            if not tracks:
                await query.message.reply_text(msg.collection_not_found())
                return
            await process_playlist(
                update, context, tracks, name, orchestrator,
                user_manager, admin_logger,
            )
            return
        return

    if data.startswith("searchpick:"):
        idx = data.split(":", 1)[1]
        meta = (
            context.user_data.get("reco_cache", {}).get(idx)
        )
        if not meta:
            await query.message.reply_text(msg.pick_expired())
            return
        await _download_and_send(query.message, update.effective_user, meta, context)
        return

    if data.startswith("toppick:"):
        idx = data.split(":", 1)[1]
        meta = context.user_data.get("top_cache", {}).get(idx)
        if not meta:
            await query.message.reply_text(msg.pick_expired_short())
            return
        await _download_and_send(query.message, update.effective_user, meta, context)
        return

    if data.startswith("discoverpick:"):
        idx = data.split(":", 1)[1]
        meta = context.user_data.get("discover_cache", {}).get(idx)
        if meta:
            await _download_and_send(query.message, update.effective_user, meta, context)
        else:
            await query.message.reply_text(msg.pick_expired_short())
        return


async def _resolve_similar_tracks(
    title, artist, user_id, limit=8, reporter=None, cancel_check=None,
):
    """Resolve similar track metadata via LLM (preferred) or iTunes fallback.

    Returns a list of TrackMetadata, or ``None`` if cancelled.
    """
    seed_key = ((title or "").strip().lower(), (artist or "").strip().lower())
    suggestions = []
    seen = set()

    def _cancelled():
        try:
            return bool(cancel_check and cancel_check())
        except Exception:
            return False

    async def _append_resolved(rec_title, rec_artist):
        query = f"{rec_title} {rec_artist}".strip() if rec_artist else rec_title
        resolved = await AppleMusicMetadata.search_by_query(query)
        if not resolved or not resolved.title:
            resolved = await AppleMusicMetadata.search_by_query(rec_title)
        if not resolved or not resolved.title:
            return False
        key = (
            resolved.title.strip().lower(),
            (resolved.artist or "").strip().lower(),
        )
        if key == seed_key or key in seen:
            return False
        seen.add(key)
        suggestions.append(TrackMetadata()._copy_from(resolved))
        return True

    recs = None
    if llm_configured():
        if _cancelled():
            return None
        if reporter:
            await reporter.update(15, msg.similar_llm_phase(), force=True)
        result, cancelled = await _await_with_progress(
            recommend_similar(title, artist, limit=limit),
            reporter,
            cancel_check,
            15,
            55,
            msg.similar_llm_phase(),
        )
        if cancelled:
            return None
        recs, usage = result
        user_manager.database.log_llm_usage(
            user_id,
            model=usage.get("model"),
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            cached=False,
            success=bool(usage.get("success") and recs is not None),
            recommendations_count=usage.get("recommendations_count", 0),
        )
        for i, rec in enumerate(recs or []):
            if _cancelled():
                return None
            if len(suggestions) >= limit:
                break
            if reporter:
                await reporter.update(
                    55 + int(20 * (i + 1) / max(len(recs), 1)),
                    msg.similar_resolve_phase(len(suggestions) + 1, limit),
                    force=True,
                )
            await _append_resolved(rec.get("title", ""), rec.get("artist", ""))

    if len(suggestions) < 3:
        queries = []
        if artist:
            queries.append(artist)
        if title and artist:
            queries.append(f"{title} {artist}")
        if title:
            queries.append(title)
        for qi, q in enumerate(queries):
            if _cancelled():
                return None
            if reporter:
                await reporter.update(
                    75 + int(15 * (qi + 1) / max(len(queries), 1)),
                    msg.similar_resolve_phase(len(suggestions) + 1, limit),
                    force=True,
                )
            results = await AppleMusicMetadata.search_many(q, limit=limit)
            for r in results or []:
                if _cancelled():
                    return None
                if len(suggestions) >= limit:
                    break
                await _append_resolved(r.title, r.artist)
            if len(suggestions) >= limit:
                break

    if _cancelled():
        return None
    return suggestions[:limit]


async def _download_and_send(message, user, metadata, context):
    user_id = user.id
    if await _deny_quota(message, context.bot, user):
        return

    if await _reject_if_busy(message, context):
        return

    job = _start_job(context, "track")
    status = await message.reply_text(msg.downloading())
    reporter = ProgressReporter(
        status,
        100,
        "آهنگ",
        bot=context.bot,
        user=user,
        progress_mode="percent",
    )
    await reporter.update(10, f"{metadata.title} — {_unknown_artist(metadata.artist)}")

    preview = PreviewSender(message, metadata)
    preview.start()

    file_path = None
    platform = None
    cached = False
    error_code = None
    try:
        file_path, platform, cached, error_code = await orchestrator.get_or_download(
            metadata,
            reporter,
            bot=context.bot,
            user=user,
            cancel_check=lambda: _cancel_check(job),
        )
        if _cancel_check(job):
            await reporter.fail(msg.download_cancelled())
            return
        if not file_path:
            await reporter.fail(msg.download_fail_message(error_code))
            await log_error(
                context.bot, user, f"Download failed ({error_code})",
                _vip_failure_detail(metadata.title),
            )
            return
        if not (platform and str(platform).endswith("_cache_id")) and not os.path.exists(file_path):
            await reporter.fail(msg.download_fail_message(error_code or "invalid_file"))
            await log_error(
                context.bot, user, "Download failed",
                _vip_failure_detail(metadata.title),
            )
            return

        kb = _track_keyboard(user_id, metadata.title, metadata.artist)
        await reporter.update(95, "در حال ارسال به تلگرام...", force=True)
        sent = await _send_track_audio(
            message, metadata, file_path, platform, reply_markup=kb,
        )
        _store_audio_file_id(metadata, platform, sent)
        user_manager.record_download(
            user_id, metadata.title, metadata.artist, platform,
            metadata.url, metadata.album, cached=cached,
        )
        await log_download(context.bot, user, metadata.title, metadata.artist, platform, cached=cached)
        await status.delete()
    except Exception as e:
        logger.error(f"Send failed: {e}")
        try:
            await status.edit_text(msg.send_failed())
        except Exception:
            pass
        await log_error(context.bot, user, "Send failed", str(e))
    finally:
        await preview.finish(delete=False)
        _end_job(context, job)
        await orchestrator.cleanup(file_path)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_access(update, context):
        return
    await _touch_user(update)

    text = update.message.text.strip()
    user = update.effective_user
    user_id = user.id

    # Collection URL?
    if await TrackMetadata.is_collection_url(text):
        if await _reject_if_busy(update.message, context):
            return
        name, tracks = await TrackMetadata.create_collection(text, _ydl_opts_factory)
        if tracks:
            await process_playlist(
                update, context, tracks, name, orchestrator,
                user_manager, admin_logger,
            )
            return
        await update.message.reply_text(msg.collection_not_found())
        return

    if await _deny_quota(update.message, context.bot, user):
        return

    if await _reject_if_busy(update.message, context):
        return

    job = _start_job(context, "track")
    status_message = await update.message.reply_text(msg.searching())
    metadata = await TrackMetadata.create(text, _ydl_opts_factory)

    if not metadata.title:
        _end_job(context, job)
        await status_message.edit_text(msg.metadata_not_found())
        await log_error(context.bot, user, "Metadata not found", text)
        return

    reporter = ProgressReporter(
        status_message,
        100,
        "آهنگ",
        bot=context.bot,
        user=user,
        progress_mode="percent",
    )
    await reporter.update(10, f"{metadata.title} — {_unknown_artist(metadata.artist)}")

    preview = PreviewSender(update.message, metadata)
    preview.start()

    file_path = None
    try:
        file_path, platform, cached, error_code = await orchestrator.get_or_download(
            metadata,
            reporter,
            bot=context.bot,
            user=user,
            cancel_check=lambda: _cancel_check(job),
        )

        if _cancel_check(job):
            await reporter.fail(msg.download_cancelled())
            return

        is_file_id = bool(platform and str(platform).endswith("_cache_id"))
        if file_path and (is_file_id or os.path.exists(file_path)):
            try:
                kb = _track_keyboard(user_id, metadata.title, metadata.artist)
                await reporter.update(95, "در حال ارسال به تلگرام...", force=True)
                sent = await _send_track_audio(
                    update.message, metadata, file_path, platform, reply_markup=kb,
                )
                _store_audio_file_id(metadata, platform, sent)
                user_manager.record_download(
                    user_id, metadata.title, metadata.artist, platform,
                    metadata.url, metadata.album, cached=cached,
                )
                await log_download(
                    context.bot, user, metadata.title, metadata.artist, platform, cached=cached,
                )
                await status_message.delete()
            except Exception as e:
                logger.error(f"Send failed: {e}")
                await status_message.edit_text(msg.send_failed())
                await log_error(context.bot, user, "Send failed", str(e))
        else:
            await reporter.fail(msg.download_fail_message(error_code))
            await log_error(
                context.bot, user, f"No full track found ({error_code})",
                _vip_failure_detail(text),
            )
    finally:
        await preview.finish(delete=False)
        _end_job(context, job)
        await orchestrator.cleanup(file_path)


_COOKIE_MAX_BYTES = 512 * 1024


def _cookie_file_status():
    """Return ``(ok, detail, updated)`` for the cookie jar currently on disk."""
    path = downloader.cookies_path
    if not os.path.exists(path):
        return False, "cookies.txt missing", None
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            ok, detail = cookie_jar_status(f.read())
    except OSError as e:
        return False, f"cookies.txt unreadable: {e}", None
    updated = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(os.path.getmtime(path)))
    return ok, detail, updated


def _youtube_auth_status():
    """Return ``(healthy, detail)`` for the credentials yt-dlp will actually use."""
    file_ok, file_detail, _updated = _cookie_file_status()
    path = downloader.cookies_path
    if file_ok:
        return True, f"cookies.txt OK — {file_detail} ({path})"
    browser = downloader.cookies_from_browser
    if browser:
        return True, (
            f"cookies.txt unusable ({file_detail}); "
            f"falling back to browser cookies ({browser})"
        )
    return False, (
        f"cookies.txt unusable ({file_detail}) at {path}. "
        "Send a fresh cookies.txt to the bot as a file to fix it — see /cookies."
    )


async def cookies_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    _file_ok, file_detail, updated = _cookie_file_status()
    healthy, _detail = _youtube_auth_status()
    if downloader.cookies_from_browser:
        file_detail += f"\nپشتیبان مرورگر: {downloader.cookies_from_browser}"
    await update.message.reply_text(
        msg.cookies_status(healthy, file_detail, downloader.cookies_path, updated)
    )


async def cookies_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Replace cookies.txt from an admin's uploaded file, if it validates."""
    if not _is_admin(update.effective_user.id):
        return
    doc = update.message.document
    if not doc:
        return
    if doc.file_size and doc.file_size > _COOKIE_MAX_BYTES:
        await update.message.reply_text(msg.cookies_too_large(_COOKIE_MAX_BYTES // 1024))
        return

    tg_file = await context.bot.get_file(doc.file_id)
    raw = bytes(await tg_file.download_as_bytearray())
    text = raw.decode("utf-8", errors="ignore")
    ok, detail = cookie_jar_status(text)
    if not ok:
        logger.warning("Rejected uploaded cookie file: %s", detail)
        await update.message.reply_text(msg.cookies_rejected(detail))
        return

    path = downloader.cookies_path
    backed_up = False
    try:
        if os.path.exists(path):
            shutil.copy2(path, f"{path}.bak")
            backed_up = True
        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        os.replace(tmp_path, path)
        os.chmod(path, 0o600)
    except OSError as e:
        logger.error("Could not write cookies.txt: %s", e)
        await update.message.reply_text(msg.cookies_rejected(str(e)))
        return

    logger.info("cookies.txt replaced via admin upload (%s)", detail)
    await update.message.reply_text(msg.cookies_accepted(detail, backed_up))
    await _check_and_report_cookie_health(context.bot)


async def _cache_sweep_job(context: ContextTypes.DEFAULT_TYPE):
    removed = orchestrator.sweep_cache()
    await log_system(context.bot, "پاکسازی کش", removed=removed)


async def _cookie_health_job(context: ContextTypes.DEFAULT_TYPE):
    await _check_and_report_cookie_health(context.bot)


async def _release_check_job(context: ContextTypes.DEFAULT_TYPE):
    from release_checker import check_new_releases
    try:
        await check_new_releases(context.bot, user_manager.database)
    except Exception as exc:
        logger.error("Release check job failed: %s", exc, exc_info=True)


async def _check_and_report_cookie_health(bot):
    healthy, detail = _youtube_auth_status()
    await report_cookie_health_transition(bot, healthy, detail=detail)
    if not healthy:
        await maybe_alert_cookie_issue(bot, detail=detail)


async def _cache_sweep_fallback_loop(bot):
    while True:
        removed = orchestrator.sweep_cache()
        await log_system(bot, "پاکسازی کش (fallback)", removed=removed)
        await _check_and_report_cookie_health(bot)
        await asyncio.sleep(3600)


async def _on_startup(application):
    gate_ok = await validate_channel_gate(application.bot)
    vip_ok = await validate_vip_log_channel(application.bot)
    _, yt_ok = get_credentials_status()
    if not vip_ok:
        await notify_admin_vip_issue(
            application.bot,
            "⚠️ لاگ VIP کار نمی‌کند.\n"
            "ربات را ادمین کانال خصوصی کن، VIP_LOG_CHANNEL_ID را در .env بگذار، "
            "و /viplogtest را بزن.",
        )
    await log_startup(application.bot, gate_ok, vip_ok, yt_ok)
    removed = orchestrator.sweep_cache()
    await log_system(application.bot, "پاکسازی کش (startup)", removed=removed)
    await _check_and_report_cookie_health(application.bot)
    try:
        from api.webapp_menu import configure_webapp_menu
        await configure_webapp_menu(application.bot)
    except Exception:
        logger.exception("Mini App menu setup skipped")
    if application.job_queue:
        application.job_queue.run_repeating(_cache_sweep_job, interval=3600, first=60)
        application.job_queue.run_repeating(_cookie_health_job, interval=3600, first=120)
        application.job_queue.run_repeating(_release_check_job, interval=6 * 3600, first=300)
        return
    logger.warning(
        "JobQueue unavailable; using asyncio fallback for cache sweep. "
        'Install with: pip install "python-telegram-bot[job-queue]"'
    )
    asyncio.create_task(_cache_sweep_fallback_loop(application.bot))


async def _send_report(message, text, reply_markup=None, edit=False):
    if edit and hasattr(message, "edit_text"):
        await message.edit_text(text, reply_markup=reply_markup)
    else:
        await message.reply_text(text, reply_markup=reply_markup)


async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    db = user_manager.database
    summary = db.global_report_summary()
    text = rpt.format_global_summary(summary, _platform_fa)
    await update.message.reply_text(text, reply_markup=rpt.build_global_menu_keyboard())


async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    page = 0
    if context.args:
        try:
            page = max(int(context.args[0]) - 1, 0)
        except ValueError:
            pass
    await _show_users_page(update.message, page)


async def user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("نحوه استفاده: /user <شناسه کاربر>")
        return
    await _show_user_detail(update.message, context.args[0])


async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    status = await update.message.reply_text("در حال آماده‌سازی خروجی...")
    db = user_manager.database
    payload = db.export_all()
    filename = f"hiit_radio_export_{int(time.time())}.json"
    path = _BASE_DIR / filename
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        with open(path, "rb") as f:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=f,
                filename=filename,
                caption="خروجی کامل پایگاه داده",
            )
        await status.delete()
    finally:
        if path.exists():
            path.unlink()


async def _show_users_page(message, page, edit=False):
    db = user_manager.database
    rows, total, total_pages = db.list_users(page, rpt.PER_PAGE)
    text = rpt.format_user_list(rows, page, total_pages, total)
    kb = rpt.build_pagination_keyboard("users", page, total_pages)
    await _send_report(message, text, kb, edit=edit)


async def _show_user_detail(message, user_id, edit=False):
    db = user_manager.database
    summary = db.get_user_summary(user_id)
    if not summary:
        text = f"کاربر {user_id} یافت نشد."
        await _send_report(message, text, edit=edit)
        return
    artists = db.user_top_artists(user_id, limit=5)
    text = rpt.format_user_detail(summary, artists)
    await _send_report(message, text, rpt.build_user_menu_keyboard(user_id), edit=edit)


async def _show_global_section(message, section, page, edit=False):
    db = user_manager.database
    if section == "dl":
        rows, total, total_pages = db.list_recent_downloads(page, rpt.PER_PAGE)
        text = rpt.format_download_page(rows, page, total_pages, total, "دانلودهای اخیر")
    elif section == "req":
        rows, total, total_pages = db.list_recent_requests(page, rpt.PER_PAGE)
        text = rpt.format_request_page(rows, page, total_pages, total, "درخواست‌های اخیر")
    elif section == "evt":
        rows, total, total_pages = db.list_recent_analytics(page, rpt.PER_PAGE)
        text = rpt.format_analytics_page(rows, page, total_pages, total, "رویدادهای تحلیلی")
    elif section == "llm":
        rows, total, total_pages = db.list_recent_llm_usage(page, rpt.PER_PAGE)
        text = rpt.format_llm_page(rows, page, total_pages, total, "استفاده LLM")
    elif section == "cache":
        rows, total, total_pages = db.list_cache_entries(page, rpt.PER_PAGE)
        text = rpt.format_cache_page(rows, page, total_pages, total)
    else:
        return
    scope = f"global:{section}"
    await _send_report(
        message, text, rpt.build_pagination_keyboard(scope, page, total_pages), edit=edit,
    )


async def _show_user_section(message, user_id, section, page, edit=False):
    db = user_manager.database
    uid = str(user_id)
    if section == "artists":
        artists = db.user_top_artists(uid, limit=10)
        lines = [f"هنرمندان کاربر {uid}\n"]
        if artists:
            for row in artists:
                lines.append(f"• {row['artist']} ({row['download_count']})")
        else:
            lines.append("موردی نیست.")
        await _send_report(
            message, "\n".join(lines), rpt.build_user_menu_keyboard(uid), edit=edit,
        )
        return
    if section == "dl":
        rows, total, total_pages = db.list_user_downloads(uid, page, rpt.PER_PAGE)
        text = rpt.format_download_page(rows, page, total_pages, total, f"دانلودهای {uid}")
    elif section == "req":
        rows, total, total_pages = db.list_user_requests(uid, page, rpt.PER_PAGE)
        text = rpt.format_request_page(rows, page, total_pages, total, f"درخواست‌های {uid}")
    elif section == "evt":
        rows, total, total_pages = db.list_user_analytics(uid, page, rpt.PER_PAGE)
        text = rpt.format_analytics_page(rows, page, total_pages, total, f"رویدادهای {uid}")
    elif section == "llm":
        rows, total, total_pages = db.list_user_llm_usage(uid, page, rpt.PER_PAGE)
        text = rpt.format_llm_page(rows, page, total_pages, total, f"LLM کاربر {uid}")
    else:
        return
    scope = f"user:{uid}:{section}"
    extra = [InlineKeyboardButton("پروفایل", callback_data=f"rpt:user:{uid}:profile")]
    await _send_report(
        message,
        text,
        rpt.build_pagination_keyboard(scope, page, total_pages, extra=extra),
        edit=edit,
    )


async def report_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _is_admin(update.effective_user.id):
        return
    data = (query.data or "").split(":")
    if len(data) < 2:
        return
    message = query.message
    if data[1] == "menu":
        db = user_manager.database
        summary = db.global_report_summary()
        text = rpt.format_global_summary(summary, _platform_fa)
        await message.edit_text(text, reply_markup=rpt.build_global_menu_keyboard())
        return
    if data[1] == "users":
        page = int(data[2]) if len(data) > 2 else 0
        await _show_users_page(message, page, edit=True)
        return
    if data[1] == "global" and len(data) >= 4:
        section, page = data[2], int(data[3])
        await _show_global_section(message, section, page, edit=True)
        return
    if data[1] == "user" and len(data) >= 4:
        uid = data[2]
        if data[3] == "profile":
            await _show_user_detail(message, uid, edit=True)
            return
        if data[3] == "artists":
            await _show_user_section(message, uid, "artists", 0, edit=True)
            return
        if len(data) >= 5:
            section, page = data[3], int(data[4])
            await _show_user_section(message, uid, section, page, edit=True)
            return
        await _show_user_detail(message, uid, edit=True)


def _describe_user_request(update):
    if update.channel_post:
        return None
    chat = update.effective_chat
    if chat and chat.type == "channel":
        return None
    user = update.effective_user
    if not user:
        return None
    if update.callback_query:
        data = update.callback_query.data or ""
        if data.startswith("rpt:"):
            return None
        return "callback", data[:500]
    if update.inline_query:
        return "inline", (update.inline_query.query or "")[:500]
    msg_obj = update.effective_message
    if not msg_obj:
        return None
    text = msg_obj.text or msg_obj.caption or ""
    if text.startswith("/"):
        cmd = text.split()[0].split("@")[0].lower()
        if cmd in _ADMIN_COMMANDS:
            return None
        if cmd == "/discover":
            return "discover", text[:500]
        return "command", text[:500]
    if text:
        return "message", text[:500]
    return "message", (msg_obj.content_type or "unknown")[:500]


async def vip_update_logger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log every incoming Telegram update to the VIP channel and DB."""
    await log_incoming_update(context.bot, update)
    req = _describe_user_request(update)
    if req and update.effective_user:
        req_type, req_text = req
        user_manager.database.log_user_request(
            update.effective_user.id, req_type, req_text,
        )


async def _on_shutdown(application):
    await log_shutdown(application.bot)


def main():
    if not BOT_TOKEN:
        env_path = _BASE_DIR / ".env"
        logger.error(
            "BOT_TOKEN is not set. Create %s with BOT_TOKEN=your_telegram_bot_token "
            "or set the variable in the systemd unit (EnvironmentFile=).",
            env_path,
        )
        sys.exit(1)

    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .connect_timeout(TG_CONNECT_TIMEOUT)
        .read_timeout(TG_READ_TIMEOUT)
        .write_timeout(TG_WRITE_TIMEOUT)
        .media_write_timeout(TG_MEDIA_WRITE_TIMEOUT)
        .pool_timeout(TG_POOL_TIMEOUT)
        .post_init(_on_startup)
        .post_shutdown(_on_shutdown)
        .build()
    )

    application.add_handler(TypeHandler(Update, vip_update_logger), group=-1)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("analytics", analytics_command))
    application.add_handler(CommandHandler("creds", creds_command))
    application.add_handler(
        CommandHandler(
            "channelid",
            channelid_command,
            filters.COMMAND
            & (
                filters.ChatType.PRIVATE
                | filters.ChatType.GROUPS
                | filters.ChatType.CHANNEL
            ),
        )
    )
    application.add_handler(CommandHandler("viplogtest", viplogtest_command))
    application.add_handler(CommandHandler("cookies", cookies_command))
    application.add_handler(CommandHandler("report", report_command))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("user", user_command))
    application.add_handler(CommandHandler("export", export_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("liked", liked_command))
    application.add_handler(CommandHandler("top", top_command))
    application.add_handler(CommandHandler("discover", discover_command))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("quality", quality_command))
    application.add_handler(CommandHandler("artist", artist_command))
    application.add_handler(CommandHandler("follow", follow_command))
    application.add_handler(CommandHandler("unfollow", unfollow_command))
    application.add_handler(CommandHandler("following", following_command))
    application.add_handler(CommandHandler("premium", premium_command))
    application.add_handler(CommandHandler("invite", invite_command))
    application.add_handler(CommandHandler("grant", grant_command))
    application.add_handler(CommandHandler("topup", topup_command))
    application.add_handler(CommandHandler("aboutme", aboutme_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CallbackQueryHandler(report_callback, pattern=r"^rpt:"))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(InlineQueryHandler(inline_search))
    payments.register_handlers(application)
    if ADMIN_ID:
        application.add_handler(
            MessageHandler(
                filters.Document.ALL
                & filters.ChatType.PRIVATE
                & filters.User(user_id=int(ADMIN_ID)),
                cookies_document,
            )
        )
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    status_text, yt_ok = get_credentials_status()
    for line in status_text.splitlines():
        logger.info(line)
    if not yt_ok:
        logger.warning("YouTube full downloads unavailable until logged-in cookies are configured")

    application.run_polling()


if __name__ == "__main__":
    main()
