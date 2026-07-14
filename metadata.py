import aiohttp
import re
import difflib
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

_STOPWORDS = frozenset({
    "and", "the", "of", "a", "an", "feat", "ft", "featuring", "vs", "with",
})

_TITLE_HOOKS = frozenset({
    "dont", "don't", "wanna", "want", "love", "hate", "need", "feel", "know",
    "baby", "girl", "boy", "heart", "night", "never", "always", "still",
    "take", "make", "let", "get", "got", "gonna", "ain't", "wont", "won't",
    "cant", "can't", "here", "there", "away", "back", "again", "alone",
})


def score_query_coverage(query, title, artist):
    """Symmetric coverage of query tokens in title+artist (0-100).

    Used to gate YouTube/SoundCloud candidates when the query orientation
    (title-last vs artist-last) is ambiguous.
    """
    q_tokens = _query_tokens(query)
    if not q_tokens:
        return 0.0
    hay_tokens = _query_tokens(f"{title or ''} {artist or ''}")
    hay_text = f"{title or ''} {artist or ''}".lower()
    hits = sum(1 for t in q_tokens if _token_in_haystack(t, hay_tokens, hay_text))
    return 100.0 * hits / len(q_tokens)


def guess_title_artist(query):
    """Split free-text into (title, artist) without trusting a single orientation.

    Patterns:
    - "Oscar and the Wolf Breathe" → title=Breathe, artist=Oscar and the Wolf
    - "dont wanna be here naits" → title=dont wanna be here, artist=naits
    """
    q = (query or "").strip()
    if not q:
        return "", ""
    if re.search(r'\s+by\s+', q, re.I):
        parts = re.split(r'\s+by\s+', q, maxsplit=1, flags=re.I)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
    if " - " in q:
        left, right = q.split(" - ", 1)
        return left.strip(), right.strip()

    words = q.split()
    if len(words) < 2:
        return q, ""
    if len(words) == 2:
        # Ambiguous — prefer Title Artist (song then artist)
        return words[0], words[1]

    last = words[-1]
    rest = words[:-1]
    rest_l = " ".join(rest).lower()

    # Band-name cue: "X and the Y Title" → last word is the song title
    if re.search(r'\band\s+the\b', rest_l) or re.search(r'\b&\b', rest_l):
        return last, " ".join(rest)

    # Default chat pattern: "song title words … artist"
    return " ".join(rest), last


def _query_tokens(text):
    return [
        t for t in re.findall(r"\w+", (text or "").lower())
        if len(t) > 1 and t not in _STOPWORDS
    ]


def _token_in_haystack(token, haystack_tokens, haystack_text):
    """Exact or fuzzy (breathe≈breathing) presence of a query token."""
    if token in haystack_text:
        return True
    for w in haystack_tokens:
        if token == w:
            return True
        if len(token) >= 4 and len(w) >= 4:
            if token in w or w in token:
                return True
            # Shared stem "breath" in breathe/breathing
            prefix = min(len(token), len(w), 5)
            if token[:prefix] == w[:prefix] and prefix >= 5:
                return True
            if difflib.SequenceMatcher(None, token, w).ratio() >= 0.72:
                return True
    return False


