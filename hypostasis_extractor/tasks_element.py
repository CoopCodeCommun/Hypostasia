"""
Taches Celery du moteur ELEMENT : ingestion et analyse.
/ Celery tasks for the ELEMENT engine: ingestion and analysis.

LOCALISATION : hypostasis_extractor/tasks_element.py

Implemente la phase H de SPEC-ancrage-par-element-v2.md.

POURQUOI UN FICHIER SEPARE DE front/tasks.py

front/tasks.py porte le moteur ANCIEN : 1400 lignes qui reconstruisent a
la main le pipeline de LangExtract pour pouvoir suivre sa progression. Le
moteur ELEMENT n'a pas besoin de ce fork : il decoupe lui-meme et appelle
LangExtract chunk par chunk (voir services/analyse_par_element.py).

Melanger les deux dans le meme fichier rendrait chacun plus difficile a
lire, et rendrait la suppression du moteur ANCIEN plus risquee le jour ou
elle arrivera.
/ Keeping them apart makes the eventual removal of the old engine safer.
"""

import logging
import time

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def analyser_une_page_avec_le_moteur_element(self, identifiant_du_job):
    """
    Analyse une page avec le moteur ELEMENT, de bout en bout.
    / Analyses a page with the ELEMENT engine, end to end.

    LOCALISATION : hypostasis_extractor/tasks_element.py

    :param identifiant_du_job: la cle primaire d'un ExtractionJob deja
        cree, en statut PENDING, avec sa page, son modele et son prompt.
    :return: le bilan de l'analyse, ou un dict d'erreur

    CE QUE FAIT LA TACHE, DANS L'ORDRE :

    1. Elle charge le job et verifie que l'IA est activee.
    2. Elle s'assure que la page a des elements — sans elements, il n'y a
       rien a analyser, et il vaut mieux le dire que produire zero
       extraction en silence.
    3. Elle lance l'analyse (services/analyse_par_element.py), qui fait
       passer le job en PROCESSING — ce qui bloque l'edition de la page
       pendant tout le traitement (services/garde_edition.py).
    4. Elle previent l'utilisateur a la fin.

    LE KILL-SWITCH EST VERIFIE ICI, PAS DANS LE SERVICE

    Le service d'analyse ne connait pas la configuration de
    l'application : il fait ce qu'on lui demande. C'est la tache, point
    d'entree depuis l'interface, qui doit refuser de depenser de l'argent
    quand l'IA est desactivee.
    / The service does as told; the task is where money is refused.
    """
    from django.utils import timezone

    from core.models import Configuration
    from hypostasis_extractor.models import ExtractionJob, ExtractionJobStatus
    from hypostasis_extractor.services.analyse_par_element import (
        lancer_l_analyse_d_une_page,
    )

    debut_du_traitement = time.time()

    try:
        job_extraction = ExtractionJob.objects.select_related(
            "page", "ai_model",
        ).get(pk=identifiant_du_job)
    except ExtractionJob.DoesNotExist:
        logger.error(
            "Job %s introuvable : la tache s'arrete.", identifiant_du_job,
        )
        return {"erreur": "job introuvable"}

    page = job_extraction.page

    # L'IA est-elle activee ? Sans cette verification, un job lance
    # pendant que l'IA est coupee partirait quand meme appeler un
    # fournisseur payant.
    # / Without this, a job would spend money while the AI is switched off.
    if not Configuration.get_solo().ai_active:
        job_extraction.status = ExtractionJobStatus.ERROR
        job_extraction.error_message = (
            "L'IA est desactivee dans la configuration. Analyse annulee."
        )
        job_extraction.save(
            update_fields=["status", "error_message", "updated_at"],
        )
        logger.info(
            "Job %s annule : l'IA est desactivee.", identifiant_du_job,
        )
        return {"erreur": "IA desactivee"}

    # Une page sans element n'a rien a analyser. Le dire vaut mieux que
    # de rendre « 0 extraction » sans expliquer pourquoi.
    # / A page with no element has nothing to analyse; say so.
    nombre_d_elements = page.elements.filter(masque=False).count()
    if nombre_d_elements == 0:
        job_extraction.status = ExtractionJobStatus.ERROR
        job_extraction.error_message = (
            "Cette page n'a aucun element a analyser. Elle doit d'abord "
            "etre ingeree avec le moteur ELEMENT (services/ingestion_docling.py) "
            "ou basculee (manage.py basculer_vers_le_moteur_element)."
        )
        job_extraction.save(
            update_fields=["status", "error_message", "updated_at"],
        )
        logger.warning(
            "Job %s : la page %s n'a aucun element.", identifiant_du_job, page.pk,
        )
        return {"erreur": "page sans element"}

    # Le job doit avoir un modele. Sans lui, resolve_model_params tombe en
    # AttributeError a chaque chunk, et le job finirait en erreur avec
    # « les N chunks ont echoue » — un message qui fait croire a une panne
    # du fournisseur alors que c'est une configuration incomplete.
    # / Without a model, the failure would look like a provider outage.
    if job_extraction.ai_model is None:
        job_extraction.status = ExtractionJobStatus.ERROR
        job_extraction.error_message = (
            "Ce job n'a pas de modele d'IA configure. Choisir un modele "
            "avant de lancer l'analyse."
        )
        job_extraction.save(
            update_fields=["status", "error_message", "updated_at"],
        )
        logger.warning("Job %s : aucun modele d'IA.", identifiant_du_job)
        return {"erreur": "modele absent"}

    # UNE SEULE TACHE A LA FOIS SUR UN JOB.
    #
    # Celery peut redelivrer un message : worker tue, reessai, double
    # envoi depuis l'interface. Deux taches sur le meme job purgeraient
    # puis insereraient chacune leurs extractions, avec un entrelacement
    # qui produit des doublons et un entities_count faux.
    #
    # La transition PENDING -> PROCESSING est faite ici, en une seule
    # requete atomique. Celle qui perd la course voit 0 ligne modifiee et
    # s'arrete. / An atomic transition; the loser stops.
    lignes_modifiees = ExtractionJob.objects.filter(
        pk=identifiant_du_job,
        status=ExtractionJobStatus.PENDING,
    ).update(
        status=ExtractionJobStatus.PROCESSING,
        error_message=None,
        updated_at=timezone.now(),
    )
    if lignes_modifiees == 0:
        job_extraction.refresh_from_db()
        logger.warning(
            "Job %s deja pris en charge (statut %s) : cette tache s'arrete "
            "pour ne pas dupliquer les extractions.",
            identifiant_du_job, job_extraction.status,
        )
        return {"erreur": "job deja en cours ou termine"}

    job_extraction.refresh_from_db()

    logger.info(
        "Job %s : analyse de la page %s (%s element(s)) par le moteur ELEMENT.",
        identifiant_du_job, page.pk, nombre_d_elements,
    )

    try:
        bilan = lancer_l_analyse_d_une_page(page, job_extraction)
    except Exception as erreur:
        # lancer_l_analyse_d_une_page a deja passe le job en ERROR et
        # journalise. On previent quand meme l'utilisateur : sans ca, son
        # interface tournerait indefiniment.
        # / The job is already in ERROR; the user must still be told.
        logger.exception("Job %s : analyse interrompue.", identifiant_du_job)
        _prevenir_l_utilisateur(job_extraction, "error")
        raise

    duree = time.time() - debut_du_traitement
    job_extraction.processing_time_seconds = duree
    job_extraction.save(update_fields=["processing_time_seconds"])

    job_extraction.refresh_from_db()
    _prevenir_l_utilisateur(job_extraction, job_extraction.status)

    logger.info(
        "Job %s termine en %.1f s : %s extraction(s), %s portion(s).",
        identifiant_du_job, duree, bilan["extractions"], bilan["portions"],
    )
    return bilan


