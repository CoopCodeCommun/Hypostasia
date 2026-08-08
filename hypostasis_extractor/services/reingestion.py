"""
Re-analyser un document qui a grossi, sans tout refaire.
/ Re-analyse a document that grew, without redoing everything.

LOCALISATION : hypostasis_extractor/services/reingestion.py

Implemente la section 5.3 de SPEC-ancrage-par-element-v2.md (phase G).

LE CAS REEL : LE GROS PAD COLLABORATIF

Un pad contient 200 comptes-rendus de reunion. Chaque semaine, un nouveau
compte-rendu est ajoute en haut, et parfois une coquille est corrigee plus
bas. Il faut pouvoir re-analyser sans repayer 200 appels au LLM, et surtout
sans perdre les debats attaches aux 199 comptes-rendus inchanges.

POURQUOI L'EMPREINTE, ET PAS LA POSITION

Mesure citee par la spec, sur un pad de test (3 comptes-rendus, puis
3 + 1 nouveau + 1 correction) :

  - identification par INDEX : les 8 premiers elements changent tous de
    sens, tout est a re-analyser.
  - identification par EMPREINTE : les elements identiques sont reconnus,
    leurs ancres et leurs commentaires restent valides, et seuls les
    elements NOUVEAUX partent en analyse. Sur ce pad, 36 % du contenu ;
    sur un pad reel de 200 comptes-rendus dont un seul est ajoute par
    semaine, de l'ordre de 2 %.
/ Fingerprints recognize unchanged content; positions do not.

CE QUE CE FICHIER NE FAIT PAS

Il ne convertit pas le document source. La spec appelle ici
convertir_avec_docling() puis extraire_les_elements() : ces deux fonctions
appartiennent au pipeline d'ingestion (phase D), qui n'est pas ecrit.
Ce fichier prend donc les elements bruts DEJA extraits, et se charge de la
seule question qui lui revient : lesquels sont nouveaux, lesquels sont
inchanges, lesquels ont disparu.
/ Conversion belongs to phase D; this file only reconciles.
"""

import logging

from django.db import transaction

from core.models import ElementDocument, empreinte_du_texte

from ..signals import recalculer_etat_de_l_element
from .garde_edition import verifier_qu_aucune_analyse_ne_tourne
from .masquage import masquer_un_element

logger = logging.getLogger(__name__)


