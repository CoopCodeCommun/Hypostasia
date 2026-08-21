"""
Taches Celery pour le traitement asynchrone (audio + analyse textuelle).
/ Celery tasks for asynchronous processing (audio + text analysis).
"""

import hashlib
import logging
import os
import re
import time

from celery import shared_task

logger = logging.getLogger(__name__)


def notifier_tache_terminee(user_pk, tache_id, tache_type, status):
    """
    Push au client une notification de fin de tache via le NotificationConsumer.
    Appele uniquement a la fin d'une tache Celery (analyse / synthese / transcription).
    Format unifie : {tache_id, tache_type, status} pousse au group user_<pk>.
    / Push a task-end notification via NotificationConsumer.
    Called only at the end of a Celery task.

    Args:
        user_pk : pk du proprietaire de la tache
        tache_id : pk du job (ExtractionJob ou TranscriptionJob)
        tache_type : "analyse" | "synthese" | "transcription"
        status : "completed" | "error"
    """
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    couche_channels = get_channel_layer()
    if couche_channels is None:
        logger.debug("notifier_tache_terminee: channel layer non configure, skip")
        return

    async_to_sync(couche_channels.group_send)(
        f"user_{user_pk}",
        {
            "type": "tache_terminee",  # nom de la methode handler du consumer
            "tache_id": tache_id,
            "tache_type": tache_type,
            "status": status,
        },
    )


def notifier_la_file_d_ingestion(user_pk):
    """
    Dit a un utilisateur que la file d'ingestion a avance devant lui.
    / Tells a user the ingestion queue has moved ahead of them.

    LOCALISATION : front/tasks.py

    Le menu des taches affiche une position dans la file d'ingestion
    (front/views_taches.py). Cette position change quand l'ingestion de
    QUELQU'UN D'AUTRE se termine — un evenement dont le destinataire
    n'a, par construction, aucun moyen d'etre averti. Sans ce message,
    son « 3ᵉ dans la file » resterait affiche jusqu'a ce qu'il rouvre le
    menu de lui-meme, et un chiffre fige se lit comme une file bloquee.
    / The displayed queue position changes when SOMEONE ELSE's ingestion
    ends — an event the recipient could never learn about otherwise.

    Le message ne transporte rien : le client se contente d'aller
    relire son bouton et son menu. C'est deliberé — la position exacte
    se calcule cote serveur, au moment de la lecture, jamais ici.
    / The message carries no payload: the position is computed server
    side at read time, never pushed.

    :param user_pk: pk de l'utilisateur a prevenir
    """
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    couche_channels = get_channel_layer()
    if couche_channels is None:
        logger.debug(
            "notifier_la_file_d_ingestion: channel layer non configure, skip",
        )
        return

    async_to_sync(couche_channels.group_send)(
        f"user_{user_pk}",
        {"type": "file_ingestion_modifiee"},
    )


def _destinataires_de_notification(page):
    """
    Les destinataires d'une notification de fin de tache sur une note :
    son owner PLUS les proprietaires des carnets qui la contiennent,
    dedoublonnes (SPEC-corpus § 11, phase D).
    / Notification recipients: the note's owner PLUS the owners of the
    notebooks containing it, deduplicated.

    LOCALISATION : front/tasks.py

    Avant la phase D, seul page.owner (ou page.dossier.owner) etait
    notifie : le second carnet d'une note n'apprenait jamais qu'une
    synthese avait tourne.
    / Before phase D, only one owner was notified.

    :return: liste de pks d'utilisateurs ; [None] si aucun destinataire,
             pour conserver le comportement d'appel existant.
             / list of user pks; [None] when nobody, preserving the
             existing call behaviour.
    """
    pks_destinataires = set()
    if page.owner_id is not None:
        pks_destinataires.add(page.owner_id)

    pks_proprietaires_de_carnets = page.appartenances_dossiers.filter(
        dossier__owner__isnull=False,
    ).values_list("dossier__owner_id", flat=True)
    pks_destinataires.update(pks_proprietaires_de_carnets)

    if not pks_destinataires:
        return [None]
    return sorted(pks_destinataires)



@shared_task(bind=True)
def transcrire_audio_task(self, job_id, chemin_fichier_audio, max_locuteurs=5, langue=""):
    """
    Tache Celery : transcrit un fichier audio et met a jour la Page associee.
    / Celery task: transcribes an audio file and updates the associated Page.

    1. Charge le TranscriptionJob → status=PROCESSING
    2. Appelle Voxtral ou Mock selon le provider
    3. Construit le HTML diarise + texte brut
    4. Met a jour la Page (html_readability, text_readability, content_hash, status)
    5. Met a jour le Job (raw_result, status, processing_time)
    6. Supprime le fichier audio temporaire
    """
    from core.models import TranscriptionJob, TranscriptionJobStatus, PageStatus
    from front.services.transcription_audio import (
        transcrire_audio_via_voxtral,
        transcrire_audio_mock,
        construire_html_diarise,
    )

    debut_traitement = time.time()

    # Charger le job de transcription
    # / Load the transcription job
    try:
        job_transcription = TranscriptionJob.objects.select_related(
            "page", "transcription_config",
        ).get(pk=job_id)
    except TranscriptionJob.DoesNotExist:
        logger.error("transcrire_audio_task: job_id=%s introuvable", job_id)
        return

    page_associee = job_transcription.page
    config_transcription = job_transcription.transcription_config

    # Passer le job en PROCESSING
    # / Set job to PROCESSING
    job_transcription.status = TranscriptionJobStatus.PROCESSING
    job_transcription.celery_task_id = self.request.id or ""
    job_transcription.save(
        update_fields=["status", "celery_task_id", "updated_at"],
    )

    logger.info(
        "transcrire_audio_task: demarrage job=%s page=%s fichier=%s provider=%s",
        job_id, page_associee.pk, chemin_fichier_audio,
        config_transcription.provider if config_transcription else "aucun",
    )

    try:
        # Dispatcher selon le provider de la config
        # / Dispatch based on config provider
        if config_transcription and config_transcription.provider == "voxtral":
            segments_transcrits = transcrire_audio_via_voxtral(
                chemin_fichier_audio, config_transcription, max_locuteurs, langue,
            )
        else:
            # Mock par defaut / Mock by default
            segments_transcrits = transcrire_audio_mock(
                chemin_fichier_audio, config_transcription, max_locuteurs, langue,
            )

        # Construire le HTML colore et le texte brut
        # (construire_html_diarise accepte un dict ou une list)
        # / Build colored HTML and plain text
        # (construire_html_diarise accepts a dict or a list)
        html_diarise, texte_brut = construire_html_diarise(segments_transcrits)

        # Calculer le hash du contenu / Compute content hash
        hash_contenu = hashlib.sha256(texte_brut.encode("utf-8")).hexdigest()

        # Stocker le dict complet (model + text + segments) dans transcription_raw
        # / Store the full dict (model + text + segments) in transcription_raw
        page_associee.transcription_raw = segments_transcrits
        page_associee.html_readability = html_diarise
        page_associee.text_readability = texte_brut
        page_associee.content_hash = hash_contenu
        page_associee.status = PageStatus.COMPLETED
        page_associee.save(update_fields=[
            "transcription_raw", "html_readability", "text_readability",
            "content_hash", "status",
        ])

        # BASCULE AUDIO (decision D2, ordre 3) : la transcription est
        # posee, on la decoupe en tours de parole pour le moteur
        # ELEMENT. C'est le dernier flux a le rejoindre.
        #
        # Encadre comme les deux autres bascules : un broker en panne ne
        # doit pas faire echouer une transcription qui, elle, a reussi.
        # / Last flow to join the ELEMENT engine; a dead broker must not
        # fail a transcription that succeeded.
        try:
            from hypostasis_extractor.tasks_element import (
                ingerer_une_transcription_diarisee_en_elements,
            )
            ingerer_une_transcription_diarisee_en_elements.delay(
                page_associee.pk,
            )
        except Exception as erreur_de_file:
            logger.warning(
                "Page %s : transcription enregistree, mais la mise en file "
                "de l'ingestion par elements a echoue (%s). La page reste "
                "lisible ; relancer l'ingestion depuis la lecture.",
                page_associee.pk, erreur_de_file,
            )

        # Mettre a jour le Job / Update the Job
        duree_traitement = time.time() - debut_traitement
        job_transcription.raw_result = segments_transcrits
        job_transcription.status = TranscriptionJobStatus.COMPLETED
        job_transcription.processing_time_seconds = round(duree_traitement, 2)
        job_transcription.save(update_fields=[
            "raw_result", "status", "processing_time_seconds",
        ])

        logger.info(
            "transcrire_audio_task: termine job=%s page=%s segments=%d duree=%.1fs",
            job_id, page_associee.pk, len(segments_transcrits), duree_traitement,
        )

        # Notifier le navigateur que la tache est terminee (succes)
        # / Notify the browser that the task is complete (success)
        for pk_destinataire in _destinataires_de_notification(page_associee):
            if pk_destinataire is None:
                continue
            try:
                notifier_tache_terminee(
                    user_pk=pk_destinataire,
                    tache_id=job_transcription.pk,
                    tache_type="transcription",
                    status="completed",
                )
            except Exception as erreur_notification:
                # Une notification qui echoue ne doit pas faire echouer
                # une transcription qui, elle, a reussi : sinon ce
                # `except` serait rattrape par celui de la tache et
                # ecraserait le statut COMPLETED deja sauvegarde par
                # ERROR. / A failed notification must not fail a
                # transcription that succeeded.
                logger.warning(
                    "Job %s : notification de transcription non "
                    "transmise (%s).",
                    job_transcription.pk, erreur_notification,
                )

    except Exception as erreur_transcription:
        # En cas d'erreur, marquer le job et la page en erreur
        # / On error, mark both job and page as error
        duree_traitement = time.time() - debut_traitement
        message_erreur = str(erreur_transcription)

        logger.error(
            "transcrire_audio_task: erreur job=%s — %s",
            job_id, message_erreur, exc_info=True,
        )

        page_associee.status = PageStatus.ERROR
        page_associee.error_message = message_erreur[:1000]
        page_associee.save(update_fields=["status", "error_message"])

        job_transcription.status = TranscriptionJobStatus.ERROR
        job_transcription.error_message = message_erreur
        job_transcription.processing_time_seconds = round(duree_traitement, 2)
        job_transcription.save(update_fields=[
            "status", "error_message", "processing_time_seconds",
        ])

        # Notifier le navigateur que la tache est terminee (erreur)
        # / Notify the browser that the task is complete (error)
        for pk_destinataire in _destinataires_de_notification(page_associee):
            if pk_destinataire is None:
                continue
            try:
                notifier_tache_terminee(
                    user_pk=pk_destinataire,
                    tache_id=job_transcription.pk,
                    tache_type="transcription",
                    status="error",
                )
            except Exception as erreur_notification:
                # Meme principe : une notification en echec ne doit pas
                # remonter et perturber le traitement de l'erreur deja
                # en cours. / Same principle, on the error path.
                logger.warning(
                    "Job %s : notification d'erreur non transmise (%s).",
                    job_transcription.pk, erreur_notification,
                )

    finally:
        # Supprimer le fichier audio temporaire (qu'il y ait eu erreur ou non)
        # / Delete the temporary audio file (whether there was an error or not)
        if os.path.exists(chemin_fichier_audio):
            try:
                os.unlink(chemin_fichier_audio)
                logger.debug("transcrire_audio_task: fichier temp supprime %s", chemin_fichier_audio)
            except OSError as erreur_suppression:
                logger.warning(
                    "transcrire_audio_task: impossible de supprimer %s — %s",
                    chemin_fichier_audio, erreur_suppression,
                )


def _extractions_pour_la_synthese(page):
    """
    Les extractions qu'une synthese a le droit de citer sur cette note :
    TOUS ses jobs termines, non masquees (relecture D, B1 — le
    « dernier job » se faisait evincer par une extraction manuelle).
    / The extractions a synthesis may cite on this note: every completed
    job, not hidden.

    LOCALISATION : front/tasks.py

    UNE SEULE DEFINITION pour trois usages : le bloc HYPOSTASES du
    prompt, le perimetre passe a indexer_les_citations() (§ 4.4) et le
    perimetre FIGE sur la SyntheseDirigee (§ 8). Le filtre « citable »
    vit dans core/services/synthese.py ; ici on n'ajoute que l'ordre et
    les prefetch du prompt. Les extractions deja commentees (debattues)
    passent en tete.
    / One definition for the prompt block, the citation scope and the
    frozen § 8 scope; commented (debated) extractions first.
    """
    from django.db.models import Case, Value, When

    from core.services.synthese import extractions_citables_de_la_note

    return extractions_citables_de_la_note(
        page,
    ).prefetch_related("commentaires__user").order_by(
        Case(
            When(statut_debat="commente", then=Value(0)),
            default=Value(1),
        ),
        "pk",
    )