def _prevenir_l_utilisateur(job_extraction, statut):
    """
    Envoie la notification de fin de tache au proprietaire de la page.
    / Sends the end-of-task notification to the page owner.

    LOCALISATION : hypostasis_extractor/tasks_element.py

    On reutilise le meme canal que le moteur ANCIEN : l'interface ecoute
    deja ces evenements, il n'y a aucune raison d'en inventer un autre.
    / Same channel as the old engine; the UI already listens to it.
    """
    from front.tasks import notifier_tache_terminee

    proprietaire = getattr(job_extraction.page, "owner", None)
    if proprietaire is None:
        return

    try:
        notifier_tache_terminee(
            user_pk=proprietaire.pk,
            tache_id=job_extraction.pk,
            tache_type="analyse",
            status=statut,
        )
    except Exception as erreur:
        # Une notification qui echoue ne doit pas faire echouer une
        # analyse qui, elle, a reussi.
        # / A failed notification must not fail a successful analysis.
        logger.warning(
            "Job %s : notification non envoyee (%s).",
            job_extraction.pk, erreur,
        )


def _noter_l_etat_d_ingestion(identifiant_de_la_page, etat, detail=""):
    """
    Ecrit l'etat d'ingestion sur la page, en une requete UPDATE (U2).
    / Writes the ingestion state on the page in one UPDATE query.

    LOCALISATION : hypostasis_extractor/tasks_element.py

    Un update() cible, jamais un save() de l'objet entier : la page
    peut etre modifiee ailleurs pendant la conversion (titre, carnets),
    on ne doit ecraser que ces trois champs. L'horodatage permet a la
    relance de detecter un etat actif FANTOME (worker tue, relecture
    U2 defaut H2). La tache FAIT FOI : elle ecrit sans condition —
    c'est la VUE qui pose son etat sous condition (defaut H1).
    / Targeted update with a timestamp; the task's write always wins,
    the view's write is conditional.
    """
    from django.utils import timezone

    from core.models import Page

    Page.objects.filter(pk=identifiant_de_la_page).update(
        ingestion_etat=etat, ingestion_detail=detail,
        ingestion_maj_le=timezone.now(),
    )


