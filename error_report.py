"""User-initiated error reports — one-click button on failure messages."""

import json
import logging
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import messages as msg

logger = logging.getLogger(__name__)

REPORT_RATE_LIMIT = 10
REPORT_RATE_WINDOW_SEC = 24 * 3600


def build_keyboard(report_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(msg.error_report_button(), callback_data=f"err:{report_id}")],
    ])


def create_context(db, user, *, kind, code, user_message, **context):
    return db.create_error_report(
        user.id,
        error_kind=kind,
        error_code=code,
        user_message=user_message,
        context=context,
        username=getattr(user, "username", None),
        first_name=getattr(user, "first_name", None),
    )


def _format_trail(trail):
    if not trail:
        return None
    parts = []
    for item in trail:
        source = item.get("source", "?")
        score = item.get("score")
        error = item.get("error", "?")
        if score is not None:
            parts.append(f"{source} {score:.0f}% → {error}")
        else:
            parts.append(f"{source} → {error}")
    return " | ".join(parts)


def format_admin_summary(row):
    ctx = {}
    raw = row.get("context_json")
    if raw:
        try:
            ctx = json.loads(raw)
        except json.JSONDecodeError:
            ctx = {"raw": raw[:200]}
    lines = [
        "گزارش خطا از کاربر",
        f"#{row.get('id')} — {row.get('error_kind', '?')} ({row.get('error_code') or '—'})",
    ]
    uid = row.get("user_id", "?")
    uname = row.get("username")
    if uname:
        lines.append(f"کاربر: {uid} (@{uname})")
    else:
        lines.append(f"کاربر: {uid}")
    if ctx.get("title"):
        lines.append(f"آهنگ: {ctx['title']} — {ctx.get('artist') or '?'}")
    if ctx.get("query"):
        lines.append(f"جستجو: {ctx['query'][:300]}")
    trail = _format_trail(ctx.get("failure_trail"))
    if trail:
        lines.append(f"تلاش‌ها: {trail}")
    if ctx.get("cookies_ok") is False:
        lines.append("کوکی یوتیوب: ناسالم")
    if row.get("user_message"):
        lines.append(f"پیام کاربر: {row['user_message'][:400]}")
    return "\n".join(lines)


async def submit_and_notify(bot, db, report_id, user):
    since = time.time() - REPORT_RATE_WINDOW_SEC
    if db.count_user_submitted_reports_since(user.id, since) >= REPORT_RATE_LIMIT:
        return "rate_limited", None

    row = db.submit_error_report(report_id, user.id)
    if not row:
        existing = db.get_error_report(report_id)
        if existing and str(existing.get("user_id")) != str(user.id):
            return "forbidden", None
        if existing and existing.get("submitted_at"):
            return "already", existing
        return "not_found", None

    import admin_logger
    await admin_logger.log_user_report(bot, user, row)
    return "ok", row
