# Database layer

`database.py` holds the SQLite schema and the `Database` class (~130 methods). Domain areas: users, cache, downloads, support, payments, community submissions, changelog entries, analytics.

**Future refactor (audit S18):** split into `database/users.py`, `cache.py`, `support.py`, etc., with a thin `Database` facade re-exporting methods. No migration required — only module boundaries.
