import os
import re
import yt_dlp
import logging
import asyncio
import json
from mutagen.mp3 import MP3 as MutagenMP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC
import requests
from PIL import Image
import io

logger = logging.getLogger(__name__)

class MusicDownloader:
    def __init__(self, download_dir="downloads"):
        self.download_dir = download_dir
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)

    async def download_song(self, metadata):
        """Download song with enhanced validation and Apple preview fallback."""
        import difflib
        
        def title_similarity(a, b):
            return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() * 100

        def clean_title(title):
            # Remove parenthetical phrases that aren't part of core title
            title = re.sub(r'\s*\([^)]*remaster[^)]*\)', '', title, flags=re.IGNORECASE)
            title = re.sub(r'\s*\([^)]*from[^)]*\)', '', title, flags=re.IGNORECASE)  # Handles "(From Hoppers)"
            title = re.sub(r'\s*\([^)]*official[^)]*\)', '', title, flags=re.IGNORECASE)
            title = re.sub(r'\s*\[[^]]*audio[^]]*\]', '', title, flags=re.IGNORECASE)
            title = re.sub(r'\s*\[[^]]*music video[^]]*\]', '', title, flags=re.IGNORECASE)
            title = re.sub(r'\s*\([^)]*lyrics[^)]*\)', '', title, flags=re.IGNORECASE)
            title = re.sub(r'\s*\|.*$', '', title)
            title = re.sub(r'\s*-.*$', '', title)
            return title.strip()

        # 🔑 IMPROVED: Include artist in similarity check
        def combined_similarity(yt_title, yt_artist, expected_title, expected_artist):
            title_sim = title_similarity(yt_title, expected_title)
            artist_sim = title_similarity(yt_artist or "", expected_artist)
            # Weight title 70%, artist 30%
            return (title_sim * 0.7) + (artist_sim * 0.3)

        search_strategies = [
            f'"{metadata.title}" "{metadata.artist}" audio',
            f'"{metadata.title}" "{metadata.artist}"',
            f'{metadata.title} {metadata.artist} official audio',
            f'{metadata.title} {metadata.artist}',
        ]

        output_template = os.path.join(self.download_dir, f"{metadata.id}.%(ext)s")
        
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
            'cookiefile': 'cookies.txt',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            'sleep_interval': 2,
            'max_sleep_interval': 5,
            'noplaylist': True,
        }

        for strategy_idx, search_query in enumerate(search_strategies):
            try:
                loop = asyncio.get_event_loop()
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    logger.info(f"🔍 Search attempt {strategy_idx + 1}/4: {search_query}")
                    
                    info = await loop.run_in_executor(
                        None, 
                        lambda: ydl.extract_info(f"ytsearch1:{search_query}", download=False)
                    )
                    
                    if 'entries' in info and info['entries']:
                        video = info['entries'][0]
                    elif info:
                        video = info
                    else:
                        video = None

                    if not video or not video.get('url'):
                        logger.warning(f"Strategy {strategy_idx + 1} returned no video")
                        continue

                    # ENHANCED VALIDATION: Combined title + artist similarity
                    youtube_title = clean_title(video.get('title', ''))
                    youtube_artist = video.get('uploader', '') or video.get('channel', '')
                    expected_title = clean_title(metadata.title)
                    expected_artist = metadata.artist

                    title_sim = title_similarity(youtube_title, expected_title)
                    artist_sim = title_similarity(youtube_artist, expected_artist)
                    # Weight title 70%, artist 30%
                    similarity = (title_sim * 0.7) + (artist_sim * 0.3)

                    logger.info(f"Match: {similarity:.1f}% (YT: '{youtube_title}' by '{youtube_artist}' | Expected: '{expected_title}' by '{expected_artist}')")
                    
                    # LOWER THRESHOLD: 50% combined similarity (was 60% title-only)
                    if similarity < 50:
                        logger.warning(f"Low similarity ({similarity:.1f}%) — skipping")
                        continue

                    await loop.run_in_executor(None, ydl.download, [video['webpage_url']])

                file_path = os.path.join(self.download_dir, f"{metadata.id}.mp3")
                if not os.path.exists(file_path):
                    logger.warning(f"Download failed for strategy {strategy_idx + 1}")
                    continue

                # Duration validation (keep existing)
                try:
                    audio_file = MutagenMP3(file_path)
                    duration = audio_file.info.length
                    if duration < 60 or duration > 600:
                        logger.warning(f"❌ Invalid duration ({duration:.1f}s)")
                        os.remove(file_path)
                        continue
                except Exception as e:
                    logger.warning(f"Duration validation skipped: {e}")

                # File size validation (keep existing)
                file_size = os.path.getsize(file_path)
                if file_size < 1_000_000:
                    logger.warning(f"❌ File too small ({file_size/1024:.0f}KB)")
                    os.remove(file_path)
                    continue

                logger.info(f"✅ Download successful (strategy {strategy_idx + 1})")
                self._apply_metadata(file_path, metadata)
                return file_path

            except Exception as e:
                logger.error(f"Strategy {strategy_idx + 1} failed: {e}", exc_info=True)
                continue

        logger.error("❌ All YouTube strategies failed — using Apple Music preview")
        return None  # main.py will handle preview fallback

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
                        
                        # 🔹 ROUTE ARTWORK PROCESSING BY SOURCE
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
                            logger.info(f"✅ Embedded {source} artwork with HiiT Radio logo")
                        else:
                            logger.warning("Artwork processing returned None")
                    else:
                        logger.warning(f"Artwork fetch failed: {response.status_code}")
                except Exception as e:
                    logger.error(f"Artwork error: {e}", exc_info=True)
            else:
                logger.info("No artwork URL — sending audio without cover")

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
                logger.warning("❌ hiit-radio.png NOT FOUND")
                out = io.BytesIO()
                img.save(out, format="JPEG", quality=95)
                return out.getvalue()

            logo = Image.open(logo_path).convert("RGBA")
            logo_w = int(target_size * 0.25)  # 150px
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
            logger.error(f"❌ Apple/Spotify artwork failed: {e}", exc_info=True)
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
                logger.warning("❌ hiit-radio.png NOT FOUND")
                out = io.BytesIO()
                bordered.save(out, format="JPEG", quality=95)
                return out.getvalue()

            logo = Image.open(logo_path).convert("RGBA")
            logo_w = int(target_size * 0.3)  # 180px
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
            logger.error(f"❌ iTunes artwork failed: {e}", exc_info=True)
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