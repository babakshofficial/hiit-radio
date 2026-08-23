#!/usr/bin/env python3
"""Fresh-process YouTube download worker for the bot.

Isolates live Chrome cookie reads from the long-lived bot process. Uses
``YTDLP_PROXY`` when set. Invoked by MusicDownloader._run_youtube_worker.
"""
from __future__ import annotations

import argparse
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="")
    parser.add_argument("--outtmpl", default="")
    parser.add_argument("--quality", default="128")
    parser.add_argument(
        "--proxy",
        default="",
        help="SOCKS/HTTP proxy URL, or empty for direct",
    )
    parser.add_argument(
        "--auth",
        choices=("browser", "cookiefile"),
        default="browser",
        help="YouTube cookie source for this attempt",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Extract formats only (health check); do not download",
    )
    parser.add_argument(
        "--refresh-cookies",
        action="store_true",
        help="Export browser cookies to cookies.txt and exit",
    )
    parser.add_argument(
        "--browser",
        default="",
        help="Browser spec for --refresh-cookies (default: YTDLP_COOKIES_FROM_BROWSER)",
    )
    args = parser.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, root)
    os.chdir(root)

    from dotenv import load_dotenv

    load_dotenv(os.path.join(root, ".env"))

    from downloader import MusicDownloader, _ensure_youtube_session_env

    _ensure_youtube_session_env()
    d = MusicDownloader()

    if args.refresh_cookies:
        spec = args.browser.strip() or None
        ok, detail = d._refresh_cookies_impl(spec)
        print(
            f"REFRESH_{'OK' if ok else 'FAIL'} {detail}",
            flush=True,
        )
        proxy = (args.proxy or os.getenv("YTDLP_PROXY") or "").strip()
        print(
            f"yt_worker auth=browser proxy={proxy or 'direct'} "
            f"dbus={bool(os.environ.get('DBUS_SESSION_BUS_ADDRESS'))} "
            f"keyring={bool(os.environ.get('SSH_AUTH_SOCK'))}",
            flush=True,
        )
        return 0 if ok else 1

    if not args.url or not args.outtmpl:
        print("url and outtmpl required unless --refresh-cookies", file=sys.stderr)
        return 2

    live = args.auth == "browser"
    opts = d._build_ydl_opts(args.outtmpl, quality=args.quality, live_browser=live)
    opts["socket_timeout"] = 15
    if args.auth == "cookiefile":
        opts.pop("cookiesfrombrowser", None)
        opts["cookiefile"] = d.cookies_path
    else:
        opts.pop("cookiefile", None)
    proxy = (args.proxy or "").strip()
    if proxy:
        opts["proxy"] = proxy
    else:
        opts.pop("proxy", None)

    auth = "browser" if opts.get("cookiesfrombrowser") else (
        "cookiefile" if opts.get("cookiefile") else "none"
    )
    print(
        f"yt_worker auth={auth} proxy={proxy or 'direct'} "
        f"dbus={bool(os.environ.get('DBUS_SESSION_BUS_ADDRESS'))} "
        f"keyring={bool(os.environ.get('SSH_AUTH_SOCK'))}",
        flush=True,
    )

    from downloader import _info_has_formats

    with d._with_ydl(opts) as ydl:
        if args.probe:
            info = ydl.extract_info(args.url, download=False)
            if not _info_has_formats(info):
                print("PROBE_NO_FORMATS", file=sys.stderr)
                return 1
            print("PROBE_OK", flush=True)
            return 0
        ydl.download([args.url])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        # Keep journal readable: one ERROR line, no full yt-dlp traceback spam.
        msg = str(exc).strip() or repr(exc)
        for line in msg.splitlines():
            if "ERROR:" in line or "Sign in" in line or "bot" in line.lower():
                print(line, file=sys.stderr)
                break
        else:
            print(msg.splitlines()[-1][:500], file=sys.stderr)
        raise SystemExit(1)
