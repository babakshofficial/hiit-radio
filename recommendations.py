"""Post-download artist recommendation keyboards."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def recommendation_keyboard(artist, track_title=None):
    if not artist:
        return None
    safe_artist = artist[:40]
    buttons = [
        [
            InlineKeyboardButton(
                "آهنگ‌های بیشتر",
                callback_data=f"reco:artist:{safe_artist}",
            ),
            InlineKeyboardButton(
                "هنرمندان مشابه",
                callback_data=f"reco:similar:{safe_artist}",
            ),
        ]
    ]
    return InlineKeyboardMarkup(buttons)
