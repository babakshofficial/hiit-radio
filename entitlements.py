"""Daily download quotas, tiers, and day-pass top-ups."""

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TIER_FREE = "free"
TIER_PREMIUM = "premium"
TIER_UNLIMITED = "unlimited"

QUOTA_TZ = ZoneInfo(os.getenv("QUOTA_TZ", "Asia/Tehran"))
FREE_DAILY_LIMIT = int(os.getenv("FREE_DAILY_LIMIT", "10"))
PREMIUM_DAILY_LIMIT = int(os.getenv("PREMIUM_DAILY_LIMIT", "100"))
TOPUP_AMOUNT = int(os.getenv("TOPUP_AMOUNT", "10"))
ADMIN_ID = os.getenv("ADMIN_ID", "").strip()


def today_key(now=None):
    """Calendar day string in the quota timezone."""
    dt = datetime.now(QUOTA_TZ) if now is None else now.astimezone(QUOTA_TZ)
    return dt.strftime("%Y-%m-%d")


def day_bounds(day=None):
    """Return ``(start_ts, end_ts)`` for a calendar day in the quota timezone."""
    if day is None:
        day = today_key()
    start = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=QUOTA_TZ)
    end = start + timedelta(days=1)
    return start.timestamp(), end.timestamp()


def daily_limit(tier):
    if tier == TIER_UNLIMITED:
        return None
    if tier == TIER_PREMIUM:
        return PREMIUM_DAILY_LIMIT
    return FREE_DAILY_LIMIT


def is_admin(user_id):
    return bool(ADMIN_ID) and str(user_id) == str(ADMIN_ID)


def resolve_tier(db, user_id, now=None):
    """Return ``(tier, subscription_row_or_None)``."""
    if is_admin(user_id):
        return TIER_UNLIMITED, None
    sub = db.get_active_subscription(user_id, now=now)
    if not sub:
        return TIER_FREE, None
    tier = (sub.get("tier") or TIER_FREE).lower()
    if tier not in (TIER_PREMIUM, TIER_UNLIMITED):
        tier = TIER_FREE
    return tier, sub


def check_quota(db, user_id, now=None):
    """Return ``(allowed, used, effective_limit, tier)``.

    ``effective_limit`` is ``None`` when unlimited.
    """
    now_ts = None if now is None else (
        now.timestamp() if isinstance(now, datetime) else float(now)
    )
    tier, _sub = resolve_tier(db, user_id, now=now_ts)
    base = daily_limit(tier)
    if base is None:
        return True, 0, None, tier

    day = today_key(
        None if now is None else (
            now if isinstance(now, datetime) else datetime.fromtimestamp(now_ts, QUOTA_TZ)
        )
    )
    start_ts, end_ts = day_bounds(day)
    used = db.count_rate_events_between(user_id, start_ts, end_ts)
    bonus = int(db.sum_quota_bonuses(user_id, day) or 0)
    effective = base + bonus
    return used < effective, used, effective, tier


def grant_bonus(db, user_id, amount=None, source="topup", day=None):
    amount = TOPUP_AMOUNT if amount is None else int(amount)
    day = day or today_key()
    db.add_quota_bonus(user_id, day, amount, source=source)
    return amount, day


def grant_subscription(db, user_id, tier, days, source="manual"):
    return db.grant_subscription(user_id, tier, days, source=source)


def status_snapshot(db, user_id):
    """Dict used by /premium and limit-hit messages."""
    tier, sub = resolve_tier(db, user_id)
    allowed, used, effective, _ = check_quota(db, user_id)
    return {
        "tier": tier,
        "subscription": sub,
        "allowed": allowed,
        "used": used,
        "limit": effective,
        "day": today_key(),
        "topup_amount": TOPUP_AMOUNT,
    }
