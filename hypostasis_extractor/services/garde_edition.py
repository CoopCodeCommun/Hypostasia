"""
Interdit d'editer une page pendant qu'une analyse tourne dessus.
/ Forbids editing a page while an analysis is running on it.

LOCALISATION : hypostasis_extractor/services/garde_edition.py

LE PROBLEME QUE CE FICHIER RESOUT

Une analyse LangExtract se deroule en plusieurs temps : on decoupe la page
en chunks, on envoie chaque chunk au LLM, on attend les reponses, puis on
traduit les spans rendus en portions d'ancrage. Entre le decoupage et
l'ancrage, il peut s'ecouler plusieurs minutes.

Si quelqu'un edite un element pendant ce temps, le job travaille sur un
texte qui n'existe plus. Deux issues, toutes deux mauvaises :

  - le job garde ses objets en memoire et ecrit des ancres calculees sur
    l'ancien texte : des ancres fausses, sans que rien ne le signale ;
  - le job relit les elements et se heurte a la garde de
    services/ancrage.py (une portion qui sort du texte) : il tombe en
    ValueError, et TOUTE l'analyse est perdue, y compris les chunks deja
    traites et payes.

On bloque donc l'edition tant qu'un job tourne. C'est la decision la plus
simple et la plus sure : une analyse dure quelques minutes, une edition
peut attendre.
/ Editing during an analysis either writes wrong anchors or kills the job.
We block the edit; an analysis lasts minutes, an edit can wait.
"""

import datetime
import logging

from django.db.models import Q
from django.utils import timezone

from core.models import TranscriptionJob, TranscriptionJobStatus

from ..models import ExtractionJob, ExtractionJobStatus

logger = logging.getLogger(__name__)

# Les statuts qui veulent dire « ce job n'a pas fini ».
# / The statuses meaning "this job is not done".
STATUTS_EN_COURS = (
    ExtractionJobStatus.PENDING,
    ExtractionJobStatus.PROCESSING,
)
STATUTS_DE_TRANSCRIPTION_EN_COURS = (
    TranscriptionJobStatus.PENDING,
    TranscriptionJobStatus.PROCESSING,
)

# Passe ce delai sans le moindre signe de vie, un job « en cours » est
# considere comme mort.
#
# POURQUOI CE DELAI EXISTE, ET POURQUOI IL EST INDISPENSABLE
#
# Un job dont le worker Celery a ete interrompu reste en base au statut
# pending ou processing, pour toujours : personne ne le repassera jamais
# en error. Sans delai de grace, un seul worker tue bloquerait l'edition
# de sa page DEFINITIVEMENT, sans que rien n'explique pourquoi.
#
# Ce n'est pas une hypothese : le CHANGELOG du 19 juin 2026 documente
# exactement ce cas, avec des jobs orphelins restes bloques et un
# nettoyage manuel a faire en shell.
#
# POURQUOI 90 MINUTES, ET PAS 30
#
# CELERY_TASK_TIME_LIMIT vaut 30 minutes (hypostasia/settings.py). Mais un
# job passe d'abord du temps EN FILE avant de commencer : avec un seul
# worker et une analyse deja en cours, l'attente s'ajoute a l'execution.
# Un delai egal au time-limit declarerait donc mort un job qui n'a pas
# encore commence, ou qui tourne encore.
#
# 90 minutes laissent la place a une attente en file plus une analyse
# complete. Au-dela, mieux vaut risquer une edition concurrente rare que
# bloquer une page pour toujours.
# / 30 min is the Celery time limit, but a job also WAITS in queue first.
DELAI_AVANT_DE_CONSIDERER_UN_JOB_MORT = datetime.timedelta(minutes=90)


class EditionBloqueePendantAnalyse(Exception):
    """
    Levee quand on tente d'editer une page dont l'analyse tourne encore.
    / Raised when editing a page whose analysis is still running.

    LOCALISATION : hypostasis_extractor/services/garde_edition.py

    Les vues (phase H) doivent l'attraper et afficher un message clair a
    l'utilisateur : « une analyse est en cours sur cette page, reessayez
    dans un instant ». Ce n'est pas une erreur technique, c'est une
    situation normale et passagere.
    / Views must catch it and show a clear, reassuring message.
    """

    def __init__(self, page, jobs_en_cours):
        self.page = page
        self.jobs_en_cours = jobs_en_cours
        super().__init__(
            f"Une analyse est en cours sur la page {page.pk} "
            f"({len(jobs_en_cours)} job(s)). L'edition est bloquee le temps "
            f"qu'elle se termine, pour ne pas ancrer les extractions sur un "
            f"texte qui aurait change entre-temps."
        )


