"""User management facade over SQLite."""

import json
import os
import time

from database import Database


class UserManager:
    def __init__(self, db_path=None):
        self.db = Database(db_path)
        self._maybe_migrate_json()

    def _maybe_migrate_json(self):
        json_path = "users.json"
        if not os.path.exists(json_path):
            return
        users, _ = self.get_stats()
        if users > 0:
            return
        try:
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
            for user_id, info in data.items():
                self.db.touch_user(user_id)
                with self.db._conn() as conn:
                    conn.execute(
                        "UPDATE users SET total_downloads=? WHERE user_id=?",
                        (info.get("total_count", 0), str(user_id)),
                    )
                    for ts in info.get("downloads", []):
                        conn.execute(
                            "INSERT INTO rate_limit_events (user_id, created_at) VALUES (?, ?)",
                            (str(user_id), ts),
                        )
            backup = f"{json_path}.bak.{int(time.time())}"
            os.rename(json_path, backup)
        except Exception:
            pass

    def touch_user(self, user_id, username=None, first_name=None):
        self.db.touch_user(user_id, username, first_name)

    def check_rate_limit(self, user_id, limit=10, period=3600):
        return self.db.check_rate_limit(user_id, limit, period)

    def record_download(self, user_id, title=None, artist=None, platform=None,
                        source_url=None, album=None, file_hash=None, cached=False):
        self.db.record_rate_event(user_id)
        if title:
            return self.db.log_download(
                user_id, title, artist, platform, source_url, album, file_hash, cached
            )
        return None

    def get_stats(self):
        return self.db.get_stats()

    def get_all_user_ids(self):
        return self.db.get_all_user_ids()

    def get_user_history(self, user_id, limit=10):
        return self.db.get_user_history(user_id, limit)

    def get_history_by_id(self, history_id):
        return self.db.get_history_by_id(history_id)

    @property
    def database(self):
        return self.db
