import os
import re
import time
import threading
import subprocess
import sys
import yt_dlp
import logging
import asyncio
import json
import difflib
from mutagen.mp3 import MP3 as MutagenMP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, USLT, SYLT, TXXX
import requests
from PIL import Image, ImageFilter, ImageChops
import io

from metadata import score_query_coverage

logger = logging.getLogger(__name__)

QUALITIES = ("128", "192", "256", "320", "original")
DEFAULT_QUALITY = "256"

# Soft signals that a YouTube cookie jar was exported while signed in.
_YT_AUTH_COOKIE_NAMES = (
    "LOGIN_INFO",
    "SAPISID",
    "APISID",
    "__Secure-1PAPISID",
    "__Secure-3PAPISID",
)
# Session cookies yt-dlp needs to pass the bot check (any one is enough).
_YT_SESSION_COOKIE_NAMES = (
    "SID",
    "__Secure-1PSID",
    "__Secure-3PSID",
)
# Legacy tuple kept for messages that reference the old combined list.
_YT_AUTH_HINT_NAMES = _YT_AUTH_COOKIE_NAMES

# web_safari + ejs:github pass YouTube bot-checks in 2026; android skips cookie auth.
_YT_PLAYER_CLIENTS = ["web_safari", "web", "tv"]
# Prefer short, widely available videos for live auth probes. Some IDs bot-check
# via proxy while normal track downloads still succeed — try several.
_DEFAULT_PROBE_URLS = (
    "https://www.youtube.com/watch?v=BaW_jenozKc",
    "https://www.youtube.com/watch?v=jNQXAC9IVRw",
)

# Representative music video for health / auth checks (override via YTDLP_HEALTH_PROBE_URL).
_HEALTH_PROBE_URL = os.getenv(
    "YTDLP_HEALTH_PROBE_URL",
    "https://www.youtube.com/watch?v=MO4cP8zsgY0",
).strip()


def _probe_urls():
    explicit = os.getenv("YTDLP_PROBE_URL", "").strip()
    if explicit:
        return (explicit,)
    extra = os.getenv("YTDLP_PROBE_URLS", "").strip()
    if extra:
        return tuple(u.strip() for u in extra.split(",") if u.strip())
    return _DEFAULT_PROBE_URLS


_YT_PROBE_URL = _DEFAULT_PROBE_URLS[-1]  # legacy single-URL callers
_PROBE_TTL_SEC = 600
_PROBE_CACHE = {"monotonic": 0.0, "ok": False, "detail": ""}
# Chrome cookie DB + keyring decrypt fails when multiple yt-dlp instances run at once.
_YTDLP_LOCK = threading.Lock()
_ACTIVE_DOWNLOADS = 0


def downloads_in_progress():
    return _ACTIVE_DOWNLOADS > 0


def _yt_proxy_url():
    """Optional SOCKS/HTTP proxy for yt-dlp (``YTDLP_PROXY`` env var)."""
    return os.getenv("YTDLP_PROXY", "").strip()


def _yt_proxy_endpoint():
    """Return ``(host, port)`` for the configured SOCKS proxy, if any."""
    from urllib.parse import urlparse

    proxy = _yt_proxy_url()
    if not proxy:
        return None
    parsed = urlparse(proxy)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (1080 if "socks" in (parsed.scheme or "") else 8080)
    return host, port


def _wait_for_yt_proxy(timeout=90):
    """Block until ``YTDLP_PROXY`` accepts connections (optional startup wait)."""
    endpoint = _yt_proxy_endpoint()
    if not endpoint:
        return True
    host, port = endpoint
    deadline = time.monotonic() + max(5, timeout)
    while time.monotonic() < deadline:
        try:
            import socket
            with socket.create_connection((host, port), timeout=2):
                return True
        except OSError:
            time.sleep(2)
    logger.warning(
        "YouTube proxy %s:%s not reachable after %ss — yt-dlp may bot-check",
        host,
        port,
        timeout,
    )
    return False


_BROWSER_RETRY_DELAYS = (2, 6, 15)


def _deno_js_runtimes():
    """Return yt-dlp ``js_runtimes`` config pointing at deno when installed."""
    explicit = os.getenv("YTDLP_DENO_PATH", "").strip()
    if explicit:
        return {"deno": {"path": explicit}}
    deno = os.path.expanduser("~/.deno/bin/deno")
    if os.path.isfile(deno) and os.access(deno, os.X_OK):
        return {"deno": {"path": deno}}
    return {"deno": {}}


def _info_has_formats(info):
    if not info:
        return False
    if info.get("url"):
        return True
    formats = info.get("formats") or []
    return any(f.get("vcodec") != "none" or f.get("acodec") != "none" for f in formats)


def _is_bot_check_error(exc):
    err = str(exc).lower()
    return "confirm you're not a bot" in err or "sign in to confirm" in err


def invalidate_youtube_auth_probe():
    """Clear cached live YouTube auth probe (e.g. after cookies.txt upload)."""
    _PROBE_CACHE["monotonic"] = 0.0


def _ensure_youtube_session_env():
    """Ensure GNOME keyring vars exist (systemd does not inherit the desktop session)."""
    uid = os.getuid()
    runtime = f"/run/user/{uid}"
    if os.path.isdir(runtime):
        os.environ.setdefault("XDG_RUNTIME_DIR", runtime)
        bus = f"{runtime}/bus"
        if os.path.exists(bus):
            os.environ.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path={bus}")
        keyring = f"{runtime}/keyring/ssh"
        if os.path.exists(keyring):
            os.environ["SSH_AUTH_SOCK"] = keyring
    os.environ.setdefault("DISPLAY", ":0")
    xauth = os.path.expanduser("~/.Xauthority")
    if os.path.exists(xauth):
        os.environ.setdefault("XAUTHORITY", xauth)
    # secretstorage needs a desktop id to unlock Chrome v11 cookies; without this,
    # systemd workers see dbus+keyring paths but decrypt fails → YouTube bot_check.
    os.environ.setdefault("XDG_CURRENT_DESKTOP", "ubuntu:GNOME")
    os.environ.setdefault("LANG", "en_US.UTF-8")


def parse_cookie_jar(text):
    """Map cookie name -> value for non-empty entries of a Netscape cookie jar."""
    values_by_name = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        name, value = parts[5], parts[6]
        if value:
            values_by_name[name] = value
    return values_by_name


def cookie_jar_status(text):
    """Return ``(ok, detail)`` for a cookie jar's logged-in YouTube session.

    Requires at least one session cookie (SID / __Secure-*PSID) and one auth
    cookie (SAPISID / APISID / __Secure-*PAPISID / LOGIN_INFO). Modern Chrome
    exports often only include __Secure-3PSID + __Secure-3PAPISID.
    """
    values_by_name = parse_cookie_jar(text)
    if not values_by_name:
        return False, "no cookies found (expected tab-separated Netscape format)"
    has_session = any(name in values_by_name for name in _YT_SESSION_COOKIE_NAMES)
    has_auth = any(name in values_by_name for name in _YT_AUTH_COOKIE_NAMES)
    missing = []
    if not has_session:
        missing.append("SID/__Secure-*PSID")
    if not has_auth:
        missing.append("SAPISID/APISID/__Secure-*PAPISID/LOGIN_INFO")
    if missing:
        return False, "missing or empty: " + ", ".join(missing)
    return True, f"{len(values_by_name)} cookies, YouTube session present"


def _cookies_look_authenticated(cookies_path):
    """Return True if cookies.txt has a usable logged-in YouTube session."""
    try:
        with open(cookies_path, "r", encoding="utf-8", errors="ignore") as f:
            ok, _detail = cookie_jar_status(f.read())
        return ok
    except OSError:
        return False


def _primary_artist(artist):
    """First credited artist for search queries (before feat/comma clutter)."""
    if not artist:
        return ""
    name = re.split(r'[,]|(?:\s+(?:feat\.?|ft\.?)\s+)', artist, maxsplit=1, flags=re.I)[0]
    return name.strip()


def _token_title_similarity(expected, actual):
    """Fraction of significant title words found in the candidate (0-100)."""
    words = [w for w in re.findall(r'\w+', (expected or "").lower()) if len(w) > 3]
    if not words:
        return 0.0
    actual_lower = (actual or "").lower()
    matched = sum(1 for w in words if w in actual_lower)
    return (matched / len(words)) * 100.0


_NOISE_PATTERNS = (
    r'\blive\b', r'\bcover\b', r'\bkaraoke\b', r'\bsped\s*up\b', r'\bslowed\b',
    r'\bnightcore\b', r'#shorts\b', r'\breaction\b', r'\binstrumental\b',
    r'\bremake\b', r'\bmashup\b', r'\b8d\s*audio\b',
)


