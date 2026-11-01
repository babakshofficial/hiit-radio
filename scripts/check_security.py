#!/usr/bin/env python3
"""Security regression checks (no Telegram or internet access). Run from repo root."""
import asyncio
import hashlib
import hmac
import http.server
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

WORK = tempfile.mkdtemp(prefix="hiit-security-check-")
BOT_TOKEN = "123456:security-check-token"
JWT_SECRET = "s" * 40
AGENT_SECRET = "agent-secret-value"
ADMIN_ID = "1000"
os.environ.update(
    BOT_TOKEN=BOT_TOKEN,
    JWT_SECRET=JWT_SECRET,
    ADMIN_ID=ADMIN_ID,
    AGENT_REPORT_SECRET=AGENT_SECRET,
    DATABASE_PATH=str(Path(WORK) / "check.db"),
    CACHE_DIR=str(Path(WORK) / "cache"),
    YTDLP_COOKIES=str(Path(WORK) / "cookies.txt"),
    CORS_ORIGINS="*,https://app.example.com",
)
os.chdir(WORK)


class Canary(http.server.BaseHTTPRequestHandler):
    """Counts every request; any hit from a hostile URL fails the check."""

    hits = 0
    redirect_to = None
    body = b"<html><title>canary</title></html>"

    def do_GET(self):
        type(self).hits += 1
        if self.path.startswith("/redirect") and type(self).redirect_to:
            self.send_response(302)
            self.send_header("Location", type(self).redirect_to)
            self.end_headers()
            return
        payload = b"x" * 4096 if self.path.startswith("/large") else type(self).body
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


class SecondCanary(Canary):
    hits = 0


def start_server(handler):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server.server_address[1]


def check_url_classification():
    import url_safety as u

    for url in (
        "https://music.apple.com/us/album/x/1?i=2",
        "see this https://music.apple.com/us/album/x/1?i=2 now",
        "music.apple.com/us/album/x/1",
    ):
        assert u.find_apple_music_url(url), url
    for url in (
        "http://127.0.0.1:8000/x?music.apple.com",
        "http://169.254.169.254/latest/music.apple.com",
        "https://music.apple.com.evil.example/x",
        "https://evil.example/#music.apple.com",
        "https://music.apple.com@evil.example/x",
        "https://evil.example\\@music.apple.com/x",
        "https://music.apple.com:8443/x",
        "ftp://music.apple.com/x",
        "file:///etc/passwd?music.apple.com",
    ):
        assert u.find_apple_music_url(url) is None, url

    for url in (
        "https://www.shazam.com/track/1/x",
        "https://shz.am/t/abc",
        "I used Shazam to find this: https://www.shazam.com/track/1/x.",
    ):
        assert u.find_shazam_url(url), url
    # A single link keeps its JSON fragment, spaces included (KI-14).
    fragment = 'https://www.shazam.com/track/1/x#{"title":"Two Words"}'
    assert u.find_shazam_url(fragment) == fragment
    for url in (
        "http://127.0.0.1/x?shazam.com",
        "http://10.0.0.1/shz.am",
        "https://notshazam.com/track/1",
        "https://shazam.com.evil.example/track/1",
    ):
        assert u.find_shazam_url(url) is None, url

    for url in (
        "https://www.youtube.com/watch?v=abc",
        "https://music.youtube.com/playlist?list=abc",
        "youtube.com/watch?v=abc",
        "https://youtu.be/abc",
        "https://soundcloud.com/a/b",
        "https://on.soundcloud.com/abc",
    ):
        assert u.find_direct_media_url(url), url
    for url in (
        "http://127.0.0.1/soundcloud.com/a",
        "http://internal/youtube.com/watch?v=a",
        "https://evil.example/youtu.be/a",
        "https://soundcloud.com.evil.example/a",
    ):
        assert u.find_direct_media_url(url) is None, url


