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
        self._min_interval = 2.0
        self._t0 = None
        self.progress_mode = progress_mode
        self._update_count = 0

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

        # ETA only makes sense when we represent real "percent" progress.
        eta_sec = None
        self._update_count += 1
        if self.progress_mode == "percent":
            elapsed = now - self._t0
            frac = 0.0
            if self.total > 0:
                frac = min(max(float(current) / float(self.total), 0.0), 1.0)
            # Avoid absurd ETA when we only updated once or before meaningful progress.
            if (
                frac >= 0.40
                and elapsed >= 10
                and self._update_count >= 2
            ):
                eta_sec = max(((elapsed / max(frac, 0.01)) - elapsed), 0.0)
                eta_sec = min(eta_sec, 6 * 3600)  # cap at 6h

        if now - self._last_edit < self._min_interval and current < self.total:
            return
        self._last_edit = now
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
