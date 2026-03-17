"""
Service de transcription audio avec diarisation pour Hypostasia.
/ Audio transcription service with diarization for Hypostasia.

Utilise l'endpoint dedie client.audio.transcriptions.complete() de Mistral.
/ Uses the dedicated client.audio.transcriptions.complete() endpoint from Mistral.

Supporte : Voxtral (Mistral API) et Mock (simulation).
Retourne des segments par locuteur avec timestamps.
/ Supports: Voxtral (Mistral API) and Mock (simulation).
Returns per-speaker segments with timestamps.
"""

import logging
import os
import time
from html import escape as html_escape

logger = logging.getLogger(__name__)

# Palette de 10 couleurs Tailwind pour les locuteurs
# / 10 Tailwind color palette for speakers
COULEURS_LOCUTEURS = [
    "#3b82f6",  # blue-500
    "#ef4444",  # red-500
    "#10b981",  # emerald-500
    "#f59e0b",  # amber-500
    "#8b5cf6",  # violet-500
    "#ec4899",  # pink-500
    "#06b6d4",  # cyan-500
    "#f97316",  # orange-500
    "#14b8a6",  # teal-500
    "#6366f1",  # indigo-500
]

# Fonds pales correspondant a chaque couleur de locuteur (opacite ~10%)
# / Pale backgrounds matching each speaker color (opacity ~10%)
FONDS_PALES_LOCUTEURS = [
    "#eff6ff",  # blue-50
    "#fef2f2",  # red-50
    "#ecfdf5",  # emerald-50
    "#fffbeb",  # amber-50
    "#f5f3ff",  # violet-50
    "#fdf2f8",  # pink-50
    "#ecfeff",  # cyan-50
    "#fff7ed",  # orange-50
    "#f0fdfa",  # teal-50
    "#eef2ff",  # indigo-50
]


