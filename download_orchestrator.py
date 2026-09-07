"""Unified download path with cache, lyrics, and analytics hooks."""

import hashlib
import logging
import os
import shutil

from cache_manager import CacheManager, content_key
from downloader import DEFAULT_QUALITY, QUALITIES
from lyrics_service import fetch_lyrics_fast

logger = logging.getLogger(__name__)


class DownloadOrchestrator:
    def __init__(self, music_downloader, db, download_dir="downloads"):
        self.music_downloader = music_downloader
        self.db = db
        self.download_dir = download_dir
        self.cache = CacheManager(db)
        os.makedirs(download_dir, exist_ok=True)

    def _source_label(self, metadata):
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

    def _cache_source(self, metadata, quality):
        return f"{self._source_label(metadata)}:{quality}"

    def _file_hash(self, path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()[:16]

    async def get_or_download(
        self,
        metadata,
        progress_reporter=None,
        bot=None,
        user=None,
        cancel_check=None,
        quality=None,
    ):
        """Return ``(file_path, platform, cached, error_code)``.

        On success ``error_code`` is ``None``. ``file_path`` may be a Telegram
        ``file_id`` when ``platform`` ends with ``_cache_id``.
        """
        source = self._source_label(metadata)
        if quality is None and user is not None:
            quality = self.db.get_audio_quality(user.id)
        if quality not in QUALITIES:
            quality = DEFAULT_QUALITY
        cache_source = self._cache_source(metadata, quality)
        self.db.log_event("download_start", payload={
            "title": metadata.title, "artist": metadata.artist, "source": source,
        })
        if bot:
            import admin_logger
            await admin_logger.log_download_start(
                bot, user, metadata.title, metadata.artist, source,
            )

        def _cancelled():
            try:
                return bool(cancel_check and cancel_check())
            except Exception:
                return False

        if _cancelled():
            return None, None, False, "cancelled"

        cached_path = self.cache.get(metadata.title, metadata.artist, cache_source)
        if cached_path:
            # Fast path: if Telegram already has this audio, skip re-upload entirely.
            file_id = self.cache.get_telegram_file_id(
                metadata.title, metadata.artist, cache_source,
            )
            if file_id and self.music_downloader.file_has_watermark(cached_path):
                self.music_downloader.sync_metadata_from_file(cached_path, metadata)
                if (
                    progress_reporter
                    and getattr(progress_reporter, "progress_mode", "tracks")
                    == "percent"
                ):
                    await progress_reporter.update(
                        98,
                        f"{metadata.title} — {metadata.artist}\nارسال سریع از کش...",
                        force=True,
                    )
                self.db.log_event("cache_hit", payload={
                    "title": metadata.title, "artist": metadata.artist,
                    "telegram_file_id": True,
                })
                if bot:
                    import admin_logger
                    await admin_logger.log_cache_hit(
                        bot, user, metadata.title, metadata.artist, source,
                    )
                return file_id, f"{cache_source}_cache_id", True, None

            send_copy = os.path.join(self.download_dir, f"{metadata.id}_send.mp3")
            if self.cache.copy_for_send(metadata.title, metadata.artist, cache_source, send_copy):
                self.music_downloader.sync_metadata_from_file(send_copy, metadata)
                try:
                    self.music_downloader.ensure_watermarked_cover(send_copy, metadata)
                except Exception:
                    pass
                if (
                    progress_reporter
                    and getattr(progress_reporter, "progress_mode", "tracks")
                    == "percent"
                ):
                    await progress_reporter.update(
                        95,
                        f"{metadata.title} — {metadata.artist}\nآماده ارسال به تلگرام...",
                        force=True,
                    )
                self.db.log_event("cache_hit", payload={
                    "title": metadata.title, "artist": metadata.artist,
                })
                if bot:
                    import admin_logger
                    await admin_logger.log_cache_hit(
                        bot, user, metadata.title, metadata.artist, source,
                    )
                return send_copy, f"{cache_source}_cache", True, None

        if _cancelled():
            return None, None, False, "cancelled"

        if (
            progress_reporter
            and getattr(progress_reporter, "progress_mode", "tracks") == "percent"
        ):
            await progress_reporter.update(
                15,
                f"{metadata.title} — {metadata.artist}\nدر حال جستجو و دانلود...",
                force=True,
            )
        file_path, error_code, failure_trail = await self.music_downloader.download_song(
            metadata,
            progress_reporter=progress_reporter,
            cancel_check=cancel_check,
            quality=quality,
            user_id=getattr(user, "id", None),
        )
        metadata.last_failure_trail = failure_trail or []
        platform = source if file_path else source

        if not file_path or not os.path.exists(file_path):
            code = error_code or "unknown"
            self.db.log_event("download_fail", payload={
                "title": metadata.title,
                "artist": metadata.artist,
                "source": source,
                "error_code": code,
                "failure_trail": failure_trail,
            })
            if bot:
                import admin_logger
                from cred_status import get_credentials_status
                from downloader import invalidate_youtube_auth_probe
                _, yt_ok = get_credentials_status()
                fail_reason = code
                if code == "bot_check" or not yt_ok:
                    invalidate_youtube_auth_probe()
                    _, yt_ok = get_credentials_status()
                    fail_reason = f"{code}; youtube cookies unavailable" if not yt_ok else code
                    await admin_logger.maybe_alert_cookie_issue(
                        bot,
                        detail=f"download bot_check for {metadata.title!r}",
                    )
                await admin_logger.log_download_fail(
                    bot, user, metadata.title, metadata.artist, source,
                    reason=fail_reason,
                )
            return None, None, False, code

        if _cancelled():
            return None, None, False, "cancelled"

        if (
            progress_reporter
            and getattr(progress_reporter, "progress_mode", "tracks") == "percent"
        ):
            await progress_reporter.update(
                88,
                f"{metadata.title} — {metadata.artist}\nدر حال آماده‌سازی...",
                force=True,
            )

        # Hot path: LRCLIB only with 3s timeout (skip Genius/Musixmatch).
        await self._embed_lyrics(file_path, metadata)

        if (
            progress_reporter
            and getattr(progress_reporter, "progress_mode", "tracks") == "percent"
        ):
            await progress_reporter.update(
                93,
                f"{metadata.title} — {metadata.artist}\nآماده ارسال به تلگرام...",
                force=True,
            )

        # Store under enriched tags AND under the original query guess so the
        # next identical search hits this watermarked file.
        self.cache.put(metadata.title, metadata.artist, cache_source, file_path)
        search_q = getattr(metadata, "search_query", None)
        if search_q:
            from metadata import guess_title_artist
            guess_title, guess_artist = guess_title_artist(search_q)
            if guess_title and (
                guess_title != metadata.title or guess_artist != metadata.artist
            ):
                self.cache.put(guess_title, guess_artist or "", cache_source, file_path)

        self.db.log_event("download_success", payload={
            "title": metadata.title, "artist": metadata.artist, "platform": platform,
        })
        return file_path, platform, False, None

    async def _embed_lyrics(self, file_path, metadata):
        try:
            from mutagen.mp3 import MP3
            duration = getattr(metadata, "duration", None)
            try:
                duration = duration or MP3(file_path).info.length
            except Exception:
                pass
            lyrics = await fetch_lyrics_fast(
                metadata.title, metadata.artist, duration, timeout=3,
            )
            self.music_downloader.embed_lyrics(file_path, lyrics)
        except Exception as e:
            logger.debug(f"Lyrics embed skipped: {e}")

    def sweep_cache(self):
        return self.cache.sweep_expired()

    async def cleanup(self, file_path, keep_cache=True):
        """Remove send copy; original may remain in cache."""
        try:
            if not file_path or not isinstance(file_path, str):
                return
            # Telegram file_id is not a filesystem path.
            if not os.path.exists(file_path):
                return
            if file_path.endswith("_send.mp3") or "/downloads/" in file_path.replace("\\", "/"):
                os.remove(file_path)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
