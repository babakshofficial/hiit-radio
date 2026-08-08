"""Per-user registry of cancellable background work.

Each entry is a plain dict shared with whatever coroutine is doing the work;
setting ``cancel`` on it is how /cancel stops a download, LLM call or playlist.
"""

import os
import secrets
import time

MAX_ACTIVE_JOBS = int(os.getenv("MAX_ACTIVE_JOBS", "3"))

_STORE_KEY = "jobs"


def active(context):
    """All jobs currently registered for this user."""
    return context.user_data.setdefault(_STORE_KEY, {})


def has_slot(context):
    return len(active(context)) < MAX_ACTIVE_JOBS


def start(context, kind):
    """Register a unit of work and return its handle."""
    job = {
        "id": secrets.token_hex(4),
        "kind": kind,
        "cancel": False,
        "started": time.time(),
    }
    active(context)[job["id"]] = job
    return job


def end(context, job):
    if job:
        active(context).pop(job.get("id"), None)


def cancelled(job):
    return bool(job and job.get("cancel"))


def cancel_all(context):
    """Flag every active job for cancellation; returns the jobs that were flagged."""
    jobs = list(active(context).values())
    for job in jobs:
        job["cancel"] = True
    return jobs
