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
    from front.tasks import _destinataires_de_notification, notifier_tache_terminee

    for pk_destinataire in _destinataires_de_notification(job_extraction.page):
        if pk_destinataire is None:
            continue
        try:
            notifier_tache_terminee(
                user_pk=pk_destinataire,
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

    Un cycle qui REDEMARRE (en_attente/en_cours) rearme aussi
    ingestion_notification_lue a False : sinon une relance qui succede
    a une notification deja lue ne rallume jamais le badge — le
    drapeau restait a True pour toujours (revue adverse, tache 8,
    addendum du 11 aout 2026). On le fait ICI, au seul endroit qui
    ecrit l'etat pour toutes les taches d'ingestion, plutot que de
    l'eparpiller chez chaque appelant.
    / A cycle restarting also rearms the read flag here — the single
    place writing ingestion state for every ingestion task — rather
    than scattering the reset across callers.

    Correction 1 (revue de cloture du 11 aout, defaut 1 : drapeau par
    destinataire) : le meme rearmement s'applique aux lignes
    NotificationTacheLue de TOUS les destinataires (auteur de la note
    ET proprietaire d'un carnet qui la contient) — pas seulement au
    booleen legacy, mort pour la decision mais laisse en place. Sans
    ce nettoyage, un destinataire qui avait deja lu un cycle precedent
    ne reverrait plus JAMAIS la notification de fin du nouveau cycle.
    / Same rearming for every recipient's NotificationTacheLue rows —
    without it, a past reader would never see a new cycle's completion.

    Correction du 14 aout 2026 (relecture adverse, defaut 1) : c'est
    aussi d'ici que part la notification de FILE QUI AVANCE. Toute
    ecriture d'un etat qui fait SORTIR de la file — en_cours, reussie,
    echouee — decale le rang de ceux qui restent derriere. La placer
    chez les appelants l'avait deja fait oublier a six endroits : les
    trois passages a `en_cours`, et les trois gardes « page deja
    ingeree » qui ecrivent `reussie` puis rendent la main sans rien
    dire. Ici, aucun chemin ne peut y echapper.
    / The queue-moved notification also fires from here: every state
    that LEAVES the queue shifts everyone else's rank. Placing it in
    the callers had already missed six paths.
    """
    from django.utils import timezone

    from core.models import EtatIngestion, NotificationTacheLue, Page

    valeurs_a_ecrire = {
        "ingestion_etat": etat, "ingestion_detail": detail,
        "ingestion_maj_le": timezone.now(),
    }

    # LE TEXTE PLAT DEVIENT UNE PROJECTION DES ELEMENTS.
    #
    # L'import d'un fichier ecrivait DEUX textes concurrents : celui de la
    # conversion synchrone (MarkItDown), puis les elements de Docling.
    # Mesure du 17 aout 2026 : une note portait 58 524 signes de texte
    # plat ET 189 elements, dont les offsets n'avaient aucun rapport.
    # C'est pire qu'un champ vide : un lecteur du champ plat y trouve un
    # texte non vide mais FAUX.
    #
    # On ne garde pas deux verites, et on ne supprime pas le champ — il
    # porte l'empreinte de deduplication et sert de repli aux pages sans
    # element. On le DERIVE : une seule verite, les elements, dont le
    # champ plat n'est que la projection.
    #
    # SEULEMENT a la reussite, et SEULEMENT s'il y a des elements : un
    # etat « en cours » qui viderait le champ laisserait la note blanche
    # a l'ecran pendant la conversion, et une reussite sans element
    # effacerait le seul texte disponible.
    # / The flat text becomes a derived projection of the elements — one
    # truth. Only on success, and only when elements exist.
    if etat == EtatIngestion.REUSSIE:
        from core.models import ElementDocument

        # Les MASQUES sont exclus, comme partout ailleurs : le lecteur ne
        # les montre pas, l'analyse ne les lit pas, l'ancrage les ignore.
        # Et on reutilise LE separateur du chunking plutot que d'en
        # recopier la valeur : le jour ou il change, il change ici aussi.
        # / Masked elements excluded, and THE shared separator reused.
        from hypostasis_extractor.services.ancrage import (
            SEPARATEUR_DE_JONCTION,
        )

        textes_des_elements = list(
            ElementDocument.objects.filter(
                page_id=identifiant_de_la_page, masque=False,
            ).order_by("ordre").values_list("texte", flat=True)
        )
        if textes_des_elements:
            valeurs_a_ecrire["text_readability"] = (
                SEPARATEUR_DE_JONCTION.join(textes_des_elements)
            )
    if etat in (EtatIngestion.EN_ATTENTE, EtatIngestion.EN_COURS):
        valeurs_a_ecrire["ingestion_notification_lue"] = False
        NotificationTacheLue.objects.filter(
            type_tache="ingestion", tache_id=identifiant_de_la_page,
        ).delete()

    Page.objects.filter(pk=identifiant_de_la_page).update(**valeurs_a_ecrire)

    # Entrer dans la file ne change le rang de personne : la page se
    # range derriere tout le monde. Les trois autres etats, eux, la
    # font sortir. / Joining the queue shifts nobody; the other three
    # states leave it.
    if etat != EtatIngestion.EN_ATTENTE:
        _prevenir_la_file_d_attente(identifiant_de_la_page)


def _traiter_comme_deja_ingeree(page):
    """
    Pose REUSSIE quand la page a deja ses elements malgre une erreur
    remontee par le service d'ingestion.
    / Marks REUSSIE when the page already has its elements despite an
    error raised by the ingestion service.

    LOCALISATION : hypostasis_extractor/tasks_element.py

    Deux executions concurrentes de la meme tache peuvent toutes deux
    franchir la garde d'entree avant que l'une n'ait fini d'ecrire : la
    perdante voit alors une erreur — une ValueError levee par
    creer_les_elements_d_une_page (Docling), ou
    {"erreur": "page deja ingeree"} rendu par le service audio — alors
    que le travail EST fait. « Page deja ingeree » n'est pas un echec :
    c'est le constat que le travail est fait, et les trois taches
    d'ingestion doivent le dire de la meme facon plutot que de repeter
    chacune leur propre logique.
    / The loser of a race sees an error though the work is done; the
    three ingestion tasks share this net instead of repeating it.

    :param page: la Page dont l'etat vient d'etre constate deja fait
    :return: {"erreur": "page deja ingeree"}, la meme reponse que celle
        rendue par la garde d'entree de chaque tache dans ce cas
    """
    from core.models import EtatIngestion

    logger.info(
        "Page %s : ingestion deja faite par une autre execution (course "
        "ou redelivrance), etat REUSSIE.", page.pk,
    )
    _noter_l_etat_d_ingestion(page.pk, EtatIngestion.REUSSIE)
    _prevenir_de_l_ingestion(page, "completed")
    return {"erreur": "page deja ingeree"}


def _prevenir_de_l_ingestion(page, statut):
    """
    Previent les interesses qu'un decoupage en elements s'est termine.
    / Tells the concerned parties an element ingestion has finished.

    LOCALISATION : hypostasis_extractor/tasks_element.py

    POURQUOI CETTE FONCTION

    Une ingestion de PDF prend 80 a 164 s (mesure du 11 aout 2026). Sans
    notification, l'utilisateur qui vient d'importer un document n'a
    aucun moyen de savoir quand son document est pret : il rafraichit au
    jugé. Les trois taches d'ingestion etaient les seules du projet a ne
    rien dire.
    / An ingestion takes up to 164 s; without this, nobody knows when.

    UNE INGESTION N'A PAS DE JOB

    Les analyses ont un ExtractionJob, les transcriptions un
    TranscriptionJob. Une ingestion n'a que sa Page, dont
    `ingestion_etat` porte l'etat. On passe donc la cle primaire de la
    PAGE comme `tache_id` — la vue des taches le sait et cherche au bon
    endroit. / An ingestion has no job: the page's pk is the task id.

    :param page: la Page ingeree
    :param statut: "completed" ou "error"
    """
    from front.tasks import (
        _destinataires_de_notification, notifier_tache_terminee,
    )

    for pk_destinataire in _destinataires_de_notification(page):
        if pk_destinataire is None:
            continue
        try:
            notifier_tache_terminee(
                user_pk=pk_destinataire,
                tache_id=page.pk,
                tache_type="ingestion",
                status=statut,
            )
        except Exception as erreur:
            # Une notification qui echoue ne doit pas faire echouer une
            # ingestion qui, elle, a reussi. Meme principe que partout
            # ailleurs dans ce fichier.
            # / A failed notification must not fail a successful ingestion.
            logger.warning(
                "Page %s : notification d'ingestion non transmise (%s).",
                page.pk, erreur,
            )


def _prevenir_la_file_d_attente(identifiant_de_la_page_sortie):
    """
    Previent ceux qui attendent derriere que la file a avance.
    / Tells those waiting behind that the queue has moved.

    LOCALISATION : hypostasis_extractor/tasks_element.py

    POURQUOI

    Le menu des taches affiche une position dans la file d'ingestion
    (« 3ᵉ dans la file », front/views_taches.py). Cette position vient
    de changer pour tous ceux qui attendent — et eux n'ont aucun moyen
    de l'apprendre : rien ne s'est passe de leur cote, et il n'existe
    aucun polling de secours (le WebSocket est le seul rafraichissement
    du menu). Sans ce fan-out, le chiffre affiche se fige, ce qui se lit
    comme une file bloquee.
    / Nothing on their side could tell them, and there is no polling
    fallback. A frozen number reads as a stuck queue.

    QUAND, EXACTEMENT

    A chaque etat qui fait SORTIR de la file, et pas seulement a la fin
    d'une ingestion : le passage a `en_cours` sort aussi une page de la
    file. C'est pourquoi l'appel vit dans `_noter_l_etat_d_ingestion` —
    le point de passage unique de l'ecriture d'etat — et non chez ses
    appelants, ou six chemins l'avaient deja manque.
    / On every state that LEAVES the queue, not just at the end.

    CE QUI EST ENVOYE, ET A QUI

    Un message sans donnee, un par UTILISATEUR (pas par page) : deux
    notes en file du meme destinataire ne valent qu'un rafraichissement.
    Les destinataires sont rassembles en DEUX requetes fixes, quelle que
    soit la longueur de la file — proprietaires des notes, puis
    proprietaires des carnets qui les contiennent. Les interroger page
    par page serait le N+1 que le calcul du rang evite justement cote
    vue.
    / Recipients gathered in two fixed queries, never one per page.

    Les fantomes sont exclus — leur worker est mort, leur proprietaire
    n'attend plus rien, et ils ne comptent deja plus dans les rangs
    affiches. La page qui vient de sortir est exclue aussi : une
    re-ingestion peut la remettre en attente dans la foulee, mais son
    proprietaire est deja prevenu par la notification de fin.
    / Ghosts and the page that just left are excluded.

    :param identifiant_de_la_page_sortie: la cle primaire de la page
        qui vient de quitter la file
    """
    from datetime import timedelta

    from django.utils import timezone

    from core.models import AppartenancePageDossier, EtatIngestion, Page
    from front.tasks import notifier_la_file_d_ingestion
    from front.views import DELAI_INGESTION_FANTOME_MIN

    seuil_fantome = timezone.now() - timedelta(minutes=DELAI_INGESTION_FANTOME_MIN)
    pages_encore_en_file = Page.objects.filter(
        ingestion_etat=EtatIngestion.EN_ATTENTE,
        ingestion_maj_le__gte=seuil_fantome,
    ).exclude(pk=identifiant_de_la_page_sortie)

    # Les memes destinataires que _destinataires_de_notification
    # (front/tasks.py) — l'auteur de la note ET les proprietaires des
    # carnets qui la contiennent — mais rassembles pour TOUTES les pages
    # en file d'un coup. / Same recipients, gathered for every queued
    # page at once.
    pks_a_prevenir = set(
        pages_encore_en_file.filter(owner__isnull=False)
        .values_list("owner_id", flat=True)
    )
    pks_a_prevenir.update(
        AppartenancePageDossier.objects.filter(
            page__in=pages_encore_en_file, dossier__owner__isnull=False,
        ).values_list("dossier__owner_id", flat=True)
    )

    for pk_destinataire in sorted(pks_a_prevenir):
        try:
            notifier_la_file_d_ingestion(user_pk=pk_destinataire)
        except Exception as erreur:
            # Meme principe que la notification de fin : prevenir la
            # file est un service rendu, jamais une condition de succes
            # de l'ingestion. / A courtesy, never a success condition.
            logger.warning(
                "File d'ingestion : utilisateur %s non prevenu (%s).",
                pk_destinataire, erreur,
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
            _prevenir_de_l_ingestion(page, "error")
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
            _prevenir_de_l_ingestion(page, "error")
            return {"erreur": "fichier source sans chemin local"}

    try:
        elements = ingestion_docling.ingerer_un_fichier(page, chemin_du_fichier)
    except Exception as erreur:
        if page.elements.exists():
            # Course avec une autre execution qui a fini la conversion
            # en premier : creer_les_elements_d_une_page a refuse
            # (ValueError) parce que la place etait deja prise, pas
            # parce que la conversion a rate.
            # / A concurrent run finished first; not a conversion failure.
            return _traiter_comme_deja_ingeree(page)
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
        _prevenir_de_l_ingestion(page, "error")
        return {"erreur": str(erreur)}

    _noter_l_etat_d_ingestion(page.pk, EtatIngestion.REUSSIE)
    _prevenir_de_l_ingestion(page, "completed")
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
        if page.elements.exists():
            # Meme course que l'ingestion de fichier : la ValueError
            # vient de creer_les_elements_d_une_page (place deja
            # prise), pas de l'absence de HTML.
            # / Same race as file ingestion, not a missing-HTML case.
            return _traiter_comme_deja_ingeree(page)
        # Pas de HTML a decouper : dit simplement, page lisible.
        # / No HTML to split; said plainly, page still readable.
        logger.warning("Page %s : capture sans HTML (%s).", page.pk, erreur)
        _noter_l_etat_d_ingestion(
            page.pk, EtatIngestion.ECHOUEE,
            "Cette page capturée n'a pas de contenu à découper en "
            "éléments. Elle reste lisible telle quelle.",
        )
        _prevenir_de_l_ingestion(page, "error")
        return {"erreur": "capture sans html"}
    except Exception as erreur:
        if page.elements.exists():
            return _traiter_comme_deja_ingeree(page)
        logger.exception(
            "Page %s : l'ingestion Docling du HTML a echoue.", page.pk,
        )
        _noter_l_etat_d_ingestion(
            page.pk, EtatIngestion.ECHOUEE,
            "La conversion de la page capturée a échoué. La note reste "
            "lisible telle quelle. Vous pouvez relancer le découpage.",
        )
        _prevenir_de_l_ingestion(page, "error")
        return {"erreur": str(erreur)}

    _noter_l_etat_d_ingestion(page.pk, EtatIngestion.REUSSIE)
    _prevenir_de_l_ingestion(page, "completed")
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
        _prevenir_de_l_ingestion(page, "error")
        return {"erreur": str(erreur)}

    if resultat.get("erreur") == "page deja ingeree":
        # Meme raisonnement que la garde d'entree de cette tache, plus
        # haut : le service vient de constater que la place est deja
        # prise (course avec une autre execution). Ce n'est pas un
        # echec, c'est le travail deja fait.
        # / Same reasoning as this task's entry guard: not a failure.
        return _traiter_comme_deja_ingeree(page)

    if "erreur" in resultat:
        # Une transcription vide ou illisible n'est pas un plantage :
        # la page reste lisible par son HTML diarise, et l'etat le dit.
        # / An empty transcript is not a crash; the page stays readable.
        _noter_l_etat_d_ingestion(
            page.pk, EtatIngestion.ECHOUEE,
            "Cet enregistrement n'a pas de transcription exploitable à "
            "découper en tours de parole. Il reste lisible tel quel.",
        )
        _prevenir_de_l_ingestion(page, "error")
        return resultat

    _noter_l_etat_d_ingestion(page.pk, EtatIngestion.REUSSIE)
    _prevenir_de_l_ingestion(page, "completed")
    logger.info(
        "Page %s : %s element(s) crees depuis la transcription.",
        page.pk, resultat["elements_crees"],
    )
    return {"elements": resultat["elements_crees"]}
