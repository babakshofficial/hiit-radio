"""Throttled Telegram status message updates for download progress."""

import logging
import time

from messages import progress_done, progress_fail, progress_update

logger = logging.getLogger(__name__)


class ProgressReporter:
    def __init__(
        self,
        status_message,
        total=1,
        label="در حال دانلود",
        bot=None,
        user=None,
        progress_mode="tracks",
    ):
        self.status_message = status_message
        self.total = max(total, 1)
        self.label = label
        self.bot = bot
        self.user = user
        self._last_edit = 0.0
        self._min_interval = 1.5
        self._t0 = None
        self.progress_mode = progress_mode
        self._update_count = 0
        self._last_current = -1
        self._last_detail = None

    async def _vip_status(self, status_text):
        if not self.bot:
            return
        # Avoid spamming VIP channel on every percent tick (extra Telegram RTT).
        if self.progress_mode == "percent" and self._update_count > 1:
            return
        import admin_logger
        await admin_logger.log_system(
            self.bot,
            f"وضعیت — {self.label}",
            user=self.user,
            **{"پیشرفت": status_text},
        )

    async def update(self, current, detail="", force=False):
        now = time.time()
        if self._t0 is None:
            self._t0 = now

        current = max(0, min(int(current or 0), self.total))
        advanced = current > self._last_current
        detail_changed = detail != self._last_detail

        # Always allow progress to move forward. Only throttle repeats.
        if (
            not force
            and not advanced
            and now - self._last_edit < self._min_interval
            and current < self.total
        ):
            return

        # ETA only when we have meaningful elapsed progress.
        eta_sec = None
        self._update_count += 1
        if self.progress_mode == "percent":
            elapsed = now - self._t0
            frac = float(current) / float(self.total) if self.total else 0.0
            if frac >= 0.35 and elapsed >= 8 and self._update_count >= 2:
                eta_sec = max((elapsed / max(frac, 0.01)) - elapsed, 0.0)
                eta_sec = min(eta_sec, 20 * 60)  # cap at 20 minutes

        self._last_edit = now
        self._last_current = current
        self._last_detail = detail
        show_counter = self.progress_mode == "tracks"
        text = progress_update(
            self.label,
            current,
            self.total,
            detail,
            eta_sec=eta_sec,
            show_counter=show_counter,
        )
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