# LE CONTRAT DE CITATION (SPEC-synthese § 4.4).
#
# LA FORMULATION EST LE FOND, PAS LA FORME. Cette consigne a longtemps
# dit « chaque affirmation TIREE D'UNE HYPOSTASE se termine par le
# marqueur de sa source ». Elle conditionnait le marqueur a l'origine de
# la phrase — et une phrase de synthese generale n'est, du point de vue
# du modele, tiree d'aucune extraction EN PARTICULIER. Elle echappait
# donc a la regle sans la violer : `mistral-large` ecrivait UNE PHRASE
# SUR DEUX sans marqueur, dont des affirmations factuelles. Une phrase
# sans marqueur ne porte aucune source — le juge ne la voit pas, et rien
# ne la verifie.
#
# La contrepartie est necessaire : exiger un marqueur PARTOUT, titres
# compris, produirait des titres balises et un texte sans charpente.
# / The wording IS the substance: conditioning the marker on the claim's
#   origin let half a text go unsourced without breaking the rule.
CONSIGNE_DE_SOURCAGE = (
    "TOUTE AFFIRMATION que porte ton article se termine par le marqueur "
    "de sa source, accolé à la fin de la phrase : `[[ext:N]]` où N est "
    "le nombre donné par « Identifiant : ext:N ». Plusieurs sources = "
    "plusieurs marqueurs consécutifs (`[[ext:12]][[ext:15]]`).\n\n"
    "Tu n'écris AUCUNE affirmation qui ne vienne d'une extraction "
    "fournie. Si une phrase que tu voulais écrire ne peut porter aucun "
    "marqueur, c'est qu'elle n'a pas sa place dans l'article : "
    "supprime-la. Cela vaut aussi pour les phrases d'ouverture, de "
    "contexte et de conclusion — une mise en perspective non sourcée "
    "reste une affirmation non sourcée.\n\n"
    "Deux exceptions, et deux seulement : les TITRES de section, qui ne "
    "portent jamais de marqueur ; et les phrases de LIAISON purement "
    "structurelles, qui annoncent ce qui suit sans rien affirmer "
    "(« Trois points ressortent : »).\n\n"
    "Ne cite JAMAIS un identifiant qui n'apparaît pas dans la section "
    "HYPOSTASES ET DEBAT."
)


def _construire_prompt_synthese(page, dernier_job_analyse, analyseur_synthese):
    """
    Construit le prompt utilisateur pour la synthese deliberative.
    Les sections injectees dependent des bool de l'analyseur :
    - inclure_texte_original → bloc TEXTE ORIGINAL
    - inclure_extractions → bloc HYPOSTASES ET DEBAT (extractions + commentaires)
    Au moins l'un des deux doit etre actif (validation faite en amont).
    / Builds the user prompt for deliberative synthesis.
    Sections depend on the analyzer's bool flags.
    At least one of the two must be active (validation done upstream).

    SPEC-synthese phase C : chaque hypostase expose son identifiant
    (« Identifiant : ext:N ») pour que le modele produise les marqueurs
    [[ext:N]], et la consigne exige la ligne finale CITATIONS_USED —
    l'anti-troncature de l'addendum n°2.
    / Phase C: each extraction exposes its id for [[ext:N]] markers, and
    the final CITATIONS_USED control line is required.
    """
    sections_du_prompt = []

    # Bloc TEXTE ORIGINAL — inclus si l'analyseur le demande
    # / TEXT block — included if analyzer requests it
    if analyseur_synthese.inclure_texte_original:
        # Le texte d'une note, ce sont ses ELEMENTS. `text_readability`
        # est VIDE sur toute note ingeree par Docling : le lire ici
        # injectait un bloc VIDE, en silence — le drapeau de l'analyseur
        # etait vivant et sans effet. Mesure du 17 aout 2026.
        # Repli sur le texte plat pour les pages sans aucun element.
        # / A note's text is its elements; text_readability is empty on
        # Docling-ingested notes. Fallback for element-less pages only.
        from front.views import _texte_de_la_note_depuis_ses_elements

        texte_original = _texte_de_la_note_depuis_ses_elements(page)
        sections_du_prompt.append(f"=== TEXTE ORIGINAL ===\n{texte_original}")

    # Bloc HYPOSTASES ET DEBAT — extractions + commentaires si l'analyseur le demande
    # ET si un job d'analyse complet existe. Si pas de job, le bloc est omis silencieusement
    # (cas du previsualiser_synthese pour estimation avant qu'une analyse n'ait ete lancee).
    # / HYPOSTASES block — extractions + comments if analyzer requests it AND analysis job exists.
    # / If no job, block is omitted silently (preview synthesis case).
    if analyseur_synthese.inclure_extractions and dernier_job_analyse is not None:
        # Toutes les extractions visibles de la note (tous jobs termines
        # — analyse, manuelles, selection). / Every visible extraction.
        entites_du_job = _extractions_pour_la_synthese(page)

        # Construire les blocs pour chaque entite / Build blocks for each entity
        blocs_entites = []
        for entite in entites_du_job:
            # Resume IA depuis le JSONField attributes / AI summary from JSONField attributes
            attributs = entite.attributes or {}
            resume_ia = attributs.get("resume", "")

            # Statut formate en majuscules / Status formatted in uppercase
            statut_affiche = (entite.statut_debat or "nouveau").upper()

            # Hypostase (classe d'extraction) / Hypostasis (extraction class)
            classe_hypostase = entite.extraction_class or "hypostase"

            # Texte de la citation / Citation text
            texte_citation = entite.extraction_text or ""

            # Resume a afficher / Summary to display
            resume_affiche = resume_ia or texte_citation[:80]

            # Commentaires de chaque participant au debat
            # / Each participant's debate comments
            lignes_commentaires = []
            for commentaire in entite.commentaires.all():
                nom_auteur = commentaire.user.username if commentaire.user else "Anonyme"
                lignes_commentaires.append(f'  - {nom_auteur} : "{commentaire.commentaire}"')

            # Assemblage du bloc / Block assembly
            bloc = f'**[{statut_affiche}] {classe_hypostase} — {resume_affiche}**\n'
            # L'identifiant expose au modele pour le marqueur [[ext:N]]
            # (SPEC-synthese § 4.4). / The id exposed for [[ext:N]] markers.
            bloc += f'Identifiant : ext:{entite.pk}\n'
            bloc += f'Citation : "{texte_citation}"\n'
            if resume_ia:
                bloc += f'Résumé IA : "{resume_ia}"\n'
            if lignes_commentaires:
                bloc += "Commentaires :\n" + "\n".join(lignes_commentaires) + "\n"

            blocs_entites.append(bloc)

        blocs_formates = "\n\n".join(blocs_entites) if blocs_entites else "(aucune hypostase extraite)"
        sections_du_prompt.append(f"=== HYPOSTASES ET DEBAT ===\n{blocs_formates}")

    # Bloc CONSIGNE + FORMAT — toujours present
    # Format Markdown impose : on parse cote serveur via la lib `markdown`.
    # / INSTRUCTION + FORMAT block — always present.
    # / Markdown format imposed: parsed server-side via the `markdown` library.
    sections_du_prompt.append(
        "=== CONSIGNE ===\n"
        "Produis la synthèse délibérative de ce débat en intégrant les pondérations "
        "par statut définies dans tes instructions. Le texte produit doit être "
        "autonome et lisible.\n\n"
        "=== FORMAT DE SORTIE ===\n"
        "Réponds UNIQUEMENT en Markdown propre :\n"
        "- `# Titre` pour le titre principal (un seul)\n"
        "- `## Section` pour les sous-parties (UNIQUEMENT ce niveau : "
        "jamais de `###` ni plus profond)\n"
        "- `**gras**` pour les concepts clés\n"
        "- `*italique*` pour les nuances\n"
        "- Paragraphes courts séparés par des lignes vides\n"
        "- `> citation` pour les citations directes du texte source\n"
        "- `-` pour les listes à puces (rare, seulement si vraiment liste)\n"
        "- Pas de blocs de code, pas de tableaux, pas de HTML brut\n"
        "- Ne précède PAS ta réponse par « Voici la synthèse » ou un préambule : "
        "commence directement par le titre ou le premier paragraphe."
    )

    # Bloc SOURCAGE — le contrat de citation (SPEC-synthese § 4.4) et la
    # ligne de controle anti-troncature (addendum n°2). La ligne est
    # TOUJOURS exigee : sans elle, impossible de distinguer une reponse
    # complete d'une reponse coupee en plein milieu.
    # / SOURCING block — citation contract and anti-truncation line. The
    # line is ALWAYS required.
    consignes_de_sourcage = []
    if analyseur_synthese.inclure_extractions and dernier_job_analyse is not None:
        consignes_de_sourcage.append(CONSIGNE_DE_SOURCAGE)
    consignes_de_sourcage.append(
        "Termine IMPÉRATIVEMENT ta réponse par une DERNIÈRE ligne de "
        "contrôle, seule sur sa ligne :\n"
        "`CITATIONS_USED: ` suivi des identifiants cités séparés par des "
        "virgules (exemple : `CITATIONS_USED: 12, 15`), ou "
        "`CITATIONS_USED: aucune` si tu n'as rien cité. Une réponse sans "
        "cette ligne finale sera rejetée comme incomplète."
    )
    sections_du_prompt.append(
        "=== SOURÇAGE ===\n" + "\n\n".join(consignes_de_sourcage)
    )

    return "\n\n".join(sections_du_prompt)


class SyntheseTronqueeError(ValueError):
    """
    Levee quand la reponse du modele n'a pas la ligne finale
    CITATIONS_USED : la generation est arrivee incomplete (addendum n°2).
    Jamais une synthese tronquee enregistree comme un succes.
    / Raised when the CITATIONS_USED control line is missing: the
    generation arrived truncated; never stored as a success.
    """


# La ligne de controle, meme habillee par le modele : backticks, gras,
# soulignes — le prompt la montre entre backticks, un modele qui recopie
# ce format ne doit pas etre rejete (relecture C, B1).
# / The control line, even wrapped in backticks/bold by the model.
MOTIF_DE_LIGNE_CITATIONS_USED = re.compile(
    r"^[`*_\s]*CITATIONS_USED[`*_\s]*:\s*(.*?)[`*_\s]*$"
)


def _detacher_la_ligne_citations_used(texte_brut):
    """
    Controle anti-troncature (SPEC-synthese addendum n°2) : la reponse
    doit se terminer par la ligne `CITATIONS_USED: ...`. On la retire du
    texte (elle est un controle, pas un contenu) et on retourne les deux.
    / Anti-truncation check: the response must end with the
    CITATIONS_USED control line; it is detached from the text.

    LOCALISATION : front/tasks.py

    TOLERANCE DE FORME (relecture C, B1) : la ligne peut etre habillee
    (`...`, **...**) ou enfermee dans un bloc de code — on la cherche
    dans les 3 dernieres lignes non vides, et les clotures de bloc
    residuelles sont nettoyees. Le FOND reste strict : pas de ligne =
    generation tronquee = echec bruyant.
    / Form-tolerant (backticks, bold, code fence — last 3 non-empty
    lines); the substance stays strict.

    :return: (texte_sans_la_ligne, contenu_de_la_ligne)
    :raises SyntheseTronqueeError: si la ligne manque / if missing
    """
    lignes = texte_brut.rstrip().split("\n")
    indices_non_vides = [
        indice for indice, ligne in enumerate(lignes) if ligne.strip()
    ]

    for indice in reversed(indices_non_vides[-3:]):
        correspondance = MOTIF_DE_LIGNE_CITATIONS_USED.match(
            lignes[indice].strip()
        )
        if correspondance is None:
            continue
        contenu_de_la_ligne = correspondance.group(1).strip()
        lignes_restantes = lignes[:indice] + lignes[indice + 1:]
        # Nettoie les restes d'habillage en fin de texte : lignes vides
        # et clotures de bloc de code (```). / Strip leftover fences.
        while lignes_restantes and (
            not lignes_restantes[-1].strip()
            or set(lignes_restantes[-1].strip()) <= set("`")
        ):
            lignes_restantes.pop()
        texte_sans_la_ligne = "\n".join(lignes_restantes).rstrip() + "\n"
        return texte_sans_la_ligne, contenu_de_la_ligne

    raise SyntheseTronqueeError(
        "La synthèse est arrivée incomplète : la ligne de contrôle "
        "CITATIONS_USED manque à la fin de la réponse (génération "
        "tronquée). Rien n'a été enregistré — relancez la synthèse. "
        "/ Truncated generation: the CITATIONS_USED control line is "
        "missing; nothing was saved."
    )


# Ce que le rendu markdown d'une synthese a le droit de produire. Tout
# le reste est retire, et les liens sont limites aux protocoles surs :
# html.escape ne touche pas [texte](url), donc markdown reconstruit des
# <a> APRES l'echappement — sans allowlist, un modele (ou une note
# hostile qui l'influence) glisserait un javascript: dans un href rendu
# |safe (relecture C, B2).
# / Allowlist for the synthesis markdown rendering; markdown rebuilds
# <a> tags AFTER escaping, so hrefs must be protocol-filtered.
BALISES_HTML_AUTORISEES = [
    "p", "br", "h1", "h2", "h3", "strong", "em", "blockquote",
    "ul", "ol", "li", "a", "code", "pre", "hr",
]
ATTRIBUTS_HTML_AUTORISES = {"a": ["href", "title"]}
PROTOCOLES_AUTORISES = ["http", "https", "mailto"]


def _nettoyer_le_html_de_synthese(html_rendu):
    """
    Passe la sortie markdown dans bleach : allowlist de balises et de
    protocoles. Defense en profondeur derriere html.escape.
    / Sanitizes the markdown output with bleach (tag and protocol
    allowlist). Defense in depth behind html.escape.

    LOCALISATION : front/tasks.py
    """
    import bleach

    return bleach.clean(
        html_rendu,
        tags=BALISES_HTML_AUTORISEES,
        attributes=ATTRIBUTS_HTML_AUTORISES,
        protocols=PROTOCOLES_AUTORISES,
        strip=False,
    )