@shared_task(bind=True)
def ingerer_un_fichier_avec_docling(self, identifiant_de_la_page, chemin_du_fichier=None):
    """
    Convertit un fichier en elements, via Docling.
    / Converts a file into elements, via Docling.

    LOCALISATION : hypostasis_extractor/tasks_element.py

    :param identifiant_de_la_page: la cle primaire de la Page a peupler
    :param chemin_du_fichier: le fichier source a convertir. Si None
        (cas normal depuis la vue d'import, BR-B), la tache le resout
        elle-meme depuis page.source_file — la vue n'a pas a connaitre
        le stockage. / If None, resolved from page.source_file.
    :return: {"elements": int} ou un dict d'erreur

    POURQUOI C'EST UNE TACHE SEPAREE DE L'ANALYSE

    La conversion Docling est longue — elle charge des modeles — et elle
    ne coute rien en appels LLM. L'analyse, elle, coute de l'argent. Les
    separer permet de re-analyser une page sans la reconvertir, et de
    convertir sans lancer d'analyse.
    / Converting is slow but free; analysing costs money. Keep them apart.
    """
    from core.models import EtatIngestion, Page
    from hypostasis_extractor.services import ingestion_docling

    try:
        page = Page.objects.get(pk=identifiant_de_la_page)
    except Page.DoesNotExist:
        logger.error("Page %s introuvable.", identifiant_de_la_page)
        return {"erreur": "page introuvable"}

    if page.elements.exists():
        logger.warning(
            "Page %s a deja des elements : ingestion refusee. Utiliser la "
            "re-ingestion pour ne pas perdre les ancres existantes.",
            page.pk,
        )
        # Redelivraison Celery apres un succes : la page a ses
        # elements, l'etat le dit. (U2)
        # / Celery redelivery after success: keep the state truthful.
        _noter_l_etat_d_ingestion(page.pk, EtatIngestion.REUSSIE)
        return {"erreur": "page deja ingeree"}

    # L'etat « en cours » est visible dans la lecture (U2) — c'est le
    # premier moment ou l'on SAIT que le worker a pris le travail.
    # / First moment the worker provably took the job.
    _noter_l_etat_d_ingestion(page.pk, EtatIngestion.EN_COURS)

    # Resoudre le chemin depuis la page si la vue ne l'a pas donne.
    # `.path` peut lever avec un stockage non-fichier : on le dit
    # proprement au lieu de faire planter le worker.
    # / Resolve the path from the page; say it cleanly if impossible.
    if chemin_du_fichier is None:
        if not page.source_file:
            logger.error(
                "Page %s : pas de fichier source, ingestion impossible.",
                page.pk,
            )
            _noter_l_etat_d_ingestion(
                page.pk, EtatIngestion.ECHOUEE,
                "Le fichier d'origine n'est plus disponible : le "
                "découpage en éléments est impossible. La note reste "
                "lisible.",
            )
            return {"erreur": "page sans fichier source"}
        try:
            chemin_du_fichier = page.source_file.path
        except Exception as erreur_de_stockage:
            logger.error(
                "Page %s : le stockage ne donne pas de chemin local (%s).",
                page.pk, erreur_de_stockage,
            )
            _noter_l_etat_d_ingestion(
                page.pk, EtatIngestion.ECHOUEE,
                "Le fichier d'origine n'est pas accessible sur ce "
                "serveur : le découpage en éléments est impossible. La "
                "note reste lisible.",
            )
            return {"erreur": "fichier source sans chemin local"}

    try:
        elements = ingestion_docling.ingerer_un_fichier(page, chemin_du_fichier)
    except Exception as erreur:
        logger.exception(
            "Page %s : l'ingestion Docling a echoue.", page.pk,
        )
        # Le detail technique va au journal ; l'ecran parle simplement
        # et rappelle que rien n'est perdu (U2, FALC).
        # / Technical detail in the log; the screen speaks plainly.
        _noter_l_etat_d_ingestion(
            page.pk, EtatIngestion.ECHOUEE,
            "La conversion du fichier a échoué. La note reste lisible "
            "telle quelle. Vous pouvez relancer le découpage.",
        )
        return {"erreur": str(erreur)}

    _noter_l_etat_d_ingestion(page.pk, EtatIngestion.REUSSIE)
    logger.info(
        "Page %s : %s element(s) ingere(s) depuis %s.",
        page.pk, len(elements), chemin_du_fichier,
    )
    return {"elements": len(elements)}


