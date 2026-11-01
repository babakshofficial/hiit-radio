#!/usr/bin/env python3
"""Payment safety checks: crash recovery, refunds and gifts. No network, no real money.

Usage: python scripts/check_payments.py
"""

import asyncio
import datetime as dt
import json
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
WORK = tempfile.mkdtemp(prefix="hiit_payment_check_")
os.environ.update(
    BOT_TOKEN="123:check",
    ADMIN_ID="1",
    DATABASE_PATH=str(Path(WORK) / "check.db"),
    REQUIRED_CHANNEL="",
)
os.chdir(WORK)

from telegram import TransactionPartnerUser, User  # noqa: E402
from telegram.error import BadRequest, TimedOut  # noqa: E402

import entitlements  # noqa: E402
import payments  # noqa: E402
from database import Database  # noqa: E402

BUYER, FRIEND = "1001", "1002"


class FakeBot:
    username = "HiitCheckBot"

    def __init__(self, transactions=()):
        self.transactions = list(transactions)
        self.sent = []
        self.refunds = []
        self.refund_error = None

    async def send_message(self, chat_id, text, reply_markup=None):
        self.sent.append((str(chat_id), text))

    async def refund_star_payment(self, user_id, telegram_payment_charge_id):
        if self.refund_error:
            raise self.refund_error
        self.refunds.append((user_id, telegram_payment_charge_id))
        return True

    async def get_star_transactions(self, offset=0, limit=100):
        return SimpleNamespace(transactions=self.transactions[offset:offset + limit])


class FakeMessage:
    def __init__(self, payment=None, refund=None):
        self.successful_payment = payment
        self.refunded_payment = refund
        self.replies = []

    async def reply_text(self, text, reply_markup=None):
        self.replies.append(text)


def fresh_db():
    path = Path(WORK) / f"db_{time.time_ns()}.db"
    db = Database(str(path))
    payments.init(database=db)
    for uid in (BUYER, FRIEND):
        db.touch_user(uid)
    return db


def payload(kind, uid=BUYER):
    return json.dumps({"uid": str(uid), "kind": kind})


def buy(db, charge, kind=payments.KIND_MONTHLY, uid=BUYER):
    return payments.apply_purchase(db, uid, kind, 200, "XTR", charge)


def pay_via_handler(db, bot, charge, kind):
    message = FakeMessage(payment=SimpleNamespace(
        invoice_payload=payload(kind),
        telegram_payment_charge_id=charge,
        total_amount=200,
        currency="XTR",
    ))
    update = SimpleNamespace(message=message, effective_user=SimpleNamespace(id=int(BUYER)))
    asyncio.run(payments.successful_payment_handler(update, SimpleNamespace(bot=bot)))
    return message


def tier(db, uid=BUYER):
    return entitlements.resolve_tier(db, uid)[0]


def count(db, table):
    with db._conn() as conn:
        return conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]


def star_tx(charge, kind, uid=BUYER, refund=False, age=0):
    partner = TransactionPartnerUser(
        transaction_type="invoice_payment",
        user=User(id=int(uid), first_name="x", is_bot=False),
        invoice_payload=None if refund else payload(kind, uid),
    )
    return SimpleNamespace(
        id=charge,
        amount=200,
        date=dt.datetime.fromtimestamp(time.time() - age, dt.timezone.utc),
        source=None if refund else partner,
        receiver=partner if refund else None,
    )


def check_crash_during_delivery_leaves_nothing():
    """The old bug: a charge recorded with nothing delivered, and retries refused."""
    db = fresh_db()
    with db._conn() as conn:
        conn.execute(
            """CREATE TRIGGER crash BEFORE INSERT ON payments
               BEGIN SELECT RAISE(ABORT, 'simulated crash'); END"""
        )
    bot = FakeBot()
    message = pay_via_handler(db, bot, "c1", payments.KIND_MONTHLY)
    assert "/paysupport" in message.replies[0], message.replies
    assert count(db, "subscriptions") == 0, "delivery must roll back with the payment"
    assert count(db, "payments") == 0
    assert tier(db) == "free"

    with db._conn() as conn:
        conn.execute("DROP TRIGGER crash")
    bot.transactions = [star_tx("c1", payments.KIND_MONTHLY)]
    assert asyncio.run(payments.reconcile_star_transactions(bot, db)) == (1, 0)
    assert tier(db) == "premium", "reconciliation must deliver the lost purchase"
    assert bot.sent and bot.sent[0][0] == BUYER, "buyer must be told"


def check_crash_before_delivery_rolls_back_payment():
    db = fresh_db()
    with db._conn() as conn:
        conn.execute(
            """CREATE TRIGGER crash BEFORE INSERT ON subscriptions
               BEGIN SELECT RAISE(ABORT, 'simulated crash'); END"""
        )
    try:
        buy(db, "c1")
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("expected the simulated crash")
    assert count(db, "payments") == 0, "no payment row may survive a failed delivery"


