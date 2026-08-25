"""Post-download recommendation / lyrics / favorites keyboards."""

import secrets
from collections import OrderedDict

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import messages as msg

# Short callback tokens → (title, artist). Bounded; single-process bot.
_TRACK_REFS = OrderedDict()
_TRACK_REFS_MAX = 400


def remember_track_ref(title, artist):
    """Store title/artist and return a short token for callback_data."""
    token = secrets.token_hex(4)
    _TRACK_REFS[token] = ((title or "").strip(), (artist or "").strip())
    while len(_TRACK_REFS) > _TRACK_REFS_MAX:
        _TRACK_REFS.popitem(last=False)
    return token


def resolve_track_ref(token):
    return _TRACK_REFS.get(token)


# Back-compat aliases used by lyrics flow.
remember_lyrics_ref = remember_track_ref
resolve_lyrics_ref = resolve_track_ref


def recommendation_keyboard(artist, track_title=None, favorited=False):
    if not artist and not track_title:
        return None

    token = remember_track_ref(track_title or "", artist or "")
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
            )
        ])

    return InlineKeyboardMarkup(buttons) if buttons else None
