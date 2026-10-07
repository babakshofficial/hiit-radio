"""User-submitted music: upload wizard, my submissions, admin review."""

from __future__ import annotations

import io
import logging
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from mutagen.id3 import APIC, ID3, TCON, TIT2, TPE1
from mutagen.mp3 import MP3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import entitlements
import messages as msg
import reporting as rpt

logger = logging.getLogger(__name__)

KIND = "usub"
_DEPS = {}

USER_MUSIC_DIR = os.getenv("USER_MUSIC_DIR", "user_music")
MAX_PENDING = int(os.getenv("USER_SUBMISSION_MAX_PENDING", "3"))
DAILY_PENDING = int(os.getenv("USER_SUBMISSION_DAILY_PENDING", "3"))
MAX_MB = int(os.getenv("USER_SUBMISSION_MAX_MB", "20"))
MAX_BYTES = MAX_MB * 1024 * 1024

GENRES = (
    ("pop", "usub_genre_pop"),
    ("rock", "usub_genre_rock"),
    ("hiphop", "usub_genre_hiphop"),
    ("electronic", "usub_genre_electronic"),
    ("classical", "usub_genre_classical"),
    ("jazz", "usub_genre_jazz"),
    ("folk", "usub_genre_folk"),
    ("metal", "usub_genre_metal"),
    ("rnb", "usub_genre_rnb"),
    ("other", "usub_genre_other"),
)


def init(**deps):
    _DEPS.update(deps)


def _db():
    return _DEPS["user_manager"].database


def _downloader():
    return _DEPS["downloader"]


def _orchestrator():
    return _DEPS["orchestrator"]


def _admin_id():
    return (_DEPS.get("admin_id") or os.getenv("ADMIN_ID") or "").strip()


def is_wizard(pending) -> bool:
    return bool(pending) and pending.get("kind") == KIND


def set_state(context, step, data=None):
    payload = dict(data or {})
    payload["step"] = step
    context.user_data["await_input"] = {
        "kind": KIND,
        "ts": time.time(),
        "data": payload,
    }


def clear(context):
    context.user_data.pop("await_input", None)
    st = state(context)
    tmp_audio = st.get("tmp_audio_path")
    if tmp_audio and os.path.isfile(tmp_audio):
        try:
            os.remove(tmp_audio)
        except OSError:
            pass


def state(context):
    pending = context.user_data.get("await_input") or {}
    if pending.get("kind") != KIND:
        return {}
    return dict(pending.get("data") or {})


def _music_root():
    root = Path(USER_MUSIC_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _submission_dir(user_id, submission_id=None):
    base = _music_root() / str(user_id)
    if submission_id is not None:
        base = base / str(submission_id)
    base.mkdir(parents=True, exist_ok=True)
    return base


def parse_community_id(url_or_id):
    text = (url_or_id or "").strip()
    if text.startswith("community:"):
        text = text.split(":", 1)[1]
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def submission_quota_ok(db, user_id):
    if db.count_user_pending_music_submissions(user_id) >= MAX_PENDING:
        return False, "usub_quota_max_pending"
    start_ts, _ = entitlements.day_bounds()
    if db.count_user_pending_music_submissions_since(user_id, start_ts) >= DAILY_PENDING:
        return False, "usub_quota_daily"
    return True, None


def embed_submission_tags(audio_path, title, artist, genre=None, artwork_jpeg=None):
    try:
        audio = MP3(audio_path, ID3=ID3)
        if audio.tags is None:
            audio.add_tags()
        audio.tags.delall("TIT2")
        audio.tags.delall("TPE1")
        audio.tags.delall("TCON")
        audio.tags.add(TIT2(encoding=3, text=title))
        audio.tags.add(TPE1(encoding=3, text=artist))
        if genre:
            audio.tags.add(TCON(encoding=3, text=genre))
        if artwork_jpeg:
            audio.tags.delall("APIC")
            audio.tags.add(
                APIC(
                    encoding=3,
                    mime="image/jpeg",
                    type=3,
                    desc="Cover",
                    data=artwork_jpeg,
                )
            )
        audio.save()
        return True
    except Exception as e:
        logger.error("embed_submission_tags failed: %s", e)
        return False


def _to_mp3(raw_path, dest_path):
    if raw_path.lower().endswith(".mp3"):
        shutil.copy2(raw_path, dest_path)
        return True
    try:
        proc = subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", raw_path,
                "-codec:a", "libmp3lame", "-q:a", "2",
                dest_path,
            ],
            capture_output=True,
            timeout=120,
        )
        return proc.returncode == 0 and os.path.isfile(dest_path)
    except Exception as e:
        logger.warning("ffmpeg mp3 convert failed: %s", e)
        return False


