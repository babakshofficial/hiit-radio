#!/usr/bin/env python3
"""Fresh-process YouTube download worker for the bot.

Isolates live Chrome cookie reads from the long-lived bot process.
Invoked by MusicDownloader._run_youtube_worker.
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
        print(
            f"yt_worker auth=browser "
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

    # Native yt-dlp proxy (set by parent after clearing proxychains LD_PRELOAD).
    proxy = (os.environ.get("YTDLP_PROXY") or "").strip()
    if proxy:
        opts["proxy"] = proxy
        print(f"yt_worker proxy={proxy}", flush=True)
    else:
        opts.pop("proxy", None)

    auth = "browser" if opts.get("cookiesfrombrowser") else (
        "cookiefile" if opts.get("cookiefile") else "none"
    )
    print(
        f"yt_worker auth={auth} "
        f"dbus={bool(os.environ.get('DBUS_SESSION_BUS_ADDRESS'))} "
        f"keyring={bool(os.environ.get('SSH_AUTH_SOCK'))}",
        flush=True,
    )

    from downloader import _info_has_formats, _YT_PLAYER_CLIENTS, _deno_js_runtimes

    if args.probe:
        # Health check must NOT select a download format — restrictive
        # bestaudio[...] filters fail with "Requested format is not available"
        # even when cookies are fine and formats exist.
        base = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "ignore_no_formats_error": True,
            "socket_timeout": 25,
            "remote_components": ["ejs:github"],
            "js_runtimes": _deno_js_runtimes(),
            "http_headers": opts.get("http_headers") or {},
        }
        if opts.get("cookiesfrombrowser"):
            base["cookiesfrombrowser"] = opts["cookiesfrombrowser"]
        if opts.get("cookiefile"):
            base["cookiefile"] = opts["cookiefile"]
        client_sets = [
            list(_YT_PLAYER_CLIENTS),
            ["android", "ios"],
            ["tv", "web"],
            ["web"],
        ]
        last_err = None
        for clients in client_sets:
            attempt = dict(base)
            attempt["extractor_args"] = {"youtube": {"player_client": list(clients)}}
            try:
                with d._with_ydl(attempt) as ydl:
                    info = ydl.extract_info(args.url, download=False)
                if _info_has_formats(info):
                    print("PROBE_OK", flush=True)
                    return 0
                last_err = RuntimeError(
                    f"PROBE_NO_FORMATS clients={','.join(clients)}"
                )
                print(
                    f"yt_worker probe no formats clients={','.join(clients)}",
                    flush=True,
                )
            except Exception as exc:
                last_err = exc
                print(
                    f"yt_worker probe retry clients={','.join(clients)} "
                    f"err={str(exc).splitlines()[-1][:120]}",
                    flush=True,
                )
                continue
        if last_err is not None:
            raise last_err
        print("PROBE_NO_FORMATS", file=sys.stderr)
        return 1

    def _try_download(player_clients, fmt):
        attempt_opts = dict(opts)
        attempt_opts["format"] = fmt
        attempt_opts["extractor_args"] = {
            "youtube": {"player_client": list(player_clients)}
        }
        with d._with_ydl(attempt_opts) as ydl:
            ydl.download([args.url])

    attempts = [
        (list(_YT_PLAYER_CLIENTS), opts.get("format") or "bestaudio/best"),
        (["android", "ios"], "bestaudio/best"),
        (["android", "web"], "bestaudio/best/best"),
        (["tv", "web"], "best"),
        (["web"], "best/bestaudio"),
    ]
    last_err = None
    for clients, fmt in attempts:
        try:
            _try_download(clients, fmt)
            return 0
        except Exception as exc:
            last_err = exc
            err = str(exc).lower()
            if "format is not available" in err or "no video formats" in err:
                print(
                    f"yt_worker format retry clients={','.join(clients)} fmt={fmt}",
                    flush=True,
                )
                continue
            break
    if last_err is not None:
        raise last_err
    return 1


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