def transcrire_audio_via_voxtral(chemin_fichier_audio, config_transcription, max_locuteurs=5, langue=""):
    """
    Transcrit un fichier audio via l'API Mistral (endpoint audio.transcriptions).
    / Transcribes an audio file via the Mistral API (audio.transcriptions endpoint).

    Utilise l'endpoint dedie avec diarisation native et timestamps par segment.
    Note : les parametres language et timestamp_granularities sont incompatibles
    dans l'API Mistral — on privilegie language quand il est specifie.
    / Uses the dedicated endpoint with native diarization and segment timestamps.
    Note: language and timestamp_granularities are incompatible in the Mistral API
    — we prioritize language when specified.

    Args:
        chemin_fichier_audio: Chemin absolu vers le fichier audio (str)
        config_transcription: Instance de TranscriptionConfig
        max_locuteurs: Nombre maximum de locuteurs attendus (int)
        langue: Code langue ISO (str, vide = detection automatique)

    Returns:
        dict — {"model": str, "text": str, "segments": [{speaker, start, end, text}, ...]}
    """
    from mistralai import Mistral

    # Utiliser la langue choisie par l'utilisateur, ou celle de la config, ou vide (auto)
    # / Use user-chosen language, or config language, or empty (auto-detect)
    langue_effective = langue or ""

    logger.info(
        "transcrire_audio_via_voxtral: fichier=%s modele=%s langue=%s max_locuteurs=%d",
        chemin_fichier_audio, config_transcription.model_name,
        langue_effective or "auto", max_locuteurs,
    )

    # Cle API : priorite au champ DB, fallback sur la variable d'environnement
    # Si aucune cle n'est disponible, erreur explicite avant d'appeler l'API
    # / API key: DB field takes priority, fallback to environment variable
    # / If no key is available, raise explicit error before calling the API
    cle_api_mistral = config_transcription.api_key or os.environ.get("MISTRAL_API_KEY", "")
    if not cle_api_mistral:
        raise ValueError(
            "Clé API Mistral manquante. "
            "Renseignez MISTRAL_API_KEY dans .env ou dans l'admin (TranscriptionConfig)."
        )
    client_mistral = Mistral(api_key=cle_api_mistral)

    # Determiner si la diarisation est activee dans la config
    # / Determine if diarization is enabled in the config
    diarisation_activee = config_transcription.diarization_enabled

    # Construire les parametres de l'appel API
    # Contraintes Mistral :
    #   - diarize=True exige timestamp_granularities=["segment"]
    #   - language et timestamp_granularities sont incompatibles
    # Donc : quand diarize=True, on envoie toujours les timestamps et jamais language
    # / Build API call parameters
    # Mistral constraints:
    #   - diarize=True requires timestamp_granularities=["segment"]
    #   - language and timestamp_granularities are incompatible
    # So: when diarize=True, always send timestamps and never language
    parametres_transcription = {
        "model": config_transcription.model_name,
        "diarize": diarisation_activee,
    }

    if diarisation_activee:
        # Diarisation active : timestamps obligatoires, language interdit
        # / Diarization on: timestamps required, language forbidden
        parametres_transcription["timestamp_granularities"] = ["segment"]
    elif langue_effective:
        # Pas de diarisation, langue specifiee : pas de timestamps
        # / No diarization, language specified: no timestamps
        parametres_transcription["language"] = langue_effective
    else:
        # Pas de diarisation, detection auto : timestamps par segment
        # / No diarization, auto-detect: segment timestamps
        parametres_transcription["timestamp_granularities"] = ["segment"]

    # Appel a l'endpoint de transcription dedie (pas chat.complete)
    # / Call the dedicated transcription endpoint (not chat.complete)
    with open(chemin_fichier_audio, "rb") as fichier_audio:
        reponse_transcription = client_mistral.audio.transcriptions.complete(
            file={
                "content": fichier_audio,
                "file_name": chemin_fichier_audio.split("/")[-1],
            },
            **parametres_transcription,
        )

    # Convertir les segments de la reponse en format interne
    # / Convert response segments to internal format
    segments_transcrits = []

    if reponse_transcription.segments:
        for segment_api in reponse_transcription.segments:
            # speaker_id est None si diarize=False
            # / speaker_id is None if diarize=False
            identifiant_locuteur = getattr(segment_api, "speaker_id", None)
            nom_locuteur = identifiant_locuteur if identifiant_locuteur else "Locuteur"

            segment_interne = {
                "speaker": nom_locuteur,
                "start": segment_api.start,
                "end": segment_api.end,
                "text": segment_api.text.strip(),
            }
            segments_transcrits.append(segment_interne)
    else:
        # Pas de segments mais du texte brut — creer un segment unique
        # / No segments but raw text — create a single segment
        segments_transcrits.append({
            "speaker": "Locuteur",
            "start": 0.0,
            "end": 0.0,
            "text": reponse_transcription.text,
        })

    # Construire le dict complet au format Voxtral (model + text + segments)
    # / Build the full Voxtral-format dict (model + text + segments)
    texte_complet = reponse_transcription.text or " ".join(
        segment["text"] for segment in segments_transcrits
    )
    resultat_complet = {
        "model": config_transcription.model_name,
        "text": texte_complet,
        "segments": segments_transcrits,
    }

    logger.info(
        "transcrire_audio_via_voxtral: %d segments transcrits",
        len(segments_transcrits),
    )
    return resultat_complet


def transcrire_audio_mock(chemin_fichier_audio, config_transcription, max_locuteurs=5, langue=""):
    """
    Transcription factice pour le developpement et les tests.
    / Mock transcription for development and testing.

    Args:
        chemin_fichier_audio: Chemin absolu vers le fichier audio (str)
        config_transcription: Instance de TranscriptionConfig
        max_locuteurs: Nombre maximum de locuteurs attendus (int)
        langue: Code langue ISO (str, non utilise en mock)

    Returns:
        dict — {"model": str, "text": str, "segments": [{speaker, start, end, text}, ...]}
    """
    logger.info("transcrire_audio_mock: simulation pour %s", chemin_fichier_audio)

    # Simuler un delai de traitement / Simulate processing delay
    time.sleep(3)

    segments_factices = [
        {"speaker": "Locuteur 1", "start": 0.0, "end": 8.5, "text": "Bonjour et bienvenue dans cette discussion. Nous allons aborder aujourd'hui le sujet de l'intelligence artificielle et ses applications dans le domaine de la recherche."},
        {"speaker": "Locuteur 2", "start": 8.5, "end": 18.2, "text": "Merci pour cette introduction. Je pense que l'IA represente une revolution majeure, notamment dans la facon dont nous analysons les textes et extrayons des connaissances."},
        {"speaker": "Locuteur 1", "start": 18.2, "end": 29.0, "text": "Exactement. Et c'est precisement ce que nous essayons de faire avec Hypostasia : permettre une analyse fine et structuree des contenus textuels."},
        {"speaker": "Locuteur 3", "start": 29.0, "end": 42.5, "text": "Si je peux ajouter quelque chose, je dirais que la diarisation est un element cle. Pouvoir identifier qui dit quoi dans une conversation audio ouvre des possibilites considerables pour l'analyse argumentative."},
        {"speaker": "Locuteur 2", "start": 42.5, "end": 55.0, "text": "Tout a fait. La combinaison de la transcription automatique avec l'extraction d'entites permet de creer une representation riche du contenu audio."},
        {"speaker": "Locuteur 1", "start": 55.0, "end": 65.3, "text": "Pour conclure, je dirais que nous n'en sommes qu'au debut. Les outils comme Voxtral ouvrent la voie a une comprehension toujours plus fine du langage parle."},
    ]

    # Concatener le texte complet / Concatenate full text
    texte_complet = " ".join(segment["text"] for segment in segments_factices)

    return {
        "model": "mock-transcription",
        "text": texte_complet,
        "segments": segments_factices,
    }


