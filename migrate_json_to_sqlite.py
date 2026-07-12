#!/usr/bin/env python3
"""One-time migration from users.json to SQLite."""

import json
import os
import sys
import time

from database import Database

JSON_PATH = "users.json"


def migrate():
    db = Database()
    if not os.path.exists(JSON_PATH):
        print(f"No {JSON_PATH} found — nothing to migrate.")
        return

    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)

    migrated = 0
    for user_id, info in data.items():
        db.touch_user(user_id)
        total = info.get("total_count", 0)
        downloads = info.get("downloads", [])
        with db._conn() as conn:
            conn.execute(
                "UPDATE users SET total_downloads=? WHERE user_id=?",
                (total, str(user_id)),
            )
            for ts in downloads:
                conn.execute(
                    "INSERT INTO rate_limit_events (user_id, created_at) VALUES (?, ?)",
                    (str(user_id), ts),
                )
        migrated += 1

    backup = f"{JSON_PATH}.bak.{int(time.time())}"
    os.rename(JSON_PATH, backup)
    print(f"Migrated {migrated} users. Backed up JSON to {backup}")


if __name__ == "__main__":
    migrate()
