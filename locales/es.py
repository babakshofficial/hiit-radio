"""Spanish (es) locale strings for the HiiT Radio bot."""

STRINGS = {
    # --- generic ---
    "unknown": "Desconocido",

    # --- platforms ---
    "platform_spotify": "Spotify",
    "platform_apple": "Apple Music",
    "platform_youtube": "YouTube",
    "platform_soundcloud": "SoundCloud",
    "platform_deezer": "Deezer",
    "platform_cache": "Caché",

    # --- download buttons ---
    "btn_redownload": "🔄 Descargar de nuevo: {label}",
    "btn_download_indexed": "{index}. Descargar «{label}»",
    "btn_download": "Descargar «{label}»",

    # --- start / help / about ---
    "start_friend_name": "amigo",
    "start_text": (
        "¡Hola {name}! 🎶\n\n"
        "Bienvenido a HiiT Radio: el bot de descarga de música sin límites.\n\n"
        "Solo envía un enlace de canción, álbum o lista de reproducción "
        "(Spotify · Apple Music · Deezer · YouTube · SoundCloud) "
        "o escribe el nombre de una canción; yo me encargo del resto.\n\n"
        "Empieza con los botones de abajo 👇"
    ),
    "help_text": (
        "¿Cómo se usa?\n\n"
        "1. Envía un enlace de canción, álbum o lista\n"
        "   (Spotify · Apple Music · Deezer · YouTube · SoundCloud)\n"
        "2. O escribe el nombre de la canción y del artista\n"
        "3. Usa los botones de abajo para buscar, artistas, calidad y más\n"
        "4. O en línea: {bot_inline} nombre de la canción — en cualquier chat\n\n"
        "Límite diario gratuito: 10 descargas (premium: {premium_daily_limit})."
    ),
    "aboutme_text": (
        "🎙 Sobre HiiT Radio\n"
        "\n"
        "Soy {developer_name} y creé este bot para que descargar música sea más fácil.\n"
        "\n"
        "📻 Canal: {channel}{developer_line}\n"
        "\n"
        "¿Qué puede hacer?\n"
        "• Enlaces de Spotify / Apple / Deezer / YouTube / SoundCloud\n"
        "• Búsqueda y artistas desde los botones del menú\n"
        "• Calidad de audio desde el menú\n"
        "• Recomendaciones personales desde Descubrir\n"
        "\n"
        "Si tienes una idea o encuentras un error, escríbeme: me encantará leerte 😊"
    ),
    "aboutme_developer_line": "\n💬 Desarrollador: {username}",

    # --- history ---
    "history_empty": (
        "Todavía no has descargado nada: envía una canción y aparecerá aquí 🎧"
    ),
    "history_header": "📜 Tus descargas recientes:\n",

    # --- discover ---
    "discover_empty_history": (
        "Para tener recomendaciones personales, descarga primero algunas canciones "
        "y luego usa /discover 🎧"
    ),
    "discover_not_configured": (
        "Las recomendaciones inteligentes no están activas ahora mismo.\n"
        "Inténtalo de nuevo pronto."
    ),
    "discover_preparing": "⏳ Estoy preparando recomendaciones para ti...",
    "discover_llm_phase": "Pensando en tus gustos...",
    "discover_resolve_phase": "Buscando las canciones ({done}/{total})...",
    "discover_llm_error": (
        "Ahora no he podido recomendarte nada: inténtalo de nuevo en un rato 🙏"
    ),
    "discover_no_results": "Por ahora no tengo nuevas sugerencias: prueba más tarde.",
    "discover_header": "🎧 Elegido para ti:\n",

    # --- cancel / jobs ---
    "cancel_ok": "⏹ Solicitud de parada registrada: la tarea actual se detendrá pronto.",
    "cancel_ok_many": (
        "⏹ Solicitud de parada registrada para {count} tareas: se detendrán pronto."
    ),
    "cancel_no_job": "Ahora mismo no tienes ninguna tarea activa.",
    "too_many_jobs": (
        "No puedes ejecutar más de {limit} tareas a la vez.\n"
        "Espera a que terminen o deténlas con /cancel."
    ),
    "download_cancelled": "Detenido.",
    "work_cancelled": "Tarea cancelada.",

    # --- preview ---
    "preview_caption": "🎧 Vista previa de 30 segundos",
    "preview_caption_title": "🎧 Vista previa de 30 segundos\n{title}",
    "preview_caption_full": "🎧 Vista previa de 30 segundos\n{title} — {artist}",

    # --- quota / tiers ---
    "rate_limit": (
        "Has alcanzado el límite de descargas: vuelve en {minutes} minutos 🙏"
    ),
    "tier_free": "Gratis",
    "tier_premium": "Premium",
    "tier_unlimited": "Ilimitado",
    "quota_exceeded": (
        "Has alcanzado el límite de descargas de hoy ({used}/{limit}) — plan: {tier}.\n"
        "Puedes ampliar el límite de hoy con Estrellas de Telegram, "
        "conseguir premium o invitar a 3 amigos."
    ),

    # --- premium status ---
    "premium_status_title": "⭐ Estado de la suscripción",
    "premium_plan": "Plan: {tier}",
    "premium_expires": "Caduca: {expires}",
    "premium_limit_unlimited": "Límite de hoy: ilimitado",
    "premium_limit_today": "Descargas de hoy: {used}/{limit}",
    "premium_day": "Fecha: {day}",
    "premium_footer": (
        "Pase diario: +{topup} descargas | "
        "Premium semanal/mensual: {premium_daily} al día"
    ),

    # --- invite / referral ---
    "invite_status": (
        "🎁 Invitar a un amigo\n"
        "Progreso: {toward}/{needed} (total confirmado: {credited})\n"
        "Pendientes de unirse al canal: {pending}\n\n"
        "Por cada 3 amigos nuevos que entren con tu enlace y se unan al canal, "
        "recibes +{topup} descargas hoy.\n\n"
        "Enlace de invitación:\n{link}"
    ),
    "referral_topup_granted": (
        "🎉 Has completado tres invitaciones: +{amount} descargas añadidas "
        "a tu cuenta hoy.\n"
        "Consulta tu siguiente meta con /invite."
    ),

    # --- payments ---
    "payment_failed": "El pago no se registró: inténtalo de nuevo desde /premium.",
    "payment_already_processed": "Este pago ya se había aplicado.",
    "payment_bonus_ok": "✅ +{amount} descargas activadas para hoy ({day}).",
    "payment_premium_ok": "✅ Tu suscripción {tier} está activa hasta {expires}.",
    "btn_buy_daypass": "🔓 +{amount} descargas hoy — {stars}⭐",
    "btn_buy_weekly": "⭐ Premium de 7 días — {stars}⭐",
    "btn_buy_monthly": "⭐ Premium de 30 días — {stars}⭐",
    "btn_invite": "🎁 Invitar a un amigo",

    # --- admin grants ---
    "grant_ok": "✅ Usuario {user_id}: {tier} hasta {expires}",
    "topup_ok": "✅ Usuario {user_id}: +{amount} para {day}",

    # --- download flow ---
    "searching": "⏳ Estoy buscando tu canción...",
    "downloading": "⏳ Descargando...",
    "metadata_not_found": (
        "No he encontrado resultados: envía otra vez el enlace o el nombre 🙏"
    ),
    "not_music_query": (
        "Esto no parece el nombre de una canción: envía un enlace de música "
        "o «artista - canción»"
    ),
    "collection_not_found": (
        "No he podido reconocer este álbum o lista: revisa el enlace y envíalo de nuevo."
    ),
    "send_failed": "No he podido enviar la canción: inténtalo de nuevo 🙏",
    "download_not_found": (
        "No encontré la versión completa: quizá busques mejor con otro nombre."
    ),
    "download_fail_bot_check": (
        "Ahora no se ha podido descargar: inténtalo en un rato o envía otro nombre."
    ),
    "download_fail_timeout": (
        "La descarga tardó demasiado y se cortó: inténtalo de nuevo 🙏"
    ),
    "download_fail_invalid": (
        "El archivo no se descargó bien: prueba con otro enlace o nombre."
    ),
    "record_not_found": "No he encontrado este elemento en el historial.",
    "songs_not_found": "No he encontrado canciones: prueba con otro nombre.",

    # --- similar ---
    "similar_preparing": "⏳ Estoy buscando canciones parecidas...",
    "similar_llm_phase": "Buscando canciones parecidas...",
    "similar_resolve_phase": "Preparando la lista ({done}/{total})...",
    "similar_header": "🎧 Parecidas a «{title}»:\n",
    "similar_header_with_artist": "🎧 Parecidas a «{title} — {artist}»:\n",
    "similar_not_found": "No he encontrado canciones parecidas: prueba más tarde.",
    "nearby_header": "🎧 Cerca de «{title}» — elige una:\n",
    "nearby_header_with_artist": "🎧 Cerca de «{title} — {artist}» — elige una:\n",

    # --- favorites ---
    "liked_empty": "Todavía no has añadido nada a favoritos ❤️",
    "liked_header": "❤️ Tus favoritos:\n",
    "favorite_added": "Añadido a favoritos: {title}",
    "favorite_removed": "Eliminado de favoritos: {title}",
    "favorite_missing": "No he encontrado esta canción para añadirla a favoritos.",

    # --- top ---
    "top_header": "🏆 Las más populares ({period}):\n",
    "top_empty": "Todavía no hay estadísticas para este periodo.",
    "top_period_day": "24 horas",
    "top_period_week": "semana",
    "top_period_all": "todos los tiempos",

    # --- lyrics / artwork ---
    "lyrics_not_found": "No he encontrado la letra de esta canción.",
    "lyrics_header": "📝 {title}\n\n",
    "lyrics_header_with_artist": "📝 {title} — {artist}\n\n",
    "artwork_not_found": "No he encontrado la portada de esta canción.",
    "artwork_sending": "Preparando la portada...",

    # --- picks / inline ---
    "pick_expired": "Esta selección ha caducado: vuelve a buscar.",
    "pick_expired_short": "Esta selección ha caducado: inténtalo de nuevo.",
    "more_by_artist": "🎵 Más canciones de {artist}:\n",
    "inline_description": "{artist} — toca para descargar",

    # --- channel gate ---
    "gate_denied": (
        "Para usar el bot, únete primero al canal @{channel} 🙏\n\n"
        "https://t.me/{channel}\n\n"
        "Cuando te hayas unido, inténtalo de nuevo."
    ),
    "gate_alert": "Únete primero al canal.",

    # --- playlists ---
    "playlist_empty": "No he encontrado canciones en esta colección.",
    "playlist_default_name": "Lista de reproducción",
    "playlist_start": (
        "📋 Empezando la descarga: {name}\n"
        "Cantidad: {total} canciones\n\n"
        "/cancel para detener la tarea actual"
    ),
    "playlist_cancelled": "Detenido. Enviadas: {sent}/{total}",
    "playlist_rate_limited": (
        "Límite de velocidad ({minutes} minutos). Enviadas: {sent}/{total}"
    ),
    "playlist_summary": "Enviadas: {sent}/{total}",
    "playlist_summary_failed": "Enviadas: {sent}/{total} | Fallidas: {failed}",
    "playlist_zip_sending": "📦 Creando el ZIP ({count} canciones) — {name}...",
    "playlist_zip_caption": "📦 {name} — {count} canciones",

    # --- progress ---
    "progress_update": "📥 {label} {bar} {pct}%{counter}{detail_line}{eta_line}",
    "progress_counter": " — canción {current} de {total}",
    "progress_eta": "\n⏳ unos {m}:{s:02d}",
    "progress_done": "✅ {label} ha terminado.",
    "progress_done_with_summary": "✅ {label} ha terminado.\n{summary}",
    "progress_fail": "❌ {label} ha fallado.",
    "progress_fail_with_reason": "❌ {label} ha fallado.\n{reason}",

    # --- error reporting ---
    "error_report_button": "📩 Informar al soporte",
    "error_retry_button": "🔄 Reintentar",
    "error_retrying": "🔄 Reintentando...",
    "error_retry_unavailable": (
        "No se puede reintentar este error: envía otra vez el enlace o el nombre."
    ),
    "error_report_sent": "\n\n✅ Tu informe se ha registrado. ¡Gracias!",
    "error_report_already_sent": "Este error ya se había informado.",
    "error_report_rate_limited": "Límite de informes: inténtalo mañana.",

    # --- support chat ---
    "support_admin_prompt": (
        "Modo respuesta activo — informe #{report_id} (usuario {user_id})\n"
        "Cualquier mensaje que envíes llegará directamente al usuario.\n"
        "Fin de la conversación: /supportend"
    ),
    "support_user_message": (
        "📩 Mensaje del soporte de HiiT Radio\n\n"
        "{admin_text}\n\n"
        "Para responder: /support tu mensaje"
    ),
    "support_user_opened": (
        "El soporte te ha contactado por tu informe de error.\n"
        "Usa /support para responder; el resto de mensajes sigue sirviendo "
        "para descargar música."
    ),
    "support_user_closed": (
        "La conversación con el soporte ha terminado. "
        "Si sigues teniendo problemas, envía otro informe."
    ),
    "support_no_thread": (
        "No tienes ninguna conversación activa con el soporte.\n"
        "Usa primero el botón «📩 Informar al soporte» en un mensaje de error; "
        "cuando el soporte responda podrás escribir con /support."
    ),
    "support_usage": (
        "Uso: /support tu mensaje\n"
        "Solo funciona si el soporte ha respondido a tu informe de error."
    ),
    "support_admin_usage": (
        "Eres administrador.\n"
        "• Pulsa «Responder» en un informe de error y cualquier mensaje de texto "
        "irá al usuario\n"
        "• Fin: /supportend"
    ),
    "support_empty_message": "Mensaje vacío: escribe el texto después de /support.",
    "support_sent_admin": "✅ Mensaje enviado al usuario {user_id}.",
    "support_sent_user": "✅ Tu mensaje ha llegado al soporte.",
    "support_forward_to_admin": (
        "💬 Respuesta del usuario ({user_label}) — informe #{report_id}\n\n{text}"
    ),
    "support_send_failed_blocked": "Envío fallido: el usuario ha bloqueado el bot.",
    "support_send_failed": "Envío fallido: inténtalo más tarde.",
    "support_thread_ended_admin": "Conversación #{thread_id} cerrada.",
    "support_thread_ended_no_open": "No hay ninguna conversación abierta.",
    "support_reply_button": "💬 Responder al usuario",
    "support_end_button": "⏹ Terminar la conversación",
    "support_report_not_found": "Informe no encontrado o aún sin enviar.",

    # --- cookies (admin) ---
    "cookies_status_title": "🍪 Estado de las cookies de YouTube",
    "cookies_state_ok": "correcto",
    "cookies_state_bad": "defectuoso",
    "cookies_status_state": "Estado: {state}",
    "cookies_status_detail": "Detalles: {detail}",
    "cookies_status_path": "Ruta: {path}",
    "cookies_status_updated": "Última actualización: {updated}",
    "cookies_status_footer": (
        "Para actualizar, envía aquí el archivo cookies.txt como documento "
        "(exportación Netscape desde un navegador con sesión en youtube.com)."
    ),
    "cookies_accepted": "✅ cookies.txt actualizado.\nDetalles: {detail}",
    "cookies_accepted_backup": "\nLa versión anterior se guardó en cookies.txt.bak.",
    "cookies_rejected": (
        "❌ Este archivo de cookies no es válido y no se ha guardado.\n"
        "Detalles: {detail}\n\n"
        "Vuelve a exportarlo en formato Netscape con la sesión abierta en youtube.com."
    ),
    "cookies_too_large": "❌ El archivo es demasiado grande (más de {limit_kb} KB).",

    # --- track action buttons ---
    "btn_more_by_artist": "Más canciones",
    "btn_similar": "Canciones parecidas",
    "btn_lyrics": "Letra",
    "btn_artwork": "🖼 Portada",
    "btn_report_track": "⚠️ Informar problema",
    "track_report_sent": "✅ Gracias — tu informe se envió al soporte.",
    "track_report_user_message": "El usuario informó esta canción (pista incorrecta / no coincide con el enlace / otro problema).",
    "btn_favorite_add": "❤️ Favorito",
    "btn_favorite_remove": "💔 Quitar de favoritos",

    # --- search ---
    "prompt_search": "🔍 Envía el nombre de una canción o artista:",
    "prompt_artist": "🎙 Envía el nombre del artista:",
    "prompt_follow": "🔔 Envía el nombre del artista a seguir:",
    "prompt_support": "💬 Escribe tu mensaje para soporte:",
    "prompt_cancelled": "⏹ Entrada cancelada.",
    "search_usage": "Uso:\n/search nombre de la canción o del artista",
    "search_empty": "No he encontrado resultados: prueba con otra frase.",
    "search_header": "🔍 Resultados de búsqueda para «{query}»:",
    "search_hit_line": "{index}. [{kind}] {name}{sub}",
    "search_kind_track": "Canción",
    "search_kind_album": "Álbum",
    "search_kind_playlist": "Lista",
    "search_kind_artist": "Artista",

    # --- artist ---
    "artist_usage": "Uso:\n/artist nombre del artista",
    "artist_not_found": "No he encontrado al artista «{name}».",
    "artist_header": "🎤 {name}",
    "artist_top_header": "Mejores canciones:",
    "artist_albums_header": "Álbumes:",

    # --- quality ---
    "quality_hint_128": "Poco peso: ideal si tienes poco espacio",
    "quality_hint_192": "Equilibrado: buena calidad",
    "quality_hint_256": "Valor por defecto del bot",
    "quality_hint_320": "El mejor MP3",
    "quality_hint_original": "Sin conversión: el archivo original tal cual",
    "quality_status_kbps": "🎚 Calidad actual: {value} kbps",
    "quality_status_original": "🎚 Calidad actual: original (sin conversión)",
    "quality_status_footer": "Pulsa uno de los botones de abajo.",
    "quality_set_kbps": "✅ Calidad ajustada a {value} kbps.",
    "quality_set_original": "✅ Calidad ajustada a original (sin conversión).",
    "quality_invalid": "Calidad no válida. Opciones: 128 · 192 · 256 · 320 · original",

    # --- artist follow ---
    "follow_success": (
        "✅ Ya sigues a «{artist}»: te avisaré cuando saque un álbum nuevo."
    ),
    "unfollow_success": "🔕 Has dejado de seguir a «{artist}».",
    "already_following": "Ya sigues a «{artist}».",
    "not_following": "Aún no sigues a ningún artista — pulsa Seguir artista para empezar!",
    "following_header": "🎙 Artistas que sigues:",
    "follow_usage": "Uso:\n/follow nombre del artista",
    "btn_follow": "🔔 Seguir a {artist}",
    "btn_unfollow": "🔕 Dejar de seguir a {artist}",
    "new_release_notification": (
        "🔔 ¡Nuevo lanzamiento!\n"
        "\n"
        "🎤 {artist}\n"
        "💿 {album}{date_line}\n"
        "\n"
        "Pulsa el botón de abajo para descargar el álbum 👇"
    ),
    "new_release_date_line": "\n📅 {date}",

    # --- main menu ---
    "menu_follow": "🔔 Seguir artista",
    "menu_support": "💬 Soporte",
    "menu_search": "🔎 Buscar canción",
    "menu_artist": "🎙 Explorar artista",
    "menu_quality": "🎛 Calidad de audio",
    "menu_help": "📚 Guía completa",
    "menu_history": "🕐 Historial de descargas",
    "menu_liked": "💖 Favoritos",
    "menu_top": "🔥 Las más populares",
    "menu_discover": "🎯 Para ti",
    "menu_following": "🔔 Mis artistas",
    "menu_invite": "🎁 Invitar a un amigo",
    "menu_premium": "💠 Premium",
    "menu_aboutme": "🤖 Sobre el bot",
    "menu_cancel": "⛔ Cancelar tarea actual",
    "menu_back": "🔙 Volver al menú",
    "menu_lang": "🌐 Idioma",
    "menu_admin": "🛠 Admin",
    "menu_admin_back": "🔙 Panel admin",
    "admin_menu_text": "🛠 Panel de administración — elige una herramienta:",
    "admin_stats": "📊 Estadísticas",
    "admin_report": "📈 Panel",
    "admin_reports": "📋 Reportes de usuarios",
    "admin_users": "👥 Usuarios",
    "admin_creds": "🔑 Credenciales",
    "admin_cookies": "🍪 Cookies",
    "admin_export": "📤 Exportar",
    "admin_viplog": "🧪 Registro VIP",
    "admin_broadcast": "📣 Difusión",
    "admin_channelid": "🆔 ID del canal",
    "admin_grant": "➕ Conceder",
    "admin_topup": "💰 Recarga",
    "admin_broadcast_usage": "Uso: /broadcast <mensaje>",
    "admin_grant_usage": "Uso: /grant <user_id> <premium|unlimited> <days>",
    "admin_topup_usage": "Uso: /topup <user_id> [amount]",
    "admin_channelid_usage": (
        "Reenvía aquí un mensaje del canal VIP (conservando el nombre del remitente),\n"
        "o envía /channelid dentro de ese canal."
    ),

    # --- language selection ---
    "lang_choose": "🌐 Elige el idioma del bot:",
    "lang_set": "✅ Idioma ajustado a {lang_name}.",
    "lang_name_fa": "فارسی",
    "lang_name_en": "English",
    "lang_name_fr": "Français",
    "lang_name_es": "Español",
    "lang_name_ru": "Русский",
    "lang_name_it": "Italiano",
}
