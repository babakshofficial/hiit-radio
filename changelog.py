"""Pending changelog notes → admin prompt → per-language LLM review → fan-out."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from collections import defaultdict
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
_REVIEW_KEY = "changelog_review"

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
    """Drop HTML comments, single-# comment lines, and blank-only content."""
    if not raw:
        return ""
    text = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
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


def _lang_display_name(lang: str) -> str:
    key = f"lang_name_{lang}"
    try:
        return msg.t(key)
    except Exception:
        return lang


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


def _get_review(context) -> dict | None:
    review = (context.user_data or {}).get(_REVIEW_KEY)
    return review if isinstance(review, dict) else None


def _set_review(context, review: dict) -> None:
    context.user_data[_REVIEW_KEY] = review


def _clear_review(context) -> None:
    context.user_data.pop(_REVIEW_KEY, None)


def _user_lang(user_id) -> str:
    try:
        stored = _user_manager.get_language(user_id) if _user_manager else None
    except Exception:
        stored = None
    lang = normalize_lang(stored) or DEFAULT_LANG
    return lang if lang in SUPPORTED else DEFAULT_LANG


def _lang_audience() -> tuple[dict[str, list], dict[str, int]]:
    """Return (user_ids_by_lang, counts) for all bot users."""
    user_ids_by_lang: dict[str, list] = defaultdict(list)
    user_ids = list(_user_manager.get_all_user_ids()) if _user_manager else []
    if not user_ids:
        user_ids_by_lang[DEFAULT_LANG] = []
    for uid in user_ids:
        lang = _user_lang(uid)
        user_ids_by_lang[lang].append(uid)
    counts = {lang: len(uids) for lang, uids in user_ids_by_lang.items()}
    return dict(user_ids_by_lang), counts


def _active_langs(counts: dict[str, int]) -> list[str]:
    return sorted(lang for lang, n in counts.items() if n > 0)


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


async def _reprompt_admin(bot, chat_id: int, context=None) -> None:
    if context is not None:
        _clear_review(context)
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


async def _generate_one(notes: str, lang: str) -> str | None:
    if lang not in SUPPORTED:
        lang = DEFAULT_LANG
    text = await generate_changelog(notes, lang)
    if not text and lang != "en":
        text = await generate_changelog(notes, "en")
    return text


async def _generate_all(notes: str, langs: set[str]) -> dict[str, str | None]:
    """Return lang → body (None when LLM failed for that lang)."""
    out: dict[str, str | None] = {}
    english = None
    for lang in sorted(langs):
        resolved = lang if lang in SUPPORTED else DEFAULT_LANG
        text = await generate_changelog(notes, resolved)
        if not text and resolved != "en":
            if english is None:
                english = await generate_changelog(notes, "en")
            text = english
        out[lang] = text
        if resolved == "en" and text:
            english = text
    return out


def _lang_card_keyboard(lang: str, review: dict) -> InlineKeyboardMarkup | None:
    status = review["status"].get(lang, "pending")
    if status in ("sent", "skipped"):
        return None
    body = review["bodies"].get(lang)
    rows = []
    if body:
        rows.append([
            InlineKeyboardButton(
                msg.changelog_btn_send(),
                callback_data=f"changelog:lang:send:{lang}",
            ),
        ])
    rows.append([
        InlineKeyboardButton(
            msg.changelog_btn_skip(),
            callback_data=f"changelog:lang:skip:{lang}",
        ),
        InlineKeyboardButton(
            msg.changelog_btn_edit(),
            callback_data=f"changelog:lang:edit:{lang}",
        ),
    ])
    rows.append([
        InlineKeyboardButton(
            msg.changelog_btn_regenerate(),
            callback_data=f"changelog:lang:regen:{lang}",
        ),
    ])
    return InlineKeyboardMarkup(rows)


