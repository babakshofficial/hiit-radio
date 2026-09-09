"""User-facing copy façade — lookups go through locales + a language contextvar."""

from __future__ import annotations

import os
from contextvars import ContextVar

from locales import DEFAULT_LANG, SUPPORTED, get_strings, normalize_lang

DEVELOPER_NAME = os.getenv("DEVELOPER_NAME", "بابک").strip() or "بابک"
DEVELOPER_USERNAME = os.getenv("DEVELOPER_USERNAME", "").strip()
DEVELOPER_CHANNEL = (
    os.getenv("DEVELOPER_CHANNEL", "").strip()
    or os.getenv("REQUIRED_CHANNEL", "@HiiTRadio").strip()
    or "@HiiTRadio"
)
if not DEVELOPER_CHANNEL.startswith("@"):
    DEVELOPER_CHANNEL = f"@{DEVELOPER_CHANNEL.lstrip('@')}"

BOT_INLINE = "@HiiTRadioBot"

_lang_var: ContextVar[str] = ContextVar("ui_lang", default=DEFAULT_LANG)


def get_lang() -> str:
    return _lang_var.get()


def set_lang(lang: str | None) -> str:
    resolved = normalize_lang(lang) or DEFAULT_LANG
    _lang_var.set(resolved)
    return resolved


def use_lang(lang: str | None):
    """Set language; returns a token for ``reset_lang``."""
    return _lang_var.set(normalize_lang(lang) or DEFAULT_LANG)


def reset_lang(token) -> None:
    _lang_var.reset(token)


def t(key: str, **kwargs) -> str:
    table = get_strings(get_lang())
    text = table.get(key)
    if text is None:
        text = get_strings(DEFAULT_LANG).get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text
    return text


def __getattr__(name: str):
    if name == "UNKNOWN":
        return t("unknown")
    if name == "BTN_INVITE":
        return t("btn_invite")
    if name == "BTN_MORE_BY_ARTIST":
        return t("btn_more_by_artist")
    if name == "BTN_SIMILAR":
        return t("btn_similar")
    if name == "BTN_LYRICS":
        return t("btn_lyrics")
    if name == "BTN_ARTWORK":
        return t("btn_artwork")
    if name == "BTN_FAVORITE_ADD":
        return t("btn_favorite_add")
    if name == "BTN_FAVORITE_REMOVE":
        return t("btn_favorite_remove")
    raise AttributeError(f"module 'messages' has no attribute {name!r}")


def platform_fa(platform):
    if not platform:
        return t("unknown")
    p = platform.lower()
    if "spotify" in p:
        return t("platform_spotify")
    if "apple" in p:
        return t("platform_apple")
    if "youtube" in p:
        return t("platform_youtube")
    if "soundcloud" in p:
        return t("platform_soundcloud")
    if "deezer" in p:
        return t("platform_deezer")
    if "cache" in p:
        return t("platform_cache")
    return platform


def unknown_artist(artist):
    return artist or t("unknown")


def btn_redownload(title):
    label = (title or t("unknown"))[:26]
    return t("btn_redownload", label=label)


def btn_download(title, index=None):
    label = (title or t("unknown"))[:24]
    if index is not None:
        return t("btn_download_indexed", index=index, label=label)
    return t("btn_download", label=label)


def start_text(first_name=""):
    name = first_name or t("start_friend_name")
    return t("start_text", name=name)


def help_text():
    return t(
        "help_text",
        bot_inline=BOT_INLINE,
        premium_daily_limit=os.getenv("PREMIUM_DAILY_LIMIT", "100"),
    )


def aboutme_text():
    channel = DEVELOPER_CHANNEL
    developer_line = ""
    if DEVELOPER_USERNAME:
        username = (
            DEVELOPER_USERNAME
            if DEVELOPER_USERNAME.startswith("@")
            else f"@{DEVELOPER_USERNAME}"
        )
        developer_line = t("aboutme_developer_line", username=username)
    return t(
        "aboutme_text",
        developer_name=DEVELOPER_NAME,
        channel=channel,
        developer_line=developer_line,
    )


