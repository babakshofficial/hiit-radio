"""API configuration from environment."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID = os.getenv("ADMIN_ID", "").strip()
JWT_SECRET = os.getenv("JWT_SECRET", "").strip()
if len(JWT_SECRET) < 32 or JWT_SECRET == BOT_TOKEN:
    raise RuntimeError(
        "JWT_SECRET must be set to a dedicated value of at least 32 characters "
        "(generate one with: openssl rand -hex 32)"
    )
JWT_TTL_SEC = int(os.getenv("JWT_TTL_SEC", "604800"))  # 7 days
FILE_URL_TTL_SEC = int(os.getenv("FILE_URL_TTL_SEC", "3600"))
API_PUBLIC_URL = os.getenv("API_PUBLIC_URL", "").strip().rstrip("/")
WEBAPP_URL = os.getenv("WEBAPP_URL", "http://127.0.0.1:3000").rstrip("/")
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", f"{WEBAPP_URL},http://localhost:3000,http://127.0.0.1:3000").split(",")
    if o.strip() and o.strip() != "*"
]
API_DOCS_ENABLED = os.getenv("API_DOCS", "").strip().lower() in ("1", "true", "yes", "on")
BOT_USERNAME = (
    os.getenv("BOT_USERNAME", "").strip().lstrip("@")
    or os.getenv("BOT_INLINE", "HiiTRadioBot").strip().lstrip("@")
    or "HiiTRadioBot"
)
MAX_ACTIVE_JOBS = int(os.getenv("MAX_ACTIVE_JOBS", "3"))
MAX_PLAYLIST_TRACKS = max(1, int(os.getenv("MAX_PLAYLIST_TRACKS", "5")))
DATABASE_PATH = os.getenv("DATABASE_PATH", str(ROOT / "hiit_radio.db"))
CACHE_DIR = os.getenv("CACHE_DIR", str(ROOT / "cache"))
