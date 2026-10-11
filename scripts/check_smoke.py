#!/usr/bin/env python3
"""Import smoke checks (no Telegram network). Run from repo root."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def main():
    from database import Database
    from metadata import guess_title_artist, split_version_descriptor, score_query_coverage
    from bot_commands import build_commands
    from locales import SUPPORTED

    title, artist = guess_title_artist("Tik taak na dige na kensiw remix")
    assert artist == "kensiw", (title, artist)
    assert "remix" in title.lower(), (title, artist)

    core, desc = split_version_descriptor("Song Artist slowed + reverb")
    assert desc, (core, desc)

    assert score_query_coverage("hello world", "hello", "world") >= 50

    for lang in SUPPORTED:
        cmds = build_commands(lang, admin=False)
        assert len(cmds) >= 10

    with tempfile.TemporaryDirectory() as td:
        db = Database(os.path.join(td, "smoke.db"))
        db.touch_user("1")
        assert db.get_language("1") is None

    print("smoke OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
