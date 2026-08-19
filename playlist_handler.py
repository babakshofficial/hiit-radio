"""Sequential unlimited playlist/album download handler."""

import logging
import os
import re
import zipfile
from io import BytesIO

import jobs
import entitlements
import payments
from cache_manager import content_key
from messages import (
    playlist_cancelled,
    playlist_empty,
    playlist_rate_limited,
    playlist_start,
    playlist_summary,
    playlist_zip_caption,
    playlist_zip_sending,
    quota_exceeded,
    unknown_artist,
)
from progress import ProgressReporter
from recommendations import recommendation_keyboard

logger = logging.getLogger(__name__)
TG_CONNECT_TIMEOUT = float(os.getenv("TG_CONNECT_TIMEOUT", "30"))
TG_READ_TIMEOUT = float(os.getenv("TG_READ_TIMEOUT", "300"))
TG_WRITE_TIMEOUT = float(os.getenv("TG_WRITE_TIMEOUT", "300"))
TG_POOL_TIMEOUT = float(os.getenv("TG_POOL_TIMEOUT", "30"))


def _safe_zip_name(title, artist):
    name = f"{artist or 'Unknown'} - {title or 'track'}.mp3"
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip()[:180]


async def _send_playlist_zip(message, collection_name, entries, bot):
    """Build and send a ZIP of successfully downloaded tracks."""
    if len(entries) < 2:
        return
    status = await message.reply_text(
        playlist_zip_sending(collection_name, len(entries)),
    )
    bio = BytesIO()
    added = 0
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as zf:
        used_names = set()
        for path, filename in entries:
            if not path or not os.path.exists(path):
                continue
            arcname = filename
            base, ext = os.path.splitext(filename)
            n = 2
            while arcname in used_names:
                arcname = f"{base} ({n}){ext}"
                n += 1
            used_names.add(arcname)
            zf.write(path, arcname=arcname)
            added += 1
    if added < 2:
        try:
            await status.delete()
        except Exception:
            pass
        return
    bio.seek(0)
    safe_collection = re.sub(r'[\\/:*?"<>|]', "_", collection_name or "playlist")[:80]
    bio.name = f"{safe_collection}.zip"
    await message.reply_document(
        document=bio,
        filename=bio.name,
        caption=playlist_zip_caption(collection_name, added),
        connect_timeout=TG_CONNECT_TIMEOUT,
        read_timeout=TG_READ_TIMEOUT,
        write_timeout=TG_WRITE_TIMEOUT,
        pool_timeout=TG_POOL_TIMEOUT,
    )
    try:
        await status.delete()
    except Exception:
        pass


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

    job = jobs.start(context, "playlist")
    try:
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
        zip_entries = []
        user_quality = user_manager.get_audio_quality(user_id)

        for i, track in enumerate(tracks, 1):
            if jobs.cancelled(job):
                cancelled = True
                stop_reason = "لغو توسط کاربر"
                await reporter.fail(playlist_cancelled(sent, total))
                break

            allowed, used, limit, tier = entitlements.check_quota(
                user_manager.database, user_id,
            )
            if not allowed:
                rate_limited = True
                stop_reason = f"سقف روزانه ({used}/{limit})"
                await admin_logger.log_rate_limit(bot, user, 0)
                await reporter.fail(playlist_rate_limited(0, sent, total))
                await update.message.reply_text(
                    quota_exceeded(used, limit, tier),
                    reply_markup=payments.quota_upsell_keyboard(),
                )
                break

            await reporter.update(i, f"{track.title} — {unknown_artist(track.artist)}")
            await admin_logger.log_playlist_track(
                bot, user, i, total, track.title, track.artist, "در حال دانلود",
            )

            file_path, platform, cached, error_code = await orchestrator.get_or_download(
                track, reporter, bot=bot, user=user,
                cancel_check=lambda: jobs.cancelled(job),
            )
            is_file_id = bool(platform and str(platform).endswith("_cache_id"))
            if not file_path or (not is_file_id and not os.path.exists(file_path)):
                failed += 1
                await admin_logger.log_playlist_track(
                    bot, user, i, total, track.title, track.artist,
                    f"ناموفق ({error_code or 'unknown'})",
                )
                continue

            zip_path = None
            if is_file_id:
                src = "spotify" if track.url and "spotify.com" in track.url else (
                    "apple" if track.url and "music.apple.com" in track.url else "youtube"
                )
                if platform and platform.endswith("_cache_id"):
                    src = platform.replace("_cache_id", "").rsplit(":", 1)[0]
                zip_path = orchestrator.cache.get(
                    track.title, track.artist, f"{src}:{user_quality}",
                ) or orchestrator.cache.get(track.title, track.artist, src)
            elif os.path.exists(file_path):
                zip_path = file_path
            if zip_path:
                zip_entries.append((
                    zip_path,
                    _safe_zip_name(track.title, track.artist),
                ))

            if jobs.cancelled(job):
                cancelled = True
                stop_reason = "لغو توسط کاربر"
                await reporter.fail(playlist_cancelled(sent, total))
                await orchestrator.cleanup(file_path)
                break

            try:
                favorited = user_manager.is_favorite(
                    user_id, content_key(track.title, track.artist, ""),
                )
                kb = recommendation_keyboard(track.artist, track.title, favorited=favorited)
                send_kwargs = dict(
                    title=track.title,
                    performer=track.artist,
                    reply_markup=kb,
                    connect_timeout=TG_CONNECT_TIMEOUT,
                    read_timeout=TG_READ_TIMEOUT,
                    write_timeout=TG_WRITE_TIMEOUT,
                    pool_timeout=TG_POOL_TIMEOUT,
                )
                if is_file_id:
                    sent_msg = await update.message.reply_audio(
                        audio=file_path, **send_kwargs,
                    )
                else:
                    with open(file_path, 'rb') as audio:
                        sent_msg = await update.message.reply_audio(
                            audio=audio, **send_kwargs,
                        )
                if sent_msg and sent_msg.audio:
                    source = "spotify" if track.url and "spotify.com" in track.url else (
                        "apple" if track.url and "music.apple.com" in track.url else "youtube"
                    )
                    if platform and platform.endswith("_cache"):
                        source = platform.replace("_cache", "")
                    if platform and platform.endswith("_cache_id"):
                        source = platform.replace("_cache_id", "")
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

        if cancelled or rate_limited:
            await admin_logger.log_playlist_done(
                bot, user, collection_name, sent, total, failed, reason=stop_reason,
            )
        elif not rate_limited and not cancelled:
            await reporter.done(playlist_summary(sent, total, failed))
            await admin_logger.log_playlist_done(
                bot, user, collection_name, sent, total, failed,
            )
            if sent >= 2:
                await _send_playlist_zip(
                    update.message, collection_name, zip_entries, bot,
                )
    finally:
        jobs.end(context, job)
