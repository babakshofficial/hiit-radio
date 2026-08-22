"""Admin ↔ user support threads tied to bug reports."""

import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import Forbidden

import messages as msg

logger = logging.getLogger(__name__)


def _admin_id():
    return os.getenv("ADMIN_ID", "").strip()


def build_admin_report_keyboard(report_id, thread_id=None):
    rows = [
        [InlineKeyboardButton(
            msg.support_reply_button(),
            callback_data=f"sup:reply:{report_id}",
        )],
    ]
    if thread_id:
        rows.append([InlineKeyboardButton(
            msg.support_end_button(),
            callback_data=f"sup:end:{thread_id}",
        )])
    return InlineKeyboardMarkup(rows)


def build_admin_active_keyboard(thread_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            msg.support_end_button(),
            callback_data=f"sup:end:{thread_id}",
        )],
    ])


async def start_admin_compose(bot, db, admin_id, report_id):
    """Open a support thread and enter admin compose mode."""
    report = db.get_error_report(report_id)
    if not report or not report.get("submitted_at"):
        return False, msg.support_report_not_found()

    user_id = report["user_id"]
    existing = db.get_open_thread_for_report(report_id)
    if existing:
        thread_id = existing["id"]
    else:
        thread_id = db.open_support_thread(report_id, user_id)

    db.set_admin_support_session(admin_id, thread_id)
    return True, msg.support_admin_prompt(report_id, user_id)


async def forward_admin_message(bot, db, admin_id, text, *, notify_opened=False):
    """Send admin text to the user for the active compose session."""
    session = db.get_admin_support_session(admin_id)
    if not session:
        return False, msg.support_thread_ended_no_open()

    thread = db.get_thread(session["thread_id"])
    if not thread or thread.get("status") != "open":
        db.clear_admin_support_session(admin_id)
        return False, msg.support_thread_ended_no_open()

    user_id = int(thread["user_id"])
    body = text.strip()
    if not body:
        return False, msg.support_empty_message()

    first_admin_msg = db.count_support_messages(thread["id"], "admin") == 0

    try:
        await bot.send_message(chat_id=user_id, text=msg.support_user_message(body))
    except Forbidden:
        return False, msg.support_send_failed_blocked()
    except Exception as exc:
        logger.warning("Support message to user %s failed: %s", user_id, exc)
        return False, msg.support_send_failed()

    db.add_support_message(thread["id"], "admin", body)
    db.set_admin_support_session(admin_id, thread["id"])

    if notify_opened and first_admin_msg:
        try:
            await bot.send_message(chat_id=user_id, text=msg.support_user_opened())
        except Exception:
            pass

    return True, msg.support_sent_admin(user_id)


async def forward_user_support_message(bot, db, user_id, text):
    """Forward a user /support message to the admin."""
    thread = db.get_open_thread_for_user(user_id)
    if not thread:
        return False, msg.support_no_thread()

    admin_id = _admin_id()
    if not admin_id:
        return False, msg.support_send_failed()

    body = text.strip()
    if not body:
        return False, msg.support_empty_message()

    report = db.get_error_report(thread["report_id"])
    label = str(user_id)
    if report and report.get("username"):
        label = f"{user_id} (@{report['username']})"

    admin_text = msg.support_forward_to_admin(label, thread["report_id"], body)
    keyboard = build_admin_active_keyboard(thread["id"])

    try:
        await bot.send_message(
            chat_id=int(admin_id),
            text=admin_text,
            reply_markup=keyboard,
        )
    except Exception as exc:
        logger.warning("Support message to admin failed: %s", exc)
        return False, msg.support_send_failed()

    db.add_support_message(thread["id"], "user", body)
    db.set_admin_support_session(admin_id, thread["id"])
    return True, msg.support_sent_user()


async def end_thread(bot, db, thread_id, admin_id=None):
    """Close thread, clear admin session, notify user."""
    thread = db.get_thread(thread_id)
    if not thread or thread.get("status") != "open":
        if admin_id:
            db.clear_admin_support_session(admin_id)
        return False, msg.support_thread_ended_no_open()

    db.close_support_thread(thread_id)
    if admin_id:
        db.clear_admin_support_session(admin_id)
    else:
        aid = _admin_id()
        if aid:
            db.clear_admin_support_session(aid)

    user_id = int(thread["user_id"])
    try:
        await bot.send_message(chat_id=user_id, text=msg.support_user_closed())
    except Exception:
        pass

    return True, msg.support_thread_ended_admin(thread_id)


async def end_admin_session(bot, db, admin_id):
    """End whatever thread the admin is composing for."""
    session = db.get_admin_support_session(admin_id)
    if not session:
        return False, msg.support_thread_ended_no_open()
    return await end_thread(bot, db, session["thread_id"], admin_id=admin_id)
