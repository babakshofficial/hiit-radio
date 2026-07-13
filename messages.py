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
        "/discover — پیشنهاد شخصی\n"
        "/aboutme — درباره ربات و سازنده\n"
        "/cancel — توقف دانلود پلی‌لیست"
    )


def help_text():
    return (
        "چطور استفاده کنم؟\n\n"
        "۱. لینک آهنگ، آلبوم یا پلی‌لیست بفرست\n"
        "۲. یا اسم آهنگ و هنرمند رو بنویس\n"
        "۳. یا اینلاین: "
        f"{BOT_INLINE} نام آهنگ — توی هر چتی\n\n"
        "/discover — بر اساس تاریخچه‌ات، ۱۰ آهنگ پیشنهاد می‌دم\n"
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


def discover_llm_error():
    return "الان نتونستم پیشنهاد بدم — یه کم دیگه دوباره امتحان کن 🙏"


def discover_no_results():
    return "فعلاً پیشنهاد تازه‌ای ندارم — بعداً دوباره امتحان کن."


def discover_header():
    return "🎧 پیشنهاد برای تو:\n"


def cancel_ok():
    return "⏹ درخواست توقف ثبت شد — به زودی متوقف می‌شه."


def cancel_no_job():
    return "الان کار فعالی در حال اجرا نیست."


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


def record_not_found():
    return "این مورد توی تاریخچه پیدا نشد."


def songs_not_found():
    return "آهنگی پیدا نشد — یه اسم دیگه امتحان کن."


def similar_not_found():
    return "آهنگ مشابهی پیدا نشد — هنرمند دیگه‌ای رو امتحان کن."


def pick_expired():
    return "این انتخاب منقضی شده — دوباره جستجو کن."


def pick_expired_short():
    return "این انتخاب منقضی شده — دوباره امتحان کن."


def more_by_artist(artist):
    return f"🎵 آهنگ‌های بیشتر از {artist}:\n"


def similar_to_artist(artist):
    return f"🎵 مشابه {artist}:\n"


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
        "/cancel برای توقف"
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


def progress_update(label, current, total, detail=""):
    detail_line = f"\n{detail}" if detail else ""
    return f"📥 {label} — آهنگ {current} از {total}{detail_line}"


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


BTN_MORE_BY_ARTIST = "آهنگ‌های بیشتر"
BTN_SIMILAR_ARTISTS = "هنرمندان مشابه"
