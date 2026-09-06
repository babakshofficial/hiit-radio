"""Interactive Q&A wizards for admin tools (grant, topup, broadcast, …)."""

from __future__ import annotations

import asyncio
import logging
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import entitlements
import messages as msg
import payments
import reporting as rpt

logger = logging.getLogger(__name__)

KIND = "awiz"
_DEPS = {}


def init(**deps):
    _DEPS.update(deps)


def _um():
    return _DEPS["user_manager"]


def is_wizard(pending) -> bool:
    return bool(pending) and pending.get("kind") == KIND


def _admin_back_row():
    return [InlineKeyboardButton(msg.t("menu_admin_back"), callback_data="admin:menu")]


def _cancel_row():
    return [InlineKeyboardButton(msg.t("awiz_cancel"), callback_data="awiz:cancel")]


def _confirm_rows():
    return [
        [
            InlineKeyboardButton(msg.t("awiz_confirm"), callback_data="awiz:ok"),
            InlineKeyboardButton(msg.t("awiz_cancel"), callback_data="awiz:cancel"),
        ],
        _admin_back_row(),
    ]


def _kb(rows):
    out = [list(r) for r in rows]
    if not any(
        getattr(b, "callback_data", None) in ("awiz:cancel", "admin:menu")
        for row in out for b in row
    ):
        out.append(_cancel_row())
    if not any(getattr(b, "callback_data", None) == "admin:menu" for row in out for b in row):
        out.append(_admin_back_row())
    return InlineKeyboardMarkup(out)


def set_state(context, flow, step, data=None):
    payload = dict(data or {})
    payload["flow"] = flow
    payload["step"] = step
    context.user_data["await_input"] = {
        "kind": KIND,
        "ts": time.time(),
        "data": payload,
    }


def state(context):
    pending = context.user_data.get("await_input") or {}
    if pending.get("kind") != KIND:
        return {}
    return dict(pending.get("data") or {})


def clear(context):
    context.user_data.pop("await_input", None)
    context.user_data.pop("awiz_uids", None)


def _label_user(uid):
    row = _um().database.get_user_row(uid)
    if not row:
        return str(uid)
    name = row.get("first_name") or ""
    uname = f"@{row['username']}" if row.get("username") else ""
    extra = " ".join(p for p in (name, uname) if p)
    return f"{uid} ({extra})" if extra else str(uid)


def _resolve_user_id(raw):
    text = (raw or "").strip().lstrip("@")
    if not text:
        return None
    token = text.split()[0].lstrip("@")
    if token.isdigit():
        return token
    with _um().database._conn() as conn:
        row = conn.execute(
            "SELECT user_id FROM users WHERE lower(username)=? LIMIT 1",
            (token.lower(),),
        ).fetchone()
    return str(row["user_id"]) if row else None


def resolve_user_id(raw):
    return _resolve_user_id(raw)


def _user_pick_keyboard(context):
    rows = []
    picks = {}
    try:
        users, _, _ = _um().database.list_users(0, 6)
    except Exception:
        users = []
    for i, row in enumerate(users, 1):
        uid = str(row["user_id"])
        name = row.get("first_name") or row.get("username") or uid
        uname = f" @{row['username']}" if row.get("username") else ""
        picks[str(i)] = uid
        rows.append([
            InlineKeyboardButton(
                f"{name}{uname} · {uid}"[:64],
                callback_data=f"awiz:uid:{i}",
            )
        ])
    context.user_data["awiz_uids"] = picks
    return _kb(rows)


async def _say(dest, text, markup):
    await dest.reply_text(text, reply_markup=markup)


async def _edit(query, text, markup):
    try:
        await query.message.edit_text(text, reply_markup=markup)
        return
    except Exception:
        pass
    await query.message.reply_text(text, reply_markup=markup)


# --- start ---

async def start_grant(dest, context, user_id=None, tier=None):
    data = {}
    uid = _resolve_user_id(user_id) if user_id else None
    if uid:
        data["user_id"] = uid
        if (tier or "").lower() in ("premium", "unlimited"):
            data["tier"] = tier.lower()
            await _ask_grant_days(dest, context, data)
            return
        await _ask_grant_tier(dest, context, data)
        return
    set_state(context, "grant", "user")
    await _say(dest, msg.t("awiz_pick_user"), _user_pick_keyboard(context))


async def start_topup(dest, context, user_id=None):
    uid = _resolve_user_id(user_id) if user_id else None
    if uid:
        await _ask_topup_amount(dest, context, {"user_id": uid})
        return
    set_state(context, "topup", "user")
    await _say(dest, msg.t("awiz_pick_user"), _user_pick_keyboard(context))


