"""Fetch lyrics from LRCLIB, Genius, or Musixmatch."""

import logging
import os
import re

import aiohttp

logger = logging.getLogger(__name__)

GENIUS_TOKEN = os.getenv("GENIUS_API_TOKEN", "").strip()
MUSIXMATCH_KEY = os.getenv("MUSIXMATCH_API_KEY", "").strip()


def _parse_lrc(lrc_text):
    """Return (plain_text, synced_lines) where synced_lines is list of (ms, text)."""
    if not lrc_text:
        return None, None
    lines = []
    plain_parts = []
    for line in lrc_text.splitlines():
        m = re.match(r"\[(\d+):(\d+\.?\d*)\](.*)", line.strip())
        if m:
            mins, secs, text = m.groups()
            ms = int(float(mins) * 60 * 1000 + float(secs) * 1000)
            text = text.strip()
            if text:
                lines.append((ms, text))
                plain_parts.append(text)
        elif line.strip() and not line.startswith("["):
            plain_parts.append(line.strip())
    plain = "\n".join(plain_parts) if plain_parts else None
    return plain, lines if lines else None


async def fetch_lyrics(title, artist, duration_sec=None):
    """Return dict with keys: text (str), synced (list of (ms,text)|None), source (str)."""
    if not title:
        return None

    result = await _fetch_lrclib(title, artist, duration_sec)
    if result:
        return result

    if GENIUS_TOKEN:
        result = await _fetch_genius(title, artist)
        if result:
            return result

    if MUSIXMATCH_KEY:
        result = await _fetch_musixmatch(title, artist)
        if result:
            return result

    return None


async def _fetch_lrclib(title, artist, duration_sec=None):
    params = {"track_name": title, "artist_name": artist or ""}
    if duration_sec:
        params["duration"] = int(duration_sec)
    url = "https://lrclib.net/api/get"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
        synced_lrc = data.get("syncedLyrics") or data.get("synced_lyrics")
        plain = data.get("plainLyrics") or data.get("plain_lyrics")
        if synced_lrc:
            text, synced = _parse_lrc(synced_lrc)
            return {"text": text or plain, "synced": synced, "source": "lrclib"}
        if plain:
            return {"text": plain, "synced": None, "source": "lrclib"}
    except Exception as e:
        logger.debug(f"LRCLIB fetch failed: {e}")
    return None


async def _fetch_genius(title, artist):
    headers = {"Authorization": f"Bearer {GENIUS_TOKEN}"}
    query = f"{title} {artist}".strip()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.genius.com/search",
                params={"q": query},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
        hits = data.get("response", {}).get("hits", [])
        if not hits:
            return None
        song_path = hits[0]["result"].get("path")
        if not song_path:
            return None
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://genius.com{song_path}",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    return None
                html = await resp.text()
        # Minimal scrape: lyrics container
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        container = soup.select_one('[data-lyrics-container="true"]')
        if not container:
            return None
        text = container.get_text("\n").strip()
        if text:
            return {"text": text, "synced": None, "source": "genius"}
    except Exception as e:
        logger.debug(f"Genius fetch failed: {e}")
    return None


async def _fetch_musixmatch(title, artist):
    params = {
        "apikey": MUSIXMATCH_KEY,
        "q_track": title,
        "q_artist": artist or "",
        "s_track_rating": "desc",
        "page_size": 1,
        "page": 1,
        "format": "json",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.musixmatch.com/ws/1.1/matcher.lyrics.get",
                params=params,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
        body = data.get("message", {}).get("body", {})
        lyrics = body.get("lyrics", {}).get("lyrics_body", "")
        if lyrics and lyrics.strip() and "***" not in lyrics[:20]:
            return {"text": lyrics.strip(), "synced": None, "source": "musixmatch"}
    except Exception as e:
        logger.debug(f"Musixmatch fetch failed: {e}")
    return None
