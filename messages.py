"""User-facing Persian copy for the HiiT Radio bot."""

import os

DEVELOPER_NAME = os.getenv("DEVELOPER_NAME", "بابک").strip() or "بابک"
DEVELOPER_USERNAME = os.getenv("DEVELOPER_USERNAME", "").strip()
DEVELOPER_CHANNEL = (
    os.getenv("DEVELOPER_CHANNEL", "").strip()
    or os.getenv("REQUIRED_CHANNEL", "@HiiTRadio").strip()
    or "@HiiTRadio"
)
if not DEVELOPER_CHANNEL.startswith("@"):
    DEVELOPER_CHANNEL = f"@{DEVELOPER_CHANNEL.lstrip('@')}"

UNKNOWN = "نامشخص"
BOT_INLINE = "@HiiTRadioBot"


def platform_fa(platform):
    if not platform:
        return UNKNOWN
    p = platform.lower()
    if "spotify" in p:
        return "اسپاتیفای"
    if "apple" in p:
        return "اپل موزیک"
    if "youtube" in p:
        return "یوتیوب"
    if "soundcloud" in p:
        return "ساندکلاود"
    if "cache" in p:
        return "کش"
    return platform


def unknown_artist(artist):
    return artist or UNKNOWN


def btn_redownload(title):
    label = (title or UNKNOWN)[:26]
    return f"🔄 دانلود مجدد: {label}"


def btn_download(title, index=None):
    label = (title or UNKNOWN)[:24]
    if index is not None:
        return f"{index}. دانلود «{label}»"
    return f"دانلود «{label}»"


def start_text():
    return (
        "سلام! خوش اومدی به HiiT Radio 🎵\n\n"
        "من اینجام تا موزیک موردعلاقه‌ات رو دانلود کنم — "
        "لینک اسپاتیفای، اپل موزیک، آلبوم، پلی‌لیست، یا فقط اسم آهنگ رو بفرست.\n\n"
        "دستورها:\n"
        "/help — راهنمای استفاده\n"
        "/history — دانلودهای اخیر\n"
        "/liked — علاقه‌مندی‌ها\n"
        "/top — محبوب‌ترین آهنگ‌ها\n"
        "/discover — پیشنهاد شخصی\n"
        "/aboutme — درباره ربات و سازنده\n"
        "/cancel — توقف کار جاری"
    )


def help_text():
    return (
        "چطور استفاده کنم؟\n\n"
        "۱. لینک آهنگ، آلبوم یا پلی‌لیست بفرست\n"
        "۲. یا اسم آهنگ و هنرمند رو بنویس\n"
        "۳. یا اینلاین: "
        f"{BOT_INLINE} نام آهنگ — توی هر چتی\n\n"
        "/liked — آهنگ‌های ذخیره‌شده\n"
        "/top — جدول محبوب‌ها (day / week / all)\n"
        "/discover — بر اساس تاریخچه‌ات، ۱۰ آهنگ پیشنهاد می‌دم\n"
        "/cancel — توقف هر کار جاری (دانلود، پیشنهاد، …)\n"
        "/aboutme — درباره ربات و سازنده\n\n"
        "محدودیت: ۱۰ دانلود در ساعت "
        "(هر آهنگ توی پلی‌لیست جدا حساب می‌شه)."
    )


def aboutme_text():
    channel = DEVELOPER_CHANNEL
    lines = [
        "🎙 درباره HiiT Radio",
        "",
        f"این ربات رو من، {DEVELOPER_NAME}، ساختم تا راحت‌تر موزیک دانلود کنی.",
        "",
        f"📻 کانال: {channel}",
    ]
    if DEVELOPER_USERNAME:
        username = (
            DEVELOPER_USERNAME
            if DEVELOPER_USERNAME.startswith("@")
            else f"@{DEVELOPER_USERNAME}"
        )
        lines.append(f"💬 توسعه‌دهنده: {username}")
    lines.extend([
        "",
        "چی کار می‌کنه؟",
        "• لینک اسپاتیفای / اپل موزیک / آلبوم و پلی‌لیست",
        "• جستجو با نام آهنگ",
        "• پیشنهاد شخصی با /discover",
        "",
        "اگه ایده یا باگی داشتی، پیام بده — خوشحال می‌شم بشنوم 😊",
    ])
    return "\n".join(lines)


def history_empty():
    return "هنوز چیزی دانلود نکردی — یه آهنگ بفرست تا اینجا ثبت بشه 🎧"


def history_header():
    return "📜 دانلودهای اخیرت:\n"


def discover_empty_history():
    return (
        "برای پیشنهاد شخصی، اول چند تا آهنگ دانلود کن — "
        "بعد /discover رو بزن 🎧"
    )


def discover_not_configured():
    return (
        "پیشنهاد هوشمند فعلاً فعال نیست.\n"
        "به زودی دوباره امتحان کن."
    )