def history_empty():
    return t("history_empty")


def history_header():
    return t("history_header")


def discover_empty_history():
    return t("discover_empty_history")


def discover_not_configured():
    return t("discover_not_configured")


def discover_preparing():
    return t("discover_preparing")


def discover_llm_phase():
    return t("discover_llm_phase")


def discover_resolve_phase(done, total):
    return t("discover_resolve_phase", done=done, total=total)


def discover_llm_error():
    return t("discover_llm_error")


def discover_no_results():
    return t("discover_no_results")


def discover_header():
    return t("discover_header")


def cancel_ok(count=1):
    if count > 1:
        return t("cancel_ok_many", count=count)
    return t("cancel_ok")


def cancel_no_job():
    return t("cancel_no_job")


def too_many_jobs(limit):
    return t("too_many_jobs", limit=limit)


def preview_caption(title="", artist=""):
    title = (title or "").strip()
    artist = (artist or "").strip()
    if title and artist:
        return t("preview_caption_full", title=title, artist=artist)
    if title:
        return t("preview_caption_title", title=title)
    return t("preview_caption")


def download_cancelled():
    return t("download_cancelled")


def work_cancelled():
    return t("work_cancelled")


def rate_limit(minutes):
    return t("rate_limit", minutes=minutes)


def _tier_label(tier):
    return {
        "free": t("tier_free"),
        "premium": t("tier_premium"),
        "unlimited": t("tier_unlimited"),
    }.get(tier, tier)


def quota_exceeded(used, limit, tier):
    return t("quota_exceeded", used=used, limit=limit, tier=_tier_label(tier))


def premium_status(snapshot):
    from datetime import datetime
    from zoneinfo import ZoneInfo
    import entitlements as ent

    lines = [
        t("premium_status_title"),
        t("premium_plan", tier=_tier_label(snapshot["tier"])),
    ]
    sub = snapshot.get("subscription")
    if sub and sub.get("expires_at"):
        exp = datetime.fromtimestamp(
            float(sub["expires_at"]), ZoneInfo(os.getenv("QUOTA_TZ", "Asia/Tehran"))
        )
        lines.append(t("premium_expires", expires=exp.strftime("%Y-%m-%d %H:%M")))
    if snapshot.get("limit") is None:
        lines.append(t("premium_limit_unlimited"))
    else:
        lines.append(
            t(
                "premium_limit_today",
                used=snapshot.get("used", 0),
                limit=snapshot.get("limit"),
            )
        )
    lines.append(t("premium_day", day=snapshot.get("day")))
    lines.append("")
    lines.append(
        t(
            "premium_footer",
            topup=ent.TOPUP_AMOUNT,
            premium_daily=ent.PREMIUM_DAILY_LIMIT,
        )
    )
    return "\n".join(lines)


def invite_status(progress):
    return t(
        "invite_status",
        toward=progress["toward"],
        needed=progress["needed"],
        credited=progress["credited"],
        pending=progress["pending"],
        topup=os.getenv("TOPUP_AMOUNT", "10"),
        link=progress["link"],
    )


def payment_failed():
    return t("payment_failed")


def payment_already_processed():
    return t("payment_already_processed")


def payment_bonus_ok(amount, day):
    return t("payment_bonus_ok", amount=amount, day=day)


def referral_topup_granted():
    return t("referral_topup_granted", amount=os.getenv("TOPUP_AMOUNT", "10"))


def payment_premium_ok(tier, expires_at):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    exp = datetime.fromtimestamp(
        float(expires_at), ZoneInfo(os.getenv("QUOTA_TZ", "Asia/Tehran"))
    )
    tier_label = t("tier_premium") if tier == "premium" else t("tier_unlimited")
    return t(
        "payment_premium_ok",
        tier=tier_label,
        expires=exp.strftime("%Y-%m-%d %H:%M"),
    )