def verifier_qu_aucune_analyse_ne_tourne(page, job_a_ignorer=None):
    """
    Leve si une analyse ou une transcription tourne sur cette page.
    / Raises if an analysis or transcription is running on this page.

    LOCALISATION : hypostasis_extractor/services/garde_edition.py

    Appelee au debut de chaque operation qui touche au texte ou a la
    structure : correction, scission, fusion, masquage, demasquage.

    On regarde les DEUX sortes de jobs :
      - les jobs d'extraction, qui vont ecrire des ancres ;
      - les jobs de transcription, qui vont remplacer le texte de la page
        entiere, donc tous ses elements.

    :param page: la Page concernee
    :param job_a_ignorer: identifiant d'un ExtractionJob a ne pas compter.
        Le pipeline d'ingestion (phase D) cree son job PUIS re-ingere la
        page : sans ce parametre, il se bloquerait lui-meme.
        / The ingestion pipeline creates its job THEN re-ingests.
    :raises EditionBloqueePendantAnalyse: si un job n'a pas fini
    :return: None
    """
    # On ne regarde que les jobs assez recents pour etre encore vivants.
    # Un job plus vieux que le delai a vu son worker mourir : le laisser
    # bloquer l'edition condamnerait la page pour toujours.
    # / Only jobs recent enough to still be alive are considered.
    limite_de_fraicheur = timezone.now() - DELAI_AVANT_DE_CONSIDERER_UN_JOB_MORT

    # ON REGARDE LES DEUX DATES, PAS UNE SEULE.
    #
    # updated_at est le battement de coeur : front/tasks.py le rafraichit a
    # chaque chunk traite. Mais Django n'applique auto_now qu'aux champs
    # listes dans update_fields — si un jour une ecriture oublie de le
    # lister, la date se fige a la creation sans que rien ne le signale, et
    # un job vivant serait declare mort en pleine analyse.
    #
    # created_at, lui, ne ment jamais. En prenant le plus recent des deux,
    # la garde reste correcte meme si le battement de coeur s'arrete : elle
    # se degrade en « 90 minutes depuis la creation », ce qui est sur.
    # / Taking the latest of both dates keeps the guard correct even if the
    # heartbeat ever stops being written.
    conditions_de_fraicheur = (
        Q(updated_at__gte=limite_de_fraicheur)
        | Q(created_at__gte=limite_de_fraicheur)
    )

    jobs_d_extraction_en_cours = list(
        ExtractionJob.objects.filter(
            conditions_de_fraicheur,
            page=page,
            status__in=STATUTS_EN_COURS,
        ).values_list("pk", flat=True)
    )
    jobs_de_transcription_en_cours = list(
        TranscriptionJob.objects.filter(
            conditions_de_fraicheur,
            page=page,
            status__in=STATUTS_DE_TRANSCRIPTION_EN_COURS,
        ).values_list("pk", flat=True)
    )

    # Le job du pipeline qui appelle lui-meme cette garde ne doit pas se
    # bloquer tout seul : la phase D cree son job, PUIS re-ingere.
    # / The pipeline's own job must not block the pipeline.
    if job_a_ignorer is not None:
        jobs_d_extraction_en_cours = [
            identifiant for identifiant in jobs_d_extraction_en_cours
            if identifiant != job_a_ignorer
        ]

    tous_les_jobs_en_cours = (
        jobs_d_extraction_en_cours + jobs_de_transcription_en_cours
    )
    if tous_les_jobs_en_cours:
        logger.info(
            "Edition refusee sur la page %s : %s job(s) en cours.",
            page.pk, len(tous_les_jobs_en_cours),
        )
        raise EditionBloqueePendantAnalyse(page, tous_les_jobs_en_cours)


def une_analyse_tourne_sur_la_page(page, job_a_ignorer=None):
    """
    Dit si une analyse tourne, sans lever.
    / Tells whether an analysis is running, without raising.

    LOCALISATION : hypostasis_extractor/services/garde_edition.py

    Pour l'interface : griser un bouton d'edition est plus agreable que
    laisser l'utilisateur cliquer pour recevoir une erreur.
    / For the UI: greying out a button beats letting the user hit an error.

    :param page: la Page concernee
    :return: True si un job d'extraction ou de transcription n'a pas fini
    """
    try:
        verifier_qu_aucune_analyse_ne_tourne(page, job_a_ignorer=job_a_ignorer)
    except EditionBloqueePendantAnalyse:
        return True
    return False


# =============================================================================
# LE BLOCAGE SUR CITATION (SPEC-synthese § 5, phase E)
# / Edit-blocking on citation (phase E).
# =============================================================================