async def _download_telegram_file(bot, file_id, dest_path):
    tg_file = await bot.get_file(file_id)
    await tg_file.download_to_drive(custom_path=dest_path)


def _chat_id(message):
    if getattr(message, "chat_id", None) is not None:
        return message.chat_id
    return message.chat.id


def _cancel_row():
    return [InlineKeyboardButton(msg.t("awiz_cancel"), callback_data="usub:cancel")]


def _back_menu_row():
    return [InlineKeyboardButton(msg.t("menu_back"), callback_data="menu:back")]


def _genre_keyboard():
    rows = []
    row = []
    for code, key in GENRES:
        row.append(
            InlineKeyboardButton(msg.t(key), callback_data=f"usub:g:{code}"),
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(_cancel_row())
    return InlineKeyboardMarkup(rows)


async def start_submit(message, context):
    ok, reason = submission_quota_ok(_db(), _chat_id(message))
    if not ok:
        await message.reply_text(msg.t(reason), reply_markup=InlineKeyboardMarkup([_back_menu_row()]))
        return
    set_state(context, "audio", {})
    await message.reply_text(
        msg.t("usub_prompt_audio"),
        reply_markup=InlineKeyboardMarkup([_cancel_row(), _back_menu_row()]),
    )


async def start_my_submissions(message, context, page=0):
    rows, total, total_pages = _db().list_user_music_submissions(_chat_id(message), page, rpt.PER_PAGE)
    lines = [msg.t("usub_my_header"), ""]
    if not rows:
        lines.append(msg.t("usub_my_empty"))
    else:
        for row in rows:
            lines.append(
                msg.t(
                    "usub_my_line",
                    title=row["title"],
                    artist=row["artist"],
                    status=msg.t(f"usub_status_{row['status']}"),
                )
            )
    buttons = []
    for row in rows:
        buttons.append([
            InlineKeyboardButton(
                f"{row['title'][:20]} — {row['artist'][:15]}",
                callback_data=f"usub:v:{row['id']}",
            )
        ])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀", callback_data=f"usub:my:{page - 1}"))
    if page + 1 < total_pages:
        nav.append(InlineKeyboardButton("▶", callback_data=f"usub:my:{page + 1}"))
    if nav:
        buttons.append(nav)
    buttons.append([
        InlineKeyboardButton(msg.t("usub_btn_submit"), callback_data="menu:submit_music"),
    ])
    buttons.append(_back_menu_row())
    await message.reply_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def show_submission_detail(message, context, submission_id, user_id):
    row = _db().get_user_music_submission(submission_id)
    if not row or str(row["user_id"]) != str(user_id):
        await message.reply_text(msg.t("usub_not_found"), reply_markup=InlineKeyboardMarkup([_back_menu_row()]))
        return
    text = msg.t(
        "usub_detail",
        title=row["title"],
        artist=row["artist"],
        genre=row.get("genre") or "—",
        status=msg.t(f"usub_status_{row['status']}"),
    )
    buttons = []
    if row["status"] == "pending":
        buttons.append([
            InlineKeyboardButton(msg.t("usub_btn_withdraw"), callback_data=f"usub:w:{row['id']}"),
        ])
    buttons.append([InlineKeyboardButton(msg.t("usub_btn_my_list"), callback_data="menu:my_submissions")])
    buttons.append(_back_menu_row())
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    if row.get("audio_path") and os.path.isfile(row["audio_path"]):
        try:
            with open(row["audio_path"], "rb") as f:
                await message.reply_audio(
                    audio=f,
                    title=row["title"],
                    performer=row["artist"],
                )
        except Exception as e:
            logger.debug("preview audio failed: %s", e)


async def withdraw_submission(message, context, submission_id, user_id):
    row = _db().get_user_music_submission(submission_id)
    if not row or str(row["user_id"]) != str(user_id) or row["status"] != "pending":
        await message.reply_text(msg.t("usub_not_found"), reply_markup=InlineKeyboardMarkup([_back_menu_row()]))
        return
    _delete_submission_files(row)
    _db().update_user_music_submission(submission_id, status="withdrawn")
    await message.reply_text(msg.t("usub_withdrawn"), reply_markup=InlineKeyboardMarkup([_back_menu_row()]))


def _delete_submission_files(row):
    for key in ("audio_path", "artwork_path"):
        path = row.get(key)
        if path and os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                pass


async def on_audio_message(update, context):
    pending = context.user_data.get("await_input")
    if not pending or pending.get("kind") != KIND:
        return False
    st = state(context)
    if st.get("step") != "audio":
        return False
    message = update.message
    user_id = message.chat.id
    ok, reason = submission_quota_ok(_db(), user_id)
    if not ok:
        clear(context)
        await message.reply_text(msg.t(reason), reply_markup=InlineKeyboardMarkup([_back_menu_row()]))
        return True

    file_id = None
    size = 0
    if message.audio:
        file_id = message.audio.file_id
        size = message.audio.file_size or 0
    elif message.document:
        mime = (message.document.mime_type or "").lower()
        if not mime.startswith("audio/"):
            await message.reply_text(msg.t("usub_bad_audio"), reply_markup=InlineKeyboardMarkup([_cancel_row()]))
            return True
        file_id = message.document.file_id
        size = message.document.file_size or 0
    else:
        return False

    if size > MAX_BYTES:
        await message.reply_text(
            msg.t("usub_audio_too_large", max_mb=MAX_MB),
            reply_markup=InlineKeyboardMarkup([_cancel_row()]),
        )
        return True

    tmp_dir = _submission_dir(user_id, "draft")
    raw_path = str(tmp_dir / f"raw_{int(time.time())}")
    await _download_telegram_file(context.bot, file_id, raw_path)
    mp3_path = str(tmp_dir / f"draft_{int(time.time())}.mp3")
    if not _to_mp3(raw_path, mp3_path):
        try:
            os.remove(raw_path)
        except OSError:
            pass
        await message.reply_text(msg.t("usub_bad_audio"), reply_markup=InlineKeyboardMarkup([_cancel_row()]))
        return True
    try:
        if os.path.isfile(raw_path) and raw_path != mp3_path:
            os.remove(raw_path)
    except OSError:
        pass

    set_state(
        context,
        "title",
        {
            "tmp_audio_path": mp3_path,
            "telegram_audio_file_id": file_id,
        },
    )
    await message.reply_text(msg.t("usub_prompt_title"), reply_markup=InlineKeyboardMarkup([_cancel_row()]))
    return True


async def on_photo_message(update, context):
    pending = context.user_data.get("await_input")
    if not pending or pending.get("kind") != KIND:
        return False
    st = state(context)
    if st.get("step") != "artwork":
        return False
    message = update.message
    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document:
        mime = (message.document.mime_type or "").lower()
        if not mime.startswith("image/"):
            await message.reply_text(msg.t("usub_bad_artwork"), reply_markup=InlineKeyboardMarkup([_cancel_row()]))
            return True
        file_id = message.document.file_id
    else:
        return False

    raw = bytes(await (await context.bot.get_file(file_id)).download_as_bytearray())
    processed = _downloader()._process_cover_artwork(raw)
    if not processed:
        await message.reply_text(msg.t("usub_bad_artwork"), reply_markup=InlineKeyboardMarkup([_cancel_row()]))
        return True

    await _finalize_submission(update, context, st, processed)
    return True


async def on_text(update, context, pending):
    st = dict(pending.get("data") or {})
    step = st.get("step")
    text = (update.message.text or "").strip()
    message = update.message
    user_id = message.chat.id

    if step == "title":
        if len(text) < 1 or len(text) > 200:
            await message.reply_text(msg.t("usub_title_invalid"), reply_markup=InlineKeyboardMarkup([_cancel_row()]))
            return
        st["title"] = text
        set_state(context, "artist", st)
        await message.reply_text(msg.t("usub_prompt_artist"), reply_markup=InlineKeyboardMarkup([_cancel_row()]))
        return

    if step == "artist":
        if len(text) < 1 or len(text) > 200:
            await message.reply_text(msg.t("usub_artist_invalid"), reply_markup=InlineKeyboardMarkup([_cancel_row()]))
            return
        st["artist"] = text
        set_state(context, "genre", st)
        await message.reply_text(
            msg.t("usub_prompt_genre"),
            reply_markup=_genre_keyboard(),
        )
        return

    if step == "genre_other":
        if len(text) < 1 or len(text) > 80:
            await message.reply_text(msg.t("usub_genre_invalid"), reply_markup=InlineKeyboardMarkup([_cancel_row()]))
            return
        st["genre"] = text
        set_state(context, "artwork", st)
        await message.reply_text(
            msg.t("usub_prompt_artwork"),
            reply_markup=InlineKeyboardMarkup([_cancel_row()]),
        )
        return

    if step == "reject_reason":
        sid = st.get("reject_submission_id")
        if sid and text:
            await _reject_submission(message, context, int(sid), text, update.effective_user.id)
        clear(context)
        return


async def on_genre_callback(query, context, code):
    st = state(context)
    if st.get("step") != "genre":
        return
    if code == "other":
        set_state(context, "genre_other", st)
        await query.message.edit_text(
            msg.t("usub_prompt_genre_other"),
            reply_markup=InlineKeyboardMarkup([_cancel_row()]),
        )
        return
    label_key = next((k for c, k in GENRES if c == code), None)
    st["genre"] = msg.t(label_key) if label_key else code
    set_state(context, "artwork", st)
    await query.message.edit_text(
        msg.t("usub_prompt_artwork"),
        reply_markup=InlineKeyboardMarkup([_cancel_row()]),
    )


async def _finalize_submission(update, context, st, artwork_jpeg):
    message = update.message
    user_id = message.chat.id
    user = update.effective_user
    tmp_audio = st.get("tmp_audio_path")
    if not tmp_audio or not os.path.isfile(tmp_audio):
        clear(context)
        await message.reply_text(msg.t("usub_session_expired"), reply_markup=InlineKeyboardMarkup([_back_menu_row()]))
        return

    title = st.get("title", "").strip()
    artist = st.get("artist", "").strip()
    genre = st.get("genre", "").strip()
    if not title or not artist:
        await message.reply_text(msg.t("usub_session_expired"), reply_markup=InlineKeyboardMarkup([_cancel_row()]))
        return

    db = _db()
    sub_id = db.create_user_music_submission(
        user_id,
        title=title,
        artist=artist,
        genre=genre,
        audio_path=tmp_audio,
        telegram_audio_file_id=st.get("telegram_audio_file_id"),
    )
    dest_dir = _submission_dir(user_id, sub_id)
    audio_final = str(dest_dir / "track.mp3")
    art_final = str(dest_dir / "cover.jpg")
    shutil.move(tmp_audio, audio_final)
    with open(art_final, "wb") as f:
        f.write(artwork_jpeg)
    embed_submission_tags(audio_final, title, artist, genre, artwork_jpeg)
    db.update_user_music_submission(
        sub_id,
        audio_path=audio_final,
        artwork_path=art_final,
    )

    clear(context)
    await message.reply_text(
        msg.t("usub_submitted", title=title, artist=artist),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(msg.t("usub_btn_my_list"), callback_data="menu:my_submissions")],
            _back_menu_row(),
        ]),
    )
    await _notify_admin_new(context.bot, sub_id, user)


