"""Sequential unlimited playlist/album download handler."""

import logging
import os

from messages import (
    playlist_cancelled,
    playlist_empty,
    playlist_rate_limited,
    playlist_start,
    playlist_summary,
    unknown_artist,
)
from progress import ProgressReporter
from recommendations import recommendation_keyboard

logger = logging.getLogger(__name__)


async def process_playlist(update, context, tracks, collection_name, orchestrator,
                           user_manager, admin_logger):
    """Download and send all tracks sequentially with progress."""
    user = update.effective_user
    user_id = user.id
    bot = context.bot
    total = len(tracks)
    if total == 0:
        await update.message.reply_text(playlist_empty())
        return

    context.user_data["active_job"] = {"cancel": False, "type": "playlist"}
    status = await update.message.reply_text(playlist_start(collection_name, total))
    await admin_logger.log_playlist_start(bot, user, collection_name, total)

    reporter = ProgressReporter(
        status, total, collection_name or "پلی‌لیست", bot=bot, user=user,
    )
    sent = 0
    failed = 0
    rate_limited = False
    cancelled = False
    stop_reason = None

    for i, track in enumerate(tracks, 1):
        if context.user_data.get("active_job", {}).get("cancel"):
            cancelled = True
            stop_reason = "لغو توسط کاربر"
            await reporter.fail(playlist_cancelled(sent, total))
            break

        allowed, wait_time = user_manager.check_rate_limit(user_id)
        if not allowed:
            rate_limited = True
            stop_reason = f"محدودیت نرخ ({wait_time // 60} دقیقه)"
            await admin_logger.log_rate_limit(bot, user, wait_time // 60)
            await reporter.fail(
                playlist_rate_limited(wait_time // 60, sent, total)
            )
            break

        await reporter.update(i, f"{track.title} — {unknown_artist(track.artist)}")
        await admin_logger.log_playlist_track(
            bot, user, i, total, track.title, track.artist, "در حال دانلود",
        )

        file_path, platform, cached = await orchestrator.get_or_download(
            track, reporter, bot=bot, user=user,
        )
        if not file_path or not os.path.exists(file_path):
            failed += 1
            await admin_logger.log_playlist_track(
                bot, user, i, total, track.title, track.artist, "ناموفق",
            )
            continue

        try:
            kb = recommendation_keyboard(track.artist, track.title)
            with open(file_path, 'rb') as audio:
                sent_msg = await update.message.reply_audio(
                    audio=audio,
                    title=track.title,
                    performer=track.artist,
                    reply_markup=kb,
                    read_timeout=120,
                    write_timeout=120,
                )
            if sent_msg and sent_msg.audio:
                source = "spotify" if track.url and "spotify.com" in track.url else (
                    "apple" if track.url and "music.apple.com" in track.url else "youtube"
                )
                if platform and platform.endswith("_cache"):
                    source = platform.replace("_cache", "")
                orchestrator.cache.save_telegram_file_id(
                    track.title, track.artist, source, sent_msg.audio.file_id,
                )
            user_manager.record_download(
                user_id, track.title, track.artist, platform,
                track.url, track.album, cached=cached,
            )
            await admin_logger.log_download(
                bot, user, track.title, track.artist, platform,
                cached=cached, playlist_info=f"{i}/{total} {collection_name}",
            )
            await admin_logger.log_playlist_track(
                bot, user, i, total, track.title, track.artist, "ارسال شد",
            )
            sent += 1
        except Exception as e:
            logger.error(f"Playlist send failed track {i}: {e}")
            failed += 1
            await admin_logger.log_error(bot, user, "Playlist send failed", str(e))
            await admin_logger.log_playlist_track(
                bot, user, i, total, track.title, track.artist, f"خطا: {e}",
            )
        finally:
            await orchestrator.cleanup(file_path)

    context.user_data.pop("active_job", None)

    if cancelled or rate_limited:
        await admin_logger.log_playlist_done(
            bot, user, collection_name, sent, total, failed, reason=stop_reason,
        )
    elif not rate_limited and not cancelled:
        await reporter.done(playlist_summary(sent, total, failed))
        await admin_logger.log_playlist_done(
            bot, user, collection_name, sent, total, failed,
        )