async def start_user(dest, context):
    set_state(context, "user", "user")
    await _say(dest, msg.t("awiz_user_ask"), _user_pick_keyboard(context))


async def start_broadcast(dest, context):
    set_state(context, "broadcast", "text")
    await _say(
        dest,
        msg.t("awiz_broadcast_ask"),
        _kb([_cancel_row()]),
    )


async def start_reports(dest, context):
    set_state(context, "reports", "choose")
    await _say(
        dest,
        msg.t("awiz_reports_ask"),
        _kb([
            [
                InlineKeyboardButton(msg.t("awiz_reports_list"), callback_data="awiz:r:list"),
                InlineKeyboardButton(msg.t("awiz_reports_id"), callback_data="awiz:r:id"),
            ],
        ]),
    )


async def start_channelid(dest, context):
    set_state(context, "channelid", "forward")
    await _say(dest, msg.t("awiz_channelid_ask"), _kb([_cancel_row()]))


async def start_viplog(dest, context):
    set_state(context, "viplog", "confirm")
    status = _DEPS["vip_status_text"]()
    await _say(
        dest,
        msg.t("awiz_viplog_ask", status=status),
        _kb([[InlineKeyboardButton(msg.t("awiz_viplog_send"), callback_data="awiz:ok")]]),
    )


async def start_export(dest, context):
    set_state(context, "export", "confirm")
    await _say(
        dest,
        msg.t("awiz_export_ask"),
        _kb([[InlineKeyboardButton(msg.t("awiz_export_go"), callback_data="awiz:ok")]]),
    )


# --- steps ---

async def _ask_grant_tier(dest, context, data, edit_query=None):
    set_state(context, "grant", "tier", data)
    text = msg.t("awiz_grant_tier", user=_label_user(data["user_id"]))
    markup = _kb([
        [
            InlineKeyboardButton(msg.t("awiz_tier_premium"), callback_data="awiz:g:premium"),
            InlineKeyboardButton(msg.t("awiz_tier_unlimited"), callback_data="awiz:g:unlimited"),
        ],
    ])
    if edit_query:
        await _edit(edit_query, text, markup)
    else:
        await _say(dest, text, markup)


async def _ask_grant_days(dest, context, data, edit_query=None):
    set_state(context, "grant", "days", data)
    text = msg.t(
        "awiz_grant_days",
        user=_label_user(data["user_id"]),
        tier=data["tier"],
    )
    markup = _kb([
        [
            InlineKeyboardButton(msg.t("awiz_days_7"), callback_data="awiz:d:7"),
            InlineKeyboardButton(msg.t("awiz_days_30"), callback_data="awiz:d:30"),
            InlineKeyboardButton(msg.t("awiz_days_90"), callback_data="awiz:d:90"),
        ],
        [InlineKeyboardButton(msg.t("awiz_days_custom"), callback_data="awiz:d:custom")],
    ])
    if edit_query:
        await _edit(edit_query, text, markup)
    else:
        await _say(dest, text, markup)


async def _ask_grant_confirm(dest, context, data, edit_query=None):
    set_state(context, "grant", "confirm", data)
    text = msg.t(
        "awiz_grant_confirm",
        user=_label_user(data["user_id"]),
        tier=data["tier"],
        days=data["days"],
    )
    markup = _kb(_confirm_rows()[:1])
    if edit_query:
        await _edit(edit_query, text, markup)
    else:
        await _say(dest, text, markup)


async def _ask_topup_amount(dest, context, data, edit_query=None):
    set_state(context, "topup", "amount", data)
    default = entitlements.TOPUP_AMOUNT
    text = msg.t("awiz_topup_amount", user=_label_user(data["user_id"]))
    markup = _kb([
        [InlineKeyboardButton(
            msg.t("awiz_amt_default", amount=default),
            callback_data=f"awiz:a:{default}",
        )],
        [
            InlineKeyboardButton("5", callback_data="awiz:a:5"),
            InlineKeyboardButton("10", callback_data="awiz:a:10"),
            InlineKeyboardButton("20", callback_data="awiz:a:20"),
        ],
        [InlineKeyboardButton(msg.t("awiz_amt_custom"), callback_data="awiz:a:custom")],
    ])
    if edit_query:
        await _edit(edit_query, text, markup)
    else:
        await _say(dest, text, markup)


async def _ask_topup_confirm(dest, context, data, edit_query=None):
    set_state(context, "topup", "confirm", data)
    text = msg.t(
        "awiz_topup_confirm",
        user=_label_user(data["user_id"]),
        amount=data["amount"],
    )
    markup = _kb(_confirm_rows()[:1])
    if edit_query:
        await _edit(edit_query, text, markup)
    else:
        await _say(dest, text, markup)


