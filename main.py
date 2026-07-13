import asyncio
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
    validate_vip_log_channel,
)
import admin_logger
from progress import ProgressReporter
from download_orchestrator import DownloadOrchestrator
from playlist_handler import process_playlist
from recommendations import recommendation_keyboard
from search_parser import parse_search_command, format_search_help

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

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
    if not platform:
        return "نامشخص"
    p = platform.lower()
    if "spotify" in p:
        return "اسپاتیفای"
    if "apple" in p:
        return "اپل موزیک"
    if "youtube" in p:
        return "یوتیوب"
    if "soundcloud" in p:
        return "ساندکلاود"
    if "cache" in p:
        return "کش"
    return platform


def _unknown_artist(artist):
    return artist or "نامشخص"


def _vip_failure_detail(context=""):
    """Technical detail for VIP admin logs only — never show to users."""
    _, yt_ok = get_credentials_status()
    parts = []
    if context:
        parts.append(str(context)[:300])
    parts.append(f"youtube={'OK' if yt_ok else 'FAIL'}")
    return " | ".join(parts)


def _btn_redownload(title):
    label = (title or "نامشخص")[:26]
    return f"🔄 دانلود مجدد: {label}"


def _btn_download(title, index=None):
    label = (title or "نامشخص")[:24]
    if index is not None:
        return f"{index}. دانلود «{label}»"
    return f"دانلود «{label}»"


async def _touch_user(update):
    u = update.effective_user
    if u:
        user_manager.touch_user(u.id, u.username, u.first_name)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _touch_user(update)
    await update.message.reply_text(
        "سلام! من ربات دانلودر موزیک HiiT Radio هستم.\n\n"
        "لینک اپل موزیک، اسپاتیفای، آلبوم/پلی‌لیست، یا نام آهنگ بفرست.\n\n"
        "/help — راهنما\n/history — دانلودهای اخیر\n/discover — پیشنهاد شخصی\n"
        "/search genre:lofi — جستجوی ژانر/مود\n/cancel — توقف پلی‌لیست"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_access(update, context):
        return
    await update.message.reply_text(
        "لینک آهنگ، آلبوم، پلی‌لیست یا نام آهنگ را ارسال کن.\n"
        "اینلاین: @HiiTRadioBot نام آهنگ در هر چتی\n"
        "محدودیت: ۱۰ دانلود در ساعت (هر آهنگ در پلی‌لیست جداگانه).\n\n"
        + format_search_help()
    )


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

    if msg.forward_from_chat:
        chat = msg.forward_from_chat
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
    if msg.sender_chat:
        chat = msg.sender_chat
        await msg.reply_text(
            f"شناسه چت: `{chat.id}`\n\nدر .env:\nVIP_LOG_CHANNEL_ID={chat.id}",
            parse_mode="Markdown",
        )
        return
    await msg.reply_text(
        "یک پیام از کانال VIP را به این چت **فوروارد** کن (با حفظ نام فرستنده).\n"
        "یا در خود کانال یک پیام بفرست و همانجا /channelid را بزن."
    )


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_access(update, context):
        return
    await _touch_user(update)
    rows = user_manager.get_user_history(update.effective_user.id, limit=10)
    if not rows:
        await update.message.reply_text("هنوز دانلودی ثبت نشده.")
        return
    lines = ["📜 دانلودهای اخیر:\n"]
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
    db = user_manager.database
    artists = db.user_top_artists(update.effective_user.id, limit=3)
    if not artists:
        artists = db.global_top_artists(limit=3)
    if not artists:
        await update.message.reply_text("هنوز داده کافی برای پیشنهاد نیست.")
        return

    suggestions = []
    seen = set()
    for row in artists:
        name = row["artist"]
        results = await AppleMusicMetadata.search_many(f"{name} new", limit=3)
        for r in results:
            key = (r.title, r.artist)
            if key in seen:
                continue
            seen.add(key)
            meta = TrackMetadata()._copy_from(r)
            suggestions.append(meta)
            if len(suggestions) >= 9:
                break
        if len(suggestions) >= 9:
            break

    if not suggestions:
        await update.message.reply_text("پیشنهادی یافت نشد.")
        return

    lines = ["🎧 پیشنهاد برای شما:\n"]
    buttons = []
    for i, s in enumerate(suggestions[:9], 1):
        lines.append(f"{i}. {s.title} — {s.artist}")
        buttons.append([
            InlineKeyboardButton(
                _btn_download(s.title, i),
                callback_data=f"discoverpick:{i}",
            )
        ])
    context.user_data["discover_cache"] = {str(i): s for i, s in enumerate(suggestions[:9], 1)}
    await update.message.reply_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons))


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await ensure_access(update, context):
        return
    parsed = parse_search_command(update.message.text)
    if not parsed:
        await update.message.reply_text(format_search_help())
        return
    _, _, query = parsed[0]
    results = await AppleMusicMetadata.search_many(query, limit=5)
    if not results:
        await update.message.reply_text("نتیجه‌ای یافت نشد.")
        return
    lines = [f"🔍 نتایج برای «{query}»:\n"]
    buttons = []
    context.user_data["search_cache"] = {}
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r.title} — {r.artist}")
        context.user_data["search_cache"][str(i)] = TrackMetadata()._copy_from(r)
        buttons.append([
            InlineKeyboardButton(
                _btn_download(r.title, i),
                callback_data=f"searchpick:{i}",
            )
        ])
    await update.message.reply_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons))


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
        await update.message.reply_text("⏹ درخواست توقف ثبت شد...")
    else:
        await update.message.reply_text("کار فعالی در حال اجرا نیست.")


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
        desc = f"{meta.artist} — برای دانلود لمس کنید"
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
            await query.message.reply_text("رکورد یافت نشد.")
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
            await query.message.reply_text("آهنگی یافت نشد.")
            return
        lines = [f"🎵 آهنگ‌های بیشتر از {artist}:\n"]
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
        artist = data.split(":", 2)[2]
        results = await AppleMusicMetadata.search_many(f"{artist} similar", limit=5)
        if not results:
            await query.message.reply_text("آهنگ مشابه یافت نشد.")
            return
        lines = [f"🎵 مشابه {artist}:\n"]
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

    if data.startswith("searchpick:"):
        idx = data.split(":", 1)[1]
        meta = (
            context.user_data.get("search_cache", {}).get(idx)
            or context.user_data.get("reco_cache", {}).get(idx)
        )
        if not meta:
            await query.message.reply_text("انتخاب منقضی شده. دوباره جستجو کنید.")
            return
        await _download_and_send(query.message, update.effective_user, meta, context)
        return

    if data.startswith("discoverpick:"):
        idx = data.split(":", 1)[1]
        meta = context.user_data.get("discover_cache", {}).get(idx)
        if meta:
            await _download_and_send(query.message, update.effective_user, meta, context)
        else:
            await query.message.reply_text("انتخاب منقضی شده.")
        return