def discover_preparing():
    return "⏳ دارم برات آهنگ پیشنهاد می‌دم..."


def discover_llm_phase():
    return "در حال فکر کردن روی سلیقه‌ات..."


def discover_resolve_phase(done, total):
    return f"در حال پیدا کردن آهنگ‌ها ({done}/{total})..."


def discover_llm_error():
    return "الان نتونستم پیشنهاد بدم — یه کم دیگه دوباره امتحان کن 🙏"


def discover_no_results():
    return "فعلاً پیشنهاد تازه‌ای ندارم — بعداً دوباره امتحان کن."


def discover_header():
    return "🎧 پیشنهاد برای تو:\n"


def cancel_ok(count=1):
    if count > 1:
        return f"⏹ درخواست توقف برای {count} کار ثبت شد — به زودی متوقف می‌شن."
    return "⏹ درخواست توقف ثبت شد — کار جاری به زودی متوقف می‌شه."


def cancel_no_job():
    return "الان کار فعالی از طرف تو در حال اجرا نیست."


def too_many_jobs(limit):
    return (
        f"همزمان بیشتر از {limit} کار نمی‌تونی اجرا کنی.\n"
        "صبر کن تموم بشه یا با /cancel متوقفش کن."
    )


def preview_caption(title="", artist=""):
    line = "🎧 پیش‌نمایش ۳۰ ثانیه‌ای — نسخه کامل داره آماده می‌شه…"
    title = (title or "").strip()
    artist = (artist or "").strip()
    if title and artist:
        return f"{line}\n{title} — {artist}"
    if title:
        return f"{line}\n{title}"
    return line


def download_cancelled():
    return "متوقف شد."


def work_cancelled():
    return "کار لغو شد."


def rate_limit(minutes):
    return f"فعلاً به سقف دانلود رسیدی — {minutes} دقیقه دیگه برگرد 🙏"


def searching():
    return "⏳ دارم آهنگت رو پیدا می‌کنم..."


def downloading():
    return "⏳ دارم دانلود می‌کنم..."


def metadata_not_found():
    return "نتیجه‌ای پیدا نشد — لینک یا نام آهنگ رو دوباره بفرست 🙏"


def collection_not_found():
    return "نتونستم این آلبوم یا پلی‌لیست رو بشناسم — لینک رو چک کن و دوباره بفرست."


def send_failed():
    return "ارسال آهنگ ممکن نشد — لطفاً دوباره تلاش کن 🙏"


def download_not_found():
    return "نسخه کامل پیدا نشد — شاید با اسم دیگه‌ای جستجو کنی بهتر بشه."


def download_fail_bot_check():
    return (
        "الان یوتیوب اجازه دانلود نداد — "
        "یه کم دیگه دوباره امتحان کن یا اسم دیگه‌ای بفرست."
    )


def download_fail_timeout():
    return "دانلود طول کشید و قطع شد — لطفاً دوباره تلاش کن 🙏"


def download_fail_invalid():
    return "فایل درست دانلود نشد — یه لینک یا اسم دیگه امتحان کن."


def download_fail_message(error_code):
    """Map internal failure codes to non-technical Persian copy."""
    mapping = {
        "no_match": download_not_found(),
        "bot_check": download_fail_bot_check(),
        "timeout": download_fail_timeout(),
        "invalid_file": download_fail_invalid(),
        "cancelled": download_cancelled(),
        "send_failed": send_failed(),
        "unknown": download_not_found(),
    }
    return mapping.get(error_code or "unknown", download_not_found())


def record_not_found():
    return "این مورد توی تاریخچه پیدا نشد."


def songs_not_found():
    return "آهنگی پیدا نشد — یه اسم دیگه امتحان کن."


def similar_preparing():
    return "⏳ دارم آهنگ‌های مشابه پیدا می‌کنم..."


def similar_llm_phase():
    return "در حال پیدا کردن آهنگ‌های مشابه..."


def similar_resolve_phase(done, total):
    return f"در حال آماده‌سازی لیست ({done}/{total})..."


def similar_header(title, artist):
    who = f" — {artist}" if artist else ""
    return f"🎧 مشابه «{title}{who}»:\n"


def similar_not_found():
    return "آهنگ مشابهی پیدا نشد — بعداً دوباره امتحان کن."


def liked_empty():
    return "هنوز چیزی به علاقه‌مندی‌ها اضافه نکردی ❤️"


def liked_header():
    return "❤️ علاقه‌مندی‌هات:\n"


def favorite_added(title):
    return f"به علاقه‌مندی‌ها اضافه شد: {title or UNKNOWN}"


def favorite_removed(title):
    return f"از علاقه‌مندی‌ها حذف شد: {title or UNKNOWN}"


def favorite_missing():
    return "این آهنگ برای علاقه‌مندی پیدا نشد."


def top_header(period_label):
    return f"🏆 محبوب‌ترین‌ها ({period_label}):\n"