def check_no_fetch_on_hostile_urls():
    from catalog import resolve_url
    from metadata import AppleMusicMetadata, ShazamMetadata

    port = start_server(Canary)
    base = f"http://127.0.0.1:{port}"

    async def run():
        assert not await AppleMusicMetadata(f"{base}/x?music.apple.com").fetch()
        assert not await ShazamMetadata(f"{base}/track/1?shazam.com").fetch()
        assert await resolve_url(f"{base}/soundcloud.com/a", dict) == (None, [])

    asyncio.run(run())

    import url_safety
    import yt_dlp

    opts = {"quiet": True, "no_warnings": True,
            "allowed_extractors": url_safety.YTDLP_ALLOWED_EXTRACTORS}
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            ydl.extract_info(f"{base}/page", download=False)
            raise AssertionError("yt-dlp accepted a non-allowlisted URL")
        except yt_dlp.utils.DownloadError:
            pass
    assert Canary.hits == 0, f"hostile URL reached the network ({Canary.hits} hits)"


def check_redirects_and_size():
    import aiohttp
    import url_safety

    first = start_server(Canary)
    second = start_server(SecondCanary)
    allowed_prefix = f"http://127.0.0.1:{first}/"
    Canary.redirect_to = f"http://127.0.0.1:{second}/secret"

    def is_allowed(url):
        return url.startswith(allowed_prefix)

    async def run():
        async with aiohttp.ClientSession() as session:
            try:
                await url_safety.fetch_allowed(session, f"{allowed_prefix}redirect", is_allowed)
                raise AssertionError("redirect left the allowlist")
            except url_safety.DisallowedUrl:
                pass
            try:
                await url_safety.fetch_allowed(
                    session, f"{allowed_prefix}large", is_allowed, max_bytes=1024,
                )
                raise AssertionError("size cap ignored")
            except url_safety.ResponseTooLarge:
                pass
            status, _final, text = await url_safety.fetch_allowed(
                session, f"{allowed_prefix}ok", is_allowed,
            )
            assert status == 200 and "canary" in text

    asyncio.run(run())
    assert SecondCanary.hits == 0, "redirect target was contacted"


def _jar(*rows):
    return "# Netscape HTTP Cookie File\n" + "".join(
        f"{domain}\tTRUE\t/\tTRUE\t0\t{name}\tvalue\n" for domain, name in rows
    )


def check_cookies():
    from downloader import cookie_jar_status, filter_cookie_jar, write_private_file

    filtered = filter_cookie_jar(_jar(
        (".youtube.com", "SID"),
        ("#HttpOnly_.youtube.com", "__Secure-3PSID"),
        (".google.com", "SAPISID"),
        ("accounts.google.com", "LSID"),
        (".soundcloud.com", "oauth"),
        (".bank.example", "BANK_SESSION"),
        (".notyoutube.com", "OTHER"),
        (".youtube.com.evil.example", "SPOOF"),
    ))
    for name in ("SID", "__Secure-3PSID", "SAPISID", "LSID", "oauth"):
        assert f"\t{name}\t" in filtered, name
    for name in ("BANK_SESSION", "OTHER", "SPOOF"):
        assert name not in filtered, name
    assert filtered.startswith("# Netscape")
    assert cookie_jar_status(filtered)[0]

    path = Path(WORK) / "private.txt"
    path.write_text("old")
    os.chmod(path, 0o644)
    write_private_file(str(path), "new")
    assert path.read_text() == "new"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert [p.name for p in Path(WORK).glob(".tmp-private-*")] == []


def _signed_init_data(fields):
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    digest = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": digest})