def btn_buy_daypass(stars, amount):
    return t("btn_buy_daypass", amount=amount, stars=stars)


def btn_buy_weekly(stars):
    return t("btn_buy_weekly", stars=stars)


def btn_buy_monthly(stars):
    return t("btn_buy_monthly", stars=stars)


def _expires_local(expires_at):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    exp = datetime.fromtimestamp(
        float(expires_at), ZoneInfo(os.getenv("QUOTA_TZ", "Asia/Tehran"))
    )
    return exp.strftime("%Y-%m-%d %H:%M")


def grant_ok(user_id, tier, expires_at):
    return t(
        "grant_ok",
        user_id=user_id,
        tier=tier,
        expires=_expires_local(expires_at),
    )


def topup_ok(user_id, amount, day):
    return t("topup_ok", user_id=user_id, amount=amount, day=day)


def grant_user_notice(tier, expires_at, days):
    tier_label = t("tier_premium") if tier == "premium" else t("tier_unlimited")
    return t(
        "grant_user_notice",
        tier=tier_label,
        days=days,
        expires=_expires_local(expires_at),
    )


def topup_user_notice(amount, day):
    return t("topup_user_notice", amount=amount, day=day)


def searching():
    return t("searching")


def downloading():
    return t("downloading")


def metadata_not_found():
    return t("metadata_not_found")


def not_music_query():
    return t("not_music_query")


def collection_not_found():
    return t("collection_not_found")


def send_failed():
    return t("send_failed")


def download_not_found():
    return t("download_not_found")


def download_fail_bot_check():
    return t("download_fail_bot_check")


def download_fail_timeout():
    return t("download_fail_timeout")


def download_fail_invalid():
    return t("download_fail_invalid")


def download_fail_message(error_code):
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
    return t("record_not_found")


def songs_not_found():
    return t("songs_not_found")


def similar_preparing():
    return t("similar_preparing")


def similar_llm_phase():
    return t("similar_llm_phase")


def similar_resolve_phase(done, total):
    return t("similar_resolve_phase", done=done, total=total)


def similar_header(title, artist):
    if artist:
        return t("similar_header_with_artist", title=title, artist=artist)
    return t("similar_header", title=title)


def similar_not_found():
    return t("similar_not_found")


def nearby_header(title, artist):
    if artist:
        return t("nearby_header_with_artist", title=title or "", artist=artist)
    return t("nearby_header", title=title or "")


def liked_empty():
    return t("liked_empty")


def liked_header():
    return t("liked_header")


def favorite_added(title):
    return t("favorite_added", title=title or t("unknown"))


def favorite_removed(title):
    return t("favorite_removed", title=title or t("unknown"))


def favorite_missing():
    return t("favorite_missing")


def top_header(period_label):
    return t("top_header", period=period_label)


def top_empty():
    return t("top_empty")


def top_period_label(period):
    return {
        "day": t("top_period_day"),
        "week": t("top_period_week"),
        "all": t("top_period_all"),
    }.get(period, t("top_period_week"))


def lyrics_not_found():
    return t("lyrics_not_found")


def lyrics_header(title, artist):
    if artist:
        return t("lyrics_header_with_artist", title=title, artist=artist)
    return t("lyrics_header", title=title)


def pick_expired():
    return t("pick_expired")


def pick_expired_short():
    return t("pick_expired_short")


def more_by_artist(artist):
    return t("more_by_artist", artist=artist)


def inline_description(artist):
    return t("inline_description", artist=artist)


def gate_denied(channel):
    channel = channel.lstrip("@")
    return t("gate_denied", channel=channel)


def gate_alert():
    return t("gate_alert")


def playlist_empty():
    return t("playlist_empty")


def playlist_start(collection_name, total, original=None):
    name = collection_name or t("playlist_default_name")
    text = t("playlist_start", name=name, total=total)
    if original and original > total:
        text = f"{text}\n{t('playlist_capped', original=original, limit=total)}"
    return text