def _has_noise(text, expected_title=""):
    """True if candidate title looks like junk the user didn't ask for."""
    hay = (text or "").lower()
    expected = (expected_title or "").lower()
    for pat in _NOISE_PATTERNS:
        if re.search(pat, hay, re.I) and not re.search(pat, expected, re.I):
            return True
    return False


def _candidate_url(video, source_label="YouTube"):
    url = (
        video.get("webpage_url")
        or video.get("permalink_url")
        or video.get("url")
    )
    if url and str(url).startswith("http"):
        return url
    vid = video.get("id")
    if not vid:
        return None
    if source_label == "SoundCloud":
        # Flat scsearch results sometimes only expose a numeric/track id.
        return None
    return f"https://www.youtube.com/watch?v={vid}"


def _strip_track_noise(title):
    """Remove common YouTube junk from a track title for clean tags."""
    if not title:
        return ""
    cleaned = title
    cleaned = re.sub(
        r'\s*[\(\[][^)\]]*(?:official|audio|lyrics|video|hd|hq|4k|visuali[sz]er|'
        r'topic|music\s*video|lyric\s*video|audio\s*only)[^)\]]*[\)\]]',
        '',
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r'\s*\|\s*.*$', '', cleaned)
    cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip(" -\u2013\u2014|")
    return cleaned.strip()


def _parse_source_track_name(video):
    """Parse YouTube/SoundCloud result into clean (title, artist).

    Prefer ``Title - Artist`` / ``Artist - Title`` in the video title, fall back
    to cleaned title + uploader/channel.
    """
    raw = (video.get("title") or "").strip()
    uploader = (video.get("uploader") or video.get("channel") or "").strip()
    uploader = re.sub(r'\s*-\s*Topic\s*$', '', uploader, flags=re.I)
    uploader = re.sub(r'VEVO\s*$', '', uploader, flags=re.I).strip()

    title, artist = raw, uploader
    for sep in (" - ", " – ", " — ", " | "):
        if sep in raw:
            left, right = raw.split(sep, 1)
            left, right = left.strip(), right.strip()
            if left and right:
                # Prefer the side that looks like the song when uploader matches one side.
                up_l = uploader.lower()
                if up_l and up_l in right.lower():
                    title, artist = left, right
                elif up_l and up_l in left.lower():
                    title, artist = right, left
                else:
                    # Default chat/YouTube pattern: Title - Artist
                    title, artist = left, right
                break

    title = _strip_track_noise(title) or _strip_track_noise(raw) or raw
    artist = _strip_track_noise(artist) or uploader
    # If artist still empty/generic, keep uploader
    if not artist or artist.lower() in {"various artists", "topic"}:
        artist = uploader or artist
    return title, artist


def _video_thumbnail_url(video):
    """Best available thumbnail URL from a yt-dlp flat or full result."""
    thumb = video.get("thumbnail")
    if thumb:
        return thumb
    thumbs = video.get("thumbnails") or []
    if thumbs:
        best = max(thumbs, key=lambda t: (t.get("height") or 0) * (t.get("width") or 0))
        url = best.get("url")
        if url:
            return url
    vid = video.get("id")
    if vid and not str(vid).startswith("http"):
        return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
    return None


