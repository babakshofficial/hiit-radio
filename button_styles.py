"""Colored inline buttons (Bot API 9.4 ``style``: primary / success / danger).

Every outgoing keyboard passes through ``ExtBot._replace_keyboard``; ``install()``
wraps it so each callback button gets a color picked from its ``callback_data``.
A button that already carries ``api_kwargs={"style": ...}`` is left untouched.
Set ``BUTTON_STYLES=0`` to disable. Clients older than 9.4 just show gray buttons.
"""

import os
from fnmatch import fnmatchcase

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ExtBot

PRIMARY = "primary"
SUCCESS = "success"
DANGER = "danger"

# Ordered (pattern, style); first match wins. None = keep default gray.
RULES = [
    # Destructive / stop / cancel -> red
    ("menu:cancel", DANGER),
    ("*:cancel", DANGER),
    ("job:stop", DANGER),
    ("sup:end:*", DANGER),
    ("fav:del:*", DANGER),
    ("unfollow:*", DANGER),
    ("changelog:sk:del:*", DANGER),
    ("changelog:skip", DANGER),
    ("changelog:lang:skip:*", DANGER),
    ("usub:adm:no:*", DANGER),
    ("usub:adm:rej:*", DANGER),
    ("mix:off", DANGER),
    ("mixfb:*:-1", DANGER),
    ("refund:confirm:*", DANGER),
    # Navigation and long pick/paging lists -> gray
    ("menu:back", None),
    ("admin:menu", None),
    ("rpt:*", None),
    ("searchpick:*", None),
    ("toppick:*", None),
    ("alt:*", None),
    ("catpick:*", None),
    ("discoverpick:*", None),
    ("mixpick:*", None),
    ("artistpick:album:*", None),
    ("artistpick:track:*", None),
    ("lang:*", None),
    ("qual:*", None),
    # Positive / confirm / money -> green
    ("pay:*", SUCCESS),
    ("menu:premium", SUCCESS),
    ("menu:gift", SUCCESS),
    ("menu:invite", SUCCESS),
    ("menu:submit_music", SUCCESS),
    ("awiz:ok", SUCCESS),
    ("usub:meta:ok", SUCCESS),
    ("usub:adm:ok:*", SUCCESS),
    ("changelog:send", SUCCESS),
    ("changelog:lang:send:*", SUCCESS),
    ("changelog:sk:send:*", SUCCESS),
    ("fav:add:*", SUCCESS),
    ("follow:*", SUCCESS),
    ("artistpick:profile:follow:*", SUCCESS),
    ("mixfb:*:1", SUCCESS),
    ("retry:*", SUCCESS),
    ("redownload:*", SUCCESS),
    ("sup:reply:*", SUCCESS),
    # Menus and features -> blue
    ("menu:*", PRIMARY),
    ("admin:*", PRIMARY),
    ("reco:*", PRIMARY),
    ("mix:*", PRIMARY),
    ("recog:*", PRIMARY),
    ("newrel:*", PRIMARY),
    ("liked:*", PRIMARY),
    ("changelog:*", PRIMARY),
    ("usub:*", PRIMARY),
    ("awiz:*", PRIMARY),
]


def style_for(callback_data):
    if not isinstance(callback_data, str):
        return None
    for pattern, style in RULES:
        if fnmatchcase(callback_data, pattern):
            return style
    return None


def _style_button(btn):
    if "style" in (btn.api_kwargs or {}) or getattr(btn, "style", None):
        return btn
    style = style_for(btn.callback_data)
    if style is None:
        return btn
    return InlineKeyboardButton.de_json({**btn.to_dict(), "style": style}, None)


def style_markup(markup):
    if not isinstance(markup, InlineKeyboardMarkup):
        return markup
    changed = False
    rows = []
    for row in markup.inline_keyboard:
        new_row = []
        for btn in row:
            styled = _style_button(btn)
            changed = changed or styled is not btn
            new_row.append(styled)
        rows.append(new_row)
    return InlineKeyboardMarkup(rows) if changed else markup


def install():
    """Wrap ExtBot._replace_keyboard once so every sent/edited keyboard is colored."""
    if os.getenv("BUTTON_STYLES", "1").strip() == "0":
        return False
    original = ExtBot._replace_keyboard
    if getattr(original, "_button_styles", False):
        return True

    def _replace_keyboard(self, reply_markup):
        return style_markup(original(self, reply_markup))

    _replace_keyboard._button_styles = True
    ExtBot._replace_keyboard = _replace_keyboard
    return True