def _remplacer_les_marqueurs_par_des_renvois(texte_markdown):
    """
    Remplace chaque marqueur [[ext:N]] par un renvoi [1], [2]... par
    ordre de premiere apparition — pour le RENDU seulement : le numero
    n'est jamais persiste, le markdown garde les marqueurs (§ 4.4).
    / Replaces markers with [N] footnote-style references, for RENDERING
    only; the number is never stored.

    LOCALISATION : front/tasks.py
    """
    from core.services.synthese import MOTIF_DE_MARQUEUR

    numero_par_identifiant = {}

    def _en_renvoi(correspondance):
        identifiant = int(correspondance.group(1))
        if identifiant not in numero_par_identifiant:
            numero_par_identifiant[identifiant] = len(numero_par_identifiant) + 1
        return f"[{numero_par_identifiant[identifiant]}]"

    return MOTIF_DE_MARQUEUR.sub(_en_renvoi, texte_markdown)


@shared_task(bind=True)
def synthetiser_page_task(self, job_id):
    """
    Tache Celery : lance la synthese deliberative sur une Page.
    / Celery task: runs deliberative synthesis on a Page.

    LOCALISATION : front/tasks.py

    SPEC-synthese phase C — la synthese N'EST PLUS une version de page.

    FLUX :
    1. Construit le prompt (texte + hypostases avec identifiants + debat)
    2. Appelle le LLM ; la reponse DOIT finir par la ligne CITATIONS_USED
       (sinon : generation tronquee, echec bruyant, rien n'est enregistre)
    3. Cree une Page type_de_note=SYNTHESE — sans parent_page, sans
       numero de version
    4. indexer_les_citations() avec le PERIMETRE des extractions envoyees
       au modele : les marqueurs [[ext:N]] deviennent des SourceLink, les
       marqueurs hallucines sont retires ET signales dans raw_result
    5. Range la note dans le carnet d'origine de la demande
       (raw_result["dossier_id"]), sinon dans les carnets de la source
    6. Cree l'acte date : SyntheseDirigee au perimetre fige
    / The synthesis is a TYPED NOTEBOOK NOTE: markers become SourceLinks,
    truncated generations fail loudly, the scope is frozen.
    """
    from core.models import Dossier, Page, SyntheseDirigee, TypeDeNote
    from core.services.corpus import ranger_une_note_dans_un_carnet
    from core.services.synthese import indexer_les_citations
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from hypostasis_extractor.models import (
        AnalyseurSyntaxique, ExtractionJob, PromptPiece,
    )

    debut_traitement = time.time()

    # Charger le job / Load the job
    try:
        job_synthese = ExtractionJob.objects.get(pk=job_id)
    except ExtractionJob.DoesNotExist:
        logger.error("synthetiser_page_task: job_id=%s introuvable", job_id)
        return

    try:
        # Marquer comme en cours / Mark as processing
        job_synthese.status = "processing"
        job_synthese.save(update_fields=["status"])

        page_source = job_synthese.page
        if not page_source:
            raise ValueError("Le job n'a pas de page associee")

        # Garde § 3.3 en profondeur : on ne synthetise JAMAIS une
        # synthese ni un wiki — sinon au troisieme tour l'article se cite
        # lui-meme. La vue refuse deja ; un job forge echoue aussi.
        # / § 3.3 depth guard: never synthesize a synthesis or a wiki.
        if page_source.type_de_note != TypeDeNote.NOTE:
            raise ValueError(
                "Cette page est déjà une synthèse (ou un wiki) : on ne "
                "synthétise pas une synthèse. Choisissez une note "
                "ordinaire. / A synthesis is never synthesized."
            )

        # Charger l'analyseur depuis raw_result / Load analyzer from raw_result
        analyseur_id = job_synthese.raw_result.get("analyseur_id")
        analyseur_synthese = AnalyseurSyntaxique.objects.get(pk=analyseur_id)

        # Le modele est celui que le JOB porte, jamais celui que la
        # Configuration porte au moment de l'execution : entre la
        # demande et son tour dans la file, le modele configure a pu
        # changer. Le job estampille ce qui a ete decide ; le relire
        # ailleurs ferait mentir la provenance de la synthese.
        # / The JOB's model, never the Configuration's at run time: the
        # configured model can change while the job waits in the queue.
        modele_ia = job_synthese.ai_model
        if not modele_ia:
            raise ValueError("Aucun modele IA selectionne dans la configuration")

        # Construire le prompt systeme depuis les pieces de l'analyseur
        # / Build system prompt from analyzer pieces
        pieces_ordonnees = PromptPiece.objects.filter(
            analyseur=analyseur_synthese,
        ).order_by("order")
        prompt_systeme = "\n".join(piece.content for piece in pieces_ordonnees)

        if not prompt_systeme.strip():
            raise ValueError(f"L'analyseur '{analyseur_synthese.name}' n'a aucune piece de prompt")

        # Trouver le dernier job d'analyse complete (pas de synthese) —
        # la MEME definition que le perimetre des ecartees § 8 (service
        # partage, phase D). / The latest completed analysis job — same
        # definition as the § 8 scope (shared service).
        from core.services.synthese import dernier_job_d_analyse_de_la_note
        dernier_job_analyse = dernier_job_d_analyse_de_la_note(page_source)

        if not dernier_job_analyse:
            raise ValueError("Aucun job d'analyse termine pour cette page. Lancez d'abord une analyse.")

        # Le perimetre des citations = EXACTEMENT les extractions
        # envoyees au modele, FIGE AVANT l'appel (relecture C, I6) : une
        # extraction masquee PENDANT la generation resterait une citation
        # legitime — sinon l'affirmation resterait et sa preuve serait
        # denoncee comme hallucination. Parametre OBLIGATOIRE ensuite.
        # / The citation scope = exactly the extractions sent to the
        # model, snapshotted BEFORE the call. Mandatory parameter.
        identifiants_du_perimetre = set()
        if analyseur_synthese.inclure_extractions:
            identifiants_du_perimetre = set(
                _extractions_pour_la_synthese(page_source)
                .values_list("pk", flat=True)
            )

        # Construire le prompt utilisateur en respectant les bool de l'analyseur
        # / Build user prompt respecting the analyzer's bool flags
        prompt_utilisateur = _construire_prompt_synthese(
            page_source, dernier_job_analyse, analyseur_synthese,
        )

        # Assemblage message complet / Full message assembly
        message_complet = prompt_systeme + "\n\n" + prompt_utilisateur

        logger.info(
            "synthetiser_page_task: job=%s page=%s model=%s msg_len=%d",
            job_id, page_source.pk, modele_ia.model_name, len(message_complet),
        )

        # Appel au LLM via la couche unifiee / Call LLM via unified layer
        from core.llm_providers import appeler_llm
        texte_synthese = appeler_llm(modele_ia, message_complet)

        if not texte_synthese or not texte_synthese.strip():
            raise ValueError("Le LLM a retourne une reponse vide")

        # Controle anti-troncature (addendum n°2) : la ligne finale
        # CITATIONS_USED doit etre la — sinon la generation est arrivee
        # coupee et RIEN n'est enregistre. Echec bruyant, jamais une
        # synthese tronquee rangee comme un succes.
        # / Anti-truncation check: no control line = loud failure.
        texte_brut, citations_annoncees = _detacher_la_ligne_citations_used(
            texte_synthese.strip()
        )

        # Le demandeur et le carnet d'origine de la demande, poses par la
        # vue dans raw_result. Replis : l'owner de la source, ses carnets.
        # / The requester and origin notebook, set by the view.
        Utilisateur = get_user_model()
        demandeur = None
        identifiant_demandeur = job_synthese.raw_result.get("demandeur_id")
        if identifiant_demandeur:
            demandeur = Utilisateur.objects.filter(
                pk=identifiant_demandeur,
            ).first()
        if demandeur is None:
            demandeur = page_source.owner

        carnet_d_origine = None
        identifiant_carnet = job_synthese.raw_result.get("dossier_id")
        if identifiant_carnet:
            carnet_d_origine = Dossier.objects.filter(
                pk=identifiant_carnet,
            ).first()

        page_racine = page_source.page_racine

        # Tout ou rien : la page, ses liens, ses appartenances et l'acte
        # date naissent ensemble — jamais une demi-synthese en base.
        # / All-or-nothing: never a half-recorded synthesis.
        with transaction.atomic():
            # La synthese est une NOTE TYPEE du carnet (§ 2.1) : pas de
            # parent_page, pas de numero de version. PAS de dossier= :
            # la FK n'est ecrite que par le service de rangement.
            # Le titre porte la date : trois syntheses de la meme note ne
            # doivent pas etre indistinguables dans la liste du carnet
            # (relecture C, M9). / Dated title: three syntheses of the
            # same note must be tellable apart.
            from django.utils import timezone as django_timezone
            date_du_jour = django_timezone.localdate().strftime("%d/%m/%Y")
            titre_de_synthese = (
                f"Synthèse du {date_du_jour} — {page_racine.title or ''}"[:500]
            )
            page_synthese = Page.objects.create(
                type_de_note=TypeDeNote.SYNTHESE,
                version_label=analyseur_synthese.name,
                source_type=page_racine.source_type,
                url=None,
                title=titre_de_synthese,
                html_original="",
                html_readability="",
                text_readability=texte_brut,
                content_hash="",
                owner=demandeur,
            )

            # LE MEME TRONC COMMUN que les articles carnet-niveau. Cette
            # tache dupliquait son ecriture, et echappait donc a TOUTES
            # les gardes : normalisation des niveaux de titre, refus des
            # titres en collision, refus d'un article sans aucune
            # citation. Une garde qui ne couvre que deux producteurs sur
            # trois n'est pas une garde.
            # / The same shared write path as notebook-level articles;
            # this task used to bypass every guard.
            bilan_d_indexation = _ecrire_le_corps_d_un_article(
                page_synthese, texte_brut, identifiants_du_perimetre,
            )

            # Rangement (§ 2.1) : le carnet d'origine de la demande ;
            # a defaut, les carnets de la note source (repli documente
            # en addendum), et la FK pour une racine anormale.
            # / File in the requesting notebook, else the source's ones.
            if carnet_d_origine is not None:
                ranger_une_note_dans_un_carnet(
                    page_synthese, carnet_d_origine, demandeur,
                )
            else:
                for appartenance_racine in (
                    page_racine.appartenances_dossiers.all()
                ):
                    ranger_une_note_dans_un_carnet(
                        page_synthese,
                        appartenance_racine.dossier,
                        demandeur,
                    )
                if (
                    page_synthese.dossier_id is None
                    and page_racine.dossier_id is not None
                ):
                    ranger_une_note_dans_un_carnet(
                        page_synthese, page_racine.dossier, demandeur,
                    )
                # SOURCE HORS DE TOUT CARNET : ON NE DEVINE PLUS.
                #
                # La synthese etait rangee dans le fourre-tout « A
                # ranger » du demandeur, cree pour l'occasion. Ce carnet
                # magique a ete supprime le 21 aout 2026 : une note
                # appartient toujours a un carnet, et une destination
                # inventee par le code n'en est pas une.
                #
                # Le refus vit maintenant DANS LA VUE, avant l'appel au
                # modele — refuser ici couterait une synthese facturee
                # pour la jeter. Ce journal n'est donc qu'un filet : s'il
                # se declenche, c'est que la note a quitte son carnet
                # PENDANT la production.
                # / We no longer guess: the refusal lives in the view,
                # before the billed call. This log is only a net for a
                # note that left its notebook mid-production.
                if page_synthese.dossier_id is None:
                    logger.error(
                        "Synthese %s produite mais rangee nulle part : la "
                        "note source n'est dans aucun carnet. Elle "
                        "n'apparaitra sur aucun ecran carnet.",
                        page_synthese.pk,
                    )

            # L'acte date (§ 3.2) : perimetre FIGE a la production — la
            # note ANALYSEE (celle dont les extractions sont parties au
            # modele), pas sa racine : le § 8 « ce qui n'a pas ete
            # repris » se calcule sur ce perimetre-la (relecture C, I1).
            # Jamais recalcule.
            # / The dated act: scope frozen on the ANALYZED note.
            synthese_dirigee = SyntheseDirigee.objects.create(
                page=page_synthese,
                dossier=carnet_d_origine or page_synthese.dossier,
                produite_par=demandeur,
                # Le perimetre d'extractions est fige MEME s'il est vide
                # (analyseur sans extractions) : c'est le flag qui dit
                # « l'instantane fait foi » (relecture D, B2/B3).
                # / Frozen even when empty; the flag says so.
                perimetre_d_extractions_fige=True,
            )
            synthese_dirigee.notes_du_perimetre.add(page_source)
            if identifiants_du_perimetre:
                # Re-requete plutot que les ids bruts (relecture E, B3) :
                # une purge legale pendant la generation a pu supprimer
                # une extraction — un id disparu ferait echouer le .set()
                # et perdrait toute la synthese dans le rollback.
                # / Re-query: a vanished id must not kill the synthesis.
                from hypostasis_extractor.models import ExtractedEntity
                synthese_dirigee.extractions_du_perimetre.set(
                    ExtractedEntity.objects.filter(
                        pk__in=identifiants_du_perimetre,
                    ),
                )

        # Stocker page_synthese_id dans raw_result pour le polling, et
        # les marqueurs retires pour que l'hallucination soit VISIBLE.
        # / Store the id for polling and stripped markers for visibility.
        donnees_resultat = job_synthese.raw_result or {}
        donnees_resultat["page_synthese_id"] = page_synthese.pk
        donnees_resultat["citations_creees"] = bilan_d_indexation["liens_crees"]
        donnees_resultat["marqueurs_retires"] = (
            bilan_d_indexation["marqueurs_retires"]
        )
        donnees_resultat["citations_annoncees"] = citations_annoncees
        job_synthese.raw_result = donnees_resultat
        job_synthese.status = "completed"
        job_synthese.save(update_fields=["raw_result", "status"])

        duree = time.time() - debut_traitement
        logger.info(
            "synthetiser_page_task: termine job=%s page_synthese=%s en %.1fs — %d chars",
            job_id, page_synthese.pk, duree, len(texte_synthese),
        )

        # Notifier le navigateur que la tache est terminee (succes).
        # Cibles : les proprietaires des carnets contenant LA SYNTHESE
        # (§ 2.1 — c'est la ou elle atterrit qui compte, pas d'ou elle
        # vient) PLUS le demandeur, a qui la vue a promis une
        # notification (relecture C, I2). Dedoublonnes.
        # / Targets: owners of the notebooks holding THE SYNTHESIS, plus
        # the requester the view promised to notify.
        pks_destinataires = set(_destinataires_de_notification(page_synthese))
        pks_destinataires.discard(None)
        if demandeur is not None:
            pks_destinataires.add(demandeur.pk)
        for pk_destinataire in sorted(pks_destinataires) or [None]:
            notifier_tache_terminee(
                user_pk=pk_destinataire,
                tache_id=job_synthese.pk,
                tache_type="synthese",
                status="completed",
            )

    except Exception as erreur_synthese:
        # Erreur : marquer le job en erreur / Error: mark job as error
        message_erreur = str(erreur_synthese)[:500]
        logger.error(
            "synthetiser_page_task: erreur job=%s — %s",
            job_id, message_erreur, exc_info=True,
        )
        job_synthese.status = "error"
        job_synthese.error_message = message_erreur
        job_synthese.save(update_fields=["status", "error_message"])

        # Notifier le navigateur que la tache est terminee (erreur).
        # On recupere le proprietaire via job_synthese.page (peut etre None
        # si l'erreur est arrivee tres tot avant que page_source soit defini).
        # / Notify the browser that the task is complete (error).
        # / We get the owner via job_synthese.page (may be None if error
        # / happened very early before page_source was defined).
        page_pour_notif = job_synthese.page
        destinataires_pour_notif = (
            _destinataires_de_notification(page_pour_notif)
            if page_pour_notif is not None
            else [None]
        )
        for pk_destinataire in destinataires_pour_notif:
            notifier_tache_terminee(
                user_pk=pk_destinataire,
                tache_id=job_synthese.pk,
                tache_type="synthese",
                status="error",
            )