def check_lost_update_is_recovered():
    db = fresh_db()
    bot = FakeBot([star_tx("lost", payments.KIND_DAYPASS)])
    assert asyncio.run(payments.reconcile_star_transactions(bot, db)) == (1, 0)
    assert entitlements.check_quota(db, BUYER)[2] == (
        entitlements.FREE_DAILY_LIMIT + entitlements.TOPUP_AMOUNT
    )


def check_each_charge_delivers_once():
    db = fresh_db()
    bot = FakeBot()
    pay_via_handler(db, bot, "c1", payments.KIND_MONTHLY)
    assert count(db, "subscriptions") == 1
    again = pay_via_handler(db, bot, "c1", payments.KIND_MONTHLY)
    assert count(db, "subscriptions") == 1
    assert again.replies
    bot.transactions = [star_tx("c1", payments.KIND_MONTHLY)]
    assert asyncio.run(payments.reconcile_star_transactions(bot, db)) == (0, 0)
    assert count(db, "subscriptions") == 1


def check_reconcile_ignores_old_and_foreign():
    db = fresh_db()
    bot = FakeBot([
        star_tx("old", payments.KIND_MONTHLY, age=10 * 86400),
        star_tx("other", "not_a_product"),
    ])
    mismatch = star_tx("spoof", payments.KIND_MONTHLY)
    mismatch.source = TransactionPartnerUser(
        transaction_type="invoice_payment",
        user=User(id=int(FRIEND), first_name="x", is_bot=False),
        invoice_payload=payload(payments.KIND_MONTHLY, BUYER),
    )
    bot.transactions.append(mismatch)
    assert asyncio.run(payments.reconcile_star_transactions(bot, db)) == (0, 0)
    assert count(db, "payments") == 0


def check_refund_removes_subscription():
    db = fresh_db()
    row, _, _ = buy(db, "c1")
    assert tier(db) == "premium"
    bot = FakeBot()
    ok, _detail = asyncio.run(payments.refund_payment(bot, db, row["id"]))
    assert ok and bot.refunds == [(int(BUYER), "c1")]
    assert tier(db) == "free"
    assert db.get_payment(row["id"])["status"] == "refunded"
    assert bot.sent, "buyer must be told"

    ok, detail = asyncio.run(payments.refund_payment(bot, db, row["id"]))
    assert not ok and "Already" in detail
    assert len(bot.refunds) == 1, "must not refund twice"


def check_refund_of_stacked_purchase_keeps_the_other():
    db = fresh_db()
    first, _, one = buy(db, "c1", payments.KIND_MONTHLY)
    _second, _, two = buy(db, "c2", payments.KIND_WEEKLY)
    assert two["expires_at"] - one["expires_at"] == 7 * 86400
    db.revoke_star_purchase("c1")
    remaining = db.get_active_subscription(BUYER)
    assert remaining, "the second purchase must survive"
    days_left = (remaining["expires_at"] - time.time()) / 86400
    assert 6.9 < days_left < 7.1, days_left


def check_refund_removes_day_pass():
    db = fresh_db()
    row, _, _ = buy(db, "c1", payments.KIND_DAYPASS)
    assert count(db, "quota_bonuses") == 1
    asyncio.run(payments.refund_payment(FakeBot(), db, row["id"]))
    assert count(db, "quota_bonuses") == 0


def check_failed_refund_changes_nothing():
    db = fresh_db()
    row, _, _ = buy(db, "c1")
    bot = FakeBot()
    bot.refund_error = BadRequest("CHARGE_NOT_FOUND")
    ok, _detail = asyncio.run(payments.refund_payment(bot, db, row["id"]))
    assert not ok
    assert tier(db) == "premium", "Telegram refused, so the user keeps the purchase"
    assert db.get_payment(row["id"])["status"] == "paid"

    bot.refund_error = BadRequest("CHARGE_ALREADY_REFUNDED")
    ok, _detail = asyncio.run(payments.refund_payment(bot, db, row["id"]))
    assert ok and tier(db) == "free"


def check_payment_and_refund_both_missed():
    """Whatever order Telegram lists them in, the purchase must end up revoked."""
    db = fresh_db()
    refund = star_tx("c1", payments.KIND_MONTHLY, refund=True, age=10)
    charge = star_tx("c1", payments.KIND_MONTHLY, age=100)
    bot = FakeBot([refund, charge])
    assert asyncio.run(payments.reconcile_star_transactions(bot, db)) == (1, 1)
    assert tier(db) == "free"