def reconcilier_les_elements_par_empreinte(page, nouveaux_elements_bruts,
                                           utilisateur=None):
    """
    Compare le contenu d'une page a une nouvelle version, par empreinte.
    / Compares a page's content to a new version, by fingerprint.

    LOCALISATION : hypostasis_extractor/services/reingestion.py

    :param page: la Page a reconcilier
    :param utilisateur: qui declenche la re-ingestion (pour le journal)
    :param nouveaux_elements_bruts: liste de dicts, dans l'ordre du
        nouveau document. Chaque dict porte au minimum "texte" et "label",
        et facultativement "provenance", "chemin_de_section",
        "reference_docling".
    :return: {
        "inchanges": [ElementDocument...],   gardent leurs ancres
        "disparus": [ElementDocument...],    masques, portions detachees
        "apparus": [ElementDocument...],     crees, a envoyer en analyse
        "deja_masques_reapparus": [ElementDocument...],  voir plus bas
        "empreintes_en_double": [str...],    voir plus bas
      }

    LES ELEMENTS INCHANGES NE SONT PAS TOUCHES

    Ils gardent leur identifiant_stable, donc leurs ancres, leurs
    commentaires et leur etat. Seul leur ordre est mis a jour, puisque le
    document a pu grossir au-dessus d'eux.
    / They keep their identifiant_stable, so anchors and comments survive.

    DEUX LIMITES DE LA SPEC, TRAITEES ICI

    1. CONTENU DUPLIQUE. La spec construit un dictionnaire empreinte ->
       element. Si deux elements ont le meme texte — un intitule de
       section repete chaque semaine, « Ordre du jour » par exemple — le
       second ecrase le premier en silence, et l'un des deux est declare
       disparu a tort. On apparie donc par FILE : les elements de meme
       empreinte sont apparies dans l'ordre, un pour un, et les empreintes
       concernees sont signalees dans le resultat.

    2. ELEMENTS DEJA MASQUES. La spec les exclut de la comparaison. Un
       element masque dont le texte reapparait serait alors recree en
       doublon a chaque re-ingestion : le nouveau serait masque a son
       tour, puis exclu lui aussi, puis recree... Un pad re-ingere
       cinquante fois accumulerait cinquante copies du meme bruit.

       On les apparie donc comme les autres. Un element masque reconnu
       reste masque et garde son identite. Il est signale dans
       "deja_masques_reapparus" parce que c'est une information utile —
       le bruit est toujours dans la source — mais rien n'est recree.
    / Hidden elements are paired too, otherwise each re-ingestion would
    add another copy of the same noise.
    """
    resultat = {
        "inchanges": [],
        "disparus": [],
        "apparus": [],
        "deja_masques_reapparus": [],
        "empreintes_en_double": [],
    }

    # Une re-ingestion refait toute la structure de la page : la lancer
    # pendant une analyse ferait travailler le job sur des elements qui
    # n'existent plus. On verifie UNE fois pour toute la page.
    # / Checked once for the whole page, not once per hidden element.
    verifier_qu_aucune_analyse_ne_tourne(page)

    with transaction.atomic():
        # Tous les elements de la page, masques compris (voir la limite 2
        # ci-dessus). / Every element of the page, hidden ones included.
        anciens_par_empreinte = _grouper_par_empreinte(
            list(
                ElementDocument.objects
                .select_for_update()
                .filter(page=page)
                .order_by("ordre")
            )
        )

        # On signale les empreintes portees par plusieurs elements DES
        # DEUX COTES. Ne regarder que l'ancien document laisserait passer
        # le cas le plus probable : un intitule repete qui apparait une
        # seconde fois dans le NOUVEAU contenu. L'appariement se fait
        # alors dans l'ordre, et peut associer l'element debattu a la
        # mauvaise occurrence — sans que rien ne le signale.
        # / Duplicates must be surfaced on BOTH sides, not just the old one.
        empreintes_en_double = set()
        for empreinte, elements in anciens_par_empreinte.items():
            if len(elements) > 1:
                empreintes_en_double.add(empreinte)

        comptage_des_nouvelles_empreintes = {}
        for element_brut in nouveaux_elements_bruts:
            empreinte = empreinte_du_texte(element_brut["texte"])
            comptage_des_nouvelles_empreintes[empreinte] = (
                comptage_des_nouvelles_empreintes.get(empreinte, 0) + 1
            )
        for empreinte, nombre in comptage_des_nouvelles_empreintes.items():
            if nombre > 1:
                empreintes_en_double.add(empreinte)

        resultat["empreintes_en_double"] = sorted(empreintes_en_double)

        # LES ORDRES SONT ATTRIBUES EN DEUX TEMPS.
        #
        # Pendant le traitement, on place les elements du nouveau document
        # dans une plage haute, loin des ordres actuels. Sinon un element
        # masque reste a l'ordre 0 et un nouvel element cree a l'ordre 0
        # entrent en collision — et ce conflit-la n'est pas transitoire :
        # il subsiste a la fin de la transaction, donc meme une contrainte
        # differee le refuse, a juste titre.
        #
        # La numerotation definitive est faite en fin de fonction : les
        # elements du contenu utile d'abord, dans l'ordre du document,
        # puis les masques a la suite.
        # / Two-step numbering: a high range during the pass, final
        # renumbering at the end. A hidden element at order 0 would
        # otherwise permanently collide with a newly created one.
        PLAGE_TEMPORAIRE = 1_000_000

        # On parcourt le nouveau document dans l'ordre. Chaque element
        # brut cherche un ancien de meme empreinte, et le consomme.
        # / Walk the new document in order; each raw element consumes an old one.
        elements_anciens_reutilises = set()
        elements_du_nouveau_document = []
        for position, element_brut in enumerate(nouveaux_elements_bruts):
            empreinte = empreinte_du_texte(element_brut["texte"])
            candidats = anciens_par_empreinte.get(empreinte, [])

            ancien_element_correspondant = None
            for candidat in candidats:
                if candidat.pk not in elements_anciens_reutilises:
                    ancien_element_correspondant = candidat
                    break

            if ancien_element_correspondant is not None:
                # Reconnu : on ne touche qu'a l'ordre. L'element garde son
                # identifiant_stable, donc ses ancres et ses commentaires.
                # S'il etait masque, il le reste : la decision humaine de
                # le retirer n'est pas annulee par une re-ingestion.
                # / Recognized: keeps its identity, and stays hidden if it was.
                elements_anciens_reutilises.add(ancien_element_correspondant.pk)
                ancien_element_correspondant.ordre = PLAGE_TEMPORAIRE + position
                ancien_element_correspondant.save(update_fields=["ordre"])
                elements_du_nouveau_document.append(ancien_element_correspondant)

                if ancien_element_correspondant.masque:
                    resultat["deja_masques_reapparus"].append(
                        ancien_element_correspondant,
                    )
                else:
                    resultat["inchanges"].append(ancien_element_correspondant)
                continue

            # Apparu : aucun ancien element ne porte ce texte.
            # / Appeared: no old element carries this text.
            element_cree = ElementDocument.objects.create(
                page=page,
                ordre=PLAGE_TEMPORAIRE + position,
                label=element_brut.get("label", "text"),
                texte=element_brut["texte"],
                empreinte_contenu=empreinte,
                provenance=element_brut.get("provenance") or {},
                chemin_de_section=element_brut.get("chemin_de_section") or [],
                reference_docling=element_brut.get("reference_docling", ""),
            )
            resultat["apparus"].append(element_cree)
            elements_du_nouveau_document.append(element_cree)

        # Ce qui n'a ete reutilise par personne a disparu du document.
        #
        # On passe par masquer_un_element, et non par un masquage ecrit a
        # la main ici, pour deux raisons :
        #  - l'operation est journalisee, donc « rien ne disparait en
        #    silence » vaut aussi pour la re-ingestion, qui est pourtant
        #    le masquage le plus massif ;
        #  - le journal note l'empreinte et les portions detachees, ce qui
        #    rend le demasquage recuperable. Sans ca, un element masque
        #    par re-ingestion ne pourrait JAMAIS retrouver ses ancres,
        #    meme si son texte n'a pas bouge d'un caractere.
        # / Going through masquer_un_element makes the hide traceable and
        # recoverable, which a hand-written hide here would not be.
        for elements in anciens_par_empreinte.values():
            for ancien_element in elements:
                if ancien_element.pk in elements_anciens_reutilises:
                    continue
                if ancien_element.masque:
                    # Deja masque et toujours absent : rien de nouveau.
                    # / Already hidden and still absent: nothing new.
                    continue
                masquer_un_element(
                    ancien_element,
                    justification=(
                        "Element absent du contenu source lors d'une "
                        "re-ingestion."
                    ),
                    utilisateur=utilisateur,
                    verifier_les_jobs=False,
                )
                resultat["disparus"].append(ancien_element)

        # Numerotation definitive : le contenu utile d'abord, dans l'ordre
        # du nouveau document, puis les elements masques a la suite. Un
        # element masque n'a plus de place naturelle dans le document —
        # il a disparu de la source — mais il doit garder un ordre unique.
        # / Final numbering: useful content first, hidden elements after.
        _renumeroter_apres_reingestion(page, elements_du_nouveau_document)

    logger.info(
        "Re-ingestion de la page %s : %s inchange(s), %s apparu(s), "
        "%s disparu(s), %s deja masque(s) reapparu(s), %s empreinte(s) "
        "en double.",
        page.pk, len(resultat["inchanges"]), len(resultat["apparus"]),
        len(resultat["disparus"]), len(resultat["deja_masques_reapparus"]),
        len(resultat["empreintes_en_double"]),
    )
    if resultat["empreintes_en_double"]:
        logger.warning(
            "Page %s : %s empreinte(s) portee(s) par plusieurs elements. "
            "L'appariement s'est fait dans l'ordre du document, ce qui peut "
            "se tromper si ces elements ont ete deplaces l'un par rapport a "
            "l'autre.",
            page.pk, len(resultat["empreintes_en_double"]),
        )
    return resultat


