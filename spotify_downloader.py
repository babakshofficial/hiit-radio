import os
import sys
import shutil
import asyncio
import logging

logger = logging.getLogger(__name__)


class SpotifyFullDownloader:
    """Download the FULL track directly from Spotify using zotify (librespot).

    Requires a Spotify Premium account and a one-time generated credentials
    file. See the `README` / setup notes for how to create it. If zotify or the
    credentials are missing, ``is_configured()`` returns False and the caller
    should fall back to the YouTube/SoundCloud pipeline.
    """

    def __init__(self, download_dir="downloads", credentials_path=None, username=None):
        self.download_dir = download_dir
        self.credentials_path = credentials_path or os.getenv(
            "SPOTIFY_CREDENTIALS",
            os.path.join(os.path.dirname(__file__), "credentials.json"),
        )
        self.username = username or os.getenv("SPOTIFY_USERNAME", "")
        self.zotify_bin = self._find_zotify()

    def _find_zotify(self):
        candidate = os.path.join(os.path.dirname(sys.executable), "zotify")
        if os.path.exists(candidate):
            return candidate
        return shutil.which("zotify")

    def is_configured(self):
        """True if we can attempt a Spotify download (binary + credentials present)."""
        if not self.zotify_bin:
            logger.warning("zotify executable not found — Spotify full download unavailable")
            return False
        if not os.path.exists(self.credentials_path):
            logger.warning(
                f"Spotify credentials not found at '{self.credentials_path}' — "
                "run the one-time login to generate them"
            )
            return False
        return True

    async def download(self, spotify_url, track_id, timeout=240):
        """Download a full Spotify track. Returns the mp3 path or None on failure."""
        if not self.is_configured():
            return None
        if not spotify_url or "spotify.com" not in spotify_url:
            return None

        # Isolate each download in its own temp dir so we can reliably locate
        # the single resulting audio file regardless of zotify's naming/foldering.
        temp_dir = os.path.join(self.download_dir, f"_sp_{track_id}")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        os.makedirs(temp_dir, exist_ok=True)

        cmd = [
            self.zotify_bin,
            spotify_url,
            "--root-path", temp_dir,
            "--credentials-location", self.credentials_path,
            "--codec", "mp3",
            "--download-quality", "very_high",
            "--download-real-time", "False",
            "--disable-song-archive", "True",
            "--skip-existing", "False",
            "--skip-prev-downloaded", "False",
            "--no-splash",
            "--print-splash", "False",
            "--print-progress-info", "False",
            "--print-downloads", "False",
            "--print-download-progress", "False",
            "--print-url-progress", "False",
        ]
        if self.username:
            cmd += ["--username", self.username]

        logger.info(f"Spotify full download starting: {spotify_url}")
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                logger.error(f"Spotify download timed out after {timeout}s")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return None

            output = (stdout or b"").decode(errors="replace")
            if proc.returncode != 0:
                logger.error(f"zotify exited with code {proc.returncode}. Output:\n{output[-1500:]}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return None

            audio_file = self._find_audio_file(temp_dir)
            if not audio_file:
                logger.error(f"zotify finished but no audio file was produced. Output:\n{output[-1500:]}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return None

            final_path = os.path.join(self.download_dir, f"{track_id}.mp3")
            if os.path.exists(final_path):
                os.remove(final_path)
            shutil.move(audio_file, final_path)
            shutil.rmtree(temp_dir, ignore_errors=True)

            file_size = os.path.getsize(final_path)
            if file_size < 500_000:
                logger.warning(f"Spotify download suspiciously small ({file_size/1024:.0f}KB)")
            logger.info(f"Spotify full download succeeded: {final_path} ({file_size/1024/1024:.1f}MB)")
            return final_path

        except Exception as e:
            logger.error(f"Spotify download error: {e}", exc_info=True)
            shutil.rmtree(temp_dir, ignore_errors=True)
            return None

    def _find_audio_file(self, directory):
        """Return the largest audio file found under directory, or None."""
        exts = (".mp3", ".ogg", ".m4a", ".opus")
        best = None
        best_size = -1
        for root, _dirs, files in os.walk(directory):
            for name in files:
                if name.lower().endswith(exts):
                    path = os.path.join(root, name)
                    try:
                        size = os.path.getsize(path)
                    except OSError:
                        continue
                    if size > best_size:
                        best, best_size = path, size
        return best