def _render_lang_card(lang: str, review: dict) -> tuple[str, InlineKeyboardMarkup | None]:
    count = review["counts"].get(lang, 0)
    lang_name = _lang_display_name(lang)
    status = review["status"].get(lang, "pending")
    body = review["bodies"].get(lang)

    token = msg.use_lang(lang)
    try:
        header = msg.changelog_header()
    finally:
        msg.reset_lang(token)

    admin_token = _admin_lang_token()
    try:
        if status == "sent":
            stats = review.get("send_stats", {}).get(lang, {})
            footer = msg.changelog_lang_sent(
                stats.get("sent", 0), stats.get("failed", 0),
            )
            text = msg.changelog_lang_card(
                lang_name=lang_name, count=count, header=header,
                body=body or msg.changelog_lang_llm_failed(lang_name=lang_name),
            )
            return f"{text}\n\n{footer}", None
        if status == "skipped":
            text = msg.changelog_lang_card(
                lang_name=lang_name, count=count, header=header,
                body=body or msg.changelog_lang_llm_failed(lang_name=lang_name),
            )
            return f"{text}\n\n{msg.changelog_lang_skipped(lang_name=lang_name)}", None
        if not body:
            text = msg.changelog_lang_card(
                lang_name=lang_name, count=count, header=header,
                body=msg.changelog_lang_llm_failed(lang_name=lang_name),
            )
        else:
            text = msg.changelog_lang_card(
                lang_name=lang_name, count=count, header=header, body=body,
            )
        return text, _lang_card_keyboard(lang, review)
    finally:
        msg.reset_lang(admin_token)


async def _update_lang_card(bot, chat_id: int, review: dict, lang: str) -> None:
    text, markup = _render_lang_card(lang, review)
    msg_id = review.get("card_msg_ids", {}).get(lang)
    if not msg_id:
        return
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=text,
            reply_markup=markup,
        )
    except Exception as e:
        logger.debug("Could not edit lang card %s: %s", lang, e)


async def _broadcast_lang(bot, review: dict, lang: str) -> tuple[int, int]:
    body = review["bodies"].get(lang)
    if not body:
        return 0, 0
    token = msg.use_lang(lang)
    try:
        header = msg.changelog_header()
    finally:
        msg.reset_lang(token)
    text = f"{header}\n\n{body}"
    sent = failed = 0
    for uid in review["user_ids_by_lang"].get(lang, []):
        try:
            await bot.send_message(chat_id=int(uid), text=text)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
    return sent, failed


def _review_complete(review: dict) -> bool:
    active = _active_langs(review["counts"])
    if not active:
        return True
    return all(
        review["status"].get(lang, "pending") in ("sent", "skipped")
        for lang in active
    )


async def _maybe_finish_review(bot, context, review: dict, admin_user=None) -> bool:
    if not _review_complete(review):
        return False
    notes = review.get("notes") or ""
    total_sent = total_failed = 0
    sent_langs = skipped_langs = 0
    for lang in _active_langs(review["counts"]):
        st = review["status"].get(lang, "pending")
        if st == "sent":
            sent_langs += 1
            stats = review.get("send_stats", {}).get(lang, {})
            total_sent += stats.get("sent", 0)
            total_failed += stats.get("failed", 0)
        elif st == "skipped":
            skipped_langs += 1

    archive_and_clear(notes, reason="sent")
    _clear_review(context)

    chat_id = admin_user.id if admin_user else int(_admin_id)
    token = _admin_lang_token()
    try:
        summary = msg.changelog_all_done(
            sent_langs=sent_langs,
            skipped_langs=skipped_langs,
            sent=total_sent,
            failed=total_failed,
        )
    finally:
        msg.reset_lang(token)
    try:
        await bot.send_message(chat_id=chat_id, text=summary)
    except Exception as e:
        logger.error("Could not send changelog summary: %s", e)

    if _log_broadcast and admin_user is not None:
        try:
            await _log_broadcast(bot, admin_user, total_sent, total_failed)
        except Exception:
            logger.exception("log_broadcast failed for changelog")
    return True


