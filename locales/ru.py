"""Russian (ru) locale strings for the HiiT Radio bot."""

STRINGS = {
    # --- generic ---
    "unknown": "Неизвестно",

    # --- platforms ---
    "platform_spotify": "Spotify",
    "platform_apple": "Apple Music",
    "platform_youtube": "YouTube",
    "platform_soundcloud": "SoundCloud",
    "platform_deezer": "Deezer",
    "platform_cache": "Кэш",

    # --- download buttons ---
    "btn_redownload": "🔄 Скачать снова: {label}",
    "btn_download_indexed": "{index}. Скачать «{label}»",
    "btn_download": "Скачать «{label}»",

    # --- start / help / about ---
    "start_friend_name": "дорогой друг",
    "start_text": (
        "Привет, {name}! 🎶\n\n"
        "Добро пожаловать в HiiT Radio — бот для скачивания музыки без ограничений!\n\n"
        "Просто пришли ссылку на трек, альбом или плейлист "
        "(Spotify · Apple Music · Deezer · YouTube · SoundCloud) "
        "или напиши название песни — остальное сделаю я.\n\n"
        "Начни с кнопок ниже 👇"
    ),
    "help_text": (
        "Как этим пользоваться?\n\n"
        "1. Пришли ссылку на трек, альбом или плейлист\n"
        "   (Spotify · Apple Music · Deezer · YouTube · SoundCloud)\n"
        "2. Или напиши название песни и исполнителя\n"
        "3. /search название трека — поиск в Deezer и Apple\n"
        "4. /artist имя исполнителя — альбомы и лучшие треки\n"
        "5. /quality — выбор качества MP3\n"
        "6. Или инлайн: {bot_inline} название трека — в любом чате\n\n"
        "/liked — сохранённые треки\n"
        "/top — чарт популярных (day / week / all)\n"
        "/discover — 10 рекомендаций на основе твоей истории\n"
        "/premium — премиум-подписка / покупка дневного лимита\n"
        "/invite — ссылка для приглашения друга\n"
        "/cancel — остановить любую текущую задачу (загрузку, подбор, …)\n"
        "/aboutme — о боте и его создателе\n\n"
        "Бесплатный дневной лимит: 10 загрузок "
        "(премиум: {premium_daily_limit})."
    ),
    "aboutme_text": (
        "🎙 О HiiT Radio\n"
        "\n"
        "Этого бота сделал я, {developer_name}, чтобы тебе было проще скачивать музыку.\n"
        "\n"
        "📻 Канал: {channel}{developer_line}\n"
        "\n"
        "Что он умеет?\n"
        "• Ссылки Spotify / Apple / Deezer / YouTube / SoundCloud\n"
        "• Поиск по названию трека (/search)\n"
        "• Просмотр исполнителей (/artist) и качество звука (/quality)\n"
        "• Персональные рекомендации через /discover\n"
        "\n"
        "Есть идея или нашёл баг? Напиши мне — буду рад 😊"
    ),
    "aboutme_developer_line": "\n💬 Разработчик: {username}",

    # --- history ---
    "history_empty": (
        "Ты пока ничего не скачивал — пришли трек, и он появится здесь 🎧"
    ),
    "history_header": "📜 Твои последние загрузки:\n",

    # --- discover ---
    "discover_empty_history": (
        "Для персональных рекомендаций скачай сначала несколько треков — "
        "потом нажми /discover 🎧"
    ),
    "discover_not_configured": (
        "Умные рекомендации пока недоступны.\nПопробуй чуть позже."
    ),
    "discover_preparing": "⏳ Подбираю для тебя музыку...",
    "discover_llm_phase": "Думаю над твоим вкусом...",
    "discover_resolve_phase": "Ищу треки ({done}/{total})...",
    "discover_llm_error": (
        "Сейчас не получилось подобрать рекомендации — попробуй чуть позже 🙏"
    ),
    "discover_no_results": "Пока новых рекомендаций нет — попробуй позже.",
    "discover_header": "🎧 Подборка для тебя:\n",

    # --- cancel / jobs ---
    "cancel_ok": "⏹ Запрос на остановку принят — текущая задача скоро остановится.",
    "cancel_ok_many": (
        "⏹ Запрос на остановку принят для {count} задач — они скоро остановятся."
    ),
    "cancel_no_job": "Сейчас у тебя нет активных задач.",
    "too_many_jobs": (
        "Нельзя запускать больше {limit} задач одновременно.\n"
        "Дождись завершения или останови их командой /cancel."
    ),
    "download_cancelled": "Остановлено.",
    "work_cancelled": "Задача отменена.",

    # --- preview ---
    "preview_caption": "🎧 30-секундный отрывок",
    "preview_caption_title": "🎧 30-секундный отрывок\n{title}",
    "preview_caption_full": "🎧 30-секундный отрывок\n{title} — {artist}",

    # --- quota / tiers ---
    "rate_limit": (
        "Пока лимит загрузок достигнут — возвращайся через {minutes} минут 🙏"
    ),
    "tier_free": "Бесплатный",
    "tier_premium": "Премиум",
    "tier_unlimited": "Без ограничений",
    "quota_exceeded": (
        "Ты достиг дневного лимита загрузок ({used}/{limit}) — тариф: {tier}.\n"
        "Можно поднять сегодняшний лимит с помощью Telegram Stars, "
        "оформить премиум или пригласить 3 друзей."
    ),

    # --- premium status ---
    "premium_status_title": "⭐ Статус подписки",
    "premium_plan": "Тариф: {tier}",
    "premium_expires": "Истекает: {expires}",
    "premium_limit_unlimited": "Лимит на сегодня: без ограничений",
    "premium_limit_today": "Загрузок сегодня: {used}/{limit}",
    "premium_day": "Дата: {day}",
    "premium_footer": (
        "Дневной пропуск: +{topup} загрузок | "
        "Премиум на неделю/месяц: {premium_daily} в день"
    ),

    # --- invite / referral ---
    "invite_status": (
        "🎁 Пригласи друга\n"
        "Прогресс: {toward}/{needed} (всего подтверждено: {credited})\n"
        "Ожидают подписки на канал: {pending}\n\n"
        "За каждые 3 новых друга, которые придут по твоей ссылке и подпишутся "
        "на канал, ты получаешь +{topup} загрузок на сегодня.\n\n"
        "Ссылка-приглашение:\n{link}"
    ),
    "referral_topup_granted": (
        "🎉 Три приглашения выполнены — +{amount} загрузок добавлено на сегодня.\n"
        "Посмотри следующую цель через /invite."
    ),

    # --- payments ---
    "payment_failed": "Платёж не прошёл — попробуй снова через /premium.",
    "payment_already_processed": "Этот платёж уже применён.",
    "payment_bonus_ok": "✅ +{amount} загрузок активировано на сегодня ({day}).",
    "payment_premium_ok": "✅ Подписка {tier} активна до {expires}.",
    "btn_buy_daypass": "🔓 +{amount} загрузок сегодня — {stars}⭐",
    "btn_buy_weekly": "⭐ Премиум на 7 дней — {stars}⭐",
    "btn_buy_monthly": "⭐ Премиум на 30 дней — {stars}⭐",
    "btn_invite": "🎁 Пригласить друга",

    # --- admin grants ---
    "grant_ok": "✅ Пользователь {user_id}: {tier} до {expires}",
    "topup_ok": "✅ Пользователь {user_id}: +{amount} на {day}",

    # --- download flow ---
    "searching": "⏳ Ищу твой трек...",
    "downloading": "⏳ Скачиваю...",
    "metadata_not_found": (
        "Ничего не нашлось — пришли ссылку или название трека снова 🙏"
    ),
    "not_music_query": (
        "Это не похоже на название трека — пришли ссылку на музыку "
        "или «исполнитель - трек»"
    ),
    "collection_not_found": (
        "Не смог распознать этот альбом или плейлист — проверь ссылку и пришли снова."
    ),
    "send_failed": "Не удалось отправить трек — попробуй ещё раз 🙏",
    "download_not_found": (
        "Полная версия не найдена — возможно, стоит поискать под другим названием."
    ),
    "download_fail_bot_check": (
        "Сейчас скачать не получилось — попробуй чуть позже или пришли другое название."
    ),
    "download_fail_timeout": "Загрузка затянулась и прервалась — попробуй ещё раз 🙏",
    "download_fail_invalid": (
        "Файл скачался некорректно — попробуй другую ссылку или название."
    ),
    "record_not_found": "Эта запись не найдена в истории.",
    "songs_not_found": "Треков не найдено — попробуй другое название.",

    # --- similar ---
    "similar_preparing": "⏳ Ищу похожие треки...",
    "similar_llm_phase": "Подбираю похожие треки...",
    "similar_resolve_phase": "Готовлю список ({done}/{total})...",
    "similar_header": "🎧 Похоже на «{title}»:\n",
    "similar_header_with_artist": "🎧 Похоже на «{title} — {artist}»:\n",
    "similar_not_found": "Похожих треков не нашлось — попробуй позже.",

    # --- favorites ---
    "liked_empty": "Ты пока ничего не добавил в избранное ❤️",
    "liked_header": "❤️ Твоё избранное:\n",
    "favorite_added": "Добавлено в избранное: {title}",
    "favorite_removed": "Удалено из избранного: {title}",
    "favorite_missing": "Этот трек не найден для добавления в избранное.",

    # --- top ---
    "top_header": "🏆 Самое популярное ({period}):\n",
    "top_empty": "Для этого периода статистики пока нет.",
    "top_period_day": "24 часа",
    "top_period_week": "неделя",
    "top_period_all": "всё время",

    # --- lyrics / artwork ---
    "lyrics_not_found": "Текст этой песни не найден.",
    "lyrics_header": "📝 {title}\n\n",
    "lyrics_header_with_artist": "📝 {title} — {artist}\n\n",
    "artwork_not_found": "Обложка этого трека не найдена.",
    "artwork_sending": "Готовлю обложку...",

    # --- picks / inline ---
    "pick_expired": "Этот выбор устарел — выполни поиск заново.",
    "pick_expired_short": "Этот выбор устарел — попробуй снова.",
    "more_by_artist": "🎵 Больше треков {artist}:\n",
    "inline_description": "{artist} — нажми, чтобы скачать",

    # --- channel gate ---
    "gate_denied": (
        "Чтобы пользоваться ботом, сначала подпишись на канал @{channel} 🙏\n\n"
        "https://t.me/{channel}\n\n"
        "После подписки попробуй снова."
    ),
    "gate_alert": "Сначала подпишись на канал.",

    # --- playlists ---
    "playlist_empty": "В этой подборке треков не нашлось.",
    "playlist_default_name": "Плейлист",
    "playlist_start": (
        "📋 Начинаю загрузку: {name}\n"
        "Количество: {total} треков\n\n"
        "/cancel — остановить текущую задачу"
    ),
    "playlist_cancelled": "Остановлено. Отправлено: {sent}/{total}",
    "playlist_rate_limited": (
        "Ограничение частоты ({minutes} минут). Отправлено: {sent}/{total}"
    ),
    "playlist_summary": "Отправлено: {sent}/{total}",
    "playlist_summary_failed": "Отправлено: {sent}/{total} | Неудачно: {failed}",
    "playlist_zip_sending": "📦 Собираю ZIP ({count} треков) — {name}...",
    "playlist_zip_caption": "📦 {name} — {count} треков",

    # --- progress ---
    "progress_update": "📥 {label} {bar} {pct}%{counter}{detail_line}{eta_line}",
    "progress_counter": " — трек {current} из {total}",
    "progress_eta": "\n⏳ примерно {m}:{s:02d}",
    "progress_done": "✅ {label} завершено.",
    "progress_done_with_summary": "✅ {label} завершено.\n{summary}",
    "progress_fail": "❌ {label} не удалось.",
    "progress_fail_with_reason": "❌ {label} не удалось.\n{reason}",

    # --- error reporting ---
    "error_report_button": "📩 Сообщить в поддержку",
    "error_retry_button": "🔄 Повторить",
    "error_retrying": "🔄 Пробую снова...",
    "error_retry_unavailable": (
        "Повторить эту ошибку нельзя — пришли ссылку или название трека снова."
    ),
    "error_report_sent": "\n\n✅ Твоё сообщение отправлено. Спасибо!",
    "error_report_already_sent": "Об этой ошибке уже сообщили.",
    "error_report_rate_limited": "Лимит обращений — попробуй завтра.",

    # --- support chat ---
    "support_admin_prompt": (
        "Режим ответа включён — обращение #{report_id} (пользователь {user_id})\n"
        "Любое сообщение уйдёт напрямую пользователю.\n"
        "Завершить диалог: /supportend"
    ),
    "support_user_message": (
        "📩 Сообщение от поддержки HiiT Radio\n\n"
        "{admin_text}\n\n"
        "Чтобы ответить: /support текст сообщения"
    ),
    "support_user_opened": (
        "Поддержка связалась с тобой по твоему сообщению об ошибке.\n"
        "Для ответа используй /support — остальные сообщения по-прежнему "
        "работают для скачивания музыки."
    ),
    "support_user_closed": (
        "Диалог с поддержкой завершён. Если проблема осталась, напиши ещё раз."
    ),
    "support_no_thread": (
        "У тебя нет активного диалога с поддержкой.\n"
        "Сначала нажми кнопку «📩 Сообщить в поддержку» под сообщением об ошибке; "
        "после ответа поддержки сможешь писать через /support."
    ),
    "support_usage": (
        "Использование: /support текст сообщения\n"
        "Работает только если поддержка ответила на твоё сообщение об ошибке."
    ),
    "support_admin_usage": (
        "Ты администратор.\n"
        "• Нажми «Ответить» на сообщении об ошибке, затем любой текст "
        "уйдёт пользователю\n"
        "• Завершить: /supportend"
    ),
    "support_empty_message": "Пустое сообщение — напиши текст после /support.",
    "support_sent_admin": "✅ Сообщение отправлено пользователю {user_id}.",
    "support_sent_user": "✅ Твоё сообщение дошло до поддержки.",
    "support_forward_to_admin": (
        "💬 Ответ пользователя ({user_label}) — обращение #{report_id}\n\n{text}"
    ),
    "support_send_failed_blocked": (
        "Отправить не удалось — пользователь заблокировал бота."
    ),
    "support_send_failed": "Отправить не удалось — попробуй позже.",
    "support_thread_ended_admin": "Диалог #{thread_id} закрыт.",
    "support_thread_ended_no_open": "Открытых диалогов нет.",
    "support_reply_button": "💬 Ответить пользователю",
    "support_end_button": "⏹ Завершить диалог",
    "support_report_not_found": "Обращение не найдено или ещё не отправлено.",

    # --- cookies (admin) ---
    "cookies_status_title": "🍪 Состояние cookies YouTube",
    "cookies_state_ok": "в порядке",
    "cookies_state_bad": "неисправно",
    "cookies_status_state": "Состояние: {state}",
    "cookies_status_detail": "Подробности: {detail}",
    "cookies_status_path": "Путь: {path}",
    "cookies_status_updated": "Последнее обновление: {updated}",
    "cookies_status_footer": (
        "Чтобы обновить, пришли сюда файл cookies.txt документом "
        "(экспорт в формате Netscape из браузера, где выполнен вход на youtube.com)."
    ),
    "cookies_accepted": "✅ cookies.txt обновлён.\nПодробности: {detail}",
    "cookies_accepted_backup": "\nПредыдущая версия сохранена в cookies.txt.bak.",
    "cookies_rejected": (
        "❌ Этот файл cookies недействителен и не сохранён.\n"
        "Подробности: {detail}\n\n"
        "Сделай экспорт в формате Netscape заново, войдя на youtube.com."
    ),
    "cookies_too_large": "❌ Файл слишком большой (больше {limit_kb} КБ).",

    # --- track action buttons ---
    "btn_more_by_artist": "Больше треков",
    "btn_similar": "Похожие треки",
    "btn_lyrics": "Текст песни",
    "btn_artwork": "🖼 Обложка",
    "btn_favorite_add": "❤️ В избранное",
    "btn_favorite_remove": "💔 Убрать из избранного",

    # --- search ---
    "search_usage": "Использование:\n/search название трека или исполнителя",
    "search_empty": "Ничего не нашлось — попробуй другой запрос.",
    "search_header": "🔍 Результаты поиска по «{query}»:",
    "search_hit_line": "{index}. [{kind}] {name}{sub}",
    "search_kind_track": "Трек",
    "search_kind_album": "Альбом",
    "search_kind_playlist": "Плейлист",
    "search_kind_artist": "Исполнитель",

    # --- artist ---
    "artist_usage": "Использование:\n/artist имя исполнителя",
    "artist_not_found": "Исполнитель «{name}» не найден.",
    "artist_header": "🎤 {name}",
    "artist_top_header": "Лучшие треки:",
    "artist_albums_header": "Альбомы:",

    # --- quality ---
    "quality_hint_128": "Небольшой размер — если мало места",
    "quality_hint_192": "Сбалансированно — хорошее качество",
    "quality_hint_256": "По умолчанию в боте",
    "quality_hint_320": "Лучший MP3",
    "quality_hint_original": "Без конвертации — исходный файл как есть",
    "quality_status_kbps": "🎚 Текущее качество: {value} kbps",
    "quality_status_original": "🎚 Текущее качество: original (без конвертации)",
    "quality_status_footer": "Нажми одну из кнопок или напиши: /quality 320",
    "quality_set_kbps": "✅ Качество установлено на {value} kbps.",
    "quality_set_original": "✅ Качество установлено на original (без конвертации).",
    "quality_invalid": "Недопустимое качество. Варианты: 128 · 192 · 256 · 320 · original",

    # --- artist follow ---
    "follow_success": (
        "✅ Ты подписался на «{artist}» — сообщу, когда выйдет новый альбом!"
    ),
    "unfollow_success": "🔕 Подписка на «{artist}» отменена.",
    "already_following": "Ты уже подписан на «{artist}».",
    "not_following": "Ты пока ни на кого не подписан — начни с /follow!",
    "following_header": "🎙 Исполнители, за которыми ты следишь:",
    "follow_usage": "Использование:\n/follow имя исполнителя",
    "btn_follow": "🔔 Подписаться на {artist}",
    "btn_unfollow": "🔕 Отписаться от {artist}",
    "new_release_notification": (
        "🔔 Новый релиз!\n"
        "\n"
        "🎤 {artist}\n"
        "💿 {album}{date_line}\n"
        "\n"
        "Нажми кнопку ниже, чтобы скачать альбом 👇"
    ),
    "new_release_date_line": "\n📅 {date}",

    # --- main menu ---
    "menu_search": "🔎 Поиск трека",
    "menu_artist": "🎙 Обзор исполнителя",
    "menu_quality": "🎛 Качество звука",
    "menu_help": "📚 Полное руководство",
    "menu_history": "🕐 История загрузок",
    "menu_liked": "💖 Избранное",
    "menu_top": "🔥 Самое популярное",
    "menu_discover": "🎯 Для тебя",
    "menu_following": "🔔 Мои исполнители",
    "menu_invite": "🎁 Пригласить друга",
    "menu_premium": "💠 Премиум",
    "menu_aboutme": "🤖 О боте",
    "menu_cancel": "⛔ Отменить текущую задачу",
    "menu_back": "🔙 Назад в меню",
    "menu_lang": "🌐 Язык",

    # --- language selection ---
    "lang_choose": "🌐 Выбери язык бота:",
    "lang_set": "✅ Язык установлен: {lang_name}.",
    "lang_name_fa": "فارسی",
    "lang_name_en": "English",
    "lang_name_fr": "Français",
    "lang_name_es": "Español",
    "lang_name_ru": "Русский",
    "lang_name_it": "Italiano",
}
