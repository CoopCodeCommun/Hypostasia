"""
Service de transcription audio avec diarisation pour Hypostasia.
/ Audio transcription service with diarization for Hypostasia.

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


def transcrire_audio_via_voxtral(chemin_fichier_audio, config_transcription):
    """
    Transcrit un fichier audio via l'API Mistral (Voxtral).
    / Transcribes an audio file via the Mistral API (Voxtral).

    Args:
        chemin_fichier_audio: Chemin absolu vers le fichier audio (str)
        config_transcription: Instance de TranscriptionConfig

    Returns:
        list[dict] — segments au format [{speaker, start, end, text}, ...]
    """
    from mistralai import Mistral

    logger.info(
        "transcrire_audio_via_voxtral: fichier=%s modele=%s langue=%s",
        chemin_fichier_audio, config_transcription.model_name, config_transcription.language,
    )

    client_mistral = Mistral(api_key=config_transcription.api_key)

    # Upload du fichier audio vers l'API Mistral
    # / Upload audio file to Mistral API
    with open(chemin_fichier_audio, "rb") as fichier_audio:
        fichier_uploade = client_mistral.files.upload(
            file={
                "content": fichier_audio,
                "file_name": chemin_fichier_audio.split("/")[-1],
            },
            purpose="audio",
        )

    # Recuperer l'URL signee du fichier uploade
    # / Get the signed URL of the uploaded file
    url_fichier_signe = client_mistral.files.get_signed_url(file_id=fichier_uploade.id)

    # Appel au modele de transcription avec diarisation
    # / Call the transcription model with diarization
    reponse_transcription = client_mistral.chat.complete(
        model=config_transcription.model_name,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": url_fichier_signe.url,
                    },
                    {
                        "type": "text",
                        "text": (
                            f"Transcris cet audio en {config_transcription.language}. "
                            "Pour chaque segment, identifie le locuteur et donne les timestamps. "
                            "Retourne UNIQUEMENT un JSON valide au format: "
                            '[{"speaker": "Locuteur 1", "start": 0.0, "end": 5.2, "text": "..."}, ...] '
                            "Sans markdown, sans explication, juste le JSON."
                        ),
                    },
                ],
            }
        ],
    )

    # Parser la reponse JSON du modele
    # / Parse the model's JSON response
    contenu_reponse = reponse_transcription.choices[0].message.content
    logger.debug("transcrire_audio_via_voxtral: reponse brute=%s", contenu_reponse[:500])

    import json
    # Nettoyer la reponse (enlever les backticks markdown si presents)
    # / Clean the response (remove markdown backticks if present)
    contenu_nettoye = contenu_reponse.strip()
    if contenu_nettoye.startswith("```"):
        # Retirer le premier bloc ```json ou ``` et le dernier ```
        # / Remove first ```json or ``` block and last ```
        lignes = contenu_nettoye.split("\n")
        lignes = lignes[1:]  # enlever la premiere ligne ```json
        if lignes and lignes[-1].strip() == "```":
            lignes = lignes[:-1]
        contenu_nettoye = "\n".join(lignes)

    segments_transcrits = json.loads(contenu_nettoye)

    logger.info(
        "transcrire_audio_via_voxtral: %d segments transcrits",
        len(segments_transcrits),
    )
    return segments_transcrits


def transcrire_audio_mock(chemin_fichier_audio, config_transcription):
    """
    Transcription factice pour le developpement et les tests.
    / Mock transcription for development and testing.

    Args:
        chemin_fichier_audio: Chemin absolu vers le fichier audio (str)
        config_transcription: Instance de TranscriptionConfig

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


def construire_html_diarise(segments_transcrits):
    """
    Construit le HTML colore par locuteur et le texte brut a partir des segments.
    / Builds speaker-colored HTML and plain text from transcription segments.

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

    # Construire le HTML pour chaque segment
    # / Build HTML for each segment
    blocs_html = []
    parties_texte_brut = []

    for segment in segments_transcrits:
        nom_locuteur = segment.get("speaker", "Inconnu")
        debut_secondes = segment.get("start", 0.0)
        fin_secondes = segment.get("end", 0.0)
        texte_segment = segment.get("text", "")
        couleur_locuteur = correspondance_couleurs.get(nom_locuteur, "#6b7280")

        # Formater les timestamps en MM:SS
        # / Format timestamps as MM:SS
        timestamp_debut = _formater_timestamp(debut_secondes)
        timestamp_fin = _formater_timestamp(fin_secondes)

        bloc_html = (
            f'<div class="speaker-block mb-4 pl-4 border-l-4 rounded-r" '
            f'style="border-color: {couleur_locuteur};">'
            f'<div class="flex items-center gap-2 mb-1">'
            f'<span class="font-semibold text-sm" style="color: {couleur_locuteur};">'
            f'{nom_locuteur}</span>'
            f'<span class="text-xs text-slate-400">{timestamp_debut} - {timestamp_fin}</span>'
            f'</div>'
            f'<p class="text-slate-700 leading-relaxed">{texte_segment}</p>'
            f'</div>'
        )
        blocs_html.append(bloc_html)

        # Texte brut avec marqueur locuteur
        # / Plain text with speaker marker
        parties_texte_brut.append(f"[{nom_locuteur} {timestamp_debut}] {texte_segment}")

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
