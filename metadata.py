import aiohttp
import re
from bs4 import BeautifulSoup
import logging
import urllib.parse
import json
import base64
import time
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Spotify token cache
_spotify_token = None
_spotify_token_expiry = 0

async def _get_spotify_token():
    global _spotify_token, _spotify_token_expiry
    now = time.time()
    if _spotify_token and now < _spotify_token_expiry:
        return _spotify_token

    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        logger.error("SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET missing in .env")
        return None

    auth_str = f"{client_id}:{client_secret}"
    auth_b64 = base64.b64encode(auth_str.encode()).decode()
    
    try:
        async with aiohttp.ClientSession() as session:
            # Token request requires Content-Type + User-Agent
            async with session.post(
                "https://accounts.spotify.com/api/token",
                headers={
                    'Authorization': f'Basic {auth_b64}',
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'User-Agent': 'HiiTRadioBot/1.0'
                },
                data={"grant_type": "client_credentials"}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    _spotify_token = data["access_token"]
                    _spotify_token_expiry = now + data["expires_in"] - 60
                    logger.info("Spotify token acquired")
                    return _spotify_token
                else:
                    error_text = await resp.text()
                    logger.error(f"Spotify auth failed ({resp.status}): {error_text}")
                    return None
    except Exception as e:
        logger.error(f"Spotify token error: {e}", exc_info=True)
        return None

class SpotifyMetadata:
    """Handle Spotify track metadata extraction."""
    def __init__(self, url):
        self.url = url
        self.title = None
        self.artist = None
        self.album = None
        self.artwork_url = None
        self.preview_url = None
        self.type = "track"
        self.id = None

    async def fetch(self):
        if not self.url:
            return False
        try:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(self.url)
            path_parts = [p for p in parsed.path.split("/") if p]
            
            if len(path_parts) >= 2 and path_parts[0] == "track":
                self.id = path_parts[1].strip()
            elif "track" in parse_qs(parsed.query):
                self.id = parse_qs(parsed.query)["track"][0].strip()
            else:
                logger.error(f"Invalid Spotify URL format: {self.url}")
                return False

            if len(self.id) != 22 or not self.id.replace("_", "").replace("-", "").isalnum():
                logger.error(f"Invalid Spotify track ID: '{self.id}'")
                return False

            logger.info(f"Extracted Spotify ID: {self.id}")

            # Preferred path: official Web API (richest metadata).
            if await self._fetch_from_api():
                return True

            # No-auth fallback: scrape the public embed page. This rescues cases
            # where the API is unavailable — e.g. 403 "premium subscription
            # required", missing credentials, or rate limiting.
            logger.warning("Spotify API unavailable — falling back to public embed page")
            return await self._fetch_from_embed()
        except Exception as e:
            logger.error(f"Spotify fetch error: {e}", exc_info=True)
            return False

    async def _fetch_from_api(self):
        """Fetch track metadata via the official Spotify Web API. Returns True on success."""
        token = await _get_spotify_token()
        if not token:
            return False
        try:
            async with aiohttp.ClientSession() as session:
                # CRITICAL: ONLY Authorization header for track requests
                async with session.get(
                    f"https://api.spotify.com/v1/tracks/{self.id}",
                    headers={'Authorization': f'Bearer {token}'}
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"Spotify API {resp.status}: {error_text}")
                        if resp.status == 403:
                            logger.error("403 Forbidden: app lacks Web API access (activation/premium required).")
                        elif resp.status == 404:
                            logger.error("Track not found. Verify link is for a SONG.")
                        return False
                    data = await resp.json()

            self.title = data.get("name", "Unknown Track")
            artists = data.get("artists", [])
            self.artist = ", ".join(a["name"] for a in artists) if artists else "Unknown Artist"
            album = data.get("album", {})
            self.album = album.get("name", "Unknown Album")
            self.preview_url = data.get("preview_url")

            images = album.get("images", [])
            if images:
                self.artwork_url = images[0].get("url", "")
                self.artwork_url = self.artwork_url.replace("640", "2000").replace("300", "2000")

            logger.info(f"Spotify (API): '{self.title}' by '{self.artist}'")
            return True
        except Exception as e:
            logger.error(f"Spotify API fetch error: {e}", exc_info=True)
            return False

    async def _fetch_from_embed(self):
        """No-auth fallback: parse metadata from the public Spotify embed page.

        The embed page ships a __NEXT_DATA__ JSON blob containing title,
        artists, cover art and (usually) a 30s preview URL — no token needed.
        """
        try:
            embed_url = f"https://open.spotify.com/embed/track/{self.id}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(embed_url, headers=headers) as resp:
                    if resp.status != 200:
                        logger.error(f"Spotify embed fetch failed: {resp.status}")
                        return False
                    html = await resp.text()

            match = re.search(
                r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
                html, re.DOTALL
            )
            if not match:
                logger.error("Spotify embed: __NEXT_DATA__ payload not found")
                return False

            data = json.loads(match.group(1))

            # Locate the track entity. The canonical path is
            # props.pageProps.state.data.entity, but be defensive: fall back to a
            # recursive search for the first dict that looks like a track entity.
            entity = None
            try:
                entity = data["props"]["pageProps"]["state"]["data"]["entity"]
            except (KeyError, TypeError):
                entity = None

            if not isinstance(entity, dict) or not (entity.get("title") or entity.get("name")):
                def find_entity(node):
                    if isinstance(node, dict):
                        if (node.get("title") or node.get("name")) and (
                            "artists" in node or "audioPreview" in node or "coverArt" in node
                        ):
                            return node
                        for v in node.values():
                            found = find_entity(v)
                            if found:
                                return found
                    elif isinstance(node, list):
                        for v in node:
                            found = find_entity(v)
                            if found:
                                return found
                    return None
                entity = find_entity(data) or {}

            self.title = entity.get("title") or entity.get("name") or self.title or "Unknown Track"

            artists = entity.get("artists") or []
            names = [a.get("name", "") for a in artists if isinstance(a, dict) and a.get("name")]
            if names:
                self.artist = ", ".join(names)
            elif entity.get("subtitle"):
                self.artist = entity.get("subtitle")
            elif not self.artist:
                self.artist = "Unknown Artist"

            sources = (entity.get("coverArt") or {}).get("sources") or []
            if sources:
                best = max(sources, key=lambda s: s.get("width") or 0)
                self.artwork_url = best.get("url")

            preview = entity.get("audioPreview") or {}
            if preview.get("url"):
                self.preview_url = preview["url"]

            logger.info(f"Spotify (embed): '{self.title}' by '{self.artist}'")
            return bool(self.title and self.title != "Unknown Track")
        except Exception as e:
            logger.error(f"Spotify embed fallback error: {e}", exc_info=True)
            return False

class AppleMusicMetadata:
    """Handle Apple Music metadata extraction and iTunes search."""
    def __init__(self, url):
        self.url = url
        self.title = None
        self.artist = None
        self.album = None
        self.artwork_url = None
        self.preview_url = None
        self.type = None
        self.id = None

    async def fetch(self):
        if not self.url:
            return False
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(self.url, headers=headers) as response:
                    if response.status != 200:
                        logger.error(f"Failed to fetch URL: {self.url}, status: {response.status}")
                        return False
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    og_title = soup.find('meta', property='og:title')
                    og_image = soup.find('meta', property='og:image')
                    og_audio = soup.find('meta', property='og:audio')

                    if og_title:
                        self.title = og_title['content']
                    
                    if og_image:
                        image_url = og_image['content']
                        if '200x200bb' in image_url:
                            image_url = image_url.replace('200x200bb', '3000x3000bb')
                        elif '200x200' in image_url:
                            image_url = image_url.replace('200x200', '3000x3000')
                        self.artwork_url = image_url

                    if og_audio:
                        self.preview_url = og_audio['content']

                    parsed_url = urllib.parse.urlparse(self.url)
                    path_parts = parsed_url.path.split('/')
                    
                    if '/album/' in self.url:
                        if '?i=' in self.url:
                            self.type = 'song'
                            query_params = urllib.parse.parse_qs(parsed_url.query)
                            song_ids = query_params.get('i', [])
                            if song_ids:
                                self.id = song_ids[0]
                            else:
                                self.id = self.url.split('?i=')[1].split('&')[0] if '?i=' in self.url else path_parts[-1]
                        else:
                            self.type = 'album'
                            album_idx = path_parts.index('album') if 'album' in path_parts else -1
                            if album_idx != -1 and album_idx + 2 < len(path_parts):
                                self.id = path_parts[album_idx + 2]
                            else:
                                self.id = path_parts[-1]
                    elif '/playlist/' in self.url:
                        self.type = 'playlist'
                        playlist_idx = path_parts.index('playlist') if 'playlist' in path_parts else -1
                        if playlist_idx != -1 and playlist_idx + 2 < len(path_parts):
                            self.id = path_parts[playlist_idx + 2]
                        else:
                            self.id = path_parts[-1]
                    
                    if 'artist' in path_parts:
                        artist_idx = path_parts.index('artist')
                        if artist_idx + 1 < len(path_parts):
                            if self.type == 'song' and not self.artist:
                                artist_elem = soup.find('p', class_='songs-table__row__text__attribution')
                                if not artist_elem:
                                    artist_elem = soup.find(string=re.compile(r'by\s+.*', re.IGNORECASE))
                                    if artist_elem and 'by' in artist_elem.lower():
                                        self.artist = artist_elem.split('by')[1].strip() if 'by' in artist_elem.lower() else None
                    else:
                        # Helper to strip "on Apple Music" or "- Apple Music" regardless of hidden Unicode spaces
                        def clean_apple_text(text):
                            if not text: return ""
                            text = re.sub(r'\s*on\s+Apple\s*Music.*$', '', text, flags=re.IGNORECASE)
                            text = re.sub(r'\s*[-–]\s*Apple\s*Music.*$', '', text, flags=re.IGNORECASE)
                            return text.strip()

                        if self.title and ' by ' in self.title:
                            parts = self.title.split(' by ')
                            self.title = clean_apple_text(parts[0])
                            self.artist = clean_apple_text(parts[1])
                        elif self.title and ' - ' in self.title:
                            parts = self.title.split(' - ', 1)
                            if len(parts) == 2:
                                self.artist = clean_apple_text(parts[0])
                                self.title = clean_apple_text(parts[1])

                    # Robust fallback for preview URL using iTunes Lookup API
                    if not self.preview_url and self.id:
                        try:
                            clean_id = str(self.id).lstrip('-')
                            if clean_id.isdigit():
                                lookup_url = f"https://itunes.apple.com/lookup?id={clean_id}"
                                async with aiohttp.ClientSession() as lookup_session:
                                    async with lookup_session.get(lookup_url) as lookup_resp:
                                        if lookup_resp.status == 200:
                                            text = await lookup_resp.text()
                                            data = json.loads(text)
                                            if data.get('resultCount', 0) > 0:
                                                for result in data['results']:
                                                    if result.get('wrapperType') == 'track' and result.get('kind') == 'song':
                                                        if result.get('previewUrl'):
                                                            self.preview_url = result['previewUrl']
                                                            logger.info("Got preview URL from iTunes Lookup API fallback")
                                                            break
                        except Exception as e:
                            logger.warning(f"iTunes Lookup fallback failed: {e}")

                    logger.info(f"Fetched meta: {self.title} by {self.artist}, artwork: {self.artwork_url}, preview: {self.preview_url}")
                    return True
        except Exception as e:
            logger.error(f"Error fetching meta: {e}", exc_info=True)
            return False

    @classmethod
    async def search_by_query(cls, query):
        """Search iTunes API and upgrade artwork to max resolution."""
        encoded_query = urllib.parse.quote(query)
        url = f"https://itunes.apple.com/search?term={encoded_query}&media=music&entity=song&limit=1"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://music.apple.com/',
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    try:
                        text = await response.text()
                        data = json.loads(text)
                    except json.JSONDecodeError:
                        return None

                    if data.get('resultCount', 0) < 1:
                        return None

                    track = data['results'][0]
                    meta = cls(None)
                    meta.title = track.get('trackName', query)
                    meta.artist = track.get('artistName', '')
                    meta.album = track.get('collectionName', '')
                    meta.preview_url = track.get('previewUrl')
                    
                    artwork = track.get('artworkUrl100', '')
                    if artwork:
                        high_res = artwork.replace('100x100bb', '3000x3000bb')
                        high_res = high_res.replace('100x100', '3000x3000')
                        high_res = high_res.replace('600x600bb', '3000x3000bb')
                        meta.artwork_url = high_res
                    meta.type = 'search'
                    meta.id = str(track.get('trackId', hash(query)))
                    logger.info(f"iTunes search: {meta.title} by {meta.artist}")
                    return meta
        except Exception as e:
            logger.error(f"iTunes search failed: {e}", exc_info=True)
            return None

    @classmethod
    async def search_many(cls, query, limit=5):
        """Search iTunes and return up to ``limit`` AppleMusicMetadata track objects."""
        encoded_query = urllib.parse.quote(query)
        url = f"https://itunes.apple.com/search?term={encoded_query}&media=music&entity=song&limit={limit}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        results = []
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    data = json.loads(await response.text())
            for track in data.get('results', [])[:limit]:
                meta = cls(None)
                meta.title = track.get('trackName', query)
                meta.artist = track.get('artistName', '')
                meta.album = track.get('collectionName', '')
                meta.preview_url = track.get('previewUrl')
                artwork = track.get('artworkUrl100', '')
                if artwork:
                    meta.artwork_url = artwork.replace('100x100bb', '3000x3000bb').replace('100x100', '3000x3000')
                meta.type = 'search'
                meta.id = str(track.get('trackId', abs(hash(query))))
                results.append(meta)
        except Exception as e:
            logger.error(f"iTunes multi-search failed: {e}")
        return results

    @classmethod
    async def lookup_album_tracks(cls, album_id):
        """Return list of iTunes track result dicts for an album."""
        url = f"https://itunes.apple.com/lookup?id={album_id}&entity=song"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    data = json.loads(await resp.text())
            return [
                item for item in data.get('results', [])
                if item.get('wrapperType') == 'track' and item.get('kind') == 'song'
            ]
        except Exception as e:
            logger.error(f"iTunes album lookup failed: {e}")
            return []

    def __str__(self):
        return f"Type: {self.type}, Title: {self.title}, Artist: {self.artist}, Album: {self.album}, Artwork: {self.artwork_url}"


class SpotifyCollection:
    """Expand Spotify album/playlist URLs into track lists."""

    def __init__(self, url):
        self.url = url
        self.collection_type = None
        self.collection_id = None
        self.name = None

    def _parse_id(self):
        from urllib.parse import urlparse
        parsed = urlparse(self.url)
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) >= 2 and parts[0] in ("album", "playlist"):
            self.collection_type = parts[0]
            self.collection_id = parts[1].split("?")[0]
            return True
        return False

    async def fetch_tracks(self):
        if not self._parse_id():
            return []
        token = await _get_spotify_token()
        if not token:
            return []
        tracks = []
        offset = 0
        limit = 50
        endpoint = (
            f"https://api.spotify.com/v1/albums/{self.collection_id}/tracks"
            if self.collection_type == "album"
            else f"https://api.spotify.com/v1/playlists/{self.collection_id}/tracks"
        )
        headers = {'Authorization': f'Bearer {token}'}
        try:
            async with aiohttp.ClientSession() as session:
                while True:
                    sep = '&' if '?' in endpoint else '?'
                    url = f"{endpoint}{sep}limit={limit}&offset={offset}"
                    async with session.get(url, headers=headers) as resp:
                        if resp.status != 200:
                            logger.error(f"Spotify collection API {resp.status}")
                            break
                        data = await resp.json()
                    items = data.get('items', [])
                    if not items:
                        break
                    for item in items:
                        t = item.get('track') or item
                        if not t or t.get('type') != 'track':
                            continue
                        meta = TrackMetadata()
                        meta.title = t.get('name')
                        artists = t.get('artists', [])
                        meta.artist = ", ".join(a['name'] for a in artists if a.get('name'))
                        album = t.get('album') or {}
                        meta.album = album.get('name')
                        meta.id = t.get('id') or str(abs(hash(meta.title)))
                        meta.url = f"https://open.spotify.com/track/{meta.id}"
                        meta.type = 'track'
                        images = album.get('images', [])
                        if images:
                            meta.artwork_url = images[0].get('url', '')
                        tracks.append(meta)
                    if self.collection_type == 'album':
                        break
                    if not data.get('next'):
                        break
                    offset += limit
            return tracks
        except Exception as e:
            logger.error(f"Spotify collection fetch error: {e}")
            return []