def check_api():
    from fastapi.testclient import TestClient

    from api import auth, config
    from api.main import app

    assert "*" not in config.CORS_ORIGINS
    client = TestClient(app, raise_server_exceptions=False)

    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404, path

    user = json.dumps({"id": 42, "first_name": "A"})
    now = str(int(time.time()))
    post = lambda data: client.post("/auth/telegram-webapp", json={"initData": data}).status_code
    assert post(_signed_init_data({"user": user, "auth_date": now})) == 200
    assert post(_signed_init_data({"user": user})) == 401, "missing auth_date"
    assert post(_signed_init_data({"user": user, "auth_date": "soon"})) == 401
    assert post(_signed_init_data({"user": user, "auth_date": "1"})) == 401, "expired"
    assert post(_signed_init_data({"user": "[1]", "auth_date": now})) == 401
    assert post(f"user=x&auth_date={now}&hash=%C3%A9") == 401, "non-ASCII hash"

    widget = {"id": 42, "auth_date": 0, "hash": "é"}
    assert client.post("/auth/telegram-login", json=widget).status_code == 401

    assert client.get(
        "/admin/agent/reports", headers={"X-Agent-Secret": "é".encode("latin-1")},
    ).status_code == 401
    assert client.get(
        "/admin/agent/reports", headers={"X-Agent-Secret": AGENT_SECRET},
    ).status_code == 200

    user_token = auth.issue_token({"id": 42})
    admin_token = auth.issue_token({"id": int(ADMIN_ID)})
    as_user = {"Authorization": f"Bearer {user_token}"}
    as_admin = {"Authorization": f"Bearer {admin_token}"}

    file_token = auth.sign_file_token(str(Path(WORK) / "a.mp3"), "42")
    assert client.get("/me", headers={"Authorization": f"Bearer {file_token}"}).status_code == 401
    assert client.get(f"/files/{user_token}").status_code == 401

    assert client.get("/history?limit=-1", headers=as_user).status_code == 422
    assert client.get("/top?limit=-1", headers=as_user).status_code == 422

    grant = {"user_id": "42", "tier": "premium", "days": 1}
    assert client.post("/admin/grant", json=grant, headers=as_user).status_code == 403
    for bad in ({"tier": "root"}, {"days": 0}, {"days": 99999}, {"user_id": "../1"}):
        response = client.post("/admin/grant", json={**grant, **bad}, headers=as_admin)
        assert response.status_code == 422, bad
    response = client.post(
        "/admin/topup", json={"user_id": "42", "amount": -5}, headers=as_admin,
    )
    assert response.status_code == 422

    upload = lambda data: client.post(
        "/admin/cookies", files={"file": ("cookies.txt", data)}, headers=as_admin,
    )
    assert upload(b"youtube.com but not a cookie jar").status_code == 400
    assert upload(b"x" * (2 * 1024 * 1024 + 1)).status_code == 413
    good = _jar(
        (".youtube.com", "SID"), (".youtube.com", "SAPISID"), (".bank.example", "BANK_SESSION"),
    )
    assert upload(good.encode()).status_code == 200
    saved = Path(os.environ["YTDLP_COOKIES"])
    assert "BANK_SESSION" not in saved.read_text()
    assert stat.S_IMODE(saved.stat().st_mode) == 0o600


def check_jwt_secret_required():
    code = "import api.config"
    long_token = BOT_TOKEN.ljust(40, "x")
    for secret in ("", "short", long_token):
        env = {**os.environ, "JWT_SECRET": secret, "PYTHONPATH": str(ROOT),
               "BOT_TOKEN": long_token}
        result = subprocess.run(
            [sys.executable, "-c", code], cwd=WORK, env=env, capture_output=True, text=True,
        )
        assert result.returncode != 0 and "JWT_SECRET" in result.stderr, repr(secret)


def check_history_ownership():
    from database import Database

    db = Database(str(Path(WORK) / "history.db"))
    db.touch_user("1")
    db.touch_user("2")
    row_id = db.log_download("1", "Title", "Artist", "youtube", None, None, None, False)
    assert db.get_history_by_id(row_id, "1")
    assert db.get_history_by_id(row_id, "2") is None