def score_query_match(query, title, artist):
    """How well an iTunes hit matches a free-text user query (0-100).

    Requires title overlap so popular artist tracks don't win when the song
    name in the query is different. Prefers contiguous artist-phrase matches
    so 'Oscar and the Wolf' beats '… Oscar … Rad Wolf'.
    """
    q = (query or "").strip()
    if not q:
        return 0.0

    q_tokens = _query_tokens(q)
    if not q_tokens:
        return 0.0

    title_l = (title or "").lower()
    artist_l = (artist or "").lower()
    title_tokens = _query_tokens(title)
    artist_tokens = _query_tokens(artist)

    title_hits = sum(1 for t in q_tokens if _token_in_haystack(t, title_tokens, title_l))
    if title_hits == 0:
        return 0.0

    words = q.split()
    # Guess "Artist … Title" (last word = title) when query has no separators.
    artist_guess = ""
    title_guess = ""
    if len(words) >= 3:
        artist_guess = " ".join(words[:-1]).lower()
        title_guess = words[-1].lower()
    elif len(words) == 2:
        artist_guess, title_guess = words[0].lower(), words[1].lower()

    artist_phrase_sim = 0.0
    if artist_guess:
        artist_phrase_sim = difflib.SequenceMatcher(None, artist_guess, artist_l).ratio() * 100.0
        # Also compare against cleaned artist without featured junk
        artist_clean = re.split(r'\s*(?:feat\.?|ft\.?|&|,)\s*', artist_l, maxsplit=1)[0].strip()
        artist_phrase_sim = max(
            artist_phrase_sim,
            difflib.SequenceMatcher(None, artist_guess, artist_clean).ratio() * 100.0,
        )

    title_focus = 0.0
    if title_guess:
        if _token_in_haystack(title_guess, title_tokens, title_l):
            # Prefer compact titles (Breathing) over long ones (Breathe of Life …)
            compactness = min(1.0, (len(title_guess) + 2) / max(len(title_l), 1))
            title_focus = 50.0 + 50.0 * compactness
            title_focus = max(
                title_focus,
                difflib.SequenceMatcher(None, title_guess, title_l).ratio() * 100.0,
            )

    coverage = (
        sum(
            1 for t in q_tokens
            if _token_in_haystack(t, title_tokens + artist_tokens, f"{title_l} {artist_l}")
        )
        / len(q_tokens)
    ) * 100.0

    # Strong contiguous artist match is required for multi-word artist queries.
    if artist_guess and len(_query_tokens(artist_guess)) >= 2 and artist_phrase_sim < 55.0:
        return 0.0

    score = coverage * 0.35 + artist_phrase_sim * 0.4 + title_focus * 0.25
    return min(score, 100.0)