class TrackMetadata:
    """Unified entry point for turning any user input (Spotify link, Apple Music
    link, or a plain search query) into normalised track metadata.

    Always returns a TrackMetadata instance. On failure the instance has
    ``title = None`` so callers can simply check ``if not metadata.title``.
    """

    def __init__(self):
        self.title = None
        self.artist = None
        self.album = None
        self.artwork_url = None
        self.preview_url = None
        self.type = None
        self.id = None
        self.url = None

    def _copy_from(self, source, url=None):
        self.title = getattr(source, "title", None)
        self.artist = getattr(source, "artist", None)
        self.album = getattr(source, "album", None)
        self.artwork_url = getattr(source, "artwork_url", None)
        self.preview_url = getattr(source, "preview_url", None)
        self.type = getattr(source, "type", None)
        self.id = getattr(source, "id", None)
        self.url = url if url is not None else getattr(source, "url", None)
        return self

    @classmethod
    async def create(cls, text):
        meta = cls()
        if not text:
            return meta
        text = text.strip()

        # SPOTIFY LINK
        if "spotify.com" in text:
            source = SpotifyMetadata(text)
            if await source.fetch():
                meta._copy_from(source, url=text)
            else:
                logger.error("Spotify metadata extraction failed")
            return meta

        # APPLE MUSIC LINK
        if "music.apple.com" in text:
            source = AppleMusicMetadata(text)
            if await source.fetch():
                meta._copy_from(source, url=text)
            else:
                logger.error("Apple Music metadata extraction failed")
            return meta

        # PLAIN TEXT SEARCH QUERY
        query = text
        if len(query) < 3:
            logger.warning("Search query too short")
            return meta

        source = await AppleMusicMetadata.search_by_query(query)
        if source:
            meta._copy_from(source, url=None)
            return meta

        # Fallback: parse "Title by Artist" / "Artist - Title" from the raw query
        title, artist = query, ""
        if re.search(r'\s+by\s+', query, re.IGNORECASE):
            parts = re.split(r'\s+by\s+', query, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) == 2:
                title, artist = parts[0].strip(), parts[1].strip()
        elif " - " in query:
            parts = query.split(" - ", 1)
            if len(parts) == 2:
                artist, title = parts[0].strip(), parts[1].strip()

        meta.title = title
        meta.artist = artist
        meta.id = str(abs(hash(query)))
        meta.type = "search"
        return meta

    @classmethod
    async def create_collection(cls, text):
        """Return (collection_name, list[TrackMetadata]) for album/playlist URLs, else ([], [])."""
        text = (text or "").strip()
        if not text:
            return None, []

        # Spotify album/playlist
        if "spotify.com" in text and ("/album/" in text or "/playlist/" in text):
            coll = SpotifyCollection(text)
            tracks = await coll.fetch_tracks()
            name = tracks[0].album if tracks else "Spotify collection"
            return name, tracks

        # Apple Music album/playlist
        if "music.apple.com" in text:
            source = AppleMusicMetadata(text)
            if not await source.fetch():
                return None, []
            if source.type == 'album' and source.id:
                raw_tracks = await AppleMusicMetadata.lookup_album_tracks(source.id)
                tracks = []
                for item in raw_tracks:
                    meta = cls()
                    meta.title = item.get('trackName')
                    meta.artist = item.get('artistName', source.artist)
                    meta.album = item.get('collectionName', source.album)
                    meta.id = str(item.get('trackId', abs(hash(meta.title))))
                    meta.url = text
                    meta.type = 'song'
                    artwork = item.get('artworkUrl100', '')
                    if artwork:
                        meta.artwork_url = artwork.replace('100x100bb', '3000x3000bb')
                    tracks.append(meta)
                return source.title or source.album, tracks
            if source.type == 'playlist':
                # iTunes has no public playlist API — search by playlist title
                if source.title:
                    results = await AppleMusicMetadata.search_many(source.title, limit=20)
                    tracks = [cls()._copy_from(r) for r in results]
                    return source.title, tracks

        return None, []

    @classmethod
    async def is_collection_url(cls, text):
        text = (text or "").strip()
        if "spotify.com" in text and ("/album/" in text or "/playlist/" in text):
            return True
        if "music.apple.com" in text and ("/album/" in text or "/playlist/" in text):
            if "?i=" in text:
                return False  # single song on album page
            return True
        return False

    def __str__(self):
        return f"Type: {self.type}, Title: {self.title}, Artist: {self.artist}, Album: {self.album}, Artwork: {self.artwork_url}"