class EditionBloqueeParUneSynthese(Exception):
    """
    Levee quand on tente de modifier un element dont une portion est
    citee par une synthese FIGEE.
    / Raised when editing an element cited by a frozen synthesis.

    LOCALISATION : hypostasis_extractor/services/garde_edition.py

    POURQUOI SEULEMENT LES SYNTHESES DIRIGEES

    Une synthese dirigee est un ACTE DATE : un collectif l'a adoptee, et
    peut s'y referer six mois plus tard. Si le texte cite bouge apres
    coup, la preuve de l'acte change en silence. C'est le pire cas de
    gouvernance.

    Un wiki, lui, est VIVANT : ses citations bougent deja a chaque tour
    de mise a jour, et s'il perd une source, la passe suivante le
    corrige. Bloquer sur les wikis figerait le corpus sans rien proteger
    — un carnet a cinq wikis gelerait la moitie de ses elements des la
    premiere semaine.
    / Wikis recompute; frozen syntheses cannot.

    Le message NOMME ce qui bloque (§ 5.3) : un refus sans motif est un
    bug d'interface. / The message names the blocker.
    """

    def __init__(self, element, citations):
        self.element = element
        self.citations = citations
        premiere_citation = citations[0] if citations else None
        nom_de_la_synthese = ""
        if premiere_citation is not None:
            article = premiere_citation.page_cible
            nom_de_la_synthese = article.title or f"synthèse {article.pk}"
            date_de_production = None
            enregistrement = getattr(article, "synthese_dirigee", None)
            if enregistrement is not None:
                date_de_production = enregistrement.produite_le
            if date_de_production is not None:
                nom_de_la_synthese += (
                    f" du {date_de_production:%d/%m/%Y}"
                )
        super().__init__(
            f"Ce passage est cité par « {nom_de_la_synthese} », une "
            f"synthèse adoptée qui ne peut plus changer. Pour corriger "
            f"ce passage, retirez d'abord la citation ou produisez une "
            f"nouvelle synthèse. / This passage is cited by a frozen "
            f"synthesis; remove the citation or produce a new synthesis "
            f"first."
        )


def verifier_qu_aucune_synthese_ne_cite(element):
    """
    Leve si une synthese DIRIGEE cite une extraction dont une portion
    vit sur cet element. / Raises if a FROZEN synthesis cites an
    extraction anchored on this element.

    LOCALISATION : hypostasis_extractor/services/garde_edition.py

    Meme patron que verifier_qu_aucune_analyse_ne_tourne(), appele aux
    memes endroits : reconciliation, moteur_structure (scission et
    fusion), masquage, reingestion.

    ATTENTION AU M2M : une extraction peut porter des portions sur
    PLUSIEURS elements. Citer cette extraction gele donc TOUS ses
    elements, pas seulement celui qui porte le passage cite. C'est
    inevitable — une preuve coupee en deux n'est plus une preuve.
    / One citation freezes every element the extraction spans.

    Seuls les liens type_lien=CITE comptent : les liens de provenance du
    versionnage historique ne gelent rien.
    / Only CITE links freeze anything.

    :raises EditionBloqueeParUneSynthese: si une dirigee cite
    """
    from core.models import SourceLink, TypeDeNote, TypeLien

    citations = list(
        SourceLink.objects.filter(
            extraction_source__ancrages__element=element,
            type_lien=TypeLien.CITE,
            page_cible__type_de_note=TypeDeNote.SYNTHESE,
        ).select_related(
            "page_cible__synthese_dirigee",
        ).distinct()[:5]
    )
    if citations:
        logger.info(
            "Edition refusee sur l'element %s : cite par %s synthese(s) "
            "dirigee(s).", element.pk, len(citations),
        )
        raise EditionBloqueeParUneSynthese(element, citations)


def verifier_qu_aucune_synthese_ne_cite_la_page(page):
    """
    La meme garde, au niveau de la PAGE entiere — pour la reingestion,
    qui remplace tous les elements d'un coup.
    / The same guard at page level — for re-ingestion, which replaces
    every element at once.

    LOCALISATION : hypostasis_extractor/services/garde_edition.py

    :raises EditionBloqueeParUneSynthese: si une dirigee cite
    """
    from core.models import SourceLink, TypeDeNote, TypeLien

    citations = list(
        SourceLink.objects.filter(
            extraction_source__ancrages__element__page=page,
            type_lien=TypeLien.CITE,
            page_cible__type_de_note=TypeDeNote.SYNTHESE,
        ).select_related(
            "page_cible__synthese_dirigee",
        ).distinct()[:5]
    )
    if citations:
        logger.info(
            "Reingestion refusee sur la page %s : cite(e) par %s "
            "synthese(s) dirigee(s).", page.pk, len(citations),
        )
        raise EditionBloqueeParUneSynthese(None, citations)