def _itunes_query_variants(query):
    """Reorder free-text queries so iTunes can find Artist+Title better."""
    q = (query or "").strip()
    if not q:
        return []
    variants = [q]
    words = q.split()
    if len(words) >= 3:
        # Treat last word as title: "Artist words … Title"
        artist, title = " ".join(words[:-1]), words[-1]
        variants.append(f"{title} {artist}")
        variants.append(f"{artist} {title}")
        if len(words) >= 4:
            artist2, title2 = " ".join(words[:-2]), " ".join(words[-2:])
            variants.append(f"{title2} {artist2}")
            variants.append(f"{artist2} {title2}")
    # dedupe preserving order
    seen = set()
    out = []
    for v in variants:
        key = v.lower()
        if key not in seen:
            seen.add(key)
            out.append(v)
    return out

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
        self.duration = None  # seconds
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
            duration_ms = data.get("duration_ms")
            if duration_ms:
                self.duration = float(duration_ms) / 1000.0

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

            duration_ms = entity.get("duration") or entity.get("durationMs") or entity.get("duration_ms")
            if duration_ms:
                try:
                    ms = float(duration_ms)
                    self.duration = ms / 1000.0 if ms > 1000 else ms
                except (TypeError, ValueError):
                    pass

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
        self.duration = None  # seconds
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
                                                        ms = result.get('trackTimeMillis')
                                                        if ms:
                                                            self.duration = float(ms) / 1000.0
                                                        break
                        except Exception as e:
                            logger.warning(f"iTunes Lookup fallback failed: {e}")

                    logger.info(f"Fetched meta: {self.title} by {self.artist}, artwork: {self.artwork_url}, preview: {self.preview_url}")
                    return True
        except Exception as e:
            logger.error(f"Error fetching meta: {e}", exc_info=True)
            return False

    @classmethod
    def _meta_from_itunes_track(cls, track, query=""):
        meta = cls(None)
        meta.title = track.get("trackName", query)
        meta.artist = track.get("artistName", "")
        meta.album = track.get("collectionName", "")
        meta.preview_url = track.get("previewUrl")
        ms = track.get("trackTimeMillis")
        if ms:
            meta.duration = float(ms) / 1000.0
        artwork = track.get("artworkUrl100", "")
        if artwork:
            high_res = artwork.replace("100x100bb", "3000x3000bb")
            high_res = high_res.replace("100x100", "3000x3000")
            high_res = high_res.replace("600x600bb", "3000x3000bb")
            meta.artwork_url = high_res
        meta.type = "search"
        meta.id = str(track.get("trackId", abs(hash(query))))
        return meta

    @classmethod
    async def _itunes_raw_search(cls, query, limit=10):
        encoded_query = urllib.parse.quote(query)
        url = (
            f"https://itunes.apple.com/search?term={encoded_query}"
            f"&media=music&entity=song&limit={limit}"
        )
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://music.apple.com/",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    text = await response.text()
                    data = json.loads(text)
            return data.get("results", [])[:limit]
        except Exception as e:
            logger.error(f"iTunes search failed for {query!r}: {e}", exc_info=True)
            return []

    @classmethod
    async def search_by_query(cls, query, min_score=55.0):
        """Search iTunes and return the best query-relevant track, or None.

        Never blindly trusts result #1 — Apple often inserts unrelated chart
        hits. Scores candidates against the user query and tries title/artist
        reorderings when needed.
        """
        if not query or len(query.strip()) < 3:
            return None

        best_meta = None
        best_score = -1.0
        seen_ids = set()

        for variant in _itunes_query_variants(query):
            tracks = await cls._itunes_raw_search(variant, limit=10)
            for track in tracks:
                tid = track.get("trackId")
                if tid in seen_ids:
                    continue
                if tid is not None:
                    seen_ids.add(tid)
                title = track.get("trackName", "")
                artist = track.get("artistName", "")
                # Score against the *original* user query, not just the variant.
                score = score_query_match(query, title, artist)
                logger.info(
                    f"iTunes candidate {score:.0f}%: '{title}' by '{artist}' (query={variant!r})"
                )
                if score > best_score:
                    best_score = score
                    best_meta = cls._meta_from_itunes_track(track, query)
            # Stop early if we already have a strong match.
            if best_score >= 80.0:
                break

        if best_meta and best_score >= min_score:
            logger.info(
                f"iTunes search picked {best_score:.0f}%: "
                f"'{best_meta.title}' by '{best_meta.artist}'"
            )
            return best_meta

        logger.warning(
            f"iTunes search: no relevant match for {query!r} "
            f"(best={best_score:.0f}%, need>={min_score:.0f}%)"
        )
        return None

    @classmethod
    async def search_many(cls, query, limit=5):
        """Search iTunes and return up to ``limit`` relevance-ranked tracks."""
        tracks = await cls._itunes_raw_search(query, limit=max(limit * 2, 10))
        scored = []
        for track in tracks:
            title = track.get("trackName", "")
            artist = track.get("artistName", "")
            score = score_query_match(query, title, artist)
            if score <= 0:
                continue
            scored.append((score, track))
        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, track in scored[:limit]:
            results.append(cls._meta_from_itunes_track(track, query))
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

    def _track_from_api_item(self, item, default_album=None, default_artwork=None):
        """Normalize a track from album or playlist API response."""
        t = item.get('item') or item.get('track') or item
        if not t or t.get('type') != 'track':
            return None
        meta = TrackMetadata()
        meta.title = t.get('name')
        artists = t.get('artists', [])
        meta.artist = ", ".join(a['name'] for a in artists if a.get('name'))
        album = t.get('album') or {}
        meta.album = album.get('name') or default_album
        meta.id = t.get('id') or str(abs(hash(meta.title or "")))
        meta.url = f"https://open.spotify.com/track/{meta.id}"
        meta.type = 'track'
        duration_ms = t.get('duration_ms')
        if duration_ms:
            meta.duration = float(duration_ms) / 1000.0
        images = album.get('images', [])
        if images:
            meta.artwork_url = images[0].get('url', '')
        elif default_artwork:
            meta.artwork_url = default_artwork
        return meta

    def _artwork_from_entity(self, entity):
        """Best-effort cover art URL from an embed entity dict."""
        cover_art = entity.get("coverArt") or {}
        sources = cover_art.get("sources") or []
        if sources:
            best = max(sources, key=lambda s: s.get("width") or 0)
            return best.get("url")
        visual = entity.get("visualIdentity") or {}
        images = visual.get("image") or []
        if images:
            return images[0].get("url")
        return None

    def _tracks_from_embed_entity(self, entity):
        """Build TrackMetadata list from embed page entity.trackList."""
        track_list = entity.get("trackList") or []
        if not track_list:
            return []
        collection_name = entity.get("name") or entity.get("title")
        artwork = self._artwork_from_entity(entity)
        self.name = collection_name or self.name
        default_artist = None
        artists = entity.get("artists") or []
        if artists:
            names = [a.get("name", "") for a in artists if isinstance(a, dict) and a.get("name")]
            if names:
                default_artist = ", ".join(names)
        tracks = []
        for item in track_list:
            if not isinstance(item, dict):
                continue
            uri = item.get("uri") or ""
            track_id = uri.split(":")[-1] if ":" in uri else None
            if not track_id:
                continue
            meta = TrackMetadata()
            meta.title = item.get("title") or item.get("name")
            item_artists = item.get("artists") or []
            artist_names = [
                a.get("name", "") for a in item_artists
                if isinstance(a, dict) and a.get("name")
            ]
            if artist_names:
                meta.artist = ", ".join(artist_names)
            else:
                meta.artist = item.get("subtitle") or default_artist or "Unknown Artist"
            meta.album = collection_name
            meta.id = track_id
            meta.url = f"https://open.spotify.com/track/{track_id}"
            meta.type = "track"
            meta.artwork_url = artwork
            duration_ms = item.get("duration") or item.get("durationMs") or item.get("duration_ms")
            if duration_ms:
                try:
                    ms = float(duration_ms)
                    meta.duration = ms / 1000.0 if ms > 1000 else ms
                except (TypeError, ValueError):
                    pass
            if meta.title:
                tracks.append(meta)
        return tracks

    async def _fetch_from_embed(self):
        """No-auth fallback: parse track list from public Spotify embed page."""
        try:
            embed_url = f"https://open.spotify.com/embed/{self.collection_type}/{self.collection_id}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(embed_url, headers=headers) as resp:
                    if resp.status != 200:
                        logger.error(f"Spotify collection embed fetch failed: {resp.status}")
                        return []
                    html = await resp.text()

            match = re.search(
                r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
                html, re.DOTALL
            )
            if not match:
                logger.error("Spotify collection embed: __NEXT_DATA__ payload not found")
                return []

            data = json.loads(match.group(1))
            entity = None
            try:
                entity = data["props"]["pageProps"]["state"]["data"]["entity"]
            except (KeyError, TypeError):
                entity = None

            if not isinstance(entity, dict) or not entity.get("trackList"):
                def find_collection_entity(node):
                    if isinstance(node, dict):
                        if node.get("trackList"):
                            return node
                        for v in node.values():
                            found = find_collection_entity(v)
                            if found:
                                return found
                    elif isinstance(node, list):
                        for v in node:
                            found = find_collection_entity(v)
                            if found:
                                return found
                    return None
                entity = find_collection_entity(data) or {}

            tracks = self._tracks_from_embed_entity(entity)
            if tracks:
                logger.info(
                    f"Spotify collection (embed): {len(tracks)} tracks from "
                    f"{self.collection_type} '{self.name or self.collection_id}'"
                )
            else:
                logger.error("Spotify collection embed: no tracks found in entity")
            return tracks
        except Exception as e:
            logger.error(f"Spotify collection embed fallback error: {e}", exc_info=True)
            return []

    async def _fetch_from_api(self):
        """Fetch tracks via official Spotify Web API. Returns [] on failure."""
        token = await _get_spotify_token()
        if not token:
            return []
        tracks = []
        offset = 0
        limit = 50
        endpoint = (
            f"https://api.spotify.com/v1/albums/{self.collection_id}/tracks"
            if self.collection_type == "album"
            else f"https://api.spotify.com/v1/playlists/{self.collection_id}/items"
        )
        headers = {'Authorization': f'Bearer {token}'}
        try:
            async with aiohttp.ClientSession() as session:
                while True:
                    sep = '&' if '?' in endpoint else '?'
                    url = f"{endpoint}{sep}limit={limit}&offset={offset}"
                    async with session.get(url, headers=headers) as resp:
                        if resp.status != 200:
                            error_text = await resp.text()
                            logger.error(f"Spotify collection API {resp.status}: {error_text}")
                            return []
                        data = await resp.json()
                    items = data.get('items', [])
                    if not items:
                        break
                    for item in items:
                        meta = self._track_from_api_item(item)
                        if meta:
                            tracks.append(meta)
                    if self.collection_type == 'album':
                        break
                    if not data.get('next'):
                        break
                    offset += limit
            if tracks:
                logger.info(
                    f"Spotify collection (API): {len(tracks)} tracks from "
                    f"{self.collection_type} '{self.collection_id}'"
                )
            return tracks
        except Exception as e:
            logger.error(f"Spotify collection API fetch error: {e}", exc_info=True)
            return []

    async def fetch_tracks(self):
        if not self._parse_id():
            return []
        tracks = await self._fetch_from_api()
        if tracks:
            return tracks
        logger.warning("Spotify collection API unavailable — falling back to public embed page")
        return await self._fetch_from_embed()


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
        self.duration = None  # seconds, when known from source metadata
        self.type = None
        self.id = None
        self.url = None
        self.search_query = None  # original free-text query when iTunes is skipped

    def _copy_from(self, source, url=None):
        self.title = getattr(source, "title", None)
        self.artist = getattr(source, "artist", None)
        self.album = getattr(source, "album", None)
        self.artwork_url = getattr(source, "artwork_url", None)
        self.preview_url = getattr(source, "preview_url", None)
        self.duration = getattr(source, "duration", None)
        self.type = getattr(source, "type", None)
        self.id = getattr(source, "id", None)
        self.url = url if url is not None else getattr(source, "url", None)
        self.search_query = getattr(source, "search_query", None)
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
            meta.search_query = query
            return meta

        # Smart title/artist guess, then retry iTunes with both orientations.
        title, artist = guess_title_artist(query)
        for variant in (
            f"{title} {artist}".strip(),
            f"{artist} {title}".strip(),
            query,
        ):
            if not variant:
                continue
            source = await AppleMusicMetadata.search_by_query(variant)
            if source:
                # Keep only if still relevant to the *original* query.
                if score_query_coverage(query, source.title, source.artist) >= 55:
                    meta._copy_from(source, url=None)
                    meta.search_query = query
                    return meta

        meta.title = title or query
        meta.artist = artist
        meta.search_query = query
        meta.id = str(abs(hash(query)))
        meta.type = "search"
        logger.info(
            f"Plain-query fallback metadata: '{meta.title}' by '{meta.artist}' "
            f"(from {query!r})"
        )
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
            name = coll.name or (tracks[0].album if tracks else "Spotify collection")
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
                    ms = item.get('trackTimeMillis')
                    if ms:
                        meta.duration = float(ms) / 1000.0
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