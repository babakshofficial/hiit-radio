"""Unified download path with cache, lyrics, and analytics hooks."""

import hashlib
import logging
import os
import shutil

from cache_manager import CacheManager, content_key
from lyrics_service import fetch_lyrics

logger = logging.getLogger(__name__)


class DownloadOrchestrator:
    def __init__(self, music_downloader, db, download_dir="downloads"):
        self.music_downloader = music_downloader
        self.db = db
        self.download_dir = download_dir
        self.cache = CacheManager(db)
        os.makedirs(download_dir, exist_ok=True)

    def _source_label(self, metadata):
        if metadata.url and "spotify.com" in metadata.url:
            return "spotify"
        if metadata.url and "music.apple.com" in metadata.url:
            return "apple"
        return "youtube"

    def _file_hash(self, path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()[:16]

    async def get_or_download(self, metadata, progress_reporter=None, bot=None, user=None):
        """Return (file_path, platform, cached) or (None, None, False)."""
        source = self._source_label(metadata)
        self.db.log_event("download_start", payload={
            "title": metadata.title, "artist": metadata.artist, "source": source,
        })
        if bot:
            import admin_logger
            await admin_logger.log_download_start(
                bot, user, metadata.title, metadata.artist, source,
            )

        cached_path = self.cache.get(metadata.title, metadata.artist, source)
        if cached_path:
            send_copy = os.path.join(self.download_dir, f"{metadata.id}_send.mp3")
            if self.cache.copy_for_send(metadata.title, metadata.artist, source, send_copy):
                self.db.log_event("cache_hit", payload={
                    "title": metadata.title, "artist": metadata.artist,
                })
                if bot:
                    import admin_logger
                    await admin_logger.log_cache_hit(
                        bot, user, metadata.title, metadata.artist, source,
                    )
                return send_copy, f"{source}_cache", True

        if progress_reporter:
            await progress_reporter.update(
                1, f"{metadata.title} — {metadata.artist}\nدر حال جستجو و دانلود...",
            )
        file_path = await self.music_downloader.download_song(metadata)
        platform = "youtube" if file_path else source

        if not file_path or not os.path.exists(file_path):
            self.db.log_event("download_fail", payload={
                "title": metadata.title, "artist": metadata.artist, "source": source,
            })
            if bot:
                import admin_logger
                from cred_status import get_credentials_status
                _, yt_ok = get_credentials_status()
                fail_reason = "youtube cookies unavailable" if not yt_ok else None
                await admin_logger.log_download_fail(
                    bot, user, metadata.title, metadata.artist, source,
                    reason=fail_reason,
                )
            return None, None, False

        # Embed lyrics (non-blocking failure)
        await self._embed_lyrics(file_path, metadata)

        # Store in cache before send
        self.cache.put(metadata.title, metadata.artist, source, file_path)

        self.db.log_event("download_success", payload={
            "title": metadata.title, "artist": metadata.artist, "platform": platform,
        })
        return file_path, platform, False

    async def _embed_lyrics(self, file_path, metadata):
        try:
            from mutagen.mp3 import MP3
            duration = None
            try:
                duration = MP3(file_path).info.length
            except Exception:
                pass
            lyrics = await fetch_lyrics(metadata.title, metadata.artist, duration)
            self.music_downloader.embed_lyrics(file_path, lyrics)
        except Exception as e:
            logger.debug(f"Lyrics embed skipped: {e}")

    def sweep_cache(self):
        return self.cache.sweep_expired()

    async def cleanup(self, file_path, keep_cache=True):
        """Remove send copy; original may remain in cache."""
        try:
            if file_path and os.path.exists(file_path):
                if file_path.endswith("_send.mp3") or "/downloads/" in file_path.replace("\\", "/"):
                    os.remove(file_path)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
