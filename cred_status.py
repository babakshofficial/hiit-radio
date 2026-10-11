"""Report readiness of YouTube download credentials and Spotify metadata API."""

import os

from downloader import MusicDownloader, _cookies_look_authenticated
from messages import t_lang


def get_credentials_status(lang=None):
    """Return (human-readable status text, yt_ok). ``lang`` is for admin UI (default en)."""

    def L(key, **kwargs):
        return t_lang(lang, key, **kwargs)

    dl = MusicDownloader()

    lines = [L("creds_header"), ""]

    lines.append(L("creds_yt_section"))
    if dl.cookies_from_browser:
        lines.append(L("creds_yt_browser", browser=dl.cookies_from_browser))
        live_ok, live_detail = dl.probe_youtube_auth()
        if live_ok:
            lines.append(L("creds_yt_live_ok", detail=live_detail))
            yt_ok = True
        else:
            lines.append(L("creds_yt_live_fail", detail=live_detail))
            lines.append(L("creds_yt_browser_hint"))
            yt_ok = False
    else:
        has_auth_cookies = (
            os.path.exists(dl.cookies_path) and _cookies_look_authenticated(dl.cookies_path)
        )
        if has_auth_cookies:
            live_ok, live_detail = dl.probe_youtube_auth()
            lines.append(L("creds_yt_cookies_path", path=dl.cookies_path))
            if live_ok:
                lines.append(L("creds_yt_live_ok", detail=live_detail))
                yt_ok = True
            else:
                lines.append(L("creds_yt_live_fail", detail=live_detail))
                lines.append(L("creds_yt_expired_hint"))
                yt_ok = False
        elif os.path.exists(dl.cookies_path):
            lines.append(L("creds_yt_cookies_incomplete"))
            lines.append(L("creds_yt_cookies_incomplete_hint"))
            yt_ok = False
        else:
            lines.append(L("creds_yt_cookies_missing", path=dl.cookies_path))
            lines.append(L("creds_yt_cookies_missing_hint"))
            yt_ok = False

    lines.append("")
    lines.append(L("creds_spotify_section"))
    has_id = bool(os.getenv("SPOTIFY_CLIENT_ID"))
    has_secret = bool(os.getenv("SPOTIFY_CLIENT_SECRET"))
    if has_id and has_secret:
        lines.append(L("creds_spotify_ok"))
        lines.append(L("creds_spotify_embed_note"))
    else:
        lines.append(L("creds_spotify_missing"))

    lines.append("")
    lines.append(L("creds_result_ok") if yt_ok else L("creds_result_fail"))

    return "\n".join(lines), yt_ok
