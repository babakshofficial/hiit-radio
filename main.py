import asyncio
import json
import logging
import os
import secrets
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
from downloader import MusicDownloader
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
)
import admin_logger
from progress import ProgressReporter
from download_orchestrator import DownloadOrchestrator
from playlist_handler import process_playlist
from recommendations import recommendation_keyboard, resolve_lyrics_ref
from lyrics_service import fetch_lyrics
from llm_service import (
    is_configured as llm_configured,
    recommend_songs,
    get_cached_recommendations,
    set_cached_recommendations,
)
import messages as msg
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
    "/broadcast", "/report", "/users", "/user", "/export",
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


def _is_admin(user_id):
    return str(user_id) == str(ADMIN_ID)


def _platform_fa(platform):
    return msg.platform_fa(platform)


def _unknown_artist(artist):
    return msg.unknown_artist(artist)


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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _touch_user(update)
    await update.message.reply_text(msg.start_text())


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

    status = await update.message.reply_text(msg.discover_preparing())

    recs = get_cached_recommendations(user_id)
    if recs is not None:
        db.log_llm_usage(
            user_id,
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            cached=True,
            success=True,
            recommendations_count=len(recs),
        )
    else:
        recs, usage = await recommend_songs(history, user_id=user_id, limit=10)
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
            await status.edit_text(msg.discover_llm_error())
            return
        set_cached_recommendations(user_id, recs)

    suggestions = []
    seen = set()
    history_keys = {
        ((r.get("title") or "").strip().lower(), (r.get("artist") or "").strip().lower())
        for r in history if r.get("title")
    }

    for rec in recs:
        title = rec.get("title", "").strip()
        artist = rec.get("artist", "").strip()
        if not title:
            continue
        key = (title.lower(), artist.lower())
        if key in seen or key in history_keys:
            continue

        query = f"{title} {artist}".strip() if artist else title
        resolved = await AppleMusicMetadata.search_by_query(query)
        if not resolved or not resolved.title:
            resolved = await AppleMusicMetadata.search_by_query(title)
        if not resolved or not resolved.title:
            continue

        res_key = (resolved.title.strip().lower(), (resolved.artist or "").strip().lower())
        if res_key in seen or res_key in history_keys:
            continue
        seen.add(res_key)
        suggestions.append(TrackMetadata()._copy_from(resolved))
        if len(suggestions) >= 10:
            break

    if not suggestions:
        await status.edit_text(msg.discover_no_results())
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
    await status.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons))


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
    job = context.user_data.get("active_job")
    if job:
        job["cancel"] = True
        await log_system(context.bot, "لغو پلی‌لیست", user=update.effective_user)
        await update.message.reply_text(msg.cancel_ok())
    else:
        await update.message.reply_text(msg.cancel_no_job())


def _source_label(metadata):
    if metadata.url and "spotify.com" in metadata.url:
        return "spotify"
    if metadata.url and "music.apple.com" in metadata.url:
        return "apple"
    return "youtube"


def _store_audio_file_id(metadata, platform, msg):
    if not msg or not msg.audio:
        return
    source = _source_label(metadata)
    if platform and platform.endswith("_cache"):
        source = platform.replace("_cache", "")
    orchestrator.cache.save_telegram_file_id(
        metadata.title, metadata.artist, source, msg.audio.file_id,
    )


async def inline_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = (update.inline_query.query or "").strip()
    if len(query) < 2:
        return
    if not await ensure_access(update, context):
        return

    results = await AppleMusicMetadata.search_many(query, limit=5)
    inline_results = []
    for i, r in enumerate(results):
        meta = TrackMetadata()._copy_from(r)
        source = _source_label(meta)
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
    await update.inline_query.answer(inline_results, cache_time=30)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await ensure_access(update, context):
        return
    data = query.data or ""

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

    if data.startswith("reco:lyrics:"):
        token = data.split(":", 2)[2]
        ref = resolve_lyrics_ref(token)
        if not ref:
            await query.message.reply_text(msg.pick_expired_short())
            return
        title, artist = ref
        status = await query.message.reply_text(msg.searching())
        text = _lyrics_from_cache(title, artist)
        if not text:
            result = await fetch_lyrics(title, artist)
            text = (result or {}).get("text") if result else None
        if not text:
            await status.edit_text(msg.lyrics_not_found())
            return
        await status.delete()
        await _reply_lyrics(query.message, title, artist, text)
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

    if data.startswith("discoverpick:"):
        idx = data.split(":", 1)[1]
        meta = context.user_data.get("discover_cache", {}).get(idx)
        if meta:
            await _download_and_send(query.message, update.effective_user, meta, context)
        else:
            await query.message.reply_text(msg.pick_expired_short())
        return


