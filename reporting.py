"""Admin reporting formatters and inline keyboards."""

import json
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

PER_PAGE = 10

REQUEST_TYPE_FA = {
    "command": "دستور",
    "message": "پیام",
    "inline": "اینلاین",
    "callback": "دکمه",
    "discover": "discover",
}


def _ts(value):
    if not value:
        return "—"
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(float(value)))


def _user_label(row):
    uid = row.get("user_id", "?")
    uname = row.get("username")
    if uname:
        return f"{uid} (@{uname})"
    return str(uid)


def _hit_pct(cached, total):
    if not total:
        return "—"
    return f"{100 * cached / total:.1f}٪"


def format_global_summary(data, platform_fa):
    hit = _hit_pct(data["cached_downloads"], data["total_downloads"])
    lines = [
        "گزارش کلی HiiT Radio",
        "",
        f"کاربران: {data['users']}",
        f"دانلودها: {data['downloads']} (کش: {hit})",
        f"درخواست‌ها: {data['requests']}",
        f"فایل‌های کش فعال: {data['cache_entries']} (برخورد: {data['cache_hits']})",
        "",
        "LLM /discover:",
        f"  فراخوانی: {data['llm_calls']} (کش: {data['llm_cached_calls']}, خطا: {data['llm_failed_calls']})",
        f"  توکن: {data['llm_tokens']} (prompt: {data['llm_prompt_tokens']}, completion: {data['llm_completion_tokens']})",
    ]
    if data.get("event_breakdown"):
        lines.append("")
        lines.append("رویدادهای تحلیلی:")
        for row in data["event_breakdown"][:8]:
            lines.append(f"  • {row['event_type']}: {row['cnt']}")
    if data.get("top_artists"):
        lines.append("")
        lines.append("پربازدیدترین هنرمندان:")
        for row in data["top_artists"][:5]:
            lines.append(f"  • {row['artist']} ({row['cnt']})")
    if data.get("platforms"):
        lines.append("")
        lines.append("پلتفرم‌ها:")
        for row in data["platforms"][:5]:
            lines.append(f"  • {platform_fa(row['platform'])}: {row['cnt']}")
    lines.append("")
    lines.append("از دکمه‌ها برای جزئیات استفاده کن یا /export")
    return "\n".join(lines)


def format_user_list(rows, page, total_pages, total):
    lines = [f"کاربران (صفحه {page + 1}/{total_pages} — {total} نفر)\n"]
    if not rows:
        lines.append("کاربری ثبت نشده.")
    for row in rows:
        uname = f"@{row['username']}" if row.get("username") else "—"
        name = row.get("first_name") or "—"
        lines.append(
            f"• {row['user_id']} {uname} ({name})\n"
            f"  دانلود: {row.get('total_downloads', 0)} | آخرین بازدید: {_ts(row.get('last_seen'))}"
        )
    return "\n".join(lines)


def format_user_detail(summary, top_artists=None):
    uname = f"@{summary['username']}" if summary.get("username") else "—"
    lines = [
        f"کاربر {summary['user_id']}",
        f"نام: {summary.get('first_name') or '—'}",
        f"یوزرنیم: {uname}",
        f"اولین بازدید: {_ts(summary.get('first_seen'))}",
        f"آخرین بازدید: {_ts(summary.get('last_seen'))}",
        "",
        f"دانلودها: {summary.get('history_count', 0)} (ثبت‌شده: {summary.get('total_downloads', 0)})",
        f"درخواست‌ها: {summary.get('request_count', 0)}",
        f"دانلود در ساعت اخیر: {summary.get('downloads_last_hour', 0)}",
        "",
        "LLM:",
        f"  فراخوانی: {summary.get('llm_calls', 0)} (کش: {summary.get('llm_cached_calls', 0)})",
        f"  توکن: {summary.get('llm_tokens', 0)}",
    ]
    if top_artists:
        lines.append("")
        lines.append("هنرمندان محبوب:")
        for row in top_artists:
            lines.append(f"  • {row['artist']} ({row['download_count']})")
    return "\n".join(lines)


def format_download_page(rows, page, total_pages, total, title="دانلودها"):
    lines = [f"{title} (صفحه {page + 1}/{total_pages} — {total})\n"]
    for row in rows:
        cached = "کش" if row.get("cached") else "جدید"
        user = _user_label(row) if "user_id" in row else ""
        prefix = f"[{user}] " if user else ""
        lines.append(
            f"• {prefix}{row.get('title', '?')} — {row.get('artist', '?')}\n"
            f"  {row.get('platform', '?')} | {cached} | {_ts(row.get('created_at'))}"
        )
    if not rows:
        lines.append("موردی نیست.")
    return "\n".join(lines)