class MusicDownloader:
    def __init__(self, download_dir="downloads"):
        self.download_dir = download_dir
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)
        self.cookies_path = os.getenv(
            "YTDLP_COOKIES",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt"),
        )
        self.cookies_from_browser = os.getenv("YTDLP_COOKIES_FROM_BROWSER", "").strip()
        _ensure_youtube_session_env()
        if self.cookies_from_browser and not os.getenv("DBUS_SESSION_BUS_ADDRESS"):
            logger.warning(
                "DBUS_SESSION_BUS_ADDRESS is unset — Chrome cookie decryption will fail. "
                "Ensure hiit-radio-stack.sh exports the user session (logged-in desktop required)."
            )
        elif self.cookies_from_browser and not os.getenv("SSH_AUTH_SOCK"):
            logger.warning(
                "SSH_AUTH_SOCK is unset — GNOME keyring may be unreachable and Chrome "
                "cookie decryption can fail under systemd."
            )

        self.logo_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "hiit-radio.png"
        )
        self._logo_base = None
        try:
            if os.path.exists(self.logo_path):
                self._logo_base = Image.open(self.logo_path).convert("RGBA")
        except Exception:
            # Artwork will gracefully fall back to "no logo" if the file is missing/broken.
            self._logo_base = None

    def _with_ydl(self, opts):
        """Serialize yt-dlp — Chrome cookie decrypt is not safe concurrently."""
        class _YtdlCtx:
            def __enter__(ctx_self):
                _ensure_youtube_session_env()
                _YTDLP_LOCK.acquire()
                ctx_self._ydl = yt_dlp.YoutubeDL(opts)
                ctx_self._ydl.__enter__()
                return ctx_self._ydl

            def __exit__(ctx_self, exc_type, exc, tb):
                try:
                    return ctx_self._ydl.__exit__(exc_type, exc, tb)
                finally:
                    _YTDLP_LOCK.release()

        return _YtdlCtx()

    def _make_dynamic_logo(self):
        """Return logo with a thin white outline around letter edges."""
        if self._logo_base is None:
            return None
        logo = self._logo_base.copy().convert("RGBA")
        w, h = logo.size
        if w <= 0 or h <= 0:
            return None

        alpha = logo.getchannel("A")
        # Thin outer rim following the glyph silhouette.
        expanded = alpha.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MaxFilter(3))
        ring = ImageChops.subtract(expanded, alpha)
        ring = ring.point(lambda v: 255 if v >= 40 else 0)

        stroke = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        stroke.paste((255, 255, 255, 220), mask=ring)
        stroke = stroke.filter(ImageFilter.GaussianBlur(radius=0.45))
        return Image.alpha_composite(stroke, logo)

    def _browser_auth_tuple(self):
        spec = self.cookies_from_browser.strip() if self.cookies_from_browser else ""
        if not spec:
            return None
        parts = spec.split(":", 1)
        browser = parts[0].strip()
        profile = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
        return (browser, profile, None, None)

    def _browser_spec_tuple(self, browser_spec=None):
        spec = (
            browser_spec
            or self.cookies_from_browser
            or os.getenv("YTDLP_AUTO_BROWSER", "chrome")
        ).strip()
        if not spec:
            return None
        parts = spec.split(":", 1)
        browser = parts[0].strip()
        profile = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
        return (browser, profile, None, None)

    def _refresh_cookies_impl(self, browser_spec=None):
        """Export Chrome cookies to cookies.txt (call from a clean subprocess only)."""
        browser = self._browser_spec_tuple(browser_spec)
        if not browser:
            return False, "no browser configured"

        os.makedirs(os.path.dirname(os.path.abspath(self.cookies_path)), exist_ok=True)
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "ignore_no_formats_error": True,
            "cookiesfrombrowser": browser,
            "cookiefile": self.cookies_path,
            "remote_components": ["ejs:github"],
            "js_runtimes": _deno_js_runtimes(),
            "socket_timeout": 45,
            "extractor_args": {"youtube": {"player_client": list(_YT_PLAYER_CLIENTS)}},
        }
        proxy = _yt_proxy_url()
        if proxy:
            opts["proxy"] = proxy
        ytdlp_log = logging.getLogger("yt_dlp")
        prev_level = ytdlp_log.level
        ytdlp_log.setLevel(logging.CRITICAL)
        last_err = None
        try:
            for attempt in range(2):
                try:
                    with self._with_ydl(opts) as ydl:
                        ydl.extract_info(_HEALTH_PROBE_URL or _YT_PROBE_URL, download=False)
                    last_err = None
                    break
                except Exception as exc:
                    last_err = exc
                    if attempt < 1:
                        time.sleep(2)
        finally:
            ytdlp_log.setLevel(prev_level)

        try:
            with open(self.cookies_path, "r", encoding="utf-8", errors="ignore") as f:
                jar_ok, jar_detail = cookie_jar_status(f.read())
            if jar_ok:
                return True, f"exported cookies.txt — {jar_detail}"
        except OSError:
            pass

        if last_err is not None and _is_bot_check_error(last_err):
            return False, "bot_check during cookie export"
        if last_err is not None:
            return False, str(last_err)[:500]
        return False, "cookie export produced no authenticated session"

    def refresh_cookies_from_browser(self, browser_spec=None):
        """Export fresh cookies via an isolated worker subprocess."""
        _wait_for_yt_proxy(timeout=60)
        ok, detail = self._run_cookie_refresh_worker(browser_spec)
        invalidate_youtube_auth_probe()
        return ok, detail

    def _run_cookie_refresh_worker(self, browser_spec=None):
        """Refresh cookies.txt in a subprocess worker."""
        _ensure_youtube_session_env()
        root = os.path.dirname(os.path.abspath(__file__))
        worker = os.path.join(root, "scripts", "yt_download_worker.py")
        env = os.environ.copy()
        deno_bin = os.path.expanduser("~/.deno/bin")
        venv_bin = os.path.join(root, ".venv", "bin")
        env["PATH"] = f"{deno_bin}:{venv_bin}:" + env.get("PATH", "")
        cmd = [sys.executable, worker, "--refresh-cookies"]
        if browser_spec:
            cmd.extend(["--browser", browser_spec])
        with _YTDLP_LOCK:
            completed = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=root,
            )
        for line in (completed.stdout or "").splitlines():
            if line.startswith("yt_worker ") or line.startswith("REFRESH_"):
                logger.info("%s", line)
        if completed.returncode == 0:
            detail = ""
            for line in (completed.stdout or "").splitlines():
                if line.startswith("REFRESH_OK "):
                    detail = line[len("REFRESH_OK "):]
            return True, detail or "browser cookies exported"
        err = (completed.stderr or completed.stdout or "").strip()
        return False, err[:500] or "cookie refresh worker failed"

    def _apply_network(self, ydl_opts):
        proxy = _yt_proxy_url()
        if proxy:
            ydl_opts["proxy"] = proxy
        return ydl_opts

    def _apply_auth(self, ydl_opts, *, live_browser=False):
        """Attach cookies to yt-dlp options.

        ``live_browser=True`` reads Chrome's cookie DB (subprocess downloads only).
        The long-lived bot must not touch Chrome during search — it locks the DB and
        breaks subprocess auth.
        """
        ydl_opts.setdefault("remote_components", ["ejs:github"])
        ydl_opts.setdefault("js_runtimes", _deno_js_runtimes())
        self._apply_network(ydl_opts)
        browser = self._browser_auth_tuple()
        if browser and live_browser:
            ydl_opts["cookiesfrombrowser"] = browser
            logger.info(
                f"Using YouTube cookies from browser: {self.cookies_from_browser}"
            )
            return ydl_opts

        if browser and not live_browser:
            return ydl_opts

        cookies_ok = (
            os.path.exists(self.cookies_path)
            and _cookies_look_authenticated(self.cookies_path)
        )
        if cookies_ok:
            ydl_opts["cookiefile"] = self.cookies_path
            logger.info(f"Using authenticated YouTube cookies from {self.cookies_path}")
        elif os.path.exists(self.cookies_path):
            ydl_opts["cookiefile"] = self.cookies_path
            logger.warning(
                f"Using partial cookies.txt at {self.cookies_path} "
                "(missing some auth names — export fresh cookies if bot-check persists)"
            )
        else:
            logger.warning(
                f"No cookies at {self.cookies_path}. YouTube may bot-block. "
                "Set YTDLP_COOKIES_FROM_BROWSER=chrome or upload cookies.txt."
            )
        return ydl_opts

    def probe_youtube_auth(self, force=False):
        """Live yt-dlp probe with format extraction; cached for ``_PROBE_TTL_SEC``."""
        now = time.monotonic()
        if not force and now - _PROBE_CACHE["monotonic"] < _PROBE_TTL_SEC:
            return _PROBE_CACHE["ok"], _PROBE_CACHE["detail"]

        use_subprocess = bool(_yt_proxy_url() or self.cookies_from_browser)
        if use_subprocess:
            ok, detail = self._probe_youtube_subprocess(thorough=force)
            _PROBE_CACHE.update(monotonic=now, ok=ok, detail=detail)
            return ok, detail

        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "ignore_no_formats_error": False,
            "socket_timeout": 30,
            "remote_components": ["ejs:github"],
            "js_runtimes": _deno_js_runtimes(),
            "extractor_args": {"youtube": {"player_client": list(_YT_PLAYER_CLIENTS)}},
        }
        self._apply_auth(opts, live_browser=True)
        ytdlp_log = logging.getLogger("yt_dlp")
        prev_level = ytdlp_log.level
        ytdlp_log.setLevel(logging.CRITICAL)
        try:
            for probe_url in _probe_urls():
                try:
                    with self._with_ydl(opts) as ydl:
                        info = ydl.extract_info(probe_url, download=False)
                    if _info_has_formats(info):
                        ok, detail = True, "live probe OK (formats available)"
                        break
                    ok, detail = False, "probe returned no formats — download would fail"
                except Exception as exc:
                    err = str(exc)
                    if _is_bot_check_error(exc):
                        ok, detail = (
                            False,
                            "bot_check on probe URL (other videos may still download)",
                        )
                        continue
                    if "no video formats found" in err.lower() or "format is not available" in err.lower():
                        ok, detail = False, "no formats — YouTube bot-check, stale cookies, or JS runtime"
                    else:
                        ok, detail = False, err[:200]
                    break
            else:
                ok, detail = (
                    False,
                    "bot_check on probe URL (other videos may still download)",
                )
            if not ok:
                try:
                    from yt_dlp.utils._jsruntime import DenoJsRuntime
                    deno_info = DenoJsRuntime(path=_deno_js_runtimes().get("deno", {}).get("path")).info
                    logger.warning(
                        "YouTube probe failed (%s); deno=%s",
                        detail,
                        deno_info,
                    )
                except Exception:
                    pass
        finally:
            ytdlp_log.setLevel(prev_level)

        _PROBE_CACHE.update(monotonic=now, ok=ok, detail=detail)
        return ok, detail

    def ensure_youtube_ready(self, refresh=False):
        """Verify YouTube can extract formats; optionally refresh browser cookies first."""
        if refresh and self.cookies_from_browser:
            ok, detail = self.refresh_cookies_from_browser()
            logger.info("YouTube cookie refresh before download: ok=%s detail=%s", ok, detail)
            invalidate_youtube_auth_probe()
        return self.probe_youtube_auth(force=True)

    def youtube_auth_ok(self):
        """True when yt-dlp can pass YouTube's bot check (live probe)."""
        ok, _detail = self.probe_youtube_auth()
        return ok

    def _build_ydl_opts(
        self, output_template, progress_hooks=None, quality=DEFAULT_QUALITY,
        player_clients=None, live_browser=False,
    ):
        """Build yt-dlp options for the final audio download."""
        clients = player_clients or list(_YT_PLAYER_CLIENTS)
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 30,
            'retries': 3,
            'fragment_retries': 3,
            'http_headers': {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/131.0.0.0 Safari/537.36'
                ),
            },
            'sleep_interval': 0,
            'max_sleep_interval': 0,
            'noplaylist': True,
            'extractor_args': {
                'youtube': {
                    'player_client': clients,
                }
            },
        }
        if quality != "original":
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': str(quality),
            }]
        if progress_hooks:
            ydl_opts['progress_hooks'] = list(progress_hooks)
        return self._apply_auth(ydl_opts, live_browser=live_browser)

    def _youtube_subprocess_attempts(self):
        """Proxy/auth combinations for subprocess YouTube operations."""
        configured = _yt_proxy_url()
        allow_direct = os.getenv("YTDLP_ALLOW_DIRECT", "").strip() == "1"
        attempts = []
        if self.cookies_from_browser:
            if configured:
                attempts.append((configured, "browser"))
            else:
                attempts.append(("", "browser"))
            if allow_direct and configured:
                attempts.append(("", "browser"))
            return attempts
        if configured:
            if _cookies_look_authenticated(self.cookies_path):
                attempts.append((configured, "cookiefile"))
            if allow_direct:
                attempts.append(("", "cookiefile"))
        else:
            if _cookies_look_authenticated(self.cookies_path):
                attempts.append(("", "cookiefile"))
        return attempts or [("", "browser")]

    def _run_youtube_worker(self, url, *, probe=False, output_template="", quality=DEFAULT_QUALITY):
        """Invoke yt_download_worker.py in an isolated subprocess."""
        _wait_for_yt_proxy(timeout=60)
        _ensure_youtube_session_env()
        root = os.path.dirname(os.path.abspath(__file__))
        worker = os.path.join(root, "scripts", "yt_download_worker.py")
        env = os.environ.copy()
        deno_bin = os.path.expanduser("~/.deno/bin")
        venv_bin = os.path.join(root, ".venv", "bin")
        env["PATH"] = f"{deno_bin}:{venv_bin}:" + env.get("PATH", "")

        last_err = ""
        for proxy, auth in self._youtube_subprocess_attempts():
            label = proxy or "direct"
            retry_delays = _BROWSER_RETRY_DELAYS if auth == "browser" else ()
            max_attempts = 1 + len(retry_delays)
            for attempt in range(max_attempts):
                cmd = [
                    sys.executable,
                    worker,
                    "--url", url,
                    "--outtmpl", output_template or os.path.join(root, "downloads", "_probe.%(ext)s"),
                    "--quality", str(quality),
                    "--proxy", proxy,
                    "--auth", auth,
                ]
                if probe:
                    cmd.append("--probe")
                with _YTDLP_LOCK:
                    completed = subprocess.run(
                        cmd,
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=120 if probe else 600,
                        cwd=root,
                    )
                for line in (completed.stdout or "").splitlines():
                    if line.startswith("yt_worker ") or line == "PROBE_OK":
                        logger.info("%s", line)
                if completed.returncode == 0:
                    return True, f"subprocess OK (proxy={label}, auth={auth})"
                err = (completed.stderr or completed.stdout or "").strip() or (
                    f"worker exited {completed.returncode}"
                )
                last_err = err or last_err
                if (
                    attempt + 1 < max_attempts
                    and auth == "browser"
                    and _is_bot_check_error(last_err)
                ):
                    delay = retry_delays[attempt]
                    logger.info(
                        "YouTube browser auth bot_check — retry %d/%d after %ds",
                        attempt + 2,
                        max_attempts,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                break
        return False, last_err or "YouTube worker failed"

    def _download_youtube_subprocess(self, url, output_template, quality=DEFAULT_QUALITY):
        """Download in a fresh worker subprocess (isolates Chrome cookie access)."""
        logger.info("YouTube subprocess download: %s", url)
        ok, detail = self._run_youtube_worker(
            url, probe=False, output_template=output_template, quality=quality,
        )
        if not ok and _is_bot_check_error(detail) and self.cookies_from_browser:
            logger.info(
                "YouTube download bot_check — exporting browser cookies and retrying once"
            )
            refresh_ok, refresh_detail = self.refresh_cookies_from_browser()
            logger.info(
                "Pre-retry cookie refresh: ok=%s detail=%s",
                refresh_ok,
                refresh_detail,
            )
            time.sleep(3)
            ok, detail = self._run_youtube_worker(
                url, probe=False, output_template=output_template, quality=quality,
            )
        if ok:
            return True
        raise RuntimeError(detail)

    def _probe_youtube_subprocess(self, thorough=False):
        """Health-check via subprocess with live Chrome cookies (browser auth only)."""
        urls = []
        if _HEALTH_PROBE_URL:
            urls.append(_HEALTH_PROBE_URL)
        if thorough or os.getenv("YTDLP_PROBE_ALL", "").strip() == "1":
            for url in _probe_urls():
                if url not in urls:
                    urls.append(url)
        last_detail = "subprocess probe failed on all URLs"
        for url in urls:
            ok, detail = self._run_youtube_worker(url, probe=True)
            if ok:
                vid = url.rsplit("=", 1)[-1]
                return True, f"live probe OK ({detail}; video={vid})"
            last_detail = detail
        return False, last_detail

    def _build_search_opts(self):
        """Fast flat search — no sleep, list results only."""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'remote_components': ['ejs:github'],
            'extract_flat': 'in_playlist',
            'skip_download': True,
            'noplaylist': True,
            'sleep_interval': 0,
            'max_sleep_interval': 0,
            'socket_timeout': 20,
            'retries': 2,
            'http_headers': {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/131.0.0.0 Safari/537.36'
                ),
            },
            'extractor_args': {
                'youtube': {
                    'player_client': list(_YT_PLAYER_CLIENTS),
                }
            },
        }
        return self._apply_auth(ydl_opts, live_browser=False)

    async def download_song(self, metadata, progress_reporter=None, cancel_check=None,
                          quality=DEFAULT_QUALITY):
        """Download song with multi-candidate search and multi-layer validation.

        Flat YouTube searches score candidates on title + artist + duration/topic
        signals, then a single best URL is downloaded.

        Returns ``(file_path, error_code, failure_trail)``. On success ``error_code`` is ``None``.
        Failure codes: ``no_match``, ``bot_check``, ``timeout``, ``invalid_file``,
        ``cancelled``, ``drm``, ``unknown``.
        """

        MATCH_THRESHOLD = 65.0
        TITLE_THRESHOLD = 70.0
        EARLY_ACCEPT = 80.0
        QUERY_COVERAGE_MIN = 55.0
        RESULTS_PER_QUERY = 8

        def _is_cancelled():
            try:
                return bool(cancel_check and cancel_check())
            except Exception:
                return False

        def _classify_error(err):
            text = str(err or "").lower()
            if "confirm you're not a bot" in text or "sign in to confirm" in text:
                return "bot_check"
            if "no video formats found" in text:
                return "bot_check"
            if "drm" in text:
                return "drm"
            if "404" in text or "not found" in text:
                return "not_found"
            if "timed out" in text or "timeout" in text:
                return "timeout"
            return "unknown"

        original_query = (
            (getattr(metadata, "search_query", None) or "")
            or f"{metadata.title or ''} {metadata.artist or ''}".strip()
        )

        def title_similarity(a, b):
            return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() * 100

        def clean_title(title, artist=""):
            if not title:
                return ""
            title = re.sub(r'\s*\([^)]*official[^)]*\)', '', title, flags=re.IGNORECASE)
            title = re.sub(r'\s*\[[^]]*audio[^]]*\]', '', title, flags=re.IGNORECASE)
            title = re.sub(r'\s*\[[^]]*music video[^]]*\]', '', title, flags=re.IGNORECASE)
            title = re.sub(r'\s*\([^)]*lyrics[^)]*\)', '', title, flags=re.IGNORECASE)
            title = re.sub(r'\s*\([^)]*remaster[^)]*\)', '', title, flags=re.IGNORECASE)
            title = re.sub(r'\s*\([^)]*(?:from|feat\.?|ft\.?)[^)]*\)', '', title, flags=re.IGNORECASE)
            title = re.sub(r'\s*\[[^]]*(?:from|feat\.?|ft\.?)[^]]*\]', '', title, flags=re.IGNORECASE)
            title = re.sub(r'\s*\|.*$', '', title)
            title = title.replace('"', '').replace("'", '')
            if artist:
                pattern = r'^\s*' + re.escape(artist) + r'\s*[-–|]\s*'
                title = re.sub(pattern, '', title, flags=re.IGNORECASE)
            title = re.sub(r'\s*[-–].*$', '', title)
            return title.strip()

        def search_title(title):
            return clean_title(title or "", "")

        def clean_artist(name):
            if not name:
                return ""
            name = re.sub(r'\s*-\s*Topic\s*$', '', name, flags=re.IGNORECASE)
            name = re.sub(r'VEVO\s*$', '', name, flags=re.IGNORECASE)
            return name.strip()

        def query_coverage(video):
            """How well this candidate matches the user's original search text."""
            if not original_query:
                return 100.0
            raw = video.get("title") or ""
            uploader = clean_artist(video.get("uploader") or video.get("channel") or "")
            scores = [score_query_coverage(original_query, raw, uploader)]
            if " - " in raw:
                left, right = raw.split(" - ", 1)
                scores.append(score_query_coverage(original_query, left, right))
                scores.append(score_query_coverage(original_query, right, left))
            # Also compare against cleaned title + expected artist
            scores.append(
                score_query_coverage(
                    original_query,
                    clean_title(raw, metadata.artist),
                    metadata.artist or uploader,
                )
            )
            return max(scores)

        expected_duration = getattr(metadata, "duration", None)
        try:
            expected_duration = float(expected_duration) if expected_duration else None
        except (TypeError, ValueError):
            expected_duration = None

        def score(video):
            raw_title = video.get('title', '') or ''
            yt_title = clean_title(raw_title, metadata.artist)
            yt_artist = clean_artist(video.get('uploader', '') or video.get('channel', ''))
            expected_title = clean_title(metadata.title, metadata.artist)
            seq_title_sim = title_similarity(yt_title, expected_title)
            token_sim = _token_title_similarity(expected_title, yt_title)
            # Also score against the original free-text query title guess
            if original_query:
                token_sim = max(
                    token_sim,
                    _token_title_similarity(original_query, raw_title),
                    _token_title_similarity(original_query, f"{raw_title} {yt_artist}"),
                )
            title_sim = max(seq_title_sim, token_sim)
            artist_sim = title_similarity(yt_artist, metadata.artist or "")
            primary = _primary_artist(metadata.artist or "")
            if primary:
                artist_sim = max(artist_sim, title_similarity(yt_artist, primary))
            combined = (title_sim * 0.7) + (artist_sim * 0.3)

            coverage = query_coverage(video)
            if coverage < QUERY_COVERAGE_MIN:
                return None

            # Blend in query coverage so strong original-query matches win.
            combined = (combined * 0.75) + (coverage * 0.25)

            uploader_raw = (video.get('uploader', '') or video.get('channel', '') or '').lower()
            is_topic = uploader_raw.endswith('topic') or ' - topic' in uploader_raw
            is_vevo = 'vevo' in uploader_raw
            if is_topic or is_vevo:
                combined = min(100.0, combined + 8.0)

            cand_dur = video.get('duration')
            try:
                cand_dur = float(cand_dur) if cand_dur is not None else None
            except (TypeError, ValueError):
                cand_dur = None
            if cand_dur is not None:
                if cand_dur < 60 or cand_dur > 720:
                    return None
                if expected_duration and expected_duration > 0:
                    ratio = abs(cand_dur - expected_duration) / expected_duration
                    if ratio <= 0.15:
                        combined = min(100.0, combined + 6.0)
                    elif ratio > 0.35:
                        combined -= 12.0

            if _has_noise(raw_title, metadata.title or original_query or ""):
                combined -= 25.0

            return combined, title_sim, artist_sim, token_sim, yt_title, yt_artist, primary, is_topic, coverage

        q_title = search_title(metadata.title)
        q_artist = (metadata.artist or "").replace('"', '').strip()
        q_primary = _primary_artist(q_artist) or q_artist

        # Prefer the exact user query first — avoids swapped title/artist traps.
        yt_search_strategies = []
        if original_query:
            yt_search_strategies.append(original_query)
            yt_search_strategies.append(f'{original_query} audio')
        if q_title and q_artist:
            yt_search_strategies.append(f'"{q_title}" "{q_artist}" audio')
            yt_search_strategies.append(f'{q_title} {q_artist}')
        if q_title and q_primary:
            yt_search_strategies.append(f'{q_title} {q_primary} - Topic')
            yt_search_strategies.append(f'{q_title} {q_primary} official audio')
        seen_q = set()
        yt_search_strategies = [
            s for s in yt_search_strategies
            if s and not (s in seen_q or seen_q.add(s))
        ][:5]

        sc_search_strategies = []
        if original_query:
            sc_search_strategies.append(original_query)
        sc_search_strategies.extend([
            f'{q_title} {q_primary}' if q_primary else f'{q_title} {q_artist}',
            f'{q_title}',
        ])
        sc_search_strategies = [s for s in sc_search_strategies if s and s.strip()]
        seen_sc = set()
        sc_search_strategies = [
            s for s in sc_search_strategies
            if s and not (s in seen_sc or seen_sc.add(s))
        ]

        output_template = os.path.join(self.download_dir, f"{metadata.id}.%(ext)s")
        search_opts = self._build_search_opts()

        expected_title_clean = clean_title(metadata.title, metadata.artist)
        loop = asyncio.get_event_loop()
        download_pct = {"value": 0.0}

        async def _report(pct, detail):
            if not progress_reporter:
                return
            if getattr(progress_reporter, "progress_mode", "tracks") != "percent":
                return
            try:
                await progress_reporter.update(pct, detail)
            except Exception:
                pass

        if quality not in QUALITIES:
            quality = DEFAULT_QUALITY

        source_url = getattr(metadata, "source_url", None)
        if source_url:
            direct_trail = []
            if _is_cancelled():
                return None, "cancelled", direct_trail
            await _report(
                25,
                f"{metadata.title} — {metadata.artist}\nدر حال دانلود...",
            )
            direct_pct = {"value": 0.0}

            def _direct_hook(d):
                try:
                    if d.get("status") == "downloading":
                        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                        done = d.get("downloaded_bytes") or 0
                        if total:
                            direct_pct["value"] = min(done / float(total), 0.99)
                        else:
                            direct_pct["value"] = min(direct_pct["value"] + 0.02, 0.85)
                    elif d.get("status") == "finished":
                        direct_pct["value"] = 1.0
                except Exception:
                    pass

            ydl_opts = self._build_ydl_opts(
                output_template, progress_hooks=[_direct_hook], quality=quality,
            )
            try:
                with self._with_ydl(ydl_opts) as ydl:
                    await loop.run_in_executor(None, ydl.download, [source_url])
            except Exception as e:
                logger.error("Direct URL download failed: %s", e, exc_info=True)
                code = _classify_error(e)
                direct_trail.append({"source": "direct", "error": code})
                return None, code, direct_trail

            file_path = os.path.join(self.download_dir, f"{metadata.id}.mp3")
            if not os.path.exists(file_path):
                prefix = f"{metadata.id}."
                for name in os.listdir(self.download_dir):
                    if name.startswith(prefix) and not name.endswith(".part"):
                        file_path = os.path.join(self.download_dir, name)
                        break
            if not os.path.exists(file_path):
                direct_trail.append({"source": "direct", "error": "invalid_file"})
                return None, "invalid_file", direct_trail

            try:
                audio_file = MutagenMP3(file_path)
                duration = audio_file.info.length
                if duration < 30 or duration > 900:
                    logger.warning("Direct download unusual duration (%.1fs)", duration)
            except Exception:
                pass

            file_size = os.path.getsize(file_path)
            if file_size < 200_000:
                os.remove(file_path)
                direct_trail.append({"source": "direct", "error": "invalid_file"})
                return None, "invalid_file", direct_trail

            await _report(
                82, f"{metadata.title} — {metadata.artist}\nبرچسب‌گذاری و کاور...",
            )
            self._apply_metadata(file_path, metadata)
            return file_path, None, direct_trail

        MAX_CANDIDATES_PER_SOURCE = 5
        failure_trail = []

        async def gather_best(search_prefix, source_label, strategies, pct_start=20, pct_end=40):
            ranked = []
            seen_ids = set()
            bot_blocked = False
            n = max(len(strategies), 1)
            with self._with_ydl(search_opts) as ydl:
                for strategy_idx, search_query in enumerate(strategies):
                    if _is_cancelled():
                        return [], False, True
                    pct = pct_start + int((pct_end - pct_start) * (strategy_idx / n))
                    await _report(
                        pct,
                        f"{metadata.title} — {metadata.artist}\n"
                        f"جستجو ({source_label}) {strategy_idx + 1}/{n}...",
                    )
                    try:
                        logger.info(
                            f"[{source_label}] Search attempt {strategy_idx + 1}/{len(strategies)}: {search_query}"
                        )
                        info = await loop.run_in_executor(
                            None,
                            lambda q=search_query: ydl.extract_info(
                                f"{search_prefix}{RESULTS_PER_QUERY}:{q}", download=False
                            )
                        )
                        entries = info.get('entries') if info else None
                        if not entries:
                            logger.warning(f"[{source_label}] Strategy {strategy_idx + 1} returned no results")
                            continue

                        for video in entries:
                            if not video:
                                continue
                            vid = video.get('id')
                            if not vid or vid in seen_ids:
                                continue
                            if not _candidate_url(video, source_label):
                                continue
                            seen_ids.add(vid)

                            scored = score(video)
                            if scored is None:
                                continue
                            (
                                combined, title_sim, artist_sim, token_sim,
                                c_title, c_artist, primary, is_topic, coverage,
                            ) = scored
                            logger.info(
                                f"[{source_label}] Candidate: Title {title_sim:.1f}%, Artist {artist_sim:.1f}%, "
                                f"Coverage {coverage:.1f}%, Combined {combined:.1f}% | "
                                f"'{c_title}' by '{c_artist}' | "
                                f"Expected: '{expected_title_clean}' by '{metadata.artist}'"
                            )
                            if title_sim < TITLE_THRESHOLD and coverage < 75.0:
                                topic_ok = (
                                    is_topic
                                    and token_sim >= 85.0
                                    and artist_sim >= 80.0
                                )
                                if not topic_ok:
                                    continue
                            ranked.append((combined, video))

                        ranked.sort(key=lambda x: x[0], reverse=True)
                        ranked = ranked[:MAX_CANDIDATES_PER_SOURCE]
                        best_score = ranked[0][0] if ranked else 0

                        if best_score >= EARLY_ACCEPT:
                            logger.info(
                                f"[{source_label}] Early accept at {best_score:.1f}% "
                                f"(strategy {strategy_idx + 1})"
                            )
                            break
                        if strategy_idx >= 1 and best_score >= MATCH_THRESHOLD:
                            logger.info(
                                f"[{source_label}] Stopping early — best {best_score:.1f}% "
                                f"after strategy {strategy_idx + 1}"
                            )
                            break
                    except Exception as e:
                        err = str(e)
                        if "confirm you're not a bot" in err or "Sign in to confirm" in err:
                            bot_blocked = True
                            logger.error(
                                f"[{source_label}] Strategy {strategy_idx + 1} blocked by YouTube bot check. "
                                "Refresh logged-in cookies (cookies.txt) or set YTDLP_COOKIES_FROM_BROWSER=chrome"
                            )
                            if source_label == "YouTube":
                                break
                        else:
                            logger.error(f"[{source_label}] Strategy {strategy_idx + 1} failed: {e}")
                        continue
            ranked.sort(key=lambda x: x[0], reverse=True)
            ranked = ranked[:MAX_CANDIDATES_PER_SOURCE]
            if bot_blocked and source_label == "YouTube" and not ranked:
                logger.error(
                    "YouTube bot-check blocked all strategies — falling through to SoundCloud. "
                    "Fix cookies to restore YouTube downloads."
                )
            return ranked, bot_blocked, False

        if _is_cancelled():
            return None, "cancelled", failure_trail

        _SOURCES = {
            "YouTube": ("ytsearch", yt_search_strategies, "در حال جستجو..."),
            "SoundCloud": ("scsearch", sc_search_strategies, "در حال جستجو..."),
        }
        found_by_source = {}
        saw_bot_check = False

        async def search_source(label, pct_start, pct_end):
            """Search one source at most once per download; returns (candidates, cancelled)."""
            nonlocal saw_bot_check
            if label in found_by_source:
                return found_by_source[label], False
            prefix, strategies, note = _SOURCES[label]
            await _report(
                max(pct_start - 2, 0), f"{metadata.title} — {metadata.artist}\n{note}"
            )
            ranked, blocked, cancelled = await gather_best(
                prefix, label, strategies, pct_start, pct_end
            )
            found_by_source[label] = ranked
            saw_bot_check = saw_bot_check or blocked
            return ranked, cancelled

        # Without usable cookies YouTube downloads hit the bot check anyway, so
        # try SoundCloud first instead of burning every search strategy on it.
        yt_usable = self.youtube_auth_ok()
        source_order = ("YouTube", "SoundCloud") if yt_usable else ("SoundCloud", "YouTube")
        if not yt_usable:
            logger.warning(
                "YouTube cookies are not usable — searching SoundCloud first "
                "(YouTube search still runs for ranking; downloads skipped if probe fails)"
            )

        best = None
        for position, label in enumerate(source_order):
            pct_start, pct_end = (20, 38) if position == 0 else (40, 48)
            ranked, cancelled = await search_source(label, pct_start, pct_end)
            if cancelled or _is_cancelled():
                return None, "cancelled", failure_trail
            if ranked and (best is None or ranked[0][0] > best[0]):
                best = ranked[0]
            if position + 1 < len(source_order):
                source_best = ranked[0][0] if ranked else 0.0
                if source_best >= MATCH_THRESHOLD:
                    logger.info(
                        f"Found {label} match ({source_best:.1f}%) — "
                        f"also searching {source_order[position + 1]}"
                    )
                else:
                    best_txt = f"{best[0]:.1f}%" if best else "n/a"
                    logger.warning(
                        f"No valid {label} match (best eligible: {best_txt}) — "
                        f"trying {source_order[position + 1]} fallback"
                    )

        download_queue = []
        for label in ("YouTube", "SoundCloud"):
            for cand in found_by_source.get(label) or []:
                if cand[0] >= MATCH_THRESHOLD:
                    download_queue.append(cand)

        if not download_queue:
            score_txt = f"{best[0]:.1f}%" if best else "n/a"
            logger.error(
                f"No candidate passed validation on any source (title >= {TITLE_THRESHOLD:.0f}% and "
                f"combined >= {MATCH_THRESHOLD:.0f}%). Best eligible: {score_txt}"
            )
            return None, ("bot_check" if saw_bot_check else "no_match"), failure_trail

        def _source_label_for(video):
            extractor = (video.get("extractor") or "").lower()
            url = video.get("url") or video.get("webpage_url") or ""
            if "soundcloud" in extractor or "soundcloud" in url:
                return "SoundCloud"
            return "YouTube"

        yt_items = [c for c in download_queue if _source_label_for(c[1]) == "YouTube"]
        other_items = [c for c in download_queue if _source_label_for(c[1]) != "YouTube"]
        # Probe URL can bot-check while real track downloads still work — never drop
        # YouTube candidates solely on probe failure. Prefer SoundCloud first when the
        # cached probe is bad; keep YouTube as fallback (e.g. SoundCloud DRM).
        yt_usable = self.youtube_auth_ok()
        if yt_usable:
            download_queue = yt_items[:3] + other_items[:3]
        else:
            logger.warning(
                "YouTube probe unhealthy — trying other sources first, "
                "YouTube kept as fallback (%d candidates)",
                len(yt_items),
            )
            download_queue = other_items[:3] + yt_items[:4]
            if not download_queue:
                return None, "bot_check", failure_trail

        def _yt_hook(d):
            try:
                if d.get("status") == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                    done = d.get("downloaded_bytes") or 0
                    if total:
                        download_pct["value"] = max(
                            download_pct["value"],
                            min(done / float(total), 0.99),
                        )
                    else:
                        download_pct["value"] = min(download_pct["value"] + 0.02, 0.85)
                elif d.get("status") == "finished":
                    download_pct["value"] = 1.0
            except Exception:
                pass

        async def _download_candidate(candidate):
            score, video = candidate
            source_label = _source_label_for(video)
            url = _candidate_url(video, source_label)
            if not url:
                logger.error(f"Best {source_label} match has no downloadable URL")
                return None, None, "no_match"
            if _is_cancelled():
                return None, None, "cancelled"
            logger.info(
                f"Best {source_label} match {score:.1f}% — '{video.get('title', '')}' "
                f"— downloading {url}"
            )

            need_hydrate = not (
                (video.get("title") or "").strip()
                and _video_thumbnail_url(video)
            )
            if need_hydrate:
                await _report(50, f"{metadata.title} — {metadata.artist}\nآماده‌سازی لینک دانلود...")
                video = await self._hydrate_video_info(url, video, loop)
            else:
                await _report(50, f"{metadata.title} — {metadata.artist}\nشروع دانلود...")

            if progress_reporter and getattr(progress_reporter, "progress_mode", "") == "percent":
                progress_reporter.reset_phase(52)

            if _is_cancelled():
                return None, None, "cancelled"

            download_pct["value"] = 0.0
            pulse = {"n": 0}

            async def _heartbeat():
                base = 52
                detail = (
                    f"{metadata.title} — {metadata.artist}\n"
                    "در حال دانلود فایل صوتی..."
                )
                while True:
                    if source_label == "YouTube":
                        pulse["n"] = min(pulse["n"] + 1, 9)
                        pct = base + pulse["n"]
                    else:
                        frac = download_pct["value"]
                        pct = base + int(frac * 28)  # 52 → 80
                    await _report(pct, detail)
                    await asyncio.sleep(3)

            # Fresh subprocess for YouTube — isolates live Chrome cookie reads from search.
            if source_label == "YouTube":
                heartbeat = asyncio.create_task(_heartbeat())
                try:
                    await loop.run_in_executor(
                        None,
                        lambda: self._download_youtube_subprocess(
                            url, output_template, quality
                        ),
                    )
                except Exception as e:
                    code = _classify_error(e)
                    logger.warning(
                        f"Download of {source_label} match failed ({code}): {url} — {e}"
                    )
                    return None, None, code
                finally:
                    heartbeat.cancel()
                    try:
                        await heartbeat
                    except asyncio.CancelledError:
                        pass

                path = os.path.join(self.download_dir, f"{metadata.id}.mp3")
                if not os.path.exists(path):
                    prefix = f"{metadata.id}."
                    for name in os.listdir(self.download_dir):
                        if name.startswith(prefix) and not name.endswith(".part"):
                            path = os.path.join(self.download_dir, name)
                            break
                if not os.path.exists(path):
                    logger.warning(
                        f"{source_label} download completed but output file not found"
                    )
                    return None, None, "invalid_file"
                return path, video, None

            ydl_opts = self._build_ydl_opts(
                output_template,
                progress_hooks=[_yt_hook],
                quality=quality,
            )
            heartbeat = asyncio.create_task(_heartbeat())
            try:
                with self._with_ydl(ydl_opts) as ydl:
                    await loop.run_in_executor(None, ydl.download, [url])
            except Exception as e:
                code = _classify_error(e)
                logger.warning(
                    f"Download of {source_label} match failed ({code}): {url} — {e}"
                )
                return None, None, code
            finally:
                heartbeat.cancel()
                try:
                    await heartbeat
                except asyncio.CancelledError:
                    pass

            path = os.path.join(self.download_dir, f"{metadata.id}.mp3")
            if not os.path.exists(path):
                logger.warning(f"{source_label} download completed but output file not found")
                return None, None, "invalid_file"
            return path, video, None

        if _is_cancelled():
            return None, "cancelled", failure_trail

        global _ACTIVE_DOWNLOADS
        _ACTIVE_DOWNLOADS += 1
        try:
            file_path = None
            best_video = None
            best_score = 0.0
            last_err = None
            for candidate in download_queue:
                if _is_cancelled():
                    return None, "cancelled", failure_trail
                score, _video = candidate
                file_path, best_video, dl_err = await _download_candidate(candidate)
                if file_path:
                    best_score = score
                    break
                last_err = dl_err
                src = _source_label_for(_video)
                failure_trail.append({
                    "source": src,
                    "score": score,
                    "error": dl_err,
                    "title": (_video.get("title") or "")[:120],
                })
                logger.warning(
                    f"{src} candidate failed ({dl_err}, score {score:.1f}%) — trying next"
                )
                # Cool down after YouTube bot-check — burst requests get blocked.
                if dl_err == "bot_check" and src == "YouTube":
                    await asyncio.sleep(5)

            if _is_cancelled():
                return None, "cancelled", failure_trail

            if not file_path:
                return None, last_err or ("bot_check" if saw_bot_check else "no_match"), failure_trail

            try:
                audio_file = MutagenMP3(file_path)
                duration = audio_file.info.length
                if duration < 60 or duration > 600:
                    logger.warning(f"Invalid duration ({duration:.1f}s) - likely wrong track")
                    os.remove(file_path)
                    return None, "invalid_file", failure_trail
                if duration < 90 or duration > 420:
                    logger.warning(f"Unusual duration ({duration:.1f}s) - proceeding anyway")
            except Exception as e:
                logger.warning(f"Duration validation skipped (error: {e})")

            file_size = os.path.getsize(file_path)
            if file_size < 1_000_000:
                logger.warning(f"File too small ({file_size/1024:.0f}KB) - likely wrong track")
                os.remove(file_path)
                return None, "invalid_file", failure_trail

            logger.info(f"Download successful (match {best_score:.1f}%)")
            await _report(82, f"{metadata.title} — {metadata.artist}\nبرچسب‌گذاری و کاور...")
            self._enrich_metadata_from_source(metadata, best_video)
            self._apply_metadata(file_path, metadata)
            return file_path, None, failure_trail
        finally:
            _ACTIVE_DOWNLOADS = max(0, _ACTIVE_DOWNLOADS - 1)

    async def _hydrate_video_info(self, download_url, flat_video, loop):
        """Replace flat-search stub with full metadata (title, uploader, thumbnail)."""
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            "socket_timeout": 20,
            "retries": 2,
            "remote_components": ["ejs:github"],
            "extractor_args": {"youtube": {"player_client": list(_YT_PLAYER_CLIENTS)}},
        }
        self._apply_auth(opts, live_browser=False)
        try:
            with self._with_ydl(opts) as ydl:
                full = await loop.run_in_executor(
                    None, lambda: ydl.extract_info(download_url, download=False)
                )
            if full:
                # Preserve flat fields that full extract might omit oddly
                merged = dict(flat_video or {})
                merged.update(full)
                logger.info(
                    f"Hydrated source info: '{merged.get('title')}' "
                    f"uploader='{merged.get('uploader') or merged.get('channel')}'"
                )
                return merged
        except Exception as e:
            logger.warning(f"Could not hydrate video info: {e}")
        return flat_video

    def file_has_cover(self, file_path):
        try:
            audio = MutagenMP3(file_path, ID3=ID3)
            if not audio.tags:
                return False
            return bool(audio.tags.getall("APIC"))
        except Exception:
            return False

    def extract_cover(self, file_path):
        """Return watermarked JPEG cover bytes from an MP3's APIC frame, or None."""
        try:
            audio = MutagenMP3(file_path, ID3=ID3)
            if not audio.tags:
                return None
            apics = audio.tags.getall("APIC")
            if not apics:
                return None
            data = getattr(apics[0], "data", None)
            return bytes(data) if data else None
        except Exception:
            return None

    def file_is_source_enriched(self, file_path):
        """True when tags were written from the downloaded YouTube/SoundCloud title."""
        try:
            audio = MutagenMP3(file_path, ID3=ID3)
            if not audio.tags:
                return False
            for frame in audio.tags.getall("TXXX"):
                if getattr(frame, "desc", "") == "HIIT_SOURCE_ENRICHED":
                    return str(frame).strip() in {"1", "True", "true"}
            return False
        except Exception:
            return False

    def sync_metadata_from_file(self, file_path, metadata):
        """Copy ID3 title/artist into the metadata object used for Telegram send."""
        try:
            audio = MutagenMP3(file_path, ID3=ID3)
            if not audio.tags:
                return
            titles = audio.tags.getall("TIT2")
            artists = audio.tags.getall("TPE1")
            albums = audio.tags.getall("TALB")
            if titles and str(titles[0]):
                metadata.title = str(titles[0])
            if artists and str(artists[0]):
                metadata.artist = str(artists[0])
            if albums and str(albums[0]):
                metadata.album = str(albums[0])
            logger.info(
                f"Synced send metadata from file: '{metadata.title}' by '{metadata.artist}'"
            )
        except Exception as e:
            logger.debug(f"sync_metadata_from_file skipped: {e}")

    def rewatermark_from_file(self, file_path, default_style="youtube"):
        """Re-embed APIC with a freshly-drawn logo stroke.

        IMPORTANT: we only repaint the logo region on the already-processed
        artwork. This avoids re-cropping/re-pasting which would duplicate the
        logo and make strokes look ridiculous.
        """
        if not file_path or not os.path.exists(file_path):
            return False
        try:
            audio = MutagenMP3(file_path, ID3=ID3)
            if not audio.tags:
                return False

            apics = audio.tags.getall("APIC")
            if not apics:
                return False
            original_artwork = getattr(apics[0], "data", None)
            if not original_artwork:
                return False

            style = default_style
            for frame in audio.tags.getall("TXXX"):
                if getattr(frame, "desc", "") == "HIIT_WATERMARK_STYLE":
                    try:
                        if getattr(frame, "text", None):
                            style = str(frame.text[0])
                    except Exception:
                        pass
                    break

            if self._logo_base is None:
                return False
            logo = self._make_dynamic_logo()
            if not logo or logo.width <= 0 or logo.height <= 0:
                return False

            img = Image.open(io.BytesIO(original_artwork))
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            w, h = img.size
            # Match the exact logo sizing used in the artwork processors.
            if style in {"spotify", "apple"}:
                logo_w = int(w * 0.25)
            else:
                logo_w = int(w * 0.30)

            base_w, base_h = self._logo_base.size
            logo_h = int(logo_w * base_h / max(base_w, 1))
            logo_w = max(1, logo_w)
            logo_h = max(1, logo_h)

            logo = logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)
            x = max(0, w - logo_w - 20)
            y = max(0, h - logo_h - 20)
            img.paste(logo, (x, y), logo)

            out = io.BytesIO()
            img.convert("RGB").save(out, format="JPEG", quality=95)
            processed_artwork = out.getvalue()
            if not processed_artwork:
                return False

            audio.tags.delall("APIC")
            audio.tags.add(
                APIC(
                    encoding=3,
                    mime="image/jpeg",
                    type=3,
                    desc="Cover",
                    data=processed_artwork,
                )
            )
            audio.tags.delall("TXXX:HIIT_WATERMARK_STYLE")
            audio.tags.add(
                TXXX(encoding=3, desc="HIIT_WATERMARK_STYLE", text=[style])
            )
            audio.save(v2_version=3, v1=1)
            return True
        except Exception as e:
            logger.debug(f"rewatermark_from_file failed: {e}")
            return False

    def _enrich_metadata_from_source(self, metadata, video):
        """Upgrade title/artist/artwork from the actual downloaded source.

        For plain-text searches always prefer the source's display name so Telegram
        shows the real track, not the user's raw query split.
        """
        if not video:
            return
        src_title, src_artist = _parse_source_track_name(video)
        had_catalog = bool(getattr(metadata, "url", None)) and (
            "spotify.com" in (metadata.url or "") or "music.apple.com" in (metadata.url or "")
        )

        if not had_catalog:
            if src_title:
                metadata.title = src_title
            if src_artist:
                metadata.artist = src_artist
            metadata._source_enriched = True
            logger.info(f"Enriched tags from source: '{metadata.title}' by '{metadata.artist}'")
        else:
            logger.info(
                f"Keeping catalog tags '{metadata.title}' by '{metadata.artist}' "
                f"(source was '{src_title}' by '{src_artist}')"
            )

        thumb = _video_thumbnail_url(video)
        if thumb and (
            not getattr(metadata, "artwork_url", None)
            or not had_catalog
        ):
            # Text search: always prefer source thumbnail for watermarking when
            # we have no catalog art. For catalog links keep Spotify/Apple art.
            if not had_catalog or not metadata.artwork_url:
                metadata.artwork_url = thumb
                metadata._artwork_from_youtube = True
                logger.info(f"Using video thumbnail for watermarked cover: {thumb[:80]}")

    def _apply_lyrics(self, audio, lyrics):
        if not lyrics or not lyrics.get("text"):
            return
        audio.tags.delall("USLT")
        audio.tags.delall("SYLT")
        audio.tags.add(USLT(encoding=3, lang="eng", desc="Lyrics", text=lyrics["text"]))
        if lyrics.get("synced"):
            try:
                audio.tags.add(SYLT(
                    encoding=3, lang="eng", format=2, type=1, desc="Synced Lyrics",
                    text=lyrics["synced"],
                ))
            except Exception:
                pass

    def embed_lyrics(self, file_path, lyrics):
        """Embed USLT/SYLT lyrics into an existing MP3 file."""
        if not lyrics or not lyrics.get("text"):
            return
        try:
            audio = MutagenMP3(file_path, ID3=ID3)
            if audio.tags is None:
                audio.add_tags()
            self._apply_lyrics(audio, lyrics)
            audio.save(v2_version=3, v1=1)
            logger.info(f"Lyrics embedded ({lyrics.get('source', 'unknown')})")
        except Exception as e:
            logger.debug(f"Lyrics embed skipped: {e}")

    def _apply_metadata(self, file_path, metadata, lyrics=None):
        try:
            audio = MutagenMP3(file_path, ID3=ID3)
            try:
                audio.add_tags()
            except:
                pass

            if metadata.title:
                audio.tags.add(TIT2(encoding=3, text=metadata.title))
            if metadata.artist:
                audio.tags.add(TPE1(encoding=3, text=metadata.artist))
            if metadata.album:
                audio.tags.add(TALB(encoding=3, text=metadata.album))
            if getattr(metadata, "_source_enriched", False):
                audio.tags.delall("TXXX:HIIT_SOURCE_ENRICHED")
                audio.tags.add(
                    TXXX(encoding=3, desc="HIIT_SOURCE_ENRICHED", text=["1"])
                )
            if lyrics:
                self._apply_lyrics(audio, lyrics)

            if metadata.artwork_url:
                try:
                    headers = {
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/131.0.0.0 Safari/537.36"
                        ),
                        "Referer": "https://www.youtube.com/",
                    }
                    response = requests.get(
                        metadata.artwork_url, timeout=15, headers=headers,
                    )
                    if response.status_code == 200 and response.content:
                        original_artwork = response.content

                        source = "unknown"
                        from_yt = getattr(metadata, "_artwork_from_youtube", False)
                        if from_yt:
                            # YouTube thumbnail: same watermark as text-search (border + logo)
                            processed_artwork = self._process_itunes_query_artwork(original_artwork)
                            source = "youtube"
                        elif hasattr(metadata, 'url') and metadata.url:
                            if "spotify.com" in metadata.url:
                                processed_artwork = self._process_apple_music_artwork(original_artwork)
                                source = "spotify"
                            elif "music.apple.com" in metadata.url:
                                processed_artwork = self._process_apple_music_artwork(original_artwork)
                                source = "apple"
                            else:
                                processed_artwork = self._process_itunes_query_artwork(original_artwork)
                                source = "itunes"
                        else:
                            processed_artwork = self._process_itunes_query_artwork(original_artwork)
                            source = "fallback"

                        if processed_artwork:
                            audio.tags.delall("APIC")
                            audio.tags.delall("TXXX:HIIT_WATERMARK_STYLE")
                            audio.tags.add(
                                TXXX(
                                    encoding=3,
                                    desc="HIIT_WATERMARK_STYLE",
                                    text=[source],
                                )
                            )
                            audio.tags.add(APIC(
                                encoding=3,
                                mime="image/jpeg",
                                type=3,
                                desc="Cover",
                                data=processed_artwork
                            ))
                            logger.info(f"Embedded {source} artwork with HiiT Radio logo")
                        else:
                            logger.warning("Artwork processing returned None")
                    else:
                        logger.warning(
                            f"Artwork fetch failed: status={getattr(response, 'status_code', '?')}"
                        )
                except Exception as e:
                    logger.error(f"Artwork error: {e}", exc_info=True)
            else:
                logger.info("No artwork URL - sending audio without cover")

            audio.save(v2_version=3, v1=1)
            logger.info(f"Metadata applied: '{metadata.title}' by '{metadata.artist}'")

        except Exception as e:
            logger.error(f"Metadata error: {e}", exc_info=True)

    def _process_apple_music_artwork(self, original_artwork_bytes):
        """Apple Music & Spotify: center-crop to square, add logo (25% of size). NO white border."""
        try:
            img = Image.open(io.BytesIO(original_artwork_bytes))
            if img.mode != 'RGB':
                img = img.convert("RGB")

            # 1. Center-crop to square
            w, h = img.size
            min_dim = min(w, h)
            left = (w - min_dim) // 2
            top = (h - min_dim) // 2
            img = img.crop((left, top, left + min_dim, top + min_dim))

            # 2. Resize to 600x600
            target_size = 600
            img = img.resize((target_size, target_size), Image.Resampling.LANCZOS)

            # 3. Paste logo (25% of 600 = 150px)
            logo = self._make_dynamic_logo()
            if not logo or logo.width <= 0 or logo.height <= 0:
                logger.warning("hiit-radio.png NOT FOUND (dynamic logo unavailable)")
                out = io.BytesIO()
                img.save(out, format="JPEG", quality=95)
                return out.getvalue()
            logo_w = int(target_size * 0.25)
            logo_h = int(logo_w * logo.height / logo.width)
            logo = logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)

            x = max(0, target_size - logo_w - 20)
            y = max(0, target_size - logo_h - 20)

            img.paste(logo, (x, y), logo)

            out = io.BytesIO()
            img.save(out, format="JPEG", quality=95)
            logger.debug(f"Logo added at ({x},{y}) on {target_size}x{target_size}")
            return out.getvalue()

        except Exception as e:
            logger.error(f"Apple/Spotify artwork failed: {e}", exc_info=True)
            try:
                img = Image.open(io.BytesIO(original_artwork_bytes))
                if img.mode != "RGB":
                    img = img.convert("RGB")
                out = io.BytesIO()
                img.save(out, format="JPEG", quality=95)
                return out.getvalue()
            except Exception:
                return None

    def _process_itunes_query_artwork(self, original_artwork_bytes):
        """iTunes query: square crop + white border (30%) + logo."""
        try:
            img = Image.open(io.BytesIO(original_artwork_bytes))
            if img.mode != 'RGB':
                img = img.convert("RGB")

            # 1. Center-crop to square
            w, h = img.size
            min_dim = min(w, h)
            left = (w - min_dim) // 2
            top = (h - min_dim) // 2
            img = img.crop((left, top, left + min_dim, top + min_dim))

            # 2. Add white border (30% padding)
            pad = int(min_dim * 0.3)
            new_size = min_dim + 2 * pad
            bordered = Image.new("RGB", (new_size, new_size), "white")
            bordered.paste(img, (pad, pad))

            # 3. Resize to 600x600
            target_size = 600
            bordered = bordered.resize((target_size, target_size), Image.Resampling.LANCZOS)

            # 4. Paste logo (30% of 600 = 180px)
            logo = self._make_dynamic_logo()
            if not logo or logo.width <= 0 or logo.height <= 0:
                logger.warning("hiit-radio.png NOT FOUND (dynamic logo unavailable)")
                out = io.BytesIO()
                bordered.save(out, format="JPEG", quality=95)
                return out.getvalue()
            logo_w = int(target_size * 0.3)
            logo_h = int(logo_w * logo.height / logo.width)
            logo = logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)

            x = max(0, target_size - logo_w - 20)
            y = max(0, target_size - logo_h - 20)

            bordered.paste(logo, (x, y), logo)

            out = io.BytesIO()
            bordered.save(out, format="JPEG", quality=95)
            logger.debug("[iTunes] Logo added with white border")
            return out.getvalue()

        except Exception as e:
            logger.error(f"iTunes artwork failed: {e}", exc_info=True)
            try:
                img = Image.open(io.BytesIO(original_artwork_bytes))
                if img.mode != "RGB":
                    img = img.convert("RGB")
                out = io.BytesIO()
                img.save(out, format="JPEG", quality=95)
                return out.getvalue()
            except Exception:
                return None

    async def cleanup(self, file_path):
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")