@shared_task(bind=True)
def ingerer_une_capture_web_avec_docling(self, identifiant_de_la_page):
    """
    Convertit le HTML d'une capture web en elements, via Docling (U4).
    / Converts a web capture's HTML into elements, via Docling.

    LOCALISATION : hypostasis_extractor/tasks_element.py

    Decision D2 (ordre 2) : meme patron que l'ingestion de fichier,
    mais la source est page.html_original (pas un fichier sur disque).
    Meme file dediee `ingestion_docling` a concurrence 1, memes etats
    (U2), meme repli honnete : un echec laisse une page ANCIEN lisible.
    / Same pattern as file ingestion; the source is the captured HTML.

    :param identifiant_de_la_page: la cle primaire de la Page capturee
    :return: {"elements": int} ou un dict d'erreur
    """
    from core.models import EtatIngestion, Page
    from hypostasis_extractor.services import ingestion_docling

    try:
        page = Page.objects.get(pk=identifiant_de_la_page)
    except Page.DoesNotExist:
        logger.error("Page %s introuvable.", identifiant_de_la_page)
        return {"erreur": "page introuvable"}

    if page.elements.exists():
        logger.warning(
            "Page %s a deja des elements : ingestion web refusee.", page.pk,
        )
        _noter_l_etat_d_ingestion(page.pk, EtatIngestion.REUSSIE)
        return {"erreur": "page deja ingeree"}

    _noter_l_etat_d_ingestion(page.pk, EtatIngestion.EN_COURS)

    try:
        elements = ingestion_docling.ingerer_une_capture_web(page)
    except ValueError as erreur:
        # Pas de HTML a decouper : dit simplement, page lisible.
        # / No HTML to split; said plainly, page still readable.
        logger.warning("Page %s : capture sans HTML (%s).", page.pk, erreur)
        _noter_l_etat_d_ingestion(
            page.pk, EtatIngestion.ECHOUEE,
            "Cette page capturée n'a pas de contenu à découper en "
            "éléments. Elle reste lisible telle quelle.",
        )
        return {"erreur": "capture sans html"}
    except Exception as erreur:
        logger.exception(
            "Page %s : l'ingestion Docling du HTML a echoue.", page.pk,
        )
        _noter_l_etat_d_ingestion(
            page.pk, EtatIngestion.ECHOUEE,
            "La conversion de la page capturée a échoué. La note reste "
            "lisible telle quelle. Vous pouvez relancer le découpage.",
        )
        return {"erreur": str(erreur)}

    _noter_l_etat_d_ingestion(page.pk, EtatIngestion.REUSSIE)
    logger.info(
        "Page %s : %s element(s) ingere(s) depuis le HTML capture.",
        page.pk, len(elements),
    )
    return {"elements": len(elements)}