def calculer_duree_audio(chemin_fichier_audio):
    """
    Calcule la duree d'un fichier audio en secondes.
    Essaie mutagen d'abord, puis ffprobe en fallback.
    / Computes the duration of an audio file in seconds.
    Tries mutagen first, then ffprobe as fallback.

    Args:
        chemin_fichier_audio: Chemin absolu vers le fichier audio (str)

    Returns:
        float — duree en secondes (0.0 si impossible a determiner)
    """
    import mutagen

    # Tentative 1 : mutagen (rapide, supporte la plupart des formats)
    # / Attempt 1: mutagen (fast, supports most formats)
    try:
        info_audio = mutagen.File(chemin_fichier_audio)
        if info_audio and info_audio.info and info_audio.info.length > 0:
            logger.debug("calculer_duree_audio: mutagen OK — %.1fs", info_audio.info.length)
            return info_audio.info.length
    except Exception as erreur_mutagen:
        logger.debug("calculer_duree_audio: mutagen a echoue — %s", erreur_mutagen)

    # Tentative 2 : ffprobe en fallback (supporte tous les formats)
    # / Attempt 2: ffprobe as fallback (supports all formats)
    import subprocess
    try:
        resultat_ffprobe = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                chemin_fichier_audio,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if resultat_ffprobe.returncode == 0 and resultat_ffprobe.stdout.strip():
            duree_ffprobe = float(resultat_ffprobe.stdout.strip())
            logger.debug("calculer_duree_audio: ffprobe OK — %.1fs", duree_ffprobe)
            return duree_ffprobe
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError) as erreur_ffprobe:
        logger.warning("calculer_duree_audio: ffprobe a echoue — %s", erreur_ffprobe)

    logger.warning("calculer_duree_audio: impossible de determiner la duree de %s", chemin_fichier_audio)
    return 0.0


