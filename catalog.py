"""Multi-catalog search and URL resolution (Deezer, YouTube, SoundCloud + iTunes)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Callable, Optional
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import yt_dlp

from metadata import AppleMusicMetadata, TrackMetadata

logger = logging.getLogger(__name__)

_DEEZER_API = "https://api.deezer.com"
_DEEZER_URL_RE = re.compile(
    r"deezer\.com/(?:[a-z]{2}/)?(track|album|playlist)/(\d+)"
)
_YOUTUBE_RE = re.compile(
    r"(?:music\.|www\.|m\.)?(?:youtube\.com/(?:watch\?|playlist\?)|youtu\.be/)"
)
_SOUNDCLOUD_RE = re.compile(r"(?:www\.|m\.|on\.)?soundcloud\.com/")

_SOURCE_WEIGHT = {"deezer": 1.0, "apple": 0.97, "soundcloud": 0.9, "youtube": 0.87}


class CatalogError(Exception):
    """User-facing catalog error."""


@dataclass
class CatalogHit:
    kind: str  # track | album | playlist | artist
    id: str
    name: str
    subtitle: str
    url: str
    source: str
    cover_url: Optional[str] = None


def is_deezer_url(url: str) -> bool:
    return bool(_DEEZER_URL_RE.search(url or ""))


def is_youtube_url(url: str) -> bool:
    return bool(_YOUTUBE_RE.search(url or ""))


def is_soundcloud_url(url: str) -> bool:
    return bool(_SOUNDCLOUD_RE.search(url or ""))


def is_direct_media_url(url: str) -> bool:
    return is_youtube_url(url) or is_soundcloud_url(url)


def is_collection_url(url: str) -> bool:
    text = (url or "").strip()
    if is_deezer_url(text):
        m = _DEEZER_URL_RE.search(text)
        return bool(m and m.group(1) in ("album", "playlist"))
    if is_youtube_url(text) and ("list=" in text or "/playlist" in text):
        return True
    if is_soundcloud_url(text) and ("/sets/" in text or "/albums/" in text):
        return True
    return False


def _deezer_get(path: str, **params) -> dict:
    url = f"{_DEEZER_API}{path}"
    if params:
        url += "?" + urlencode(params)
    try:
        with urlopen(Request(url), timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except URLError as exc:
        raise CatalogError(f"دسترسی به Deezer ممکن نشد: {exc.reason}") from exc
    if isinstance(data, dict) and data.get("error"):
        message = data["error"].get("message", "خطای ناشناخته")
        raise CatalogError(f"Deezer: {message}")
    return data


def _deezer_track_meta(item: dict, url: str = "", album_name: str = "") -> TrackMetadata:
    meta = TrackMetadata()
    meta.title = item.get("title")
    meta.artist = (item.get("artist") or {}).get("name")
    album = item.get("album") or {}
    meta.album = album.get("title") or album_name or None
    meta.artwork_url = album.get("cover_big") or item.get("album", {}).get("cover_big")
    if item.get("duration"):
        meta.duration = float(item["duration"])
    meta.preview_url = item.get("preview")
    meta.id = str(item.get("id", ""))
    meta.url = url or item.get("link") or f"https://www.deezer.com/track/{meta.id}"
    meta.type = "track"
    return meta


def _deezer_resolve_sync(url: str) -> tuple[Optional[str], list[TrackMetadata]]:
    match = _DEEZER_URL_RE.search(url)
    if not match:
        raise CatalogError("لینک Deezer نامعتبر است.")
    kind, deezer_id = match.group(1), match.group(2)

    if kind == "track":
        item = _deezer_get(f"/track/{deezer_id}")
        track = _deezer_track_meta(item, url=url)
        return track.title, [track]

    if kind == "album":
        album = _deezer_get(f"/album/{deezer_id}")
        name = album.get("title") or "آلبوم"
        tracks = []
        for item in (album.get("tracks") or {}).get("data") or []:
            tracks.append(_deezer_track_meta(item, album_name=name))
        return name, tracks

    playlist = _deezer_get(f"/playlist/{deezer_id}")
    name = playlist.get("title") or "پلی‌لیست"
    items = list((playlist.get("tracks") or {}).get("data") or [])
    next_url = (playlist.get("tracks") or {}).get("next")
    while next_url:
        page = json.loads(urlopen(Request(next_url), timeout=15).read().decode())
        items.extend(page.get("data") or [])
        next_url = page.get("next")
    tracks = [_deezer_track_meta(item) for item in items if item]
    return name, tracks


def _squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _relevance(hit: CatalogHit, query: str) -> float:
    q = _squash(query)
    name = _squash(hit.name)
    both = f"{name} {_squash(hit.subtitle)}".strip()
    score = max(
        SequenceMatcher(None, q, name).ratio(),
        SequenceMatcher(None, q, both).ratio(),
    )
    if name == q:
        score = 1.0
    elif name.startswith(q):
        score = max(score, 0.93)
    elif q in name:
        score = max(score, 0.86)
    return score * _SOURCE_WEIGHT.get(hit.source, 0.85)


def _deezer_search_sync(query: str, limit: int = 8) -> list[CatalogHit]:
    hits: list[CatalogHit] = []
    for kind, path in (
        ("track", "/search/track"),
        ("album", "/search/album"),
        ("artist", "/search/artist"),
        ("playlist", "/search/playlist"),
    ):
        per_kind = max(2, limit // 4)
        try:
            data = _deezer_get(path, q=query, limit=per_kind)
        except CatalogError:
            continue
        for item in data.get("data") or []:
            if kind == "track":
                hits.append(CatalogHit(
                    kind="track",
                    id=str(item["id"]),
                    name=item.get("title", ""),
                    subtitle=(item.get("artist") or {}).get("name", ""),
                    url=item.get("link", ""),
                    source="deezer",
                    cover_url=(item.get("album") or {}).get("cover_medium"),
                ))
            elif kind == "album":
                artist = (item.get("artist") or {}).get("name", "")
                year = (item.get("release_date") or "")[:4]
                hits.append(CatalogHit(
                    kind="album",
                    id=str(item["id"]),
                    name=item.get("title", ""),
                    subtitle=" · ".join(p for p in (artist, year) if p),
                    url=item.get("link", ""),
                    source="deezer",
                    cover_url=item.get("cover_medium"),
                ))
            elif kind == "artist":
                hits.append(CatalogHit(
                    kind="artist",
                    id=str(item["id"]),
                    name=item.get("name", ""),
                    subtitle=f"{item.get('nb_album', '')} آلبوم",
                    url=item.get("link", ""),
                    source="deezer",
                    cover_url=item.get("picture_medium"),
                ))
            else:
                owner = (item.get("creator") or {}).get("name", "")
                hits.append(CatalogHit(
                    kind="playlist",
                    id=str(item["id"]),
                    name=item.get("title", ""),
                    subtitle=f"توسط {owner}" if owner else "",
                    url=item.get("link", ""),
                    source="deezer",
                    cover_url=item.get("picture_medium"),
                ))
    return hits


def _ytdlp_resolve_sync(url: str, ydl_opts: dict) -> tuple[Optional[str], list[TrackMetadata]]:
    opts = {
        **ydl_opts,
        "extract_flat": "in_playlist",
        "skip_download": True,
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    if not info:
        raise CatalogError("صفحه قابل خواندن نیست.")

    def _from_entry(entry: dict, album: str = "", idx: int = 0) -> TrackMetadata:
        title = entry.get("title") or "Unknown"
        artist = (
            entry.get("artist")
            or entry.get("uploader")
            or entry.get("channel")
            or "Unknown"
        )
        if " - " in title:
            left, right = title.split(" - ", 1)
            if left.strip() and right.strip():
                artist, title = left.strip(), right.strip()
        meta = TrackMetadata()
        meta.title = title
        meta.artist = artist
        meta.album = album or None
        meta.duration = float(entry.get("duration") or 0) or None
        meta.id = str(entry.get("id") or idx)
        meta.url = entry.get("webpage_url") or entry.get("url") or url
        meta.source_url = meta.url
        meta.type = "track"
        thumbs = entry.get("thumbnails") or []
        if entry.get("thumbnail"):
            meta.artwork_url = entry["thumbnail"]
        elif thumbs:
            meta.artwork_url = max(thumbs, key=lambda t: t.get("width") or 0).get("url")
        return meta

    if info.get("_type") == "playlist" or info.get("entries"):
        entries = [e for e in (info.get("entries") or []) if e]
        if not entries:
            raise CatalogError("پلی‌لیست خالی یا خصوصی است.")
        name = re.sub(
            r"\s*\((?:All|Tracks|Popular tracks)\)$",
            "",
            info.get("title") or "مجموعه",
        ).strip()
        tracks = [_from_entry(e, album=name, idx=i) for i, e in enumerate(entries, 1)]
        return name, tracks

    track = _from_entry(info)
    return track.title, [track]


def _deezer_artist_sync(artist_id: str) -> dict:
    profile = _deezer_get(f"/artist/{artist_id}")
    top = _deezer_get(f"/artist/{artist_id}/top", limit=10)
    albums_page = _deezer_get(f"/artist/{artist_id}/albums", limit=50)
    albums = list(albums_page.get("data") or [])
    next_url = albums_page.get("next")
    while next_url:
        page = json.loads(urlopen(Request(next_url), timeout=15).read().decode())
        albums.extend(page.get("data") or [])
        next_url = page.get("next")
    return {
        "name": profile.get("name", ""),
        "top": [_deezer_track_meta(i) for i in top.get("data") or []],
        "albums": albums,
    }


async def resolve_url(url: str, ydl_opts_factory: Callable[[], dict]) -> tuple[Optional[str], list[TrackMetadata]]:
    text = (url or "").strip()
    if is_deezer_url(text):
        return await asyncio.to_thread(_deezer_resolve_sync, text)
    if is_direct_media_url(text):
        opts = ydl_opts_factory()
        return await asyncio.to_thread(_ytdlp_resolve_sync, text, opts)
    return None, []


async def search_all(query: str, limit: int = 12) -> list[CatalogHit]:
    query = (query or "").strip()
    if len(query) < 2:
        return []

    deezer_task = asyncio.create_task(asyncio.to_thread(_deezer_search_sync, query, limit))
    apple_hits: list[CatalogHit] = []
    try:
        apple_results = await AppleMusicMetadata.search_many(query, limit=limit)
        for r in apple_results:
            apple_hits.append(CatalogHit(
                kind="track",
                id=str(r.id or abs(hash(f"{r.title}{r.artist}"))),
                name=r.title or "",
                subtitle=r.artist or "",
                url=r.url or "",
                source="apple",
                cover_url=getattr(r, "artwork_url", None),
            ))
    except Exception as exc:
        logger.warning("Apple search failed: %s", exc)

    deezer_hits = await deezer_task

    merged: list[CatalogHit] = []
    seen: set[str] = set()
    for hit in deezer_hits + apple_hits:
        key = f"{hit.kind}:{_squash(hit.name)}:{_squash(hit.subtitle.split('·')[0])}"
        if key in seen:
            continue
        seen.add(key)
        merged.append(hit)

    merged.sort(key=lambda h: _relevance(h, query), reverse=True)
    return merged[:limit]


def hit_to_track_metadata(hit: CatalogHit) -> TrackMetadata:
    if hit.kind != "track":
        raise ValueError("not a track hit")
    meta = TrackMetadata()
    meta.title = hit.name
    meta.artist = hit.subtitle.split("·")[0].strip() if hit.subtitle else None
    meta.url = hit.url
    meta.id = hit.id
    meta.type = "track"
    meta.artwork_url = hit.cover_url
    if hit.source in ("youtube", "soundcloud"):
        meta.source_url = hit.url
    return meta


def _deezer_artist_latest_albums(artist_id: str, limit: int = 5) -> list[dict]:
    """Fetch the most recent albums sorted by release_date desc."""
    data = _deezer_get(f"/artist/{artist_id}/albums", limit=limit, order="DATE")
    return data.get("data") or []


async def fetch_artist(artist_id: str) -> dict:
    return await asyncio.to_thread(_deezer_artist_sync, artist_id)


async def fetch_artist_latest_albums(artist_id: str, limit: int = 5) -> list[dict]:
    return await asyncio.to_thread(_deezer_artist_latest_albums, artist_id, limit)