async def _download_and_send(message, user, metadata, context):
    user_id = user.id
    allowed, wait_time = user_manager.check_rate_limit(user_id)
    if not allowed:
        await log_rate_limit(context.bot, user, wait_time // 60)
        await message.reply_text(msg.rate_limit(wait_time // 60))
        return

    status = await message.reply_text(msg.downloading())
    reporter = ProgressReporter(status, 1, "آهنگ", bot=context.bot, user=user)
    await reporter.update(1, f"{metadata.title} — {_unknown_artist(metadata.artist)}")

    file_path, platform, cached = await orchestrator.get_or_download(
        metadata, reporter, bot=context.bot, user=user,
    )
    if not file_path or not os.path.exists(file_path):
        await reporter.fail(msg.download_not_found())
        await log_error(
            context.bot, user, "Download failed",
            _vip_failure_detail(metadata.title),
        )
        return

    try:
        kb = recommendation_keyboard(metadata.artist, metadata.title)
        with open(file_path, "rb") as audio:
            sent = await message.reply_audio(
                audio=audio,
                title=metadata.title,
                performer=metadata.artist,
                reply_markup=kb,
                connect_timeout=TG_CONNECT_TIMEOUT,
                read_timeout=TG_READ_TIMEOUT,
                write_timeout=TG_WRITE_TIMEOUT,
                pool_timeout=TG_POOL_TIMEOUT,
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
        await status.edit_text(msg.send_failed())
    finally:
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
        name, tracks = await TrackMetadata.create_collection(text)
        if tracks:
            await process_playlist(
                update, context, tracks, name, orchestrator,
                user_manager, admin_logger,
            )
            return
        await update.message.reply_text(msg.collection_not_found())
        return

    allowed, wait_time = user_manager.check_rate_limit(user_id)
    if not allowed:
        await log_rate_limit(context.bot, user, wait_time // 60)
        await update.message.reply_text(msg.rate_limit(wait_time // 60))
        return

    status_message = await update.message.reply_text(msg.searching())
    metadata = await TrackMetadata.create(text)

    if not metadata.title:
        await status_message.edit_text(msg.metadata_not_found())
        await log_error(context.bot, user, "Metadata not found", text)
        return

    reporter = ProgressReporter(status_message, 1, "آهنگ", bot=context.bot, user=user)
    await reporter.update(1, f"{metadata.title} — {_unknown_artist(metadata.artist)}")

    file_path, platform, cached = await orchestrator.get_or_download(
        metadata, reporter, bot=context.bot, user=user,
    )

    if file_path and os.path.exists(file_path):
        try:
            kb = recommendation_keyboard(metadata.artist, metadata.title)
            with open(file_path, "rb") as audio:
                sent = await update.message.reply_audio(
                    audio=audio,
                    title=metadata.title,
                    performer=metadata.artist,
                    reply_markup=kb,
                    connect_timeout=TG_CONNECT_TIMEOUT,
                    read_timeout=TG_READ_TIMEOUT,
                    write_timeout=TG_WRITE_TIMEOUT,
                    pool_timeout=TG_POOL_TIMEOUT,
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
        await orchestrator.cleanup(file_path)
    else:
        await reporter.fail(msg.download_not_found())
        await log_error(
            context.bot, user, "No full track found",
            _vip_failure_detail(text),
        )


async def _cache_sweep_job(context: ContextTypes.DEFAULT_TYPE):
    removed = orchestrator.sweep_cache()
    await log_system(context.bot, "پاکسازی کش", removed=removed)


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


async def _cache_sweep_fallback_loop(bot):
    """Hourly cache sweep when PTB JobQueue is unavailable."""
    await asyncio.sleep(60)
    while True:
        removed = orchestrator.sweep_cache()
        await log_system(bot, "پاکسازی کش (fallback)", removed=removed)
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
    if application.job_queue:
        application.job_queue.run_repeating(_cache_sweep_job, interval=3600, first=60)
        return
    logger.warning(
        "JobQueue unavailable; using asyncio fallback for cache sweep. "
        'Install with: pip install "python-telegram-bot[job-queue]"'
    )
    asyncio.create_task(_cache_sweep_fallback_loop(application.bot))


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
    application.add_handler(CommandHandler("report", report_command))
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("user", user_command))
    application.add_handler(CommandHandler("export", export_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("discover", discover_command))
    application.add_handler(CommandHandler("aboutme", aboutme_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CallbackQueryHandler(report_callback, pattern=r"^rpt:"))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(InlineQueryHandler(inline_search))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    status_text, yt_ok = get_credentials_status()
    for line in status_text.splitlines():
        logger.info(line)
    if not yt_ok:
        logger.warning("YouTube full downloads unavailable until logged-in cookies are configured")

    application.run_polling()


if __name__ == "__main__":
    main()
