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
    from metadata import (
        guess_title_artist,
        split_version_descriptor,
        score_query_coverage,
        strip_featured_credit,
        looks_like_type_beat,
    )
    from downloader import _no_candidate_code
    from bot_commands import build_commands
    from locales import SUPPORTED

    title, artist = guess_title_artist("Tik taak na dige na kensiw remix")
    assert artist == "kensiw", (title, artist)
    assert "remix" in title.lower(), (title, artist)

    core, desc = split_version_descriptor("Song Artist slowed + reverb")
    assert desc, (core, desc)

    assert score_query_coverage("hello world", "hello", "world") >= 50

    # KI-11: featured-artist tokens must not sink catalog coverage.
    feat_query = strip_featured_credit(
        "tv off (feat. Lefty Gunplay) Kendrick Lamar",
        "Kendrick Lamar",
    )
    assert "lefty" not in feat_query.lower(), feat_query
    assert "kendrick" in feat_query.lower(), feat_query
    assert score_query_coverage(feat_query, "tv off", "Kendrick Lamar") >= 80
    inline = strip_featured_credit(
        "tv off feat. Lefty Gunplay Kendrick Lamar",
        "Kendrick Lamar",
    )
    assert score_query_coverage(inline, "tv off", "Kendrick Lamar") >= 80, inline
    # KI-3: a similar artist name still fails coverage when there is no feat credit.
    delorians = score_query_coverage(
        "The Center of the Universe Delorians",
        "Center of the Universe",
        "Deradoorian",
    )
    assert delorians < 80, delorians

    # KI-12: type-beat spam stays out of nearby suggestions.
    assert looks_like_type_beat(
        "Tv Off (Westcoast Kendrick Trap Drill Hip Hop Lefty Rap Gunplay Beat) KINGBNUT"
    )
    assert looks_like_type_beat(
        "Tv off (Originally Performed by Kendrick Lamar and Lefty Gunplay) [Instrumental]"
    )
    assert not looks_like_type_beat("tv off (feat. Lefty Gunplay)")
    assert not looks_like_type_beat("The Center of the Universe")
    assert not looks_like_type_beat("Instrumental")
    assert _no_candidate_code(
        nothing_scored=True,
        catalog_identified=False,
        saw_raw_results=False,
        saw_search_error=False,
        saw_bot_check=False,
    ) == "not_available"
    assert _no_candidate_code(
        nothing_scored=True,
        catalog_identified=False,
        saw_raw_results=True,
        saw_search_error=False,
        saw_bot_check=False,
    ) == "no_match"
    assert _no_candidate_code(
        nothing_scored=True,
        catalog_identified=True,
        saw_raw_results=True,
        saw_search_error=False,
        saw_bot_check=False,
    ) == "not_available"
    assert _no_candidate_code(
        nothing_scored=False,
        catalog_identified=False,
        saw_raw_results=True,
        saw_search_error=False,
        saw_bot_check=True,
    ) == "bot_check"

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
