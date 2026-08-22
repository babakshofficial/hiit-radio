"""Background job: check Deezer for new releases from followed artists."""

import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import catalog
import messages as msg

logger = logging.getLogger(__name__)

_BATCH_SLEEP = 1.5  # seconds between Deezer API calls per artist


async def check_new_releases(bot, db):
    """Poll Deezer for new albums from every followed artist and notify followers."""
    artist_ids = db.get_all_followed_artist_ids()
    if not artist_ids:
        return
    logger.info("Release check: scanning %d followed artists", len(artist_ids))
    notified_total = 0

    for artist_id in artist_ids:
        try:
            albums = await catalog.fetch_artist_latest_albums(artist_id, limit=5)
        except Exception as exc:
            logger.warning("Release check: Deezer error for artist %s: %s", artist_id, exc)
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
            artist_name = album.get("artist", {}).get("name") or ""
            if not artist_name:
                try:
                    info = await catalog.fetch_artist(artist_id)
                    artist_name = info.get("name") or "هنرمند"
                except Exception:
                    artist_name = "هنرمند"

            followers = db.get_followers(artist_id)
            text = msg.new_release_notification(artist_name, title, release_date)
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    f"💿 دانلود آلبوم «{title[:24]}»",
                    callback_data=f"newrel:{link[:50]}",
                )],
            ])

            for user_id in followers:
                try:
                    await bot.send_message(
                        chat_id=int(user_id), text=text, reply_markup=keyboard,
                    )
                except Exception as exc:
                    logger.debug("Release notify failed user=%s: %s", user_id, exc)

            db.mark_release_notified(artist_id, album_id, title, release_date)
            notified_total += 1
            logger.info(
                "New release notified: %s — %s (%d followers)",
                artist_name, title, len(followers),
            )

        await asyncio.sleep(_BATCH_SLEEP)

    if notified_total:
        logger.info("Release check done: %d new releases notified", notified_total)
