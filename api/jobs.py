"""In-memory download / playlist job tracker."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

from api import auth, config
from api.deps import get_db, get_orchestrator, get_user_manager, ydl_opts_factory
from metadata import TrackMetadata

logger = logging.getLogger(__name__)


@dataclass
class Job:
    id: str
    user_id: str
    kind: str  # download | playlist
    status: str = "queued"  # queued|running|done|error|cancelled
    query: str = ""
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    artwork_url: Optional[str] = None
    source_url: Optional[str] = None
    error: Optional[str] = None
    progress: int = 0
    message: str = ""
    file_path: Optional[str] = None
    file_url: Optional[str] = None
    artwork_file_url: Optional[str] = None
    platform: Optional[str] = None
    cached: bool = False
    tracks_total: int = 0
    tracks_done: int = 0
    track_results: list = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    cancel_requested: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("file_path", None)
        d.pop("cancel_requested", None)
        return d


class JobManager:
    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._user_active: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def active_count(self, user_id: str) -> int:
        return len(self._user_active.get(str(user_id), set()))

    async def create_download(self, user_id: str, query: str) -> Job:
        async with self._lock:
            if self.active_count(user_id) >= config.MAX_ACTIVE_JOBS:
                raise RuntimeError("too_many_jobs")
            job = Job(
                id=str(uuid.uuid4()),
                user_id=str(user_id),
                kind="download",
                query=query.strip(),
            )
            self._jobs[job.id] = job
            self._user_active.setdefault(str(user_id), set()).add(job.id)
        asyncio.create_task(self._run_download(job.id))
        return job

    async def create_playlist(self, user_id: str, query: str) -> Job:
        async with self._lock:
            if self.active_count(user_id) >= config.MAX_ACTIVE_JOBS:
                raise RuntimeError("too_many_jobs")
            job = Job(
                id=str(uuid.uuid4()),
                user_id=str(user_id),
                kind="playlist",
                query=query.strip(),
            )
            self._jobs[job.id] = job
            self._user_active.setdefault(str(user_id), set()).add(job.id)
        asyncio.create_task(self._run_playlist(job.id))
        return job

    def cancel(self, job_id: str, user_id: str) -> Optional[Job]:
        job = self._jobs.get(job_id)
        if not job or job.user_id != str(user_id):
            return None
        job.cancel_requested = True
        if job.status in ("queued", "running"):
            job.status = "cancelled"
            job.message = "لغو شد"
            job.updated_at = time.time()
            self._release(job)
        return job

    def _release(self, job: Job):
        active = self._user_active.get(job.user_id)
        if active:
            active.discard(job.id)

    def _update(self, job: Job, **kwargs):
        for k, v in kwargs.items():
            setattr(job, k, v)
        job.updated_at = time.time()

    async def _run_download(self, job_id: str):
        job = self._jobs[job_id]
        db = get_db()
        um = get_user_manager()
        orch = get_orchestrator()
        try:
            self._update(job, status="running", progress=5, message="در حال دریافت اطلاعات...")
            if job.cancel_requested:
                self._update(job, status="cancelled")
                return

            import entitlements

            allowed, used, limit, tier = entitlements.check_quota(db, job.user_id)
            if not allowed:
                self._update(
                    job,
                    status="error",
                    error="quota",
                    message=f"سهمیه امروز تمام شد ({used}/{limit})",
                )
                return

            metadata = await TrackMetadata.create(job.query, ydl_opts_factory)
            if not metadata.title:
                self._update(job, status="error", error="not_found", message="آهنگ پیدا نشد")
                return

            self._update(
                job,
                title=metadata.title,
                artist=metadata.artist,
                album=metadata.album,
                artwork_url=metadata.artwork_url,
                source_url=metadata.url,
                progress=15,
                message="در حال دانلود...",
            )

            class _Reporter:
                progress_mode = "percent"

                async def update(self, pct, text, force=False):
                    if job.cancel_requested:
                        return
                    self_outer = job
                    self_outer.progress = max(15, min(95, int(pct)))
                    self_outer.message = text or self_outer.message
                    self_outer.updated_at = time.time()

            file_path, platform, cached, err = await orch.get_or_download(
                metadata,
                progress_reporter=_Reporter(),
                cancel_check=lambda: job.cancel_requested,
            )
            if job.cancel_requested or err == "cancelled":
                self._update(job, status="cancelled", message="لغو شد")
                return
            if err or not file_path:
                self._update(
                    job,
                    status="error",
                    error=err or "download_failed",
                    message="دانلود ناموفق بود",
                )
                return

            # Telegram file_id cannot be served to browsers — need disk path
            local_path = file_path
            if platform and str(platform).endswith("_cache_id"):
                cached_disk = orch.cache.get(metadata.title, metadata.artist, orch._source_label(metadata))
                if not cached_disk or not os.path.isfile(cached_disk):
                    self._update(
                        job,
                        status="error",
                        error="no_local_file",
                        message="فایل در کش محلی موجود نیست؛ از ربات تلگرام دوباره دانلود کنید",
                    )
                    return
                local_path = cached_disk

            if not os.path.isfile(str(local_path)):
                self._update(job, status="error", error="missing_file", message="فایل پیدا نشد")
                return

            # Persist under a stable web-served path
            web_dir = os.path.join(config.CACHE_DIR, "web")
            os.makedirs(web_dir, exist_ok=True)
            dest = os.path.join(web_dir, f"{job.id}.mp3")
            if os.path.abspath(local_path) != os.path.abspath(dest):
                shutil.copy2(local_path, dest)

            file_hash = None
            try:
                file_hash = orch._file_hash(dest)
            except Exception:
                pass

            um.record_download(
                job.user_id,
                title=metadata.title,
                artist=metadata.artist,
                platform=platform,
                source_url=metadata.url or job.query,
                album=metadata.album,
                file_hash=file_hash,
                cached=bool(cached),
            )

            token = auth.sign_file_token(dest, job.user_id, kind="audio")
            file_url = f"{config.API_PUBLIC_URL}/files/{token}" if config.API_PUBLIC_URL else f"/backend/files/{token}"
            self._update(
                job,
                status="done",
                progress=100,
                message="آماده دانلود",
                file_path=dest,
                file_url=file_url,
                platform=platform,
                cached=bool(cached),
            )
        except Exception as e:
            logger.exception("download job failed: %s", job_id)
            self._update(job, status="error", error="exception", message=str(e)[:200])
        finally:
            self._release(job)

    async def _run_playlist(self, job_id: str):
        job = self._jobs[job_id]
        db = get_db()
        um = get_user_manager()
        orch = get_orchestrator()
        try:
            self._update(job, status="running", progress=2, message="در حال خواندن پلی‌لیست...")
            name, tracks = await TrackMetadata.create_collection(job.query, ydl_opts_factory)
            if not tracks:
                # Fallback: single track
                await self._run_download(job_id)
                return

            if len(tracks) > config.MAX_PLAYLIST_TRACKS:
                tracks = tracks[:config.MAX_PLAYLIST_TRACKS]

            job.title = name or "Playlist"
            job.tracks_total = len(tracks)
            results = []
            web_dir = os.path.join(config.CACHE_DIR, "web", job.id)
            os.makedirs(web_dir, exist_ok=True)

            for i, metadata in enumerate(tracks):
                if job.cancel_requested:
                    self._update(job, status="cancelled", message="لغو شد")
                    return

                import entitlements

                allowed, used, limit, _tier = entitlements.check_quota(db, job.user_id)
                if not allowed:
                    results.append({
                        "title": metadata.title,
                        "artist": metadata.artist,
                        "status": "quota",
                    })
                    self._update(
                        job,
                        tracks_done=i,
                        track_results=results,
                        message=f"سهمیه تمام شد ({used}/{limit})",
                    )
                    break

                if not metadata.title:
                    results.append({"title": None, "status": "skip"})
                    continue

                self._update(
                    job,
                    progress=int(5 + (90 * i / max(len(tracks), 1))),
                    message=f"{metadata.title} — {metadata.artist}",
                    tracks_done=i,
                )

                file_path, platform, cached, err = await orch.get_or_download(
                    metadata,
                    cancel_check=lambda: job.cancel_requested,
                )
                if job.cancel_requested or err == "cancelled":
                    self._update(job, status="cancelled")
                    return

                entry = {
                    "title": metadata.title,
                    "artist": metadata.artist,
                    "album": metadata.album,
                    "artwork_url": metadata.artwork_url,
                    "status": "error" if err else "ok",
                    "error": err,
                    "file_url": None,
                }
                if not err and file_path:
                    local_path = file_path
                    if platform and str(platform).endswith("_cache_id"):
                        local_path = orch.cache.get(
                            metadata.title, metadata.artist, orch._source_label(metadata)
                        )
                    if local_path and os.path.isfile(str(local_path)):
                        dest = os.path.join(web_dir, f"{i}.mp3")
                        shutil.copy2(local_path, dest)
                        token = auth.sign_file_token(dest, job.user_id, kind="audio")
                        entry["file_url"] = (
                            f"{config.API_PUBLIC_URL}/files/{token}"
                            if config.API_PUBLIC_URL
                            else f"/backend/files/{token}"
                        )
                        um.record_download(
                            job.user_id,
                            title=metadata.title,
                            artist=metadata.artist,
                            platform=platform,
                            source_url=metadata.url or job.query,
                            album=metadata.album,
                            cached=bool(cached),
                        )
                results.append(entry)
                job.tracks_done = i + 1
                job.track_results = results
                job.updated_at = time.time()

            ok_count = sum(1 for r in results if r.get("status") == "ok")
            self._update(
                job,
                status="done" if ok_count else "error",
                progress=100,
                message=f"{ok_count}/{len(tracks)} آماده",
                track_results=results,
                error=None if ok_count else "all_failed",
            )
        except Exception as e:
            logger.exception("playlist job failed: %s", job_id)
            self._update(job, status="error", error="exception", message=str(e)[:200])
        finally:
            self._release(job)


jobs = JobManager()