class ModeleAvecCompteurTokens:
    """
    Proxy autour du modele LLM langextract qui accumule les tokens.
    Utilise len(texte) // 4 comme estimation generique (ratio caracteres/tokens).
    / Proxy around the langextract LLM model that accumulates tokens.
    / Uses len(text) // 4 as a generic estimate (chars/tokens ratio).

    LOCALISATION : front/tasks.py
    """
    def __init__(self, modele_llm_original):
        self._modele = modele_llm_original
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    def infer(self, batch_prompts, **kwargs):
        # Compter tokens input (estimation) / Count input tokens (estimate)
        for prompt in batch_prompts:
            self.total_input_tokens += len(str(prompt)) // 4
        # Appeler le vrai modele / Call the real model
        outputs = self._modele.infer(batch_prompts=batch_prompts, **kwargs)
        resultats = list(outputs)
        # Compter tokens output (estimation) / Count output tokens (estimate)
        for scored_list in resultats:
            for scored in (scored_list if isinstance(scored_list, list) else [scored_list]):
                self.total_output_tokens += len(scored.output) // 4
        return resultats

    def __getattr__(self, name):
        return getattr(self._modele, name)


def _blocs_d_extractions_par_note(pages):
    """
    Le corpus d'un article carnet-niveau : un bloc par note, chaque
    extraction avec son identifiant [ext:N] et ses commentaires.
    / One block per note; each extraction with its id and comments.

    LOCALISATION : front/tasks.py

    :return: (texte_des_blocs, identifiants_du_perimetre)
    """
    from core.services.synthese import extractions_citables_de_la_note

    blocs = []
    identifiants_du_perimetre = set()
    for page in pages:
        lignes = [f"=== NOTE : {page.title or f'Note {page.pk}'} ==="]
        extractions = list(
            extractions_citables_de_la_note(page)
            .prefetch_related("commentaires__user").order_by("pk")
        )
        for extraction in extractions:
            identifiants_du_perimetre.add(extraction.pk)
            lignes.append(
                f"Identifiant : ext:{extraction.pk}\n"
                f'Citation : "{extraction.extraction_text}"'
            )
            for commentaire in extraction.commentaires.all():
                nom = (
                    commentaire.user.username if commentaire.user
                    else "Anonyme"
                )
                lignes.append(f'  - {nom} : "{commentaire.commentaire}"')
        if len(lignes) == 1:
            lignes.append("(aucune extraction sur cette note)")
        blocs.append("\n".join(lignes))
    return "\n\n".join(blocs), identifiants_du_perimetre


def _consignes_de_forme_d_article():
    """Le contrat de forme commun (## + marqueurs + CITATIONS_USED).
    / The shared form contract."""
    return (
        "=== FORMAT DE SORTIE ===\n"
        "Réponds UNIQUEMENT en Markdown propre :\n"
        "- `## Section` pour les sous-parties (UNIQUEMENT ce niveau : "
        "jamais de `#` seul ni de `###`)\n"
        "- Paragraphes courts séparés par des lignes vides\n"
        "- Pas de blocs de code, pas de tableaux, pas de HTML brut\n\n"
        "=== SOURÇAGE (OBLIGATOIRE) ===\n"
        "CHAQUE paragraphe doit citer au moins une extraction : chaque "
        "affirmation se termine par le marqueur de sa source, accolé à "
        "la fin de la phrase : `[[ext:N]]` (exemple : « Le seuil est "
        "acté.[[ext:12]] »). Plusieurs sources = plusieurs marqueurs "
        "consécutifs. Ne cite JAMAIS un identifiant qui n'apparaît pas "
        "ci-dessus. Jamais de marqueur dans un titre. Un article sans "
        "marqueurs sera REJETÉ.\n\n"
        "Termine IMPÉRATIVEMENT ta réponse par une DERNIÈRE ligne de "
        "contrôle, seule sur sa ligne :\n"
        "`CITATIONS_USED: ` suivi des identifiants cités séparés par "
        "des virgules, ou `CITATIONS_USED: aucune`. Une réponse sans "
        "cette ligne sera rejetée comme incomplète."
    )


def _prompt_systeme_de_synthese():
    """
    Le prompt systeme : l'analyseur de synthese par defaut s'il existe,
    sinon une consigne generique honnete.
    / The default synthesis analyzer's prompt, or a plain fallback.
    """
    from hypostasis_extractor.models import AnalyseurSyntaxique, PromptPiece

    analyseur = AnalyseurSyntaxique.objects.filter(
        is_active=True, type_analyseur="synthetiser",
    ).order_by("-est_par_defaut", "name").first()
    if analyseur is not None:
        pieces = PromptPiece.objects.filter(
            analyseur=analyseur,
        ).order_by("order")
        prompt = "\n".join(piece.content for piece in pieces)
        if prompt.strip():
            return prompt
    return (
        "Tu es un moteur de synthèse délibérative : tu rédiges des "
        "articles sobres, fidèles aux extractions fournies, sans rien "
        "inventer."
    )


# `[ \t]*`, jamais `\s*` : en mode MULTILINE, `\s` mange les retours a
# la ligne, et la ligne vide qui suit un titre disparaitrait — le
# markdown recollerait le titre a son paragraphe.
# / `[ \t]*` not `\s*`: in MULTILINE, `\s` would swallow the newline.
MOTIF_DE_SOUS_TITRE = re.compile(r"^([ \t]*)#{3,} +(.+?)[ \t]*$", re.MULTILINE)


def _normaliser_les_niveaux_de_titre(texte_markdown):
    """
    Ramene tout titre de niveau 3 ou plus au niveau 2.
    / Demotes any level-3+ heading to level 2.

    LOCALISATION : front/tasks.py

    L'applieur ne resout QUE les `##` (SPEC-synthese § 6, addendum
    n°3). Un `###` stocke est donc une zone de l'article que la mise a
    jour ne peut plus jamais atteindre — et RIEN ne le signale : la
    proposition part, elle est rejetee, l'article ne bouge pas.

    Le prompt interdit deja les `###`. Ca ne suffit pas : mesure du
    16 aout 2026, Gemini 2.5 Flash a rendu un wiki a 1 seul `##` et
    5 `###` malgre la consigne. La garde doit donc etre MECANIQUE —
    « le LLM propose, le code dispose ».
    / The prompt already forbids `###`; a real model disobeyed it, so
    the guard must be mechanical, not merely written.

    Seule la NOTATION du titre change : le texte de la ligne et le
    corps des sections sont rendus intacts. Un `#` en milieu de phrase
    (« #gouvernance ») n'est pas une notation de titre et n'est pas
    touche.
    / Only heading notation changes; prose is untouched.
    """
    return MOTIF_DE_SOUS_TITRE.sub(r"\1## \2", texte_markdown or "")


def _refuser_les_titres_en_collision(texte_markdown):
    """
    Refuse un article dont deux sections porteraient le meme titre.
    / Refuses an article whose two sections would share a title.

    LOCALISATION : front/tasks.py

    L'aplatissement des niveaux peut FABRIQUER cette collision :
    « ## Conclusion » et « ### Conclusion » deviennent deux sections
    homonymes, et l'applieur les declare alors ambigues TOUTES LES DEUX
    — elles ne sont plus jamais atteignables par une mise a jour. C'est
    exactement l'etat que la relecture F interdisait a l'insertion de
    creer ; il ne doit pas entrer par la porte de derriere.

    Echec BRUYANT, comme la garde « zero citation » : un article qu'on
    ne pourra plus jamais mettre a jour n'est pas un succes.
    / Loud failure, like the zero-citation guard.

    :raises ValueError: si deux titres se retrouvent identiques
    """
    from core.services.synthese import titre_de_section

    titres_vus = []
    for ligne in (texte_markdown or "").split("\n"):
        titre = titre_de_section(ligne)
        if titre is not None:
            titres_vus.append(titre.strip()[:200])

    for titre in titres_vus:
        if titres_vus.count(titre) > 1:
            raise ValueError(
                f"L'article porte deux sections intitulées "
                f"« {titre} » : elles seraient l'une et l'autre "
                f"impossibles à mettre à jour. L'article n'est pas "
                f"enregistré — relancez la production. "
                f"/ Duplicate section title: refused."
            )


def _demandeur_du_job(job):
    """
    L'utilisateur qui a demande cette production, ou None.
    / The user who asked for this production, or None.

    LOCALISATION : front/tasks.py

    Les vues posent `demandeur_id` dans `raw_result` ; les commandes de
    management, non — un article produit par l'installation n'a aucun
    demandeur, et c'est exactement ce que None veut dire.
    / Management commands set no requester: None says so.
    """
    from django.contrib.auth import get_user_model

    identifiant = (job.raw_result or {}).get("demandeur_id")
    if not identifiant:
        return None
    return get_user_model().objects.filter(pk=identifiant).first()