async def _ask_broadcast_confirm(dest, context, data):
    set_state(context, "broadcast", "confirm", data)
    count = len(_um().get_all_user_ids())
    preview = data.get("text") or ""
    if len(preview) > 800:
        preview = preview[:800] + "…"
    await _say(
        dest,
        msg.t("awiz_broadcast_confirm", count=count, preview=preview),
        _kb(_confirm_rows()[:1]),
    )


async def _done(dest, text):
    kb = InlineKeyboardMarkup([_admin_back_row()])
    if hasattr(dest, "edit_text"):
        try:
            await dest.edit_text(text, reply_markup=kb)
            return
        except Exception:
            pass
    await dest.reply_text(text, reply_markup=kb)


async def _apply_grant(dest, context, data, admin_id):
    target = data["user_id"]
    tier = data["tier"]
    days = int(data["days"])
    _um().touch_user(target)
    sub = payments.apply_manual_grant(
        _um().database, target, tier, days, admin_id=admin_id,
    )
    clear(context)
    await _done(dest, msg.grant_ok(target, tier, sub["expires_at"]))


async def _apply_topup(dest, context, data, admin_id):
    target = data["user_id"]
    amount = int(data["amount"])
    _um().touch_user(target)
    granted, day = payments.apply_manual_topup(
        _um().database, target, amount=amount, admin_id=admin_id,
    )
    clear(context)
    await _done(dest, msg.topup_ok(target, granted, day))


async def _apply_broadcast(dest, context, data, bot, admin_user):
    body = (data.get("text") or "").strip()
    clear(context)
    user_ids = _um().get_all_user_ids()
    sent = failed = 0
    for uid in user_ids:
        try:
            await bot.send_message(chat_id=int(uid), text=body)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
    await _DEPS["log_broadcast"](bot, admin_user, sent, failed)
    await _done(dest, msg.t("awiz_broadcast_done", sent=sent, failed=failed))


async def _on_user_chosen(dest, context, data, user_id, edit_query=None):
    data = dict(data)
    data["user_id"] = str(user_id)
    flow = data.get("flow")
    if flow == "grant":
        await _ask_grant_tier(dest, context, data, edit_query=edit_query)
    elif flow == "topup":
        await _ask_topup_amount(dest, context, data, edit_query=edit_query)
    elif flow == "user":
        clear(context)
        target = edit_query.message if edit_query else dest
        await _DEPS["show_user_detail"](target, user_id, edit=bool(edit_query))
    else:
        await _say(dest, msg.t("awiz_invalid_user"), _user_pick_keyboard(context))


# --- text / callback ---

async def on_text(update, context, pending):
    data = dict((pending or {}).get("data") or {})
    flow = data.get("flow")
    step = data.get("step")
    dest = update.effective_message
    text = (getattr(dest, "text", None) or getattr(dest, "caption", None) or "").strip()

    if flow == "channelid" and step == "forward":
        return await _finish_channelid(update, context)

    if flow in ("grant", "topup", "user") and step == "user":
        uid = _resolve_user_id(text)
        if not uid:
            await _say(dest, msg.t("awiz_invalid_user"), _user_pick_keyboard(context))
            return True
        await _on_user_chosen(dest, context, data, uid)
        return True

    if flow == "grant" and step == "days_custom":
        try:
            days = int(text)
        except ValueError:
            days = 0
        if days < 1:
            await _say(
                dest,
                msg.t("awiz_grant_days_custom"),
                _kb([_cancel_row()]),
            )
            return True
        data["days"] = days
        await _ask_grant_confirm(dest, context, data)
        return True

    if flow == "topup" and step == "amount_custom":
        try:
            amount = int(text)
        except ValueError:
            amount = 0
        if amount < 1:
            await _say(
                dest,
                msg.t("awiz_topup_amount_custom"),
                _kb([_cancel_row()]),
            )
            return True
        data["amount"] = amount
        await _ask_topup_confirm(dest, context, data)
        return True

    if flow == "broadcast" and step == "text":
        if not text:
            await _say(dest, msg.t("awiz_broadcast_empty"), _kb([_cancel_row()]))
            return True
        data["text"] = text
        await _ask_broadcast_confirm(dest, context, data)
        return True

    if flow == "reports" and step in ("choose", "id"):
        raw = text.lstrip("#")
        try:
            rid = int(raw)
        except ValueError:
            await _say(
                dest,
                msg.t("awiz_reports_bad_id"),
                _kb([
                    [InlineKeyboardButton(msg.t("awiz_reports_list"), callback_data="awiz:r:list")],
                ]),
            )
            set_state(context, "reports", "id", data)
            return True
        clear(context)
        await _DEPS["show_error_report_detail"](dest, rid)
        return True

    return False


