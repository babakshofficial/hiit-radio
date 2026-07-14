"""SQLite persistence for users, history, cache, and analytics."""

import json
import os
import sqlite3
import time
from contextlib import contextmanager

DEFAULT_DB_PATH = os.getenv("DATABASE_PATH", "hiit_radio.db")

_SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_seen REAL,
    first_seen REAL,
    total_downloads INTEGER DEFAULT 0,
    is_blocked INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS rate_limit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    created_at REAL NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_rate_limit_user_time
    ON rate_limit_events(user_id, created_at);

CREATE TABLE IF NOT EXISTS download_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    title TEXT,
    artist TEXT,
    album TEXT,
    platform TEXT,
    source_url TEXT,
    file_hash TEXT,
    cached INTEGER DEFAULT 0,
    created_at REAL NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_history_user_time
    ON download_history(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS cache_files (
    content_key TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    size_bytes INTEGER DEFAULT 0,
    expires_at REAL NOT NULL,
    hit_count INTEGER DEFAULT 0,
    title TEXT,
    artist TEXT,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache_files(expires_at);

CREATE TABLE IF NOT EXISTS analytics_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    user_id TEXT,
    payload_json TEXT,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_analytics_type_time
    ON analytics_events(event_type, created_at DESC);

CREATE TABLE IF NOT EXISTS user_artist_stats (
    user_id TEXT NOT NULL,
    artist TEXT NOT NULL,
    download_count INTEGER DEFAULT 0,
    PRIMARY KEY (user_id, artist)
);

CREATE TABLE IF NOT EXISTS broadcast_pending (
    token TEXT PRIMARY KEY,
    message TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS user_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    request_type TEXT NOT NULL,
    text TEXT,
    created_at REAL NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_user_requests_user_time
    ON user_requests(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_user_requests_time
    ON user_requests(created_at DESC);

CREATE TABLE IF NOT EXISTS llm_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    model TEXT,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    cached INTEGER DEFAULT 0,
    success INTEGER DEFAULT 1,
    recommendations_count INTEGER DEFAULT 0,
    created_at REAL NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_llm_usage_user_time
    ON llm_usage(user_id, created_at DESC);
"""

EXPORT_EVENT_LIMIT = 10000


class Database:
    def __init__(self, db_path=None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self._init_schema()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        with self._conn() as conn:
            conn.executescript(_SCHEMA)
            try:
                conn.execute(
                    "ALTER TABLE cache_files ADD COLUMN telegram_file_id TEXT"
                )
            except sqlite3.OperationalError:
                pass

    # --- Users ---

    def touch_user(self, user_id, username=None, first_name=None):
        user_id = str(user_id)
        now = time.time()
        with self._conn() as conn:
            row = conn.execute(
                "SELECT user_id FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            if row:
                conn.execute(
                    """UPDATE users SET username=COALESCE(?, username),
                       first_name=COALESCE(?, first_name), last_seen=? WHERE user_id=?""",
                    (username, first_name, now, user_id),
                )
            else:
                conn.execute(
                    """INSERT INTO users (user_id, username, first_name, first_seen, last_seen)
                       VALUES (?, ?, ?, ?, ?)""",
                    (user_id, username, first_name, now, now),
                )

    def get_all_user_ids(self):
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT user_id FROM users WHERE is_blocked = 0"
            ).fetchall()
            return [r["user_id"] for r in rows]

    def get_stats(self):
        with self._conn() as conn:
            users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
            downloads = conn.execute(
                "SELECT COALESCE(SUM(total_downloads), 0) AS c FROM users"
            ).fetchone()["c"]
            return users, downloads

    # --- Rate limiting ---

    def check_rate_limit(self, user_id, limit=10, period=3600):
        user_id = str(user_id)
        now = time.time()
        cutoff = now - period
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM rate_limit_events WHERE user_id=? AND created_at < ?",
                (user_id, cutoff),
            )
            count = conn.execute(
                "SELECT COUNT(*) AS c FROM rate_limit_events WHERE user_id=?",
                (user_id,),
            ).fetchone()["c"]
            if count >= limit:
                oldest = conn.execute(
                    "SELECT MIN(created_at) AS t FROM rate_limit_events WHERE user_id=?",
                    (user_id,),
                ).fetchone()["t"]
                wait = int(period - (now - oldest)) if oldest else period
                return False, max(wait, 0)
        return True, 0

    def record_rate_event(self, user_id):
        user_id = str(user_id)
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO rate_limit_events (user_id, created_at) VALUES (?, ?)",
                (user_id, time.time()),
            )
            conn.execute(
                "UPDATE users SET total_downloads = total_downloads + 1, last_seen = ? WHERE user_id = ?",
                (time.time(), user_id),
            )

    # --- Download history ---

    def log_download(self, user_id, title, artist, platform, source_url=None,
                     album=None, file_hash=None, cached=False):
        user_id = str(user_id)
        now = time.time()
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO download_history
                   (user_id, title, artist, album, platform, source_url, file_hash, cached, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (user_id, title, artist, album, platform, source_url, file_hash,
                 1 if cached else 0, now),
            )
            if artist:
                conn.execute(
                    """INSERT INTO user_artist_stats (user_id, artist, download_count)
                       VALUES (?, ?, 1)
                       ON CONFLICT(user_id, artist) DO UPDATE SET
                       download_count = download_count + 1""",
                    (user_id, artist),
                )
            return cur.lastrowid

    def get_user_history(self, user_id, limit=10):
        user_id = str(user_id)
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT id, title, artist, album, platform, created_at
                   FROM download_history WHERE user_id=? ORDER BY created_at DESC LIMIT ?""",
                (user_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_history_by_id(self, history_id):
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM download_history WHERE id=?", (history_id,)
            ).fetchone()
            return dict(row) if row else None

    # --- Cache index ---

    def get_cache_entry(self, content_key):
        now = time.time()
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM cache_files WHERE content_key=? AND expires_at > ?",
                (content_key, now),
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE cache_files SET hit_count = hit_count + 1 WHERE content_key=?",
                    (content_key,),
                )
                return dict(row)
        return None

    def upsert_cache_entry(self, content_key, path, size_bytes, expires_at, title=None, artist=None,
                           telegram_file_id=None):
        now = time.time()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO cache_files
                   (content_key, path, size_bytes, expires_at, hit_count, title, artist, created_at,
                    telegram_file_id)
                   VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?)
                   ON CONFLICT(content_key) DO UPDATE SET
                   path=excluded.path, size_bytes=excluded.size_bytes,
                   expires_at=excluded.expires_at, title=excluded.title, artist=excluded.artist,
                   telegram_file_id=COALESCE(excluded.telegram_file_id, cache_files.telegram_file_id)""",
                (content_key, path, size_bytes, expires_at, title, artist, now, telegram_file_id),
            )

    def set_cache_file_id(self, content_key, file_id):
        with self._conn() as conn:
            conn.execute(
                "UPDATE cache_files SET telegram_file_id=? WHERE content_key=?",
                (file_id, content_key),
            )

    def get_cache_file_id(self, content_key):
        entry = self.get_cache_entry(content_key)
        if entry:
            return entry.get("telegram_file_id")
        return None

    def delete_cache_entry(self, content_key):
        with self._conn() as conn:
            row = conn.execute(
                "SELECT path FROM cache_files WHERE content_key=?", (content_key,)
            ).fetchone()
            conn.execute("DELETE FROM cache_files WHERE content_key=?", (content_key,))
            return dict(row) if row else None

    def delete_all_cache_entries(self):
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT content_key, path FROM cache_files"
            ).fetchall()
            conn.execute("DELETE FROM cache_files")
            return [dict(r) for r in rows]

    def delete_expired_cache_entries(self):
        now = time.time()
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT content_key, path FROM cache_files WHERE expires_at <= ?", (now,)
            ).fetchall()
            conn.execute("DELETE FROM cache_files WHERE expires_at <= ?", (now,))
            return [dict(r) for r in rows]

    # --- Analytics ---

    def log_event(self, event_type, user_id=None, payload=None):
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO analytics_events (event_type, user_id, payload_json, created_at)
                   VALUES (?, ?, ?, ?)""",
                (event_type, str(user_id) if user_id else None,
                 json.dumps(payload or {}), time.time()),
            )

    def top_artists(self, limit=10):
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT artist, COUNT(*) AS cnt FROM download_history
                   WHERE artist IS NOT NULL AND artist != ''
                   GROUP BY artist ORDER BY cnt DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def top_songs(self, limit=10):
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT title, artist, COUNT(*) AS cnt FROM download_history
                   WHERE title IS NOT NULL
                   GROUP BY title, artist ORDER BY cnt DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def platform_breakdown(self):
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT platform, COUNT(*) AS cnt FROM download_history
                   WHERE platform IS NOT NULL GROUP BY platform ORDER BY cnt DESC"""
            ).fetchall()
            return [dict(r) for r in rows]

    def cache_hit_rate(self):
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) AS c FROM download_history").fetchone()["c"]
            cached = conn.execute(
                "SELECT COUNT(*) AS c FROM download_history WHERE cached=1"
            ).fetchone()["c"]
            return cached, total

    def user_top_artists(self, user_id, limit=3):
        user_id = str(user_id)
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT artist, download_count FROM user_artist_stats
                   WHERE user_id=? ORDER BY download_count DESC LIMIT ?""",
                (user_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def global_top_artists(self, limit=3):
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT artist, SUM(download_count) AS download_count
                   FROM user_artist_stats GROUP BY artist
                   ORDER BY download_count DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    # --- Broadcast confirmation ---

    def save_broadcast_pending(self, token, message):
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO broadcast_pending (token, message, created_at) VALUES (?, ?, ?)",
                (token, message, time.time()),
            )

    def pop_broadcast_pending(self, token):
        with self._conn() as conn:
            row = conn.execute(
                "SELECT message FROM broadcast_pending WHERE token=?", (token,)
            ).fetchone()
            conn.execute("DELETE FROM broadcast_pending WHERE token=?", (token,))
            return row["message"] if row else None

    # --- User requests ---

    def log_user_request(self, user_id, request_type, text=None):
        user_id = str(user_id)
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO user_requests (user_id, request_type, text, created_at)
                   VALUES (?, ?, ?, ?)""",
                (user_id, request_type, (text or "")[:500], time.time()),
            )

    # --- LLM usage ---

    def log_llm_usage(
        self,
        user_id,
        model=None,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        cached=False,
        success=True,
        recommendations_count=0,
    ):
        user_id = str(user_id)
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO llm_usage
                   (user_id, model, prompt_tokens, completion_tokens, total_tokens,
                    cached, success, recommendations_count, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    model,
                    prompt_tokens or 0,
                    completion_tokens or 0,
                    total_tokens or 0,
                    1 if cached else 0,
                    1 if success else 0,
                    recommendations_count or 0,
                    time.time(),
                ),
            )

    # --- Admin reporting ---

    def _paginate(self, count_sql, count_args, data_sql, data_args, page, per_page):
        page = max(page, 0)
        offset = page * per_page
        with self._conn() as conn:
            total = conn.execute(count_sql, count_args).fetchone()[0]
            rows = conn.execute(
                f"{data_sql} LIMIT ? OFFSET ?",
                (*data_args, per_page, offset),
            ).fetchall()
        total_pages = max((total + per_page - 1) // per_page, 1)
        return [dict(r) for r in rows], total, total_pages

    def list_users(self, page=0, per_page=10):
        return self._paginate(
            "SELECT COUNT(*) FROM users",
            (),
            """SELECT user_id, username, first_name, total_downloads,
                      first_seen, last_seen, is_blocked
               FROM users ORDER BY last_seen DESC""",
            (),
            page,
            per_page,
        )

    def get_user_row(self, user_id):
        user_id = str(user_id)
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE user_id=?", (user_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_user_summary(self, user_id):
        user_id = str(user_id)
        user = self.get_user_row(user_id)
        if not user:
            return None
        with self._conn() as conn:
            downloads = conn.execute(
                "SELECT COUNT(*) AS c FROM download_history WHERE user_id=?",
                (user_id,),
            ).fetchone()["c"]
            requests = conn.execute(
                "SELECT COUNT(*) AS c FROM user_requests WHERE user_id=?",
                (user_id,),
            ).fetchone()["c"]
            llm = conn.execute(
                """SELECT COUNT(*) AS calls,
                          COALESCE(SUM(total_tokens), 0) AS tokens,
                          COALESCE(SUM(cached), 0) AS cached_calls
                   FROM llm_usage WHERE user_id=?""",
                (user_id,),
            ).fetchone()
            rate_1h = conn.execute(
                """SELECT COUNT(*) AS c FROM rate_limit_events
                   WHERE user_id=? AND created_at > ?""",
                (user_id, time.time() - 3600),
            ).fetchone()["c"]
        return {
            **user,
            "history_count": downloads,
            "request_count": requests,
            "llm_calls": llm["calls"],
            "llm_tokens": llm["tokens"],
            "llm_cached_calls": llm["cached_calls"],
            "downloads_last_hour": rate_1h,
        }

    def list_user_downloads(self, user_id, page=0, per_page=10):
        user_id = str(user_id)
        return self._paginate(
            "SELECT COUNT(*) FROM download_history WHERE user_id=?",
            (user_id,),
            """SELECT id, title, artist, album, platform, cached, created_at
               FROM download_history WHERE user_id=? ORDER BY created_at DESC""",
            (user_id,),
            page,
            per_page,
        )

    def list_user_requests(self, user_id, page=0, per_page=10):
        user_id = str(user_id)
        return self._paginate(
            "SELECT COUNT(*) FROM user_requests WHERE user_id=?",
            (user_id,),
            """SELECT id, request_type, text, created_at
               FROM user_requests WHERE user_id=? ORDER BY created_at DESC""",
            (user_id,),
            page,
            per_page,
        )

    def list_user_analytics(self, user_id, page=0, per_page=10):
        user_id = str(user_id)
        return self._paginate(
            "SELECT COUNT(*) FROM analytics_events WHERE user_id=?",
            (user_id,),
            """SELECT id, event_type, payload_json, created_at
               FROM analytics_events WHERE user_id=? ORDER BY created_at DESC""",
            (user_id,),
            page,
            per_page,
        )

    def list_user_llm_usage(self, user_id, page=0, per_page=10):
        user_id = str(user_id)
        return self._paginate(
            "SELECT COUNT(*) FROM llm_usage WHERE user_id=?",
            (user_id,),
            """SELECT id, model, prompt_tokens, completion_tokens, total_tokens,
                      cached, success, recommendations_count, created_at
               FROM llm_usage WHERE user_id=? ORDER BY created_at DESC""",
            (user_id,),
            page,
            per_page,
        )

    def list_recent_downloads(self, page=0, per_page=10):
        return self._paginate(
            "SELECT COUNT(*) FROM download_history",
            (),
            """SELECT dh.id, dh.user_id, u.username, dh.title, dh.artist,
                      dh.platform, dh.cached, dh.created_at
               FROM download_history dh
               LEFT JOIN users u ON u.user_id = dh.user_id
               ORDER BY dh.created_at DESC""",
            (),
            page,
            per_page,
        )

    def list_recent_requests(self, page=0, per_page=10):
        return self._paginate(
            "SELECT COUNT(*) FROM user_requests",
            (),
            """SELECT ur.id, ur.user_id, u.username, ur.request_type,
                      ur.text, ur.created_at
               FROM user_requests ur
               LEFT JOIN users u ON u.user_id = ur.user_id
               ORDER BY ur.created_at DESC""",
            (),
            page,
            per_page,
        )

    def list_recent_analytics(self, page=0, per_page=10):
        return self._paginate(
            "SELECT COUNT(*) FROM analytics_events",
            (),
            """SELECT ae.id, ae.user_id, u.username, ae.event_type,
                      ae.payload_json, ae.created_at
               FROM analytics_events ae
               LEFT JOIN users u ON u.user_id = ae.user_id
               ORDER BY ae.created_at DESC""",
            (),
            page,
            per_page,
        )

    def list_recent_llm_usage(self, page=0, per_page=10):
        return self._paginate(
            "SELECT COUNT(*) FROM llm_usage",
            (),
            """SELECT lu.id, lu.user_id, u.username, lu.model,
                      lu.prompt_tokens, lu.completion_tokens, lu.total_tokens,
                      lu.cached, lu.success, lu.recommendations_count, lu.created_at
               FROM llm_usage lu
               LEFT JOIN users u ON u.user_id = lu.user_id
               ORDER BY lu.created_at DESC""",
            (),
            page,
            per_page,
        )

    def list_cache_entries(self, page=0, per_page=10):
        now = time.time()
        return self._paginate(
            "SELECT COUNT(*) FROM cache_files WHERE expires_at > ?",
            (now,),
            """SELECT content_key, title, artist, size_bytes, hit_count,
                      expires_at, created_at
               FROM cache_files WHERE expires_at > ?
               ORDER BY hit_count DESC, created_at DESC""",
            (now,),
            page,
            per_page,
        )

    def global_report_summary(self):
        with self._conn() as conn:
            users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
            downloads = conn.execute(
                "SELECT COUNT(*) AS c FROM download_history"
            ).fetchone()["c"]
            requests = conn.execute(
                "SELECT COUNT(*) AS c FROM user_requests"
            ).fetchone()["c"]
            cached_dl, total_dl = self.cache_hit_rate()
            cache_entries = conn.execute(
                "SELECT COUNT(*) AS c FROM cache_files WHERE expires_at > ?",
                (time.time(),),
            ).fetchone()["c"]
            cache_hits = conn.execute(
                "SELECT COALESCE(SUM(hit_count), 0) AS c FROM cache_files"
            ).fetchone()["c"]
            llm = conn.execute(
                """SELECT COUNT(*) AS calls,
                          COALESCE(SUM(total_tokens), 0) AS tokens,
                          COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                          COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                          COALESCE(SUM(cached), 0) AS cached_calls,
                          COALESCE(SUM(CASE WHEN success=0 THEN 1 ELSE 0 END), 0) AS failed_calls
                   FROM llm_usage"""
            ).fetchone()
            events = conn.execute(
                """SELECT event_type, COUNT(*) AS cnt FROM analytics_events
                   GROUP BY event_type ORDER BY cnt DESC"""
            ).fetchall()
        return {
            "users": users,
            "downloads": downloads,
            "requests": requests,
            "cached_downloads": cached_dl,
            "total_downloads": total_dl,
            "cache_entries": cache_entries,
            "cache_hits": cache_hits,
            "llm_calls": llm["calls"],
            "llm_tokens": llm["tokens"],
            "llm_prompt_tokens": llm["prompt_tokens"],
            "llm_completion_tokens": llm["completion_tokens"],
            "llm_cached_calls": llm["cached_calls"],
            "llm_failed_calls": llm["failed_calls"],
            "event_breakdown": [dict(r) for r in events],
            "top_artists": self.top_artists(5),
            "top_songs": self.top_songs(5),
            "platforms": self.platform_breakdown(),
        }

    def _rows_to_dicts(self, conn, table, where="", args=(), limit=None, order=""):
        sql = f"SELECT * FROM {table}"
        if where:
            sql += f" WHERE {where}"
        if order:
            sql += f" ORDER BY {order}"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [dict(r) for r in conn.execute(sql, args).fetchall()]

    def export_all(self):
        now = time.time()
        with self._conn() as conn:
            analytics_total = conn.execute(
                "SELECT COUNT(*) FROM analytics_events"
            ).fetchone()[0]
            rate_total = conn.execute(
                "SELECT COUNT(*) FROM rate_limit_events"
            ).fetchone()[0]
            return {
                "exported_at": now,
                "truncation": {
                    "analytics_events": (
                        analytics_total
                        if analytics_total <= EXPORT_EVENT_LIMIT
                        else f"last {EXPORT_EVENT_LIMIT} of {analytics_total}"
                    ),
                    "rate_limit_events": (
                        rate_total
                        if rate_total <= EXPORT_EVENT_LIMIT
                        else f"last {EXPORT_EVENT_LIMIT} of {rate_total}"
                    ),
                },
                "summary": self.global_report_summary(),
                "users": self._rows_to_dicts(conn, "users", order="last_seen DESC"),
                "download_history": self._rows_to_dicts(
                    conn, "download_history", order="created_at DESC"
                ),
                "user_requests": self._rows_to_dicts(
                    conn, "user_requests", order="created_at DESC"
                ),
                "llm_usage": self._rows_to_dicts(
                    conn, "llm_usage", order="created_at DESC"
                ),
                "analytics_events": self._rows_to_dicts(
                    conn,
                    "analytics_events",
                    order="created_at DESC",
                    limit=EXPORT_EVENT_LIMIT,
                ),
                "rate_limit_events": self._rows_to_dicts(
                    conn,
                    "rate_limit_events",
                    order="created_at DESC",
                    limit=EXPORT_EVENT_LIMIT,
                ),
                "user_artist_stats": self._rows_to_dicts(conn, "user_artist_stats"),
                "cache_files": self._rows_to_dicts(conn, "cache_files"),
                "broadcast_pending": self._rows_to_dicts(conn, "broadcast_pending"),
            }
