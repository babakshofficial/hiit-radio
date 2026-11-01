"""Telegram Stars invoices, delivery, refunds and gifts, plus manual grant helpers."""

import json
import logging
import os
import secrets
import time
from urllib.parse import quote

from telegram import (
    InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice, TransactionPartnerUser, Update,
)
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes, PreCheckoutQueryHandler, MessageHandler, filters

import entitlements
import messages as msg

logger = logging.getLogger(__name__)

_db = None


def init(user_manager=None, database=None):
    """Use the bot's shared database (avoids a second UserManager/connection)."""
    global _db
    if database is not None:
        _db = database
    elif user_manager is not None:
        _db = user_manager.database


def _database():
    if _db is not None:
        return _db
    from user_manager import UserManager
    return UserManager().database

STARS_DAYPASS = int(os.getenv("STARS_DAYPASS", "15"))
STARS_WEEKLY = int(os.getenv("STARS_WEEKLY", "75"))
STARS_MONTHLY = int(os.getenv("STARS_MONTHLY", "200"))

KIND_DAYPASS = "daypass"
KIND_WEEKLY = "premium_weekly"
KIND_MONTHLY = "premium_monthly"

_PRODUCTS = {
    KIND_DAYPASS: {
        "title": "HiiT Radio Day Pass",
        "description": (
            f"+{entitlements.TOPUP_AMOUNT} downloads for today. "
            "Unused downloads expire at midnight Tehran time."
        ),
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


KIND_GIFT_WEEKLY = "gift_weekly"
KIND_GIFT_MONTHLY = "gift_monthly"

# Not in product_catalog(): gifts are sold in the bot only.
_GIFT_PRODUCTS = {
    KIND_GIFT_WEEKLY: {
        "title": "HiiT Radio Premium gift — 7 days",
        "description": f"A link that gives a friend {entitlements.PREMIUM_DAILY_LIMIT} downloads/day for 7 days",
        "stars": STARS_WEEKLY,
        "payload": {"kind": KIND_GIFT_WEEKLY},
        "tier": "premium",
        "days": 7,
    },
    KIND_GIFT_MONTHLY: {
        "title": "HiiT Radio Premium gift — 30 days",
        "description": f"A link that gives a friend {entitlements.PREMIUM_DAILY_LIMIT} downloads/day for 30 days",
        "stars": STARS_MONTHLY,
        "payload": {"kind": KIND_GIFT_MONTHLY},
        "tier": "premium",
        "days": 30,
    },
}
_ALL_PRODUCTS = {**_PRODUCTS, **_GIFT_PRODUCTS}

# How far back reconciliation looks. Older charges predate this code.
_RECONCILE_WINDOW_SEC = 3 * 86400
_RECONCILE_PAGE = 100
_RECONCILE_MAX_PAGES = 50


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
        [InlineKeyboardButton(msg.t("btn_gift_menu"), callback_data="pay:gift")],
        [InlineKeyboardButton(msg.BTN_INVITE, callback_data="pay:invite")],
    ])


def gift_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            msg.t("btn_gift_weekly", stars=STARS_WEEKLY),
            callback_data=f"pay:{KIND_GIFT_WEEKLY}",
        )],
        [InlineKeyboardButton(
            msg.t("btn_gift_monthly", stars=STARS_MONTHLY),
            callback_data=f"pay:{KIND_GIFT_MONTHLY}",
        )],
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
    meta = _ALL_PRODUCTS.get(kind)
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
        if kind not in _ALL_PRODUCTS:
            await query.answer(ok=False, error_message="Unknown product")
            return
        if str(data.get("uid") or "") != str(query.from_user.id):
            await query.answer(ok=False, error_message="Invoice user mismatch")
            return
        await query.answer(ok=True)
    except Exception as e:
        logger.error("precheckout failed: %s", e, exc_info=True)
        await query.answer(ok=False, error_message="Payment error")


