"""Strict classification and allowlisted fetching of user-supplied music links.

User text must never reach an HTTP client or yt-dlp because it merely *contains*
a music hostname: ``http://127.0.0.1/x?music.apple.com`` is not an Apple link.
Hosts are compared exactly, after parsing, and re-checked on every redirect.
"""

import re
from urllib.parse import urljoin, urlsplit

APPLE_MUSIC_HOSTS = frozenset({
    "music.apple.com", "geo.music.apple.com", "embed.music.apple.com",
})
SHAZAM_DOMAINS = ("shazam.com", "shz.am")
YOUTUBE_HOSTS = frozenset({
    "youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
})
YOUTU_BE_HOSTS = frozenset({"youtu.be", "www.youtu.be"})
SOUNDCLOUD_HOSTS = frozenset({
    "soundcloud.com", "www.soundcloud.com", "m.soundcloud.com", "on.soundcloud.com",
})

# yt-dlp only ever needs these. Excluding its generic extractor means an
# unexpected URL fails with "unsupported" instead of being fetched.
YTDLP_ALLOWED_EXTRACTORS = ["youtube.*", "soundcloud.*"]

MAX_PAGE_BYTES = 8 * 1024 * 1024
MAX_REDIRECTS = 5

_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)
_URL_TOKEN_RE = re.compile(r"(?:https?://)?[^\s<>\"'()\[\]{}]+", re.IGNORECASE)
_BAD_NETLOC_RE = re.compile(r"[\s\\\x00-\x1f\x7f]")
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


class DisallowedUrl(ValueError):
    """A fetch or redirect pointed outside the allowlist."""


class ResponseTooLarge(ValueError):
    """A remote page exceeded ``MAX_PAGE_BYTES``."""


def _parse(candidate):
    """Return ``(normalized_url, SplitResult)`` for a safe http(s) URL, else None."""
    url = (candidate or "").strip()
    if not url or re.search(r"[\x00-\x1f\x7f]", url):
        return None
    if not _SCHEME_RE.match(url):
        url = f"https://{url}"
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return None
    if parts.scheme.lower() not in ("http", "https"):
        return None
    if _BAD_NETLOC_RE.search(parts.netloc) or "@" in parts.netloc:
        return None
    if port not in (None, 80, 443) or not parts.hostname:
        return None
    return url, parts


def _host(parts):
    return (parts.hostname or "").lower().rstrip(".")


def _is_apple(parts):
    return _host(parts) in APPLE_MUSIC_HOSTS


def _is_shazam(parts):
    host = _host(parts)
    return any(host == d or host.endswith(f".{d}") for d in SHAZAM_DOMAINS)


def _is_youtube(parts):
    host = _host(parts)
    if host in YOUTU_BE_HOSTS:
        return len(parts.path) > 1
    if host in YOUTUBE_HOSTS:
        return parts.path.rstrip("/") in ("/watch", "/playlist") and bool(parts.query)
    return False


def _is_soundcloud(parts):
    return _host(parts) in SOUNDCLOUD_HOSTS and len(parts.path) > 1


def _find(text, predicate):
    """Return the URL in ``text`` that satisfies ``predicate``, else None.

    A message that is one URL is returned whole, because Shazam links can carry
    spaces in their JSON fragment. Otherwise share text ("I found X with Shazam:
    https://...") is searched token by token.
    """
    whole = _parse(text)
    if whole and predicate(whole[1]):
        return whole[0]
    for match in _URL_TOKEN_RE.finditer(text or ""):
        token = match.group(0).rstrip(".,;:!?")
        parsed = _parse(token)
        if parsed and predicate(parsed[1]):
            return parsed[0]
    return None


def find_apple_music_url(text):
    return _find(text, _is_apple)


def find_shazam_url(text):
    return _find(text, _is_shazam)


def find_youtube_url(text):
    return _find(text, _is_youtube)


def find_soundcloud_url(text):
    return _find(text, _is_soundcloud)


def find_direct_media_url(text):
    return find_youtube_url(text) or find_soundcloud_url(text)


def is_apple_music_page(url):
    parsed = _parse(url)
    return bool(parsed and _is_apple(parsed[1]))


def is_shazam_page(url):
    parsed = _parse(url)
    return bool(parsed and _is_shazam(parsed[1]))


def is_soundcloud_page(url):
    parsed = _parse(url)
    return bool(parsed and _host(parsed[1]) in SOUNDCLOUD_HOSTS)


async def fetch_allowed(session, url, is_allowed, *, headers=None, max_bytes=MAX_PAGE_BYTES):
    """GET ``url``, following redirects only while ``is_allowed`` accepts them.

    Returns ``(status, final_url, text)``. Raises ``DisallowedUrl`` before
    contacting a rejected host, and ``ResponseTooLarge`` past ``max_bytes``.
    """
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        if not is_allowed(current):
            raise DisallowedUrl("URL host is not allowed")
        async with session.get(current, headers=headers, allow_redirects=False) as resp:
            location = resp.headers.get("Location")
            if resp.status in _REDIRECT_STATUSES and location:
                current = urljoin(str(resp.url), location)
                continue
            received = bytearray()
            async for chunk in resp.content.iter_chunked(64 * 1024):
                received.extend(chunk)
                if len(received) > max_bytes:
                    raise ResponseTooLarge(f"response exceeded {max_bytes} bytes")
            text = bytes(received).decode(resp.charset or "utf-8", errors="replace")
            return resp.status, str(resp.url), text
    raise DisallowedUrl("too many redirects")
