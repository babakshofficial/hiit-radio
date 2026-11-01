"""Opt-in weekly message: personal picks plus new releases from followed artists."""

import asyncio
import logging
import os
import time
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import Forbidden

import entitlements
import messages as msg
from llm_service import is_configured as llm_configured, recommend_songs
from metadata import AppleMusicMetadata

logger = logging.getLogger(__name__)

MIX_INTERVAL_SEC = 7 * 86400
MIX_SIZE = 5
_RELEASE_WINDOW_DAYS = 14
_SEND_FROM_HOUR = int(os.getenv("WEEKLY_MIX_FROM_HOUR", "10"))
_SEND_UNTIL_HOUR = int(os.getenv("WEEKLY_MIX_UNTIL_HOUR", "22"))


def _within_send_hours(now=None):
    hour = datetime.fromtimestamp(
        time.time() if now is None else now, entitlements.QUOTA_TZ,
    ).hour
    return _SEND_FROM_HOUR <= hour < _SEND_UNTIL_HOUR


def _pair_key(title, artist):
    return (title or "").strip().lower(), (artist or "").strip().lower()


async def _llm_candidates(db, user_id, history):
    if not history or not llm_configured():
        return []
    recs, usage = await recommend_songs(history, user_id=user_id, limit=MIX_SIZE + 3)
    db.log_llm_usage(
        user_id,
        model=usage.get("model"),
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        total_tokens=usage.get("total_tokens", 0),
        cached=False,
        success=bool(usage.get("success") and recs is not None),
        recommendations_count=usage.get("recommendations_count", 0),
    )
    return recs or []


async def _resolve_picks(candidates, heard):
    """Confirm each candidate exists in the catalog; drop anything already heard."""
    picks, seen = [], set(heard)
    for rec in candidates:
        title = (rec.get("title") or "").strip()
        artist = (rec.get("artist") or "").strip()
        if not title or _pair_key(title, artist) in seen:
            continue
        query = f"{title} {artist}".strip()
        resolved = await AppleMusicMetadata.search_by_query(query)
        if not resolved or not resolved.title:
            continue  # AI suggestions can be songs that don't exist.
        title, artist = resolved.title, resolved.artist or artist
        key = _pair_key(title, artist)
        if key in seen:
            continue
        seen.add(key)
        picks.append({"title": title, "artist": artist})
        if len(picks) >= MIX_SIZE:
            break
    return picks


async def build_mix(db, user_id):
    """Return ``(picks, releases)``. Charts are the fallback when AI picks fail."""
    history = db.get_user_history(user_id, limit=40)
    heard = {_pair_key(r.get("title"), r.get("artist")) for r in history}
    try:
        candidates = await _llm_candidates(db, user_id, history)
        picks = await _resolve_picks(candidates, heard)
    except Exception:
        logger.exception("Weekly mix picks failed for user %s", user_id)
        picks = []
    if len(picks) < MIX_SIZE:
        taken = heard | {_pair_key(p["title"], p["artist"]) for p in picks}
        charts = (
            db.get_top_songs(period="week", limit=MIX_SIZE * 4)
            + db.get_top_songs(period="all", limit=MIX_SIZE * 4)
        )
        for row in charts:
            key = _pair_key(row.get("title"), row.get("artist"))
            if len(picks) < MIX_SIZE and row.get("title") and key not in taken:
                taken.add(key)
                picks.append({"title": row["title"], "artist": row.get("artist") or ""})
    releases = db.recent_releases_for_user(
        user_id, days=_RELEASE_WINDOW_DAYS, limit=5,
    )
    return picks, releases


def render_mix(picks, releases, item_ids):
    lines = [msg.t("mix_header")]
    buttons = []
    for i, (pick, item_id) in enumerate(zip(picks, item_ids), 1):
        who = pick["artist"] or msg.t("unknown")
        lines.append(f"{i}. {pick['title']} — {who}")
        buttons.append([InlineKeyboardButton(
            f"⬇️ {i}. {pick['title']}"[:60], callback_data=f"mixpick:{item_id}",
        )])
    if releases:
        lines.extend(["", msg.t("mix_new_releases")])
        lines.extend(f"• {r['artist_name']} — {r['title']}" for r in releases)
    buttons.append([InlineKeyboardButton(msg.t("btn_mix_off"), callback_data="mix:off")])
    return "\n".join(lines), InlineKeyboardMarkup(buttons)


async def send_mix(bot, db, user_id, now=None):
    """Send one user's mix if it is due. Returns True when a message went out."""
    now = time.time() if now is None else now
    previous = db.claim_weekly_mix(user_id, now, MIX_INTERVAL_SEC)
    if previous is False:
        return False
    token = msg.use_lang(db.get_language(user_id))
    try:
        picks, releases = await build_mix(db, user_id)
        if not picks and not releases:
            return False
        item_ids = db.save_weekly_mix_items(user_id, picks, now=now)
        text, keyboard = render_mix(picks, releases, item_ids)
        await bot.send_message(chat_id=int(user_id), text=text, reply_markup=keyboard)
        db.log_event("weekly_mix_sent", user_id=user_id, payload={"picks": len(picks)})
        return True
    except Forbidden:
        logger.info("Weekly mix off for user %s: bot was blocked", user_id)
        db.set_weekly_mix(user_id, False)
        return False
    except Exception:
        # Nothing reached the user, so let the next hourly run try again.
        logger.exception("Weekly mix send failed for user %s", user_id)
        db.release_weekly_mix(user_id, previous)
        return False
    finally:
        msg.reset_lang(token)


async def run_due(bot, db, now=None):
    """Send every due mix, one at a time so LLM and Telegram calls stay gentle."""
    now = time.time() if now is None else now
    if not _within_send_hours(now):
        return 0
    sent = 0
    for user_id in db.list_weekly_mix_due(now, MIX_INTERVAL_SEC):
        if await send_mix(bot, db, user_id, now=now):
            sent += 1
        await asyncio.sleep(0.5)
    return sent
