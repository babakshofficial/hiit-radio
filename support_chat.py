"""Admin ↔ user support threads tied to bug reports."""

import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import Forbidden

import messages as msg

logger = logging.getLogger(__name__)


def _admin_id():
    return os.getenv("ADMIN_ID", "").strip()


def _agent_session_id():
    """Session key for external agent replies.

    Uses ADMIN_ID when it is set so the reply is recorded as that admin.
    Otherwise a synthetic key — support_admin_sessions.admin_id is plain text.
    Returns (admin_id, borrowed) where borrowed means we must restore the
    Telegram admin's compose session after the send.
    """
    admin_id = _admin_id()
    if admin_id:
        return admin_id, True
    return "agent", False


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


async def _deliver_admin_text(bot, db, admin_id, text, *, notify_opened=False):
    """Send the active compose session's text to the user.

    Returns (status, user_id). status is ok, no_session, closed, empty,
    blocked, or send_failed.
    """
    session = db.get_admin_support_session(admin_id)
    if not session:
        return "no_session", None

    thread = db.get_thread(session["thread_id"])
    if not thread or thread.get("status") != "open":
        db.clear_admin_support_session(admin_id)
        return "closed", None

    user_id = int(thread["user_id"])
    body = (text or "").strip()
    if not body:
        return "empty", user_id

    first_admin_msg = db.count_support_messages(thread["id"], "admin") == 0

    try:
        await bot.send_message(chat_id=user_id, text=msg.support_user_message(body))
    except Forbidden:
        return "blocked", user_id
    except Exception as exc:
        logger.warning("Support message to user %s failed: %s", user_id, exc)
        return "send_failed", user_id

    db.add_support_message(thread["id"], "admin", body)
    db.set_admin_support_session(admin_id, thread["id"])

    if notify_opened and first_admin_msg:
        try:
            await bot.send_message(chat_id=user_id, text=msg.support_user_opened())
        except Exception:
            pass

    return "ok", user_id


async def forward_admin_message(bot, db, admin_id, text, *, notify_opened=False):
    """Send admin text to the user for the active compose session."""
    status, user_id = await _deliver_admin_text(
        bot, db, admin_id, text, notify_opened=notify_opened,
    )
    if status == "ok":
        return True, msg.support_sent_admin(user_id)
    if status == "empty":
        return False, msg.support_empty_message()
    if status == "blocked":
        return False, msg.support_send_failed_blocked()
    if status == "send_failed":
        return False, msg.support_send_failed()
    return False, msg.support_thread_ended_no_open()


def _restore_admin_session(db, admin_id, previous, owned_thread_id):
    """Give the Telegram admin's compose target back after an agent reply."""
    if owned_thread_id is None:
        return
    current = db.get_admin_support_session(admin_id)
    if not current or str(current.get("thread_id")) != str(owned_thread_id):
        return
    if previous and previous.get("thread_id") is not None:
        if str(previous["thread_id"]) == str(owned_thread_id):
            return
        db.set_admin_support_session(admin_id, previous["thread_id"])
        return
    db.clear_admin_support_session(admin_id)


async def reply_to_report(bot, db, report_id, text):
    """Open or reuse the report's support thread and send one admin reply.

    Returns (status, info). status is ok, not_found, empty, no_bot, blocked,
    or send_failed. On ok, info is {thread_id, user_id}.
    """
    report = db.get_error_report(report_id)
    if not report or not report.get("submitted_at"):
        return "not_found", None

    body = (text or "").strip()
    if not body:
        return "empty", None
    if bot is None:
        return "no_bot", None

    user_id = report["user_id"]
    try:
        lang = db.get_language(user_id)
    except Exception:
        lang = None
    token = msg.use_lang(lang)
    admin_id, borrow = _agent_session_id()
    previous = db.get_admin_support_session(admin_id) if borrow else None
    thread_id = None
    try:
        opened, _prompt = await start_admin_compose(bot, db, admin_id, report_id)
        if not opened:
            return "not_found", None
        session = db.get_admin_support_session(admin_id)
        thread_id = session["thread_id"] if session else None
        status, sent_user = await _deliver_admin_text(
            bot, db, admin_id, body, notify_opened=True,
        )
        resolved_user = sent_user if sent_user is not None else user_id
        try:
            resolved_user = int(resolved_user)
        except (TypeError, ValueError):
            pass
        info = {"thread_id": thread_id, "user_id": resolved_user}
        if status != "ok":
            if status in ("blocked", "send_failed"):
                return status, info
            return "send_failed", info
        return "ok", info
    finally:
        if borrow:
            _restore_admin_session(db, admin_id, previous, thread_id)
        msg.reset_lang(token)


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
