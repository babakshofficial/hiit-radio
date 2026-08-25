"""Background job: check Deezer for new releases from followed artists."""

import asyncio
import logging
import time
from datetime import datetime, timezone

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import catalog
import messages as msg

logger = logging.getLogger(__name__)

_BATCH_SLEEP = 1.5  # seconds between Deezer API calls per artist
# Never alert for catalog entries older than this (guards first-follow floods).
_MAX_RELEASE_AGE_DAYS = 60


def _parse_release_ts(release_date: str):
    """Parse Deezer YYYY-MM-DD (or YYYY-MM / YYYY) to unix seconds, or None."""
    raw = (release_date or "").strip()
    if not raw:
        return None
    for fmt, n in (("%Y-%m-%d", 10), ("%Y-%m", 7), ("%Y", 4)):
        try:
            dt = datetime.strptime(raw[:n], fmt)
            return dt.replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            continue
    return None


def _release_too_old(release_date: str, *, now: float | None = None) -> bool:
    ts = _parse_release_ts(release_date)
    if ts is None:
        return False
    now = now if now is not None else time.time()
    return (now - ts) > (_MAX_RELEASE_AGE_DAYS * 86400)


async def seed_artist_releases(db, artist_id, *, limit=10):
    """Mark current catalog albums as already seen (no user notifications)."""
    try:
        albums = await catalog.fetch_artist_latest_albums(artist_id, limit=limit)
    except Exception as exc:
        logger.warning("Release seed: Deezer error for artist %s: %s", artist_id, exc)
        return 0
    seeded = 0
    for album in albums:
        album_id = str(album.get("id", ""))
        if not album_id:
            continue
        db.mark_release_notified(
            artist_id,
            album_id,
            album.get("title") or "",
            album.get("release_date") or "",
        )
        seeded += 1
    if seeded:
        logger.info("Release seed: artist %s marked %d albums as known", artist_id, seeded)
    return seeded


async def check_new_releases(bot, db):
    """Poll Deezer for new albums from every followed artist and notify followers."""
    artist_ids = db.get_all_followed_artist_ids()
    if not artist_ids:
        return
    logger.info("Release check: scanning %d followed artists", len(artist_ids))
    notified_total = 0
    now = time.time()

    for artist_id in artist_ids:
        try:
            albums = await catalog.fetch_artist_latest_albums(artist_id, limit=5)
        except Exception as exc:
            logger.warning("Release check: Deezer error for artist %s: %s", artist_id, exc)
            await asyncio.sleep(_BATCH_SLEEP)
            continue

        # First time we see this artist in the releases table: baseline only.
        if not db.has_release_baseline(artist_id):
            for album in albums:
                album_id = str(album.get("id", ""))
                if not album_id:
                    continue
                db.mark_release_notified(
                    artist_id,
                    album_id,
                    album.get("title") or "",
                    album.get("release_date") or "",
                )
            logger.info(
                "Release check: baselined %d albums for artist %s (no spam)",
                len(albums), artist_id,
            )
            await asyncio.sleep(_BATCH_SLEEP)
            continue

        for album in albums:
            album_id = str(album.get("id", ""))
            if not album_id:
                continue
            if db.is_release_notified(artist_id, album_id):
                continue

            title = album.get("title") or "آلبوم جدید"
            release_date = album.get("release_date") or ""
            link = album.get("link") or f"https://www.deezer.com/album/{album_id}"

            # Stale catalog entry — remember it, don't ping users.
            if _release_too_old(release_date, now=now):
                db.mark_release_notified(artist_id, album_id, title, release_date)
                logger.debug(
                    "Release check: skip old album %s (%s) for artist %s",
                    title, release_date, artist_id,
                )
                continue

            artist_name = album.get("artist", {}).get("name") or ""
            if not artist_name:
                try:
                    info = await catalog.fetch_artist(artist_id)
                    artist_name = info.get("name") or "هنرمند"
                except Exception:
                    artist_name = "هنرمند"

            release_ts = _parse_release_ts(release_date)
            followers = db.get_followers(artist_id)
            text = msg.new_release_notification(artist_name, title, release_date)
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    f"💿 {title[:28]}",
                    callback_data=f"newrel:{link[:50]}",
                )],
                [InlineKeyboardButton(
                    msg.t("menu_back"),
                    callback_data="menu:back",
                )],
            ])

            sent = 0
            for user_id, followed_at in followers:
                # Only notify users who followed before (or around) this release.
                if release_ts is not None and followed_at is not None:
                    try:
                        followed_at_f = float(followed_at)
                    except (TypeError, ValueError):
                        followed_at_f = 0.0
                    # Album clearly predates the follow — skip this user.
                    if release_ts < followed_at_f - 86400:
                        continue
                try:
                    await bot.send_message(
                        chat_id=int(user_id), text=text, reply_markup=keyboard,
                    )
                    sent += 1
                except Exception as exc:
                    logger.debug("Release notify failed user=%s: %s", user_id, exc)

            db.mark_release_notified(artist_id, album_id, title, release_date)
            if sent:
                notified_total += 1
                logger.info(
                    "New release notified: %s — %s (%d followers)",
                    artist_name, title, sent,
                )

        await asyncio.sleep(_BATCH_SLEEP)

    if notified_total:
        logger.info("Release check done: %d new releases notified", notified_total)