async def _notify_admin_new(bot, submission_id, user):
    admin = _admin_id()
    if not admin:
        return
    row = _db().get_user_music_submission(submission_id)
    if not row:
        return
    try:
        uname = f"@{user.username}" if user and user.username else "—"
        await bot.send_message(
            int(admin),
            msg.t(
                "usub_admin_new",
                id=submission_id,
                title=row["title"],
                artist=row["artist"],
                user_id=row["user_id"],
                username=uname,
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(msg.t("usub_admin_review"), callback_data=f"usub:adm:v:{submission_id}")],
            ]),
        )
    except Exception as e:
        logger.debug("admin notify failed: %s", e)


# --- Admin ---


def _admin_back():
    return [InlineKeyboardButton(msg.t("menu_admin_back"), callback_data="admin:menu")]


async def start_admin_queue(message, context, page=0):
    rows, total, total_pages = _db().list_pending_user_music_submissions(page, rpt.PER_PAGE)
    lines = [msg.t("usub_admin_queue_header", count=total), ""]
    if not rows:
        lines.append(msg.t("usub_admin_queue_empty"))
    for row in rows:
        uname = f"@{row['username']}" if row.get("username") else row["user_id"]
        lines.append(
            msg.t(
                "usub_admin_queue_line",
                id=row["id"],
                title=row["title"],
                artist=row["artist"],
                user=uname,
            )
        )
    buttons = []
    for row in rows:
        buttons.append([
            InlineKeyboardButton(
                f"#{row['id']} {row['title'][:18]}",
                callback_data=f"usub:adm:v:{row['id']}",
            )
        ])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀", callback_data=f"usub:adm:p:{page - 1}"))
    if page + 1 < total_pages:
        nav.append(InlineKeyboardButton("▶", callback_data=f"usub:adm:p:{page + 1}"))
    if nav:
        buttons.append(nav)
    buttons.append(_admin_back())
    await message.reply_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(buttons))


