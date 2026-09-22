"""
Ecrire la provenance d'une production, en un seul endroit.
/ Writing a production's provenance, in one place.

LOCALISATION : hypostasis_extractor/services/provenance.py

POURQUOI UN SERVICE, ET PAS UN APPEL ENVELOPPE AUTOUR DE `appeler_llm`.
Un enrobage automatique attraperait tout le monde sans qu'on ait a y
penser — et c'est precisement ce qui le disqualifie : il ne saurait dire
NI quel geste appelle, NI quel analyseur a servi, NI quelles extractions
ont ete montrees. Il ecrirait une provenance vide et bruyante, qui
donnerait l'illusion d'une trace.
/ An automatic wrapper around the LLM call would catch every path
without knowing the gesture, the analyzer, or the shown extractions.

L'appel est donc EXPLICITE dans chaque producteur, et un test par chemin
epingle qu'il y est.
/ Explicit in each producer, with one test per path.
"""

import hashlib
import logging

logger = logging.getLogger(__name__)


def empreinte_d_un_prompt(prompt):
    """
    Le SHA-256 hexadecimal d'un prompt assemble.
    / The hex SHA-256 of an assembled prompt.

    LOCALISATION : hypostasis_extractor/services/provenance.py

    UTF-8 EXPLICITE : l'encodage fait partie de l'empreinte. Les prompts
    du projet portent des accents, des guillemets francais et des puces —
    deux encodages donneraient deux empreintes pour un meme texte.
    / Explicit UTF-8: the encoding is part of the fingerprint.

    :param prompt: le texte assemble / the assembled text
    :return: 64 caracteres hexadecimaux / 64 hex characters
    """
    return hashlib.sha256((prompt or "").encode("utf-8")).hexdigest()


def derniere_version_de(analyseur):
    """
    La derniere version enregistree d'un analyseur, ou None.
    / An analyzer's latest recorded version, or None.

    LOCALISATION : hypostasis_extractor/services/provenance.py

    :param analyseur: l'`AnalyseurSyntaxique` / the analyzer
    :return: une `AnalyseurVersion` ou None
    """
    if analyseur is None:
        return None
    return analyseur.versions.order_by("-version_number").first()


def analyseur_de_redaction():
    """
    L'analyseur dont le preambule sert aux articles, et sa derniere
    version. / The analyzer whose preamble serves articles.

    LOCALISATION : hypostasis_extractor/services/provenance.py

    LE RESOLVEUR UNIQUE DU DEFAUT, sur le modele de `modele_du_role()` :
    actif, du type `rediger_un_article`, trie `-est_par_defaut, name`.
    Tout chemin qui a besoin du defaut passe par lui — deux regles de
    choix designeraient un jour deux analyseurs differents, et la
    provenance nommerait celui qui n'a pas servi.
    / The single resolver of the default, so the trace can never name an
    analyzer that did not serve.

    L'ORDRE DE RESOLUTION, DU PLUS PRECIS AU PLUS GENERAL :
    1. ce que le GESTE a fige — l'analyseur pose sur le job
       (`front.tasks._analyseur_fige_sur_le_job`) ou porte par le wiki
       (`Wiki.analyseur_de_redaction`) ;
    2. a defaut, ce resolveur : le defaut du type ;
    3. a defaut encore, le repli en dur, JOURNALISE chez
       `_prompt_systeme_de_synthese`.
    Le carnet, lui, ne porte pas d'analyseur : aucune cle etrangere
    `Dossier -> AnalyseurSyntaxique` n'existe.
    / Resolution order: what the gesture froze (job or wiki), then this
    type default, then a logged hard fallback.

    :return: `(analyseur, version)` — l'un et l'autre peuvent etre None
    """
    from ..models import AnalyseurSyntaxique

    analyseur = AnalyseurSyntaxique.objects.filter(
        is_active=True,
        type_analyseur=AnalyseurSyntaxique.TypeAnalyseur.REDIGER_UN_ARTICLE,
    ).order_by("-est_par_defaut", "name").first()
    if analyseur is None:
        return None, None
    return analyseur, derniere_version_de(analyseur)


def enregistrer_la_provenance(chemin, prompt, modele=None, job=None,
                              tour_de_wiki=None, analyseur=None,
                              analyseur_version=None,
                              extractions_montrees=None):
    """
    Ecrit la provenance d'une production.
    / Records a production's provenance.

    LOCALISATION : hypostasis_extractor/services/provenance.py

    ELLE NE LEVE JAMAIS. Une trace qui empeche la production qu'elle
    trace serait une regression pure : l'article compte plus que son
    journal. L'echec part au journal du worker, ou il se lit.
    / It never raises: the article matters more than its record.

    :param chemin: une valeur de `CheminDeProduction` / the gesture
    :param prompt: le texte EXACT envoye au modele / the exact text sent
    :param modele: l'`AIModel` destinataire / the receiving model
    :param job: l'`ExtractionJob` de la demande, s'il y en a un
    :param tour_de_wiki: le `TourDeWiki` ecrit, s'il existe deja
    :param analyseur: l'analyseur dont le preambule a servi
    :param analyseur_version: sa version au moment de l'envoi
    :param extractions_montrees: les identifiants montres au modele —
        un `set` est accepte, il est trie ici
    :return: la `ProvenanceDeProduction` ecrite, ou None si l'ecriture
        a echoue / the record, or None on failure
    """
    from ..models import ProvenanceDeProduction

    try:
        return ProvenanceDeProduction.objects.create(
            job=job,
            tour_de_wiki=tour_de_wiki,
            chemin=chemin,
            analyseur=analyseur,
            analyseur_version=analyseur_version,
            modele=modele,
            empreinte=empreinte_d_un_prompt(prompt),
            longueur=len(prompt or ""),
            extractions_montrees=sorted(extractions_montrees or []),
        )
    except Exception as erreur:
        logger.exception(
            "enregistrer_la_provenance: chemin=%s job=%s — la trace n'a "
            "pas pu être écrite (%s). La production, elle, continue.",
            chemin, getattr(job, "pk", None), erreur,
        )
        return None
