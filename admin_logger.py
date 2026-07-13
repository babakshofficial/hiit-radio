"""VIP admin channel logging — all bot activity."""

import html
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from telegram.error import BadRequest, Forbidden

load_dotenv(Path(__file__).resolve().parent / ".env")

logger = logging.getLogger(__name__)


def _vip_channel_id():
    return os.getenv("VIP_LOG_CHANNEL_ID", "").strip()


def _normalize_chat_id(raw):
    """Return int chat id or @username string for Telegram API calls."""
    if not raw:
        return None
    stripped = str(raw).strip()
    if stripped.startswith("@"):
        return stripped
    digits = stripped.lstrip("-")
    if not digits.isdigit():
        return stripped
    if stripped.startswith("-100"):
        return int(stripped)
    # Private channels/groups use -100xxxxxxxxxx; fix common copy mistakes.
    return int(f"-100{digits}")


def _parse_chat_id(raw):
    return _normalize_chat_id(raw)


def _enabled():
    return bool(_vip_channel_id())


def _ts():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _fmt_user(user):
    if not user:
        return "—"
    parts = [f"شناسه={user.id}"]
    if user.username:
        parts.append(f"@{user.username}")
    if user.first_name:
        parts.append(user.first_name)
    return " ".join(parts)


def _plain_from_html(text):
    return re.sub(r"<[^>]+>", "", text)


async def _check_post_permission(bot, chat_id, chat_type):
    me = await bot.get_me()
    member = await bot.get_chat_member(chat_id, me.id)
    status = getattr(member, "status", "")
    if chat_type == "channel":
        if status != "administrator":
            return False, "ربات ادمین کانال نیست"
        if hasattr(member, "can_post_messages") and not member.can_post_messages:
            return False, "ربات اجازه ارسال پیام در کانال را ندارد"
    elif status not in {"administrator", "member", "creator"}:
        return False, f"ربات عضو چت نیست (وضعیت: {status})"
    return True, None


async def validate_vip_log_channel(bot):
    channel = _vip_channel_id()
    if not channel:
        logger.warning("VIP logging disabled: VIP_LOG_CHANNEL_ID is not set in .env")
        return False
    chat_id = _parse_chat_id(channel)
    try:
        chat = await bot.get_chat(chat_id)
        ok, reason = await _check_post_permission(bot, chat.id, chat.type)
        if not ok:
            logger.error(f"VIP log channel permission error for {channel}: {reason}")
            return False
        logger.info(
            f"VIP log channel OK: {getattr(chat, 'title', channel)} "
            f"(type={chat.type}, id={chat.id})"
        )
        return True
    except (BadRequest, Forbidden) as e:
        logger.error(
            f"VIP log channel broken for {channel}: {e}. "
            "Add the bot as channel administrator with permission to post messages. "
            "Use /channelid to get the numeric chat id (must start with -100)."
        )
        return False
    except Exception as e:
        logger.error(f"VIP log channel validation error for {channel}: {e}")
        return False


async def send_test_message(bot):
    """Send a test log entry; returns (ok, detail)."""
    channel = _vip_channel_id()
    if not channel:
        return False, "VIP_LOG_CHANNEL_ID در .env تنظیم نشده"
    chat_id = _parse_chat_id(channel)
    try:
        chat = await bot.get_chat(chat_id)
        ok, reason = await _check_post_permission(bot, chat.id, chat.type)
        if not ok:
            return False, reason
        text = (
            f"<b>تست لاگ VIP</b> {_ts()}\n"
            f"کانال: {html.escape(getattr(chat, 'title', str(chat.id)))}\n"
            f"شناسه: {chat.id}"
        )
        sent = await _send(bot, text)
        if not sent:
            return False, "ارسال پیام ناموفق بود — لاگ سرور را بررسی کن"
        return True, f"پیام تست به {chat.title or chat.id} ارسال شد (id={chat.id})"
    except (BadRequest, Forbidden) as e:
        return False, (
            f"{e}. ربات را ادمین کانال کن با اجازه ارسال پیام. "
            "شناسه باید عددی باشد (مثلاً -1001234567890)."
        )
    except Exception as e:
        return False, str(e)


async def notify_admin_vip_issue(bot, message):
    admin_id = os.getenv("ADMIN_ID", "").strip()
    if not admin_id or not bot:
        return
    try:
        await bot.send_message(chat_id=int(admin_id), text=message)
    except Exception as e:
        logger.error(f"Could not notify admin about VIP logging: {e}")


def vip_status_text():
    channel = _vip_channel_id()
    if not channel:
        return (
            "لاگ VIP غیرفعال است.\n\n"
            "۱. ربات را ادمین کانال خصوصی کن (با اجازه ارسال پیام)\n"
            "۲. در کانال /channelid@HiiTRadioBot بزن یا یک پست را فوروارد کن\n"
            "۳. در .env بگذار:\nVIP_LOG_CHANNEL_ID=-100xxxxxxxxxx\n"
            "۴. ربات را ری‌استارت کن\n\n"
            "برای تست: /viplogtest"
        )
    parsed = _parse_chat_id(channel)
    return (
        f"VIP_LOG_CHANNEL_ID={channel}\n"
        f"شناسه پردازش‌شده: {parsed}\n\n"
        "برای تست ارسال: /viplogtest"
    )


