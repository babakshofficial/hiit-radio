"""Shared bot services for the HTTP API."""

from __future__ import annotations

import logging
from functools import lru_cache

from telegram import Bot

from api import config
from downloader import MusicDownloader
from download_orchestrator import DownloadOrchestrator
from user_manager import UserManager

logger = logging.getLogger(__name__)


def ydl_opts_factory():
    return get_downloader()._build_search_opts()


@lru_cache(maxsize=1)
def get_user_manager() -> UserManager:
    return UserManager(config.DATABASE_PATH)


@lru_cache(maxsize=1)
def get_db():
    return get_user_manager().database


@lru_cache(maxsize=1)
def get_downloader() -> MusicDownloader:
    return MusicDownloader()


@lru_cache(maxsize=1)
def get_orchestrator() -> DownloadOrchestrator:
    dl = get_downloader()
    return DownloadOrchestrator(dl, get_db(), download_dir=dl.download_dir)


@lru_cache(maxsize=1)
def get_bot() -> Bot | None:
    if not config.BOT_TOKEN:
        return None
    return Bot(token=config.BOT_TOKEN)