async def _post_lang_cards(bot, chat_id: int, review: dict) -> None:
    for lang in _active_langs(review["counts"]):
        text, markup = _render_lang_card(lang, review)
        try:
            sent = await bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)
            review.setdefault("card_msg_ids", {})[lang] = sent.message_id
        except Exception as e:
            logger.error("Could not post changelog card for %s: %s", lang, e)


async def _start_review(bot, context, user, query) -> str | None:
    """Generate per-language previews. Returns error message key or None on success."""
    global _busy
    notes = read_pending()
    if not notes:
        return "empty"
    if not is_configured():
        return "llm_unavailable"

    async with _lock:
        if _busy:
            return "busy"
        _busy = True
    try:
        user_ids_by_lang, counts = _lang_audience()
        active = set(_active_langs(counts))
        if not active:
            active = {DEFAULT_LANG}
            counts = {DEFAULT_LANG: 0}
            user_ids_by_lang = {DEFAULT_LANG: []}

        bodies = await _generate_all(notes, active)
        review = {
            "notes": notes,
            "bodies": bodies,
            "counts": counts,
            "user_ids_by_lang": user_ids_by_lang,
            "status": {lang: "pending" for lang in active},
            "send_stats": {},
            "card_msg_ids": {},
        }
        _set_review(context, review)

        token = _admin_lang_token()
        try:
            status_text = msg.changelog_review_started()
        finally:
            msg.reset_lang(token)
        try:
            await query.edit_message_text(status_text)
        except Exception:
            await bot.send_message(chat_id=user.id, text=status_text)

        await _post_lang_cards(bot, user.id, review)
        _set_review(context, review)
        return None
    finally:
        _busy = False


async def handle_lang_edit_text(update, context, *, lang: str | None = None) -> bool:
    """Handle admin text after ``changelog:lang:edit:{lang}``."""
    user = update.effective_user
    if not user or str(user.id) != str(_admin_id):
        return False
    if not lang:
        return False

    review = _get_review(context)
    if not review:
        token = _admin_lang_token()
        try:
            await update.message.reply_text(msg.changelog_empty())
        finally:
            msg.reset_lang(token)
        return True

    text = (update.message.text or "").strip()
    lang_name = _lang_display_name(lang)
    admin_token = _admin_lang_token()
    try:
        if not text:
            await update.message.reply_text(msg.changelog_lang_edit_empty(lang_name=lang_name))
            context.user_data["await_input"] = {
                "kind": "changelog_lang_edit",
                "ts": time.time(),
                "data": {"lang": lang},
            }
            return True
        review["bodies"][lang] = text
        if review["status"].get(lang) == "pending":
            pass
        await update.message.reply_text(msg.changelog_lang_edit_saved(lang_name=lang_name))
    finally:
        msg.reset_lang(admin_token)

    _set_review(context, review)
    await _update_lang_card(context.bot, user.id, review, lang)
    return True


async def handle_edit_text(update, context) -> bool:
    """Handle admin's replacement notes after ``changelog:edit``."""
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
    await _reprompt_admin(context.bot, user.id, context)
    return True