def top_empty():
    return "فعلاً آماری برای این بازه نیست."


def top_period_label(period):
    return {"day": "۲۴ ساعت", "week": "هفته", "all": "همه زمان‌ها"}.get(
        period, "هفته"
    )


def lyrics_not_found():
    return "متن این آهنگ پیدا نشد."


def lyrics_header(title, artist):
    who = f" — {artist}" if artist else ""
    return f"📝 {title}{who}\n\n"


def pick_expired():
    return "این انتخاب منقضی شده — دوباره جستجو کن."


def pick_expired_short():
    return "این انتخاب منقضی شده — دوباره امتحان کن."


def more_by_artist(artist):
    return f"🎵 آهنگ‌های بیشتر از {artist}:\n"


def inline_description(artist):
    return f"{artist} — برای دانلود لمس کن"


def gate_denied(channel):
    channel = channel.lstrip("@")
    return (
        f"برای استفاده از ربات، اول عضو کانال @{channel} شو 🙏\n\n"
        f"https://t.me/{channel}\n\n"
        "بعد از عضویت، دوباره امتحان کن."
    )


def gate_alert():
    return "ابتدا عضو کانال شو."


def playlist_empty():
    return "هیچ آهنگی توی این مجموعه پیدا نشد."


def playlist_start(collection_name, total):
    name = collection_name or "پلی‌لیست"
    return (
        f"📋 شروع دانلود: {name}\n"
        f"تعداد: {total} آهنگ\n\n"
        "/cancel برای توقف کار جاری"
    )


def playlist_cancelled(sent, total):
    return f"متوقف شد. ارسال شده: {sent}/{total}"


def playlist_rate_limited(minutes, sent, total):
    return f"محدودیت نرخ ({minutes} دقیقه). ارسال شده: {sent}/{total}"


def playlist_summary(sent, total, failed=0):
    summary = f"ارسال شده: {sent}/{total}"
    if failed:
        summary += f" | ناموفق: {failed}"
    return summary


def progress_update(label, current, total, detail="", eta_sec=None, show_counter=True):
    total = max(int(total or 1), 1)
    current = max(int(current or 0), 0)
    current = min(current, total)
    pct = int((current / total) * 100)
    bar_len = 20
    filled = int((bar_len * current) / total)
    bar = "[" + ("#" * filled) + ("-" * (bar_len - filled)) + "]"
    detail_line = f"\n{detail}" if detail else ""
    eta_line = ""
    if eta_sec is not None:
        eta_sec = max(int(round(eta_sec)), 0)
        m = eta_sec // 60
        s = eta_sec % 60
        eta_line = f"\n⏳ حدودا {m}:{s:02d}"
    counter = f" — آهنگ {current} از {total}" if show_counter else ""
    return f"📥 {label} {bar} {pct}%{counter}{detail_line}{eta_line}"


def progress_done(label, summary=""):
    text = f"✅ {label} تمام شد."
    if summary:
        text += f"\n{summary}"
    return text


def progress_fail(label, reason=""):
    text = f"❌ {label} ناموفق بود."
    if reason:
        text += f"\n{reason}"
    return text


def cookies_status(ok, detail, path, updated=None):
    """Admin-facing cookie jar health report."""
    lines = [
        "🍪 وضعیت کوکی یوتیوب",
        f"وضعیت: {'سالم' if ok else 'ناسالم'}",
        f"جزئیات: {detail}",
        f"مسیر: {path}",
    ]
    if updated:
        lines.append(f"آخرین به‌روزرسانی: {updated}")
    lines.append("")
    lines.append(
        "برای به‌روزرسانی، فایل cookies.txt رو (خروجی Netscape از مرورگری که "
        "توی youtube.com لاگین هستی) همین‌جا به‌صورت فایل بفرست."
    )
    return "\n".join(lines)


def cookies_accepted(detail, backed_up):
    text = f"✅ cookies.txt به‌روزرسانی شد.\nجزئیات: {detail}"
    if backed_up:
        text += "\nنسخه قبلی در cookies.txt.bak ذخیره شد."
    return text


def cookies_rejected(detail):
    return (
        "❌ این فایل کوکی معتبر نیست و ذخیره نشد.\n"
        f"جزئیات: {detail}\n\n"
        "دوباره در حالی که توی youtube.com لاگین هستی خروجی Netscape بگیر."
    )


def cookies_too_large(limit_kb):
    return f"❌ فایل خیلی بزرگه (بیشتر از {limit_kb} کیلوبایت)."


BTN_MORE_BY_ARTIST = "آهنگ‌های بیشتر"
BTN_SIMILAR = "آهنگ‌های مشابه"
BTN_LYRICS = "متن آهنگ"
BTN_FAVORITE_ADD = "❤️ علاقه‌مندی"
BTN_FAVORITE_REMOVE = "💔 حذف علاقه‌مندی"
