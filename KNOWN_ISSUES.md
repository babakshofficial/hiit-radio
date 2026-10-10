# Known issues — HIIT Radio bot

Open problems backed by evidence: submitted user error reports (`user_error_reports` in `hiit_radio.db`), `journalctl --user -u hiit-radio` logs, or code reading. Nothing goes on this list without evidence.

Last reviewed: 2026-10-10 (all 69 rows; 18 submitted).

Status values: `open`, `fix in draft PR #N` (not merged/deployed), `config` (not a code bug), `monitor` (historical; not seen recently, not re-verified — **not** for automatic fixing), `blocked: <reason>`.

Language = the reporting user's current `users.language` setting.

## All submitted reports (full history from `user_error_reports`)

Every row with `submitted_at` set, grouped by root cause. Unsubmitted rows (62, 66, 68, 69 and older drafts) are only cited as extra evidence inside issues.

| Report | Date (Tehran) | Lang | error_kind / code | Track / query | Root-cause group | Status |
|---|---|---|---|---|---|---|
| #1 | 2026-08-22 | fa | download / drm | Stop Beating on My Heart — Tigercub (Apple) | KI-8 | monitor |
| #2 | 2026-08-22 | fa | download / drm | Stop Beating on My Heart — Tigercub (Apple) | KI-8 | monitor |
| #6 | 2026-08-22 | fa | download / bot_check | Stop Beating on My Heart — Tigercub (Apple) | KI-8 | monitor |
| #19 | 2026-08-25 | fa | metadata / not_found | Apple `lifeforce/1762787830` | KI-10 | monitor |
| #20 | 2026-08-25 | fa | download / unknown | Heart's Enigma — AL3 (Apple) | KI-5 | open |
| #22 | 2026-08-25 | fa | mismatch / wrong_track | ghost (feat. HUMAN) [Alex Wann Remix] — Aaron Hibell | KI-9 | monitor |
| #23 | 2026-08-25 | fa | mismatch / wrong_track | Summertime DJ Jazzy Jeff and The Fresh Prince (free text) | KI-9 | monitor |
| #26 | 2026-09-03 | fa | mismatch / wrong_track | Loser — Tame Impala (Apple) | KI-9 | monitor |
| #40 | 2026-09-06 | fa | mismatch / wrong_track | HOW STRONG IS YOUR LOVE RH0NIQ (free text) | KI-9 | monitor |
| #44 | 2026-09-06 | fa | discover / llm_error | /discover | KI-7 | config (401) + open (key in logs) |
| #52 | 2026-09-16 | fa | mismatch / wrong_track | Neverender — Justice & Tame Impala (Apple) | KI-9 | monitor |
| #53 | 2026-09-16 | fa | mismatch / wrong_track | Neverender — Justice & Tame Impala (Apple) | KI-9 | monitor |
| #56 | 2026-09-16 | fa | mismatch / wrong_track | Neverender — Justice & Tame Impala (Apple) | KI-9 (cache) | monitor |
| #58 | 2026-09-16 | fa | mismatch / wrong_track | Neverender — Justice & Tame Impala (Apple) | KI-9 (cache) | monitor |
| #63 | 2026-10-07 | fa | download / no_match | Tik taak na dige na kensiw remix | KI-1, KI-2 | fix in draft PR #2 / open |
| #64 | 2026-10-07 | en | download / no_match | Tik taak na dige na kensiw remix | KI-1, KI-2 | fix in draft PR #2 / open |
| #65 | 2026-10-08 | fa | download / no_match | Mahshid — Yonatan Riklis (free text) | KI-4 | open |
| #67 | 2026-10-10 | en | mismatch / wrong_track | The Center of the Universe — Delorians (Apple) | KI-3 | open |

---

## Open

