"""VIP admin channel logging — all bot activity."""

import html
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from telegram.error import BadRequest, Forbidden

from messages import t_lang

load_dotenv(Path(__file__).resolve().parent / ".env")

logger = logging.getLogger(__name__)

_vip_lang: str | None = None


def set_vip_log_language(lang: str | None) -> None:
    """VIP channel log labels follow the admin's bot language."""
    global _vip_lang
    _vip_lang = lang


def _L(key: str, **kwargs) -> str:
    return t_lang(_vip_lang, key, **kwargs)


def _vip_field_label(key: str) -> str:
    fld = f"vip_fld_{key}"
    text = _L(fld)
    return text if text != fld else key


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
    return int(f"-100{digits}")


def _parse_chat_id(raw):
    return _normalize_chat_id(raw)


def _enabled():
    return bool(_vip_channel_id())


_COOKIE_ALERT_COOLDOWN = 30 * 60
_last_cookie_alert_at = 0.0
_last_cookie_health = None


def _ts():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _fmt_user(user):
    if not user:
        return "—"
    parts = [_L("vip_log_user_fmt", user_id=user.id)]
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
            return False, _L("admin_vip_not_admin")
        if hasattr(member, "can_post_messages") and not member.can_post_messages:
            return False, _L("admin_vip_no_post")
    elif status not in {"administrator", "member", "creator"}:
        return False, _L("admin_vip_not_member", status=status)
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
        return False, _L("admin_vip_env_missing")
    chat_id = _parse_chat_id(channel)
    try:
        chat = await bot.get_chat(chat_id)
        ok, reason = await _check_post_permission(bot, chat.id, chat.type)
        if not ok:
            return False, reason
        title = html.escape(getattr(chat, "title", str(chat.id)))
        text = (
            f"<b>{html.escape(_L('admin_vip_test_title'))}</b> {_ts()}\n"
            f"{html.escape(_L('admin_vip_test_channel', title=title))}\n"
            f"{html.escape(_L('admin_vip_test_id', chat_id=chat.id))}"
        )
        sent = await _send(bot, text)
        if not sent:
            return False, _L("admin_vip_send_failed")
        return True, _L(
            "admin_vip_test_ok",
            title=getattr(chat, "title", None) or chat.id,
            chat_id=chat.id,
        )
    except (BadRequest, Forbidden) as e:
        return False, _L("admin_vip_forbidden_hint", error=e)
    except Exception as e:
        return False, str(e)


async def notify_admin_vip_issue(bot, message, reply_markup=None):
    admin_id = os.getenv("ADMIN_ID", "").strip()
    if not admin_id or not bot:
        return
    try:
        await bot.send_message(
            chat_id=int(admin_id),
            text=message,
            reply_markup=reply_markup,
        )
    except Exception as e:
        logger.error(f"Could not notify admin about VIP logging: {e}")


def vip_status_text():
    channel = _vip_channel_id()
    if not channel:
        return _L("admin_vip_status_disabled")
    parsed = _parse_chat_id(channel)
    return _L("admin_vip_status_enabled", channel=channel, parsed=parsed)


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


async def log_vip(bot, event_key, user=None, **fields):
    """Generic VIP log entry. ``event_key`` is a locale key (vip_evt_*)."""
    if not _enabled():
        return
    lines = [f"<b>{html.escape(_L(event_key))}</b> {_ts()}"]
    if user is not None:
        lines.append(f"{html.escape(_vip_field_label('user'))}: {html.escape(_fmt_user(user))}")
    for key, value in fields.items():
        if value is None:
            continue
        label = html.escape(_vip_field_label(key))
        text = html.escape(str(value)[:800])
        lines.append(f"{label}: {text}")
    await _send(bot, "\n".join(lines))


def message_media_kind(msg):
    if not msg:
        return "unknown"
    for name in (
        "text", "caption", "audio", "voice", "document", "photo",
        "video", "animation", "sticker", "video_note", "contact",
        "location", "venue", "poll", "dice",
    ):
        if getattr(msg, name, None):
            return name
    return "unknown"


def _describe_update(update):
    if update.callback_query:
        return "vip_evt_button", {"data": update.callback_query.data or ""}
    if update.inline_query:
        return "vip_evt_inline", {"search": update.inline_query.query or ""}
    msg = update.effective_message
    if msg:
        text = msg.text or msg.caption or ""
        if text.startswith("/"):
            return "vip_evt_command", {"text": text[:500]}
        if text:
            return "vip_evt_message", {"text": text[:500]}
        return "vip_evt_message", {"kind": message_media_kind(msg)}
    if update.channel_post:
        text = update.channel_post.text or ""
        return "vip_evt_channel_post", {"text": text[:500]}
    return "vip_evt_update", {"kind": "other"}


