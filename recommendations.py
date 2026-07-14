"""Post-download recommendation / lyrics keyboards."""

import secrets
from collections import OrderedDict

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from messages import BTN_MORE_BY_ARTIST, BTN_LYRICS

# Short callback tokens → (title, artist). Bounded; single-process bot.
_LYRICS_REFS = OrderedDict()
_LYRICS_REFS_MAX = 400


def remember_lyrics_ref(title, artist):
    """Store title/artist and return a short token for callback_data."""
    token = secrets.token_hex(4)
    _LYRICS_REFS[token] = ((title or "").strip(), (artist or "").strip())
    while len(_LYRICS_REFS) > _LYRICS_REFS_MAX:
        _LYRICS_REFS.popitem(last=False)
    return token


def resolve_lyrics_ref(token):
    return _LYRICS_REFS.get(token)


def recommendation_keyboard(artist, track_title=None):
    if not artist and not track_title:
        return None
    buttons = []
    row = []
    if artist:
        row.append(
            InlineKeyboardButton(
                BTN_MORE_BY_ARTIST,
                callback_data=f"reco:artist:{artist[:40]}",
            )
        )
    if track_title:
        token = remember_lyrics_ref(track_title, artist or "")
        row.append(
            InlineKeyboardButton(
                BTN_LYRICS,
                callback_data=f"reco:lyrics:{token}",
            )
        )
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons) if buttons else None
