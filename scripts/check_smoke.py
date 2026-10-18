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
        shazam_track_id,
        is_shazam_url,
        ShazamMetadata,
    )
    from bs4 import BeautifulSoup
    from downloader import (
        _no_candidate_code,
        _primary_artist,
        _lead_artist,
        _coverage_query,
        _uploader_artist_match,
        _title_artist_credit,
    )
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

    # KI-13: "&" collaborators and label "Artist - Song" uploads.
    assert _primary_artist("Florence & The Machine") == "Florence & The Machine"
    assert _lead_artist("WizTheMc & bees & honey") == "WizTheMc"
    assert _uploader_artist_match("WizTheMc & bees & honey", "WizTheMc") >= 85
    assert _uploader_artist_match("Delorians", "Deradoorian") < 85
    assert _title_artist_credit(
        "Jazzy & Ankhoï - Closer To The Floor", "Jazzy & Ankhoï",
    ) >= 85
    assert _title_artist_credit(
        "WizTheMc - Take My Mind (Official Video)", "WizTheMc & bees & honey",
    ) >= 85
    assert _title_artist_credit("Center of the Universe", "Delorians") == 0
    assert _title_artist_credit(
        "Deradoorian - Center of the Universe", "Delorians",
    ) < 85
    wiz = _coverage_query(
        "Take My Mind WizTheMc & bees & honey", "WizTheMc & bees & honey",
    )
    assert "bees" not in wiz.lower() and "honey" not in wiz.lower(), wiz
    assert score_query_coverage(
        wiz, "WizTheMc - Take My Mind (Official Video)", "WizTheMc",
    ) >= 80
    jazzy = _coverage_query("Closer To The Floor Jazzy & Ankhoï", "Jazzy & Ankhoï")
    assert score_query_coverage(
        jazzy, "Jazzy & Ankhoï - Closer To The Floor", "Melodicity Recordings",
    ) >= 80, jazzy
    assert score_query_coverage(
        _coverage_query("The Center of the Universe Delorians", "Delorians"),
        "Center of the Universe",
        "Deradoorian",
    ) < 80

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

    assert shazam_track_id(
        "https://www.shazam.com/track/549952578/blinding-lights"
    ) == "549952578"
    assert shazam_track_id(
        "https://www.shazam.com/en-us/song/657717032/as-it-was"
    ) == "657717032"
    assert shazam_track_id(
        "https://www.shazam.com/charts/top-200/united-states"
    ) is None
    assert is_shazam_url("https://www.shazam.com/track/1/x")
    assert is_shazam_url("https://shz.am/t/abc")
    assert not is_shazam_url("https://music.apple.com/us/album/x/1")

    # KI-14: unavailable Shazam pages omit og:title; the header still has the song.
    header = ShazamMetadata("https://www.shazam.com/track/861026094/x")
    assert header._apply_page_header(BeautifulSoup(
        '<div class="NewTrackPageHeader_trackTitle__abc">'
        'Million Pieces (feat. x) [Malive Remix]</div>'
        '<span class="TrackPageArtistLink_artistNameText__xyz">'
        'Adam Ten &amp; Mita Gami</span>',
        "html.parser",
    ))
    assert header.title.startswith("Million Pieces")
    assert header.artist == "Adam Ten & Mita Gami"
    hashed = ShazamMetadata(
        "https://www.shazam.com/track/861026094/x"
        "#%7B%22title%22%3A%22Million%20Pieces%22%2C%22artist%22%3A%22Adam%20Ten%22%7D"
    )
    assert hashed._apply_fragment()
    assert hashed.title == "Million Pieces"
    assert hashed.artist == "Adam Ten"

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
