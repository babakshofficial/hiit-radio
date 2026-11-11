"""Opt-in daily or weekly message: personal picks plus new releases from followed artists.

Daily picks come from Deezer's related artists (free); weekly picks use the LLM.
"""

import asyncio
import logging
import os
import random
import time
from collections import Counter
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import Forbidden

import catalog
import entitlements
import messages as msg
from database import MIX_INTERVALS
from llm_service import is_configured as llm_configured, recommend_songs
from metadata import AppleMusicMetadata

logger = logging.getLogger(__name__)

MIX_INTERVAL_SEC = MIX_INTERVALS["weekly"]
MIX_SIZE = 5
_RELEASE_WINDOW_DAYS = 14
_SEED_WINDOW_DAYS = 14
_NO_REPEAT_DAYS = 30
_DAILY_SEED_ARTISTS = 3
_SEND_FROM_HOUR = int(os.getenv("WEEKLY_MIX_FROM_HOUR", "10"))
_SEND_UNTIL_HOUR = int(os.getenv("WEEKLY_MIX_UNTIL_HOUR", "22"))


def _within_send_hours(now=None):
    hour = datetime.fromtimestamp(
        time.time() if now is None else now, entitlements.QUOTA_TZ,
    ).hour
    return _SEND_FROM_HOUR <= hour < _SEND_UNTIL_HOUR


def _pair_key(title, artist):
    return (title or "").strip().lower(), (artist or "").strip().lower()


async def _llm_candidates(db, user_id, history, avoid=None):
    if not history or not llm_configured():
        return []
    kwargs = {"avoid": avoid} if avoid else {}
    recs, usage = await recommend_songs(
        history, user_id=user_id, limit=MIX_SIZE + 3, **kwargs,
    )
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


async def _resolve_picks(candidates, heard, blocked_artists=frozenset()):
    """Confirm each candidate exists in the catalog; drop anything already heard."""
    picks, seen = [], set(heard)
    for rec in candidates:
        title = (rec.get("title") or "").strip()
        artist = (rec.get("artist") or "").strip()
        if not title or _pair_key(title, artist) in seen:
            continue
        if artist.lower() in blocked_artists:
            continue
        query = f"{title} {artist}".strip()
        resolved = await AppleMusicMetadata.search_by_query(query)
        if not resolved or not resolved.title:
            continue  # AI suggestions can be songs that don't exist.
        title, artist = resolved.title, resolved.artist or artist
        key = _pair_key(title, artist)
        if key in seen or key[1] in blocked_artists:
            continue
        seen.add(key)
        picks.append({"title": title, "artist": artist})
        if len(picks) >= MIX_SIZE:
            break
    return picks


def _seed_profile(db, user_id, now):
    """Recent downloads, favorites and liked picks, plus what the mix must leave out."""
    history = db.get_user_history(user_id, limit=40, since=now - _SEED_WINDOW_DAYS * 86400)
    if len(history) < MIX_SIZE:
        history = db.get_user_history(user_id, limit=40)
    feedback = db.mix_feedback_summary(user_id)
    favorites = db.list_favorites(user_id, limit=10)
    liked = [{"title": t, "artist": a} for t, a in feedback["liked"]]
    blocked = feedback["disliked_artists"]

    counts = Counter()
    for row in [*history, *favorites, *liked]:
        artist = (row.get("artist") or "").strip()
        if artist and artist.lower() not in blocked:
            counts[artist] += 1

    everything = db.get_user_history(user_id, limit=500)
    exclude = {_pair_key(r.get("title"), r.get("artist")) for r in everything}
    exclude |= {_pair_key(t, a) for t, a in db.recent_mix_pairs(user_id, _NO_REPEAT_DAYS, now)}
    exclude |= {_pair_key(t, a) for t, a in feedback["disliked"]}
    in_history = {_pair_key(h.get("title"), h.get("artist")) for h in history}
    return {
        "history": history + [r for r in liked if _pair_key(r["title"], r["artist"]) not in in_history],
        "artists": [a for a, _ in counts.most_common()],
        "exclude": exclude,
        "blocked": blocked,
        "avoid": [{"title": t, "artist": a} for t, a in feedback["disliked"]][:20],
    }


