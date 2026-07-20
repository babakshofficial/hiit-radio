"""Throttled Telegram status message updates for download progress."""

import logging
import time

from messages import progress_done, progress_fail, progress_update

logger = logging.getLogger(__name__)


class ProgressReporter:
    def __init__(self, status_message, total=1, label="در حال دانلود", bot=None, user=None):
        self.status_message = status_message
        self.total = max(total, 1)
        self.label = label
        self.bot = bot
        self.user = user
        self._last_edit = 0.0
        self._min_interval = 2.0
        self._t0 = None

    async def _vip_status(self, status_text):
        if not self.bot:
            return
        import admin_logger
        await admin_logger.log_system(
            self.bot,
            f"وضعیت — {self.label}",
            user=self.user,
            **{"پیشرفت": status_text},
        )

    async def update(self, current, detail=""):
        now = time.time()
        if self._t0 is None:
            self._t0 = now

        eta_sec = None
        if self.total > 0 and current > 0:
            elapsed = now - self._t0
            frac = min(max(float(current) / float(self.total), 0.0), 1.0)
            if frac > 0:
                # Simple linear ETA based on achieved fraction.
                eta_sec = max((elapsed / frac) - elapsed, 0.0)
        if now - self._last_edit < self._min_interval and current < self.total:
            return
        self._last_edit = now
        text = progress_update(self.label, current, self.total, detail, eta_sec=eta_sec)
        status_text = f"{current}/{self.total}"
        if detail:
            status_text += f" — {detail}"
        await self._vip_status(status_text)
        try:
            await self.status_message.edit_text(text)
        except Exception as e:
            logger.debug(f"Progress edit skipped: {e}")

    async def done(self, summary=""):
        text = progress_done(self.label, summary)
        await self._vip_status(summary or "تمام شد")
        try:
            await self.status_message.edit_text(text)
        except Exception:
            pass

    async def fail(self, reason=""):
        text = progress_fail(self.label, reason)
        await self._vip_status(reason or "ناموفق")
        try:
            await self.status_message.edit_text(text)
        except Exception:
            pass