async def _handle_lang_callback(query, context, user, action: str, lang: str) -> None:
    global _busy
    review = _get_review(context)
    if not review or lang not in review.get("counts", {}):
        token = _admin_lang_token()
        try:
            await query.answer(msg.changelog_empty(), show_alert=True)
        finally:
            msg.reset_lang(token)
        return

    lang_name = _lang_display_name(lang)
    admin_token = _admin_lang_token()

    if action == "skip":
        review["status"][lang] = "skipped"
        _set_review(context, review)
        try:
            await query.answer()
        except Exception:
            pass
        await _update_lang_card(context.bot, user.id, review, lang)
        msg.reset_lang(admin_token)
        await _maybe_finish_review(context.bot, context, review, admin_user=user)
        return

    if action == "edit":
        context.user_data["await_input"] = {
            "kind": "changelog_lang_edit",
            "ts": time.time(),
            "data": {"lang": lang},
        }
        try:
            await query.answer()
        except Exception:
            pass
        try:
            await context.bot.send_message(
                chat_id=user.id,
                text=msg.changelog_lang_edit_prompt(lang_name=lang_name),
            )
        finally:
            msg.reset_lang(admin_token)
        return

    if action == "regen":
        if _busy:
            try:
                await query.answer(msg.changelog_busy(), show_alert=True)
            except Exception:
                pass
            msg.reset_lang(admin_token)
            return
        async with _lock:
            if _busy:
                try:
                    await query.answer(msg.changelog_busy(), show_alert=True)
                except Exception:
                    pass
                msg.reset_lang(admin_token)
                return
            _busy = True
        try:
            try:
                await query.answer()
            except Exception:
                pass
            try:
                await query.edit_message_text(
                    msg.changelog_lang_regenerating(lang_name=lang_name),
                )
            except Exception:
                pass
            body = await _generate_one(review["notes"], lang)
            review["bodies"][lang] = body
            review["status"][lang] = "pending"
            _set_review(context, review)
            await _update_lang_card(context.bot, user.id, review, lang)
        finally:
            _busy = False
            msg.reset_lang(admin_token)
        return

    if action == "send":
        if review["status"].get(lang) != "pending":
            try:
                await query.answer()
            except Exception:
                pass
            msg.reset_lang(admin_token)
            return
        if not review["bodies"].get(lang):
            try:
                await query.answer(msg.changelog_llm_failed(), show_alert=True)
            except Exception:
                pass
            msg.reset_lang(admin_token)
            return
        if _busy:
            try:
                await query.answer(msg.changelog_busy(), show_alert=True)
            except Exception:
                pass
            msg.reset_lang(admin_token)
            return
        async with _lock:
            if _busy:
                try:
                    await query.answer(msg.changelog_busy(), show_alert=True)
                except Exception:
                    pass
                msg.reset_lang(admin_token)
                return
            _busy = True
        try:
            try:
                await query.answer()
            except Exception:
                pass
            sent, failed = await _broadcast_lang(context.bot, review, lang)
            review["status"][lang] = "sent"
            review.setdefault("send_stats", {})[lang] = {"sent": sent, "failed": failed}
            _set_review(context, review)
            await _update_lang_card(context.bot, user.id, review, lang)
            await _maybe_finish_review(context.bot, context, review, admin_user=user)
        finally:
            _busy = False
            msg.reset_lang(admin_token)
        return

    msg.reset_lang(admin_token)


async def handle_callback(update, context) -> bool:
    """Handle changelog admin callbacks."""
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

    parts = data.split(":")
    if len(parts) >= 4 and parts[1] == "lang":
        action, lang = parts[2], parts[3]
        if lang not in SUPPORTED:
            lang = normalize_lang(lang) or DEFAULT_LANG
        await _handle_lang_callback(query, context, user, action, lang)
        return True

    action = parts[1] if len(parts) > 1 else ""
    token = _admin_lang_token()
    try:
        if action == "skip":
            _clear_review(context)
            notes = read_pending()
            archive_and_clear(notes, reason="skipped")
            text = msg.changelog_skipped()
            try:
                await query.edit_message_text(text)
            except Exception:
                await context.bot.send_message(chat_id=user.id, text=text)
            return True

        if action == "edit":
            _clear_review(context)
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

    err = await _start_review(context.bot, context, user, query)
    token = _admin_lang_token()
    try:
        if err == "busy":
            text = msg.changelog_busy()
        elif err == "empty":
            text = msg.changelog_empty()
        elif err == "llm_unavailable":
            text = msg.changelog_llm_unavailable()
        else:
            return True
    finally:
        msg.reset_lang(token)
    try:
        await query.edit_message_text(text)
    except Exception:
        await context.bot.send_message(chat_id=user.id, text=text)
    return True
