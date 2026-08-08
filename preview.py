"""30-second preview clips sent while the full track downloads.

Uses the Apple/iTunes/Spotify preview_url already attached to metadata.
A voice note is only posted when the real download is taking a while —
cache hits and fast downloads cancel the timer before anything is sent.
"""

import asyncio
import logging
import os
import subprocess
import tempfile

import aiohttp

import messages as msg

logger = logging.getLogger(__name__)

PREVIEW_ENABLED = os.getenv("PREVIEW_ENABLED", "1").lower() not in ("0", "false", "no")
PREVIEW_DELAY_SEC = float(os.getenv("PREVIEW_DELAY_SEC", "4"))
PREVIEW_MAX_BYTES = 3 * 1024 * 1024


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


def _to_opus(src_path, dest_path):
    """Telegram voice notes must be OGG/Opus; iTunes previews are AAC in m4a."""
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", src_path, "-vn", "-ac", "1", "-ar", "48000",
            "-c:a", "libopus", "-b:a", "48k", dest_path,
        ],
        check=True,
        timeout=30,
        capture_output=True,
    )


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
        if not url:
            return
        self._task = asyncio.create_task(self._run())

    async def _run(self):
        try:
            await asyncio.sleep(self.delay)
            if self._done:
                return

            data = await _fetch(self.metadata.preview_url)
            if not data or self._done:
                return

            with tempfile.TemporaryDirectory(prefix="hiit_preview_") as tmp:
                src = os.path.join(tmp, "preview.m4a")
                dest = os.path.join(tmp, "preview.ogg")
                with open(src, "wb") as f:
                    f.write(data)
                try:
                    await asyncio.to_thread(_to_opus, src, dest)
                except Exception as e:
                    logger.info("Preview convert failed: %s", e)
                    return
                if self._done or not os.path.exists(dest):
                    return

                title = getattr(self.metadata, "title", "") or ""
                artist = getattr(self.metadata, "artist", "") or ""
                caption = msg.preview_caption(title, artist)
                with open(dest, "rb") as voice:
                    self._sent = await self.message.reply_voice(
                        voice=voice,
                        caption=caption,
                    )
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.info("Preview skipped: %s", e)

    async def finish(self, delete=True):
        """Stop the delayed send. delete=True removes a preview that already posted."""
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