def _rotate(items, now, count):
    """A different slice each day so consecutive mixes don't share seeds."""
    if len(items) <= count:
        return list(items)
    day = int(now // 86400)
    start = (day * count) % len(items)
    return (items[start:] + items[:start])[:count]


async def _daily_candidates(profile, user_id, now):
    seeds = _rotate(profile["artists"][:9], now, _DAILY_SEED_ARTISTS)
    candidates = []
    for artist in seeds:
        candidates.extend(await catalog.fetch_related_tracks(artist))
    random.Random(f"{user_id}:{int(now // 86400)}").shuffle(candidates)
    picks, seen = [], set(profile["exclude"])
    for rec in candidates:
        key = _pair_key(rec.get("title"), rec.get("artist"))
        if not key[0] or key in seen or key[1] in profile["blocked"]:
            continue
        seen.add(key)
        picks.append({"title": rec["title"], "artist": rec.get("artist") or ""})
        if len(picks) >= MIX_SIZE:
            break
    return picks


async def build_mix(db, user_id, frequency="weekly", now=None):
    """Return ``(picks, releases)``. Charts are the fallback when the main source fails."""
    now = time.time() if now is None else now
    profile = _seed_profile(db, user_id, now)
    try:
        if frequency == "daily":
            picks = await _daily_candidates(profile, user_id, now)
        else:
            candidates = await _llm_candidates(
                db, user_id, profile["history"], avoid=profile["avoid"],
            )
            picks = await _resolve_picks(candidates, profile["exclude"], profile["blocked"])
    except Exception:
        logger.exception("Mix picks failed for user %s", user_id)
        picks = []
    if len(picks) < MIX_SIZE:
        taken = profile["exclude"] | {_pair_key(p["title"], p["artist"]) for p in picks}
        charts = (
            db.get_top_songs(period="week", limit=MIX_SIZE * 4)
            + db.get_top_songs(period="all", limit=MIX_SIZE * 4)
        )
        for row in charts:
            key = _pair_key(row.get("title"), row.get("artist"))
            if (len(picks) < MIX_SIZE and row.get("title") and key not in taken
                    and key[1] not in profile["blocked"]):
                taken.add(key)
                picks.append({"title": row["title"], "artist": row.get("artist") or ""})
    releases = db.recent_releases_for_user(
        user_id, days=_RELEASE_WINDOW_DAYS, limit=5,
    )
    return picks, releases


def render_mix(picks, releases, item_ids, frequency="weekly"):
    lines = [msg.t("mix_header_daily" if frequency == "daily" else "mix_header")]
    buttons = []
    for i, (pick, item_id) in enumerate(zip(picks, item_ids), 1):
        who = pick["artist"] or msg.t("unknown")
        lines.append(f"{i}. {pick['title']} — {who}")
        buttons.append([
            InlineKeyboardButton(
                f"⬇️ {i}. {pick['title']}"[:60], callback_data=f"mixpick:{item_id}",
            ),
            InlineKeyboardButton("👍", callback_data=f"mixfb:{item_id}:1"),
            InlineKeyboardButton("👎", callback_data=f"mixfb:{item_id}:-1"),
        ])
    if releases:
        lines.extend(["", msg.t("mix_new_releases")])
        lines.extend(f"• {r['artist_name']} — {r['title']}" for r in releases)
    other = "weekly" if frequency == "daily" else "daily"
    buttons.append([
        InlineKeyboardButton(msg.t(f"btn_mix_{other}"), callback_data=f"mix:{other}"),
        InlineKeyboardButton(msg.t("btn_mix_off"), callback_data="mix:off"),
    ])
    return "\n".join(lines), InlineKeyboardMarkup(buttons)


async def send_mix(bot, db, user_id, now=None):
    """Send one user's mix if it is due. Returns True when a message went out."""
    now = time.time() if now is None else now
    previous = db.claim_weekly_mix(user_id, now)
    if previous is False:
        return False
    frequency = db.get_mix_frequency(user_id)
    token = msg.use_lang(db.get_language(user_id))
    try:
        picks, releases = await build_mix(db, user_id, frequency, now=now)
        if not picks and not releases:
            return False
        item_ids = db.save_weekly_mix_items(user_id, picks, now=now)
        text, keyboard = render_mix(picks, releases, item_ids, frequency)
        await bot.send_message(chat_id=int(user_id), text=text, reply_markup=keyboard)
        db.log_event(
            "weekly_mix_sent", user_id=user_id,
            payload={"picks": len(picks), "freq": frequency},
        )
        return True
    except Forbidden:
        logger.info("Weekly mix off for user %s: bot was blocked", user_id)
        db.set_weekly_mix(user_id, False)
        return False
    except Exception:
        # Nothing reached the user, so let the next hourly run try again.
        logger.exception("Mix send failed for user %s", user_id)
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
    for user_id in db.list_weekly_mix_due(now):
        if await send_mix(bot, db, user_id, now=now):
            sent += 1
        await asyncio.sleep(0.5)
    return sent
