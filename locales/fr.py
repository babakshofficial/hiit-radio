"""French (fr) locale strings for the HiiT Radio bot."""

STRINGS = {
    # --- generic ---
    "unknown": "Inconnu",

    # --- platforms ---
    "platform_spotify": "Spotify",
    "platform_apple": "Apple Music",
    "platform_youtube": "YouTube",
    "platform_soundcloud": "SoundCloud",
    "platform_deezer": "Deezer",
    "platform_cache": "Cache",

    # --- download buttons ---
    "btn_redownload": "🔄 Télécharger à nouveau : {label}",
    "btn_download_indexed": "{index}. Télécharger « {label} »",
    "btn_download": "Télécharger « {label} »",

    # --- start / help / about ---
    "start_friend_name": "cher ami",
    "start_text": (
        "Salut {name} ! 🎶\n\n"
        "Bienvenue sur HiiT Radio — le bot de téléchargement de musique sans limites !\n\n"
        "Envoie simplement un lien de titre, d'album ou de playlist "
        "(Spotify · Apple Music · Deezer · YouTube · SoundCloud) "
        "ou écris le nom d'une chanson — je m'occupe du reste.\n\n"
        "Commence avec les boutons ci-dessous 👇"
    ),
    "help_text": (
        "Comment ça marche ?\n\n"
        "1. Envoie un lien de titre, d'album ou de playlist\n"
        "   (Spotify · Apple Music · Deezer · YouTube · SoundCloud)\n"
        "2. Ou écris le nom de la chanson et de l'artiste\n"
        "3. Utilise les boutons ci-dessous pour chercher, les artistes, la qualité, etc.\n"
        "4. Ou en inline : {bot_inline} nom du titre — dans n'importe quel chat\n\n"
        "Limite quotidienne gratuite : 10 téléchargements "
        "(premium : {premium_daily_limit})."
    ),
    "aboutme_text": (
        "🎙 À propos de HiiT Radio\n"
        "\n"
        "C'est moi, {developer_name}, qui ai créé ce bot pour te simplifier "
        "le téléchargement de musique.\n"
        "\n"
        "📻 Chaîne : {channel}{developer_line}\n"
        "\n"
        "Qu'est-ce qu'il sait faire ?\n"
        "• Liens Spotify / Apple / Deezer / YouTube / SoundCloud\n"
        "• Recherche et exploration d'artistes via les boutons du menu\n"
        "• Qualité audio depuis le menu\n"
        "• Suggestions personnalisées via Découvrir\n"
        "\n"
        "Une idée ou un bug ? Écris-moi — ça me fera plaisir 😊"
    ),
    "aboutme_developer_line": "\n💬 Développeur : {username}",

    # --- history ---
    "history_empty": (
        "Tu n'as encore rien téléchargé — envoie un titre et il apparaîtra ici 🎧"
    ),
    "history_header": "📜 Tes téléchargements récents :\n",

    # --- discover ---
    "discover_empty_history": (
        "Pour des suggestions personnalisées, télécharge d'abord quelques titres — "
        "puis lance /discover 🎧"
    ),
    "discover_not_configured": (
        "Les suggestions intelligentes ne sont pas actives pour le moment.\n"
        "Réessaie bientôt."
    ),
    "discover_preparing": "⏳ Je te prépare des suggestions...",
    "discover_llm_phase": "Je réfléchis à tes goûts...",
    "discover_resolve_phase": "Je retrouve les titres ({done}/{total})...",
    "discover_llm_error": (
        "Je n'ai pas réussi à proposer quelque chose — réessaie dans un instant 🙏"
    ),
    "discover_no_results": "Aucune nouvelle suggestion pour l'instant — réessaie plus tard.",
    "discover_header": "🎧 Sélection pour toi :\n",

    # --- cancel / jobs ---
    "cancel_ok": "⏹ Demande d'arrêt enregistrée — la tâche en cours va s'arrêter.",
    "cancel_ok_many": (
        "⏹ Demande d'arrêt enregistrée pour {count} tâches — elles vont s'arrêter."
    ),
    "cancel_no_job": "Aucune tâche active de ta part en ce moment.",
    "too_many_jobs": (
        "Tu ne peux pas lancer plus de {limit} tâches en même temps.\n"
        "Attends qu'elles se terminent ou arrête-les avec /cancel."
    ),
    "download_cancelled": "Arrêté.",
    "work_cancelled": "Tâche annulée.",

    # --- preview ---
    "preview_caption": "🎧 Aperçu de 30 secondes",
    "preview_caption_title": "🎧 Aperçu de 30 secondes\n{title}",
    "preview_caption_full": "🎧 Aperçu de 30 secondes\n{title} — {artist}",

    # --- quota / tiers ---
    "rate_limit": (
        "Tu as atteint la limite de téléchargement — reviens dans {minutes} minutes 🙏"
    ),
    "tier_free": "Gratuit",
    "tier_premium": "Premium",
    "tier_unlimited": "Illimité",
    "quota_exceeded": (
        "Tu as atteint la limite de téléchargements du jour ({used}/{limit}) — "
        "formule : {tier}.\n"
        "Tu peux augmenter la limite du jour avec les Stars Telegram, "
        "passer en premium ou inviter 3 amis."
    ),

    # --- premium status ---
    "premium_status_title": "⭐ État de l'abonnement",
    "premium_plan": "Formule : {tier}",
    "premium_expires": "Expiration : {expires}",
    "premium_limit_unlimited": "Limite du jour : illimitée",
    "premium_limit_today": "Téléchargements aujourd'hui : {used}/{limit}",
    "premium_day": "Date : {day}",
    "premium_footer": (
        "Pass journalier : +{topup} téléchargements | "
        "Premium hebdo/mensuel : {premium_daily} par jour"
    ),

    # --- invite / referral ---
    "invite_status": (
        "🎁 Inviter un ami\n"
        "Progression : {toward}/{needed} (total confirmé : {credited})\n"
        "En attente d'adhésion à la chaîne : {pending}\n\n"
        "Pour chaque groupe de 3 nouveaux amis qui arrivent via ton lien et "
        "rejoignent la chaîne, tu reçois +{topup} téléchargements aujourd'hui.\n\n"
        "Lien d'invitation :\n{link}"
    ),
    "referral_topup_granted": (
        "🎉 Tes trois invitations sont complètes — +{amount} téléchargements ajoutés "
        "à ton compte aujourd'hui.\n"
        "Vois ta prochaine étape avec /invite."
    ),

    # --- payments ---
    "payment_failed": "Le paiement n'a pas abouti — réessaie depuis /premium.",
    "payment_already_processed": "Ce paiement a déjà été appliqué.",
    "payment_bonus_ok": "✅ +{amount} téléchargements activés pour aujourd'hui ({day}).",
    "payment_premium_ok": "✅ Ton abonnement {tier} est actif jusqu'au {expires}.",
    "btn_buy_daypass": "🔓 +{amount} téléchargements aujourd'hui — {stars}⭐",
    "btn_buy_weekly": "⭐ Premium 7 jours — {stars}⭐",
    "btn_buy_monthly": "⭐ Premium 30 jours — {stars}⭐",
    "btn_invite": "🎁 Inviter un ami",

    # --- admin grants ---
    "grant_ok": "✅ Utilisateur {user_id} : {tier} jusqu'au {expires}",
    "topup_ok": "✅ Utilisateur {user_id} : +{amount} pour {day}",

    # --- download flow ---
    "searching": "⏳ Je cherche ton titre...",
    "downloading": "⏳ Téléchargement en cours...",
    "metadata_not_found": (
        "Aucun résultat — renvoie le lien ou le nom du titre 🙏"
    ),
    "not_music_query": (
        "Ça ne ressemble pas à un nom de titre — envoie un lien musical "
        "ou « artiste - titre »"
    ),
    "collection_not_found": (
        "Je n'ai pas reconnu cet album ou cette playlist — vérifie le lien et renvoie-le."
    ),
    "send_failed": "L'envoi du titre a échoué — réessaie s'il te plaît 🙏",
    "download_not_found": (
        "Version complète introuvable — essaie peut-être avec un autre nom."
    ),
    "download_fail_bot_check": (
        "Le téléchargement a échoué — réessaie dans un instant ou envoie un autre nom."
    ),
    "download_fail_timeout": (
        "Le téléchargement a été trop long et a été interrompu — réessaie s'il te plaît 🙏"
    ),
    "download_fail_invalid": (
        "Le fichier n'a pas été téléchargé correctement — essaie un autre lien ou nom."
    ),
    "record_not_found": "Cet élément ne figure pas dans ton historique.",
    "songs_not_found": "Aucun titre trouvé — essaie un autre nom.",

    # --- similar ---
    "similar_preparing": "⏳ Je cherche des titres similaires...",
    "similar_llm_phase": "Recherche de titres similaires...",
    "similar_resolve_phase": "Préparation de la liste ({done}/{total})...",
    "similar_header": "🎧 Similaire à « {title} » :\n",
    "similar_header_with_artist": "🎧 Similaire à « {title} — {artist} » :\n",
    "similar_not_found": "Aucun titre similaire trouvé — réessaie plus tard.",
    "nearby_header": "🎧 Proche de « {title} » — choisis-en un :\n",
    "nearby_header_with_artist": "🎧 Proche de « {title} — {artist} » — choisis-en un :\n",

    # --- favorites ---
    "liked_empty": "Tu n'as encore rien ajouté à tes favoris ❤️",
    "liked_header": "❤️ Tes favoris :\n",
    "favorite_added": "Ajouté aux favoris : {title}",
    "favorite_removed": "Retiré des favoris : {title}",
    "favorite_missing": "Ce titre n'a pas été trouvé pour les favoris.",

    # --- top ---
    "top_header": "🏆 Les plus populaires ({period}) :\n",
    "top_empty": "Pas encore de statistiques pour cette période.",
    "top_period_day": "24 heures",
    "top_period_week": "semaine",
    "top_period_all": "tous les temps",

    # --- lyrics / artwork ---
    "lyrics_not_found": "Paroles introuvables pour ce titre.",
    "lyrics_header": "📝 {title}\n\n",
    "lyrics_header_with_artist": "📝 {title} — {artist}\n\n",
    "artwork_not_found": "Pochette introuvable pour ce titre.",
    "artwork_sending": "Préparation de la pochette...",

    # --- picks / inline ---
    "pick_expired": "Cette sélection a expiré — relance une recherche.",
    "pick_expired_short": "Cette sélection a expiré — réessaie.",
    "more_by_artist": "🎵 Plus de titres de {artist} :\n",
    "inline_description": "{artist} — touche pour télécharger",

    # --- channel gate ---
    "gate_denied": (
        "Pour utiliser le bot, rejoins d'abord la chaîne @{channel} 🙏\n\n"
        "https://t.me/{channel}\n\n"
        "Une fois inscrit, réessaie."
    ),
    "gate_alert": "Rejoins d'abord la chaîne.",

    # --- playlists ---
    "playlist_empty": "Aucun titre trouvé dans cette collection.",
    "playlist_default_name": "Playlist",
    "playlist_start": (
        "📋 Début du téléchargement : {name}\n"
        "Nombre : {total} titres\n\n"
        "/cancel pour arrêter la tâche en cours"
    ),
    "playlist_cancelled": "Arrêté. Envoyés : {sent}/{total}",
    "playlist_rate_limited": (
        "Limite de débit ({minutes} minutes). Envoyés : {sent}/{total}"
    ),
    "playlist_summary": "Envoyés : {sent}/{total}",
    "playlist_summary_failed": "Envoyés : {sent}/{total} | Échecs : {failed}",
    "playlist_zip_sending": "📦 Création du ZIP ({count} titres) — {name}...",
    "playlist_zip_caption": "📦 {name} — {count} titres",

    # --- progress ---
    "progress_update": "📥 {label} {bar} {pct}%{counter}{detail_line}{eta_line}",
    "progress_counter": " — titre {current} sur {total}",
    "progress_eta": "\n⏳ environ {m}:{s:02d}",
    "progress_done": "✅ {label} terminé.",
    "progress_done_with_summary": "✅ {label} terminé.\n{summary}",
    "progress_fail": "❌ {label} a échoué.",
    "progress_fail_with_reason": "❌ {label} a échoué.\n{reason}",

    # --- error reporting ---
    "error_report_button": "📩 Signaler au support",
    "error_retry_button": "🔄 Réessayer",
    "error_retrying": "🔄 Nouvelle tentative...",
    "error_retry_unavailable": (
        "Impossible de réessayer pour cette erreur — renvoie le lien ou le nom du titre."
    ),
    "error_report_sent": "\n\n✅ Ton signalement a été envoyé. Merci !",
    "error_report_already_sent": "Cette erreur a déjà été signalée.",
    "error_report_rate_limited": "Limite de signalements atteinte — réessaie demain.",

    # --- support chat ---
    "support_admin_prompt": (
        "Mode réponse actif — signalement #{report_id} (utilisateur {user_id})\n"
        "Tout message que tu envoies va directement à l'utilisateur.\n"
        "Fin de la conversation : /supportend"
    ),
    "support_user_message": (
        "📩 Message du support HiiT Radio\n\n"
        "{admin_text}\n\n"
        "Pour répondre : /support ton message"
    ),
    "support_user_opened": (
        "Le support t'a contacté au sujet de ton signalement d'erreur.\n"
        "Utilise /support pour répondre — les autres messages servent toujours "
        "à télécharger de la musique."
    ),
    "support_user_closed": (
        "La conversation avec le support est terminée. "
        "Si tu as encore un problème, envoie un nouveau signalement."
    ),
    "support_no_thread": (
        "Tu n'as pas de conversation active avec le support.\n"
        "Utilise d'abord le bouton « 📩 Signaler au support » sur un message d'erreur ; "
        "après la réponse du support, tu pourras écrire avec /support."
    ),
    "support_usage": (
        "Utilisation : /support ton message\n"
        "Cela fonctionne seulement si le support a répondu à ton signalement."
    ),
    "support_admin_usage": (
        "Tu es administrateur.\n"
        "• Appuie sur « Répondre » sur un signalement, puis tout message texte "
        "part vers l'utilisateur\n"
        "• Fin : /supportend"
    ),
    "support_empty_message": "Message vide — écris du texte après /support.",
    "support_sent_admin": "✅ Message envoyé à l'utilisateur {user_id}.",
    "support_sent_user": "✅ Ton message est bien arrivé au support.",
    "support_forward_to_admin": (
        "💬 Réponse de l'utilisateur ({user_label}) — signalement #{report_id}\n\n{text}"
    ),
    "support_send_failed_blocked": "Envoi échoué — l'utilisateur a bloqué le bot.",
    "support_send_failed": "Envoi échoué — réessaie plus tard.",
    "support_thread_ended_admin": "Conversation #{thread_id} fermée.",
    "support_thread_ended_no_open": "Aucune conversation ouverte.",
    "support_reply_button": "💬 Répondre à l'utilisateur",
    "support_end_button": "⏹ Terminer la conversation",
    "support_report_not_found": "Signalement introuvable ou pas encore envoyé.",

    # --- cookies (admin) ---
    "cookies_status_title": "🍪 État des cookies YouTube",
    "cookies_state_ok": "sain",
    "cookies_state_bad": "défectueux",
    "cookies_status_state": "État : {state}",
    "cookies_status_detail": "Détails : {detail}",
    "cookies_status_path": "Chemin : {path}",
    "cookies_status_updated": "Dernière mise à jour : {updated}",
    "cookies_status_footer": (
        "Pour mettre à jour, envoie ici le fichier cookies.txt en pièce jointe "
        "(export Netscape depuis un navigateur connecté à youtube.com)."
    ),
    "cookies_accepted": "✅ cookies.txt mis à jour.\nDétails : {detail}",
    "cookies_accepted_backup": (
        "\nLa version précédente a été enregistrée dans cookies.txt.bak."
    ),
    "cookies_rejected": (
        "❌ Ce fichier de cookies n'est pas valide et n'a pas été enregistré.\n"
        "Détails : {detail}\n\n"
        "Refais l'export Netscape en étant connecté à youtube.com."
    ),
    "cookies_too_large": "❌ Le fichier est trop volumineux (plus de {limit_kb} Ko).",

    # --- track action buttons ---
    "btn_more_by_artist": "Plus de titres",
    "btn_similar": "Titres similaires",
    "btn_lyrics": "Paroles",
    "btn_artwork": "🖼 Pochette",
    "btn_report_track": "⚠️ Signaler un problème",
    "track_report_sent": "✅ Merci — ton signalement a été envoyé au support.",
    "track_report_user_message": "L'utilisateur a signalé ce titre (mauvais morceau / ne correspond pas au lien / autre problème).",
    "btn_favorite_add": "❤️ Favori",
    "btn_favorite_remove": "💔 Retirer des favoris",

    # --- search ---
    "prompt_search": "🔍 Envoie un titre ou un nom d'artiste :",
    "prompt_artist": "🎙 Envoie le nom de l'artiste :",
    "prompt_follow": "🔔 Envoie le nom de l'artiste à suivre :",
    "prompt_support": "💬 Écris ton message pour le support :",
    "prompt_cancelled": "⏹ Saisie annulée.",
    "search_usage": "Utilisation :\n/search nom du titre ou de l'artiste",
    "search_empty": "Aucun résultat — essaie une autre formulation.",
    "search_header": "🔍 Résultats de recherche pour « {query} » :",
    "search_hit_line": "{index}. [{kind}] {name}{sub}",
    "search_kind_track": "Titre",
    "search_kind_album": "Album",
    "search_kind_playlist": "Playlist",
    "search_kind_artist": "Artiste",

    # --- artist ---
    "artist_usage": "Utilisation :\n/artist nom de l'artiste",
    "artist_not_found": "Artiste « {name} » introuvable.",
    "artist_header": "🎤 {name}",
    "artist_top_header": "Meilleurs titres :",
    "artist_albums_header": "Albums :",

    # --- quality ---
    "quality_hint_128": "Léger — idéal si tu manques d'espace",
    "quality_hint_192": "Équilibré — bonne qualité",
    "quality_hint_256": "Valeur par défaut du bot",
    "quality_hint_320": "Meilleur MP3",
    "quality_hint_original": "Sans conversion — le fichier source tel quel",
    "quality_status_kbps": "🎚 Qualité actuelle : {value} kbps",
    "quality_status_original": "🎚 Qualité actuelle : original (sans conversion)",
    "quality_status_footer": "Appuie sur un des boutons ci-dessous.",
    "quality_set_kbps": "✅ Qualité réglée sur {value} kbps.",
    "quality_set_original": "✅ Qualité réglée sur original (sans conversion).",
    "quality_invalid": "Qualité invalide. Options : 128 · 192 · 256 · 320 · original",

    # --- artist follow ---
    "follow_success": (
        "✅ Tu suis maintenant « {artist} » — je te préviens dès qu'un nouvel album sort !"
    ),
    "unfollow_success": "🔕 Tu ne suis plus « {artist} ».",
    "already_following": "Tu suis déjà « {artist} ».",
    "not_following": "Tu ne suis encore aucun artiste — appuie sur Suivre un artiste !",
    "following_header": "🎙 Artistes suivis :",
    "follow_usage": "Utilisation :\n/follow nom de l'artiste",
    "btn_follow": "🔔 Suivre {artist}",
    "btn_unfollow": "🔕 Ne plus suivre {artist}",
    "new_release_notification": (
        "🔔 Nouvelle sortie !\n"
        "\n"
        "🎤 {artist}\n"
        "💿 {album}{date_line}\n"
        "\n"
        "Appuie sur le bouton ci-dessous pour télécharger l'album 👇"
    ),
    "new_release_date_line": "\n📅 {date}",

    # --- main menu ---
    "menu_follow": "🔔 Suivre un artiste",
    "menu_support": "💬 Support",
    "menu_search": "🔎 Rechercher un titre",
    "menu_artist": "🎙 Explorer un artiste",
    "menu_quality": "🎛 Qualité audio",
    "menu_help": "📚 Guide complet",
    "menu_history": "🕐 Historique",
    "menu_liked": "💖 Favoris",
    "menu_top": "🔥 Les plus populaires",
    "menu_discover": "🎯 Pour toi",
    "menu_following": "🔔 Mes artistes",
    "menu_invite": "🎁 Inviter un ami",
    "menu_premium": "💠 Premium",
    "menu_aboutme": "🤖 À propos du bot",
    "menu_cancel": "⛔ Annuler la tâche en cours",
    "menu_back": "🔙 Retour au menu",
    "menu_lang": "🌐 Langue",

    # --- language selection ---
    "lang_choose": "🌐 Choisis la langue du bot :",
    "lang_set": "✅ Langue réglée sur {lang_name}.",
    "lang_name_fa": "فارسی",
    "lang_name_en": "English",
    "lang_name_fr": "Français",
    "lang_name_es": "Español",
    "lang_name_ru": "Русский",
    "lang_name_it": "Italiano",
}