async def show_admin_detail(message, context, submission_id):
    row = _db().get_user_music_submission(submission_id)
    if not row:
        await message.reply_text(msg.t("usub_not_found"), reply_markup=InlineKeyboardMarkup([_admin_back()]))
        return
    uname = row.get("username") or row["user_id"]
    text = msg.t(
        "usub_admin_detail",
        id=row["id"],
        title=row["title"],
        artist=row["artist"],
        genre=row.get("genre") or "—",
        status=msg.t(f"usub_status_{row['status']}"),
        user_id=row["user_id"],
        username=uname,
    )
    buttons = [
        [
            InlineKeyboardButton(msg.t("usub_admin_listen"), callback_data=f"usub:adm:listen:{row['id']}"),
            InlineKeyboardButton(msg.t("usub_admin_artwork"), callback_data=f"usub:adm:art:{row['id']}"),
        ],
    ]
    if row["status"] == "pending":
        buttons.append([
            InlineKeyboardButton(msg.t("usub_admin_approve"), callback_data=f"usub:adm:ok:{row['id']}"),
            InlineKeyboardButton(msg.t("usub_admin_reject"), callback_data=f"usub:adm:no:{row['id']}"),
        ])
    buttons.append([InlineKeyboardButton(msg.t("usub_admin_back_queue"), callback_data="admin:usub")])
    buttons.append(_admin_back())
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))


