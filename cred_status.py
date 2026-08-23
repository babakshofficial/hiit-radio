"""Report readiness of YouTube download credentials and Spotify metadata API."""

import os

from downloader import MusicDownloader, _cookies_look_authenticated


def get_credentials_status():
    """Return (human-readable status text, yt_ok)."""
    dl = MusicDownloader()

    lines = ["وضعیت اعتبارنامه‌ها:", ""]

    # --- YouTube (all audio downloads) ---
    lines.append("▶ یوتیوب (دانلود صدا — همه لینک‌ها)")
    if dl.cookies_from_browser:
        lines.append(f"  ✓ مرورگر: YTDLP_COOKIES_FROM_BROWSER={dl.cookies_from_browser}")
        live_ok, live_detail = dl.probe_youtube_auth()
        if live_ok:
            lines.append(f"  ✓ تست زنده: {live_detail}")
            yt_ok = True
        else:
            lines.append(f"  ✗ تست زنده: {live_detail}")
            lines.append("    → در Chrome وارد youtube.com شو؛ secretstorage نصب باشد")
            yt_ok = False
    else:
        has_auth_cookies = (
            os.path.exists(dl.cookies_path) and _cookies_look_authenticated(dl.cookies_path)
        )
        if has_auth_cookies:
            live_ok, live_detail = dl.probe_youtube_auth()
            lines.append(f"  ✓ cookies.txt: {dl.cookies_path}")
            if live_ok:
                lines.append(f"  ✓ تست زنده: {live_detail}")
                yt_ok = True
            else:
                lines.append(f"  ✗ تست زنده: {live_detail}")
                lines.append("    → کوکی منقضی شده — از PC export کن یا /cookies بفرست")
                yt_ok = False
        elif os.path.exists(dl.cookies_path):
            lines.append(f"  ✗ cookies.txt هست ولی نشست یوتیوب کامل نیست")
            lines.append("    → در مرورگر وارد youtube.com شو و کوکی را دوباره export کن")
            lines.append("    → یا YTDLP_COOKIES_FROM_BROWSER=chrome و YTDLP_AUTO_REFRESH_COOKIES=1")
            yt_ok = False
        else:
            lines.append(f"  ✗ cookies.txt پیدا نشد: {dl.cookies_path}")
            lines.append("    → فایل را از PC کپی کن یا در مرورگر export کن")
            yt_ok = False

    # --- Spotify API (metadata only) ---
    lines.append("")
    lines.append("▶ اسپاتیفای API (فقط متادیتا — دانلود از یوتیوب)")
    has_id = bool(os.getenv("SPOTIFY_CLIENT_ID"))
    has_secret = bool(os.getenv("SPOTIFY_CLIENT_SECRET"))
    if has_id and has_secret:
        lines.append("  ✓ SPOTIFY_CLIENT_ID / SECRET در .env هستند")
        lines.append("  (در صورت خطای ۴۰۳، از embed برای ترک/آلبوم/پلی‌لیست استفاده می‌شود)")
    else:
        lines.append("  ✗ CLIENT_ID/SECRET ناقص — برای لینک اسپاتیفای از embed استفاده می‌شود")

    lines.append("")
    if yt_ok:
        lines.append("نتیجه: یوتیوب آمادهٔ دانلود است.")
    else:
        lines.append("نتیجه: یوتیوب هنوز آماده نیست — cookies.txt را تنظیم کن.")

    return "\n".join(lines), yt_ok
