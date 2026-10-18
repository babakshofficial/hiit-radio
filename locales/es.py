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
    "platform_shazam": "Shazam",
    "platform_cache": "Caché",
    "platform_community": "Comunidad",

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
        "(Spotify · Apple Music · Deezer · Shazam · YouTube · SoundCloud) "
        "o escribe el nombre de una canción; yo me encargo del resto.\n\n"
        "Empieza con los botones de abajo 👇"
    ),
    "cmd_start": "Abrir menú principal",
    "cmd_search": "Buscar una canción",
    "cmd_artist": "Explorar artista",
    "cmd_follow": "Seguir artista",
    "cmd_following": "Artistas seguidos",
    "cmd_history": "Historial de descargas",
    "cmd_liked": "Favoritos",
    "cmd_top": "Más populares",
    "cmd_discover": "Recomendaciones",
    "cmd_quality": "Calidad de audio",
    "cmd_premium": "Estado Premium",
    "cmd_invite": "Invitar a un amigo",
    "cmd_submit": "Enviar tu canción",
    "cmd_uploads": "Tus envíos",
    "cmd_support": "Soporte",
    "cmd_lang": "Cambiar idioma",
    "cmd_help": "Guía del bot",
    "cmd_aboutme": "Sobre HiiT Radio",
    "cmd_stop": "Cancelar descarga",
    "cmd_admin": "Panel admin",
    "cmd_stats": "Estadísticas",
    "cmd_report": "Panel de uso",
    "cmd_reports": "Informes de usuarios",
    "cmd_users": "Lista de usuarios",
    "cmd_user": "Detalle de usuario",
    "cmd_export": "Exportar base de datos",
    "cmd_cookies": "Estado cookies YouTube",
    "cmd_creds": "Estado credenciales",
    "cmd_broadcast": "Mensaje a todos",
    "cmd_grant": "Dar Premium",
    "cmd_topup": "Recargar cuota",
    "cmd_supportend": "Cerrar sesión soporte",

    "help_text": (
        "¿Cómo se usa?\n\n"
        "1. Envía un enlace de canción, álbum o lista\n"
        "   (Spotify · Apple Music · Deezer · Shazam · YouTube · SoundCloud)\n"
        "2. O escribe el nombre de la canción y del artista\n"
        "3. Usa los botones de abajo para buscar, artistas, calidad y más\n"
        "4. O en línea: {bot_inline} nombre de la canción — en cualquier chat\n\n"
        "Límite diario gratuito: 10 descargas (premium: {premium_daily_limit}).\n"
        "Envía /stop en cualquier momento para detener una descarga."
    ),
    "aboutme_text": (
        "🎙 Sobre HiiT Radio\n"
        "\n"
        "Soy {developer_name} y creé este bot para que descargar música sea más fácil.\n"
        "\n"
        "📻 Canal: {channel}{developer_line}\n"
        "\n"
        "¿Qué puede hacer?\n"
        "• Enlaces de Spotify / Apple / Deezer / Shazam / YouTube / SoundCloud\n"
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
        "Espera a que terminen o deténlas con /stop."
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
    "grant_user_notice": (
        "🎁 Has recibido {days} días de {tier}, activo hasta {expires}.\n"
        "Envía una canción cuando quieras."
    ),
    "topup_user_notice": (
        "🎁 Se añadieron +{amount} descargas extra a tu cuenta para hoy ({day})."
    ),
    "grant_notify_failed": (
        "⚠️ No se pudo avisar al usuario — quizá tiene que pulsar Iniciar en el bot."
    ),

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
    "download_not_available": (
        "Esta canción aún no está en nuestras fuentes. Si tienes un enlace de YouTube o SoundCloud, envíalo directamente."
    ),
    "download_fail_network": "Problema de conexión — inténtalo de nuevo en un minuto.",
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
        "/stop para detener la tarea actual"
    ),
    "playlist_capped": (
        "Esta lista tiene {original} canciones. Enviaré solo las primeras {limit}."
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
    "progress_label_track": "Canción",
    "progress_label_download": "Descargando",
    "progress_label_playlist": "Lista",
    "progress_label_similar": "Similares",
    "progress_label_lyrics": "Letra",
    "progress_label_discover": "Descubrir",
    "progress_searching": "Buscando...",
    "progress_searching_n": "Buscando ({current}/{total})...",
    "progress_downloading": "Descargando...",
    "progress_downloading_audio": "Descargando el audio...",
    "progress_starting_download": "Iniciando la descarga...",
    "progress_preparing_link": "Preparando el enlace...",
    "progress_tagging": "Etiquetas y portada...",
    "progress_sending": "Enviando a Telegram...",
    "progress_ready": "Listo",
    "progress_cache_fast": "Envío rápido desde la caché...",
    "progress_ready_send": "Listo para enviar a Telegram...",
    "progress_search_download": "Buscando y descargando...",
    "progress_preparing": "Preparando...",
    "progress_fetching_lyrics": "Obteniendo la letra...",

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
    "btn_stop": "⏹ Detener",
    "btn_stop_ack": "Deteniendo…",
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
    "admin_changelog": "✨ Changelog",
    "admin_channelid": "🆔 ID del canal",
    "admin_grant": "➕ Conceder",
    "admin_topup": "💰 Recarga",
    "admin_user_music": "🎵 Música de usuarios",
    "menu_submit_music": "📤 Enviar música",
    "menu_my_submissions": "📋 Mis envíos",
    "admin_broadcast_usage": "Uso: /broadcast <mensaje>",
    "admin_grant_usage": "Uso: /grant <user_id> <premium|unlimited> <days>",
    "admin_topup_usage": "Uso: /topup <user_id> [amount]",
    "admin_channelid_usage": (
        "Reenvía aquí un mensaje del canal VIP (conservando el nombre del remitente),\n"
        "o envía /channelid dentro de ese canal."
    ),
    "awiz_cancel": "❌ Cancelar",
    "awiz_confirm": "✅ Confirmar",
    "awiz_cancelled": "Cancelado.",
    "awiz_invalid_user": "Eso no parece un ID de usuario. Envía un número, @username, o elige abajo.",
    "awiz_pick_user": "¿A quién?\nEnvía un ID o @username, o elige un usuario reciente.",
    "awiz_grant_tier": "Conceder a {user} — ¿qué plan?",
    "awiz_tier_premium": "⭐ Premium",
    "awiz_tier_unlimited": "♾ Ilimitado",
    "awiz_grant_days": "{user} → {tier}\n¿Cuántos días?",
    "awiz_days_7": "7 días",
    "awiz_days_30": "30 días",
    "awiz_days_90": "90 días",
    "awiz_days_custom": "Personalizado…",
    "awiz_grant_days_custom": "Envía el número de días (p. ej. 14).",
    "awiz_grant_confirm": "¿Conceder {tier} a {user} durante {days} días?",
    "awiz_topup_amount": "Recarga para {user} — ¿cuántas descargas extra?",
    "awiz_amt_default": "Predeterminado ({amount})",
    "awiz_amt_custom": "Personalizado…",
    "awiz_topup_amount_custom": "Envía el número de descargas extra.",
    "awiz_topup_confirm": "¿Añadir +{amount} descargas hoy para {user}?",
    "awiz_broadcast_ask": "Envía el texto del mensaje en el siguiente mensaje.",
    "awiz_broadcast_empty": "El mensaje estaba vacío — envía el texto.",
    "awiz_broadcast_confirm": "¿Enviar esto a {count} usuarios?\n\n{preview}",
    "awiz_broadcast_done": "Difusión terminada: enviados={sent}, fallidos={failed}",
    "awiz_viplog_ask": "Estado del registro VIP:\n\n{status}\n\n¿Enviar un mensaje de prueba al canal VIP?",
    "awiz_viplog_send": "🧪 Enviar prueba",
    "awiz_reports_ask": "Reportes de usuarios — ver la lista o enviar un ID.",
    "awiz_reports_list": "📋 Ver lista",
    "awiz_reports_id": "🔎 Introducir ID",
    "awiz_reports_ask_id": "Envía el ID del reporte (número).",
    "awiz_reports_bad_id": "ID no válido. Envía un número o vuelve atrás.",
    "awiz_user_ask": "Envía un ID o @username, o elige un usuario reciente.",
    "awiz_channelid_ask": (
        "Reenvía aquí un post del canal VIP (conservando el nombre del remitente).\n"
        "O envía /channelid en ese canal."
    ),
    "awiz_channelid_need_forward": "Necesito un post reenviado del canal. Reenvía uno, o cancela.",
    "awiz_export_ask": "¿Exportar toda la base de datos en JSON?",
    "awiz_export_go": "📤 Exportar ahora",

    # --- changelog broadcast ---
    "changelog_header": "✨ Novedades de HiiT Radio",
    "changelog_admin_prompt": (
        "Tras el reinicio hay notas de changelog pendientes.\n"
        "Edítalas si hace falta y pulsa Enviar — verás una tarjeta por idioma "
        "para revisar, editar, regenerar o enviar por separado. O Omite para archivar sin enviar."
    ),
    "changelog_admin_preview": "Vista previa de las notas:\n{preview}",
    "changelog_btn_send": "✅ Enviar changelog",
    "changelog_btn_edit": "✏️ Editar notas",
    "changelog_btn_skip": "⏭ Omitir",
    "changelog_btn_regenerate": "🔄 Regenerar",
    "changelog_review_started": "Revisa cada idioma abajo. Envía, omite, edita o regenera por idioma.",
    "changelog_lang_card": "{lang_name} ({count} usuarios)\n\n{header}\n\n{body}",
    "changelog_lang_sent": "✅ Enviado: {sent} ok, {failed} fallidos.",
    "changelog_lang_skipped": "⏭ Omitido para {lang_name}.",
    "changelog_lang_regenerating": "⏳ Regenerando {lang_name}…",
    "changelog_lang_edit_prompt": "Envía el mensaje de changelog en {lang_name} en tu próxima respuesta.",
    "changelog_lang_edit_saved": "✅ Texto de {lang_name} actualizado.",
    "changelog_lang_edit_empty": "Mensaje vacío — envía el texto de changelog en {lang_name}.",
    "changelog_lang_llm_failed": "No se pudo generar el texto para {lang_name}. Regenera o edita manualmente.",
    "changelog_all_done": (
        "Todos los idiomas gestionados. Enviados: {sent_langs}, omitidos: {skipped_langs}. "
        "Mensajes a usuarios: {sent} ok, {failed} fallidos."
    ),
    "changelog_edit_prompt": (
        "Envía las notas de changelog actualizadas en tu próximo mensaje.\n"
        "El inglés está bien — el LLM localizará para cada usuario.\n"
        "Tu mensaje reemplaza por completo las notas pendientes."
    ),
    "changelog_edit_saved": "✅ Notas actualizadas. Envía, edita de nuevo u omite.",
    "changelog_edit_empty": "Mensaje vacío — envía el texto de las notas para reemplazar el changelog.",
    "changelog_edit_failed": "No se pudieron guardar las notas. Inténtalo de nuevo.",
    "changelog_generating": "⏳ Generando changelogs localizados…",
    "changelog_done": "Difusión del changelog terminada: enviados={sent}, fallidos={failed}",
    "changelog_skipped": "Changelog omitido. Las notas pendientes se archivaron.",
    "changelog_empty": "No hay notas de changelog pendientes.",
    "changelog_llm_unavailable": (
        "Hay notas de changelog pendientes, pero el LLM no está configurado.\n"
        "Define LLM_API_KEY / LLM_API_BASE y reinicia — u omite para archivar."
    ),
    "changelog_llm_failed": (
        "No se pudo generar el changelog con el LLM. Las notas siguen pendientes."
    ),
    "changelog_busy": "Ya hay una difusión de changelog en curso.",
    "changelog_forbidden": "Solo el admin puede usar esto.",
    "changelog_btn_manual_new": "✍️ Nuevo changelog",
    "changelog_btn_skipped_list": "⏭ Changelogs omitidos ({count})",
    "changelog_skipped_header": "Changelogs omitidos ({count}) — página {page}/{pages}",
    "changelog_skipped_empty": "No hay changelogs omitidos.",
    "changelog_skipped_line": "#{id} · {date} · {langs} · {preview}",
    "changelog_skipped_detail": "Changelog omitido #{id}\nFecha: {date}\nEstado: {status}\nIdiomas: {langs}\n\n{notes}",
    "changelog_btn_skipped_send": "📣 Enviar",
    "changelog_btn_skipped_delete": "🗑 Eliminar",
    "changelog_btn_skipped_back": "⬅️ Volver",
    "changelog_skipped_deleted": "Changelog omitido eliminado.",
    "changelog_skipped_not_found": "Changelog omitido no encontrado.",
    "changelog_skipped_langs_all": "todos los idiomas",
    "changelog_skipped_status_skipped": "omitido",
    "changelog_skipped_status_partial": "enviado parcialmente",
    "changelog_skipped_reminder": "📌 Tienes {count} changelog(s) omitido(s). Abre Admin → Changelog para enviarlos.",
    "changelog_manual_intro": (
        "No hay notas pendientes en CHANGELOG_PENDING.md.\n"
        "Pulsa Nuevo changelog, o añade notas en el archivo del repo y reinicia."
    ),
    "changelog_manual_prompt": (
        "Envía las notas del changelog en tu próximo mensaje.\n"
        "El inglés está bien — el LLM localizará por idioma.\n"
        "Revisarás una tarjeta por idioma antes de enviar."
    ),
    "changelog_manual_empty": "Mensaje vacío — envía el texto del changelog.",
    "changelog_pending_admin_header": "Changelog pendiente (CHANGELOG_PENDING.md):",

    # --- user music submissions ---
    "usub_prompt_audio": "Envía un archivo de audio o un documento MP3 con tu canción.",
    "usub_prompt_title": "¿Título de la canción?",
    "usub_prompt_artist": "¿Nombre del artista?",
    "usub_prompt_genre": "Elige un género:",
    "usub_prompt_genre_other": "Escribe el género:",
    "usub_prompt_artwork": "Envía la portada (foto o archivo de imagen).",
    "usub_submitted": "✅ Enviada para revisión: {title} — {artist}",
    "usub_quota_max_pending": "Ya tienes 3 canciones esperando revisión. Retira una o espera al admin.",
    "usub_quota_daily": "Puedes enviar hasta 3 canciones al día. Inténtalo mañana.",
    "usub_bad_audio": "No pude usar ese archivo. Envía un MP3 u otro formato de audio.",
    "usub_audio_too_large": "El archivo es demasiado grande (máx. {max_mb} MB).",
    "usub_bad_artwork": "Envía una foto o imagen para la portada.",
    "usub_title_invalid": "El título debe tener entre 1 y 200 caracteres.",
    "usub_artist_invalid": "El artista debe tener entre 1 y 200 caracteres.",
    "usub_genre_invalid": "El género debe tener entre 1 y 80 caracteres.",
    "usub_session_expired": "La sesión de subida expiró — empieza de nuevo desde el menú.",
    "usub_not_found": "Envío no encontrado.",
    "usub_withdrawn": "Retirada — no se revisará.",
    "usub_no_artwork": "No hay portada guardada.",
    "usub_my_header": "📋 Tus canciones enviadas",
    "usub_my_empty": "Todavía no hay nada.",
    "usub_my_line": "• {title} — {artist} ({status})",
    "usub_detail": "🎵 {title}\n👤 {artist}\n🎼 {genre}\n📌 {status}",
    "usub_btn_submit": "📤 Enviar otra",
    "usub_btn_my_list": "📋 Mis envíos",
    "usub_btn_withdraw": "🗑 Retirar",
    "usub_status_pending": "Pendiente de revisión",
    "usub_status_approved": "Aprobada",
    "usub_status_rejected": "Rechazada",
    "usub_status_withdrawn": "Retirada",
    "usub_genre_pop": "Pop",
    "usub_genre_rock": "Rock",
    "usub_genre_hiphop": "Hip-Hop",
    "usub_genre_electronic": "Electrónica",
    "usub_genre_classical": "Clásica",
    "usub_genre_jazz": "Jazz",
    "usub_genre_folk": "Folk",
    "usub_genre_metal": "Metal",
    "usub_genre_rnb": "R&B",
    "usub_genre_other": "Otro",
    "usub_admin_new": "🎵 Nuevo envío de la comunidad #{id}\n{title} — {artist}\nDe {user_id} {username}",
    "usub_admin_review": "Revisar",
    "usub_admin_queue_header": "Música de usuarios pendiente ({count})",
    "usub_admin_queue_empty": "La cola está vacía.",
    "usub_admin_queue_line": "#{id} {title} — {artist} ({user})",
    "usub_admin_detail": "Envío #{id}\n{title} — {artist}\nGénero: {genre}\nEstado: {status}\nUsuario: {user_id} ({username})",
    "usub_admin_listen": "▶️ Escuchar",
    "usub_admin_artwork": "🖼 Portada",
    "usub_admin_approve": "✅ Aprobar",
    "usub_admin_reject": "❌ Rechazar",
    "usub_admin_back_queue": "📋 Cola",
    "usub_admin_approved_ok": "Aprobada #{id} — ya aparece en la búsqueda.",
    "usub_admin_reject_prompt": "Elige un motivo o envía un mensaje corto:",
    "usub_admin_rejected_ok": "Rechazada #{id}.",
    "usub_reject_low_quality": "Baja calidad",
    "usub_reject_rights": "Derechos / copyright",
    "usub_reject_metadata": "Metadatos incorrectos",
    "usub_approved_user": "✅ Tu canción “{title}” fue aprobada — todos pueden buscarla y descargarla.",
    "usub_approved_user_bonus": "✅ Tu canción “{title}” fue aprobada.\n+{bonus} descargas extra para hoy ({used}/{limit}).",
    "usub_rejected_user": "Tu envío “{title}” no fue aprobado.\nMotivo: {reason}",

    # --- language selection ---
    "lang_choose": "🌐 Elige el idioma del bot:",
    "lang_set": "✅ Idioma ajustado a {lang_name}.",
    "lang_name_fa": "فارسی",
    "lang_name_en": "English",
    "lang_name_fr": "Français",
    "lang_name_es": "Español",
    "lang_name_ru": "Русский",
    "lang_name_it": "Italiano",
    # --- admin ops (en fallback) ---
    "creds_header": 'Credentials status:',
    "creds_yt_section": '▶ YouTube (audio downloads — all links)',
    "creds_yt_browser": '  ✓ Browser: YTDLP_COOKIES_FROM_BROWSER={browser}',
    "creds_yt_live_ok": '  ✓ Live probe: {detail}',
    "creds_yt_live_fail": '  ✗ Live probe: {detail}',
    "creds_yt_browser_hint": '    → Log into youtube.com in Chrome; install secretstorage',
    "creds_yt_cookies_path": '  ✓ cookies.txt: {path}',
    "creds_yt_expired_hint": '    → Cookies expired — export from PC or send /cookies',
    "creds_yt_cookies_incomplete": '  ✗ cookies.txt exists but YouTube session is incomplete',
    "creds_yt_cookies_incomplete_hint": ('    → Log into youtube.com in the browser and re-export cookies\n    → Or set YTDLP_COOKIES_FROM_BROWSER=chrome and YTDLP_AUTO_REFRESH_COOKIES=1'),
    "creds_yt_cookies_missing": '  ✗ cookies.txt not found: {path}',
    "creds_yt_cookies_missing_hint": '    → Copy the file from your PC or export from the browser',
    "creds_spotify_section": '▶ Spotify API (metadata only — audio from YouTube)',
    "creds_spotify_ok": '  ✓ SPOTIFY_CLIENT_ID / SECRET set in .env',
    "creds_spotify_embed_note": '  (On 403 errors, embed is used for track/album/playlist links)',
    "creds_spotify_missing": '  ✗ Missing CLIENT_ID/SECRET — Spotify links use embed',
    "creds_result_ok": 'Result: YouTube is ready for downloads.',
    "creds_result_fail": 'Result: YouTube is not ready — fix cookies.txt.',
    "admin_stats_users": 'Users: {count}',
    "admin_stats_downloads": 'Downloads: {count}',
    "admin_stats_cache_rate": 'Cache hit rate: {pct} ({cached}/{total})',
    "admin_stats_top_artists": 'Top artists:',
    "admin_stats_top_songs": 'Top tracks:',
    "admin_stats_platforms": 'Platforms:',
    "admin_stats_skipped_changelog": 'Skipped changelogs (DB): {count}',
    "admin_stats_error_reports": 'Submitted user reports: {count}',
    "admin_stats_footer": 'Full dashboard: /report  ·  User reports: /reports',
    "admin_channelid_in_channel": ('Chat id: `{chat_id}`\n\nIn .env:\nVIP_LOG_CHANNEL_ID={chat_id}'),
    "admin_channelid_chat_id": 'Chat id: `{chat_id}`',
    "admin_channelid_type": 'Type: {chat_type}',
    "admin_channelid_title": 'Title: {title}',
    "admin_channelid_username": 'Username: @{username}',
    "admin_channelid_env_hint": ('\nAdd to .env:\nVIP_LOG_CHANNEL_ID={chat_id}'),
    "admin_vip_startup_broken": ('⚠️ VIP logging is not working.\nMake the bot a private channel admin, set VIP_LOG_CHANNEL_ID in .env, then run /viplogtest.'),
    "admin_vip_env_missing": 'VIP_LOG_CHANNEL_ID is not set in .env',
    "admin_vip_not_admin": 'Bot is not a channel administrator',
    "admin_vip_no_post": 'Bot cannot post messages in the channel',
    "admin_vip_not_member": 'Bot is not a chat member (status: {status})',
    "admin_vip_test_title": 'VIP log test',
    "admin_vip_test_channel": 'Channel: {title}',
    "admin_vip_test_id": 'Id: {chat_id}',
    "admin_vip_send_failed": 'Could not send message — check server logs',
    "admin_vip_test_ok": 'Test message sent to {title} (id={chat_id})',
    "admin_vip_forbidden_hint": '{error}. Make the bot a channel admin with post permission. Chat id must be numeric (e.g. -1001234567890).',
    "admin_vip_status_disabled": ('VIP logging is disabled.\n\n1. Add the bot as admin of a private channel (with post permission)\n2. In the channel run /channelid@HiiTRadioBot or forward a post\n3. In .env set:\nVIP_LOG_CHANNEL_ID=-100xxxxxxxxxx\n4. Restart the bot\n\nTest: /viplogtest'),
    "admin_vip_status_enabled": ('VIP_LOG_CHANNEL_ID={channel}\nParsed id: {parsed}\n\nSend a test: /viplogtest'),
    "vip_log_user_fmt": 'id={user_id}',
    "vip_evt_startup": 'Bot startup',
    "vip_evt_shutdown": 'Bot shutdown',
    "vip_evt_gate_denied": 'Blocked — not a channel member',
    "vip_evt_rate_limit": 'Rate limit',
    "vip_evt_dl_start": 'Download started',
    "vip_evt_cache_hit": 'Cache hit',
    "vip_evt_request": 'Request',
    "vip_evt_dl_ok": 'Download OK',
    "vip_evt_dl_fail": 'Download failed',
    "vip_evt_error": 'Error',
    "vip_evt_user_report": 'User error report',
    "vip_evt_pl_start": 'Playlist started',
    "vip_evt_pl_track": 'Playlist — track',
    "vip_evt_pl_done": 'Playlist finished',
    "vip_evt_broadcast": 'Broadcast',
    "vip_evt_cookie_health": 'YouTube cookie health',
    "vip_evt_button": 'Button',
    "vip_evt_inline": 'Inline',
    "vip_evt_command": 'Command',
    "vip_evt_message": 'Message',
    "vip_evt_channel_post": 'Channel post',
    "vip_evt_update": 'Update',
    "vip_fld_user": 'User',
    "vip_fld_chat": 'Chat',
    "vip_fld_data": 'Data',
    "vip_fld_search": 'Query',
    "vip_fld_text": 'Text',
    "vip_fld_kind": 'Kind',
    "vip_fld_gate": 'Gate',
    "vip_fld_vip_log": 'VIP log',
    "vip_fld_youtube": 'YouTube',
    "vip_fld_wait": 'Wait',
    "vip_fld_song": 'Track',
    "vip_fld_artist": 'Artist',
    "vip_fld_source": 'Source',
    "vip_fld_platform": 'Platform',
    "vip_fld_cached": 'Cached',
    "vip_fld_playlist": 'Playlist',
    "vip_fld_reason": 'Reason',
    "vip_fld_message": 'Message',
    "vip_fld_detail": 'Detail',
    "vip_fld_error_kind": 'Kind',
    "vip_fld_error_code": 'Code',
    "vip_fld_collection": 'Collection',
    "vip_fld_count": 'Count',
    "vip_fld_progress": 'Progress',
    "vip_fld_status": 'Status',
    "vip_fld_sent": 'Sent',
    "vip_fld_failed": 'Failed',
    "vip_fld_stop_reason": 'Stop reason',
    "vip_fld_health": 'Status',
    "vip_fld_channel": 'Channel',
    "vip_val_yes": 'yes',
    "vip_val_no": 'no',
    "vip_val_healthy": 'OK',
    "vip_val_unhealthy": 'FAIL',
    "vip_cookie_alert_detail": 'YouTube cookies look invalid or expired. Re-export cookies.txt with a logged-in session (non-empty SID / __Secure-*PSID).',
    "vip_fld_removed": 'Removed',
    "vip_evt_job_cancel": "User job cancelled",
    "vip_evt_cache_sweep": "Cache sweep",
    "vip_evt_cache_sweep_fallback": "Cache sweep (fallback)",
    "vip_evt_cache_sweep_startup": "Cache sweep (startup)",
    "vip_evt_progress": "Progress",
    "vip_fld_label": "Label",
}
