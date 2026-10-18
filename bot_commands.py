"""Telegram bot command menu (blue Menu button) — localized slash commands."""

from __future__ import annotations

import logging
import os

from telegram import BotCommand, MenuButtonCommands

import messages as msg
from locales import DEFAULT_LANG, SUPPORTED, get_strings

logger = logging.getLogger(__name__)

PUBLIC_COMMANDS = (
    ("start", "cmd_start"),
    ("search", "cmd_search"),
    ("artist", "cmd_artist"),
    ("follow", "cmd_follow"),
    ("following", "cmd_following"),
    ("history", "cmd_history"),
    ("liked", "cmd_liked"),
    ("top", "cmd_top"),
    ("discover", "cmd_discover"),
    ("quality", "cmd_quality"),
    ("premium", "cmd_premium"),
    ("invite", "cmd_invite"),
    ("submit", "cmd_submit"),
    ("uploads", "cmd_uploads"),
    ("support", "cmd_support"),
    ("lang", "cmd_lang"),
    ("help", "cmd_help"),
    ("aboutme", "cmd_aboutme"),
    ("stop", "cmd_stop"),
)

ADMIN_COMMANDS = (
    ("admin", "cmd_admin"),
    ("stats", "cmd_stats"),
    ("report", "cmd_report"),
    ("reports", "cmd_reports"),
    ("users", "cmd_users"),
    ("user", "cmd_user"),
    ("export", "cmd_export"),
    ("cookies", "cmd_cookies"),
    ("creds", "cmd_creds"),
    ("broadcast", "cmd_broadcast"),
    ("grant", "cmd_grant"),
    ("topup", "cmd_topup"),
    ("supportend", "cmd_supportend"),
)


def build_commands(lang: str, admin: bool = False) -> list[BotCommand]:
    lang = msg.normalize_lang(lang) or DEFAULT_LANG
    table = get_strings(lang)
    fallback = get_strings(DEFAULT_LANG)
    pairs = list(PUBLIC_COMMANDS)
    if admin:
        pairs = pairs + list(ADMIN_COMMANDS)
    out: list[BotCommand] = []
    for command, key in pairs:
        text = table.get(key) or fallback.get(key) or key
        text = (text or "").strip()[:256]
        out.append(BotCommand(command, text))
    return out


async def _set_commands_safe(bot, commands, scope=None, language_code=None):
    try:
        await bot.set_my_commands(
            commands,
            scope=scope,
            language_code=language_code,
        )
    except Exception as exc:
        logger.warning(
            "set_my_commands failed (scope=%s lang=%s): %s",
            scope,
            language_code,
            exc,
        )


async def configure_menu(bot, admin_id=None, admin_lang=None) -> None:
    """Register fallback command lists and MenuButtonCommands.

    Only the bot default language is registered on the default scope so Telegram
    does not pick command text from the client's UI language. Per-user menus are
    set via ``refresh_user_commands`` from the user's stored bot language.
    """
    from telegram import BotCommandScopeChat, BotCommandScopeDefault

    admin_id = (admin_id or "").strip()
    admin_lang = msg.normalize_lang(admin_lang) or DEFAULT_LANG

    await _set_commands_safe(
        bot,
        build_commands(DEFAULT_LANG, admin=False),
        scope=BotCommandScopeDefault(),
    )

    if admin_id:
        try:
            chat_id = int(admin_id)
        except ValueError:
            chat_id = None
        if chat_id is not None:
            await _set_commands_safe(
                bot,
                build_commands(admin_lang, admin=True),
                scope=BotCommandScopeChat(chat_id),
            )

    mode = (os.getenv("MENU_BUTTON_MODE") or "commands").strip().lower()
    if mode == "webapp":
        logger.debug("MENU_BUTTON_MODE=webapp — skipping MenuButtonCommands")
        return
    try:
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        logger.info("Chat menu button set to commands list")
    except Exception as exc:
        logger.warning("set_chat_menu_button(commands) failed: %s", exc)


async def refresh_user_commands(bot, user_id, lang, admin_id=None) -> bool:
    """Per-user command list (overrides client language_code). Returns success."""
    from telegram import BotCommandScopeChat

    admin_id = (str(admin_id) if admin_id else "").strip()
    is_admin = bool(admin_id) and str(user_id) == admin_id
    lang = msg.normalize_lang(lang) or DEFAULT_LANG
    commands = build_commands(lang, admin=is_admin)
    try:
        await bot.set_my_commands(
            commands,
            scope=BotCommandScopeChat(int(user_id)),
        )
        return True
    except Exception as exc:
        logger.warning("refresh_user_commands(%s, %s): %s", user_id, lang, exc)
        return False