def playlist_cancelled(sent, total):
    return t("playlist_cancelled", sent=sent, total=total)


def playlist_rate_limited(minutes, sent, total):
    return t("playlist_rate_limited", minutes=minutes, sent=sent, total=total)


def playlist_summary(sent, total, failed=0):
    if failed:
        return t("playlist_summary_failed", sent=sent, total=total, failed=failed)
    return t("playlist_summary", sent=sent, total=total)


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
        eta_line = t("progress_eta", m=m, s=s)
    counter = (
        t("progress_counter", current=current, total=total) if show_counter else ""
    )
    return t(
        "progress_update",
        label=label,
        bar=bar,
        pct=pct,
        counter=counter,
        detail_line=detail_line,
        eta_line=eta_line,
    )


def progress_done(label, summary=""):
    if summary:
        return t("progress_done_with_summary", label=label, summary=summary)
    return t("progress_done", label=label)


def progress_fail(label, reason=""):
    if reason:
        return t("progress_fail_with_reason", label=label, reason=reason)
    return t("progress_fail", label=label)


def progress_detail(title, artist, phase_key, **kwargs):
    """Title/artist line plus a localized download-phase message."""
    name = (title or "").strip() or t("unknown")
    who = (artist or "").strip() or t("unknown")
    return f"{name} — {who}\n{t(phase_key, **kwargs)}"


def error_report_button():
    return t("error_report_button")


def error_retry_button():
    return t("error_retry_button")


def error_retrying():
    return t("error_retrying")


def error_retry_unavailable():
    return t("error_retry_unavailable")


def error_report_sent():
    return t("error_report_sent")


def error_report_already_sent():
    return t("error_report_already_sent")


def error_report_rate_limited():
    return t("error_report_rate_limited")


def track_report_button():
    return t("btn_report_track")


def track_report_sent():
    return t("track_report_sent")


def track_report_user_message():
    return t("track_report_user_message")


def support_admin_prompt(report_id, user_id):
    return t("support_admin_prompt", report_id=report_id, user_id=user_id)


def support_user_message(admin_text):
    return t("support_user_message", admin_text=admin_text)


def support_user_opened():
    return t("support_user_opened")


def support_user_closed():
    return t("support_user_closed")


def support_no_thread():
    return t("support_no_thread")


def support_usage():
    return t("support_usage")


def support_admin_usage():
    return t("support_admin_usage")


def support_empty_message():
    return t("support_empty_message")


def support_sent_admin(user_id):
    return t("support_sent_admin", user_id=user_id)


def support_sent_user():
    return t("support_sent_user")


def support_forward_to_admin(user_label, report_id, text):
    return t(
        "support_forward_to_admin",
        user_label=user_label,
        report_id=report_id,
        text=text,
    )


def support_send_failed_blocked():
    return t("support_send_failed_blocked")


def support_send_failed():
    return t("support_send_failed")


def support_thread_ended_admin(thread_id):
    return t("support_thread_ended_admin", thread_id=thread_id)


def support_thread_ended_no_open():
    return t("support_thread_ended_no_open")


def support_reply_button():
    return t("support_reply_button")


def support_end_button():
    return t("support_end_button")


def support_report_not_found():
    return t("support_report_not_found")


def cookies_status(ok, detail, path, updated=None):
    state = t("cookies_state_ok") if ok else t("cookies_state_bad")
    lines = [
        t("cookies_status_title"),
        t("cookies_status_state", state=state),
        t("cookies_status_detail", detail=detail),
        t("cookies_status_path", path=path),
    ]
    if updated:
        lines.append(t("cookies_status_updated", updated=updated))
    lines.append("")
    lines.append(t("cookies_status_footer"))
    return "\n".join(lines)


def cookies_accepted(detail, backed_up):
    text = t("cookies_accepted", detail=detail)
    if backed_up:
        text += t("cookies_accepted_backup")
    return text


