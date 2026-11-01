#!/usr/bin/env python3
"""Checks for version picking, song recognition, gift links and the weekly mix. No network.

Usage: python scripts/check_features.py
"""

import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(ROOT / "scripts"))
WORK = tempfile.mkdtemp(prefix="hiit_feature_check_")
os.environ.update(
    BOT_TOKEN="123:check",
    ADMIN_ID="1",
    DATABASE_PATH=str(Path(WORK) / "check.db"),
    CACHE_DIR=str(Path(WORK) / "cache"),
    YTDLP_COOKIES=str(Path(WORK) / "cookies.txt"),
    REQUIRED_CHANNEL="",
    LLM_API_KEY="",
)
os.chdir(WORK)

from telegram.error import Forbidden  # noqa: E402

import download_orchestrator  # noqa: E402
import main as bot_main  # noqa: E402
import song_recognition  # noqa: E402
import weekly_mix  # noqa: E402
from database import Database  # noqa: E402
from downloader import MusicDownloader  # noqa: E402
from metadata import AppleMusicMetadata  # noqa: E402
from recommendations import recommendation_keyboard, resolve_track_ref_full  # noqa: E402

USER = "2001"
WEEK = weekly_mix.MIX_INTERVAL_SEC


class FakeBot:
    def __init__(self, error=None):
        self.sent = []
        self.error = error

    async def send_message(self, chat_id, text, reply_markup=None):
        if self.error:
            raise self.error
        self.sent.append(SimpleNamespace(chat_id=chat_id, text=text, keyboard=reply_markup))


def fresh_db():
    db = Database(str(Path(WORK) / f"db_{time.time_ns()}.db"))
    db.touch_user(USER)
    return db


def seed_chart(db, n=8):
    for i in range(n):
        db.log_download("9", f"Song {i}", f"Artist {i}", "youtube", None, None, None, False)


def buttons(markup):
    return [b for row in markup.inline_keyboard for b in row]


def check_wrong_version_button_keeps_delivered_url():
    markup = recommendation_keyboard(
        "Artist", "Song", matched_url="https://www.youtube.com/watch?v=abc",
    )
    alt = [b for b in buttons(markup) if b.callback_data.startswith("alt:list:")]
    assert len(alt) == 1 and len(alt[0].callback_data.encode()) <= 64
    token = alt[0].callback_data.split(":")[2]
    assert resolve_track_ref_full(token)["matched_url"].endswith("v=abc")