def construire_html_diarise(segments_transcrits):
    """
    Construit le HTML colore par locuteur et le texte brut a partir des segments.
    Regroupe les segments consecutifs du meme locuteur en un seul bloc.
    / Builds speaker-colored HTML and plain text from transcription segments.
    Groups consecutive segments from the same speaker into a single block.

    Args:
        segments_transcrits: dict avec {model, text, segments} OU list[dict] avec {speaker, start, end, text}

    Returns:
        tuple (html_blocs_locuteurs, texte_brut)
    """
    # Extraction intelligente : si l'input est un dict avec 'segments', extraire la liste
    # / Smart extraction: if input is a dict with 'segments', extract the list
    if isinstance(segments_transcrits, dict) and "segments" in segments_transcrits:
        segments_transcrits = segments_transcrits["segments"]

    # Normaliser les segments : Voxtral brut utilise 'speaker_id' au lieu de 'speaker'
    # / Normalize segments: raw Voxtral uses 'speaker_id' instead of 'speaker'
    for segment in segments_transcrits:
        if "speaker" not in segment and "speaker_id" in segment:
            segment["speaker"] = segment["speaker_id"] or "Locuteur"

    # Mapper chaque locuteur unique a une couleur
    # / Map each unique speaker to a color
    locuteurs_uniques = []
    for segment in segments_transcrits:
        nom_locuteur = segment.get("speaker", "Inconnu")
        if nom_locuteur not in locuteurs_uniques:
            locuteurs_uniques.append(nom_locuteur)

    correspondance_couleurs = {}
    correspondance_fonds = {}
    correspondance_index = {}
    for index_locuteur, nom_locuteur in enumerate(locuteurs_uniques):
        correspondance_couleurs[nom_locuteur] = COULEURS_LOCUTEURS[
            index_locuteur % len(COULEURS_LOCUTEURS)
        ]
        correspondance_fonds[nom_locuteur] = FONDS_PALES_LOCUTEURS[
            index_locuteur % len(FONDS_PALES_LOCUTEURS)
        ]
        correspondance_index[nom_locuteur] = index_locuteur

    # Regrouper les segments consecutifs du meme locuteur
    # / Group consecutive segments from the same speaker
    groupes_locuteurs = []
    for segment in segments_transcrits:
        nom_locuteur = segment.get("speaker", "Inconnu")
        texte_segment = segment.get("text", "").strip()
        debut_secondes = segment.get("start", 0.0)
        fin_secondes = segment.get("end", 0.0)

        if not texte_segment:
            continue

        # Si le locuteur est le meme que le groupe precedent, on ajoute la phrase
        # / If speaker is the same as previous group, append the sentence
        if groupes_locuteurs and groupes_locuteurs[-1]["speaker"] == nom_locuteur:
            groupe_courant = groupes_locuteurs[-1]
            groupe_courant["phrases"].append(texte_segment)
            groupe_courant["end"] = fin_secondes
        else:
            # Nouveau locuteur : creer un nouveau groupe
            # / New speaker: create a new group
            groupes_locuteurs.append({
                "speaker": nom_locuteur,
                "start": debut_secondes,
                "end": fin_secondes,
                "phrases": [texte_segment],
            })

    # Construire le HTML et le texte brut a partir des groupes
    # Insere des marqueurs temporels toutes les 5 minutes
    # / Build HTML and plain text from groups
    # / Insert time markers every 5 minutes
    blocs_html = []
    parties_texte_brut = []
    prochain_marqueur_5min = 300  # 5 minutes en secondes / 5 minutes in seconds

    for index_bloc, groupe in enumerate(groupes_locuteurs):
        nom_locuteur = groupe["speaker"]
        couleur_locuteur = correspondance_couleurs.get(nom_locuteur, "#6b7280")
        fond_pale_locuteur = correspondance_fonds.get(nom_locuteur, "#f8fafc")
        index_locuteur = correspondance_index.get(nom_locuteur, 0)
        timestamp_debut = _formater_timestamp(groupe["start"])
        timestamp_fin = _formater_timestamp(groupe["end"])

        # Inserer un marqueur temporel si on a depasse le seuil de 5 min
        # / Insert a time marker if we passed the 5-min threshold
        while groupe["start"] >= prochain_marqueur_5min:
            marqueur_temps = _formater_timestamp(prochain_marqueur_5min)
            blocs_html.append(
                f'<div class="marqueur-temporel" data-time="{prochain_marqueur_5min}">'
                f'<span>{marqueur_temps}</span></div>'
            )
            prochain_marqueur_5min += 300

        # Chaque phrase est echappee HTML puis jointe par <br>
        # / Each sentence is HTML-escaped then joined with <br>
        phrases_echappees = [html_escape(phrase) for phrase in groupe["phrases"]]
        texte_html = "<br>\n".join(phrases_echappees)

        # Echapper le nom du locuteur pour eviter les injections XSS
        # / Escape speaker name to prevent XSS injection
        nom_locuteur_echappe = html_escape(nom_locuteur)

        # Le nom du locuteur est cliquable pour permettre le renommage
        # Le paragraphe de texte est cliquable pour passer en mode edition inline
        # / Speaker name is clickable to allow renaming
        # / Text paragraph is clickable to switch to inline edit mode
        bloc_html = (
            f'<div id="speaker-block-{index_bloc}" class="speaker-block mb-2 pl-4 rounded-r" '
            f'data-speaker="{nom_locuteur_echappe}" data-speaker-index="{index_locuteur}" '
            f'data-start="{groupe["start"]}" data-end="{groupe["end"]}" '
            f'style="background-color: {fond_pale_locuteur}; border-left: 3px solid {couleur_locuteur};">'
            f'<div class="flex items-center gap-2 mb-1">'
            f'<span class="speaker-name font-semibold text-sm cursor-pointer hover:underline" '
            f'style="color: {couleur_locuteur};" '
            f'data-speaker="{nom_locuteur_echappe}" data-block-index="{index_bloc}">'
            f'{nom_locuteur_echappe}</span>'
            f'<span class="text-xs text-slate-400">{timestamp_debut} — {timestamp_fin}</span>'
            f'</div>'
            f'<p class="texte-bloc-cliquable text-slate-700 leading-relaxed cursor-text hover:bg-slate-50 '
            f'rounded px-1 -mx-1 transition-colors" '
            f'data-block-index="{index_bloc}">{texte_html}</p>'
            f'</div>'
        )
        blocs_html.append(bloc_html)

        # Texte brut : toutes les phrases du groupe jointes par des retours a la ligne
        # / Plain text: all group sentences joined by newlines
        texte_brut_groupe = "\n".join(groupe["phrases"])
        parties_texte_brut.append(f"[{nom_locuteur} {timestamp_debut}]\n{texte_brut_groupe}")

    html_complet = "\n".join(blocs_html)
    texte_brut_complet = "\n\n".join(parties_texte_brut)

    return html_complet, texte_brut_complet


