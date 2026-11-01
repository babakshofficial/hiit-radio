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
    lines.append(L("creds_yt_anon"))
    if _cookies_look_authenticated(dl.cookies_path):
        lines.append(L("creds_yt_fallback_file", path=dl.cookies_path))
    if dl.cookies_from_browser:
        lines.append(L("creds_yt_fallback_browser", browser=dl.cookies_from_browser))
    yt_ok, live_detail = dl.probe_youtube_auth()
    if yt_ok:
        lines.append(L("creds_yt_live_ok", detail=live_detail))
    else:
        lines.append(L("creds_yt_live_fail", detail=live_detail))
        lines.append(L("creds_yt_blocked_hint"))

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
