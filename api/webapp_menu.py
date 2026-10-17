"""Set Telegram Mini App menu button when WEBAPP_URL is configured."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


async def configure_webapp_menu(bot) -> None:
    """Point the chat menu button at the Mini App URL when MENU_BUTTON_MODE=webapp."""
    mode = (os.getenv("MENU_BUTTON_MODE") or "commands").strip().lower()
    if mode != "webapp":
        logger.debug("MENU_BUTTON_MODE=%s — commands menu handled by bot_commands", mode)
        return
    url = (os.getenv("WEBAPP_URL") or "").strip()
    if not url:
        logger.info("WEBAPP_URL not set — skipping Mini App menu button")
        return
    if not url.startswith("https://"):
        logger.info(
            "WEBAPP_URL is not HTTPS (%s) — skipping Mini App menu button "
            "(Telegram only accepts https:// URLs; set WEBAPP_URL empty for local dev "
            "or use a public HTTPS domain)",
            url,
        )
        return
    try:
        from telegram import MenuButtonWebApp, WebAppInfo

        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="HiiT Radio",
                web_app=WebAppInfo(url=url),
            )
        )
        logger.info("Mini App menu button set to %s", url)
    except Exception:
        logger.exception("Failed to set Mini App menu button")
