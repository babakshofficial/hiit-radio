"""30-second preview clips sent while the full track downloads.

Uses the Apple/Deezer preview_url already attached to metadata.
Sent as audio (not voice) to preserve quality. A preview is only posted
when the real download is taking a while — cache hits and fast downloads
cancel the timer before anything is sent.
"""

import asyncio
import logging
import os
import tempfile
from io import BytesIO

import aiohttp

import catalog
import messages as msg

logger = logging.getLogger(__name__)

PREVIEW_ENABLED = os.getenv("PREVIEW_ENABLED", "1").lower() not in ("0", "false", "no")
PREVIEW_DELAY_SEC = float(os.getenv("PREVIEW_DELAY_SEC", "4"))
PREVIEW_MAX_BYTES = 8 * 1024 * 1024


async def _fetch(url):
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            clen = resp.content_length
            if clen is not None and clen > PREVIEW_MAX_BYTES:
                return None
            data = await resp.read()
            if not data or len(data) > PREVIEW_MAX_BYTES:
                return None
            return data


def _preview_filename(url, title, artist):
    url_l = (url or "").lower()
    if ".mp3" in url_l:
        ext = "mp3"
    elif ".m4a" in url_l or ".aac" in url_l:
        ext = "m4a"
    else:
        ext = "m4a"
    safe_title = (title or "preview").replace("/", "-")[:80]
    safe_artist = (artist or "unknown").replace("/", "-")[:60]
    return f"{safe_artist} - {safe_title}.{ext}"


class PreviewSender:
    """Sends a preview clip only when the real download is taking a while."""

    def __init__(self, message, metadata, delay=None):
        self.message = message
        self.metadata = metadata
        self.delay = PREVIEW_DELAY_SEC if delay is None else delay
        self._task = None
        self._sent = None
        self._done = False

    def start(self):
        if not PREVIEW_ENABLED:
            return
        url = getattr(self.metadata, "preview_url", None)
        title = getattr(self.metadata, "title", "") or ""
        artist = getattr(self.metadata, "artist", "") or ""
        if not url and not (title and artist):
            return
        self._task = asyncio.create_task(self._run())

    async def _run(self):
        try:
            await asyncio.sleep(self.delay)
            if self._done:
                return

            title = getattr(self.metadata, "title", "") or ""
            artist = getattr(self.metadata, "artist", "") or ""
            preview_url = getattr(self.metadata, "preview_url", None)
            if title and artist:
                try:
                    deezer = await catalog.fetch_track_preview(title, artist)
                    if deezer:
                        preview_url = deezer
                except Exception:
                    pass
            if not preview_url:
                return

            data = await _fetch(preview_url)
            if not data or self._done:
                return

            caption = msg.preview_caption(title, artist)
            filename = _preview_filename(preview_url, title, artist)
            bio = BytesIO(data)
            bio.name = filename

            if self._done:
                return
            self._sent = await self.message.reply_audio(
                audio=bio,
                title=title or None,
                performer=artist or None,
                caption=caption,
            )
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.info("Preview skipped: %s", e)

    async def finish(self, delete=False):
        """Stop the delayed send. Leave any posted preview in the chat by default."""
        if self._done:
            return
        self._done = True
        task = self._task
        self._task = None
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
        if delete and self._sent is not None:
            try:
                await self._sent.delete()
            except Exception:
                pass
            self._sent = None