def _ecrire_le_corps_d_un_article(page_d_article, texte_brut,
                                  identifiants_du_perimetre,
                                  motif_du_tour=None,
                                  bilan_des_operations=None,
                                  fait_par=None, depuis=None,
                                  job_du_tour=None, wiki_du_tour=None):
    """
    Le tronc commun d'ecriture d'un article (wiki ou synthese carnet) :
    indexation des citations avec le perimetre OBLIGATOIRE, rendu HTML
    en renvois [N], nettoyage bleach, hash.
    / Shared article write path: mandatory-scope indexing, [N] HTML
    rendering, bleach, hash.

    LOCALISATION : front/tasks.py

    :param motif_du_tour: une valeur de `MotifDeTourDeWiki`.
        **OBLIGATOIRE des que la page porte un wiki** : voir la garde
        ci-dessous. Une note ordinaire ou une synthese dirigee n'en
        demande aucun.
    :param bilan_des_operations: le bilan de `appliquer_les_operations`
        quand le tour vient d'operations de section ; None pour une
        production complete (creation, regeneration, reparation).
    :param fait_par: l'humain qui a accepte, ou None pour le moteur.
    :param depuis: la borne basse du comptage des nouveautes du tour.
    :param job_du_tour: l'`ExtractionJob` de la proposition, s'il y en a.
    :param wiki_du_tour: l'objet `Wiki` a jour — l'appelant qui vient
        d'incrementer `tours_de_mise_a_jour` en memoire doit le passer,
        sinon le tour porterait le numero d'avant.
    :return: le bilan d'indexation / the indexing report
    :raises ValueError: si le perimetre offrait des extractions et que
        l'article n'en cite AUCUNE — un article sans preuve n'est pas un
        succes dans un systeme de synthese SOURCEE (constat reel du
        9 aout : GPT-4o-mini a redige un wiki entier sans un marqueur).
        / A citation-less article over a non-empty scope fails loudly.
    :raises ValueError: si la page porte un wiki et qu'aucun motif de
        tour n'est donne. / If the page carries a wiki and no motive.
    """
    import html

    import markdown

    from core.models import Wiki
    from core.services.synthese import indexer_les_citations

    # LA GARDE DE L'HISTORIQUE (addendum du 21 aout 2026). Cette
    # fonction est le SEUL endroit ou un corps d'article s'ecrit : un
    # chemin qui oublierait le motif ferait changer un wiki sans que le
    # journal n'en dise rien. On refuse AVANT d'ecrire quoi que ce soit,
    # pour qu'un refus soit un refus.
    # / The guard: a wiki body never changes without a recorded motive.
    wiki_de_l_article = wiki_du_tour or Wiki.objects.filter(
        page=page_d_article,
    ).first()
    if wiki_de_l_article is not None and not motif_du_tour:
        raise ValueError(
            "Écrire le corps d'un wiki exige un motif de tour : sans "
            "lui, l'article changerait sans laisser d'histoire. "
            "/ Writing a wiki body requires a round motive."
        )

    # L'« avant » se lit AVANT toute ecriture, et depuis la base : c'est
    # ce que le lecteur verra a cote du nouveau contenu (§ 6.4).
    # / The before is read before anything is written.
    texte_de_l_article_avant_ce_tour = page_d_article.text_readability or ""

    # AVANT l'indexation : c'est elle qui range chaque citation dans SA
    # section, et elle ne reconnait que les `##`. Normaliser apres
    # rangerait des liens sous une section qui n'existe pas.
    # / Before indexing: it files each citation under its `##` section.
    texte_brut = _normaliser_les_niveaux_de_titre(texte_brut)
    _refuser_les_titres_en_collision(texte_brut)

    bilan_d_indexation = indexer_les_citations(
        page_d_article, texte_brut, identifiants_du_perimetre,
    )
    if identifiants_du_perimetre and bilan_d_indexation["liens_crees"] == 0:
        raise ValueError(
            "L'article est arrivé sans aucune citation alors que le "
            "périmètre offrait des extractions : un texte sans preuve "
            "n'est pas enregistré. Relancez la production. "
            "/ No citation over a non-empty scope: refused."
        )
    texte_definitif = bilan_d_indexation["texte_nettoye"]
    html_d_article = _nettoyer_le_html_de_synthese(
        markdown.markdown(
            html.escape(
                _remplacer_les_marqueurs_par_des_renvois(texte_definitif)
            ),
            extensions=["extra", "nl2br"],
        )
    )
    page_d_article.text_readability = texte_definitif
    page_d_article.html_original = html_d_article
    page_d_article.html_readability = html_d_article
    page_d_article.content_hash = hashlib.sha256(
        texte_definitif.encode("utf-8")
    ).hexdigest()
    page_d_article.save(update_fields=[
        "text_readability", "html_original", "html_readability",
        "content_hash", "updated_at",
    ])

    # L'HISTOIRE S'ECRIT ICI, avant l'enchainement des juges : un tour
    # doit exister meme si la mise en file echoue. Le bilan porte le
    # texte DEFINITIF (indexe, nettoye), pas celui de l'applieur — sinon
    # le « apres » du journal ne serait pas ce qui est en base.
    # / History is written here, with the definitive text.
    if wiki_de_l_article is not None:
        from core.services.historique_de_wiki import enregistrer_un_tour

        bilan_du_tour = dict(bilan_des_operations or {})
        bilan_du_tour["texte_final"] = texte_definitif
        enregistrer_un_tour(
            wiki=wiki_de_l_article,
            motif=motif_du_tour,
            fait_par=fait_par,
            bilan=bilan_du_tour,
            texte_avant=texte_de_l_article_avant_ce_tour,
            depuis=depuis,
            job=job_du_tour,
            identifiants_du_perimetre=identifiants_du_perimetre,
        )

    # UN ARTICLE ECRIT EST UN ARTICLE JUGE. C'est le SEUL endroit ou un
    # corps d'article s'ecrit et ou ses citations s'indexent — creation
    # comme mise a jour appliquee passent ici. Y accrocher la
    # verification, c'est la garantir aux deux, sans la demander deux
    # fois ailleurs.
    #
    # Seules les citations SANS VERDICT sont jugees : celles qu'un
    # paragraphe intact porte encore gardent le leur, et ne coutent rien.
    # / The one place an article body is written and its citations
    # indexed: creation and applied update both come through here.
    # LE DESTINATAIRE EST LE PROPRIETAIRE DE L'ARTICLE, et non le
    # demandeur de la production : les cinq appelants de cette fonction
    # ne connaissent pas tous un utilisateur, et l'article, lui, en a
    # toujours un. / The article always has an owner; its five callers
    # do not all know a user.
    enchainer_la_verification(page_d_article, page_d_article.owner_id)

    return bilan_d_indexation


def appliquer_un_tour_de_wiki(wiki, operations, motif, fait_par=None,
                              job=None, updated_at_de_la_proposition=None):
    """
    Applique un lot d'operations sur un wiki, et ecrit son histoire.
    / Applies a batch of operations on a wiki, and records its history.

    LOCALISATION : front/tasks.py

    UN SEUL CHEMIN pour les deux appelants — la vue, quand un humain
    accepte operation par operation, et la passe de nuit, quand le
    moteur applique seul. Deux copies de cette sequence divergeraient,
    et c'est toujours l'historique qui mentirait le premier.
    / One path for both callers: the human view and the nightly pass.

    FLUX :
    1. controle de fraicheur (addendum n°1) quand la proposition en
       porte un jeton : une proposition perimee ne decrit plus
       l'article, on refuse plutot que d'ecraser ;
    2. l'applieur rejette VISIBLEMENT ce qui viole le § 6.2/6.3 ;
    3. le compteur de tours monte, en memoire d'abord — le tour doit
       porter le numero d'APRES ;
    4. l'ecriture du corps enchaine l'indexation, l'historique et les
       juges ;
    5. le compteur n'est sauve qu'ensuite : si l'ecriture refuse, rien
       n'a bouge.

    :param wiki: le `Wiki` a mettre a jour / the wiki
    :param operations: les operations retenues / the retained operations
    :param motif: une valeur de `MotifDeTourDeWiki`
    :param fait_par: l'humain qui accepte, ou None pour le moteur
    :param job: l'`ExtractionJob` de la proposition
    :param updated_at_de_la_proposition: le jeton de fraicheur, s'il y en a
    :return: `(bilan des operations, bilan d'indexation)`
    :raises PropositionPerimee: si l'article a bouge depuis la proposition
    """
    from core.services.section_ops import (
        appliquer_les_operations, verifier_que_la_proposition_est_fraiche,
    )
    from core.services.synthese import extractions_du_perimetre

    if updated_at_de_la_proposition is not None:
        verifier_que_la_proposition_est_fraiche(
            wiki.page, updated_at_de_la_proposition,
        )

    identifiants_du_perimetre = set(
        extractions_du_perimetre(wiki.page).values_list("pk", flat=True)
    )
    bilan = appliquer_les_operations(
        wiki.page.text_readability or "",
        operations, identifiants_du_perimetre,
    )

    # La borne basse des nouveautes est la DERNIERE MISE A JOUR, lue
    # avant l'ecriture : `derniere_mise_a_jour` est un auto_now, le save
    # qui suit l'ecrasera. C'est la meme borne que celle de l'ecran
    # (`_contexte_d_article`), donc la meme raison des deux cotes.
    # / Read the previous date before the save overwrites it.
    depuis = wiki.derniere_mise_a_jour

    # RIEN D'APPLICABLE : on ecrit l'histoire de la tentative, et on ne
    # touche PAS a l'article. Le reecrire a l'identique le ferait passer
    # par une reindexation complete pour zero changement, et ferait
    # monter un compteur de tours qui ne raconte rien.
    # / Nothing applicable: record the attempt, leave the article alone.
    if not bilan["operations_appliquees"]:
        from core.services.historique_de_wiki import enregistrer_un_tour

        texte_inchange = wiki.page.text_readability or ""
        enregistrer_un_tour(
            wiki=wiki,
            motif=motif,
            fait_par=fait_par,
            bilan={**bilan, "texte_final": texte_inchange},
            texte_avant=texte_inchange,
            depuis=depuis,
            job=job,
            identifiants_du_perimetre=identifiants_du_perimetre,
        )
        return bilan, {"liens_crees": 0, "contestations_perdues": []}

    wiki.tours_de_mise_a_jour += 1
    bilan_d_indexation = _ecrire_le_corps_d_un_article(
        wiki.page, bilan["texte_final"], identifiants_du_perimetre,
        motif_du_tour=motif,
        bilan_des_operations=bilan,
        fait_par=fait_par,
        depuis=depuis,
        job_du_tour=job,
        wiki_du_tour=wiki,
    )
    wiki.save(update_fields=[
        "tours_de_mise_a_jour", "derniere_mise_a_jour",
    ])

    return bilan, bilan_d_indexation


@shared_task(bind=True)
def lancer_la_passe_de_nuit_task(self, maximum=0):
    """
    Ouvre la passe de nuit et met un wiki par tache en file.
    / Opens the nightly pass and queues one task per wiki.

    LOCALISATION : front/tasks.py

    DECLENCHEE PAR LE BEAT (`hypostasia/celery.py`, `beat_schedule`) —
    la planification vit dans le code de l'application, pas dans le
    crontab d'une machine : elle est versionnee, et elle survit a un
    changement de machine.

    LE FAN-OUT, ET CE QU'IL CHANGE. Une tache par wiki, sur la file par
    defaut : les appels au redacteur avancent a la concurrence du
    worker au lieu de se suivre. Chaque tache tient largement sous le
    plafond de 30 minutes (`CELERY_TASK_TIME_LIMIT`), la ou une passe
    sequentielle de vingt wikis le crevait — et un redemarrage ne coute
    qu'un wiki, pas la nuit entiere.
    / One task per wiki on the default queue: parallel, and each stays
    far below the 30-minute task limit.

    LA PASSE NE SE FERME PAS ICI. Aucune tache ne sait si elle est la
    derniere : c'est le compteur `wikis_termines` qui le dit, et la
    derniere a rendre la main ferme la passe. Tant qu'elle est ouverte,
    le recapitulatif du matin attend.
    / The pass is closed by the counter, not here.

    :param maximum: nombre maximum de wikis (0 = tous). Ce qui est
        ecarte par cette borne est COMPTE — une troncature muette se
        lirait comme une couverture complete.
    :return: le pk de la `PasseDeNuit` ouverte, ou None
    """
    from core.models import PasseDeNuit, Wiki
    from core.services.passe_de_nuit import passe_en_cours
    from core.services.synthese import extractions_ecartees

    # DEUX PASSES EN MEME TEMPS DOUBLERAIENT LA FACTURE, et deux tours
    # concurrents se disputeraient le meme article. Le cas arrive tout
    # seul : une nuit plus longue que prevu, et le beat repart.
    # / Concurrent passes double the bill.
    deja_en_cours = passe_en_cours()
    if deja_en_cours is not None:
        logger.warning(
            "lancer_la_passe_de_nuit_task: une passe (#%s) tourne "
            "encore — celle-ci ne demarre pas.", deja_en_cours.pk,
        )
        return None

    wikis_a_examiner = []
    for wiki in Wiki.objects.select_related("page", "dossier"):
        try:
            a_du_neuf = extractions_ecartees(wiki.page).exists()
        except Exception as erreur:
            # Un perimetre illisible (article historique) n'est pas une
            # raison d'arreter la nuit. / An unreadable scope does not
            # stop the night.
            logger.warning(
                "lancer_la_passe_de_nuit_task: wiki=%s perimetre "
                "illisible (%s) — laisse de cote.", wiki.pk, erreur,
            )
            continue
        if a_du_neuf:
            wikis_a_examiner.append(wiki)

    ecartes_par_le_maximum = 0
    if maximum and len(wikis_a_examiner) > maximum:
        ecartes_par_le_maximum = len(wikis_a_examiner) - maximum
        wikis_a_examiner = wikis_a_examiner[:maximum]

    passe = PasseDeNuit.objects.create(
        wikis_examines=len(wikis_a_examiner),
        wikis_ecartes_par_le_maximum=ecartes_par_le_maximum,
    )

    # RIEN A FAIRE EST UN CAS NORMAL, et il doit fermer la passe tout
    # de suite : sinon le recapitulatif du matin attendrait une passe
    # qui n'a personne pour la finir.
    # / Nothing to do must close the pass at once.
    if not wikis_a_examiner:
        _fermer_la_passe(passe)
        return passe.pk

    for wiki in wikis_a_examiner:
        mettre_a_jour_un_wiki_la_nuit_task.delay(passe.pk, wiki.pk)

    logger.info(
        "lancer_la_passe_de_nuit_task: passe #%s ouverte, %s wiki(s) en "
        "file, %s ecarte(s) par le maximum.",
        passe.pk, len(wikis_a_examiner), ecartes_par_le_maximum,
    )
    return passe.pk


def _fermer_la_passe(passe):
    """
    Ferme la passe et laisse partir le recapitulatif.
    / Closes the pass and lets the recap go.

    LOCALISATION : front/tasks.py
    """
    from django.utils import timezone

    passe.terminee_le = timezone.now()
    passe.save(update_fields=["terminee_le"])
    logger.info(
        "passe de nuit #%s terminee : %s examine(s), %s modifie(s), "
        "%s en erreur.", passe.pk, passe.wikis_examines,
        passe.wikis_modifies, passe.wikis_en_erreur,
    )