async def admin_listen(message, context, submission_id):
    row = _db().get_user_music_submission(submission_id)
    if not row or not row.get("audio_path") or not os.path.isfile(row["audio_path"]):
        await message.reply_text(msg.t("usub_not_found"))
        return
    with open(row["audio_path"], "rb") as f:
        await message.reply_audio(
            audio=f,
            title=row["title"],
            performer=row["artist"],
        )


async def admin_artwork(message, context, submission_id):
    row = _db().get_user_music_submission(submission_id)
    path = row.get("artwork_path") if row else None
    if not path or not os.path.isfile(path):
        await message.reply_text(msg.t("usub_no_artwork"))
        return
    with open(path, "rb") as f:
        await message.reply_photo(photo=f)


async def approve_submission(message, context, submission_id, admin_user_id):
    db = _db()
    row = db.get_user_music_submission(submission_id)
    if not row or row["status"] != "pending":
        await message.reply_text(msg.t("usub_not_found"), reply_markup=InlineKeyboardMarkup([_admin_back()]))
        return
    audio_path = row["audio_path"]
    if row.get("artwork_path") and os.path.isfile(row["artwork_path"]):
        with open(row["artwork_path"], "rb") as f:
            art = f.read()
        embed_submission_tags(
            audio_path, row["title"], row["artist"], row.get("genre"), art,
        )

    from downloader import DEFAULT_QUALITY, QUALITIES

    orch = _orchestrator()
    for quality in QUALITIES:
        cache_source = f"community:{quality}"
        orch.cache.put(row["title"], row["artist"], cache_source, audio_path)

    orch.cache.put(row["title"], row["artist"], "community", audio_path)

    bonus_amount = 0
    if not row.get("quota_bonus_granted"):
        bonus_amount, _day = entitlements.grant_music_approval_bonus(
            db, row["user_id"], submission_id,
        )
    if not row.get("quota_bonus_granted"):
        db.update_user_music_submission(submission_id, quota_bonus_granted=1)

    now = time.time()
    db.update_user_music_submission(
        submission_id,
        status="approved",
        admin_id=str(admin_user_id),
        reviewed_at=now,
    )

    snap = entitlements.status_snapshot(db, row["user_id"])
    try:
        if bonus_amount and snap.get("limit") is not None:
            note = msg.t(
                "usub_approved_user_bonus",
                title=row["title"],
                bonus=bonus_amount,
                used=snap["used"],
                limit=snap["limit"],
            )
        else:
            note = msg.t("usub_approved_user", title=row["title"])
        await context.bot.send_message(int(row["user_id"]), note)
    except Exception as e:
        logger.debug("approve notify failed: %s", e)

    await message.reply_text(
        msg.t("usub_admin_approved_ok", id=submission_id),
        reply_markup=InlineKeyboardMarkup([_admin_back()]),
    )


