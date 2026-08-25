"""Post-download recommendation / lyrics / favorites keyboards."""

import secrets
from collections import OrderedDict

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import messages as msg

# Short callback tokens → track info dict. Bounded; single-process bot.
_TRACK_REFS = OrderedDict()
_TRACK_REFS_MAX = 400


def remember_track_ref(title, artist, **extra):
    """Store track info and return a short token for callback_data.

    Extra keys (url, query, platform, album, search_query) are kept for
    mismatch reports and ignored by simple (title, artist) consumers.
    """
    token = secrets.token_hex(4)
    payload = {
        "title": (title or "").strip(),
        "artist": (artist or "").strip(),
    }
    for key in ("url", "query", "platform", "album", "search_query"):
        val = extra.get(key)
        if val is not None and val != "":
            payload[key] = val
    _TRACK_REFS[token] = payload
    while len(_TRACK_REFS) > _TRACK_REFS_MAX:
        _TRACK_REFS.popitem(last=False)
    return token


def resolve_track_ref(token):
    """Return (title, artist) or None."""
    data = resolve_track_ref_full(token)
    if not data:
        return None
    return data.get("title") or "", data.get("artist") or ""


def resolve_track_ref_full(token):
    """Return the full track payload dict or None."""
    data = _TRACK_REFS.get(token)
    if not data:
        return None
    if isinstance(data, tuple) and len(data) >= 2:
        return {"title": data[0], "artist": data[1]}
    if isinstance(data, dict):
        return data
    return None


# Back-compat aliases used by lyrics flow.
remember_lyrics_ref = remember_track_ref
resolve_lyrics_ref = resolve_track_ref


def recommendation_keyboard(
    artist,
    track_title=None,
    favorited=False,
    *,
    url=None,
    query=None,
    platform=None,
    album=None,
    search_query=None,
):
    if not artist and not track_title:
        return None

    token = remember_track_ref(
        track_title or "",
        artist or "",
        url=url,
        query=query,
        platform=platform,
        album=album,
        search_query=search_query,
    )
    buttons = []

    row1 = []
    if artist:
        row1.append(
            InlineKeyboardButton(
                msg.t("btn_more_by_artist"),
                callback_data=f"reco:artist:{artist[:40]}",
            )
        )
    if track_title:
        row1.append(
            InlineKeyboardButton(
                msg.t("btn_similar"),
                callback_data=f"reco:similar:{token}",
            )
        )
    if row1:
        buttons.append(row1)

    row2 = []
    if track_title:
        row2.append(
            InlineKeyboardButton(
                msg.t("btn_lyrics"),
                callback_data=f"reco:lyrics:{token}",
            )
        )
        if favorited:
            row2.append(
                InlineKeyboardButton(
                    msg.t("btn_favorite_remove"),
                    callback_data=f"fav:del:{token}",
                )
            )
        else:
            row2.append(
                InlineKeyboardButton(
                    msg.t("btn_favorite_add"),
                    callback_data=f"fav:add:{token}",
                )
            )
    if row2:
        buttons.append(row2)

    if track_title:
        buttons.append([
            InlineKeyboardButton(
                msg.t("btn_artwork"),
                callback_data=f"reco:art:{token}",
            ),
            InlineKeyboardButton(
                msg.t("btn_report_track"),
                callback_data=f"trkrep:{token}",
            ),
        ])

    return InlineKeyboardMarkup(buttons) if buttons else None