async def _download_and_send(message, user, metadata, context):
    user_id = user.id
    allowed, wait_time = user_manager.check_rate_limit(user_id)
    if not allowed:
        await log_rate_limit(context.bot, user, wait_time // 60)
        await message.reply_text(f"محدودیت دانلود. {wait_time // 60} دقیقه صبر کنید.")
        return

    status = await message.reply_text("🔍 در حال دانلود...")
    reporter = ProgressReporter(status, 1, "آهنگ", bot=context.bot, user=user)
    await reporter.update(1, f"{metadata.title} — {_unknown_artist(metadata.artist)}")

    file_path, platform, cached = await orchestrator.get_or_download(
        metadata, reporter, bot=context.bot, user=user,
    )
    if not file_path or not os.path.exists(file_path):
        await reporter.fail("نسخه کامل پیدا نشد.")
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
                read_timeout=120,
                write_timeout=120,
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
        await status.edit_text("❌ ارسال آهنگ ممکن نشد. لطفاً دوباره تلاش کنید.")
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
        await update.message.reply_text("❌ آلبوم/پلی‌لیست شناسایی نشد.")
        return

    allowed, wait_time = user_manager.check_rate_limit(user_id)
    if not allowed:
        await log_rate_limit(context.bot, user, wait_time // 60)
        await update.message.reply_text(f"محدودیت دانلود. {wait_time // 60} دقیقه صبر کنید.")
        return

    status_message = await update.message.reply_text("🔍 در حال بررسی...")
    metadata = await TrackMetadata.create(text)

    if not metadata.title:
        await status_message.edit_text("❌ اطلاعات آهنگ یافت نشد.")
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
                    read_timeout=120,
                    write_timeout=120,
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
            await status_message.edit_text("❌ ارسال آهنگ ممکن نشد. لطفاً دوباره تلاش کنید.")
            await log_error(context.bot, user, "Send failed", str(e))
        await orchestrator.cleanup(file_path)
    else:
        await reporter.fail("نسخه کامل پیدا نشد.")
        await log_error(
            context.bot, user, "No full track found",
            _vip_failure_detail(text),
        )


async def _cache_sweep_job(context: ContextTypes.DEFAULT_TYPE):
    removed = orchestrator.sweep_cache()
    await log_system(context.bot, "پاکسازی کش", removed=removed)


async def vip_update_logger(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log every incoming Telegram update to the VIP channel."""
    await log_incoming_update(context.bot, update)


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
    application.add_handler(CommandHandler("channelid", channelid_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("discover", discover_command))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
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
