import time
import json
import os

class UserManager:
    def __init__(self, db_path="users.json"):
        self.db_path = db_path
        self.users = self._load_users()

    def _load_users(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r') as f:
                return json.load(f)
        return {}

    def _save_users(self):
        with open(self.db_path, 'w') as f:
            json.dump(self.users, f, indent=4)

    def check_rate_limit(self, user_id, limit=10, period=3600):
        user_id = str(user_id)
        now = time.time()
        if user_id not in self.users:
            self.users[user_id] = {"downloads": [], "total_count": 0}
        self.users[user_id]["downloads"] = [t for t in self.users[user_id]["downloads"] if now - t < period]
        if len(self.users[user_id]["downloads"]) >= limit:
            return False, int(period - (now - self.users[user_id]["downloads"][0]))
        return True, 0

    def record_download(self, user_id):
        user_id = str(user_id)
        now = time.time()
        if user_id not in self.users:
            self.users[user_id] = {"downloads": [], "total_count": 0}
        self.users[user_id]["downloads"].append(now)
        self.users[user_id]["total_count"] += 1
        self._save_users()

    def get_stats(self):
        total_users = len(self.users)
        total_downloads = sum(u["total_count"] for u in self.users.values())
        return total_users, total_downloads