async def _send(bot, text):
    channel = _vip_channel_id()
    if not channel or not bot:
        return False
    chat_id = _parse_chat_id(channel)
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return True
    except BadRequest as e:
        if "can't parse entities" in str(e).lower():
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=_plain_from_html(text),
                    disable_web_page_preview=True,
                )
                return True
            except Exception as plain_err:
                logger.error(f"VIP log plain-text send failed: {plain_err}")
                return False
        logger.error(f"VIP log send failed for chat_id={chat_id}: {e}")
        return False
    except Forbidden as e:
        logger.error(
            f"VIP log forbidden for chat_id={chat_id}: {e}. "
            "Is the bot a channel admin with post permission?"
        )
        return False
    except Exception as e:
        logger.error(f"VIP log send failed for chat_id={chat_id}: {e}")
        return False


async def log_vip(bot, event_type, user=None, **fields):
    """Generic VIP log entry. All specialized loggers delegate here."""
    if not _enabled():
        return
    lines = [f"<b>{html.escape(event_type)}</b> {_ts()}"]
    if user is not None:
        lines.append(f"کاربر: {html.escape(_fmt_user(user))}")
    for key, value in fields.items():
        if value is None:
            continue
        label = html.escape(str(key))
        text = html.escape(str(value)[:800])
        lines.append(f"{label}: {text}")
    await _send(bot, "\n".join(lines))


def _describe_update(update):
    if update.callback_query:
        return "دکمه", {"داده": update.callback_query.data or ""}
    if update.inline_query:
        return "اینلاین", {"جستجو": update.inline_query.query or ""}
    msg = update.effective_message
    if msg:
        text = msg.text or msg.caption or ""
        if text.startswith("/"):
            return "دستور", {"متن": text[:500]}
        if text:
            return "پیام", {"متن": text[:500]}
        return "پیام", {"نوع": msg.content_type or "unknown"}
    if update.channel_post:
        text = update.channel_post.text or ""
        return "پست کانال", {"متن": text[:500]}
    return "به‌روزرسانی", {"نوع": "other"}


async def log_incoming_update(bot, update):
    if not _enabled() or not update:
        return
    event_type, fields = _describe_update(update)
    chat = update.effective_chat
    if chat:
        fields["چت"] = f"{chat.type}:{chat.id}"
    await log_vip(bot, event_type, user=update.effective_user, **fields)


async def log_startup(bot, gate_ok, vip_ok, yt_ok):
    await log_vip(
        bot,
        "راه‌اندازی ربات",
        gate="OK" if gate_ok else "FAIL",
        vip_log="OK" if vip_ok else "FAIL",
        youtube="OK" if yt_ok else "FAIL",
    )


async def log_shutdown(bot):
    await log_vip(bot, "خاموش شدن ربات")


async def log_system(bot, event, user=None, **fields):
    await log_vip(bot, event, user=user, **fields)


async def log_gate_denied(bot, user, channel):
    await log_vip(bot, "مسدود — عضو کانال نیست", user=user, **{"کانال": channel})


async def log_rate_limit(bot, user, wait_minutes):
    await log_vip(bot, "محدودیت نرخ", user=user, **{"انتظار": f"{wait_minutes} دقیقه"})


async def log_download_start(bot, user, title, artist, source):
    await log_vip(bot, "شروع دانلود", user=user, **{
        "آهنگ": title, "هنرمند": artist, "منبع": source,
    })


async def log_cache_hit(bot, user, title, artist, source):
    await log_vip(bot, "برخورد کش", user=user, **{
        "آهنگ": title, "هنرمند": artist, "منبع": source,
    })


async def log_request(bot, update, query_text):
    await log_vip(
        bot, "درخواست", user=update.effective_user if update else None,
        **{"متن": query_text[:500]},
    )


async def log_download(bot, user, title, artist, platform, cached=False, playlist_info=None):
    fields = {
        "آهنگ": title or "?",
        "هنرمند": artist or "?",
        "پلتفرم": platform or "?",
        "کش": "بله" if cached else "خیر",
    }
    if playlist_info:
        fields["پلی‌لیست"] = playlist_info
    await log_vip(bot, "دانلود موفق", user=user, **fields)


async def log_download_fail(bot, user, title, artist, source, reason=None):
    await log_vip(bot, "دانلود ناموفق", user=user, **{
        "آهنگ": title, "هنرمند": artist, "منبع": source, "دلیل": reason or "—",
    })


async def log_error(bot, user, message, detail=None):
    fields = {"پیام": message}
    if detail:
        fields["جزئیات"] = str(detail)[:400]
    await log_vip(bot, "خطا", user=user, **fields)


async def log_playlist_start(bot, user, name, track_count):
    await log_vip(bot, "شروع پلی‌لیست", user=user, **{
        "مجموعه": name or "?", "تعداد": track_count,
    })


async def log_playlist_track(bot, user, index, total, title, artist, status):
    await log_vip(bot, "پلی‌لیست — آهنگ", user=user, **{
        "پیشرفت": f"{index}/{total}",
        "آهنگ": title,
        "هنرمند": artist,
        "وضعیت": status,
    })


async def log_playlist_done(bot, user, name, sent, total, failed=0, reason=None):
    fields = {
        "مجموعه": name or "?",
        "ارسال‌شده": f"{sent}/{total}",
        "ناموفق": failed,
    }
    if reason:
        fields["دلیل توقف"] = reason
    await log_vip(bot, "پایان پلی‌لیست", user=user, **fields)


async def log_broadcast(bot, admin_user, sent, failed):
    await log_vip(bot, "پیام همگانی", user=admin_user, **{
        "ارسال": sent, "ناموفق": failed,
    })
