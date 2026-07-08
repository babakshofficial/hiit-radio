import os
import re
import yt_dlp
import logging
import asyncio
import json
import difflib
from mutagen.mp3 import MP3 as MutagenMP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC
import requests
from PIL import Image
import io

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

    def _build_ydl_opts(self, output_template):
        """Build yt-dlp options, preferring logged-in browser cookies when available."""
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
            'sleep_interval': 2,
            'max_sleep_interval': 5,
            'noplaylist': True,
            'extractor_args': {
                'youtube': {
                    # Prefer Android client — less aggressive bot checks than web.
                    'player_client': ['android', 'web'],
                }
            },
        }

        if self.cookies_from_browser:
            # e.g. YTDLP_COOKIES_FROM_BROWSER=chrome  or  chrome:Profile\ 1
            parts = self.cookies_from_browser.split(":", 1)
            browser = parts[0].strip()
            profile = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
            ydl_opts['cookiesfrombrowser'] = (browser, profile, None, None)
            logger.info(f"Using YouTube cookies from browser: {self.cookies_from_browser}")
        elif os.path.exists(self.cookies_path):
            ydl_opts['cookiefile'] = self.cookies_path
            if _cookies_look_authenticated(self.cookies_path):
                logger.info(f"Using authenticated YouTube cookies from {self.cookies_path}")
            else:
                logger.warning(
                    f"cookies.txt at {self.cookies_path} has no logged-in YouTube session "
                    "(missing LOGIN_INFO/SAPISID). YouTube will likely bot-block downloads. "
                    "Export fresh cookies while signed into youtube.com, or set "
                    "YTDLP_COOKIES_FROM_BROWSER=chrome in .env"
                )
        else:
            logger.warning(
                f"No cookies file at {self.cookies_path}. YouTube may bot-block. "
                "Export cookies.txt or set YTDLP_COOKIES_FROM_BROWSER=chrome"
            )

        return ydl_opts

    async def download_song(self, metadata):
        """Download song with multi-candidate search and multi-layer validation.

        Instead of trusting only YouTube's #1 hit per query, we collect several
        candidates from every search strategy, score each one on title + artist
        similarity, and download the single best match above a safety threshold.
        If YouTube yields no valid match, SoundCloud is tried as a fallback
        before giving up.
        """

        # Minimum combined (title+artist) score required to accept a candidate.
        MATCH_THRESHOLD = 65.0
        # The title itself must clear this bar independently, so that a wrong
        # song by the *right* artist (100% artist boost) can't sneak through.
        TITLE_THRESHOLD = 70.0
        # How many results to inspect per search query.
        RESULTS_PER_QUERY = 5

        def title_similarity(a, b):
            """Calculate similarity between two strings (0-100%)."""
            return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() * 100

        def clean_title(title, artist=""):
            """Remove common junk from YouTube titles and intelligently strip artist names."""
            if not title: return ""
            title = re.sub(r'\s*\([^)]*official[^)]*\)', '', title, flags=re.IGNORECASE)
            title = re.sub(r'\s*\[[^]]*audio[^]]*\]', '', title, flags=re.IGNORECASE)
            title = re.sub(r'\s*\[[^]]*music video[^]]*\]', '', title, flags=re.IGNORECASE)
            title = re.sub(r'\s*\([^)]*lyrics[^)]*\)', '', title, flags=re.IGNORECASE)
            title = re.sub(r'\s*\([^)]*remaster[^)]*\)', '', title, flags=re.IGNORECASE)
            # Strip soundtrack/feature markers like (From "Hoppers") / (feat. X)
            title = re.sub(r'\s*\([^)]*(?:from|feat\.?|ft\.?)[^)]*\)', '', title, flags=re.IGNORECASE)
            title = re.sub(r'\s*\[[^]]*(?:from|feat\.?|ft\.?)[^]]*\]', '', title, flags=re.IGNORECASE)
            title = re.sub(r'\s*\|.*$', '', title)
            title = title.replace('"', '').replace("'", '')

            # Smart artist stripping: If title starts with "Artist -", "Artist |", etc., remove it
            if artist:
                pattern = r'^\s*' + re.escape(artist) + r'\s*[-–|]\s*'
                title = re.sub(pattern, '', title, flags=re.IGNORECASE)

            title = re.sub(r'\s*[-–].*$', '', title)
            return title.strip()

        def search_title(title):
            """Title cleaned for search queries (no nested quotes / soundtrack tags)."""
            return clean_title(title or "", "")

        def clean_artist(name):
            """Normalise a YouTube uploader/channel into an artist name for comparison."""
            if not name: return ""
            name = re.sub(r'\s*-\s*Topic\s*$', '', name, flags=re.IGNORECASE)
            name = re.sub(r'VEVO\s*$', '', name, flags=re.IGNORECASE)
            return name.strip()

        def score(video):
            """Combined title(70%) + artist(30%) similarity for a candidate video."""
            yt_title = clean_title(video.get('title', ''), metadata.artist)
            yt_artist = clean_artist(video.get('uploader', '') or video.get('channel', ''))
            expected_title = clean_title(metadata.title, metadata.artist)
            title_sim = title_similarity(yt_title, expected_title)
            artist_sim = title_similarity(yt_artist, metadata.artist or "")
            combined = (title_sim * 0.7) + (artist_sim * 0.3)
            return combined, title_sim, artist_sim, yt_title, yt_artist

        q_title = search_title(metadata.title)
        q_artist = (metadata.artist or "").replace('"', '').strip()

        # YouTube search strategies ordered from most specific to least specific.
        yt_search_strategies = [
            f'"{q_title}" "{q_artist}" audio',
            f'"{q_title}" "{q_artist}"',
            f'{q_title} {q_artist} official audio',
            f'{q_title} {q_artist}',
        ]

        # SoundCloud handles plain keyword queries best — no quotes, no
        # "official audio"/"audio" suffixes, which tend to return zero results.
        sc_search_strategies = [
            f'{q_title} {q_artist}',
            f'{q_title}',
        ]

        output_template = os.path.join(self.download_dir, f"{metadata.id}.%(ext)s")
        ydl_opts = self._build_ydl_opts(output_template)

        expected_title_clean = clean_title(metadata.title, metadata.artist)
        loop = asyncio.get_event_loop()

        async def gather_best(search_prefix, source_label, strategies):
            """Search one engine (e.g. 'ytsearch' / 'scsearch') across the given
            strategies and return the best eligible candidate as
            (combined_score, video) or None."""
            best_local = None
            seen_ids = set()
            bot_blocked = False
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
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
                            if not video or not video.get('webpage_url'):
                                continue
                            vid = video.get('id')
                            if vid in seen_ids:
                                continue
                            seen_ids.add(vid)

                            combined, title_sim, artist_sim, c_title, c_artist = score(video)
                            logger.info(
                                f"[{source_label}] Candidate: Title {title_sim:.1f}%, Artist {artist_sim:.1f}%, "
                                f"Combined {combined:.1f}% | '{c_title}' by '{c_artist}' | "
                                f"Expected: '{expected_title_clean}' by '{metadata.artist}'"
                            )
                            # A candidate is only eligible if its title matches well enough.
                            # This rejects other songs by the same artist.
                            if title_sim < TITLE_THRESHOLD:
                                continue
                            if best_local is None or combined > best_local[0]:
                                best_local = (combined, video)

                        # Early exit: a strong match this early is very likely correct.
                        if best_local and best_local[0] >= 85:
                            break
                    except Exception as e:
                        err = str(e)
                        if "confirm you're not a bot" in err or "Sign in to confirm" in err:
                            bot_blocked = True
                            logger.error(
                                f"[{source_label}] Strategy {strategy_idx + 1} blocked by YouTube bot check. "
                                "Refresh logged-in cookies (cookies.txt) or set YTDLP_COOKIES_FROM_BROWSER=chrome"
                            )
                            # No point retrying more YouTube strategies with the same bad cookies.
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

        # PHASE 1: search YouTube; fall back to SoundCloud before giving up.
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
        logger.info(f"Best match {best_score:.1f}% — '{best_video.get('title', '')}' — downloading")

        # PHASE 2: download the chosen candidate and run post-download validation.
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                await loop.run_in_executor(None, ydl.download, [best_video['webpage_url']])
        except Exception as e:
            logger.error(f"Download of best match failed: {e}", exc_info=True)
            return None

        file_path = os.path.join(self.download_dir, f"{metadata.id}.mp3")
        if not os.path.exists(file_path):
            logger.warning("Download completed but output file not found")
            return None

        # VALIDATION: Duration check
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

        # VALIDATION: File size check
        file_size = os.path.getsize(file_path)
        if file_size < 1_000_000:
            logger.warning(f"File too small ({file_size/1024:.0f}KB) - likely wrong track")
            os.remove(file_path)
            return None

        logger.info(f"Download successful (match {best_score:.1f}%)")
        self._apply_metadata(file_path, metadata)
        return file_path

    def _apply_metadata(self, file_path, metadata):
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

            if metadata.artwork_url:
                try:
                    response = requests.get(metadata.artwork_url, timeout=10)
                    if response.status_code == 200:
                        original_artwork = response.content
                        
                        # Route artwork processing by source
                        source = "unknown"
                        if hasattr(metadata, 'url') and metadata.url:
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
                        logger.warning(f"Artwork fetch failed: {response.status_code}")
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
            logo_path = os.path.join(os.path.dirname(__file__), "hiit-radio.png")
            if not os.path.exists(logo_path):
                logger.warning("hiit-radio.png NOT FOUND")
                out = io.BytesIO()
                img.save(out, format="JPEG", quality=95)
                return out.getvalue()

            logo = Image.open(logo_path).convert("RGBA")
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
            logo_path = os.path.join(os.path.dirname(__file__), "hiit-radio.png")
            if not os.path.exists(logo_path):
                logger.warning("hiit-radio.png NOT FOUND")
                out = io.BytesIO()
                bordered.save(out, format="JPEG", quality=95)
                return out.getvalue()

            logo = Image.open(logo_path).convert("RGBA")
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