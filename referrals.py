"""Referral deep-links that grant day-pass top-ups."""

import logging
import os

import entitlements

logger = logging.getLogger(__name__)

REFERRALS_PER_TOPUP = int(os.getenv("REFERRALS_PER_TOPUP", "3"))
BOT_USERNAME = (
    os.getenv("BOT_USERNAME", "").strip().lstrip("@")
    or os.getenv("BOT_INLINE", "HiiTRadioBot").strip().lstrip("@")
    or "HiiTRadioBot"
)


def invite_link(user_id):
    return f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"


def parse_start_payload(args):
    """Return inviter_id from ``/start ref_<id>`` args, or None."""
    if not args:
        return None
    raw = (args[0] or "").strip()
    if not raw.startswith("ref_"):
        return None
    inviter = raw[4:].strip()
    if not inviter.isdigit():
        return None
    return inviter


def record_pending(db, inviter_id, invited_id, *, is_new_user):
    """Record a pending referral for a brand-new invitee.

    Returns one of: ``created``, ``self``, ``duplicate``, ``existing_user``.
    """
    inviter_id = str(inviter_id)
    invited_id = str(invited_id)
    if inviter_id == invited_id:
        return "self"
    if not is_new_user:
        return "existing_user"
    ok = db.create_referral(inviter_id, invited_id)
    return "created" if ok else "duplicate"


def maybe_credit_on_membership(db, invited_id):
    """If invitee just passed the channel gate, credit inviter and maybe top-up.

    Returns ``(credited_inviter_id_or_None, topups_granted)``.
    """
    inviter_id = db.credit_referral(invited_id)
    if not inviter_id:
        return None, 0
    credited_total = db.count_credited_referrals(inviter_id)
    topups = 0
    if credited_total > 0 and credited_total % REFERRALS_PER_TOPUP == 0:
        entitlements.grant_bonus(
            db,
            inviter_id,
            amount=entitlements.TOPUP_AMOUNT,
            source=f"referral:{invited_id}",
        )
        topups = 1
        logger.info(
            "Referral top-up granted to %s after %s credits (invitee=%s)",
            inviter_id, credited_total, invited_id,
        )
    return inviter_id, topups


def progress(db, inviter_id):
    credited = db.count_credited_referrals(inviter_id)
    pending = db.count_pending_referrals(inviter_id)
    toward = credited % REFERRALS_PER_TOPUP
    return {
        "credited": credited,
        "pending": pending,
        "toward": toward,
        "needed": REFERRALS_PER_TOPUP,
        "link": invite_link(inviter_id),
    }
