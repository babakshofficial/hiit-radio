"""30-second preview clips sent while the full track downloads.

Uses the Apple/Deezer preview_url already attached to metadata.
Converted to high-quality Opus and sent as a Telegram voice message,
with the watermarked cover attached as a photo (voice API has no thumbnail).
A preview is only posted when the real download is taking a while —
cache hits and fast downloads cancel the timer before anything is sent.
"""

import asyncio
import logging
import os
import subprocess
import tempfile
from io import BytesIO

import aiohttp
import requests
from PIL import Image

import catalog
import messages as msg
from metadata import _normalize_apple_artwork_url

logger = logging.getLogger(__name__)

PREVIEW_ENABLED = os.getenv("PREVIEW_ENABLED", "1").lower() not in ("0", "false", "no")
PREVIEW_DELAY_SEC = float(os.getenv("PREVIEW_DELAY_SEC", "4"))
PREVIEW_MAX_BYTES = 8 * 1024 * 1024
# High-quality Opus for music-like previews (Telegram voice is OGG/Opus).
PREVIEW_OPUS_BITRATE = os.getenv("PREVIEW_OPUS_BITRATE", "160k").strip() or "160k"


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


def _to_opus_ogg(audio_bytes: bytes) -> bytes | None:
    """Transcode preview bytes to high-quality OGG Opus for sendVoice."""
    if not audio_bytes:
        return None
    src_path = out_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as src:
            src.write(audio_bytes)
            src_path = src.name
        out_fd, out_path = tempfile.mkstemp(suffix=".ogg")
        os.close(out_fd)
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", src_path,
            "-c:a", "libopus",
            "-b:a", PREVIEW_OPUS_BITRATE,
            "-vbr", "on",
            "-application", "audio",
            "-f", "ogg",
            out_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, timeout=60)
        if proc.returncode != 0 or not os.path.exists(out_path):
            err = (proc.stderr or b"").decode("utf-8", errors="ignore")[:200]
            logger.debug("ffmpeg opus failed: %s", err)
            return None
        with open(out_path, "rb") as f:
            data = f.read()
        return data or None
    except Exception as e:
        logger.debug("Opus convert failed: %s", e)
        return None
    finally:
        for path in (src_path, out_path):
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass


def _fetch_artwork_bytes(metadata, music_downloader):
    """Download + watermark cover JPEG for the preview photo, or None."""
    if not music_downloader:
        return None
    urls = []
    primary = getattr(metadata, "artwork_url", None)
    if primary:
        normalized = _normalize_apple_artwork_url(primary)
        urls.append(normalized)
        if primary != normalized:
            urls.append(primary)
    title = getattr(metadata, "title", "") or ""
    artist = getattr(metadata, "artist", "") or ""
    fallback = music_downloader._itunes_artwork_url(title, artist)
    if fallback and fallback not in urls:
        urls.append(fallback)

    for art_url in urls:
        try:
            response = requests.get(
                art_url,
                timeout=12,
                headers=music_downloader._artwork_headers(art_url),
            )
            if response.status_code != 200 or not response.content:
                continue
            try:
                probe = Image.open(BytesIO(response.content))
                pw, ph = probe.size
                if pw > 0 and ph > 0 and (pw / ph > 1.25 or ph / pw > 1.25):
                    continue
            except Exception:
                pass
            processed = music_downloader._process_cover_artwork(response.content)
            if processed:
                return processed
        except Exception as e:
            logger.debug("Preview artwork fetch failed (%s): %s", (art_url or "")[:60], e)
    return None


def _photo_bio(jpeg_bytes):
    if not jpeg_bytes:
        return None
    bio = BytesIO(jpeg_bytes)
    bio.name = "cover.jpg"
    return bio


class PreviewSender:
    """Sends a HQ voice preview only when the real download is taking a while."""

    def __init__(self, message, metadata, delay=None, music_downloader=None):
        self.message = message
        self.metadata = metadata
        self.delay = PREVIEW_DELAY_SEC if delay is None else delay
        self.music_downloader = music_downloader
        self._task = None
        self._sent = []  # photo and/or voice messages to delete on finish(delete=True)
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

            opus = await asyncio.to_thread(_to_opus_ogg, data)
            if not opus or self._done:
                return

            caption = msg.preview_caption(title, artist)
            cover = None
            try:
                cover = await asyncio.to_thread(
                    _fetch_artwork_bytes, self.metadata, self.music_downloader,
                )
            except Exception as e:
                logger.debug("Preview artwork skipped: %s", e)

            if self._done:
                return

            voice_bio = BytesIO(opus)
            voice_bio.name = "preview.ogg"

            # Voice notes can't carry a thumbnail — send cover as a photo first,
            # then the voice message as a reply so they stay linked in the chat.
            photo_msg = None
            photo = _photo_bio(cover)
            if photo is not None:
                try:
                    photo_msg = await self.message.reply_photo(
                        photo=photo,
                        caption=caption,
                    )
                    self._sent.append(photo_msg)
                except Exception as e:
                    logger.debug("Preview photo failed: %s", e)
                    photo_msg = None

            if self._done:
                return

            voice_kwargs = {"voice": voice_bio}
            if photo_msg is None:
                voice_kwargs["caption"] = caption
            try:
                if photo_msg is not None:
                    voice_msg = await photo_msg.reply_voice(**voice_kwargs)
                else:
                    voice_msg = await self.message.reply_voice(**voice_kwargs)
                self._sent.append(voice_msg)
            except Exception as e:
                logger.info("Preview voice failed: %s", e)
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
        if delete and self._sent:
            for m in self._sent:
                try:
                    await m.delete()
                except Exception:
                    pass
            self._sent = []