def _renumeroter_apres_reingestion(page, elements_du_nouveau_document):
    """
    Donne les ordres definitifs apres une re-ingestion.
    / Assigns the final ordering after a re-ingestion.

    LOCALISATION : hypostasis_extractor/services/reingestion.py

    Deux groupes, dans cet ordre :
      1. les elements du nouveau document, dans l'ordre du document ;
      2. les elements masques, a la suite, dans leur ordre precedent.

    Un element masque garde une place — il reste affiche, barre et grise —
    mais il ne peut pas s'intercaler dans le nouveau document : il a
    disparu de la source, il n'y a plus de position qui lui revienne.
    / A hidden element keeps a place but no longer claims a position
    inside the new document.

    :param page: la Page concernee
    :param elements_du_nouveau_document: les elements du contenu utile,
        dans l'ordre du nouveau document
    """
    identifiants_du_nouveau_document = {
        element.pk for element in elements_du_nouveau_document
    }
    elements_masques = list(
        ElementDocument.objects
        .filter(page=page)
        .exclude(pk__in=identifiants_du_nouveau_document)
        .order_by("ordre", "pk")
    )

    ordre_courant = 0
    for element in elements_du_nouveau_document:
        if element.ordre != ordre_courant:
            element.ordre = ordre_courant
            element.save(update_fields=["ordre"])
        ordre_courant += 1

    for element in elements_masques:
        if element.ordre != ordre_courant:
            element.ordre = ordre_courant
            element.save(update_fields=["ordre"])
        ordre_courant += 1


def _grouper_par_empreinte(elements):
    """
    Range des elements par empreinte, en gardant les doublons.
    / Groups elements by fingerprint, keeping duplicates.

    LOCALISATION : hypostasis_extractor/services/reingestion.py

    Un simple dictionnaire empreinte -> element perdrait les doublons :
    le dernier ecraserait les precedents. On garde donc une LISTE par
    empreinte, dans l'ordre du document.
    / A plain dict would silently drop duplicates; we keep a list.

    :param elements: les ElementDocument, dans l'ordre du document
    :return: {empreinte: [ElementDocument, ...]}
    """
    elements_par_empreinte = {}
    for element in elements:
        elements_par_empreinte.setdefault(
            element.empreinte_contenu, [],
        ).append(element)
    return elements_par_empreinte