def cookies_rejected(detail):
    return t("cookies_rejected", detail=detail)


def cookies_too_large(limit_kb):
    return t("cookies_too_large", limit_kb=limit_kb)


def artwork_not_found():
    return t("artwork_not_found")


def artwork_sending():
    return t("artwork_sending")


def search_usage():
    return t("search_usage")


def search_empty():
    return t("search_empty")


def search_header(query):
    return t("search_header", query=query)


def search_hit_line(index, name, subtitle, kind, source):
    kind_label = {
        "track": t("search_kind_track"),
        "album": t("search_kind_album"),
        "playlist": t("search_kind_playlist"),
        "artist": t("search_kind_artist"),
    }.get(kind, kind)
    sub = f" — {subtitle}" if subtitle else ""
    return t("search_hit_line", index=index, kind=kind_label, name=name, sub=sub)


def artist_usage():
    return t("artist_usage")


def artist_not_found(name):
    return t("artist_not_found", name=name)


def artist_header(name):
    return t("artist_header", name=name)


def artist_top_header():
    return t("artist_top_header")


def artist_albums_header():
    return t("artist_albums_header")


def quality_status(current):
    hint = {
        "128": t("quality_hint_128"),
        "192": t("quality_hint_192"),
        "256": t("quality_hint_256"),
        "320": t("quality_hint_320"),
        "original": t("quality_hint_original"),
    }.get(current, "")
    head = (
        t("quality_status_kbps", value=current)
        if current != "original"
        else t("quality_status_original")
    )
    return head + (f"\n{hint}" if hint else "") + "\n\n" + t("quality_status_footer")


def quality_set(value):
    if value == "original":
        return t("quality_set_original")
    return t("quality_set_kbps", value=value)


def quality_invalid():
    return t("quality_invalid")


def playlist_zip_sending(name, count):
    return t("playlist_zip_sending", name=name, count=count)


def playlist_zip_caption(name, count):
    return t("playlist_zip_caption", name=name, count=count)


def follow_success(artist_name):
    return t("follow_success", artist=artist_name)


def unfollow_success(artist_name):
    return t("unfollow_success", artist=artist_name)


def already_following(artist_name):
    return t("already_following", artist=artist_name)


def not_following():
    return t("not_following")


def following_header():
    return t("following_header")


def follow_usage():
    return t("follow_usage")


def btn_follow(artist):
    return t("btn_follow", artist=artist)


def btn_unfollow(artist):
    return t("btn_unfollow", artist=artist)


def new_release_notification(artist, album, date=""):
    date_line = t("new_release_date_line", date=date) if date else ""
    return t(
        "new_release_notification",
        artist=artist,
        album=album,
        date_line=date_line,
    )


def lang_choose():
    return t("lang_choose")


def lang_set(lang_code):
    return t("lang_set", lang_name=t(f"lang_name_{lang_code}"))


def changelog_header():
    return t("changelog_header")


def changelog_admin_prompt():
    return t("changelog_admin_prompt")


def changelog_admin_preview(preview):
    return t("changelog_admin_preview", preview=preview)


def changelog_btn_send():
    return t("changelog_btn_send")


def changelog_btn_skip():
    return t("changelog_btn_skip")


def changelog_generating():
    return t("changelog_generating")


def changelog_done(sent, failed):
    return t("changelog_done", sent=sent, failed=failed)


def changelog_skipped():
    return t("changelog_skipped")


def changelog_empty():
    return t("changelog_empty")


def changelog_llm_unavailable():
    return t("changelog_llm_unavailable")


def changelog_llm_failed():
    return t("changelog_llm_failed")


def changelog_busy():
    return t("changelog_busy")


def changelog_forbidden():
    return t("changelog_forbidden")


def menu_label(key):
    return t(key)


__all__ = [
    "SUPPORTED",
    "DEFAULT_LANG",
    "get_lang",
    "set_lang",
    "use_lang",
    "reset_lang",
    "t",
    "normalize_lang",
]
