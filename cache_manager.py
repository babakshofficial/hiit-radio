"""24-hour file cache for downloaded tracks."""

import hashlib
import logging
import os
import shutil
import time

logger = logging.getLogger(__name__)

CACHE_DIR = os.getenv("CACHE_DIR", "cache")
CACHE_TTL_HOURS = int(os.getenv("CACHE_TTL_HOURS", "24"))


def _normalize(text):
    return (text or "").strip().lower()


def content_key(title, artist, source=""):
    raw = f"{_normalize(title)}|{_normalize(artist)}|{_normalize(source)}"
    return hashlib.sha256(raw.encode()).hexdigest()


class CacheManager:
    def __init__(self, db, cache_dir=None):
        self.db = db
        self.cache_dir = cache_dir or CACHE_DIR
        os.makedirs(self.cache_dir, exist_ok=True)

    def _cache_path(self, key):
        sub = key[:2]
        folder = os.path.join(self.cache_dir, sub)
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, f"{key}.mp3")

    def get(self, title, artist, source=""):
        key = content_key(title, artist, source)
        entry = self.db.get_cache_entry(key)
        if not entry:
            return None
        path = entry["path"]
        if os.path.exists(path):
            logger.info(f"Cache hit: {title} — {artist}")
            return path
        return None

    def put(self, title, artist, source, src_path, telegram_file_id=None):
        if not src_path or not os.path.exists(src_path):
            return None
        key = content_key(title, artist, source)
        dest = self._cache_path(key)
        try:
            shutil.copy2(src_path, dest)
            size = os.path.getsize(dest)
            expires = time.time() + CACHE_TTL_HOURS * 3600
            self.db.upsert_cache_entry(
                key, dest, size, expires, title, artist, telegram_file_id=telegram_file_id,
            )
            logger.info(f"Cached: {title} — {artist} ({size/1024/1024:.1f}MB)")
            return dest
        except Exception as e:
            logger.error(f"Cache store failed: {e}")
            return None

    def save_telegram_file_id(self, title, artist, source, file_id):
        key = content_key(title, artist, source)
        self.db.set_cache_file_id(key, file_id)

    def get_telegram_file_id(self, title, artist, source):
        key = content_key(title, artist, source)
        return self.db.get_cache_file_id(key)

    def copy_for_send(self, title, artist, source, dest_path):
        cached = self.get(title, artist, source)
        if not cached:
            return False
        try:
            shutil.copy2(cached, dest_path)
            return True
        except Exception as e:
            logger.error(f"Cache copy failed: {e}")
            return False

    def sweep_expired(self):
        expired = self.db.delete_expired_cache_entries()
        removed = 0
        for entry in expired:
            path = entry.get("path")
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                    removed += 1
                except OSError:
                    pass
        if removed:
            logger.info(f"Cache sweep: removed {removed} expired files")
        return removed