async def log_incoming_update(bot, update):
    if not _enabled() or not update:
        return
    event_key, fields = _describe_update(update)
    chat = update.effective_chat
    if chat:
        fields["chat"] = f"{chat.type}:{chat.id}"
    await log_vip(bot, event_key, user=update.effective_user, **fields)


async def log_startup(bot, gate_ok, vip_ok, yt_ok):
    await log_vip(
        bot,
        "vip_evt_startup",
        gate=_L("vip_val_healthy") if gate_ok else _L("vip_val_unhealthy"),
        vip_log=_L("vip_val_healthy") if vip_ok else _L("vip_val_unhealthy"),
        youtube=_L("vip_val_healthy") if yt_ok else _L("vip_val_unhealthy"),
    )


async def log_shutdown(bot):
    await log_vip(bot, "vip_evt_shutdown")


async def log_system(bot, event, user=None, **fields):
    await log_vip(bot, event, user=user, **fields)


async def log_gate_denied(bot, user, channel):
    await log_vip(bot, "vip_evt_gate_denied", user=user, channel=channel)


async def log_rate_limit(bot, user, wait_minutes):
    await log_vip(
        bot, "vip_evt_rate_limit", user=user, wait=f"{wait_minutes} min",
    )


async def log_download_start(bot, user, title, artist, source):
    await log_vip(bot, "vip_evt_dl_start", user=user, song=title, artist=artist, source=source)


async def log_cache_hit(bot, user, title, artist, source):
    await log_vip(bot, "vip_evt_cache_hit", user=user, song=title, artist=artist, source=source)


async def log_request(bot, update, query_text):
    await log_vip(
        bot, "vip_evt_request", user=update.effective_user if update else None,
        text=query_text[:500],
    )


async def log_download(bot, user, title, artist, platform, cached=False, playlist_info=None):
    fields = {
        "song": title or "?",
        "artist": artist or "?",
        "platform": platform or "?",
        "cached": _L("vip_val_yes") if cached else _L("vip_val_no"),
    }
    if playlist_info:
        fields["playlist"] = playlist_info
    await log_vip(bot, "vip_evt_dl_ok", user=user, **fields)


async def log_download_fail(bot, user, title, artist, source, reason=None):
    await log_vip(bot, "vip_evt_dl_fail", user=user, song=title, artist=artist, source=source, reason=reason or "—")


async def log_error(bot, user, message, detail=None):
    fields = {"message": message}
    if detail:
        fields["detail"] = str(detail)[:400]
    await log_vip(bot, "vip_evt_error", user=user, **fields)


async def log_user_report(bot, user, report_row):
    import error_report
    import support_chat

    summary = error_report.format_admin_summary(report_row)
    report_id = report_row.get("id")
    keyboard = support_chat.build_admin_report_keyboard(report_id)
    await log_vip(
        bot,
        "vip_evt_user_report",
        user=user,
        error_kind=report_row.get("error_kind") or "?",
        error_code=report_row.get("error_code") or "—",
        detail=summary[:3500],
    )
    await notify_admin_vip_issue(bot, summary, reply_markup=keyboard)


async def log_playlist_start(bot, user, name, track_count):
    await log_vip(bot, "vip_evt_pl_start", user=user, collection=name or "?", count=track_count)


async def log_playlist_track(bot, user, index, total, title, artist, status):
    await log_vip(bot, "vip_evt_pl_track", user=user, progress=f"{index}/{total}", song=title, artist=artist, status=status)


async def log_playlist_done(bot, user, name, sent, total, failed=0, reason=None):
    fields = {
        "collection": name or "?",
        "sent": f"{sent}/{total}",
        "failed": failed,
    }
    if reason:
        fields["stop_reason"] = reason
    await log_vip(bot, "vip_evt_pl_done", user=user, **fields)


async def log_broadcast(bot, admin_user, sent, failed):
    await log_vip(bot, "vip_evt_broadcast", user=admin_user, sent=sent, failed=failed)


async def log_cookie_health(bot, healthy, detail=None):
    fields = {"health": _L("vip_val_healthy") if healthy else _L("vip_val_unhealthy")}
    if detail:
        fields["detail"] = str(detail)[:400]
    await log_vip(bot, "vip_evt_cookie_health", **fields)


async def maybe_alert_cookie_issue(bot, detail=None, force=False):
    import time

    global _last_cookie_alert_at
    now = time.time()
    if not force and (now - _last_cookie_alert_at) < _COOKIE_ALERT_COOLDOWN:
        return False
    _last_cookie_alert_at = now
    await log_cookie_health(
        bot,
        healthy=False,
        detail=detail or _L("vip_cookie_alert_detail"),
    )
    return True


async def report_cookie_health_transition(bot, healthy, detail=None):
    global _last_cookie_health
    if _last_cookie_health is healthy:
        return False
    _last_cookie_health = healthy
    await log_cookie_health(bot, healthy, detail=detail)
    return True
