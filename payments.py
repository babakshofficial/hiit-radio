"""Telegram Stars invoices + manual grant helpers."""

import json
import logging
import os

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, Update
from telegram.ext import ContextTypes, PreCheckoutQueryHandler, MessageHandler, filters

import entitlements
import messages as msg

logger = logging.getLogger(__name__)

STARS_DAYPASS = int(os.getenv("STARS_DAYPASS", "15"))
STARS_WEEKLY = int(os.getenv("STARS_WEEKLY", "75"))
STARS_MONTHLY = int(os.getenv("STARS_MONTHLY", "200"))

KIND_DAYPASS = "daypass"
KIND_WEEKLY = "premium_weekly"
KIND_MONTHLY = "premium_monthly"

_PRODUCTS = {
    KIND_DAYPASS: {
        "title": "HiiT Radio Day Pass",
        "description": f"+{entitlements.TOPUP_AMOUNT} downloads for today",
        "stars": STARS_DAYPASS,
        "payload": {"kind": KIND_DAYPASS},
    },
    KIND_WEEKLY: {
        "title": "HiiT Radio Premium — 7 days",
        "description": f"{entitlements.PREMIUM_DAILY_LIMIT} downloads/day for 7 days",
        "stars": STARS_WEEKLY,
        "payload": {"kind": KIND_WEEKLY, "tier": "premium", "days": 7},
    },
    KIND_MONTHLY: {
        "title": "HiiT Radio Premium — 30 days",
        "description": f"{entitlements.PREMIUM_DAILY_LIMIT} downloads/day for 30 days",
        "stars": STARS_MONTHLY,
        "payload": {"kind": KIND_MONTHLY, "tier": "premium", "days": 30},
    },
}


def product_catalog():
    return {
        kind: {
            "title": meta["title"],
            "description": meta["description"],
            "stars": meta["stars"],
        }
        for kind, meta in _PRODUCTS.items()
    }


def premium_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            msg.btn_buy_daypass(STARS_DAYPASS, entitlements.TOPUP_AMOUNT),
            callback_data=f"pay:{KIND_DAYPASS}",
        )],
        [InlineKeyboardButton(
            msg.btn_buy_weekly(STARS_WEEKLY),
            callback_data=f"pay:{KIND_WEEKLY}",
        )],
        [InlineKeyboardButton(
            msg.btn_buy_monthly(STARS_MONTHLY),
            callback_data=f"pay:{KIND_MONTHLY}",
        )],
        [InlineKeyboardButton(msg.BTN_INVITE, callback_data="pay:invite")],
    ])


def quota_upsell_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            msg.btn_buy_daypass(STARS_DAYPASS, entitlements.TOPUP_AMOUNT),
            callback_data=f"pay:{KIND_DAYPASS}",
        )],
        [InlineKeyboardButton(
            msg.btn_buy_weekly(STARS_WEEKLY),
            callback_data=f"pay:{KIND_WEEKLY}",
        )],
        [InlineKeyboardButton(msg.BTN_INVITE, callback_data="pay:invite")],
    ])


async def send_stars_invoice(bot, chat_id, user_id, kind):
    meta = _PRODUCTS.get(kind)
    if not meta:
        raise ValueError(f"unknown product: {kind}")
    payload = json.dumps({"uid": str(user_id), **meta["payload"]}, separators=(",", ":"))
    await bot.send_invoice(
        chat_id=chat_id,
        title=meta["title"],
        description=meta["description"],
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=meta["title"], amount=meta["stars"])],
    )


async def precheckout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    try:
        data = json.loads(query.invoice_payload or "{}")
        kind = data.get("kind")
        if kind not in _PRODUCTS:
            await query.answer(ok=False, error_message="Unknown product")
            return
        if str(data.get("uid") or "") != str(query.from_user.id):
            await query.answer(ok=False, error_message="Invoice user mismatch")
            return
        await query.answer(ok=True)
    except Exception as e:
        logger.error("precheckout failed: %s", e, exc_info=True)
        await query.answer(ok=False, error_message="Payment error")


def _apply_purchase(db, user_id, kind, source="stars"):
    if kind == KIND_DAYPASS:
        amount, day = entitlements.grant_bonus(
            db, user_id, amount=entitlements.TOPUP_AMOUNT, source=source,
        )
        return {"type": "bonus", "amount": amount, "day": day}
    meta = _PRODUCTS[kind]["payload"]
    sub = entitlements.grant_subscription(
        db, user_id, meta["tier"], meta["days"], source=source,
    )
    return {"type": "subscription", "tier": sub["tier"], "expires_at": sub["expires_at"]}


async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from user_manager import UserManager

    payment = update.message.successful_payment
    user = update.effective_user
    db = UserManager().database
    try:
        data = json.loads(payment.invoice_payload or "{}")
    except json.JSONDecodeError:
        data = {}
    kind = data.get("kind")
    if kind not in _PRODUCTS:
        logger.error("Unknown payment kind in payload: %s", payment.invoice_payload)
        await update.message.reply_text(msg.payment_failed())
        return

    charge_id = payment.telegram_payment_charge_id
    row, created = db.record_payment(
        user.id,
        provider="stars",
        kind=kind,
        amount=payment.total_amount,
        currency=payment.currency,
        telegram_charge_id=charge_id,
        status="paid",
    )
    if not created:
        await update.message.reply_text(msg.payment_already_processed())
        return

    result = _apply_purchase(db, user.id, kind, source="stars")
    logger.info(
        "Stars payment applied user=%s kind=%s charge=%s result=%s",
        user.id, kind, charge_id, result,
    )
    if result["type"] == "bonus":
        await update.message.reply_text(
            msg.payment_bonus_ok(result["amount"], result["day"])
        )
    else:
        await update.message.reply_text(
            msg.payment_premium_ok(result["tier"], result["expires_at"])
        )


def apply_manual_grant(db, user_id, tier, days, admin_id=None):
    source = f"manual:{admin_id}" if admin_id else "manual"
    db.record_payment(
        user_id,
        provider="manual",
        kind=f"grant_{tier}_{days}d",
        amount=0,
        currency="manual",
        telegram_charge_id=None,
        status="paid",
    )
    return entitlements.grant_subscription(db, user_id, tier, days, source=source)


def apply_manual_topup(db, user_id, amount=None, admin_id=None):
    source = f"manual:{admin_id}" if admin_id else "manual"
    amount = entitlements.TOPUP_AMOUNT if amount is None else int(amount)
    db.record_payment(
        user_id,
        provider="manual",
        kind="daypass",
        amount=0,
        currency="manual",
        telegram_charge_id=None,
        status="paid",
    )
    return entitlements.grant_bonus(db, user_id, amount=amount, source=source)


def register_handlers(application):
    application.add_handler(PreCheckoutQueryHandler(precheckout_handler))
    application.add_handler(
        MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_handler)
    )