def check_uncertain_refund_changes_nothing():
    db = fresh_db()
    row, _, _ = buy(db, "c1")
    bot = FakeBot()
    bot.refund_error = TimedOut("timed out")
    ok, detail = asyncio.run(payments.refund_payment(bot, db, row["id"]))
    assert not ok and "/payments" in detail
    assert db.get_payment(row["id"])["status"] == "paid"


def check_outside_refund_is_applied():
    db = fresh_db()
    buy(db, "viaupdate")
    buy(db, "viasync", payments.KIND_WEEKLY, uid=FRIEND)
    bot = FakeBot()
    message = FakeMessage(refund=SimpleNamespace(telegram_payment_charge_id="viaupdate"))
    update = SimpleNamespace(message=message)
    context = SimpleNamespace(bot=bot)
    asyncio.run(payments.refunded_payment_handler(update, context))
    asyncio.run(payments.refunded_payment_handler(update, context))
    assert tier(db) == "free"
    assert len(bot.sent) == 1, "buyer is told once"

    bot.transactions = [star_tx("viasync", payments.KIND_WEEKLY, uid=FRIEND, refund=True)]
    assert asyncio.run(payments.reconcile_star_transactions(bot, db)) == (0, 1)
    assert tier(db, FRIEND) == "free"


def check_only_stars_payments_refund():
    db = fresh_db()
    payments.apply_manual_grant(db, BUYER, "premium", 7, admin_id="1")
    manual = db.list_star_payments(BUYER)
    assert manual == []
    with db._conn() as conn:
        pid = conn.execute("SELECT id FROM payments").fetchone()["id"]
    bot = FakeBot()
    ok, _detail = asyncio.run(payments.refund_payment(bot, db, pid))
    assert not ok and bot.refunds == []


def check_gift_flow():
    db = fresh_db()
    bot = FakeBot()
    message = pay_via_handler(db, bot, "g1", payments.KIND_GIFT_WEEKLY)
    assert f"t.me/{bot.username}?start=gift_" in message.replies[0]
    assert tier(db) == "free", "buying a gift must not upgrade the buyer"
    with db._conn() as conn:
        code = conn.execute("SELECT code FROM gift_codes").fetchone()["code"]
    assert len(f"gift_{code}") <= 64 and all(c.isalnum() or c in "-_" for c in code)
    invoice = json.dumps({"uid": "1234567890", **payments._GIFT_PRODUCTS[
        payments.KIND_GIFT_MONTHLY]["payload"]}, separators=(",", ":"))
    assert len(invoice) <= 128, "Telegram limits invoice payloads to 128 bytes"

    bot.sent.clear()
    text = asyncio.run(payments.redeem_gift(bot, db, code, FRIEND))
    assert "✅" in text
    assert tier(db, FRIEND) == "premium"
    assert bot.sent and bot.sent[0][0] == BUYER, "buyer is told it was redeemed"

    days = (db.get_active_subscription(FRIEND)["expires_at"] - time.time()) / 86400
    assert 6.9 < days < 7.1
    third = "1003"
    db.touch_user(third)
    used = asyncio.run(payments.redeem_gift(bot, db, code, third))
    assert tier(db, third) == "free" and used and "✅" not in used
    assert count(db, "subscriptions") == 1

    invalid = asyncio.run(payments.redeem_gift(bot, db, "nope", third))
    assert tier(db, third) == "free" and invalid


def check_gift_refund():
    db = fresh_db()
    bot = FakeBot()

    unredeemed, _, result = buy(db, "g1", payments.KIND_GIFT_WEEKLY)
    asyncio.run(payments.refund_payment(bot, db, unredeemed["id"]))
    asyncio.run(payments.redeem_gift(bot, db, result["code"], FRIEND))
    assert tier(db, FRIEND) == "free", "a refunded gift link must stop working"

    redeemed, _, result = buy(db, "g2", payments.KIND_GIFT_WEEKLY)
    asyncio.run(payments.redeem_gift(bot, db, result["code"], FRIEND))
    assert tier(db, FRIEND) == "premium"
    bot.sent.clear()
    bot.refunds.clear()
    asyncio.run(payments.refund_payment(bot, db, redeemed["id"]))
    assert bot.refunds == [(int(BUYER), "g2")], "the payer gets the money back"
    assert tier(db, FRIEND) == "free", "the recipient loses the refunded gift"
    assert {uid for uid, _ in bot.sent} == {BUYER, FRIEND}


def check_gifts_not_in_web_catalog():
    assert not set(payments._GIFT_PRODUCTS) & set(payments.product_catalog())


def main():
    for name, check in sorted(globals().items()):
        if name.startswith("check_"):
            check()
    print("payment checks OK")


if __name__ == "__main__":
    main()
