"""Pending changelog notes → admin prompt → LLM-localized fan-out."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import messages as msg
from locales import DEFAULT_LANG, SUPPORTED, normalize_lang
from llm_service import generate_changelog, is_configured

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent
PENDING_PATH = Path(os.getenv("CHANGELOG_PENDING_PATH", str(_ROOT / "CHANGELOG_PENDING.md")))
ARCHIVE_PATH = Path(os.getenv("CHANGELOG_ARCHIVE_PATH", str(_ROOT / "CHANGELOG_ARCHIVE.md")))
_PREVIEW_LIMIT = 1200

_user_manager = None
_log_broadcast = None
_resolve_admin_lang = None
_admin_id = None
_busy = False
_lock = asyncio.Lock()


def init(*, user_manager, log_broadcast, resolve_admin_lang, admin_id):
    global _user_manager, _log_broadcast, _resolve_admin_lang, _admin_id
    _user_manager = user_manager
    _log_broadcast = log_broadcast
    _resolve_admin_lang = resolve_admin_lang
    _admin_id = str(admin_id).strip() if admin_id else ""


def _strip_notes(raw: str) -> str:
    """Drop HTML comments, single-# comment lines, and blank-only content.

    Markdown headings (``## …``) and bullet lists are kept.
    """
    if not raw:
        return ""
    text = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Ignore ``# comment`` but keep ``## Heading`` / ``###``.
        if re.match(r"^#[^#]", stripped) or stripped == "#":
            continue
        lines.append(line.rstrip())
    return "\n".join(lines).strip()


def read_pending() -> str:
    try:
        raw = PENDING_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except OSError as e:
        logger.warning("Could not read changelog pending file: %s", e)
        return ""
    return _strip_notes(raw)


def has_pending() -> bool:
    return bool(read_pending())


def _pending_header() -> str:
    return (
        "<!--\n"
        "Pending changelog notes for the next bot restart broadcast.\n"
        "Append dated bullets when shipping user-facing features.\n"
        "English notes are fine — the LLM localizes per user language.\n"
        "Lines starting with # or this HTML comment block are ignored.\n"
        "Leave empty (aside from this header) to skip the admin prompt on restart.\n"
        "-->\n"
    )


def write_pending(notes: str) -> bool:
    """Replace pending notes body (keeps the standard HTML header)."""
    body = (notes or "").strip()
    if not body:
        return False
    try:
        PENDING_PATH.write_text(_pending_header() + "\n" + body + "\n", encoding="utf-8")
        return True
    except OSError as e:
        logger.error("Could not write pending changelog: %s", e)
        return False


def archive_and_clear(notes: str | None = None, *, reason: str = "cleared") -> None:
    body = notes if notes is not None else read_pending()
    # Prefer archiving the stripped notes we actually considered; if empty, nothing to do.
    if not body:
        try:
            if PENDING_PATH.exists():
                PENDING_PATH.write_text(_pending_header(), encoding="utf-8")
        except OSError as e:
            logger.warning("Could not reset empty pending changelog: %s", e)
        return
    stamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    block = f"\n## {stamp} ({reason})\n\n{body.strip()}\n"
    try:
        with ARCHIVE_PATH.open("a", encoding="utf-8") as f:
            f.write(block)
    except OSError as e:
        logger.error("Could not append changelog archive: %s", e)
        return
    try:
        PENDING_PATH.write_text(_pending_header(), encoding="utf-8")
    except OSError as e:
        logger.error("Could not clear pending changelog: %s", e)


def _admin_lang_token():
    if not _admin_id or not _resolve_admin_lang:
        return msg.use_lang(DEFAULT_LANG)
    try:
        lang = _resolve_admin_lang(int(_admin_id))
    except Exception:
        lang = DEFAULT_LANG
    return msg.use_lang(lang)


def _preview(notes: str) -> str:
    text = notes.strip()
    if len(text) <= _PREVIEW_LIMIT:
        return text
    return text[: _PREVIEW_LIMIT - 1] + "…"


def _keyboard(*, include_send: bool):
    rows = []
    if include_send:
        rows.append([
            InlineKeyboardButton(msg.changelog_btn_send(), callback_data="changelog:send"),
        ])
        rows.append([
            InlineKeyboardButton(msg.changelog_btn_edit(), callback_data="changelog:edit"),
        ])
    rows.append([
        InlineKeyboardButton(msg.changelog_btn_skip(), callback_data="changelog:skip"),
    ])
    return InlineKeyboardMarkup(rows)


def _prompt_text(notes: str, *, llm_ok: bool) -> str:
    if not llm_ok:
        return (
            f"{msg.changelog_llm_unavailable()}\n\n"
            f"{msg.changelog_admin_preview(_preview(notes))}"
        )
    return (
        f"{msg.changelog_admin_prompt()}\n\n"
        f"{msg.changelog_admin_preview(_preview(notes))}"
    )


async def prompt_admin(bot) -> None:
    """DM admin about pending notes after restart (no-op if empty / no admin)."""
    if not _admin_id:
        return
    notes = read_pending()
    if not notes:
        return

    token = _admin_lang_token()
    try:
        llm_ok = is_configured()
        text = _prompt_text(notes, llm_ok=llm_ok)
        kb = _keyboard(include_send=llm_ok)
    finally:
        msg.reset_lang(token)

    try:
        await bot.send_message(chat_id=int(_admin_id), text=text, reply_markup=kb)
    except Exception as e:
        logger.error("Could not DM admin changelog prompt: %s", e)


async def _reprompt_admin(bot, chat_id: int) -> None:
    notes = read_pending()
    token = _admin_lang_token()
    try:
        if not notes:
            text = msg.changelog_empty()
            kb = None
        else:
            llm_ok = is_configured()
            text = _prompt_text(notes, llm_ok=llm_ok)
            kb = _keyboard(include_send=llm_ok)
    finally:
        msg.reset_lang(token)
    await bot.send_message(chat_id=chat_id, text=text, reply_markup=kb)


def _user_lang(user_id) -> str:
    try:
        stored = _user_manager.get_language(user_id) if _user_manager else None
    except Exception:
        stored = None
    return normalize_lang(stored) or DEFAULT_LANG


async def _generate_all(notes: str, langs: set[str]) -> dict[str, str] | None:
    """Return lang → body. Falls back to English generation if a locale fails."""
    out: dict[str, str] = {}
    english = None
    for lang in sorted(langs):
        if lang not in SUPPORTED:
            lang = DEFAULT_LANG
        text = await generate_changelog(notes, lang)
        if not text and lang != "en":
            if english is None:
                english = await generate_changelog(notes, "en")
            text = english
        if not text:
            return None
        out[lang] = text
        if lang == "en":
            english = text
    return out


async def broadcast(bot, *, admin_user=None):
    """Generate localized changelogs and send to all users.

    Returns ``(sent, failed)``, ``"busy"``, ``"empty"``, or ``"llm_failed"``.
    """
    global _busy
    async with _lock:
        if _busy:
            return "busy"
        _busy = True
    try:
        notes = read_pending()
        if not notes:
            return "empty"

        user_ids = list(_user_manager.get_all_user_ids()) if _user_manager else []
        langs = {_user_lang(uid) for uid in user_ids} or {DEFAULT_LANG}
        langs.add("en")  # always have English for fallbacks

        bodies = await _generate_all(notes, langs)
        if not bodies:
            return "llm_failed"

        sent = failed = 0
        for uid in user_ids:
            lang = _user_lang(uid)
            body = bodies.get(lang) or bodies.get("en") or next(iter(bodies.values()))
            token = msg.use_lang(lang)
            try:
                header = msg.changelog_header()
            finally:
                msg.reset_lang(token)
            text = f"{header}\n\n{body}"
            try:
                await bot.send_message(chat_id=int(uid), text=text)
                sent += 1
                await asyncio.sleep(0.05)
            except Exception:
                failed += 1

        archive_and_clear(notes, reason="sent")
        if _log_broadcast and admin_user is not None:
            try:
                await _log_broadcast(bot, admin_user, sent, failed)
            except Exception:
                logger.exception("log_broadcast failed for changelog")
        return sent, failed
    finally:
        _busy = False


async def handle_edit_text(update, context) -> bool:
    """Handle admin's replacement notes after ``changelog:edit``. Returns True if handled."""
    user = update.effective_user
    if not user or str(user.id) != str(_admin_id):
        return False
    text = (update.message.text or "").strip() if update.message else ""
    token = _admin_lang_token()
    try:
        if not text:
            await update.message.reply_text(msg.changelog_edit_empty())
            return True
        if not write_pending(text):
            await update.message.reply_text(msg.changelog_edit_failed())
            return True
        await update.message.reply_text(msg.changelog_edit_saved())
    finally:
        msg.reset_lang(token)
    await _reprompt_admin(context.bot, user.id)
    return True


async def handle_callback(update, context) -> bool:
    """Handle ``changelog:send`` / ``changelog:edit`` / ``changelog:skip``."""
    query = update.callback_query
    data = (query.data or "") if query else ""
    if not data.startswith("changelog:"):
        return False

    user = update.effective_user
    if not user or str(user.id) != str(_admin_id):
        token = _admin_lang_token()
        try:
            text = msg.changelog_forbidden()
        finally:
            msg.reset_lang(token)
        try:
            await query.answer(text, show_alert=True)
        except Exception:
            pass
        return True

    action = data.split(":", 1)[1]
    token = _admin_lang_token()
    try:
        if action == "skip":
            notes = read_pending()
            archive_and_clear(notes, reason="skipped")
            text = msg.changelog_skipped()
            try:
                await query.edit_message_text(text)
            except Exception:
                await context.bot.send_message(chat_id=user.id, text=text)
            return True

        if action == "edit":
            # Ask admin for replacement notes; next text message is captured.
            context.user_data["await_input"] = {
                "kind": "changelog_edit",
                "ts": time.time(),
            }
            try:
                await query.answer()
            except Exception:
                pass
            try:
                await query.edit_message_reply_markup(reply_markup=None)
            except Exception:
                pass
            await context.bot.send_message(chat_id=user.id, text=msg.changelog_edit_prompt())
            return True

        if action != "send":
            return True

        if not is_configured():
            text = msg.changelog_llm_unavailable()
            try:
                await query.edit_message_text(text)
            except Exception:
                pass
            return True

        if _busy:
            try:
                await query.answer(msg.changelog_busy(), show_alert=True)
            except Exception:
                pass
            return True

        try:
            await query.edit_message_text(msg.changelog_generating())
        except Exception:
            pass
    finally:
        msg.reset_lang(token)

    result = await broadcast(context.bot, admin_user=user)
    token = _admin_lang_token()
    try:
        if result == "busy":
            text = msg.changelog_busy()
        elif result == "empty":
            text = msg.changelog_empty()
        elif result == "llm_failed":
            text = msg.changelog_llm_failed()
        else:
            sent, failed = result
            text = msg.changelog_done(sent, failed)
    finally:
        msg.reset_lang(token)
    try:
        await query.edit_message_text(text)
    except Exception:
        await context.bot.send_message(chat_id=user.id, text=text)
    return True