def _grant_for(kind):
    if kind == KIND_DAYPASS:
        return {
            "type": "bonus",
            "amount": entitlements.TOPUP_AMOUNT,
            "day": entitlements.today_key(),
        }
    if kind in _GIFT_PRODUCTS:
        meta = _GIFT_PRODUCTS[kind]
        return {
            "type": "gift",
            "tier": meta["tier"],
            "days": meta["days"],
            "code": secrets.token_urlsafe(9),
        }
    meta = _PRODUCTS[kind]["payload"]
    return {"type": "subscription", "tier": meta["tier"], "days": meta["days"]}


def apply_purchase(db, user_id, kind, amount, currency, charge_id):
    """Record the charge and deliver it atomically. See ``apply_star_purchase``."""
    return db.apply_star_purchase(
        user_id, kind, amount, currency, charge_id, _grant_for(kind),
    )


def gift_link(bot, code):
    return f"https://t.me/{bot.username}?start=gift_{code}"


def _purchase_message(bot, result):
    """Return ``(text, reply_markup)`` telling the buyer what they received."""
    if result["type"] == "bonus":
        return msg.payment_bonus_ok(result["amount"], result["day"]), None
    if result["type"] == "gift":
        link = gift_link(bot, result["code"])
        share = (
            f"https://t.me/share/url?url={quote(link, safe='')}"
            f"&text={quote(msg.t('gift_share_text'), safe='')}"
        )
        return (
            msg.t("gift_bought", days=result["days"], link=link),
            InlineKeyboardMarkup([[InlineKeyboardButton(msg.t("btn_gift_share"), url=share)]]),
        )
    return msg.payment_premium_ok(result["tier"], result["expires_at"]), None


async def successful_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    user = update.effective_user
    db = _database()
    try:
        data = json.loads(payment.invoice_payload or "{}")
    except json.JSONDecodeError:
        data = {}
    kind = data.get("kind")
    if kind not in _ALL_PRODUCTS:
        logger.error("Unknown payment kind in payload: %s", payment.invoice_payload)
        await update.message.reply_text(msg.payment_failed())
        return

    charge_id = payment.telegram_payment_charge_id
    try:
        _row, created, result = apply_purchase(
            db, user.id, kind, payment.total_amount, payment.currency, charge_id,
        )
    except Exception:
        # Nothing was saved. Telegram holds the charge, so reconciliation delivers it.
        logger.exception("Stars payment not applied yet user=%s charge=%s", user.id, charge_id)
        await update.message.reply_text(msg.t("payment_delayed"))
        return
    if not created:
        await update.message.reply_text(msg.payment_already_processed())
        return

    logger.info("Stars payment applied user=%s kind=%s charge=%s", user.id, kind, charge_id)
    text, keyboard = _purchase_message(context.bot, result)
    await update.message.reply_text(text, reply_markup=keyboard)


async def _notify(bot, db, user_id, build):
    """Message a user in their language; a failure here must not undo anything."""
    token = msg.use_lang(db.get_language(user_id))
    try:
        text, keyboard = build()
        await bot.send_message(chat_id=int(user_id), text=text, reply_markup=keyboard)
    except Exception as exc:
        logger.warning("Could not notify user %s: %s", user_id, exc)
    finally:
        msg.reset_lang(token)


async def _notify_refund(bot, db, payment, recipient):
    await _notify(
        bot, db, payment["user_id"],
        lambda: (msg.t("payment_refunded_user", kind=payment["kind"]), None),
    )
    if recipient and str(recipient) != str(payment["user_id"]):
        await _notify(bot, db, recipient, lambda: (msg.t("gift_revoked_recipient"), None))