def _rendre_la_main_a_la_passe(passe_id, a_modifie, en_erreur):
    """
    Une tache de wiki a fini : compte, et ferme si elle etait la
    derniere. / One wiki task finished: count, and close if last.

    LOCALISATION : front/tasks.py

    LES TROIS INCREMENTS SONT ATOMIQUES (`F(...) + 1`), et la relecture
    se fait sous VERROU. Deux taches qui finissent dans la meme
    milliseconde liraient sinon le meme total et, ou bien fermeraient la
    passe deux fois, ou bien ne la fermeraient JAMAIS — et le
    recapitulatif du matin attendrait pour toujours une passe finie.
    / Atomic increments and a locked read: otherwise two tasks finishing
    together would either close twice or never, and the morning recap
    would wait forever on a finished pass.
    """
    from django.db import transaction
    from django.db.models import F

    from core.models import PasseDeNuit

    with transaction.atomic():
        PasseDeNuit.objects.filter(pk=passe_id).update(
            wikis_termines=F("wikis_termines") + 1,
            wikis_modifies=F("wikis_modifies") + (1 if a_modifie else 0),
            wikis_en_erreur=F("wikis_en_erreur") + (1 if en_erreur else 0),
        )
        passe = PasseDeNuit.objects.select_for_update().filter(
            pk=passe_id,
        ).first()
        if passe is None:
            return
        c_est_la_derniere = (
            passe.terminee_le is None
            and passe.wikis_termines >= passe.wikis_examines
        )
        if c_est_la_derniere:
            _fermer_la_passe(passe)


@shared_task(bind=True)
def mettre_a_jour_un_wiki_la_nuit_task(self, passe_id, wiki_id):
    """
    Un wiki, un tour, sans humain — puis la main rendue a la passe.
    / One wiki, one round, no human — then the pass is told.

    LOCALISATION : front/tasks.py

    UN ECHEC NE COUTE QUE SON WIKI. Un modele injoignable sur l'un ne
    doit priver aucun autre de sa mise a jour, et surtout ne doit pas
    laisser la passe ouverte : la main est rendue dans TOUS les cas,
    sinon le recapitulatif du matin n'arriverait jamais.
    / A failure costs only its own wiki, and always gives the hand back.
    """
    from core.models import RoleDeModele, Wiki
    from core.services.modeles_par_role import modele_du_role

    a_modifie = False
    en_erreur = False
    try:
        wiki = Wiki.objects.select_related("page", "dossier").get(pk=wiki_id)
        tour = mettre_a_jour_un_wiki_la_nuit(
            wiki, modele_du_role(RoleDeModele.REDACTEUR_D_ARTICLE),
        )
        a_modifie = tour is not None and tour.a_change_l_article
    except Exception as erreur:
        en_erreur = True
        logger.exception(
            "mettre_a_jour_un_wiki_la_nuit_task: wiki=%s a echoue (%s)",
            wiki_id, erreur,
        )
    finally:
        _rendre_la_main_a_la_passe(passe_id, a_modifie, en_erreur)


# Combien de fois le recapitulatif se repasse la main en attendant la
# fin de la passe de nuit, et a quel intervalle.
#
# POURQUOI SE REPASSER LA MAIN PLUTOT QUE DORMIR. Un `sleep` dans une
# tache OCCUPE un slot du worker — sur une file a concurrence 2, une
# heure d'attente en mangerait la moitie, et les analyses des
# utilisateurs attendraient derriere. La tache se remet donc en file
# avec un `countdown`, exactement comme le juge local se repasse la
# main entre deux paquets.
# / A sleeping task holds a worker slot; re-queueing with a countdown
# does not.
SECONDES_ENTRE_DEUX_REGARDS = 120
REGARDS_MAXIMUM_SUR_LA_PASSE = 30


@shared_task(bind=True)
def envoyer_le_recapitulatif_du_matin_task(self, regards_deja_faits=0):
    """
    Le recapitulatif du matin — APRES la passe de nuit, toujours.
    / The morning recap — always after the nightly pass.

    LOCALISATION : front/tasks.py

    DECLENCHEE PAR LE BEAT, quelques heures apres la passe. L'ecart
    d'horaire est une ESPERANCE d'ordre, pas une garantie : une nuit
    chargee suffirait a faire partir le mail avant la fin du travail
    qu'il annonce. La tache interroge donc la `PasseDeNuit` et SE
    REPASSE LA MAIN tant qu'elle tourne.
    / The schedule gap is a hope, not a guarantee: this task waits on
    the pass itself.

    AU BOUT DE L'ATTENTE, ELLE N'ENVOIE PAS. Un mail qui annonce a
    moitie serait pire qu'un mail en retard, et le journal le dit
    fort. / After the last look, it does not send: half-announcing is
    worse than late.
    """
    from core.services.passe_de_nuit import passe_en_cours

    passe = passe_en_cours()
    if passe is not None:
        if regards_deja_faits >= REGARDS_MAXIMUM_SUR_LA_PASSE:
            logger.error(
                "envoyer_le_recapitulatif_du_matin_task: la passe #%s "
                "tourne encore apres %s regards — AUCUN mail envoye. "
                "Le recapitulatif annoncerait un travail a moitie fait.",
                passe.pk, regards_deja_faits,
            )
            return 0
        envoyer_le_recapitulatif_du_matin_task.apply_async(
            kwargs={"regards_deja_faits": regards_deja_faits + 1},
            countdown=SECONDES_ENTRE_DEUX_REGARDS,
        )
        return 0

    from django.core.management import call_command

    call_command("envoyer_le_recapitulatif_du_matin",
                 sans_attendre_la_nuit=True, verbosity=0)
    return 1


def mettre_a_jour_un_wiki_la_nuit(wiki, modele_ia):
    """
    Un tour de wiki sans humain : proposer, puis appliquer.
    / One wiki round without a human: propose, then apply.

    LOCALISATION : front/tasks.py

    CE QUE LA NUIT NE PEUT PAS FAIRE, et qui rend l'automatisme
    acceptable (addendum du 21 aout 2026) :

    - elle passe par le MEME applieur que la vue, donc par les memes
      controles § 6.2/6.3 — un titre halluciné, une affirmation sans
      preuve, une source hors perimetre sont rejetes ici comme
      ailleurs ;
    - elle n'a AUCUN chemin vers `produire_un_wiki_task` : elle ajoute,
      remplace ou insere, jamais ne regenere ;
    - tout ce qu'elle fait s'ecrit dans l'historique, rejets compris,
      et se relit le lendemain matin.
    / The night has no privilege over the applier, and never regenerates.

    Aucune tache Celery ici : la passe est SEQUENTIELLE, dans la
    commande de management. Un appel au redacteur a la fois, donc un
    cout previsible et une file qui ne se remplit pas d'un coup.
    / Sequential on purpose: one writer call at a time.

    :param wiki: le `Wiki` a mettre a jour / the wiki
    :param modele_ia: l'`AIModel` du role redacteur / the writer model
    :return: le `TourDeWiki` ecrit / the recorded round
    """
    from core.models import MotifDeTourDeWiki

    operations, _jeton = construire_la_proposition_d_operations(
        wiki, modele_ia,
    )
    # PAS de jeton de fraicheur : la proposition vient d'etre produite
    # sur l'article qu'on applique, dans le meme fil. Le controle
    # protege d'une previsualisation vieille de dix minutes, pas de
    # deux instructions consecutives. / No staleness token needed here.
    appliquer_un_tour_de_wiki(
        wiki, operations,
        motif=MotifDeTourDeWiki.MAJ_NOCTURNE,
        fait_par=None,
    )
    return wiki.tours.first()


def _terminer_un_job_d_article(job, page_d_article, bilan_d_indexation,
                               citations_annoncees, tache_type):
    """Cloture commune : raw_result + notifications. / Shared wrap-up."""
    donnees = job.raw_result or {}
    donnees["page_synthese_id"] = page_d_article.pk
    donnees["citations_creees"] = bilan_d_indexation["liens_crees"]
    donnees["marqueurs_retires"] = bilan_d_indexation["marqueurs_retires"]
    # LE COMPTE DES GROUPES REECRITS, PERSISTE. Sans cette ligne, le
    # repli du 19 aout repare en SILENCE : on ne saurait plus quel modele
    # desobeit au format des marqueurs, et le signal de qualite que le
    # repli devait preserver serait perdu. `groupes_restants == 0` ne
    # suffit pas a le deduire — ce serait aussi vrai si personne ne
    # groupait plus.
    # / Persisted: otherwise the fallback repairs silently and the
    #   per-model disobedience signal is lost.
    donnees["marqueurs_groupes_normalises"] = bilan_d_indexation[
        "marqueurs_groupes_normalises"
    ]
    donnees["citations_annoncees"] = citations_annoncees
    job.raw_result = donnees
    job.status = "completed"
    job.save(update_fields=["raw_result", "status"])

    pks_destinataires = set(_destinataires_de_notification(page_d_article))
    pks_destinataires.discard(None)
    identifiant_demandeur = (job.raw_result or {}).get("demandeur_id")
    if identifiant_demandeur:
        pks_destinataires.add(identifiant_demandeur)
    for pk_destinataire in sorted(pks_destinataires) or [None]:
        notifier_tache_terminee(
            user_pk=pk_destinataire, tache_id=job.pk,
            tache_type=tache_type, status="completed",
        )


def _echouer_un_job_d_article(job, erreur, tache_type):
    """Cloture d'erreur commune. / Shared failure wrap-up."""
    message = str(erreur)[:500]
    logger.error(
        "%s: erreur job=%s — %s", tache_type, job.pk, message,
        exc_info=True,
    )
    job.status = "error"
    job.error_message = message
    job.save(update_fields=["status", "error_message"])
    identifiant_demandeur = (job.raw_result or {}).get("demandeur_id")
    notifier_tache_terminee(
        user_pk=identifiant_demandeur or None, tache_id=job.pk,
        tache_type=tache_type, status="error",
    )


def _le_job_n_est_pas_le_mien(job, marqueur, tache_type):
    """
    Vrai si ce job n'a pas ete produit pour CETTE tache.
    / True when this job was not produced for THIS task.

    LOCALISATION : front/tasks.py

    Une tache ne doit JAMAIS degrader un job qu'elle n'a pas produit. Un
    message mal cible — meme cle primaire, tout autre objet — levait
    jusqu'ici dans le corps de la tache, et le gestionnaire d'erreur
    marquait le job `error`. Sur un job d'ANALYSE, cela rend ses
    extractions NON CITABLES : de la donnee valide devient invisible.

    Constate le 17 aout 2026 sur une installation neuve : le carnet
    etalon est passe de 101 a 41 extractions citables, sans qu'aucun
    test n'echoue.

    On refuse donc AVANT de toucher a quoi que ce soit, et on journalise
    en AVERTISSEMENT — le job reste exactement dans l'etat ou il etait.
    / Refuse before touching anything; the job stays exactly as it was.
    """
    if (job.raw_result or {}).get(marqueur):
        return False
    logger.warning(
        "%s: le job %s n'est pas un job de %s (marqueur « %s » absent) — "
        "la tache s'arrete SANS y toucher.",
        tache_type, job.pk, tache_type, marqueur,
    )
    return True

@shared_task(bind=True)
def produire_un_wiki_task(self, job_id):
    """
    Produit (ou reproduit) l'article d'un Wiki : perimetre RECALCULE au
    moment de la production (§ 3.1.1), marqueurs + CITATIONS_USED.
    / Produces a Wiki article on its recomputed scope.

    LOCALISATION : front/tasks.py
    """
    from core.models import MotifDeTourDeWiki, Wiki
    from core.services.synthese import notes_du_perimetre_d_un_wiki
    from hypostasis_extractor.models import ExtractionJob

    try:
        job = ExtractionJob.objects.get(pk=job_id)
    except ExtractionJob.DoesNotExist:
        logger.error("produire_un_wiki_task: job=%s introuvable", job_id)
        return
    if _le_job_n_est_pas_le_mien(job, "est_wiki", "wiki"):
        return
    try:
        job.status = "processing"
        job.save(update_fields=["status"])

        wiki = Wiki.objects.get(pk=job.raw_result["wiki_id"])
        notes = list(notes_du_perimetre_d_un_wiki(wiki))
        blocs, identifiants_du_perimetre = _blocs_d_extractions_par_note(notes)

        prompt = (
            _prompt_systeme_de_synthese() + "\n\n"
            f"=== SUJET DE L'ARTICLE ===\n{wiki.sujet}\n\n"
            "=== EXTRACTIONS DU PÉRIMÈTRE ===\n" + blocs + "\n\n"
            "=== CONSIGNE ===\n"
            "Rédige un article de wiki sur ce sujet, nourri UNIQUEMENT "
            "des extractions ci-dessus. Le sujet oriente la rédaction ; "
            "il ne t'autorise pas à inventer.\n\n"
            + _consignes_de_forme_d_article()
        )
        from core.llm_providers import appeler_llm
        reponse = appeler_llm(job.ai_model, prompt)
        if not reponse or not reponse.strip():
            raise ValueError("Le LLM a retourne une reponse vide")
        texte_brut, citations_annoncees = _detacher_la_ligne_citations_used(
            reponse.strip()
        )
        # PREMIERE REDACTION ou REGENERATION : la distinction se lit sur
        # l'article. Une regeneration reecrit tout et fait partir les
        # avis des juges par CASCADE — l'historique doit pouvoir le
        # nommer, sinon elle ressemble a un tour ordinaire (constat du
        # 19 aout 2026 : 165 avis perdus en silence).
        # / A regeneration must be nameable in the history.
        l_article_avait_deja_un_corps = bool(
            (wiki.page.text_readability or "").strip()
        )
        motif_de_ce_tour = (
            MotifDeTourDeWiki.REGENERATION if l_article_avait_deja_un_corps
            else MotifDeTourDeWiki.CREATION
        )
        bilan = _ecrire_le_corps_d_un_article(
            wiki.page, texte_brut, identifiants_du_perimetre,
            motif_du_tour=motif_de_ce_tour,
            fait_par=_demandeur_du_job(job),
            job_du_tour=job,
            wiki_du_tour=wiki,
        )
        # Le compteur de tours ne bouge pas ici : la production initiale
        # est le tour 1 (defaut du modele) ; seuls les tours de MISE A
        # JOUR l'incrementent. / Rounds only bump on updates.
        wiki.save(update_fields=["derniere_mise_a_jour"])
        _terminer_un_job_d_article(
            job, wiki.page, bilan, citations_annoncees, "wiki",
        )
    except Exception as erreur:
        _echouer_un_job_d_article(job, erreur, "wiki")


