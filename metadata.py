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
        logger.error("❌ SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET missing in .env")
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
                    logger.info("✅ Spotify token acquired")
                    return _spotify_token
                else:
                    error_text = await resp.text()
                    logger.error(f"❌ Spotify auth failed ({resp.status}): {error_text}")
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
        self.preview_url = None  # 30s legal preview
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

            logger.info(f"✅ Extracted Spotify ID: {self.id}")

            token = await _get_spotify_token()
            if not token:
                return False

            async with aiohttp.ClientSession() as session:
                # 🔑 CRITICAL: ONLY Authorization header for track requests
                async with session.get(
                    f"https://api.spotify.com/v1/tracks/{self.id}",
                    headers={
                        'Authorization': f'Bearer {token}'  # ONLY THIS HEADER
                    }
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"Spotify API {resp.status}: {error_text}")
                        if resp.status == 403:
                            logger.error(
                                "→ 403 Forbidden: Spotify app NOT ACTIVATED in dashboard.\n"
                                "   FIX: https://developer.spotify.com/dashboard → Edit Settings →\n"
                                "   Add Redirect URI: http://localhost → Save → Wait for 'Activated' status"
                            )
                        elif resp.status == 404:
                            logger.error("→ Track not found. Verify link is for a SONG (not album/playlist).")
                        return False
                    data = await resp.json()

            self.title = data.get("name", "Unknown Track")
            artists = data.get("artists", [])
            self.artist = ", ".join(a["name"] for a in artists) if artists else "Unknown Artist"
            album = data.get("album", {})
            self.album = album.get("name", "Unknown Album")
            self.preview_url = data.get("preview_url")  # 30s legal preview
            
            images = album.get("images", [])
            if images:
                self.artwork_url = images[0].get("url", "")
                self.artwork_url = self.artwork_url.replace("640", "2000").replace("300", "2000")
            
            logger.info(f"✅ Spotify: '{self.title}' by '{self.artist}'")
            return True
            
        except Exception as e:
            logger.error(f"Spotify fetch error: {e}", exc_info=True)
            return False

class AppleMusicMetadata:
    """Handle Apple Music metadata extraction and iTunes search."""
    def __init__(self, url):
        self.url = url
        self.title = None
        self.artist = None
        self.album = None
        self.artwork_url = None
        self.preview_url = None  # 30s legal preview
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
                    og_audio = soup.find('meta', property='og:audio')  # 30s preview

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
                        if self.title and ' by ' in self.title:
                            parts = self.title.split(' by ')
                            self.title = parts[0]
                            self.artist = parts[1].replace(' on Apple Music', '').replace(' on Apple\u00a0Music', '').replace(' - Apple Music', '').strip()
                        elif self.title and ' - ' in self.title:
                            parts = self.title.split(' - ', 1)
                            if len(parts) == 2:
                                self.artist = parts[0].strip()
                                self.title = parts[1].replace(' on Apple Music', '').replace(' on Apple\u00a0Music', '').replace(' - Apple Music', '').strip()
                    
                    logger.info(f"Fetched meta: {self.title} by {self.artist}, artwork: {self.artwork_url}")
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
                    meta.preview_url = track.get('previewUrl')  # 30s legal preview
                    
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

    def __str__(self):
        return f"Type: {self.type}, Title: {self.title}, Artist: {self.artist}, Album: {self.album}, Artwork: {self.artwork_url}"