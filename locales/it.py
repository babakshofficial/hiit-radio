"""Italian (it) locale strings for the HiiT Radio bot."""

STRINGS = {
    # --- generic ---
    "unknown": "Sconosciuto",

    # --- platforms ---
    "platform_spotify": "Spotify",
    "platform_apple": "Apple Music",
    "platform_youtube": "YouTube",
    "platform_soundcloud": "SoundCloud",
    "platform_deezer": "Deezer",
    "platform_cache": "Cache",

    # --- download buttons ---
    "btn_redownload": "🔄 Scarica di nuovo: {label}",
    "btn_download_indexed": "{index}. Scarica «{label}»",
    "btn_download": "Scarica «{label}»",

    # --- start / help / about ---
    "start_friend_name": "amico",
    "start_text": (
        "Ciao {name}! 🎶\n\n"
        "Benvenuto su HiiT Radio — il bot per scaricare musica senza limiti!\n\n"
        "Basta inviare il link di un brano, di un album o di una playlist "
        "(Spotify · Apple Music · Deezer · YouTube · SoundCloud) "
        "oppure scrivere il nome di una canzone — al resto penso io.\n\n"
        "Inizia con i pulsanti qui sotto 👇"
    ),
    "help_text": (
        "Come si usa?\n\n"
        "1. Invia il link di un brano, di un album o di una playlist\n"
        "   (Spotify · Apple Music · Deezer · YouTube · SoundCloud)\n"
        "2. Oppure scrivi il nome del brano e dell'artista\n"
        "3. Usa i pulsanti qui sotto per cerca, artisti, qualità e altro\n"
        "4. Oppure inline: {bot_inline} nome del brano — in qualsiasi chat\n\n"
        "Limite giornaliero gratuito: 10 download "
        "(premium: {premium_daily_limit})."
    ),
    "aboutme_text": (
        "🎙 Info su HiiT Radio\n"
        "\n"
        "Questo bot l'ho creato io, {developer_name}, per farti scaricare musica "
        "più facilmente.\n"
        "\n"
        "📻 Canale: {channel}{developer_line}\n"
        "\n"
        "Cosa sa fare?\n"
        "• Link Spotify / Apple / Deezer / YouTube / SoundCloud\n"
        "• Ricerca e artisti dai pulsanti del menu\n"
        "• Qualità audio dal menu\n"
        "• Consigli personalizzati da Scopri\n"
        "\n"
        "Se hai un'idea o trovi un bug, scrivimi — mi fa piacere 😊"
    ),
    "aboutme_developer_line": "\n💬 Sviluppatore: {username}",

    # --- history ---
    "history_empty": (
        "Non hai ancora scaricato nulla — invia un brano e comparirà qui 🎧"
    ),
    "history_header": "📜 I tuoi download recenti:\n",

    # --- discover ---
    "discover_empty_history": (
        "Per i consigli personalizzati scarica prima qualche brano — "
        "poi premi /discover 🎧"
    ),
    "discover_not_configured": (
        "I consigli intelligenti non sono attivi al momento.\nRiprova a breve."
    ),
    "discover_preparing": "⏳ Sto preparando dei consigli per te...",
    "discover_llm_phase": "Sto ragionando sui tuoi gusti...",
    "discover_resolve_phase": "Sto cercando i brani ({done}/{total})...",
    "discover_llm_error": (
        "Adesso non riesco a darti consigli — riprova tra un po' 🙏"
    ),
    "discover_no_results": "Per ora non ho nuovi consigli — riprova più tardi.",
    "discover_header": "🎧 Scelti per te:\n",

    # --- cancel / jobs ---
    "cancel_ok": "⏹ Richiesta di stop registrata — l'operazione in corso si fermerà presto.",
    "cancel_ok_many": (
        "⏹ Richiesta di stop registrata per {count} operazioni — si fermeranno presto."
    ),
    "cancel_no_job": "In questo momento non hai operazioni attive.",
    "too_many_jobs": (
        "Non puoi eseguire più di {limit} operazioni contemporaneamente.\n"
        "Aspetta che finiscano oppure fermale con /cancel."
    ),
    "download_cancelled": "Fermato.",
    "work_cancelled": "Operazione annullata.",

    # --- preview ---
    "preview_caption": "🎧 Anteprima di 30 secondi",
    "preview_caption_title": "🎧 Anteprima di 30 secondi\n{title}",
    "preview_caption_full": "🎧 Anteprima di 30 secondi\n{title} — {artist}",

    # --- quota / tiers ---
    "rate_limit": (
        "Per ora hai raggiunto il limite di download — torna tra {minutes} minuti 🙏"
    ),
    "tier_free": "Gratuito",
    "tier_premium": "Premium",
    "tier_unlimited": "Illimitato",
    "quota_exceeded": (
        "Hai raggiunto il limite di download di oggi ({used}/{limit}) — piano: {tier}.\n"
        "Puoi alzare il limite di oggi con le Stelle di Telegram, "
        "passare a premium o invitare 3 amici."
    ),

    # --- premium status ---
    "premium_status_title": "⭐ Stato dell'abbonamento",
    "premium_plan": "Piano: {tier}",
    "premium_expires": "Scadenza: {expires}",
    "premium_limit_unlimited": "Limite di oggi: illimitato",
    "premium_limit_today": "Download di oggi: {used}/{limit}",
    "premium_day": "Data: {day}",
    "premium_footer": (
        "Pass giornaliero: +{topup} download | "
        "Premium settimanale/mensile: {premium_daily} al giorno"
    ),

    # --- invite / referral ---
    "invite_status": (
        "🎁 Invita un amico\n"
        "Avanzamento: {toward}/{needed} (totale confermato: {credited})\n"
        "In attesa di iscrizione al canale: {pending}\n\n"
        "Per ogni 3 nuovi amici che entrano dal tuo link e si iscrivono al canale, "
        "ricevi +{topup} download per oggi.\n\n"
        "Link di invito:\n{link}"
    ),
    "referral_topup_granted": (
        "🎉 Hai completato tre inviti — +{amount} download aggiunti al tuo "
        "account per oggi.\n"
        "Guarda il prossimo traguardo con /invite."
    ),

    # --- payments ---
    "payment_failed": "Il pagamento non è andato a buon fine — riprova da /premium.",
    "payment_already_processed": "Questo pagamento è già stato applicato.",
    "payment_bonus_ok": "✅ +{amount} download attivati per oggi ({day}).",
    "payment_premium_ok": "✅ L'abbonamento {tier} è attivo fino al {expires}.",
    "btn_buy_daypass": "🔓 +{amount} download oggi — {stars}⭐",
    "btn_buy_weekly": "⭐ Premium 7 giorni — {stars}⭐",
    "btn_buy_monthly": "⭐ Premium 30 giorni — {stars}⭐",
    "btn_invite": "🎁 Invita un amico",

    # --- admin grants ---
    "grant_ok": "✅ Utente {user_id}: {tier} fino al {expires}",
    "topup_ok": "✅ Utente {user_id}: +{amount} per {day}",

    # --- download flow ---
    "searching": "⏳ Sto cercando il tuo brano...",
    "downloading": "⏳ Sto scaricando...",
    "metadata_not_found": (
        "Nessun risultato — invia di nuovo il link o il nome del brano 🙏"
    ),
    "not_music_query": (
        "Non sembra il nome di un brano — invia un link musicale "
        "oppure «artista - brano»"
    ),
    "collection_not_found": (
        "Non ho riconosciuto questo album o questa playlist — controlla il link e "
        "invialo di nuovo."
    ),
    "send_failed": "Non è stato possibile inviare il brano — riprova per favore 🙏",
    "download_not_found": (
        "Versione completa non trovata — forse cercando con un altro nome va meglio."
    ),
    "download_fail_bot_check": (
        "Ora il download non è andato — riprova tra un po' o invia un altro nome."
    ),
    "download_fail_timeout": (
        "Il download è durato troppo e si è interrotto — riprova per favore 🙏"
    ),
    "download_fail_invalid": (
        "Il file non è stato scaricato correttamente — prova un altro link o nome."
    ),
    "record_not_found": "Questo elemento non è stato trovato nella cronologia.",
    "songs_not_found": "Nessun brano trovato — prova con un altro nome.",

    # --- similar ---
    "similar_preparing": "⏳ Sto cercando brani simili...",
    "similar_llm_phase": "Sto cercando brani simili...",
    "similar_resolve_phase": "Sto preparando la lista ({done}/{total})...",
    "similar_header": "🎧 Simili a «{title}»:\n",
    "similar_header_with_artist": "🎧 Simili a «{title} — {artist}»:\n",
    "similar_not_found": "Nessun brano simile trovato — riprova più tardi.",
    "nearby_header": "🎧 Vicino a «{title}» — scegline uno:\n",
    "nearby_header_with_artist": "🎧 Vicino a «{title} — {artist}» — scegline uno:\n",

    # --- favorites ---
    "liked_empty": "Non hai ancora aggiunto nulla ai preferiti ❤️",
    "liked_header": "❤️ I tuoi preferiti:\n",
    "favorite_added": "Aggiunto ai preferiti: {title}",
    "favorite_removed": "Rimosso dai preferiti: {title}",
    "favorite_missing": "Non ho trovato questo brano da aggiungere ai preferiti.",

    # --- top ---
    "top_header": "🏆 I più popolari ({period}):\n",
    "top_empty": "Per questo periodo non ci sono ancora statistiche.",
    "top_period_day": "24 ore",
    "top_period_week": "settimana",
    "top_period_all": "sempre",

    # --- lyrics / artwork ---
    "lyrics_not_found": "Testo di questo brano non trovato.",
    "lyrics_header": "📝 {title}\n\n",
    "lyrics_header_with_artist": "📝 {title} — {artist}\n\n",
    "artwork_not_found": "Copertina di questo brano non trovata.",
    "artwork_sending": "Sto preparando la copertina...",

    # --- picks / inline ---
    "pick_expired": "Questa selezione è scaduta — fai una nuova ricerca.",
    "pick_expired_short": "Questa selezione è scaduta — riprova.",
    "more_by_artist": "🎵 Altri brani di {artist}:\n",
    "inline_description": "{artist} — tocca per scaricare",

    # --- channel gate ---
    "gate_denied": (
        "Per usare il bot, iscriviti prima al canale @{channel} 🙏\n\n"
        "https://t.me/{channel}\n\n"
        "Dopo l'iscrizione, riprova."
    ),
    "gate_alert": "Iscriviti prima al canale.",

    # --- playlists ---
    "playlist_empty": "Nessun brano trovato in questa raccolta.",
    "playlist_default_name": "Playlist",
    "playlist_start": (
        "📋 Avvio del download: {name}\n"
        "Numero: {total} brani\n\n"
        "/cancel per fermare l'operazione in corso"
    ),
    "playlist_cancelled": "Fermato. Inviati: {sent}/{total}",
    "playlist_rate_limited": (
        "Limite di frequenza ({minutes} minuti). Inviati: {sent}/{total}"
    ),
    "playlist_summary": "Inviati: {sent}/{total}",
    "playlist_summary_failed": "Inviati: {sent}/{total} | Non riusciti: {failed}",
    "playlist_zip_sending": "📦 Sto creando lo ZIP ({count} brani) — {name}...",
    "playlist_zip_caption": "📦 {name} — {count} brani",

    # --- progress ---
    "progress_update": "📥 {label} {bar} {pct}%{counter}{detail_line}{eta_line}",
    "progress_counter": " — brano {current} di {total}",
    "progress_eta": "\n⏳ circa {m}:{s:02d}",
    "progress_done": "✅ {label} completato.",
    "progress_done_with_summary": "✅ {label} completato.\n{summary}",
    "progress_fail": "❌ {label} non riuscito.",
    "progress_fail_with_reason": "❌ {label} non riuscito.\n{reason}",

    # --- error reporting ---
    "error_report_button": "📩 Segnala all'assistenza",
    "error_retry_button": "🔄 Riprova",
    "error_retrying": "🔄 Nuovo tentativo...",
    "error_retry_unavailable": (
        "Per questo errore non si può riprovare — invia di nuovo il link o il nome."
    ),
    "error_report_sent": "\n\n✅ La tua segnalazione è stata registrata. Grazie!",
    "error_report_already_sent": "Questo errore è già stato segnalato.",
    "error_report_rate_limited": "Limite di segnalazioni — riprova domani.",

    # --- support chat ---
    "support_admin_prompt": (
        "Modalità risposta attiva — segnalazione #{report_id} (utente {user_id})\n"
        "Qualsiasi messaggio invii arriva direttamente all'utente.\n"
        "Fine della conversazione: /supportend"
    ),
    "support_user_message": (
        "📩 Messaggio dall'assistenza HiiT Radio\n\n"
        "{admin_text}\n\n"
        "Per rispondere: /support il tuo messaggio"
    ),
    "support_user_opened": (
        "L'assistenza ti ha contattato per la tua segnalazione di errore.\n"
        "Usa /support per rispondere — gli altri messaggi servono come sempre "
        "a scaricare musica."
    ),
    "support_user_closed": (
        "La conversazione con l'assistenza è terminata. "
        "Se hai ancora problemi, invia una nuova segnalazione."
    ),
    "support_no_thread": (
        "Non hai una conversazione attiva con l'assistenza.\n"
        "Usa prima il pulsante «📩 Segnala all'assistenza» su un messaggio di errore; "
        "dopo la risposta dell'assistenza potrai scrivere con /support."
    ),
    "support_usage": (
        "Uso: /support il tuo messaggio\n"
        "Funziona solo se l'assistenza ha risposto alla tua segnalazione."
    ),
    "support_admin_usage": (
        "Sei un amministratore.\n"
        "• Premi «Rispondi» su una segnalazione, poi ogni messaggio di testo "
        "va all'utente\n"
        "• Fine: /supportend"
    ),
    "support_empty_message": "Messaggio vuoto — scrivi il testo dopo /support.",
    "support_sent_admin": "✅ Messaggio inviato all'utente {user_id}.",
    "support_sent_user": "✅ Il tuo messaggio è arrivato all'assistenza.",
    "support_forward_to_admin": (
        "💬 Risposta dell'utente ({user_label}) — segnalazione #{report_id}\n\n{text}"
    ),
    "support_send_failed_blocked": "Invio non riuscito — l'utente ha bloccato il bot.",
    "support_send_failed": "Invio non riuscito — riprova più tardi.",
    "support_thread_ended_admin": "Conversazione #{thread_id} chiusa.",
    "support_thread_ended_no_open": "Non c'è nessuna conversazione aperta.",
    "support_reply_button": "💬 Rispondi all'utente",
    "support_end_button": "⏹ Termina la conversazione",
    "support_report_not_found": "Segnalazione non trovata o non ancora inviata.",

    # --- cookies (admin) ---
    "cookies_status_title": "🍪 Stato dei cookie YouTube",
    "cookies_state_ok": "integro",
    "cookies_state_bad": "non integro",
    "cookies_status_state": "Stato: {state}",
    "cookies_status_detail": "Dettagli: {detail}",
    "cookies_status_path": "Percorso: {path}",
    "cookies_status_updated": "Ultimo aggiornamento: {updated}",
    "cookies_status_footer": (
        "Per aggiornare, invia qui il file cookies.txt come documento "
        "(esportazione Netscape da un browser con l'accesso attivo su youtube.com)."
    ),
    "cookies_accepted": "✅ cookies.txt aggiornato.\nDettagli: {detail}",
    "cookies_accepted_backup": (
        "\nLa versione precedente è stata salvata in cookies.txt.bak."
    ),
    "cookies_rejected": (
        "❌ Questo file di cookie non è valido e non è stato salvato.\n"
        "Dettagli: {detail}\n\n"
        "Rifai l'esportazione Netscape mentre sei collegato a youtube.com."
    ),
    "cookies_too_large": "❌ Il file è troppo grande (oltre {limit_kb} KB).",

    # --- track action buttons ---
    "btn_more_by_artist": "Altri brani",
    "btn_similar": "Brani simili",
    "btn_lyrics": "Testo",
    "btn_artwork": "🖼 Copertina",
    "btn_report_track": "⚠️ Segnala problema",
    "track_report_sent": "✅ Grazie — la segnalazione è stata inviata al supporto.",
    "track_report_user_message": "L'utente ha segnalato questo brano (brano sbagliato / non corrisponde al link / altro problema).",
    "btn_favorite_add": "❤️ Preferiti",
    "btn_favorite_remove": "💔 Rimuovi dai preferiti",

    # --- search ---
    "prompt_search": "🔍 Invia il nome di un brano o artista:",
    "prompt_artist": "🎙 Invia il nome dell'artista:",
    "prompt_follow": "🔔 Invia il nome dell'artista da seguire:",
    "prompt_support": "💬 Scrivi il messaggio per il supporto:",
    "prompt_cancelled": "⏹ Input annullato.",
    "search_usage": "Uso:\n/search nome del brano o dell'artista",
    "search_empty": "Nessun risultato — prova con un'altra frase.",
    "search_header": "🔍 Risultati della ricerca per «{query}»:",
    "search_hit_line": "{index}. [{kind}] {name}{sub}",
    "search_kind_track": "Brano",
    "search_kind_album": "Album",
    "search_kind_playlist": "Playlist",
    "search_kind_artist": "Artista",

    # --- artist ---
    "artist_usage": "Uso:\n/artist nome dell'artista",
    "artist_not_found": "Artista «{name}» non trovato.",
    "artist_header": "🎤 {name}",
    "artist_top_header": "Brani migliori:",
    "artist_albums_header": "Album:",

    # --- quality ---
    "quality_hint_128": "Leggero — adatto se hai poco spazio",
    "quality_hint_192": "Equilibrato — buona qualità",
    "quality_hint_256": "Valore predefinito del bot",
    "quality_hint_320": "Il miglior MP3",
    "quality_hint_original": "Senza conversione — il file originale così com'è",
    "quality_status_kbps": "🎚 Qualità attuale: {value} kbps",
    "quality_status_original": "🎚 Qualità attuale: original (senza conversione)",
    "quality_status_footer": "Tocca uno dei pulsanti qui sotto.",
    "quality_set_kbps": "✅ Qualità impostata su {value} kbps.",
    "quality_set_original": "✅ Qualità impostata su original (senza conversione).",
    "quality_invalid": "Qualità non valida. Opzioni: 128 · 192 · 256 · 320 · original",

    # --- artist follow ---
    "follow_success": (
        "✅ Ora segui «{artist}» — ti avviso quando pubblica un nuovo album!"
    ),
    "unfollow_success": "🔕 Non segui più «{artist}».",
    "already_following": "Segui già «{artist}».",
    "not_following": "Non segui ancora nessun artista — tocca Segui artista per iniziare!",
    "following_header": "🎙 Artisti che segui:",
    "follow_usage": "Uso:\n/follow nome dell'artista",
    "btn_follow": "🔔 Segui {artist}",
    "btn_unfollow": "🔕 Non seguire più {artist}",
    "new_release_notification": (
        "🔔 Nuova uscita!\n"
        "\n"
        "🎤 {artist}\n"
        "💿 {album}{date_line}\n"
        "\n"
        "Premi il pulsante qui sotto per scaricare l'album 👇"
    ),
    "new_release_date_line": "\n📅 {date}",

    # --- main menu ---
    "menu_follow": "🔔 Segui artista",
    "menu_support": "💬 Supporto",
    "menu_search": "🔎 Cerca un brano",
    "menu_artist": "🎙 Esplora artista",
    "menu_quality": "🎛 Qualità audio",
    "menu_help": "📚 Guida completa",
    "menu_history": "🕐 Cronologia download",
    "menu_liked": "💖 Preferiti",
    "menu_top": "🔥 I più popolari",
    "menu_discover": "🎯 Per te",
    "menu_following": "🔔 I miei artisti",
    "menu_invite": "🎁 Invita un amico",
    "menu_premium": "💠 Premium",
    "menu_aboutme": "🤖 Info sul bot",
    "menu_cancel": "⛔ Annulla operazione in corso",
    "menu_back": "🔙 Torna al menu",
    "menu_lang": "🌐 Lingua",
    "menu_admin": "🛠 Admin",
    "menu_admin_back": "🔙 Pannello admin",
    "admin_menu_text": "🛠 Pannello admin — scegli uno strumento:",
    "admin_stats": "📊 Statistiche",
    "admin_report": "📈 Dashboard",
    "admin_reports": "📋 Segnalazioni utenti",
    "admin_users": "👥 Utenti",
    "admin_creds": "🔑 Credenziali",
    "admin_cookies": "🍪 Cookie",
    "admin_export": "📤 Esporta",
    "admin_viplog": "🧪 Log VIP",
    "admin_broadcast": "📣 Broadcast",
    "admin_channelid": "🆔 ID canale",
    "admin_grant": "➕ Grant",
    "admin_topup": "💰 Ricarica",
    "admin_broadcast_usage": "Uso: /broadcast <messaggio>",
    "admin_grant_usage": "Uso: /grant <user_id> <premium|unlimited> <days>",
    "admin_topup_usage": "Uso: /topup <user_id> [amount]",
    "admin_channelid_usage": (
        "Inoltra qui un post del canale VIP (mantenendo il nome del mittente),\n"
        "oppure invia /channelid nel canale."
    ),

    # --- language selection ---
    "lang_choose": "🌐 Scegli la lingua del bot:",
    "lang_set": "✅ Lingua impostata su {lang_name}.",
    "lang_name_fa": "فارسی",
    "lang_name_en": "English",
    "lang_name_fr": "Français",
    "lang_name_es": "Español",
    "lang_name_ru": "Русский",
    "lang_name_it": "Italiano",
}
