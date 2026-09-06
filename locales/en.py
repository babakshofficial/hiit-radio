"""English (en) locale strings for the HiiT Radio bot."""

STRINGS = {
    # --- generic ---
    "unknown": "Unknown",

    # --- platforms ---
    "platform_spotify": "Spotify",
    "platform_apple": "Apple Music",
    "platform_youtube": "YouTube",
    "platform_soundcloud": "SoundCloud",
    "platform_deezer": "Deezer",
    "platform_cache": "Cache",

    # --- download buttons ---
    "btn_redownload": "🔄 Download again: {label}",
    "btn_download_indexed": "{index}. Download “{label}”",
    "btn_download": "Download “{label}”",

    # --- start / help / about ---
    "start_friend_name": "friend",
    "start_text": (
        "Hi {name}! 🎶\n\n"
        "Welcome to HiiT Radio — the unlimited music download bot!\n\n"
        "Just send a track, album or playlist link "
        "(Spotify · Apple Music · Deezer · YouTube · SoundCloud) "
        "or type a song name — I'll take care of the rest.\n\n"
        "Start with the buttons below 👇"
    ),
    "help_text": (
        "How do I use this?\n\n"
        "1. Send a track, album or playlist link\n"
        "   (Spotify · Apple Music · Deezer · YouTube · SoundCloud)\n"
        "2. Or type a song and artist name\n"
        "3. Use the buttons below for search, artists, quality, and more\n"
        "4. Or inline: {bot_inline} song name — in any chat\n\n"
        "Free daily limit: 10 downloads (premium: {premium_daily_limit})."
    ),
    "aboutme_text": (
        "🎙 About HiiT Radio\n"
        "\n"
        "I'm {developer_name}, and I built this bot to make downloading music easier.\n"
        "\n"
        "📻 Channel: {channel}{developer_line}\n"
        "\n"
        "What can it do?\n"
        "• Spotify / Apple / Deezer / YouTube / SoundCloud links\n"
        "• Search and browse artists from the menu buttons\n"
        "• Set audio quality from the menu\n"
        "• Personal recommendations from Discover\n"
        "\n"
        "Got an idea or found a bug? Send me a message — I'd love to hear it 😊"
    ),
    "aboutme_developer_line": "\n💬 Developer: {username}",

    # --- history ---
    "history_empty": "You haven't downloaded anything yet — send a track and it'll show up here 🎧",
    "history_header": "📜 Your recent downloads:\n",

    # --- discover ---
    "discover_empty_history": (
        "For personal recommendations, download a few tracks first — then hit /discover 🎧"
    ),
    "discover_not_configured": (
        "Smart recommendations aren't available right now.\nPlease try again soon."
    ),
    "discover_preparing": "⏳ Putting together some recommendations...",
    "discover_llm_phase": "Thinking about your taste...",
    "discover_resolve_phase": "Finding the tracks ({done}/{total})...",
    "discover_llm_error": "I couldn't come up with recommendations right now — try again in a bit 🙏",
    "discover_no_results": "No fresh recommendations for now — try again later.",
    "discover_header": "🎧 Picked for you:\n",

    # --- cancel / jobs ---
    "cancel_ok": "⏹ Stop request received — the current job will stop shortly.",
    "cancel_ok_many": "⏹ Stop request received for {count} jobs — they'll stop shortly.",
    "cancel_no_job": "You don't have any active job running right now.",
    "too_many_jobs": (
        "You can't run more than {limit} jobs at the same time.\n"
        "Wait for them to finish or stop one with /cancel."
    ),
    "download_cancelled": "Stopped.",
    "work_cancelled": "Job cancelled.",

    # --- preview ---
    "preview_caption": "🎧 30-second preview",
    "preview_caption_title": "🎧 30-second preview\n{title}",
    "preview_caption_full": "🎧 30-second preview\n{title} — {artist}",

    # --- quota / tiers ---
    "rate_limit": "You've hit the download limit for now — come back in {minutes} minutes 🙏",
    "tier_free": "Free",
    "tier_premium": "Premium",
    "tier_unlimited": "Unlimited",
    "quota_exceeded": (
        "You've reached today's download limit ({used}/{limit}) — plan: {tier}.\n"
        "You can raise today's limit with Telegram Stars, "
        "get premium, or invite 3 friends."
    ),

    # --- premium status ---
    "premium_status_title": "⭐ Subscription status",
    "premium_plan": "Plan: {tier}",
    "premium_expires": "Expires: {expires}",
    "premium_limit_unlimited": "Today's limit: unlimited",
    "premium_limit_today": "Downloads today: {used}/{limit}",
    "premium_day": "Date: {day}",
    "premium_footer": (
        "Day pass: +{topup} downloads | Weekly/monthly premium: {premium_daily} per day"
    ),

    # --- invite / referral ---
    "invite_status": (
        "🎁 Invite a friend\n"
        "Progress: {toward}/{needed} (total confirmed: {credited})\n"
        "Waiting for channel join: {pending}\n\n"
        "For every 3 new friends who join through your link and subscribe to the channel, "
        "you get +{topup} downloads today.\n\n"
        "Invite link:\n{link}"
    ),
    "referral_topup_granted": (
        "🎉 Three invites completed — +{amount} downloads were added to your account today.\n"
        "Check your next milestone with /invite."
    ),

    # --- payments ---
    "payment_failed": "The payment didn't go through — try again from /premium.",
    "payment_already_processed": "This payment has already been applied.",
    "payment_bonus_ok": "✅ +{amount} downloads activated for today ({day}).",
    "payment_premium_ok": "✅ Your {tier} subscription is active until {expires}.",
    "btn_buy_daypass": "🔓 +{amount} downloads today — {stars}⭐",
    "btn_buy_weekly": "⭐ 7-day premium — {stars}⭐",
    "btn_buy_monthly": "⭐ 30-day premium — {stars}⭐",
    "btn_invite": "🎁 Invite a friend",

    # --- admin grants ---
    "grant_ok": "✅ User {user_id}: {tier} until {expires}",
    "topup_ok": "✅ User {user_id}: +{amount} for {day}",
    "grant_user_notice": (
        "🎁 You received {days} days of {tier}, active until {expires}.\n"
        "Send a song whenever you like."
    ),
    "topup_user_notice": (
        "🎁 +{amount} extra downloads were added to your account for today ({day})."
    ),
    "grant_notify_failed": (
        "⚠️ Could not message the user — they may need to tap Start on the bot first."
    ),

    # --- download flow ---
    "searching": "⏳ Looking for your track...",
    "downloading": "⏳ Downloading...",
    "metadata_not_found": "Nothing found — send the link or song name again 🙏",
    "not_music_query": "That doesn't look like a song name — send a music link or “artist - track”",
    "collection_not_found": (
        "I couldn't recognise this album or playlist — check the link and send it again."
    ),
    "send_failed": "I couldn't send the track — please try again 🙏",
    "download_not_found": "No full version found — searching under a different name might help.",
    "download_fail_bot_check": (
        "The download failed right now — try again in a bit or send a different name."
    ),
    "download_fail_timeout": "The download took too long and was cut off — please try again 🙏",
    "download_fail_invalid": "The file didn't download properly — try another link or name.",
    "record_not_found": "This item wasn't found in your history.",
    "songs_not_found": "No tracks found — try a different name.",

    # --- similar ---
    "similar_preparing": "⏳ Looking for similar tracks...",
    "similar_llm_phase": "Finding similar tracks...",
    "similar_resolve_phase": "Preparing the list ({done}/{total})...",
    "similar_header": "🎧 Similar to “{title}”:\n",
    "similar_header_with_artist": "🎧 Similar to “{title} — {artist}”:\n",
    "similar_not_found": "No similar tracks found — try again later.",
    "nearby_header": "🎧 Close to “{title}” — pick one:\n",
    "nearby_header_with_artist": "🎧 Close to “{title} — {artist}” — pick one:\n",

    # --- favorites ---
    "liked_empty": "You haven't added anything to your favorites yet ❤️",
    "liked_header": "❤️ Your favorites:\n",
    "favorite_added": "Added to favorites: {title}",
    "favorite_removed": "Removed from favorites: {title}",
    "favorite_missing": "This track wasn't found for favoriting.",

    # --- top ---
    "top_header": "🏆 Most popular ({period}):\n",
    "top_empty": "No stats for this period yet.",
    "top_period_day": "24 hours",
    "top_period_week": "week",
    "top_period_all": "all time",

    # --- lyrics / artwork ---
    "lyrics_not_found": "No lyrics found for this track.",
    "lyrics_header": "📝 {title}\n\n",
    "lyrics_header_with_artist": "📝 {title} — {artist}\n\n",
    "artwork_not_found": "No artwork found for this track.",
    "artwork_sending": "Preparing the artwork...",

    # --- picks / inline ---
    "pick_expired": "This selection has expired — please search again.",
    "pick_expired_short": "This selection has expired — please try again.",
    "more_by_artist": "🎵 More tracks by {artist}:\n",
    "inline_description": "{artist} — tap to download",

    # --- channel gate ---
    "gate_denied": (
        "To use the bot, please join the @{channel} channel first 🙏\n\n"
        "https://t.me/{channel}\n\n"
        "Once you've joined, try again."
    ),
    "gate_alert": "Join the channel first.",

    # --- playlists ---
    "playlist_empty": "No tracks found in this collection.",
    "playlist_default_name": "Playlist",
    "playlist_start": (
        "📋 Starting download: {name}\n"
        "Tracks: {total}\n\n"
        "/cancel to stop the current job"
    ),
    "playlist_cancelled": "Stopped. Sent: {sent}/{total}",
    "playlist_rate_limited": "Rate limited ({minutes} minutes). Sent: {sent}/{total}",
    "playlist_summary": "Sent: {sent}/{total}",
    "playlist_summary_failed": "Sent: {sent}/{total} | Failed: {failed}",
    "playlist_zip_sending": "📦 Building the ZIP ({count} tracks) — {name}...",
    "playlist_zip_caption": "📦 {name} — {count} tracks",

    # --- progress ---
    "progress_update": "📥 {label} {bar} {pct}%{counter}{detail_line}{eta_line}",
    "progress_counter": " — track {current} of {total}",
    "progress_eta": "\n⏳ about {m}:{s:02d}",
    "progress_done": "✅ {label} finished.",
    "progress_done_with_summary": "✅ {label} finished.\n{summary}",
    "progress_fail": "❌ {label} failed.",
    "progress_fail_with_reason": "❌ {label} failed.\n{reason}",

    # --- error reporting ---
    "error_report_button": "📩 Report to support",
    "error_retry_button": "🔄 Try again",
    "error_retrying": "🔄 Trying again...",
    "error_retry_unavailable": (
        "This error can't be retried — send the link or song name again."
    ),
    "error_report_sent": "\n\n✅ Your report was sent. Thanks!",
    "error_report_already_sent": "This error has already been reported.",
    "error_report_rate_limited": "Report limit reached — try again tomorrow.",

    # --- support chat ---
    "support_admin_prompt": (
        "Reply mode active — report #{report_id} (user {user_id})\n"
        "Any message you send goes straight to the user.\n"
        "End the conversation: /supportend"
    ),
    "support_user_message": (
        "📩 Message from HiiT Radio support\n\n"
        "{admin_text}\n\n"
        "To reply: /support your message"
    ),
    "support_user_opened": (
        "Support got in touch about your error report.\n"
        "Use /support to reply — all other messages still work for downloading music."
    ),
    "support_user_closed": (
        "The support conversation has ended. If you still have trouble, send another report."
    ),
    "support_no_thread": (
        "You don't have an active support conversation.\n"
        "First use the “📩 Report to support” button on an error message; "
        "once support replies you can send messages with /support."
    ),
    "support_usage": (
        "Usage: /support your message\n"
        "It only works once support has replied to your error report."
    ),
    "support_admin_usage": (
        "You are an admin.\n"
        "• Hit “Reply” on an error report, then any text message goes to the user\n"
        "• End: /supportend"
    ),
    "support_empty_message": "Empty message — write some text after /support.",
    "support_sent_admin": "✅ Message sent to user {user_id}.",
    "support_sent_user": "✅ Your message reached support.",
    "support_forward_to_admin": (
        "💬 User reply ({user_label}) — report #{report_id}\n\n{text}"
    ),
    "support_send_failed_blocked": "Send failed — the user has blocked the bot.",
    "support_send_failed": "Send failed — try again later.",
    "support_thread_ended_admin": "Conversation #{thread_id} closed.",
    "support_thread_ended_no_open": "There is no open conversation.",
    "support_reply_button": "💬 Reply to user",
    "support_end_button": "⏹ End conversation",
    "support_report_not_found": "Report not found or not submitted yet.",

    # --- cookies (admin) ---
    "cookies_status_title": "🍪 YouTube cookie status",
    "cookies_state_ok": "healthy",
    "cookies_state_bad": "unhealthy",
    "cookies_status_state": "Status: {state}",
    "cookies_status_detail": "Details: {detail}",
    "cookies_status_path": "Path: {path}",
    "cookies_status_updated": "Last update: {updated}",
    "cookies_status_footer": (
        "To update, send the cookies.txt file here as a document "
        "(Netscape export from a browser logged into youtube.com)."
    ),
    "cookies_accepted": "✅ cookies.txt updated.\nDetails: {detail}",
    "cookies_accepted_backup": "\nThe previous version was saved to cookies.txt.bak.",
    "cookies_rejected": (
        "❌ This cookie file isn't valid and wasn't saved.\n"
        "Details: {detail}\n\n"
        "Export it again in Netscape format while logged into youtube.com."
    ),
    "cookies_too_large": "❌ The file is too large (over {limit_kb} KB).",

    # --- track action buttons ---
    "btn_more_by_artist": "More tracks",
    "btn_similar": "Similar tracks",
    "btn_lyrics": "Lyrics",
    "btn_artwork": "🖼 Artwork",
    "btn_report_track": "⚠️ Report issue",
    "track_report_sent": "✅ Thanks — your report was sent to support.",
    "track_report_user_message": "User reported this track (wrong song / mismatch / other issue).",
    "btn_favorite_add": "❤️ Favorite",
    "btn_favorite_remove": "💔 Remove favorite",

    # --- search ---
    "prompt_search": "🔍 Send a song or artist name to search:",
    "prompt_artist": "🎙 Send the artist name:",
    "prompt_follow": "🔔 Send the artist name to follow:",
    "prompt_support": "💬 Write your message for support:",
    "prompt_cancelled": "⏹ Input cancelled.",
    "search_usage": "Usage:\n/search song or artist name",
    "search_empty": "Nothing found — try a different phrase.",
    "search_header": "🔍 Search results for “{query}”:",
    "search_hit_line": "{index}. [{kind}] {name}{sub}",
    "search_kind_track": "Track",
    "search_kind_album": "Album",
    "search_kind_playlist": "Playlist",
    "search_kind_artist": "Artist",

    # --- artist ---
    "artist_usage": "Usage:\n/artist artist name",
    "artist_not_found": "Artist “{name}” not found.",
    "artist_header": "🎤 {name}",
    "artist_top_header": "Top tracks:",
    "artist_albums_header": "Albums:",

    # --- quality ---
    "quality_hint_128": "Small files — good for tight storage",
    "quality_hint_192": "Balanced — good quality",
    "quality_hint_256": "Bot default",
    "quality_hint_320": "Best MP3",
    "quality_hint_original": "No conversion — the source file as is",
    "quality_status_kbps": "🎚 Current quality: {value} kbps",
    "quality_status_original": "🎚 Current quality: original (no conversion)",
    "quality_status_footer": "Tap one of the buttons below.",
    "quality_set_kbps": "✅ Quality set to {value} kbps.",
    "quality_set_original": "✅ Quality set to original (no conversion).",
    "quality_invalid": "Invalid quality. Options: 128 · 192 · 256 · 320 · original",

    # --- artist follow ---
    "follow_success": "✅ Now following “{artist}” — I'll let you know when a new album drops!",
    "unfollow_success": "🔕 Unfollowed “{artist}”.",
    "already_following": "You already follow “{artist}”.",
    "not_following": "You aren't following any artists yet — tap Follow artist to start!",
    "following_header": "🎙 Artists you follow:",
    "follow_usage": "Usage:\n/follow artist name",
    "btn_follow": "🔔 Follow {artist}",
    "btn_unfollow": "🔕 Unfollow {artist}",
    "new_release_notification": (
        "🔔 New release!\n"
        "\n"
        "🎤 {artist}\n"
        "💿 {album}{date_line}\n"
        "\n"
        "Tap the button below to download the album 👇"
    ),
    "new_release_date_line": "\n📅 {date}",

    # --- main menu ---
    "menu_follow": "🔔 Follow artist",
    "menu_support": "💬 Support",
    "menu_search": "🔎 Search a track",
    "menu_artist": "🎙 Browse artist",
    "menu_quality": "🎛 Audio quality",
    "menu_help": "📚 Full guide",
    "menu_history": "🕐 Download history",
    "menu_liked": "💖 Favorites",
    "menu_top": "🔥 Most popular",
    "menu_discover": "🎯 For you",
    "menu_following": "🔔 My artists",
    "menu_invite": "🎁 Invite a friend",
    "menu_premium": "💠 Premium",
    "menu_aboutme": "🤖 About the bot",
    "menu_cancel": "⛔ Cancel current job",
    "menu_back": "🔙 Back to menu",
    "menu_lang": "🌐 Language",
    "menu_admin": "🛠 Admin",
    "menu_admin_back": "🔙 Admin panel",
    "admin_menu_text": "🛠 Admin panel — pick a tool:",
    "admin_stats": "📊 Stats",
    "admin_report": "📈 Dashboard",
    "admin_reports": "📋 User reports",
    "admin_users": "👥 Users",
    "admin_creds": "🔑 Credentials",
    "admin_cookies": "🍪 Cookies",
    "admin_export": "📤 Export",
    "admin_viplog": "🧪 VIP log",
    "admin_broadcast": "📣 Broadcast",
    "admin_channelid": "🆔 Channel ID",
    "admin_grant": "➕ Grant",
    "admin_topup": "💰 Top-up",
    "admin_broadcast_usage": "Usage: /broadcast <message>",
    "admin_grant_usage": "Usage: /grant <user_id> <premium|unlimited> <days>",
    "admin_topup_usage": "Usage: /topup <user_id> [amount]",
    "admin_channelid_usage": (
        "Forward a VIP channel post here (keep sender name),\n"
        "or send /channelid inside that channel."
    ),
    "awiz_cancel": "❌ Cancel",
    "awiz_confirm": "✅ Confirm",
    "awiz_cancelled": "Cancelled.",
    "awiz_invalid_user": "That doesn’t look like a user ID. Send a numeric ID, @username, or pick someone below.",
    "awiz_pick_user": "Who should this apply to?\nSend a user ID or @username, or tap a recent user.",
    "awiz_grant_tier": "Grant for {user} — which plan?",
    "awiz_tier_premium": "⭐ Premium",
    "awiz_tier_unlimited": "♾ Unlimited",
    "awiz_grant_days": "{user} → {tier}\nHow many days?",
    "awiz_days_7": "7 days",
    "awiz_days_30": "30 days",
    "awiz_days_90": "90 days",
    "awiz_days_custom": "Custom…",
    "awiz_grant_days_custom": "Send the number of days (e.g. 14).",
    "awiz_grant_confirm": "Grant {tier} to {user} for {days} days?",
    "awiz_topup_amount": "Top-up for {user} — how many extra downloads?",
    "awiz_amt_default": "Default ({amount})",
    "awiz_amt_custom": "Custom…",
    "awiz_topup_amount_custom": "Send the number of extra downloads.",
    "awiz_topup_confirm": "Add +{amount} downloads today for {user}?",
    "awiz_broadcast_ask": "Send the broadcast text in the next message.",
    "awiz_broadcast_empty": "Message was empty — send the text to broadcast.",
    "awiz_broadcast_confirm": "Send this to {count} users?\n\n{preview}",
    "awiz_broadcast_done": "Broadcast finished: sent={sent}, failed={failed}",
    "awiz_viplog_ask": "VIP log status:\n\n{status}\n\nSend a test message to the VIP channel?",
    "awiz_viplog_send": "🧪 Send test",
    "awiz_reports_ask": "User reports — browse the list, or send a report ID.",
    "awiz_reports_list": "📋 Browse list",
    "awiz_reports_id": "🔎 Enter ID",
    "awiz_reports_ask_id": "Send the report ID (number).",
    "awiz_reports_bad_id": "That isn’t a valid report ID. Send a number, or go back.",
    "awiz_user_ask": "Send a user ID or @username, or tap a recent user.",
    "awiz_channelid_ask": (
        "Forward a post from the VIP channel here (keep the sender name).\n"
        "Or send /channelid inside that channel."
    ),
    "awiz_channelid_need_forward": "I need a forwarded channel post. Forward one here, or cancel.",
    "awiz_export_ask": "Export the full database as JSON?",
    "awiz_export_go": "📤 Export now",

    # --- language selection ---
    "lang_choose": "🌐 Choose the bot language:",
    "lang_set": "✅ Language set to {lang_name}.",
    "lang_name_fa": "فارسی",
    "lang_name_en": "English",
    "lang_name_fr": "Français",
    "lang_name_es": "Español",
    "lang_name_ru": "Русский",
    "lang_name_it": "Italiano",
}
