"""Shared admin authorization for Telegram callbacks and commands."""

from __future__ import annotations

import os


def admin_id() -> str:
    return (os.getenv("ADMIN_ID") or "").strip()


def is_admin(user_id) -> bool:
    aid = admin_id()
    return bool(aid) and str(user_id) == aid


async def deny_callback(query, *, alert: str | None = None) -> bool:
    """Answer callback and return True if caller is not admin."""
    if query is None:
        return True
    user = getattr(query, "from_user", None)
    if user and is_admin(user.id):
        return False
    try:
        await query.answer(alert or "Forbidden", show_alert=bool(alert))
    except Exception:
        pass
    return True
