"""Per-user registry of cancellable background work.

Jobs live in ``context.user_data`` *and* in process-global maps keyed by
Telegram user id, so /stop works even while another handler is still running.
"""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
import threading
import time

logger = logging.getLogger(__name__)

MAX_ACTIVE_JOBS = int(os.getenv("MAX_ACTIVE_JOBS", "3"))

_STORE_KEY = "jobs"

_guard = threading.Lock()
_abort_events: dict[int, threading.Event] = {}
_procs: dict[int, set] = {}
_tasks: dict[int, set] = {}
_jobs_by_user: dict[int, dict] = {}


def _as_uid(user_id):
    try:
        return int(user_id)
    except (TypeError, ValueError):
        return None


def user_id_of(context):
    uid = getattr(context, "_user_id", None)
    if uid is not None:
        return _as_uid(uid)
    return None


def _event(uid: int) -> threading.Event:
    with _guard:
        ev = _abort_events.get(uid)
        if ev is None:
            ev = threading.Event()
            _abort_events[uid] = ev
        return ev


def abort_requested(user_id) -> bool:
    uid = _as_uid(user_id)
    if uid is None:
        return False
    ev = _abort_events.get(uid)
    return bool(ev and ev.is_set())


def clear_abort(user_id) -> None:
    uid = _as_uid(user_id)
    if uid is None:
        return
    ev = _abort_events.get(uid)
    if ev:
        ev.clear()


def register_proc(user_id, proc) -> None:
    uid = _as_uid(user_id)
    if uid is None or proc is None:
        return
    with _guard:
        _procs.setdefault(uid, set()).add(proc)


def unregister_proc(user_id, proc) -> None:
    uid = _as_uid(user_id)
    if uid is None or proc is None:
        return
    with _guard:
        bucket = _procs.get(uid)
        if bucket:
            bucket.discard(proc)
            if not bucket:
                _procs.pop(uid, None)


def register_task(user_id, task) -> None:
    uid = _as_uid(user_id)
    if uid is None or task is None:
        return
    with _guard:
        _tasks.setdefault(uid, set()).add(task)


def unregister_task(user_id, task) -> None:
    uid = _as_uid(user_id)
    if uid is None or task is None:
        return
    with _guard:
        bucket = _tasks.get(uid)
        if bucket:
            bucket.discard(task)
            if not bucket:
                _tasks.pop(uid, None)


def has_work(user_id) -> bool:
    uid = _as_uid(user_id)
    if uid is None:
        return False
    with _guard:
        return bool(_procs.get(uid) or _tasks.get(uid) or _jobs_by_user.get(uid))


def _kill_proc(proc) -> None:
    try:
        proc.kill()
    except Exception:
        pass
    try:
        proc.wait(timeout=3)
    except Exception:
        pass


def request_abort(user_id) -> bool:
    """Set abort, kill worker processes, cancel download tasks. Returns True if work existed."""
    uid = _as_uid(user_id)
    if uid is None:
        return False
    _event(uid).set()
    with _guard:
        procs = list(_procs.get(uid, ()))
        tasks = list(_tasks.get(uid, ()))
        job_count = len(_jobs_by_user.get(uid, {}))
    had = bool(procs or tasks or job_count)
    for proc in procs:
        _kill_proc(proc)
    current = None
    try:
        current = asyncio.current_task()
    except Exception:
        pass
    for task in tasks:
        if task is current or task.done():
            continue
        task.cancel()
    if had:
        logger.info(
            "Abort requested for user %s (procs=%d tasks=%d jobs=%d)",
            uid, len(procs), len(tasks), job_count,
        )
    return had


def active(context):
    """All jobs currently registered for this user."""
    return context.user_data.setdefault(_STORE_KEY, {})


def has_slot(context):
    uid = user_id_of(context)
    n = len(active(context))
    if uid is not None:
        with _guard:
            n = max(n, len(_jobs_by_user.get(uid, {})))
    return n < MAX_ACTIVE_JOBS