### KI-1 — Version words (remix / live / cover / slowed / sped up / extended…) parsed as the artist
- **Status:** fix in draft PR #2 (`fix/search-remix-not-artist`, commit 44a42ec). Not merged, not deployed.
- **Source reports:** #63 (submitted), #64 (submitted); unsubmitted repeats #62, #68, #69.
- **Symptoms:** Free-text `Tik taak na dige na kensiw remix` → `Plain-query fallback metadata: 'Tik taak na dige na kensiw' by 'remix'`. Every search ends in `no_match` ("No full version found…"). Same for `Tik taak na dige na afrohouse remix` (2026-10-10 12:55 and 12:58).
- **Root cause:** `metadata.guess_title_artist()` uses the last word as the artist, so `remix` becomes the artist. In `downloader.MusicDownloader.download_song()`, the artist gate (`presence < 55 and artist_sim < 55` → reject) then drops real uploads. `_has_noise()` also rejects remix uploads, because "remix" is not in the expected title and `_required_version_tokens()` only reads bracketed groups.
- **Files:** `metadata.py` (`guess_title_artist`, `TrackMetadata.create` plain-text branch); `downloader.py` (`_has_noise`, `_required_version_tokens`, `score()` inside `download_song`).
- **Fix (PR #2):** `split_version_descriptor()` strips trailing version words and bracket groups, then re-attaches them to the title as `(remix)`. The iTunes plain-text lookup also retries without the version words.
- **Known gap:** genre words are not version words. With PR #2, `… afrohouse remix` becomes title `… (remix)` with artist `afrohouse`, which is still wrong (see KI-2).
- **Verify:** after deploy, send `Tik taak na dige na kensiw remix`. The log should show `Plain-query fallback metadata: 'Tik taak na dige na (remix)' by 'kensiw'`, never `by 'remix'`. Run the unit cases for `guess_title_artist` / `split_version_descriptor` locally (note that `tests/` is gitignored).

### KI-2 — Finglish / free-text searches take the last word as the artist
- **Status:** open.
- **Source reports:** #63, #64, #68, #69 (same user flow). Log 2026-10-10 12:50: `'Tik taak na dige' by 'na' (from 'Tik taak na dige na')`.
- **Symptoms:** When iTunes has no hit (common for Persian songs typed in Latin script), the fallback guesses `title = all but last word`, `artist = last word`. The fake artist then only matches by luck. On 12:50 the download worked only because every candidate scored `Artist 50%` and the title alone carried it. A different last word (e.g. `kensiw`, `afrohouse`) leads to `no_match`.
- **Root cause:** `metadata.guess_title_artist()`'s default "song words … artist" heuristic is applied with no confidence signal. The downloader's artist gate treats the guessed artist as known (`(metadata.artist or "").strip()`).
- **Files:** `metadata.py` (`guess_title_artist`, `TrackMetadata.create` → `meta.type = "search"`); `downloader.py` (`download_song` → `score()` artist gate, `sc_search_strategies`).
- **Suggested fix:** when `metadata.type == "search"` (plain-query fallback, artist is only a guess), don't hard-reject on the artist gate. Score candidates on whole-query coverage (`query_coverage`) plus title tokens instead. Alternatively, mark the guessed artist as `artist_guess` and leave `artist` empty for gating. Optionally add a small list of genre words (afrohouse, house, techno, lofi, trap, …) that are never artists.
- **Verify:** `Tik taak na dige na afrohouse remix` and `Tik taak na dige na kensiw remix` should find a `Tik Taak … Na Dige Na` upload. Catalog-link matches must not regress (re-test #67 and the Neverender case).

### KI-3 — YouTube matcher accepts a similar-named artist when the title is exact (catalog links)
- **Status:** open (Babak: no branch yet).
- **Source reports:** #67 (`wrong_track`, Apple link `…/6799234014?i=6799234017`).
- **Symptoms:** Apple track "The Center of the Universe" by **Delorians** (202 s). Log 2026-10-10 12:28: `Candidate: Title 100.0%, Artist 70.0%, Coverage 66.7%, Combined 90.9% | 'Center of the Universe' by 'Deradoorian'` → downloaded. Catalog tags were then written on top ("Keeping catalog tags…"), so the file *looks* right but the audio is wrong.
- **Root cause (as understood):** in `downloader.MusicDownloader.download_song()`, the catalog coverage gate (`coverage_gate = 80` when `had_catalog`) is only enforced when `title_sim < TITLE_THRESHOLD`. A 100% title skips it, so 66.7% coverage passes. Fuzzy `_uploader_artist_match()` gives 70% for Delorians vs Deradoorian, which clears the 55% artist gate, and the 0.7 title / 0.3 artist weighting gets the total to 90.9%.
- **Files:** `downloader.py` — `score()` and the ranking loop in `download_song` (around `if title_sim < TITLE_THRESHOLD and coverage < coverage_gate`), `_uploader_artist_match`, `_artist_presence`.
- **Suggested fix:** for catalog links (`had_catalog`), require `artist_sim >= ~85` (or exact primary-artist token match) unless Topic/VEVO, and apply `coverage_gate` regardless of `title_sim`. Consider using `expected_duration` as a hard gate (±15%) for catalog links when the candidate duration is known.
- **Verify:** re-run the #67 Apple link. Deradoorian must be rejected and the result is either the real Delorians upload or `no_match`. Invalidate the cache for that title+artist first (`CacheManager.invalidate_track`). Re-test earlier catalog links that work today (e.g. Neverender, Faded Eyes) so nothing regresses.

### KI-4 — Tracks that aren't on YouTube/SoundCloud get the generic "try a different name" message
- **Status:** open.
- **Source reports:** #65 ("Mahshid" — Yonatan Riklis, from the *Reading Lolita in Tehran* score; on Apple Music but no YouTube/SoundCloud candidates at all, 2026-10-08 03:34). Possibly #18/#45 ("Basslines Under Control" — Qloom); not re-verified.
- **Symptoms:** all 5 YouTube strategies and SoundCloud return zero eligible candidates (`Best eligible: n/a`). The user is told "No full version found — searching under a different name might help", even though their query was correct.
- **Root cause:** `messages.download_fail_message()` maps every `no_match` to `download_not_found`. There's no difference between "nothing found anywhere" and "candidates found but rejected".
- **Files:** `downloader.py` (`download_song` return codes at the "No candidate passed validation" branch), `messages.py` (`download_fail_message`), `locales/*.py` (`download_not_found`).
- **Suggested fix:** return a distinct code (e.g. `not_available`) when there are no raw search results or no eligible candidates for a catalog-identified track (iTunes/Deezer hit exists). Add a localized message like "This track isn't available on our sources yet; if you have a YouTube/SoundCloud link, send it directly."
- **Verify:** request `Mahshid Yonatan Riklis` and check that the new message appears in both en and fa. Check that a real mismatch case still says "try a different name".

### KI-5 — Network / format / probe failures reported as `unknown` and shown as "No full version found"
- **Status:** open.
- **Source reports:** #20 (submitted, 2026-08-25, Heart's Enigma — AL3: `Best YouTube match 88.0%` then `Requested format is not available` for two candidates → `unknown`); #66 (Grim Velocity — Threnqelia, never submitted, `cookies_ok: false`, `timeout after 20s (auth=cookiefile)`). Same pattern in #59, #60 (Neverender, `unknown`, 20 s timeout) and #57 (`send_failed`, 20 s timeout).
- **Symptoms:** log 2026-10-10 11:08: `Download of YouTube match failed (unknown) … [Errno 101] Network is unreachable`, then `yt_worker probe no formats` → `YouTube worker failure under proxychains — retrying without LD_PRELOAD` → `YouTube worker timeout after 20s (auth=cookiefile)` twice. Error code `unknown`; user sees "No full version found…".
- **Root cause:** `_classify_error()` inside `download_song()` doesn't recognise network errors or `Requested format is not available` (#20) ("network is unreachable", proxy/SSL errors). `_is_network_probe_error()` already lists them but isn't used there, so they fall through to `unknown`, and `download_fail_message("unknown")` reuses `download_not_found`. The 20 s worker timeout is likely the proxy/network path, not the cookies.
- **Files:** `downloader.py` (`_classify_error` in `download_song`, `_is_network_probe_error`, yt_worker timeout around `last_err = f"timeout after {timeout}s (auth={auth})"`); `messages.py` (`download_fail_message`); `main.py` (report context `cookies_ok` / `cookies_detail`).
- **Suggested fix:** in `_classify_error`, return `"network"` (or `"timeout"`) when `_is_network_probe_error(err)` is true. Map it to a "connection problem, please try again in a minute" message, and don't count it as cookie failure in reports.
- **Verify:** simulate by pointing the proxy at a dead port (local only) or unit-test `_classify_error` with the logged error string. Expect code `network`/`timeout` and the matching message, not `unknown`.

### KI-6 — `WEBAPP_URL` is not HTTPS, so the Telegram Mini App menu button is skipped
- **Status:** config (not a code bug).
- **Source:** log on every start, e.g. 2026-10-10 12:46 and 13:02: `WEBAPP_URL is not HTTPS (http://127.0.0.1:3000) — skipping Mini App menu button`.
- **Files:** `api/webapp_menu.py`, `api/config.py` (default `http://127.0.0.1:3000`).
- **Suggested fix:** set `WEBAPP_URL` to a public HTTPS domain in `.env` when the Mini App should be live, or leave it empty for local dev to silence the log. No code change needed.
- **Verify:** after restart the log shows the menu button being set (no "not HTTPS" line).

---

### KI-7 — /discover LLM call failed with HTTP 401, and the error log prints the full LLM URL (contains a credential)
- **Status:** 401 = config (provider auth), not re-verified since 2026-09-06. URL logging = open (security hygiene).
- **Source reports:** #44 (submitted, 2026-09-06, fa, discover / llm_error); unsubmitted #43, #46.
- **Symptoms:** log 2026-09-06 21:55: `llm_service - ERROR - LLM API 401 model='GPT-OSS-20B' url=https://arvancloudai.ir/gateway/models/GPT-OSS-20B/<long token>…`. The gateway URL path carries a secret-looking token, and it is written to the journal in plain text.
- **Root cause:** the 401 is a rejected or expired LLM credential (config). The leak comes from `llm_service.py` error logs that format the full `url` (lines ~253, ~365, ~457: `LLM API … url=…`).
- **Files:** `llm_service.py` (error logging in the chat / similar / third LLM call paths).
- **Suggested fix:** log only the host plus model (e.g. `urllib.parse.urlsplit(url).netloc`) or redact path segments longer than ~20 chars. Rotate the LLM key if journal logs were ever shared. Check `.env` LLM settings by hand; agents must not print them.
- **Verify:** force a 401 (bad key in a local test env) and confirm the log line has no token. Run `/discover` and check that it answers.

### KI-8 — YouTube bot-check plus SoundCloud DRM left catalog tracks undownloadable (Aug)
- **Status:** monitor. Since the cookie work on 2026-08-23 (`d87c40a` live-probe cookie health, `7dde582`) and 2026-09-16 (`df816c3`, `33c772c`), recent reports show `live probe OK`. Not re-verified for this track.
- **Source reports:** #1, #2 (download / drm), #6 (download / bot_check), all 2026-08-22, fa. Unsubmitted #3–#5, #7–#17, #25 for the same track.
- **Symptoms:** `Sign in to confirm you're not a bot` on every YouTube candidate, then the SoundCloud fallback `1069996387: This video is DRM protected`. Since `drm` was the last error, the user saw DRM.
- **Root cause:** expired or unusable YouTube cookies (bot check), and the only SoundCloud upload is DRM-protected.
- **Files:** `downloader.py` (cookie probe / `youtube_auth_ok`, SoundCloud fallback ordering), `cred_status.py`, `check_creds.sh`.
- **Suggested fix:** none needed now; reopen if bot_check reports return. When YouTube is bot-blocked and SoundCloud is DRM-only, report `bot_check` (the real cause) rather than `drm`.
- **Verify:** request the Tigercub Apple link with good cookies; it should download from YouTube.

### KI-9 — Wrong track: SoundCloud remix/flip/fan uploads accepted, then hidden behind catalog tags and cached (Aug–Sep)
- **Status:** monitor. Later gates likely cover it: `_required_version_tokens` (its docstring cites the #22 case), `_NOISE_PATTERNS` with `flip`/`remix`, "Prefer official YouTube over SoundCloud flips/remixes" in `download_song`, and cache invalidation on mismatch reports (log 2026-10-10 12:30 `Cache invalidated track` right after #67). Not re-verified per track. KI-3 is the open, still-reproducing member of this family.
- **Source reports:** #22, #23 (2026-08-25), #26 (2026-09-03), #40 (2026-09-06), #52, #53, #56, #58 (2026-09-16). All fa, mismatch / wrong_track.
- **Symptoms (logs):**
  - #22: `Best SoundCloud match 68.2% — 'Aaron Hibell feat. Alex Wann - Set Me Free (Dealex Remix)'` downloaded for *ghost [Alex Wann Remix]*, even though YouTube had `Early accept at 100.0%`.
  - #23: SoundCloud fan upload `summertime-high-quality` (86.8%) chosen over YouTube 100%.
  - #26: SoundCloud `'Loser     - Tame Impala .mp3'` (82.5%) chosen over YouTube 100%.
  - #40: SoundCloud `How strong is your love (feat. Luis Daniel)` (DRM) then `RH0NIQ` upload.
  - #52/#53: SoundCloud `Neverender (Mersiv Flip)` at 100% chosen.
  - #56/#58: `Cache hit: Neverender — Justice & Tame Impala`, so the wrong flip was served from cache after the report.
  - Every one logged `Keeping catalog tags …`, so file tags looked correct.
- **Root cause:** SoundCloud candidates were tried before or instead of a 100% YouTube match. Remix/flip and fan uploads weren't gated, and wrong audio stayed in cache after a mismatch report.
- **Files:** `downloader.py` (`download_song` source ordering/download queue, `_has_noise`, `_required_version_tokens`), `cache_manager.py` (`invalidate_track`), `main.py` (mismatch report handler).
- **Suggested fix:** if any of these reappears, prefer the higher-scoring YouTube candidate over SoundCloud for catalog links, and reject SoundCloud uploads whose uploader doesn't match the artist (same idea as KI-3).
- **Verify:** re-request each listed Apple link / query after invalidating its cache. The audio should be the original track (check the duration against iTunes `trackTimeMillis`).

### KI-10 — Apple metadata fetch failed: `music.apple.com` unreachable (Aug)
- **Status:** monitor (environmental / network).
- **Source reports:** #19 (2026-08-25, fa, metadata / not_found).
- **Symptoms:** log 2026-08-25 08:24: `Error fetching meta: Cannot connect to host music.apple.com:443 … [Network is unreachable]` → `Apple Music metadata extraction failed` → user told "not found".
- **Root cause:** network/proxy outage on the host, reported to the user as `not_found`.
- **Files:** `metadata.py` (`AppleMusicMetadata.fetch`, `TrackMetadata.create`), `main.py` (metadata error report).
- **Suggested fix:** classify connection errors as `network` and tell the user to retry, as in KI-5.
- **Verify:** unit-test the classification with the logged error string.

---

## How to add an issue

1. Find evidence first: a `user_error_reports` row (`id`, `error_kind`, `error_code`, `context_json`) and/or the matching `journalctl --user -u hiit-radio` lines around `created_at`. No evidence, no entry.
2. Add a `### KI-N — short title` section under **Open** using the next free number. Fill in **Status**, **Source reports**, **Symptoms** (quote the log line), **Root cause** (say "as understood" if unconfirmed), **Files**, **Suggested fix**, and **Verify**.
3. If a fix is attempted but blocked, set `Status: blocked: <reason>` and keep the item under Open.
4. Never paste secrets, cookies, tokens, or `.env` values here.

## Fixed

Move an item here when its fix is merged (or committed to the deployed branch). Keep the KI number and add: date, commit/PR, and how it was verified.

_(none yet)_