def construire_widgets_audio(transcription_raw, entites_extraction=None):
    """
    Construit les widgets audio : filtre par locuteur et timeline horizontale.
    / Builds audio widgets: speaker filter and horizontal timeline.

    Args:
        transcription_raw: dict avec {model, text, segments} OU list[dict]
        entites_extraction: queryset d'entites (optionnel, pour les points d'extraction)

    Returns:
        tuple (html_filtre_locuteurs, html_timeline)
    """
    # Extraction intelligente : si l'input est un dict avec 'segments', extraire la liste
    # / Smart extraction: if input is a dict with 'segments', extract the list
    segments = transcription_raw
    if isinstance(segments, dict) and "segments" in segments:
        segments = segments["segments"]

    if not segments:
        return "", ""

    # Normaliser les segments
    # / Normalize segments
    for segment in segments:
        if "speaker" not in segment and "speaker_id" in segment:
            segment["speaker"] = segment["speaker_id"] or "Locuteur"

    # Mapper les locuteurs uniques
    # / Map unique speakers
    locuteurs_uniques = []
    for segment in segments:
        nom_locuteur = segment.get("speaker", "Inconnu")
        if nom_locuteur not in locuteurs_uniques:
            locuteurs_uniques.append(nom_locuteur)

    # Regrouper les segments consecutifs (meme logique que construire_html_diarise)
    # / Group consecutive segments (same logic as construire_html_diarise)
    groupes_locuteurs = []
    for segment in segments:
        nom_locuteur = segment.get("speaker", "Inconnu")
        texte_segment = segment.get("text", "").strip()
        debut_secondes = segment.get("start", 0.0)
        fin_secondes = segment.get("end", 0.0)
        if not texte_segment:
            continue
        if groupes_locuteurs and groupes_locuteurs[-1]["speaker"] == nom_locuteur:
            groupes_locuteurs[-1]["phrases"].append(texte_segment)
            groupes_locuteurs[-1]["end"] = fin_secondes
        else:
            groupes_locuteurs.append({
                "speaker": nom_locuteur,
                "start": debut_secondes,
                "end": fin_secondes,
                "phrases": [texte_segment],
            })

    if not groupes_locuteurs:
        return "", ""

    # Duree totale de l'audio
    # / Total audio duration
    duree_totale = max(groupe["end"] for groupe in groupes_locuteurs)
    if duree_totale <= 0:
        return "", ""

    # --- Filtre locuteurs : pilules cliquables ---
    # / --- Speaker filter: clickable pills ---
    pilules_html = [
        '<button class="pilule-locuteur pilule-active" data-speaker-filter="tous">Tous</button>'
    ]
    for index_locuteur, nom_locuteur in enumerate(locuteurs_uniques):
        couleur_locuteur = COULEURS_LOCUTEURS[index_locuteur % len(COULEURS_LOCUTEURS)]
        nom_echappe = html_escape(nom_locuteur)
        pilules_html.append(
            f'<button class="pilule-locuteur" data-speaker-filter="{nom_echappe}">'
            f'<span class="pilule-pastille" style="background-color: {couleur_locuteur};"></span>'
            f'{nom_echappe}</button>'
        )
    html_filtre_locuteurs = (
        '<div id="filtre-locuteurs" class="filtre-locuteurs">'
        + "".join(pilules_html)
        + '</div>'
    )

    # --- Timeline audio : barre horizontale avec segments colores ---
    # / --- Audio timeline: horizontal bar with colored segments ---
    segments_timeline_html = []
    for index_bloc, groupe in enumerate(groupes_locuteurs):
        nom_locuteur = groupe["speaker"]
        index_locuteur = locuteurs_uniques.index(nom_locuteur)
        couleur_locuteur = COULEURS_LOCUTEURS[index_locuteur % len(COULEURS_LOCUTEURS)]
        nom_echappe = html_escape(nom_locuteur)

        # Calcul de la largeur proportionnelle
        # / Calculate proportional width
        duree_groupe = groupe["end"] - groupe["start"]
        pourcentage_largeur = (duree_groupe / duree_totale) * 100

        # Apercu du texte pour le tooltip (30 premiers caracteres)
        # / Text preview for tooltip (first 30 chars)
        apercu_texte = " ".join(groupe["phrases"])[:30]
        if len(" ".join(groupe["phrases"])) > 30:
            apercu_texte += "…"
        apercu_echappe = html_escape(apercu_texte)
        timestamp_debut = _formater_timestamp(groupe["start"])

        segments_timeline_html.append(
            f'<div class="timeline-segment" '
            f'data-speaker="{nom_echappe}" data-block-index="{index_bloc}" '
            f'data-start="{groupe["start"]}" data-end="{groupe["end"]}" '
            f'style="width: {pourcentage_largeur:.2f}%; background-color: {couleur_locuteur};" '
            f'title="{nom_echappe} {timestamp_debut} — {apercu_echappe}"></div>'
        )

    # Points d'extraction sur la timeline (si entites fournies)
    # / Extraction dots on timeline (if entities provided)
    dots_extraction_html = ""
    if entites_extraction:
        # Calcul du texte brut total pour l'interpolation position char → temps
        # / Calculate total plain text for char→time position interpolation
        texte_brut_total = " ".join(
            " ".join(groupe["phrases"]) for groupe in groupes_locuteurs
        )
        longueur_texte_total = len(texte_brut_total) if texte_brut_total else 1

        dots_html_parties = []
        for entite in entites_extraction:
            texte_entite = getattr(entite, "source_text", "") or ""
            if not texte_entite:
                continue
            # Trouver la position approximative dans le texte brut
            # / Find approximate position in plain text
            position_char = texte_brut_total.find(texte_entite[:50])
            if position_char < 0:
                continue
            # Interpolation position → pourcentage horizontal
            # / Interpolate position → horizontal percentage
            pourcentage_position = (position_char / longueur_texte_total) * 100
            dots_html_parties.append(
                f'<div class="timeline-extraction-dot" '
                f'style="left: {pourcentage_position:.1f}%;" '
                f'title="{html_escape(texte_entite[:40])}"></div>'
            )
        if dots_html_parties:
            dots_extraction_html = "".join(dots_html_parties)

    html_timeline = (
        '<div id="timeline-audio" class="timeline-audio">'
        '<div class="timeline-segments">'
        + "".join(segments_timeline_html)
        + '</div>'
        + (f'<div class="timeline-extraction-dots">{dots_extraction_html}</div>' if dots_extraction_html else '')
        + '</div>'
    )

    return html_filtre_locuteurs, html_timeline


def _formater_timestamp(secondes):
    """
    Formate un nombre de secondes en MM:SS ou H:MM:SS si >= 1 heure.
    / Formats a number of seconds as MM:SS or H:MM:SS if >= 1 hour.
    """
    heures = int(secondes // 3600)
    minutes = int((secondes % 3600) // 60)
    secondes_restantes = int(secondes % 60)
    if heures > 0:
        return f"{heures}:{minutes:02d}:{secondes_restantes:02d}"
    return f"{minutes:02d}:{secondes_restantes:02d}"
