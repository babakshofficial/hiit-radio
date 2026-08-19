"""Set Telegram Mini App menu button when WEBAPP_URL is configured."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


async def configure_webapp_menu(bot) -> None:
    """Point the chat menu button at the Mini App URL if configured."""
    url = (os.getenv("WEBAPP_URL") or "").strip()
    if not url:
        logger.info("WEBAPP_URL not set — skipping Mini App menu button")
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
