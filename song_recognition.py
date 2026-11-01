"""Identify a song from a voice note or video clip.

Uses ``shazamio``, an unofficial Shazam client, so it can stop working without
notice. Every failure is reported to the caller as "not available" or "not found";
nothing here may break the rest of the bot. The clip goes to Shazam and is not kept.
"""

import asyncio
import logging
import os
import tempfile
import time
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 20 * 1024 * 1024  # Bot API getFile limit
CLIP_SECONDS = 20
RECOGNIZE_TIMEOUT_SEC = 40
RATE_LIMIT = int(os.getenv("RECOGNIZE_HOURLY_LIMIT", "10"))
_RATE_WINDOW_SEC = 3600

_recent = defaultdict(deque)
_slots = asyncio.Semaphore(2)


class RecognitionUnavailable(RuntimeError):
    """The recognizer is not installed or could not be reached."""


def within_rate_limit(user_id, now=None):
    """Record an attempt; return False once the user is over the hourly limit."""
    now = time.monotonic() if now is None else now
    attempts = _recent[str(user_id)]
    while attempts and now - attempts[0] > _RATE_WINDOW_SEC:
        attempts.popleft()
    if len(attempts) >= RATE_LIMIT:
        return False
    attempts.append(now)
    return True


async def _extract_clip(source, dest):
    """Write the first seconds of audio as mono WAV; False when there is no audio."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-nostdin", "-v", "error", "-y", "-i", source,
            "-t", str(CLIP_SECONDS), "-vn", "-ac", "1", "-ar", "16000", dest,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except FileNotFoundError as exc:
        raise RecognitionUnavailable("ffmpeg is not installed") from exc
    try:
        code = await asyncio.wait_for(proc.wait(), timeout=60)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return False
    return code == 0 and os.path.exists(dest) and os.path.getsize(dest) > 0


def parse_result(result):
    """Return ``{"title", "artist"}`` from a Shazam response, or None."""
    track = (result or {}).get("track") or {}
    title = (track.get("title") or "").strip()
    if not title:
        return None
    return {"title": title, "artist": (track.get("subtitle") or "").strip()}


async def recognize_file(path):
    """Return ``{"title", "artist"}``, or None when no song was found."""
    try:
        from shazamio import Shazam
    except ImportError as exc:
        raise RecognitionUnavailable("shazamio is not installed") from exc

    async with _slots:
        with tempfile.TemporaryDirectory(prefix="hiit_recog_") as tmp:
            clip = os.path.join(tmp, "clip.wav")
            if not await _extract_clip(path, clip):
                return None
            try:
                result = await asyncio.wait_for(
                    Shazam().recognize(clip), timeout=RECOGNIZE_TIMEOUT_SEC,
                )
            except Exception as exc:
                raise RecognitionUnavailable(str(exc)[:200]) from exc
    return parse_result(result)