@shared_task(bind=True)
def produire_une_synthese_de_carnet_task(self, job_id):
    """
    Remplit une synthese dirigee de CARNET dont l'acte date (page +
    SyntheseDirigee, perimetre fige au moment du geste) existe deja —
    la vue cree, la tache remplit.
    / Fills a notebook-level synthesis whose frozen act already exists.

    LOCALISATION : front/tasks.py
    """
    from hypostasis_extractor.models import ExtractionJob

    try:
        job = ExtractionJob.objects.get(pk=job_id)
    except ExtractionJob.DoesNotExist:
        logger.error(
            "produire_une_synthese_de_carnet_task: job=%s introuvable",
            job_id,
        )
        return
    if _le_job_n_est_pas_le_mien(job, "est_synthese_carnet", "synthese"):
        return
    try:
        job.status = "processing"
        job.save(update_fields=["status"])

        page_de_synthese = job.page
        synthese_dirigee = page_de_synthese.synthese_dirigee
        notes = list(synthese_dirigee.notes_du_perimetre.all())
        blocs, identifiants_du_perimetre = _blocs_d_extractions_par_note(notes)

        direction = ""
        if synthese_dirigee.categorie_de_direction is not None:
            direction = (
                f"\n=== DIRECTION ===\nLa synthèse porte sur la "
                f"catégorie « "
                f"{synthese_dirigee.categorie_de_direction.nom} ».\n"
            )
        prompt = (
            _prompt_systeme_de_synthese() + "\n\n"
            f"=== TITRE DEMANDÉ ===\n{page_de_synthese.title}\n"
            + direction + "\n"
            "=== EXTRACTIONS DU PÉRIMÈTRE ===\n" + blocs + "\n\n"
            "=== CONSIGNE ===\n"
            "Produis la synthèse délibérative de ce corpus : un texte "
            "autonome et lisible, nourri UNIQUEMENT des extractions "
            "ci-dessus.\n\n"
            + _consignes_de_forme_d_article()
        )
        from core.llm_providers import appeler_llm
        reponse = appeler_llm(job.ai_model, prompt)
        if not reponse or not reponse.strip():
            raise ValueError("Le LLM a retourne une reponse vide")
        texte_brut, citations_annoncees = _detacher_la_ligne_citations_used(
            reponse.strip()
        )
        bilan = _ecrire_le_corps_d_un_article(
            page_de_synthese, texte_brut, identifiants_du_perimetre,
        )
        # Le perimetre d'extractions fige = ce qui a ete montre au
        # modele (re-requete : jamais un id disparu, relecture E B3).
        # / Freeze exactly what the model saw, re-queried.
        from hypostasis_extractor.models import ExtractedEntity
        synthese_dirigee.extractions_du_perimetre.set(
            ExtractedEntity.objects.filter(pk__in=identifiants_du_perimetre),
        )
        _terminer_un_job_d_article(
            job, page_de_synthese, bilan, citations_annoncees, "synthese",
        )
    except Exception as erreur:
        _echouer_un_job_d_article(job, erreur, "synthese")


def construire_la_proposition_d_operations(wiki, modele_ia, job=None):
    """
    Demande au redacteur des operations de section pour un wiki.
    / Asks the writer model for a wiki's section operations.

    LOCALISATION : front/tasks.py

    UN SEUL PROMPT pour les deux appelants — la mise a jour demandee a
    la main, et la passe de nuit. Une seconde copie de ce prompt
    divergerait de la premiere, et personne ne saurait laquelle a
    produit un article donne.
    / One prompt for both callers: the manual update and the night pass.

    :param wiki: le `Wiki` a mettre a jour / the wiki
    :param modele_ia: l'`AIModel` du role redacteur / the writer model
    :param job: l'`ExtractionJob` de la demande, s'il y en a un. La
        passe de nuit n'en a pas.
    :return: `(operations, jeton de fraicheur)` — le jeton est
        l'`updated_at` ISO de l'article APRES la reparation des titres.
    :raises ValueError: s'il n'y a rien a reprendre, ou si la reponse
        n'est pas un tableau JSON lisible.
    """
    import json as json_module

    from core.models import MotifDeTourDeWiki
    from core.services.synthese import (
        extractions_du_perimetre, extractions_ecartees, titre_de_section,
    )

    article = wiki.page
    ecartees = list(extractions_ecartees(article).order_by("pk"))
    if not ecartees:
        raise ValueError(
            "Rien à mettre à jour : toutes les extractions du "
            "périmètre sont déjà reprises par l'article. "
            "/ Nothing left out."
        )

    lignes_d_ecartees = []
    for extraction in ecartees:
        lignes_d_ecartees.append(
            f"Identifiant : ext:{extraction.pk}\n"
            f'Citation : "{extraction.extraction_text}"'
        )

    # Un article d'avant la garde mecanique peut porter des `###`, que
    # l'applieur ne resout pas. On le repare AVANT de batir le prompt :
    # sans ca, le modele verrait des titres condamnes, et la
    # proposition serait rejetee en bloc (mesure du 16 aout :
    # 6 operations proposees, 6 rejetees). La reparation ne touche que
    # la notation des titres, jamais le texte — et le jeton de
    # fraicheur est pris APRES, donc il reste juste.
    # / Repair legacy `###` before prompting, so the model never sees a
    # heading the applier will reject.
    texte_normalise = _normaliser_les_niveaux_de_titre(
        article.text_readability or ""
    )
    if texte_normalise != (article.text_readability or ""):
        # PAS un simple save() : chaque `###` ramene a `##` retire UN
        # caractere, donc decale toutes les bornes des SourceLink en
        # aval. Sauver le texte seul les perimerait — et la
        # reindexation suivante ne retrouverait plus la paire
        # (extraction, paragraphe), donc PERDRAIT les verdicts de
        # verification en silence. Passer par l'ecriture normale
        # reindexe, reconcilie les verdicts sur les ANCIENNES bornes,
        # et regenere le HTML et l'empreinte.
        # / Not a bare save(): demoting a heading shifts every
        # downstream bound, and a later reindex would silently drop the
        # verdicts. The normal write path reconciles them.
        _ecrire_le_corps_d_un_article(
            article, texte_normalise,
            set(
                extractions_du_perimetre(article)
                .values_list("pk", flat=True)
            ),
            motif_du_tour=MotifDeTourDeWiki.REPARATION_DE_TITRES,
            fait_par=_demandeur_du_job(job) if job is not None else None,
            job_du_tour=job,
            wiki_du_tour=wiki,
        )
        article.refresh_from_db()

    titres_adressables = [
        titre for titre in (
            titre_de_section(ligne)
            for ligne in (article.text_readability or "").split("\n")
        ) if titre is not None
    ]
    liste_des_titres = "\n".join(
        f"- {titre}" for titre in titres_adressables
    ) or "(l'article n'a aucune section : seule une insertion est possible)"

    prompt = (
        _prompt_systeme_de_synthese() + "\n\n"
        "=== ARTICLE ACTUEL ===\n" + article.text_readability + "\n\n"
        "=== TITRES DE SECTION ADRESSABLES ===\n"
        "Ce sont les SEULS titres que tu peux viser. Reprends-les "
        "au mot près, SANS les dièses. Toute opération visant un "
        "autre titre sera rejetée.\n"
        + liste_des_titres + "\n\n"
        "=== EXTRACTIONS NON REPRISES ===\n"
        + "\n\n".join(lignes_d_ecartees) + "\n\n"
        "=== CONSIGNE ===\n"
        "Propose des opérations de mise à jour de l'article pour "
        "intégrer ces extractions. Tu ne réécris JAMAIS l'article : "
        "tu proposes des opérations, un humain les acceptera une "
        "par une.\n"
        "UNE OPÉRATION PORTE SUR UNE SECTION, JAMAIS SUR UNE "
        "EXTRACTION. N'émets donc pas une entrée par extraction : "
        "regroupe dans une même opération toutes les extractions "
        "qui vont dans la même section, et n'émets AUCUNE entrée "
        "pour une extraction que tu écartes — ne pas la citer "
        "suffit. `no_change` est une opération GLOBALE, à émettre "
        "SEULE et seulement si aucune extraction n'apporte quoi "
        "que ce soit à l'article.\n\n"
        "=== FORMAT DE SORTIE ===\n"
        "Réponds UNIQUEMENT par un tableau JSON d'opérations, sans "
        "aucun texte autour :\n"
        '[{"type": "append_to_section", "section": "<un titre de '
        'la liste, sans dièses>", "contenu": "<markdown avec '
        '[[ext:N]]>"}, ...]\n'
        "Types permis : no_change, append_to_section, "
        "replace_section, insert_section (avec \"titre\" et "
        "\"apres\"). Chaque contenu cite ses sources par [[ext:N]] "
        "et ne contient JAMAIS de ligne de titre."
    )
    from core.llm_providers import appeler_llm
    reponse = appeler_llm(modele_ia, prompt)

    # Contrat anti-troncature : la reponse DOIT etre un tableau JSON
    # parseable — echec bruyant sinon, jamais une proposition a moitie
    # lue. / Loud failure on unparseable JSON.
    texte_json = (reponse or "").strip()
    if texte_json.startswith("```"):
        texte_json = texte_json.strip("`")
        if texte_json.startswith("json"):
            texte_json = texte_json[4:]
    try:
        operations = json_module.loads(texte_json)
        if not isinstance(operations, list):
            raise ValueError("pas un tableau")
    except (ValueError, TypeError):
        raise ValueError(
            "La proposition est arrivée illisible (pas un tableau "
            "JSON d'opérations). Rien n'a été proposé — relancez "
            "la mise à jour. / Unparseable proposal."
        )

    return operations, article.updated_at.isoformat()


@shared_task(bind=True)
def proposer_une_maj_de_wiki_task(self, job_id):
    """
    Propose des operations de section (§ 6) sur les extractions que le
    wiki n'a pas encore reprises. La proposition N'EST PAS appliquee :
    elle attend l'humain (previsualiser -> accepter, phase I). Elle
    porte l'updated_at de l'article (addendum n°1).
    / Proposes section operations on the wiki's left-out extractions;
    never auto-applied; carries the article's updated_at.

    LOCALISATION : front/tasks.py
    """
    from core.models import Wiki
    from hypostasis_extractor.models import ExtractionJob

    try:
        job = ExtractionJob.objects.get(pk=job_id)
    except ExtractionJob.DoesNotExist:
        logger.error(
            "proposer_une_maj_de_wiki_task: job=%s introuvable", job_id,
        )
        return
    if _le_job_n_est_pas_le_mien(job, "est_maj_wiki", "maj_wiki"):
        return
    try:
        job.status = "processing"
        job.save(update_fields=["status"])

        wiki = Wiki.objects.get(pk=job.raw_result["wiki_id"])
        operations, jeton_de_fraicheur = (
            construire_la_proposition_d_operations(
                wiki, job.ai_model, job=job,
            )
        )

        donnees = job.raw_result or {}
        donnees["operations"] = operations
        # La fraicheur (addendum n°1) : l'application refusera si
        # l'article a bouge depuis. / Optimistic concurrency token.
        donnees["updated_at_de_l_article"] = jeton_de_fraicheur
        job.raw_result = donnees
        job.status = "completed"
        job.save(update_fields=["raw_result", "status"])
        notifier_tache_terminee(
            user_pk=(job.raw_result or {}).get("demandeur_id") or None,
            tache_id=job.pk, tache_type="maj_wiki", status="completed",
        )
    except Exception as erreur:
        _echouer_un_job_d_article(job, erreur, "maj_wiki")


# Combien de paires un paquet de second avis note avant de repasser la
# main.
#
# POURQUOI DES PAQUETS, ET PAS UN SEUL PASSAGE. `CELERY_TASK_TIME_LIMIT`
# vaut 30 minutes (settings.py). Le juge local coute ~25 s par paire a
# six threads : la synthese dirigee etalon, avec ses 87 citations,
# demanderait 37 minutes — le worker recevrait un SIGKILL, le modele de
# 7,7 Go serait recharge, et le reste du lot n'aurait pas d'avis SANS
# QUE PERSONNE NE LE SACHE.
#
# Dix paires font ~4 min 20 : loin sous le plafond. Et le decoupage rend
# deux services de plus — un redemarrage ne coute qu'un paquet, et
# l'avancement se lit tout seul dans le nombre de paires deja notees.
# / Packets, because the 30-minute task limit would SIGKILL an 87-citation
# article mid-way, silently.
TAILLE_DU_PAQUET_DU_JUGE_LOCAL = 10