async def on_callback(update, context):
    query = update.callback_query
    data_s = (query.data or "")
    parts = data_s.split(":")
    dest = query.message
    st = state(context)
    flow = st.get("flow")

    if data_s == "awiz:cancel" or (len(parts) > 1 and parts[1] == "cancel"):
        clear(context)
        await _edit(
            query,
            msg.t("awiz_cancelled"),
            InlineKeyboardMarkup([_admin_back_row()]),
        )
        return

    if len(parts) >= 3 and parts[1] == "uid":
        uid = (context.user_data.get("awiz_uids") or {}).get(parts[2])
        if not uid:
            await _edit(query, msg.t("awiz_invalid_user"), _user_pick_keyboard(context))
            return
        await _on_user_chosen(dest, context, st, uid, edit_query=query)
        return

    if flow == "grant":
        if parts[1] == "g" and parts[2] in ("premium", "unlimited"):
            st["tier"] = parts[2]
            await _ask_grant_days(dest, context, st, edit_query=query)
            return
        if parts[1] == "d":
            if parts[2] == "custom":
                set_state(context, "grant", "days_custom", st)
                await _edit(query, msg.t("awiz_grant_days_custom"), _kb([_cancel_row()]))
                return
            st["days"] = int(parts[2])
            await _ask_grant_confirm(dest, context, st, edit_query=query)
            return
        if parts[1] == "ok" and st.get("step") == "confirm":
            await _apply_grant(dest, context, st, update.effective_user.id)
            return

    if flow == "topup":
        if parts[1] == "a":
            if parts[2] == "custom":
                set_state(context, "topup", "amount_custom", st)
                await _edit(query, msg.t("awiz_topup_amount_custom"), _kb([_cancel_row()]))
                return
            st["amount"] = int(parts[2])
            await _ask_topup_confirm(dest, context, st, edit_query=query)
            return
        if parts[1] == "ok" and st.get("step") == "confirm":
            await _apply_topup(dest, context, st, update.effective_user.id)
            return

    if flow == "broadcast" and parts[1] == "ok" and st.get("step") == "confirm":
        await _apply_broadcast(
            dest, context, st, context.bot, update.effective_user,
        )
        return

    if flow == "viplog" and parts[1] == "ok":
        clear(context)
        status = _DEPS["vip_status_text"]()
        ok, detail = await _DEPS["send_test_message"](context.bot)
        mark = "✅" if ok else "❌"
        await _edit(
            query,
            f"{mark} {detail}\n\n{status}",
            InlineKeyboardMarkup([_admin_back_row()]),
        )
        return

    if flow == "export" and parts[1] == "ok":
        clear(context)
        await _DEPS["run_export"](context.bot, query.message.chat_id)
        return

    if flow == "reports" or parts[1] == "r":
        if len(parts) >= 3 and parts[2] == "list":
            clear(context)
            await _DEPS["show_global_section"](dest, "bugs", 0, edit=True)
            return
        if len(parts) >= 3 and parts[2] == "id":
            set_state(context, "reports", "id", st)
            await _edit(query, msg.t("awiz_reports_ask_id"), _kb([_cancel_row()]))
            return


async def _finish_channelid(update, context):
    from telegram import MessageOriginChannel, MessageOriginChat

    message = update.effective_message
    chat = None
    origin = getattr(message, "forward_origin", None)
    if isinstance(origin, MessageOriginChannel):
        chat = origin.chat
    elif isinstance(origin, MessageOriginChat):
        chat = origin.sender_chat
    elif getattr(message, "forward_from_chat", None):
        chat = message.forward_from_chat
    elif getattr(message, "sender_chat", None) and message.chat and message.chat.type != "private":
        chat = message.sender_chat
    if not chat:
        await _say(
            message,
            msg.t("awiz_channelid_need_forward"),
            _kb([_cancel_row()]),
        )
        return True
    lines = [
        f"شناسه چت: `{chat.id}`",
        f"نوع: {chat.type}",
    ]
    if chat.title:
        lines.append(f"عنوان: {chat.title}")
    if chat.username:
        lines.append(f"یوزرنیم: @{chat.username}")
    lines.append("\nVIP_LOG_CHANNEL_ID=" + str(chat.id))
    clear(context)
    await message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([_admin_back_row()]),
    )
    return True