def check_alternatives_only_offer_downloadable_links():
    results = {
        "ytsearch": [
            {"id": "delivered", "url": "https://www.youtube.com/watch?v=delivered", "title": "Same"},
            {"id": "good", "url": "https://www.youtube.com/watch?v=good", "title": "Good",
             "uploader": "Up", "duration": 200},
            {"id": "long", "url": "https://www.youtube.com/watch?v=long", "title": "10 hours",
             "duration": 36000},
            {"id": "evil", "url": "http://127.0.0.1/x?youtube.com", "title": "Evil"},
            None,
        ],
        "scsearch": [
            {"id": "1", "webpage_url": "https://soundcloud.com/a/b", "title": "SC"},
            {"id": "2", "url": "https://api.soundcloud.com/tracks/2", "title": "API only"},
        ],
    }

    class FakeYdl:
        def __init__(self, opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_info(self, query, download=False):
            return {"entries": results[query.split(":")[0].rstrip("0123456789")]}

    import downloader as dl
    real = dl.yt_dlp.YoutubeDL
    dl.yt_dlp.YoutubeDL = FakeYdl
    try:
        found = MusicDownloader(download_dir=str(Path(WORK) / "dl")).search_alternatives(
            "Song", "Artist", "https://www.youtube.com/watch?v=delivered",
        )
    finally:
        dl.yt_dlp.YoutubeDL = real
    assert [f["url"] for f in found] == [
        "https://www.youtube.com/watch?v=good", "https://soundcloud.com/a/b",
    ], found
    assert found[0]["source"] == "YouTube" and found[1]["source"] == "SoundCloud"


def check_chosen_version_stays_out_of_shared_cache():
    class FakeCache:
        puts = 0

        def get(self, *a):
            raise AssertionError("a chosen version must not read the shared cache")

        def put(self, *a):
            type(self).puts += 1

    db = fresh_db()
    orchestrator = download_orchestrator.DownloadOrchestrator.__new__(
        download_orchestrator.DownloadOrchestrator,
    )
    target = Path(WORK) / "picked.mp3"
    target.write_bytes(b"x")

    class FakeDownloader:
        async def download_song(self, metadata, **kwargs):
            return str(target), None, []

    orchestrator.db = db
    orchestrator.cache = FakeCache()
    orchestrator.music_downloader = FakeDownloader()

    async def no_lyrics(*a):
        return None

    orchestrator._embed_lyrics = no_lyrics
    meta = bot_main._track_from_names("Song", "Artist")
    meta.source_url = meta.url = "https://www.youtube.com/watch?v=good"
    meta.is_replacement = True
    meta.search_query = "song artist"
    path, _platform, cached, code = asyncio.run(orchestrator.get_or_download(meta, quality="192"))
    assert path == str(target) and code is None and not cached
    assert FakeCache.puts == 0


def check_only_first_replacement_is_free():
    denied, started = [], []

    async def fake_deny(message, bot, user):
        denied.append(True)
        return True

    async def not_busy(message, context):
        return False

    real = (bot_main._deny_quota, bot_main._reject_if_busy, bot_main._start_job, bot_main._spawn_job)
    bot_main._deny_quota = fake_deny
    bot_main._reject_if_busy = not_busy
    bot_main._start_job = lambda context, kind: {}
    bot_main._spawn_job = lambda context, job, coro: (started.append(True), coro.close())
    try:
        context = SimpleNamespace(bot=None)
        meta = bot_main._track_from_names("Song", "Artist")
        meta.alt_entry = {"free": True}
        asyncio.run(bot_main._download_and_send(None, None, meta, context))
        assert started and not denied, "over-quota users can still fix a wrong match"
        started.clear()
        meta.alt_entry = {"free": False}
        asyncio.run(bot_main._download_and_send(None, None, meta, context))
        assert denied and not started, "later swaps use normal quota"
    finally:
        (bot_main._deny_quota, bot_main._reject_if_busy,
         bot_main._start_job, bot_main._spawn_job) = real


def check_quota_flag():
    manager = bot_main.user_manager
    manager.record_download(USER, "Song", "Artist", "youtube", count_quota=False)
    now = time.time()
    assert manager.db.count_rate_events_between(USER, now - 60, now + 60) == 0
    manager.record_download(USER, "Song", "Artist", "youtube")
    assert manager.db.count_rate_events_between(USER, now - 60, now + 60) == 1


def check_recognition_parsing_and_limit():
    parse = song_recognition.parse_result
    assert parse({"track": {"title": "T", "subtitle": "A"}}) == {"title": "T", "artist": "A"}
    assert parse({"matches": []}) is None and parse(None) is None
    assert parse({"track": {"title": "  "}}) is None
    for i in range(song_recognition.RATE_LIMIT):
        assert song_recognition.within_rate_limit("u", now=100.0 + i)
    assert not song_recognition.within_rate_limit("u", now=200.0)
    assert song_recognition.within_rate_limit("u", now=5000.0), "the limit resets"


def check_recognition_handles_junk_and_missing_library():
    junk = Path(WORK) / "junk.bin"
    junk.write_bytes(b"not media")

    async def run():
        return await song_recognition._extract_clip(str(junk), str(Path(WORK) / "out.wav"))

    assert asyncio.run(run()) is False

    path = os.environ["PATH"]
    os.environ["PATH"] = str(Path(WORK) / "empty")
    try:
        asyncio.run(run())
    except song_recognition.RecognitionUnavailable:
        pass
    else:
        raise AssertionError("a missing ffmpeg must report recognition as unavailable")
    finally:
        os.environ["PATH"] = path


def check_mix_is_opt_in():
    db = fresh_db()
    seed_chart(db)
    bot = FakeBot()
    now = time.time()
    assert db.list_weekly_mix_due(now, WEEK) == []
    assert asyncio.run(weekly_mix.send_mix(bot, db, USER, now=now)) is False
    assert not bot.sent


def _no_catalog():
    async def search(query):
        return None
    AppleMusicMetadata.search_by_query = staticmethod(search)


def check_mix_sends_at_most_weekly():
    _no_catalog()
    db = fresh_db()
    seed_chart(db)
    db.set_weekly_mix(USER, True)
    bot = FakeBot()
    now = time.time()
    assert asyncio.run(weekly_mix.send_mix(bot, db, USER, now=now)) is True
    assert asyncio.run(weekly_mix.send_mix(bot, db, USER, now=now + 60)) is False
    db.set_weekly_mix(USER, False)
    db.set_weekly_mix(USER, True)
    assert asyncio.run(weekly_mix.send_mix(bot, db, USER, now=now + 120)) is False
    assert len(bot.sent) == 1, "toggling must not produce extra mixes"
    assert db.list_weekly_mix_due(now + 60, WEEK) == []
    assert db.list_weekly_mix_due(now + WEEK + 1, WEEK) == [USER]

    sent = bot.sent[0]
    picks = [b for b in buttons(sent.keyboard) if b.callback_data.startswith("mixpick:")]
    assert picks and len(picks) <= weekly_mix.MIX_SIZE
    assert any(b.callback_data == "mix:off" for b in buttons(sent.keyboard))
    item_id = int(picks[0].callback_data.split(":")[1])
    assert db.get_weekly_mix_item(item_id, USER), "picks must survive a restart"
    assert db.get_weekly_mix_item(item_id, "other") is None, "picks belong to their user"


def check_mix_skips_what_user_heard_and_blocks():
    _no_catalog()
    db = fresh_db()
    seed_chart(db)
    db.log_download(USER, "Song 0", "Artist 0", "youtube", None, None, None, False)
    db.set_weekly_mix(USER, True)
    bot = FakeBot()
    asyncio.run(weekly_mix.send_mix(bot, db, USER))
    assert "Song 0" not in bot.sent[0].text
    assert bot.sent[0].text.count("Song ") == weekly_mix.MIX_SIZE

    db = fresh_db()
    seed_chart(db)
    db.set_weekly_mix(USER, True)
    asyncio.run(weekly_mix.send_mix(FakeBot(Forbidden("blocked")), db, USER))
    assert not db.get_weekly_mix_enabled(USER), "stop messaging someone who blocked the bot"


def check_mix_retries_after_send_failure():
    _no_catalog()
    db = fresh_db()
    seed_chart(db)
    db.set_weekly_mix(USER, True)
    now = time.time()
    assert asyncio.run(weekly_mix.send_mix(FakeBot(RuntimeError("down")), db, USER, now=now)) is False
    assert db.list_weekly_mix_due(now, WEEK) == [USER]


def check_mix_ai_picks():
    db = fresh_db()
    seed_chart(db)
    db.log_download(USER, "Heard", "Me", "youtube", None, None, None, False)
    db.set_weekly_mix(USER, True)

    async def catalog(query):
        if "Fake" in query:
            return None
        title, artist = query.rsplit(" ", 1)
        return SimpleNamespace(title=title, artist=artist)

    async def good(history, user_id=None, limit=10):
        recs = [
            {"title": "Real", "artist": "One"},
            {"title": "Fake", "artist": "Two"},
            {"title": "Heard", "artist": "Me"},
        ]
        return recs, {"model": "m", "success": True, "recommendations_count": 3}

    async def bad(history, user_id=None, limit=10):
        raise RuntimeError("LLM down")

    real = (weekly_mix.recommend_songs, weekly_mix.llm_configured, AppleMusicMetadata.search_by_query)
    weekly_mix.llm_configured = lambda: True
    AppleMusicMetadata.search_by_query = staticmethod(catalog)
    try:
        weekly_mix.recommend_songs = good
        picks, _ = asyncio.run(weekly_mix.build_mix(db, USER))
        titles = [p["title"] for p in picks]
        assert titles[0] == "Real", titles
        assert "Fake" not in titles, "songs missing from the catalog are dropped"
        assert "Heard" not in titles, "songs the user already downloaded are dropped"
        assert len(picks) == weekly_mix.MIX_SIZE, "charts fill the remaining places"

        weekly_mix.recommend_songs = bad
        picks, _ = asyncio.run(weekly_mix.build_mix(db, USER))
        assert len(picks) == weekly_mix.MIX_SIZE, "an AI outage still produces a mix"
    finally:
        weekly_mix.recommend_songs, weekly_mix.llm_configured = real[:2]
        AppleMusicMetadata.search_by_query = staticmethod(real[2])


def check_mix_release_window():
    db = fresh_db()
    db.follow_artist(USER, "New Artist", "77")
    today = time.strftime("%Y-%m-%d", time.gmtime())
    db.mark_release_notified("77", "fresh", "Fresh Album", today)
    db.mark_release_notified("77", "stale", "Old Album", "2001-01-01")
    db.mark_release_notified("88", "unfollowed", "Other", today)
    assert [r["title"] for r in db.recent_releases_for_user(USER)] == ["Fresh Album"]


def check_mix_respects_send_hours():
    db = fresh_db()
    # 2026-01-01 00:00 UTC is 03:30 in Tehran; 12:00 UTC is 15:30.
    assert weekly_mix._within_send_hours(1767225600) is False
    assert weekly_mix._within_send_hours(1767225600 + 12 * 3600) is True
    real = weekly_mix._within_send_hours
    weekly_mix._within_send_hours = lambda now=None: False
    try:
        db.set_weekly_mix(USER, True)
        seed_chart(db)
        bot = FakeBot()
        assert asyncio.run(weekly_mix.run_due(bot, db)) == 0 and not bot.sent
    finally:
        weekly_mix._within_send_hours = real


class FakeMessage:
    def __init__(self, text=None, **media):
        self.text = text
        self.chat_id = int(USER)
        self.replies = []
        self.voice = media.get("voice")
        self.video_note = media.get("video_note")
        self.video = media.get("video")
        self.audio = media.get("audio")

    async def reply_text(self, text, reply_markup=None, **kwargs):
        reply = SimpleNamespace(text=text, keyboard=reply_markup, edits=[])

        async def edit_text(new_text, reply_markup=None, **kw):
            reply.text, reply.keyboard = new_text, reply_markup

        reply.edit_text = edit_text
        self.replies.append(reply)
        return reply


def _context(**extra):
    bot = FakeBot()
    bot.username = "HiitCheckBot"
    tasks = []

    def create_task(coro):
        tasks.append(coro)

    return SimpleNamespace(
        bot=bot, args=[], user_data={},
        application=SimpleNamespace(create_task=create_task), tasks=tasks, **extra,
    )


def _user(uid=USER):
    return SimpleNamespace(
        id=int(uid), username=None, first_name="X", last_name=None,
        language_code="en", is_bot=False, full_name="X",
    )


def _press(data, context, uid=USER):
    message = FakeMessage()
    edits = []

    async def answer(*a, **k):
        return None

    async def edit_message_text(text, **k):
        edits.append(text)

    query = SimpleNamespace(
        data=data, message=message, from_user=_user(uid), answer=answer,
        edit_message_text=edit_message_text,
    )
    update = SimpleNamespace(
        callback_query=query, effective_user=_user(uid), effective_message=message,
        effective_chat=SimpleNamespace(id=int(uid)), message=None,
    )
    asyncio.run(bot_main.callback_handler(update, context))
    return message, edits


def check_buttons_route_to_their_features():
    db = bot_main.user_manager.database
    seed_chart(db)
    _no_catalog()

    # Weekly mix on and off.
    context = _context()
    message, _ = _press("mix:on", context)
    assert db.get_weekly_mix_enabled(USER) and message.replies
    assert context.tasks, "turning it on sends the first mix"
    context.tasks[0].close()
    _press("mix:off", context)
    assert not db.get_weekly_mix_enabled(USER)

    # Gift menu.
    message, _ = _press("pay:gift", _context())
    labels = [b.callback_data for b in buttons(message.replies[0].keyboard)]
    assert "pay:gift_weekly" in labels and "pay:gift_monthly" in labels

    # A mix pick belongs to its owner.
    item_id = db.save_weekly_mix_items(USER, [{"title": "Song", "artist": "A"}])[0]
    downloads = []

    async def fake_named(message, user, context, title, artist):
        downloads.append((title, artist))

    real = bot_main._download_named_track
    bot_main._download_named_track = fake_named
    try:
        _press(f"mixpick:{item_id}", _context())
        assert downloads == [("Song", "A")]
        downloads.clear()
        message, _ = _press(f"mixpick:{item_id}", _context(), uid="2002")
        assert not downloads and message.replies, "another user's pick must not download"

        # A recognized song.
        token = bot_main.remember_track_ref("Found", "Singer")
        _press(f"recog:{token}", _context())
        assert downloads == [("Found", "Singer")]
    finally:
        bot_main._download_named_track = real


def check_only_admin_can_refund():
    db = bot_main.user_manager.database
    db.touch_user(USER)
    row, _, _ = bot_main.payments.apply_purchase(
        db, USER, bot_main.payments.KIND_WEEKLY, 75, "XTR", "route_charge",
    )
    calls = []

    async def refund(user_id, telegram_payment_charge_id):
        calls.append(telegram_payment_charge_id)

    context = _context()
    context.bot.refund_star_payment = refund
    _press(f"refund:confirm:{row['id']}", context, uid=USER)
    assert not calls and db.get_payment(row["id"])["status"] == "paid", "non-admin refund"

    update = SimpleNamespace(
        effective_user=_user(USER), message=FakeMessage(), effective_message=None,
    )
    context.args = [str(row["id"])]
    asyncio.run(bot_main.refund_command(update, context))
    asyncio.run(bot_main.payments_command(update, context))
    assert not update.message.replies, "admin commands must stay silent for others"

    _, edits = _press(f"refund:confirm:{row['id']}", context, uid="1")
    assert calls == ["route_charge"] and edits
    assert db.get_payment(row["id"])["status"] == "refunded"


def check_alternative_buttons():
    token = bot_main.remember_track_ref(
        "Song", "Artist", matched_url="https://www.youtube.com/watch?v=old",
    )
    items = [{
        "url": "https://www.youtube.com/watch?v=new", "title": "Song live",
        "uploader": "Up", "duration": 200, "source": "YouTube",
    }]
    real_search = bot_main.downloader.search_alternatives
    real_send = bot_main._download_and_send
    sent = []

    async def fake_send(message, user, metadata, context):
        sent.append(metadata)

    bot_main.downloader.search_alternatives = lambda *a: items
    bot_main._download_and_send = fake_send
    try:
        context = _context()
        message, _ = _press(f"alt:list:{token}", context)
        keyboard = message.replies[0].keyboard
        pick = [b for b in buttons(keyboard) if b.callback_data.startswith("alt:pick:")]
        assert len(pick) == 1 and len(pick[0].callback_data.encode()) <= 64
        _press(pick[0].callback_data, context)
        chosen = sent[0]
        assert chosen.source_url == items[0]["url"] and chosen.is_replacement
        assert (chosen.title, chosen.artist) == ("Song", "Artist")
        assert chosen.alt_entry["free"] is True

        message, _ = _press(f"alt:pick:{token}:9", context)
        assert len(sent) == 1 and message.replies, "an out-of-range pick is rejected"
        message, _ = _press("alt:pick:deadbeef:0", _context())
        assert len(sent) == 1 and message.replies, "a pick from before a restart expires"
    finally:
        bot_main.downloader.search_alternatives = real_search
        bot_main._download_and_send = real_send


def _media_update(**media):
    message = FakeMessage(**media)
    return SimpleNamespace(
        message=message, effective_message=message, effective_user=_user("2003"),
        effective_chat=SimpleNamespace(id=2003),
    ), message


def check_voice_note_flow():
    class Media:
        file_size = 1000

        async def get_file(self):
            async def download_to_drive(path):
                Path(path).write_bytes(b"x")
            return SimpleNamespace(download_to_drive=download_to_drive)

    real = song_recognition.recognize_file

    async def found(path):
        assert os.path.exists(path)
        return {"title": "Faded", "artist": "Alan Walker"}

    async def nothing(path):
        return None

    async def broken(path):
        raise song_recognition.RecognitionUnavailable("down")

    try:
        song_recognition.recognize_file = found
        update, message = _media_update(voice=Media())
        asyncio.run(bot_main.recognize_media_handler(update, _context()))
        reply = message.replies[0]
        assert "Faded" in reply.text
        assert buttons(reply.keyboard)[0].callback_data.startswith("recog:")

        song_recognition.recognize_file = nothing
        update, message = _media_update(video_note=Media())
        asyncio.run(bot_main.recognize_media_handler(update, _context()))
        assert not buttons(message.replies[0].keyboard)[0].callback_data.startswith("recog:")

        song_recognition.recognize_file = broken
        update, message = _media_update(video=Media())
        asyncio.run(bot_main.recognize_media_handler(update, _context()))
        assert message.replies, "a recognizer outage must get an answer, not an exception"

        big = Media()
        big.file_size = song_recognition.MAX_FILE_BYTES + 1
        song_recognition.recognize_file = found
        update, message = _media_update(video=big)
        asyncio.run(bot_main.recognize_media_handler(update, _context()))
        assert len(message.replies) == 1 and "Faded" not in message.replies[0].text

        # A pending prompt owns the next message.
        update, message = _media_update(voice=Media())
        context = _context()
        bot_main.set_await_input(context, "search")
        asyncio.run(bot_main.recognize_media_handler(update, context))
        assert not message.replies
    finally:
        song_recognition.recognize_file = real


def check_gift_link_via_start():
    db = bot_main.user_manager.database
    _, _, result = bot_main.payments.apply_purchase(
        db, "3001", bot_main.payments.KIND_GIFT_WEEKLY, 75, "XTR", "start_charge",
    )
    message = FakeMessage(text="/start")
    update = SimpleNamespace(
        message=message, effective_message=message, effective_user=_user("3002"),
        effective_chat=SimpleNamespace(id=3002),
    )
    context = _context()
    context.args = [f"gift_{result['code']}"]

    async def no_sync(*a, **k):
        return None

    real = bot_main._sync_commands_lang
    bot_main._sync_commands_lang = no_sync
    try:
        asyncio.run(bot_main.start(update, context))
    finally:
        bot_main._sync_commands_lang = real
    assert message.replies and "✅" in message.replies[0].text
    assert bot_main.entitlements.resolve_tier(db, "3002")[0] == "premium"


def check_paysupport_needs_no_channel_and_reaches_admin():
    captured = {}
    real_create, real_submit = (
        bot_main.error_report.create_context, bot_main.error_report.submit_and_notify,
    )

    def fake_create(db, user, **kw):
        captured.update(kw)
        return 1

    async def fake_submit(bot, db, rid, user):
        return "ok", None

    bot_main.error_report.create_context = fake_create
    bot_main.error_report.submit_and_notify = fake_submit
    try:
        message = FakeMessage(text="/paysupport")
        update = SimpleNamespace(
            message=message, effective_message=message, effective_user=_user("3003"),
            effective_chat=SimpleNamespace(id=3003),
        )
        context = _context()
        asyncio.run(bot_main.paysupport_command(update, context))
        assert bot_main.peek_await_input(context)["kind"] == "paysupport"

        message.text = "I paid and got nothing"
        asyncio.run(bot_main.consume_await_input(update, context))
        assert captured["kind"] == "payment"
        assert captured["user_message"] == "I paid and got nothing"
        assert len(message.replies) == 2
    finally:
        bot_main.error_report.create_context = real_create
        bot_main.error_report.submit_and_notify = real_submit


def check_new_commands_and_handlers_are_listed():
    import bot_commands
    public = dict(bot_commands.PUBLIC_COMMANDS)
    admin = dict(bot_commands.ADMIN_COMMANDS)
    for name in ("mix", "gift", "terms", "paysupport"):
        assert name in public and name not in admin
    for name in ("refund", "payments"):
        assert name in admin and name not in public


def main():
    for name, check in sorted(globals().items()):
        if name.startswith("check_"):
            check()
    print("feature checks OK")


if __name__ == "__main__":
    main()
