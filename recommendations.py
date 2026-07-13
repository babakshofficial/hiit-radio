"""Post-download artist recommendation keyboards."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from messages import BTN_MORE_BY_ARTIST, BTN_SIMILAR_ARTISTS


def recommendation_keyboard(artist, track_title=None):
    if not artist:
        return None
    safe_artist = artist[:40]
    buttons = [
        [
            InlineKeyboardButton(
                BTN_MORE_BY_ARTIST,
                callback_data=f"reco:artist:{safe_artist}",
            ),
            InlineKeyboardButton(
                BTN_SIMILAR_ARTISTS,
                callback_data=f"reco:similar:{safe_artist}",
            ),
        ]
    ]
    return InlineKeyboardMarkup(buttons)