async def refund_payment(bot, db, payment_id):
    """Refund through Telegram, then take the purchase back. Returns ``(ok, detail)``.

    Telegram goes first: its refund can't be undone, and if we crash right after it
    the refund update and reconciliation still revoke the purchase.
    """
    payment = db.get_payment(payment_id)
    if not payment:
        return False, "Payment not found."
    if payment["provider"] != "stars" or not payment["telegram_charge_id"]:
        return False, "Only Telegram Stars payments can be refunded."
    if payment["status"] == "refunded":
        return False, "Already refunded."
    charge_id = payment["telegram_charge_id"]
    try:
        await bot.refund_star_payment(
            user_id=int(payment["user_id"]), telegram_payment_charge_id=charge_id,
        )
    except BadRequest as exc:
        if "ALREADY_REFUNDED" not in str(exc).upper():
            logger.warning("Refund refused for payment %s: %s", payment_id, exc)
            return False, f"Telegram refused the refund: {exc}"
    except TelegramError as exc:
        # The outcome is unknown. If it did go through, reconciliation revokes it.
        logger.warning("Refund uncertain for payment %s: %s", payment_id, exc)
        return False, (
            f"Couldn't confirm the refund ({exc}). Check /payments in an hour before retrying."
        )
    updated, changed, recipient = db.revoke_star_purchase(charge_id)
    if changed:
        await _notify_refund(bot, db, updated, recipient)
    db.log_event("payment_refunded", user_id=payment["user_id"], payload={
        "payment_id": payment["id"], "kind": payment["kind"], "amount": payment["amount"],
    })
    return True, f"Refunded {payment['amount']} Stars and revoked {payment['kind']}."


async def refunded_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """A refund Telegram reports, including ones made outside the bot."""
    refund = update.message.refunded_payment
    db = _database()
    updated, changed, recipient = db.revoke_star_purchase(refund.telegram_payment_charge_id)
    if changed:
        logger.info("Refund applied for payment %s", updated["id"])
        await _notify_refund(context.bot, db, updated, recipient)
    elif updated is None:
        logger.warning("Refund for unknown charge %s", refund.telegram_payment_charge_id)


async def redeem_gift(bot, db, code, user_id):
    """Redeem a gift link. Returns the message to show the user."""
    status, gift, sub = db.redeem_gift_code(code, user_id)
    if status == "invalid":
        return msg.t("gift_invalid")
    if status == "used":
        return msg.t("gift_already_used")
    db.log_event("gift_redeemed", user_id=user_id, payload={"gift_id": gift["id"]})
    if str(gift["buyer_id"]) != str(user_id):
        await _notify(
            bot, db, gift["buyer_id"], lambda: (msg.t("gift_redeemed_buyer"), None),
        )
    return msg.payment_premium_ok(sub["tier"], sub["expires_at"])


async def reconcile_star_transactions(bot, db, now=None):
    """Compare recent Telegram transactions with our records and fix any gap.

    Covers a payment or refund update lost to a crash or outage. A refund shares its
    id with the charge it refunds, so transactions must be applied oldest first.
    Returns ``(payments_applied, refunds_applied)``.
    """
    now = time.time() if now is None else now
    cutoff = now - _RECONCILE_WINDOW_SEC
    applied = refunded = 0
    transactions = []
    for page in range(_RECONCILE_MAX_PAGES):
        batch = await bot.get_star_transactions(
            offset=page * _RECONCILE_PAGE, limit=_RECONCILE_PAGE,
        )
        transactions.extend(batch.transactions)
        if len(batch.transactions) < _RECONCILE_PAGE:
            break

    for tx in sorted(transactions, key=lambda t: t.date):
        if tx.date.timestamp() < cutoff:
            continue
        if isinstance(tx.source, TransactionPartnerUser):
            user_id = tx.source.user.id
            try:
                data = json.loads(tx.source.invoice_payload or "{}")
            except json.JSONDecodeError:
                continue
            kind = data.get("kind")
            if kind not in _ALL_PRODUCTS or str(data.get("uid") or "") != str(user_id):
                continue
            _row, created, result = apply_purchase(db, user_id, kind, tx.amount, "XTR", tx.id)
            if created:
                applied += 1
                logger.warning("Reconciled missed Stars payment user=%s kind=%s", user_id, kind)
                await _notify(bot, db, user_id, lambda r=result: _purchase_message(bot, r))
        elif isinstance(tx.receiver, TransactionPartnerUser):
            updated, changed, recipient = db.revoke_star_purchase(tx.id)
            if changed:
                refunded += 1
                logger.warning("Reconciled missed refund for payment %s", updated["id"])
                await _notify_refund(bot, db, updated, recipient)
    return applied, refunded


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
    application.add_handler(
        MessageHandler(filters.StatusUpdate.REFUNDED_PAYMENT, refunded_payment_handler)
    )
