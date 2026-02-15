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
import time

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
        list[dict] — segments au format [{speaker, start, end, text}, ...]
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

    client_mistral = Mistral(api_key=config_transcription.api_key)

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

    logger.info(
        "transcrire_audio_via_voxtral: %d segments transcrits",
        len(segments_transcrits),
    )
    return segments_transcrits


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
        list[dict] — segments factices
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

    return segments_factices


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
        segments_transcrits: list[dict] avec {speaker, start, end, text}

    Returns:
        tuple (html_blocs_locuteurs, texte_brut)
    """
    # Mapper chaque locuteur unique a une couleur
    # / Map each unique speaker to a color
    locuteurs_uniques = []
    for segment in segments_transcrits:
        nom_locuteur = segment.get("speaker", "Inconnu")
        if nom_locuteur not in locuteurs_uniques:
            locuteurs_uniques.append(nom_locuteur)

    correspondance_couleurs = {}
    for index_locuteur, nom_locuteur in enumerate(locuteurs_uniques):
        correspondance_couleurs[nom_locuteur] = COULEURS_LOCUTEURS[
            index_locuteur % len(COULEURS_LOCUTEURS)
        ]

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
    # / Build HTML and plain text from groups
    blocs_html = []
    parties_texte_brut = []

    for groupe in groupes_locuteurs:
        nom_locuteur = groupe["speaker"]
        couleur_locuteur = correspondance_couleurs.get(nom_locuteur, "#6b7280")
        timestamp_debut = _formater_timestamp(groupe["start"])
        timestamp_fin = _formater_timestamp(groupe["end"])

        # Chaque phrase sur sa propre ligne avec <br>
        # / Each sentence on its own line with <br>
        texte_html = "<br>\n".join(groupe["phrases"])

        bloc_html = (
            f'<div class="speaker-block mb-4 pl-4 border-l-4 rounded-r" '
            f'style="border-color: {couleur_locuteur};">'
            f'<div class="flex items-center gap-2 mb-1">'
            f'<span class="font-semibold text-sm" style="color: {couleur_locuteur};">'
            f'{nom_locuteur}</span>'
            f'<span class="text-xs text-slate-400">{timestamp_debut} — {timestamp_fin}</span>'
            f'</div>'
            f'<p class="text-slate-700 leading-relaxed">{texte_html}</p>'
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


def _formater_timestamp(secondes):
    """
    Formate un nombre de secondes en MM:SS.
    / Formats a number of seconds as MM:SS.
    """
    minutes = int(secondes // 60)
    secondes_restantes = int(secondes % 60)
    return f"{minutes:02d}:{secondes_restantes:02d}"