def start(context, kind, user_id=None):
    """Register a unit of work and return its handle."""
    uid = _as_uid(user_id) or user_id_of(context)
    if uid is not None:
        with _guard:
            existing = _jobs_by_user.get(uid)
        if not existing and not active(context):
            clear_abort(uid)
    job = {
        "id": secrets.token_hex(4),
        "kind": kind,
        "cancel": False,
        "started": time.time(),
        "user_id": uid,
        "lang": None,
    }
    try:
        import messages as _msg
        job["lang"] = _msg.get_lang()
    except Exception:
        pass
    active(context)[job["id"]] = job
    if uid is not None:
        with _guard:
            _jobs_by_user.setdefault(uid, {})[job["id"]] = job
    return job


def attach_task(job, task) -> None:
    if not job or not task:
        return
    job["task"] = task
    uid = job.get("user_id")
    if uid is not None:
        register_task(uid, task)


def spawn(context, job, coro):
    """Run ``coro`` in the background so /stop can be handled immediately."""

    async def _runner():
        uid = job.get("user_id") if job else None
        lang_token = None
        try:
            import messages as msg
            if job and job.get("lang"):
                lang_token = msg.use_lang(job["lang"])
        except Exception:
            lang_token = None
        try:
            await coro
        except asyncio.CancelledError:
            logger.info("Job %s cancelled", (job or {}).get("kind") or "work")
            status = (job or {}).get("status_message")
            if status is not None:
                try:
                    import messages as msg
                    kind = (job or {}).get("kind") or ""
                    text = (
                        msg.download_cancelled()
                        if kind in ("track", "playlist", "work")
                        else msg.work_cancelled()
                    )
                    await status.edit_text(text)
                except Exception:
                    pass
        except Exception:
            logger.exception("Job %s crashed", (job or {}).get("kind") or "work")
        finally:
            if lang_token is not None:
                try:
                    import messages as msg
                    msg.reset_lang(lang_token)
                except Exception:
                    pass
            if uid is not None:
                unregister_task(uid, asyncio.current_task())
            end(context, job)

    task = asyncio.create_task(_runner())
    attach_task(job, task)
    uid = job.get("user_id") if job else None
    if uid is not None and abort_requested(uid) and not task.done():
        task.cancel()
    return task


def end(context, job):
    if not job:
        return
    if context is not None:
        active(context).pop(job.get("id"), None)
    uid = job.get("user_id")
    task = job.get("task")
    if uid is not None and task is not None:
        unregister_task(uid, task)
    if uid is not None:
        with _guard:
            bucket = _jobs_by_user.get(uid)
            if bucket:
                bucket.pop(job.get("id"), None)
                if not bucket:
                    _jobs_by_user.pop(uid, None)
            leftover = _jobs_by_user.get(uid)
            still = bool(leftover or _procs.get(uid) or _tasks.get(uid))
        if not still:
            clear_abort(uid)


def cancelled(job):
    if job and job.get("cancel"):
        return True
    uid = job.get("user_id") if job else None
    return abort_requested(uid)


def cancel_all(context, user_id=None):
    """Flag every active job for cancellation; returns the jobs that were flagged."""
    uid = _as_uid(user_id) or user_id_of(context)
    flagged = list(active(context).values())
    if uid is not None:
        with _guard:
            seen = {j.get("id") for j in flagged}
            for job in list((_jobs_by_user.get(uid) or {}).values()):
                if job.get("id") not in seen:
                    flagged.append(job)
                    seen.add(job.get("id"))
    for job in flagged:
        job["cancel"] = True
        if uid is None:
            uid = job.get("user_id")
    had_work = bool(flagged) or (uid is not None and has_work(uid))
    aborted = False
    if uid is not None and had_work:
        aborted = request_abort(uid)
    elif uid is not None:
        clear_abort(uid)
    if flagged:
        return flagged
    if had_work or aborted:
        return [{"kind": "work", "id": "abort", "cancel": True, "user_id": uid}]
    return []
