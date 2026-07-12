"""Report readiness of YouTube + Spotify full-download credentials."""

import os

from downloader import MusicDownloader, _cookies_look_authenticated
from spotify_downloader import SpotifyFullDownloader


def get_credentials_status():
    """Return a human-readable multi-line status for YouTube + Spotify full downloads."""
    dl = MusicDownloader()
    sp = SpotifyFullDownloader(download_dir=dl.download_dir)

    lines = ["وضعیت اعتبارنامه‌ها برای دانلود نسخه کامل:", ""]

    # --- YouTube ---
    lines.append("▶ یوتیوب (Apple Music / جستجو / بیشتر لینک‌ها)")
    if dl.cookies_from_browser:
        lines.append(f"  ✓ YTDLP_COOKIES_FROM_BROWSER={dl.cookies_from_browser}")
        yt_ok = True
    elif os.path.exists(dl.cookies_path) and _cookies_look_authenticated(dl.cookies_path):
        lines.append(f"  ✓ cookies.txt لاگین‌شده: {dl.cookies_path}")
        yt_ok = True
    elif os.path.exists(dl.cookies_path):
        lines.append(f"  ✗ cookies.txt هست ولی بدون LOGIN_INFO/SAPISID (مهمان)")
        lines.append("    → در مرورگر وارد youtube.com شو و کوکی را دوباره export کن")
        yt_ok = False
    else:
        lines.append(f"  ✗ cookies.txt پیدا نشد: {dl.cookies_path}")
        lines.append("    → یا فایل را بگذار، یا در .env: YTDLP_COOKIES_FROM_BROWSER=chrome")
        yt_ok = False

    # --- Spotify full (zotify) ---
    lines.append("")
    lines.append("▶ اسپاتیفای نسخه کامل (zotify / Premium)")
    if sp.is_configured():
        lines.append(f"  ✓ credentials.json: {sp.credentials_path}")
        if sp.username:
            lines.append(f"  ✓ SPOTIFY_USERNAME تنظیم شده")
        sp_ok = True
    else:
        lines.append(f"  ✗ credentials.json نیست: {sp.credentials_path}")
        lines.append("    → یک‌بار با اکانت Premium لاگین کن (دستور در SETUP_CREDENTIALS.md)")
        sp_ok = False

    # --- Spotify API (metadata only) ---
    lines.append("")
    lines.append("▶ اسپاتیفای API (فقط متادیتا — دانلود صدا نیست)")
    has_id = bool(os.getenv("SPOTIFY_CLIENT_ID"))
    has_secret = bool(os.getenv("SPOTIFY_CLIENT_SECRET"))
    if has_id and has_secret:
        lines.append("  ✓ SPOTIFY_CLIENT_ID / SECRET در .env هستند")
        lines.append("  (در صورت خطای ۴۰۳، از embed به‌عنوان جایگزین استفاده می‌شود)")
    else:
        lines.append("  ✗ CLIENT_ID/SECRET ناقص — برای لینک اسپاتیفای از embed استفاده می‌شود")

    lines.append("")
    if yt_ok and sp_ok:
        lines.append("نتیجه: هر دو مسیر آمادهٔ دانلود نسخه کامل هستند.")
    elif yt_ok:
        lines.append("نتیجه: فقط یوتیوب آماده است. اسپاتیفای کامل هنوز نه.")
    elif sp_ok:
        lines.append("نتیجه: فقط اسپاتیفای کامل آماده است. یوتیوب هنوز نه.")
    else:
        lines.append("نتیجه: هیچ‌کدام برای نسخه کامل آماده نیست.")

    return "\n".join(lines), yt_ok, sp_ok
