"""Persian (fa) locale strings for the HiiT Radio bot."""

STRINGS = {
    # --- generic ---
    "unknown": "نامشخص",

    # --- platforms ---
    "platform_spotify": "اسپاتیفای",
    "platform_apple": "اپل موزیک",
    "platform_youtube": "یوتیوب",
    "platform_soundcloud": "ساندکلاود",
    "platform_deezer": "دیزر",
    "platform_cache": "کش",

    # --- download buttons ---
    "btn_redownload": "🔄 دانلود مجدد: {label}",
    "btn_download_indexed": "{index}. دانلود «{label}»",
    "btn_download": "دانلود «{label}»",

    # --- start / help / about ---
    "start_friend_name": "دوست عزیز",
    "start_text": (
        "سلام {name}! 🎶\n\n"
        "به HiiT Radio خوش اومدی — ربات دانلود موزیک بدون محدودیت!\n\n"
        "فقط کافیه لینک آهنگ، آلبوم یا پلی‌لیست رو بفرستی "
        "(اسپاتیفای · اپل موزیک · دیزر · یوتیوب · ساندکلاود) "
        "یا اسم آهنگ رو بنویسی — بقیه‌اش با من.\n\n"
        "از دکمه‌های زیر شروع کن 👇"
    ),
    "help_text": (
        "چطور استفاده کنم؟\n\n"
        "۱. لینک آهنگ، آلبوم یا پلی‌لیست بفرست\n"
        "   (اسپاتیفای · اپل موزیک · دیزر · یوتیوب · ساندکلاود)\n"
        "۲. یا اسم آهنگ و هنرمند رو بنویس\n"
        "۳. از دکمه‌های زیر برای جستجو، هنرمند، کیفیت و بقیه استفاده کن\n"
        "۴. یا اینلاین: {bot_inline} نام آهنگ — توی هر چتی\n\n"
        "سقف روزانه رایگان: ۱۰ دانلود (پریمیوم: {premium_daily_limit})."
    ),
    "aboutme_text": (
        "🎙 درباره HiiT Radio\n"
        "\n"
        "این ربات رو من، {developer_name}، ساختم تا راحت‌تر موزیک دانلود کنی.\n"
        "\n"
        "📻 کانال: {channel}{developer_line}\n"
        "\n"
        "چی کار می‌کنه؟\n"
        "• لینک اسپاتیفای / اپل / دیزر / یوتیوب / ساندکلاود\n"
        "• جستجو و مرور هنرمند از دکمه‌های منو\n"
        "• تنظیم کیفیت صدا از منو\n"
        "• پیشنهاد شخصی از دکمه پیشنهاد\n"
        "\n"
        "اگه ایده یا باگی داشتی، پیام بده — خوشحال می‌شم بشنوم 😊"
    ),
    "aboutme_developer_line": "\n💬 توسعه‌دهنده: {username}",

    # --- history ---
    "history_empty": "هنوز چیزی دانلود نکردی — یه آهنگ بفرست تا اینجا ثبت بشه 🎧",
    "history_header": "📜 دانلودهای اخیرت:\n",

    # --- discover ---
    "discover_empty_history": (
        "برای پیشنهاد شخصی، اول چند تا آهنگ دانلود کن — بعد /discover رو بزن 🎧"
    ),
    "discover_not_configured": (
        "پیشنهاد هوشمند فعلاً فعال نیست.\nبه زودی دوباره امتحان کن."
    ),
    "discover_preparing": "⏳ دارم برات آهنگ پیشنهاد می‌دم...",
    "discover_llm_phase": "در حال فکر کردن روی سلیقه‌ات...",
    "discover_resolve_phase": "در حال پیدا کردن آهنگ‌ها ({done}/{total})...",
    "discover_llm_error": "الان نتونستم پیشنهاد بدم — یه کم دیگه دوباره امتحان کن 🙏",
    "discover_no_results": "فعلاً پیشنهاد تازه‌ای ندارم — بعداً دوباره امتحان کن.",
    "discover_header": "🎧 پیشنهاد برای تو:\n",

    # --- cancel / jobs ---
    "cancel_ok": "⏹ درخواست توقف ثبت شد — کار جاری به زودی متوقف می‌شه.",
    "cancel_ok_many": "⏹ درخواست توقف برای {count} کار ثبت شد — به زودی متوقف می‌شن.",
    "cancel_no_job": "الان کار فعالی از طرف تو در حال اجرا نیست.",
    "too_many_jobs": (
        "همزمان بیشتر از {limit} کار نمی‌تونی اجرا کنی.\n"
        "صبر کن تموم بشه یا با /cancel متوقفش کن."
    ),
    "download_cancelled": "متوقف شد.",
    "work_cancelled": "کار لغو شد.",

    # --- preview ---
    "preview_caption": "🎧 پیش‌نمایش ۳۰ ثانیه‌ای",
    "preview_caption_title": "🎧 پیش‌نمایش ۳۰ ثانیه‌ای\n{title}",
    "preview_caption_full": "🎧 پیش‌نمایش ۳۰ ثانیه‌ای\n{title} — {artist}",

    # --- quota / tiers ---
    "rate_limit": "فعلاً به سقف دانلود رسیدی — {minutes} دقیقه دیگه برگرد 🙏",
    "tier_free": "رایگان",
    "tier_premium": "پریمیوم",
    "tier_unlimited": "نامحدود",
    "quota_exceeded": (
        "به سقف دانلود امروز رسیدی ({used}/{limit}) — طرح: {tier}.\n"
        "می‌تونی با ستاره تلگرام سقف امروز رو بالا ببری، "
        "پریمیوم بگیری، یا ۳ دوست دعوت کنی."
    ),

    # --- premium status ---
    "premium_status_title": "⭐ وضعیت اشتراک",
    "premium_plan": "طرح: {tier}",
    "premium_expires": "انقضا: {expires}",
    "premium_limit_unlimited": "سقف امروز: نامحدود",
    "premium_limit_today": "دانلود امروز: {used}/{limit}",
    "premium_day": "تاریخ: {day}",
    "premium_footer": (
        "روزپس: +{topup} دانلود | پریمیوم هفتگی/ماهانه: {premium_daily} در روز"
    ),

    # --- invite / referral ---
    "invite_status": (
        "🎁 دعوت دوست\n"
        "پیشرفت: {toward}/{needed} (مجموع تأییدشده: {credited})\n"
        "در انتظار عضویت کانال: {pending}\n\n"
        "با هر ۳ دوست جدید که از لینک تو وارد بشن و عضو کانال بشن، "
        "+{topup} دانلود امروز بهت اضافه می‌شه.\n\n"
        "لینک دعوت:\n{link}"
    ),
    "referral_topup_granted": (
        "🎉 سه دعوتت تکمیل شد — +{amount} دانلود امروز به حسابت اضافه شد.\n"
        "با /invite پیشرفت بعدیت رو ببین."
    ),

    # --- payments ---
    "payment_failed": "پرداخت ثبت نشد — دوباره از /premium تلاش کن.",
    "payment_already_processed": "این پرداخت قبلاً اعمال شده.",
    "payment_bonus_ok": "✅ +{amount} دانلود برای امروز ({day}) فعال شد.",
    "payment_premium_ok": "✅ اشتراک {tier} فعال شد تا {expires}.",
    "btn_buy_daypass": "🔓 +{amount} دانلود امروز — {stars}⭐",
    "btn_buy_weekly": "⭐ پریمیوم ۷ روزه — {stars}⭐",
    "btn_buy_monthly": "⭐ پریمیوم ۳۰ روزه — {stars}⭐",
    "btn_invite": "🎁 دعوت دوست",

    # --- admin grants ---
    "grant_ok": "✅ کاربر {user_id}: {tier} تا {expires}",
    "topup_ok": "✅ کاربر {user_id}: +{amount} برای {day}",

    # --- download flow ---
    "searching": "⏳ دارم آهنگت رو پیدا می‌کنم...",
    "downloading": "⏳ دارم دانلود می‌کنم...",
    "metadata_not_found": "نتیجه‌ای پیدا نشد — لینک یا نام آهنگ رو دوباره بفرست 🙏",
    "not_music_query": "این شبیه نام آهنگ نیست — لینک موزیک یا «هنرمند - آهنگ» بفرست",
    "collection_not_found": (
        "نتونستم این آلبوم یا پلی‌لیست رو بشناسم — لینک رو چک کن و دوباره بفرست."
    ),
    "send_failed": "ارسال آهنگ ممکن نشد — لطفاً دوباره تلاش کن 🙏",
    "download_not_found": "نسخه کامل پیدا نشد — شاید با اسم دیگه‌ای جستجو کنی بهتر بشه.",
    "download_fail_bot_check": (
        "الان دانلود ممکن نشد — یه کم دیگه دوباره امتحان کن یا اسم دیگه‌ای بفرست."
    ),
    "download_fail_timeout": "دانلود طول کشید و قطع شد — لطفاً دوباره تلاش کن 🙏",
    "download_fail_invalid": "فایل درست دانلود نشد — یه لینک یا اسم دیگه امتحان کن.",
    "record_not_found": "این مورد توی تاریخچه پیدا نشد.",
    "songs_not_found": "آهنگی پیدا نشد — یه اسم دیگه امتحان کن.",

    # --- similar ---
    "similar_preparing": "⏳ دارم آهنگ‌های مشابه پیدا می‌کنم...",
    "similar_llm_phase": "در حال پیدا کردن آهنگ‌های مشابه...",
    "similar_resolve_phase": "در حال آماده‌سازی لیست ({done}/{total})...",
    "similar_header": "🎧 مشابه «{title}»:\n",
    "similar_header_with_artist": "🎧 مشابه «{title} — {artist}»:\n",
    "similar_not_found": "آهنگ مشابهی پیدا نشد — بعداً دوباره امتحان کن.",

    # --- favorites ---
    "liked_empty": "هنوز چیزی به علاقه‌مندی‌ها اضافه نکردی ❤️",
    "liked_header": "❤️ علاقه‌مندی‌هات:\n",
    "favorite_added": "به علاقه‌مندی‌ها اضافه شد: {title}",
    "favorite_removed": "از علاقه‌مندی‌ها حذف شد: {title}",
    "favorite_missing": "این آهنگ برای علاقه‌مندی پیدا نشد.",

    # --- top ---
    "top_header": "🏆 محبوب‌ترین‌ها ({period}):\n",
    "top_empty": "فعلاً آماری برای این بازه نیست.",
    "top_period_day": "۲۴ ساعت",
    "top_period_week": "هفته",
    "top_period_all": "همه زمان‌ها",

    # --- lyrics / artwork ---
    "lyrics_not_found": "متن این آهنگ پیدا نشد.",
    "lyrics_header": "📝 {title}\n\n",
    "lyrics_header_with_artist": "📝 {title} — {artist}\n\n",
    "artwork_not_found": "کاور این آهنگ پیدا نشد.",
    "artwork_sending": "در حال آماده‌سازی کاور...",

    # --- picks / inline ---
    "pick_expired": "این انتخاب منقضی شده — دوباره جستجو کن.",
    "pick_expired_short": "این انتخاب منقضی شده — دوباره امتحان کن.",
    "more_by_artist": "🎵 آهنگ‌های بیشتر از {artist}:\n",
    "inline_description": "{artist} — برای دانلود لمس کن",

    # --- channel gate ---
    "gate_denied": (
        "برای استفاده از ربات، اول عضو کانال @{channel} شو 🙏\n\n"
        "https://t.me/{channel}\n\n"
        "بعد از عضویت، دوباره امتحان کن."
    ),
    "gate_alert": "ابتدا عضو کانال شو.",

    # --- playlists ---
    "playlist_empty": "هیچ آهنگی توی این مجموعه پیدا نشد.",
    "playlist_default_name": "پلی‌لیست",
    "playlist_start": (
        "📋 شروع دانلود: {name}\n"
        "تعداد: {total} آهنگ\n\n"
        "/cancel برای توقف کار جاری"
    ),
    "playlist_cancelled": "متوقف شد. ارسال شده: {sent}/{total}",
    "playlist_rate_limited": "محدودیت نرخ ({minutes} دقیقه). ارسال شده: {sent}/{total}",
    "playlist_summary": "ارسال شده: {sent}/{total}",
    "playlist_summary_failed": "ارسال شده: {sent}/{total} | ناموفق: {failed}",
    "playlist_zip_sending": "📦 در حال ساخت ZIP ({count} آهنگ) — {name}...",
    "playlist_zip_caption": "📦 {name} — {count} آهنگ",

    # --- progress ---
    "progress_update": "📥 {label} {bar} {pct}%{counter}{detail_line}{eta_line}",
    "progress_counter": " — آهنگ {current} از {total}",
    "progress_eta": "\n⏳ حدودا {m}:{s:02d}",
    "progress_done": "✅ {label} تمام شد.",
    "progress_done_with_summary": "✅ {label} تمام شد.\n{summary}",
    "progress_fail": "❌ {label} ناموفق بود.",
    "progress_fail_with_reason": "❌ {label} ناموفق بود.\n{reason}",

    # --- error reporting ---
    "error_report_button": "📩 گزارش به پشتیبان",
    "error_retry_button": "🔄 تلاش مجدد",
    "error_retrying": "🔄 در حال تلاش مجدد...",
    "error_retry_unavailable": (
        "تلاش مجدد برای این خطا ممکن نیست — دوباره لینک یا اسم آهنگ رو بفرست."
    ),
    "error_report_sent": "\n\n✅ گزارشت ثبت شد. ممنون!",
    "error_report_already_sent": "این خطا قبلاً گزارش شده.",
    "error_report_rate_limited": "محدودیت گزارش — فردا دوباره امتحان کن.",

    # --- support chat ---
    "support_admin_prompt": (
        "حالت پاسخ فعال — گزارش #{report_id} (کاربر {user_id})\n"
        "هر پیامی بفرستی مستقیم به کاربر می‌رسد.\n"
        "پایان گفتگو: /supportend"
    ),
    "support_user_message": (
        "📩 پیام از پشتیبان HiiT Radio\n\n"
        "{admin_text}\n\n"
        "برای پاسخ: /support متن پیام"
    ),
    "support_user_opened": (
        "پشتیبان درباره گزارش خطایت باهات تماس گرفت.\n"
        "برای پاسخ از /support استفاده کن — بقیه پیام‌ها مثل همیشه برای دانلود آهنگه."
    ),
    "support_user_closed": (
        "گفتگو با پشتیبان پایان یافت. اگر باز هم مشکلی داری، دوباره گزارش بده."
    ),
    "support_no_thread": (
        "گفتگوی فعالی با پشتیبان نداری.\n"
        "اول از دکمه «📩 گزارش به پشتیبان» روی پیام خطا استفاده کن؛ "
        "بعد از پاسخ پشتیبان می‌توانی با /support پیام بفرستی."
    ),
    "support_usage": (
        "نحوه استفاده: /support متن پیام\n"
        "فقط وقتی کار می‌کند که پشتیبان از گزارش خطایت جواب داده باشد."
    ),
    "support_admin_usage": (
        "شما ادمین هستید.\n"
        "• روی گزارش خطا «پاسخ» بزن، بعد هر پیام متنی = ارسال به کاربر\n"
        "• پایان: /supportend"
    ),
    "support_empty_message": "پیام خالی — بعد از /support متن بنویس.",
    "support_sent_admin": "✅ پیام به کاربر {user_id} ارسال شد.",
    "support_sent_user": "✅ پیامت به پشتیبان رسید.",
    "support_forward_to_admin": (
        "💬 پاسخ کاربر ({user_label}) — گزارش #{report_id}\n\n{text}"
    ),
    "support_send_failed_blocked": "ارسال ناموفق — کاربر ربات را block کرده.",
    "support_send_failed": "ارسال ناموفق — بعداً دوباره امتحان کن.",
    "support_thread_ended_admin": "گفتگو #{thread_id} بسته شد.",
    "support_thread_ended_no_open": "گفتگوی باز فعالی نیست.",
    "support_reply_button": "💬 پاسخ به کاربر",
    "support_end_button": "⏹ پایان گفتگو",
    "support_report_not_found": "گزارش پیدا نشد یا هنوز ارسال نشده.",

    # --- cookies (admin) ---
    "cookies_status_title": "🍪 وضعیت کوکی یوتیوب",
    "cookies_state_ok": "سالم",
    "cookies_state_bad": "ناسالم",
    "cookies_status_state": "وضعیت: {state}",
    "cookies_status_detail": "جزئیات: {detail}",
    "cookies_status_path": "مسیر: {path}",
    "cookies_status_updated": "آخرین به‌روزرسانی: {updated}",
    "cookies_status_footer": (
        "برای به‌روزرسانی، فایل cookies.txt رو (خروجی Netscape از مرورگری که "
        "توی youtube.com لاگین هستی) همین‌جا به‌صورت فایل بفرست."
    ),
    "cookies_accepted": "✅ cookies.txt به‌روزرسانی شد.\nجزئیات: {detail}",
    "cookies_accepted_backup": "\nنسخه قبلی در cookies.txt.bak ذخیره شد.",
    "cookies_rejected": (
        "❌ این فایل کوکی معتبر نیست و ذخیره نشد.\n"
        "جزئیات: {detail}\n\n"
        "دوباره در حالی که توی youtube.com لاگین هستی خروجی Netscape بگیر."
    ),
    "cookies_too_large": "❌ فایل خیلی بزرگه (بیشتر از {limit_kb} کیلوبایت).",

    # --- track action buttons ---
    "btn_more_by_artist": "آهنگ‌های بیشتر",
    "btn_similar": "آهنگ‌های مشابه",
    "btn_lyrics": "متن آهنگ",
    "btn_artwork": "🖼 کاور آهنگ",
    "btn_favorite_add": "❤️ علاقه‌مندی",
    "btn_favorite_remove": "💔 حذف علاقه‌مندی",

    # --- search ---
    "prompt_search": "🔍 اسم آهنگ یا هنرمند رو بفرست:",
    "prompt_artist": "🎙 اسم هنرمند رو بفرست:",
    "prompt_follow": "🔔 اسم هنرمندی که می‌خوای دنبال کنی رو بفرست:",
    "prompt_support": "💬 پیام خودت برای پشتیبان رو بنویس:",
    "prompt_cancelled": "⏹ ورود متن لغو شد.",
    "search_usage": "نحوه استفاده:\n/search نام آهنگ یا هنرمند",
    "search_empty": "نتیجه‌ای پیدا نشد — عبارت دیگه‌ای امتحان کن.",
    "search_header": "🔍 نتایج جستجو برای «{query}»:",
    "search_hit_line": "{index}. [{kind}] {name}{sub}",
    "search_kind_track": "آهنگ",
    "search_kind_album": "آلبوم",
    "search_kind_playlist": "پلی‌لیست",
    "search_kind_artist": "هنرمند",

    # --- artist ---
    "artist_usage": "نحوه استفاده:\n/artist نام هنرمند",
    "artist_not_found": "هنرمند «{name}» پیدا نشد.",
    "artist_header": "🎤 {name}",
    "artist_top_header": "برترین آهنگ‌ها:",
    "artist_albums_header": "آلبوم‌ها:",

    # --- quality ---
    "quality_hint_128": "کم‌حجم — مناسب فضای کم",
    "quality_hint_192": "متعادل — کیفیت خوب",
    "quality_hint_256": "پیش‌فرض ربات",
    "quality_hint_320": "بهترین MP3",
    "quality_hint_original": "بدون تبدیل — همان فایل منبع",
    "quality_status_kbps": "🎚 کیفیت فعلی: {value} kbps",
    "quality_status_original": "🎚 کیفیت فعلی: original (بدون تبدیل)",
    "quality_status_footer": "یکی از دکمه‌ها رو بزن.",
    "quality_set_kbps": "✅ کیفیت روی {value} kbps تنظیم شد.",
    "quality_set_original": "✅ کیفیت روی original (بدون تبدیل) تنظیم شد.",
    "quality_invalid": "کیفیت نامعتبر. گزینه‌ها: 128 · 192 · 256 · 320 · original",

    # --- artist follow ---
    "follow_success": "✅ هنرمند «{artist}» دنبال شد — وقتی آلبوم جدید بذاره بهت خبر می‌دم!",
    "unfollow_success": "🔕 دنبال‌کردن «{artist}» لغو شد.",
    "already_following": "قبلاً «{artist}» رو دنبال کردی.",
    "not_following": "هنوز هیچ هنرمندی رو دنبال نکردی — از دکمه دنبال‌کردن هنرمند شروع کن!",
    "following_header": "🎙 هنرمندان دنبال‌شده:",
    "follow_usage": "نحوه استفاده:\n/follow نام هنرمند",
    "btn_follow": "🔔 دنبال‌کردن {artist}",
    "btn_unfollow": "🔕 لغو دنبال‌کردن {artist}",
    "new_release_notification": (
        "🔔 انتشار جدید!\n"
        "\n"
        "🎤 {artist}\n"
        "💿 {album}{date_line}\n"
        "\n"
        "برای دانلود آلبوم دکمه زیر رو بزن 👇"
    ),
    "new_release_date_line": "\n📅 {date}",

    # --- main menu ---
    "menu_follow": "🔔 دنبال‌کردن هنرمند",
    "menu_support": "💬 پشتیبانی",
    "menu_search": "🔎 جستجوی آهنگ",
    "menu_artist": "🎙 مرور هنرمند",
    "menu_quality": "🎛 کیفیت صدا",
    "menu_help": "📚 راهنمای کامل",
    "menu_history": "🕐 تاریخچه دانلود",
    "menu_liked": "💖 علاقه‌مندی‌ها",
    "menu_top": "🔥 محبوب‌ترین‌ها",
    "menu_discover": "🎯 پیشنهاد شخصی",
    "menu_following": "🔔 هنرمندان من",
    "menu_invite": "🎁 دعوت دوست",
    "menu_premium": "💠 پریمیوم",
    "menu_aboutme": "🤖 درباره ربات",
    "menu_cancel": "⛔ لغو کار جاری",
    "menu_back": "🔙 بازگشت به منو",
    "menu_lang": "🌐 زبان",

    # --- language selection ---
    "lang_choose": "🌐 زبان ربات را انتخاب کن:",
    "lang_set": "✅ زبان روی {lang_name} تنظیم شد.",
    "lang_name_fa": "فارسی",
    "lang_name_en": "English",
    "lang_name_fr": "Français",
    "lang_name_es": "Español",
    "lang_name_ru": "Русский",
    "lang_name_it": "Italiano",
}