async def start_reject(message, context, submission_id):
    set_state(context, "reject_reason", {"reject_submission_id": submission_id})
    await message.reply_text(
        msg.t("usub_admin_reject_prompt"),
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(msg.t("usub_reject_low_quality"), callback_data=f"usub:adm:rej:{submission_id}:quality"),
                InlineKeyboardButton(msg.t("usub_reject_rights"), callback_data=f"usub:adm:rej:{submission_id}:rights"),
            ],
            [
                InlineKeyboardButton(msg.t("usub_reject_metadata"), callback_data=f"usub:adm:rej:{submission_id}:metadata"),
            ],
            _admin_back(),
        ]),
    )


async def _reject_submission(message, context, submission_id, reason, admin_user_id):
    db = _db()
    row = db.get_user_music_submission(submission_id)
    if not row or row["status"] != "pending":
        await message.reply_text(msg.t("usub_not_found"), reply_markup=InlineKeyboardMarkup([_admin_back()]))
        return
    db.update_user_music_submission(
        submission_id,
        status="rejected",
        admin_id=str(admin_user_id),
        reviewed_at=time.time(),
        reject_reason=(reason or "")[:500],
    )
    try:
        await context.bot.send_message(
            int(row["user_id"]),
            msg.t("usub_rejected_user", title=row["title"], reason=reason or "—"),
        )
    except Exception:
        pass
    await message.reply_text(
        msg.t("usub_admin_rejected_ok", id=submission_id),
        reply_markup=InlineKeyboardMarkup([_admin_back()]),
    )


async def on_callback(update, context):
    query = update.callback_query
    data = query.data or ""
    parts = data.split(":")

    if data == "usub:cancel":
        clear(context)
        await query.message.edit_text(msg.t("awiz_cancelled"))
        return

    if len(parts) >= 3 and parts[0] == "usub" and parts[1] == "g":
        await on_genre_callback(query, context, parts[2])
        return

    if len(parts) >= 3 and parts[0] == "usub" and parts[1] == "v":
        await show_submission_detail(query.message, context, int(parts[2]), update.effective_user.id)
        return

    if len(parts) >= 3 and parts[0] == "usub" and parts[1] == "w":
        await withdraw_submission(query.message, context, int(parts[2]), update.effective_user.id)
        return

    if len(parts) >= 3 and parts[0] == "usub" and parts[1] == "my":
        await start_my_submissions(query.message, context, int(parts[2]))
        return

    if len(parts) >= 4 and parts[0] == "usub" and parts[1] == "adm":
        admin = _admin_id()
        if not admin or str(update.effective_user.id) != str(admin):
            return
        action = parts[2]
        sid = int(parts[3])
        if action == "p":
            await start_admin_queue(query.message, context, sid)
            return
        if action == "v":
            await show_admin_detail(query.message, context, sid)
            return
        if action == "listen":
            await admin_listen(query.message, context, sid)
            return
        if action == "art":
            await admin_artwork(query.message, context, sid)
            return
        if action == "ok":
            await approve_submission(query.message, context, sid, update.effective_user.id)
            return
        if action == "no":
            await start_reject(query.message, context, sid)
            return
        if action == "rej" and len(parts) >= 5:
            reasons = {
                "quality": msg.t("usub_reject_low_quality"),
                "rights": msg.t("usub_reject_rights"),
                "metadata": msg.t("usub_reject_metadata"),
            }
            await _reject_submission(
                query.message, context, sid, reasons.get(parts[4], parts[4]), update.effective_user.id,
            )
            return