@shared_task(bind=True)
def noter_avec_le_juge_local_task(self, job_id):
    """
    Le SECOND AVIS, paquet par paquet. / The SECOND OPINION, packet by
    packet.

    LOCALISATION : front/tasks.py

    ELLE NE PILOTE RIEN. Le juge local tourne A COTE du juge de
    production pour etre compare a lui : il n'ecrit ni l'etat, ni le
    degre de production, ni le libelle affiche.

    ELLE EST IDEMPOTENTE. Elle recalcule a chaque paquet les paires qui
    n'ont pas encore d'avis DE CETTE METHODE. Relancee, elle ne refait
    pas le travail ; interrompue, elle reprend ou elle en etait.

    ELLE SE REPASSE LA MAIN. Tant qu'il reste des paires, elle remet un
    paquet en file. C'est ce qui la garde loin du plafond de 30 minutes,
    et ce qui limite la perte d'un redemarrage a un seul paquet.

    UN ECHEC NE COUTE QUE SA PAIRE. Les liens sont re-resolus a chaque
    paquet : une reindexation de wiki qui survient pendant la tache
    supprime des SourceLink (core/services/synthese.py), et il ne faut
    pas que la disparition d'un lien emporte les neuf autres.
    / Drives nothing, idempotent, self-requeueing, and a failure costs
    only its own pair.
    """
    from core.services.juges_locaux import (
        JUGES, methode, noter_une_paire, seuil_du_juge,
    )
    from core.services.verification import (
        paires_sans_avis, poser_un_avis_local,
    )
    from hypostasis_extractor.models import ExtractionJob

    try:
        job = ExtractionJob.objects.get(pk=job_id)
    except ExtractionJob.DoesNotExist:
        logger.error(
            "noter_avec_le_juge_local_task: job=%s introuvable", job_id,
        )
        return
    # La MEME garde que les quatre autres taches d'article : un message
    # mal cible ferait passer un job quelconque en `processing` puis
    # `completed` avec un bilan de second avis.
    # / The same guard as the four other article tasks.
    if _le_job_n_est_pas_le_mien(job, "est_second_avis", "second_avis"):
        return

    try:
        job.status = "processing"
        job.save(update_fields=["status"])

        # UN JUGE A LA FOIS, MAIS **A TOUR DE ROLE**, ET C'EST UN
        # CORRECTIF. Prendre systematiquement « le premier qui a du
        # reste » AFFAMAIT les trois autres : si le premier juge echoue
        # a chaque fois — modele qui ne charge pas, tokeniseur casse —
        # chaque execution le re-choisit, echoue, s'arrete, et les trois
        # suivants ne notent JAMAIS rien. Sans que rien ne le dise.
        #
        # Le tour de role part du juge qui suit celui du paquet
        # precedent : un juge en panne coute un paquet, pas la campagne.
        # / Round-robin, not first-with-backlog: a failing first judge
        # used to starve the other three silently.
        restes_par_juge = {
            nom: paires_sans_avis(job.page, methode(nom)) for nom in JUGES
        }
        noms = list(JUGES)
        precedent = (job.raw_result or {}).get("dernier_juge")
        depart = (noms.index(precedent) + 1) if precedent in noms else 0
        juge_courant = None
        restantes = []
        for decalage in range(len(noms)):
            nom_du_juge = noms[(depart + decalage) % len(noms)]
            if restes_par_juge[nom_du_juge]:
                juge_courant = nom_du_juge
                restantes = restes_par_juge[nom_du_juge]
                break

        if juge_courant is None:
            restantes, paquet, notees, sans_avis = [], [], 0, 0
            nom_de_la_methode, seuil = "", None
        else:
            nom_de_la_methode = methode(juge_courant)
            seuil = seuil_du_juge(juge_courant)
            paquet = restantes[:TAILLE_DU_PAQUET_DU_JUGE_LOCAL]
            notees = 0
            sans_avis = 0

        for paire in paquet:
            try:
                score = noter_une_paire(
                    juge_courant, paire.affirmation, paire.texte_source,
                )
                if score is None:
                    sans_avis += 1
                    continue
                poser_un_avis_local(
                    paire.lien, score=score, methode=nom_de_la_methode,
                    seuil=seuil,
                )
                notees += 1
            except Exception as erreur_de_la_paire:
                # Le lien a pu disparaitre (reindexation), ou le modele
                # caler sur une paire : ca ne doit couter que cette
                # paire. / A vanished link or a stuck pair costs itself.
                sans_avis += 1
                logger.warning(
                    "noter_avec_le_juge_local_task: paire du lien %s "
                    "perdue (job %s) : %s",
                    getattr(paire.lien, "pk", "?"), job_id,
                    erreur_de_la_paire,
                )

        donnees = job.raw_result or {}
        bilan = donnees.get("bilan_du_second_avis") or {
            "notees": 0, "sans_avis": 0,
        }
        bilan["notees"] += notees
        bilan["sans_avis"] += sans_avis
        bilan["methode"] = nom_de_la_methode
        bilan["seuil_utile"] = seuil
        # LES QUATRE JUGES SONT NOMMES DANS LE BILAN, pas seulement
        # celui du paquet courant : un bilan qui ne citerait que le
        # dernier ferait croire qu'un seul a tourne.
        # / Name all four, not just the current packet's judge.
        bilan["juges"] = [methode(nom) for nom in JUGES]
        # LE JUGE DU PAQUET, POUR QUE LE SUIVANT PRENNE LE TOUR D'APRES.
        # / Remembered so the next packet takes the next judge.
        if juge_courant:
            donnees["dernier_juge"] = juge_courant
        donnees["bilan_du_second_avis"] = bilan
        job.raw_result = donnees

        # LA CONDITION DE PROGRES, ET ELLE EST INDISPENSABLE.
        #
        # Sans elle, cette tache BOUCLE SANS FIN et en silence : si le
        # modele ne se charge pas — ou si le juge ne rend `None` pour
        # toutes les paires — le `try` par paire avale l'echec, `notees`
        # reste a zero, `restantes` ne decroit jamais, et le paquet se
        # remet en file indefiniment. Un article de plus de dix
        # citations brulerait alors du processeur pour toujours, avec un
        # job « processing » eternel qui tient aussi le verrou de
        # re-clic.
        #
        # On ne repasse donc la main QUE si le paquet a progresse. Sinon
        # on s'arrete, et le bilan porte le motif — un echec bruyant vaut
        # mieux qu'une boucle muette.
        # / Without this, a model that never loads makes the task requeue
        # itself forever, silently, holding the re-click lock.
        # IL RESTE DU TRAVAIL SI CE JUGE N'A PAS FINI, **OU** SI UN
        # AUTRE EN A. Les restes des quatre juges ont ete calcules en
        # une seule passe plus haut : les recalculer ici couterait un
        # second parcours deterministe complet par paquet.
        # / Work remains if THIS judge has more, OR another has any;
        # reuse the single pass computed above.
        un_autre_juge_a_du_reste = any(
            restes for nom, restes in restes_par_juge.items()
            if nom != juge_courant
        )
        il_reste_des_paires = (
            len(restantes) > len(paquet) or un_autre_juge_a_du_reste
        )
        if il_reste_des_paires and notees > 0:
            job.save(update_fields=["raw_result"])
            noter_avec_le_juge_local_task.delay(job_id)
            return
        if il_reste_des_paires and notees == 0:
            reste_total = sum(len(r) for r in restes_par_juge.values())
            bilan["arret_sans_progres"] = (
                f"{len(paquet)} paire(s) tentée(s) par « {juge_courant} », "
                f"aucune notée. {reste_total} paire(s) restent sans avis, "
                f"tous juges confondus."
            )
            logger.error(
                "noter_avec_le_juge_local_task: aucun progrès sur le "
                "paquet (job %s) — arrêt pour ne pas boucler.", job_id,
            )

        # LES ECHECS DU DERNIER PAQUET NE SE RETENTENT PAS TOUT SEULS,
        # et il faut donc les DIRE. Un paquet final ou la moitie des
        # paires echoue laisse `il_reste_des_paires` a faux : la tache
        # finit « completed » sans que rien ne signale les manquantes.
        # Elles restent notables — un nouveau geste les reprendra — mais
        # un compte muet aurait fait passer un lot a moitie fait pour un
        # lot fini.
        # / Last-packet failures are not auto-retried: say so.
        if sans_avis:
            bilan["paires_sans_avis_au_dernier_paquet"] = sans_avis
        job.raw_result = donnees
        job.status = "completed"
        job.save(update_fields=["raw_result", "status"])
        notifier_tache_terminee(
            user_pk=(job.raw_result or {}).get("demandeur_id") or None,
            tache_id=job.pk, tache_type="second_avis", status="completed",
        )
    except Exception as erreur:
        _echouer_un_job_d_article(job, erreur, "second_avis")


def enchainer_la_verification(page_d_article, demandeur_id=None):
    """
    Met en file le jugement des citations SANS VERDICT de cet article.
    / Queues the judging of this article's unverified citations.

    LOCALISATION : front/tasks.py

    QUAND. A la production d'un article et a chaque mise a jour
    appliquee — les deux moments ou des citations apparaissent ou
    changent. Le lecteur n'a plus a demander une verification pour
    savoir ce que vaut ce qu'il vient de lire.

    CE QUI EST JUGE, ET SEULEMENT CELA : les citations `non_verifie`.
    Une citation portee par un paragraphe intact garde son verdict et ne
    coute rien ; une citation neuve ou dont le passage a change repart
    sans verdict, et c'est elle qu'on juge.

    ⚠️ CELA APPELLE UN VRAI MODELE, ET C'EST FACTURE. Un article produit
    est un article juge : c'est le prix de ne plus avoir a le demander.
    Sans juge affecte au role, on ne met rien en file — un job qui
    echouerait faute de modele ferait un bandeau d'erreur a chaque
    production. / This calls a real, billed model. With no judge
    assigned to the role, nothing is queued.

    :param page_d_article: la Page (wiki ou synthese) qu'on vient d'ecrire
    :param demandeur_id: qui recevra la notification, s'il y a quelqu'un
    :return: le job cree, ou None
    """
    from core.models import RoleDeModele
    from core.services.modeles_par_role import modele_du_role
    from hypostasis_extractor.models import ExtractionJob

    juge = modele_du_role(RoleDeModele.JUGE_DE_VERIFICATION)
    if juge is None:
        logger.warning(
            "enchainer_la_verification: aucun juge affecte, page=%s",
            page_d_article.pk,
        )
        return None

    job = ExtractionJob.objects.create(
        page=page_d_article,
        ai_model=juge,
        name=f"Vérification — {page_d_article.title}"[:200],
        prompt_description="Vérification des citations (§ 7), enchaînée",
        status="pending",
        raw_result={
            "est_verification": True,
            "seulement_les_non_jugees": True,
            "demandeur_id": demandeur_id,
        },
    )
    verifier_les_citations_task.delay(job.pk)

    # LES QUATRE JUGES LOCAUX PARTENT AVEC, et c'est ce qui rend la
    # colonne complete. Sans eux, un article fraichement produit porte
    # des verdicts mais AUCUN controleur : le renvoi ne peut jamais
    # s'ambrer, la fiche annonce « comparaison impossible », et tout le
    # signal de tension pose le 20 aout reste mort sur les articles
    # neufs — sur les seuls, justement, qu'on vient de lire.
    #
    # Ils ne coutent RIEN a la facture : ils tournent sur cette machine,
    # sur leur propre worker a concurrence 1 et sous `nice -n 19`.
    #
    # LE FAN-OUT RESTE HORS DE `verifier_les_citations_task`, et c'est
    # la contrainte a ne pas defaire : `bin/install.sh` appelle cette
    # tache DIRECTEMENT a chaque demarrage de conteneur, et un fan-out
    # place dedans remettrait l'etalon entier en file a chaque fois.
    # Ici, on est accroche a l'ECRITURE d'un article, qui n'arrive
    # qu'une fois par production.
    # / The four local judges go with it: without them a fresh article
    # has verdicts but no controllers, and the whole tension signal is
    # dead on the very articles one has just read. They cost nothing —
    # local, concurrency 1, niced. The fan-out stays out of the task
    # itself, which install.sh calls at every container start.
    from front.views_synthese import _lancer_un_second_avis

    _lancer_un_second_avis(demandeur_id, page_d_article)
    return job


@shared_task(bind=True)
def verifier_les_citations_task(self, job_id):
    """
    La verification § 7 en asynchrone — un geste explicite, jamais
    automatique (decision Q3). / On-demand § 7 verification.

    LOCALISATION : front/tasks.py
    """
    from core.services.verification import verifier_les_citations_d_un_article
    from hypostasis_extractor.models import ExtractionJob

    try:
        job = ExtractionJob.objects.get(pk=job_id)
    except ExtractionJob.DoesNotExist:
        logger.error(
            "verifier_les_citations_task: job=%s introuvable", job_id,
        )
        return
    if _le_job_n_est_pas_le_mien(job, "est_verification", "verification"):
        return
    try:
        job.status = "processing"
        job.save(update_fields=["status"])

        # LE REGIME EST INSCRIT DANS LE JOB, pas devine ici : le bilan
        # est relu apres coup, et « 3 vérifiées » ne veut pas dire la
        # meme chose selon qu'on a juge tout l'article ou seulement ses
        # citations neuves.
        # / The regime is recorded in the job: the same count means two
        # different things depending on it.
        seulement_les_non_jugees = bool(
            (job.raw_result or {}).get("seulement_les_non_jugees")
        )
        bilan = verifier_les_citations_d_un_article(
            job.page, job.ai_model, seulement_les_non_jugees,
        )

        donnees = job.raw_result or {}
        donnees["bilan_de_verification"] = bilan
        job.raw_result = donnees
        job.status = "completed"
        job.save(update_fields=["raw_result", "status"])
        notifier_tache_terminee(
            user_pk=(job.raw_result or {}).get("demandeur_id") or None,
            tache_id=job.pk, tache_type="verification", status="completed",
        )
    except Exception as erreur:
        _echouer_un_job_d_article(job, erreur, "verification")