def format_request_page(rows, page, total_pages, total, title="درخواست‌ها"):
    lines = [f"{title} (صفحه {page + 1}/{total_pages} — {total})\n"]
    for row in rows:
        rtype = REQUEST_TYPE_FA.get(row.get("request_type"), row.get("request_type", "?"))
        user = _user_label(row) if "user_id" in row else ""
        prefix = f"[{user}] " if user else ""
        text = (row.get("text") or "")[:120]
        lines.append(f"• {prefix}{rtype}: {text}\n  {_ts(row.get('created_at'))}")
    if not rows:
        lines.append("موردی نیست.")
    return "\n".join(lines)


def format_analytics_page(rows, page, total_pages, total, title="رویدادها"):
    lines = [f"{title} (صفحه {page + 1}/{total_pages} — {total})\n"]
    for row in rows:
        user = _user_label(row) if row.get("user_id") else "—"
        payload = row.get("payload_json") or "{}"
        try:
            payload_obj = json.loads(payload)
            payload_short = json.dumps(payload_obj, ensure_ascii=False)[:100]
        except json.JSONDecodeError:
            payload_short = payload[:100]
        lines.append(
            f"• [{user}] {row.get('event_type', '?')}\n"
            f"  {payload_short} | {_ts(row.get('created_at'))}"
        )
    if not rows:
        lines.append("موردی نیست.")
    return "\n".join(lines)


def format_llm_page(rows, page, total_pages, total, title="LLM"):
    lines = [f"{title} (صفحه {page + 1}/{total_pages} — {total})\n"]
    for row in rows:
        user = _user_label(row) if "user_id" in row else ""
        prefix = f"[{user}] " if user else ""
        cached = "کش" if row.get("cached") else "API"
        ok = "OK" if row.get("success") else "FAIL"
        lines.append(
            f"• {prefix}{row.get('model', '?')} | {cached} | {ok}\n"
            f"  توکن: {row.get('total_tokens', 0)} "
            f"(p={row.get('prompt_tokens', 0)}, c={row.get('completion_tokens', 0)}) | "
            f"پیشنهاد: {row.get('recommendations_count', 0)} | {_ts(row.get('created_at'))}"
        )
    if not rows:
        lines.append("موردی نیست.")
    return "\n".join(lines)


def format_cache_page(rows, page, total_pages, total):
    lines = [f"کش فعال (صفحه {page + 1}/{total_pages} — {total})\n"]
    for row in rows:
        size_kb = (row.get("size_bytes") or 0) // 1024
        lines.append(
            f"• {row.get('title', '?')} — {row.get('artist', '?')}\n"
            f"  برخورد: {row.get('hit_count', 0)} | {size_kb}KB | انقضا: {_ts(row.get('expires_at'))}"
        )
    if not rows:
        lines.append("موردی نیست.")
    return "\n".join(lines)


def _page_row(scope, page, total_pages):
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton("◀ قبلی", callback_data=f"rpt:{scope}:{page - 1}"))
    if page + 1 < total_pages:
        buttons.append(InlineKeyboardButton("بعدی ▶", callback_data=f"rpt:{scope}:{page + 1}"))
    return buttons


def build_global_menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("کاربران", callback_data="rpt:users:0"),
            InlineKeyboardButton("دانلودها", callback_data="rpt:global:dl:0"),
        ],
        [
            InlineKeyboardButton("درخواست‌ها", callback_data="rpt:global:req:0"),
            InlineKeyboardButton("رویدادها", callback_data="rpt:global:evt:0"),
        ],
        [
            InlineKeyboardButton("LLM", callback_data="rpt:global:llm:0"),
            InlineKeyboardButton("کش", callback_data="rpt:global:cache:0"),
        ],
        [InlineKeyboardButton("بازگشت به خلاصه", callback_data="rpt:menu")],
    ])


def build_user_menu_keyboard(user_id):
    uid = str(user_id)
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("دانلودها", callback_data=f"rpt:user:{uid}:dl:0"),
            InlineKeyboardButton("درخواست‌ها", callback_data=f"rpt:user:{uid}:req:0"),
        ],
        [
            InlineKeyboardButton("رویدادها", callback_data=f"rpt:user:{uid}:evt:0"),
            InlineKeyboardButton("LLM", callback_data=f"rpt:user:{uid}:llm:0"),
        ],
        [
            InlineKeyboardButton("هنرمندان", callback_data=f"rpt:user:{uid}:artists"),
            InlineKeyboardButton("بازگشت", callback_data="rpt:users:0"),
        ],
    ])


def build_pagination_keyboard(scope, page, total_pages, extra=None):
    rows = []
    if extra:
        rows.append(extra)
    nav = _page_row(scope, page, total_pages)
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton("منوی گزارش", callback_data="rpt:menu")])
    return InlineKeyboardMarkup(rows)
