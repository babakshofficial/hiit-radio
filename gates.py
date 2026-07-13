"""Channel membership gate for bot access."""

import logging
import os
import time

from telegram.error import BadRequest, Forbidden

from messages import gate_alert, gate_denied

logger = logging.getLogger(__name__)

REQUIRED_CHANNEL_RAW = os.getenv("REQUIRED_CHANNEL", "@HiiTRadio").strip()
ALLOWED_STATUSES = {"member", "administrator", "creator", "restricted"}

# user_id -> (is_member, expiry_ts)
_membership_cache = {}
_CACHE_TTL = 300  # 5 minutes


def parse_channel_id(raw):
    """Return int chat id or @username string for Telegram API calls."""
    raw = (raw or "").strip()
    if not raw:
        return None
    if raw.lstrip("-").isdigit():
        return int(raw)
    return raw if raw.startswith("@") else f"@{raw}"


REQUIRED_CHANNEL = parse_channel_id(REQUIRED_CHANNEL_RAW)


async def validate_channel_gate(bot):
    """Run once at startup; verify getChatMember will work for the required channel."""
    if not REQUIRED_CHANNEL:
        return True

    try:
        chat = await bot.get_chat(REQUIRED_CHANNEL)
        admin_id = os.getenv("ADMIN_ID", "").strip()
        if admin_id:
            await bot.get_chat_member(REQUIRED_CHANNEL, int(admin_id))
        logger.info(
            f"Channel gate OK: {getattr(chat, 'title', REQUIRED_CHANNEL)} "
            f"(type={chat.type}, id={chat.id})"
        )
        return True
    except (BadRequest, Forbidden) as e:
        logger.error(
            f"Channel gate broken for {REQUIRED_CHANNEL}: {e}. "
            "For private channels, add the bot as an administrator with permission "
            "to manage/chat. You can also set REQUIRED_CHANNEL to the numeric "
            "chat id (use /channelid)."
        )
        return False
    except Exception as e:
        logger.error(f"Channel gate validation error for {REQUIRED_CHANNEL}: {e}")
        return False


async def is_member(bot, user_id, channel=None):
    channel = channel or REQUIRED_CHANNEL
    uid = str(user_id)
    now = time.time()
    cached = _membership_cache.get(uid)
    if cached and cached[1] > now:
        return cached[0]

    try:
        member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
        ok = member.status in ALLOWED_STATUSES
        _membership_cache[uid] = (ok, now + _CACHE_TTL)
        return ok
    except (BadRequest, Forbidden) as e:
        logger.warning(f"Channel membership check failed for {uid}: {e}")
        # Fail open so a misconfigured gate does not brick the bot.
        return True
    except Exception as e:
        logger.warning(f"Channel membership check failed for {uid}: {e}")
        return True


async def ensure_access(update, context, allow_start=False):
    """Return True if user may proceed. Sends join prompt and returns False otherwise."""
    if not REQUIRED_CHANNEL:
        return True

    user = update.effective_user
    if not user:
        return True

    if allow_start and update.message and update.message.text and update.message.text.startswith("/start"):
        return True

    if await is_member(context.bot, user.id):
        return True

    channel = REQUIRED_CHANNEL_RAW.lstrip("@")
    try:
        import admin_logger
        await admin_logger.log_gate_denied(context.bot, user, f"@{channel}")
    except Exception:
        pass
    text = gate_denied(channel)
    if update.callback_query:
        await update.callback_query.answer(gate_alert(), show_alert=True)
        if update.callback_query.message:
            await update.callback_query.message.reply_text(text)
    elif update.inline_query:
        pass  # inline answers handled separately
    elif update.message:
        await update.message.reply_text(text)
    return False