@shared_task(bind=True)
def ingerer_une_transcription_diarisee_en_elements(self, identifiant_de_la_page):
    """
    Convertit la transcription d'un audio en elements (D2, ordre 3).
    / Converts an audio transcript into elements.

    LOCALISATION : hypostasis_extractor/tasks_element.py

    Le dernier flux a rejoindre le moteur ELEMENT. Meme patron que
    l'import de fichier (BR-B) et la capture web (U4) : meme surface
    d'etat (U2), meme garde de re-ingestion, meme repli honnete.

    UNE DIFFERENCE, ET ELLE COMPTE : PAS DE DOCLING.

    Il n'y a rien a convertir — la transcription EST deja structuree,
    en tours de parole diarises. Cette tache ne charge donc aucun modele
    et ne passe pas par la file `ingestion_docling` a concurrence 1 :
    elle ne pese rien, la ou une conversion Docling charge plusieurs Go.
    / No Docling here: a transcript is already structured.

    :param identifiant_de_la_page: la cle primaire de la Page audio
    :return: {"elements": int} ou un dict d'erreur
    """
    from core.models import EtatIngestion, Page
    from hypostasis_extractor.services.ingestion_audio import (
        ingerer_une_transcription_diarisee,
    )

    try:
        page = Page.objects.get(pk=identifiant_de_la_page)
    except Page.DoesNotExist:
        logger.error("Page %s introuvable.", identifiant_de_la_page)
        return {"erreur": "page introuvable"}

    if page.elements.exists():
        logger.warning(
            "Page %s a deja des elements : ingestion audio refusee.", page.pk,
        )
        _noter_l_etat_d_ingestion(page.pk, EtatIngestion.REUSSIE)
        return {"erreur": "page deja ingeree"}

    _noter_l_etat_d_ingestion(page.pk, EtatIngestion.EN_COURS)

    # UNE LEVEE NE DOIT PAS FIGER L'ETAT SUR « EN COURS ».
    #
    # Le service promet de ne pas lever pour un cas normal, mais un cas
    # ANORMAL existe : deux workers sur la meme page passent tous deux
    # la garde `elements.exists()`, et le second prend le ValueError de
    # `creer_les_elements_d_une_page`. Sans ce filet, la tache meurt et
    # l'etat reste EN_COURS pour toujours — la puce d'ingestion tourne
    # dans le vide et « Relancer » refuse d'agir. Les trois autres
    # taches d'ingestion ont ce filet ; celle-ci l'avait oublie.
    # / Without this, a crash freezes the state on EN_COURS forever.
    try:
        resultat = ingerer_une_transcription_diarisee(page)
    except Exception as erreur:  # noqa: BLE001 — on veut TOUT rattraper
        logger.exception(
            "Page %s : l'ingestion de la transcription a echoue.", page.pk,
        )
        _noter_l_etat_d_ingestion(
            page.pk, EtatIngestion.ECHOUEE,
            "Le découpage de cette transcription en tours de parole a "
            "échoué. L'enregistrement reste lisible tel quel.",
        )
        return {"erreur": str(erreur)}

    if "erreur" in resultat:
        # Une transcription vide ou illisible n'est pas un plantage :
        # la page reste lisible par son HTML diarise, et l'etat le dit.
        # / An empty transcript is not a crash; the page stays readable.
        _noter_l_etat_d_ingestion(
            page.pk, EtatIngestion.ECHOUEE,
            "Cet enregistrement n'a pas de transcription exploitable à "
            "découper en tours de parole. Il reste lisible tel quel.",
        )
        return resultat

    _noter_l_etat_d_ingestion(page.pk, EtatIngestion.REUSSIE)
    logger.info(
        "Page %s : %s element(s) crees depuis la transcription.",
        page.pk, resultat["elements_crees"],
    )
    return {"elements": resultat["elements_crees"]}
