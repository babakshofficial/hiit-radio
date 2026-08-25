"""User-initiated error reports — one-click button on failure messages."""

import json
import logging
import time
from datetime import datetime, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import messages as msg

logger = logging.getLogger(__name__)

REPORT_RATE_LIMIT = 10
REPORT_RATE_WINDOW_SEC = 24 * 3600
ADMIN_SUMMARY_MAX = 3500


def build_keyboard(report_id, *, include_retry=True):
    """Report + optional Retry on one row."""
    row = [
        InlineKeyboardButton(
            msg.error_report_button(),
            callback_data=f"err:{report_id}",
        ),
    ]
    if include_retry:
        row.append(
            InlineKeyboardButton(
                msg.error_retry_button(),
                callback_data=f"retry:{report_id}",
            )
        )
    return InlineKeyboardMarkup([row])


def create_context(db, user, *, kind, code, user_message, **context):
    # Ensure retry payload is always present for supported kinds.
    if "retry" not in context:
        retry = _default_retry_payload(kind, context)
        if retry is not None:
            context["retry"] = retry
    return db.create_error_report(
        user.id,
        error_kind=kind,
        error_code=code,
        user_message=user_message,
        context=context,
        username=getattr(user, "username", None),
        first_name=getattr(user, "first_name", None),
    )


def _default_retry_payload(kind, ctx):
    if kind == "payment":
        return None
    if kind == "download":
        payload = {}
        if ctx.get("query"):
            payload["query"] = ctx["query"]
        if ctx.get("title"):
            payload["title"] = ctx["title"]
        if ctx.get("artist"):
            payload["artist"] = ctx["artist"]
        if ctx.get("quality"):
            payload["quality"] = ctx["quality"]
        return payload or None
    if kind in ("metadata", "collection"):
        if ctx.get("query"):
            return {"query": ctx["query"]}
        return None
    if kind in ("similar", "lyrics"):
        if ctx.get("title"):
            return {
                "title": ctx.get("title"),
                "artist": ctx.get("artist") or "",
            }
        return None
    if kind == "discover":
        return {}
    if kind == "playlist":
        payload = {}
        if ctx.get("collection_url"):
            payload["collection_url"] = ctx["collection_url"]
        elif ctx.get("query"):
            payload["query"] = ctx["query"]
        if ctx.get("collection"):
            payload["collection"] = ctx["collection"]
        return payload or None
    return None


def kind_supports_retry(kind, ctx=None):
    ctx = ctx or {}
    if kind == "payment":
        return False
    retry = ctx.get("retry")
    if retry is None:
        retry = _default_retry_payload(kind, ctx)
    if retry is None:
        return False
    if kind == "playlist":
        return bool(retry.get("collection_url") or retry.get("query"))
    if kind == "discover":
        return True
    if kind in ("similar", "lyrics"):
        return bool(retry.get("title"))
    if kind in ("metadata", "collection"):
        return bool(retry.get("query"))
    if kind == "download":
        return bool(retry.get("query") or retry.get("title"))
    return False


def _format_trail(trail):
    if not trail:
        return None
    parts = []
    for item in trail:
        source = item.get("source", "?")
        score = item.get("score")
        error = item.get("error", "?")
        title = (item.get("title") or "").strip()
        bit = f"{source}"
        if score is not None:
            try:
                bit += f" {float(score):.0f}%"
            except (TypeError, ValueError):
                pass
        bit += f" → {error}"
        if title:
            bit += f" «{title[:80]}»"
        parts.append(bit)
    return " | ".join(parts)


def _ts(value):
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC"
        )
    except (TypeError, ValueError, OSError):
        return str(value)


def parse_context(row):
    raw = row.get("context_json") if row else None
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"raw": str(raw)[:200]}


def format_admin_summary(row):
    ctx = parse_context(row)
    lines = [
        "گزارش خطا از کاربر",
        f"#{row.get('id')} — {row.get('error_kind', '?')} ({row.get('error_code') or '—'})",
    ]
    created = _ts(row.get("created_at"))
    submitted = _ts(row.get("submitted_at"))
    if created:
        lines.append(f"زمان ثبت: {created}")
    if submitted:
        lines.append(f"زمان ارسال: {submitted}")

    uid = row.get("user_id", "?")
    uname = row.get("username")
    first = row.get("first_name")
    user_bits = [str(uid)]
    if uname:
        user_bits.append(f"@{uname}")
    if first:
        user_bits.append(first)
    lines.append(f"کاربر: {' · '.join(user_bits)}")

    if ctx.get("title"):
        album = ctx.get("album")
        line = f"آهنگ: {ctx['title']} — {ctx.get('artist') or '?'}"
        if album:
            line += f" (آلبوم: {album})"
        lines.append(line)
    if ctx.get("query"):
        lines.append(f"ورودی کاربر: {str(ctx['query'])[:400]}")
    if ctx.get("search_query"):
        lines.append(f"کوئری جستجو: {str(ctx['search_query'])[:300]}")
    if ctx.get("quality"):
        lines.append(f"کیفیت: {ctx['quality']}")
    if ctx.get("platform"):
        lines.append(f"پلتفرم/منبع: {ctx['platform']}")
    if ctx.get("collection"):
        lines.append(f"مجموعه: {ctx['collection']}")
    if ctx.get("collection_url"):
        lines.append(f"لینک مجموعه: {str(ctx['collection_url'])[:400]}")
    if any(k in ctx for k in ("sent", "total", "failed")):
        lines.append(
            f"پلی‌لیست: ارسال={ctx.get('sent', '?')} کل={ctx.get('total', '?')} "
            f"ناموفق={ctx.get('failed', '?')}"
        )
    failed_tracks = ctx.get("failed_tracks")
    if failed_tracks:
        bits = []
        for item in failed_tracks[:12]:
            if isinstance(item, dict):
                bits.append(
                    f"{item.get('title') or '?'} [{item.get('error') or '?'}]"
                )
            else:
                bits.append(str(item)[:80])
        lines.append("آهنگ‌های ناموفق: " + " | ".join(bits))

    trail = _format_trail(ctx.get("failure_trail"))
    if trail:
        lines.append(f"تلاش‌ها: {trail}")

    if "cookies_ok" in ctx:
        cookie_line = "کوکی یوتیوب: " + ("سالم" if ctx.get("cookies_ok") else "ناسالم")
        if ctx.get("cookies_detail"):
            cookie_line += f" — {str(ctx['cookies_detail'])[:200]}"
        lines.append(cookie_line)

    detail = ctx.get("detail") or ctx.get("exception")
    if detail:
        lines.append(f"جزئیات فنی: {str(detail)[:600]}")

    if row.get("user_message"):
        lines.append(f"پیام کاربر: {row['user_message'][:500]}")

    text = "\n".join(lines)
    if len(text) > ADMIN_SUMMARY_MAX:
        text = text[: ADMIN_SUMMARY_MAX - 20] + "\n… (truncated)"
    return text


def trail_snippet(ctx, limit=120):
    trail = _format_trail((ctx or {}).get("failure_trail"))
    if not trail:
        return None
    if len(trail) <= limit:
        return trail
    return trail[: limit - 1] + "…"


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