def check_env_parser():
    script = (ROOT / "scripts" / "hiit-radio-stack.sh").read_text()
    function = re.search(r"^load_env_file\(\) \{.*?^\}$", script, re.S | re.M).group(0)
    assert 'source "$ROOT/.env"' not in script
    marker = Path(WORK) / "env-parser-ran-code"
    env_file = Path(WORK) / "sample.env"
    env_file.write_text(
        f"INJECT_A=$(touch {marker})\n"
        f"INJECT_B=`touch {marker}`\n"
        f'INJECT_C="$(touch {marker})"\n'
        f"INJECT_D=; touch {marker}\n"
        f"touch {marker}\n"
        "# COMMENTED=1\n"
        "\n"
        "PLAIN=value\n"
        "EMPTY=\n"
        'DOUBLE="two words" # note\n'
        "SINGLE='a#b'\n"
        "TRAILING=abc # note\n"
        "HASH=abc#def\n"
        "EQUALS=a=b=c\n"
        "export EXPORTED=yes\n"
        "CRLF=value\r\n"
    )
    probe = (
        f"{function}\nload_env_file {env_file}\n"
        'printf "%s|" "$PLAIN" "$EMPTY" "$DOUBLE" "$SINGLE" "$TRAILING" "$HASH" "$EQUALS" '
        '"$EXPORTED" "$CRLF" "$INJECT_A"\n'
    )
    result = subprocess.run(["bash", "-c", probe], capture_output=True, text=True, check=True)
    expected = (
        f"value||two words|a#b|abc|abc#def|a=b=c|yes|value|$(touch {marker})|"
    )
    assert result.stdout == expected, result.stdout
    assert not marker.exists(), ".env content was executed"


def check_cookieless_youtube():
    import downloader as dl

    d = dl.MusicDownloader(download_dir=str(Path(WORK) / "dl"))
    d.cookies_from_browser = ""
    jar = Path(d.cookies_path)
    jar.unlink(missing_ok=True)
    assert d._youtube_subprocess_attempts() == ["none"]

    opts = d._build_ydl_opts("x.%(ext)s")
    assert "cookiefile" not in opts and "cookiesfrombrowser" not in opts
    assert opts["extractor_args"]["youtube"]["player_client"] == dl._YT_ANON_CLIENTS
    search = d._build_search_opts()
    assert "cookiefile" not in search and "cookiesfrombrowser" not in search

    jar.write_text(_jar((".youtube.com", "SID"), (".google.com", "SAPISID")))
    d.cookies_from_browser = "chrome"
    assert d._youtube_subprocess_attempts() == ["none", "cookiefile", "browser"]
    assert d._probe_auth_attempts() == ["none", "cookiefile"]
    # A present jar is still not used unless the attempt asks for it.
    assert "cookiefile" not in d._build_ydl_opts("x.%(ext)s")
    assert d._build_ydl_opts("x.%(ext)s", auth="cookiefile")["cookiefile"] == d.cookies_path

    def walk(*errors):
        """Run the worker loop against scripted failures; return auth modes tried."""
        tried, script = [], list(errors)

        def fake_run(cmd, **_kwargs):
            tried.append(cmd[cmd.index("--auth") + 1])
            err = script.pop(0) if script else ""
            return (1 if err else 0), "", err, False

        real = dl._run_interruptible
        dl._run_interruptible = fake_run
        try:
            ok, _detail = d._run_youtube_worker(
                "https://www.youtube.com/watch?v=x",
                output_template="x", auth_modes=["none", "cookiefile"],
            )
        finally:
            dl._run_interruptible = real
        return ok, tried

    bot = "ERROR: Sign in to confirm you're not a bot"
    assert walk() == (True, ["none"])
    assert walk(bot) == (True, ["none", "cookiefile"])
    assert walk("ERROR: Sign in to confirm your age") == (True, ["none", "cookiefile"])
    assert walk("ERROR: Requested format is not available") == (True, ["none", "cookiefile"])
    # Cookies cannot fix these, so the account must not be exposed to them.
    assert walk("ERROR: Video unavailable") == (False, ["none"])
    assert walk("ERROR: Connection reset by peer") == (False, ["none"])
    jar.unlink()
    d.cookies_from_browser = ""


def main():
    check_url_classification()
    check_no_fetch_on_hostile_urls()
    check_redirects_and_size()
    check_cookies()
    check_cookieless_youtube()
    check_jwt_secret_required()
    check_api()
    check_history_ownership()
    check_env_parser()
    print("security checks OK")


if __name__ == "__main__":
    main()
