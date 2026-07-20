import os
import re
import yt_dlp
import logging
import asyncio
import json
import difflib
import random
from mutagen.mp3 import MP3 as MutagenMP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, USLT, SYLT, TXXX
import requests
from PIL import Image, ImageDraw
import io

from metadata import score_query_coverage

logger = logging.getLogger(__name__)

# Auth cookie names that indicate a logged-in YouTube session.
_YT_AUTH_COOKIE_NAMES = (
    "LOGIN_INFO",
    "SAPISID",
    "__Secure-1PSID",
    "__Secure-3PSID",
    "SID",
)


def _cookies_look_authenticated(cookies_path):
    """Return True if cookies.txt appears to contain a logged-in YouTube session."""
    try:
        with open(cookies_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        return any(name in text for name in _YT_AUTH_COOKIE_NAMES)
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
    url = video.get("webpage_url") or video.get("url")
    if url and url.startswith("http"):
        return url
    vid = video.get("id")
    if not vid:
        return None
    if source_label == "SoundCloud":
        return url
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

    def _make_dynamic_logo(self):
        """Return a RGBA logo with a random colorful stroke drawn on it."""
        if self._logo_base is None:
            return None
        logo = self._logo_base.copy()
        w, h = logo.size
        if w <= 0 or h <= 0:
            return logo

        rng = random.Random(int.from_bytes(os.urandom(4), "little", signed=False))
        draw = ImageDraw.Draw(logo)

        # Bright palette for visible strokes.
        palette = [
            (255, 64, 64),    # red
            (64, 255, 64),    # green
            (64, 128, 255),   # blue
            (255, 200, 64),   # yellow
            (255, 64, 200),   # magenta
            (64, 255, 240),   # cyan
        ]

        strokes = rng.randint(1, 3)
        for _ in range(strokes):
            color = rng.choice(palette)
            alpha = rng.randint(110, 220)
            width = max(2, int(min(w, h) * rng.uniform(0.02, 0.06)))

            # Draw a slightly "brushy" polyline across the logo.
            x1, y1 = rng.randint(0, w), rng.randint(0, h)
            x2, y2 = rng.randint(0, w), rng.randint(0, h)
            x3, y3 = rng.randint(0, w), rng.randint(0, h)
            draw.line(
                [(x1, y1), (x2, y2), (x3, y3)],
                fill=(color[0], color[1], color[2], alpha),
                width=width,
            )

        return logo

    def _apply_auth(self, ydl_opts):
        """Attach cookies / proxy to yt-dlp options."""
        if os.path.exists(self.cookies_path) and _cookies_look_authenticated(self.cookies_path):
            ydl_opts['cookiefile'] = self.cookies_path
            logger.info(f"Using authenticated YouTube cookies from {self.cookies_path}")
        elif self.cookies_from_browser:
            parts = self.cookies_from_browser.split(":", 1)
            browser = parts[0].strip()
            profile = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
            ydl_opts['cookiesfrombrowser'] = (browser, profile, None, None)
            logger.info(f"Using YouTube cookies from browser: {self.cookies_from_browser}")
        elif os.path.exists(self.cookies_path):
            ydl_opts['cookiefile'] = self.cookies_path
            logger.warning(
                f"cookies.txt at {self.cookies_path} has no logged-in YouTube session "
                "(missing LOGIN_INFO/SAPISID). YouTube will likely bot-block downloads. "
                "Export fresh cookies while signed into youtube.com."
            )
        else:
            logger.warning(
                f"No authenticated cookies at {self.cookies_path}. YouTube may bot-block. "
                "Copy cookies.txt from your PC or export fresh cookies on desktop."
            )

        proxy = os.getenv("YTDLP_PROXY", "").strip() or os.getenv("HTTPS_PROXY", "").strip()
        if proxy:
            ydl_opts['proxy'] = proxy
            logger.info(f"Using proxy for yt-dlp: {proxy}")
        return ydl_opts

    def _build_search_opts(self):
        """Fast flat search — no sleep, list results only."""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': 'in_playlist',
            'skip_download': True,
            'noplaylist': True,
            'sleep_interval': 0,
            'max_sleep_interval': 0,
            'http_headers': {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/131.0.0.0 Safari/537.36'
                ),
            },
        }
        return self._apply_auth(ydl_opts)

    def _build_ydl_opts(self, output_template):
        """Build yt-dlp options for the final audio download."""
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '256',
            }],
            'quiet': True,
            'no_warnings': True,
            'http_headers': {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/131.0.0.0 Safari/537.36'
                ),
            },
            'sleep_interval': 1,
            'max_sleep_interval': 2,
            'noplaylist': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                }
            },
        }
        return self._apply_auth(ydl_opts)

    async def download_song(self, metadata):
        """Download song with multi-candidate search and multi-layer validation.

        Flat YouTube searches score candidates on title + artist + duration/topic
        signals, then a single best URL is downloaded.
        """

        MATCH_THRESHOLD = 65.0
        TITLE_THRESHOLD = 70.0
        EARLY_ACCEPT = 80.0
        QUERY_COVERAGE_MIN = 55.0
        RESULTS_PER_QUERY = 8

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
        ydl_opts = self._build_ydl_opts(output_template)

        expected_title_clean = clean_title(metadata.title, metadata.artist)
        loop = asyncio.get_event_loop()

        async def gather_best(search_prefix, source_label, strategies):
            best_local = None
            seen_ids = set()
            bot_blocked = False
            with yt_dlp.YoutubeDL(search_opts) as ydl:
                for strategy_idx, search_query in enumerate(strategies):
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
                            if best_local is None or combined > best_local[0]:
                                best_local = (combined, video)

                        if best_local and best_local[0] >= EARLY_ACCEPT:
                            logger.info(
                                f"[{source_label}] Early accept at {best_local[0]:.1f}% "
                                f"(strategy {strategy_idx + 1})"
                            )
                            break
                        # After first two strategies, stop if we already cleared the bar.
                        if strategy_idx >= 1 and best_local and best_local[0] >= MATCH_THRESHOLD:
                            logger.info(
                                f"[{source_label}] Stopping early — best {best_local[0]:.1f}% "
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
            if bot_blocked and source_label == "YouTube" and not best_local:
                logger.error(
                    "YouTube bot-check blocked all strategies — falling through to SoundCloud. "
                    "Fix cookies to restore YouTube downloads."
                )
            return best_local

        best = await gather_best("ytsearch", "YouTube", yt_search_strategies)
        if not best or best[0] < MATCH_THRESHOLD:
            yt_txt = f"{best[0]:.1f}%" if best else "n/a"
            logger.warning(f"No valid YouTube match (best eligible: {yt_txt}) — trying SoundCloud fallback")
            best = await gather_best("scsearch", "SoundCloud", sc_search_strategies)

        if not best or best[0] < MATCH_THRESHOLD:
            score_txt = f"{best[0]:.1f}%" if best else "n/a"
            logger.error(
                f"No candidate passed validation on any source (title >= {TITLE_THRESHOLD:.0f}% and "
                f"combined >= {MATCH_THRESHOLD:.0f}%). Best eligible: {score_txt}"
            )
            return None

        best_score, best_video = best
        download_url = _candidate_url(
            best_video,
            "SoundCloud" if "soundcloud" in (best_video.get("extractor") or "").lower()
            or (best_video.get("url") or "").find("soundcloud") >= 0
            else "YouTube",
        )
        if not download_url:
            logger.error("Best match has no downloadable URL")
            return None
        logger.info(f"Best match {best_score:.1f}% — '{best_video.get('title', '')}' — downloading")

        # Flat search may lack full title/thumbnail — refresh from the watch URL.
        best_video = await self._hydrate_video_info(download_url, best_video, loop)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                await loop.run_in_executor(None, ydl.download, [download_url])
        except Exception as e:
            logger.error(f"Download of best match failed: {e}", exc_info=True)
            return None

        file_path = os.path.join(self.download_dir, f"{metadata.id}.mp3")
        if not os.path.exists(file_path):
            logger.warning("Download completed but output file not found")
            return None

        try:
            audio_file = MutagenMP3(file_path)
            duration = audio_file.info.length
            if duration < 60 or duration > 600:
                logger.warning(f"Invalid duration ({duration:.1f}s) - likely wrong track")
                os.remove(file_path)
                return None
            if duration < 90 or duration > 420:
                logger.warning(f"Unusual duration ({duration:.1f}s) - proceeding anyway")
        except Exception as e:
            logger.warning(f"Duration validation skipped (error: {e})")

        file_size = os.path.getsize(file_path)
        if file_size < 1_000_000:
            logger.warning(f"File too small ({file_size/1024:.0f}KB) - likely wrong track")
            os.remove(file_path)
            return None

        logger.info(f"Download successful (match {best_score:.1f}%)")
        self._enrich_metadata_from_source(metadata, best_video)
        self._apply_metadata(file_path, metadata)
        return file_path

    async def _hydrate_video_info(self, download_url, flat_video, loop):
        """Replace flat-search stub with full metadata (title, uploader, thumbnail)."""
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
        }
        self._apply_auth(opts)
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
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
        """Re-embed APIC with a freshly-drawn random logo stroke."""
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

            # Re-apply the same artwork layout style, but with a new random stroke.
            if style in {"spotify", "apple"}:
                processed_artwork = self._process_apple_music_artwork(original_artwork)
            else:
                processed_artwork = self._process_itunes_query_artwork(original_artwork)

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
            if not logo:
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
            if not logo:
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