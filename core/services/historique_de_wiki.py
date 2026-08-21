"""
L'ecriture de l'histoire d'un wiki (SPEC-synthese, addendum du
21 aout 2026).
/ Writing a wiki's history.

LOCALISATION : core/services/historique_de_wiki.py

A QUOI CA SERT. Un tour de mise a jour produisait toute la matiere de
sa propre tracabilite — les operations appliquees AVEC l'ancien
contenu, les rejets AVEC leur motif, le compte des nouveautes — puis
la jetait. Il ne restait qu'un compteur, `Wiki.tours_de_mise_a_jour`,
et une date ECRASEE a chaque tour. Sur un wiki suivi depuis six
semaines, personne ne pouvait dire quand un paragraphe etait entre, ni
pourquoi, ni ce qu'il avait remplace.

CE MODULE NE CONNAIT PAS `front`. Il ecrit ce qu'on lui remet : le
bilan rendu par `appliquer_les_operations` (fonction pure), le texte
d'avant, et la borne basse du comptage. C'est l'appelant — la vue ou
la passe de nuit — qui connait le MOTIF, et lui seul.
/ This module never imports `front`: it writes the report it is given.

LES SOURCES VIENNENT DES MARQUEURS, jamais d'un champ parallele
(§ 4.4) : le markdown est la verite, et `MOTIF_DE_MARQUEUR` en est le
seul lecteur.
/ Sources are derived from the [[ext:N]] markers, never a side field.
"""

from core.models import OperationDeWiki, TourDeWiki
from core.services.nouveautes_du_perimetre import nouveautes_du_perimetre
from core.services.synthese import MOTIF_DE_MARQUEUR


# La taille de `OperationDeWiki.section`, elle-meme calee sur
# `SourceLink.section` : la forme sous laquelle l'applieur compare les
# titres (§ 6, relecture F, I3). Un titre halluciné plus long ne doit
# pas faire tomber l'ecriture de l'historique — on tronque.
# / Titles are truncated, never allowed to break the history write.
TAILLE_D_UN_TITRE = 200


def identifiants_cites_par(contenu):
    """
    Les identifiants d'extraction cites par un contenu.
    / The extraction ids a content cites.

    LOCALISATION : core/services/historique_de_wiki.py

    :param contenu: le markdown d'une operation / an operation's markdown
    :return: un ensemble d'entiers / a set of ints
    """
    return {
        int(correspondance.group(1))
        for correspondance in MOTIF_DE_MARQUEUR.finditer(contenu or "")
    }


def _ecrire_une_operation(tour, ligne_du_bilan, appliquee,
                          identifiants_du_perimetre):
    """
    Ecrit UNE ligne du bilan, appliquee ou rejetee.
    / Writes ONE report line, applied or rejected.

    LOCALISATION : core/services/historique_de_wiki.py

    Le contenu d'une operation REJETEE est conserve (§ 6.2) : le jeter
    serait une perte de donnees, et un titre introuvable est une
    hallucination du modele qu'il faut pouvoir relire.
    / Rejected content is kept: throwing it away would lose data.
    """
    from hypostasis_extractor.models import ExtractedEntity

    operation = ligne_du_bilan.get("operation") or {}
    type_d_operation = str(operation.get("type") or "")[:20]

    # Pour une INSERTION, la section concernee est celle que
    # l'operation CREE (`titre`) ; `apres` porte l'ancre. Pour les
    # autres, c'est la section visee (`section`).
    # / For an insertion, the section is the one being created.
    if type_d_operation == "insert_section":
        titre_de_la_section = str(operation.get("titre") or "")
    else:
        titre_de_la_section = str(operation.get("section") or "")

    operation_ecrite = OperationDeWiki.objects.create(
        tour=tour,
        indice=ligne_du_bilan.get("indice", 0),
        type_d_operation=type_d_operation,
        section=titre_de_la_section[:TAILLE_D_UN_TITRE],
        apres=str(operation.get("apres") or "")[:TAILLE_D_UN_TITRE],
        contenu=str(operation.get("contenu") or ""),
        ancien_contenu=ligne_du_bilan.get("ancien_contenu") or "",
        appliquee=appliquee,
        motif_de_rejet=str(ligne_du_bilan.get("motif") or "")[:300],
    )

    identifiants_cites = identifiants_cites_par(operation.get("contenu"))
    if identifiants_du_perimetre is not None:
        # On n'attache que des extractions du perimetre : une operation
        # rejetee peut citer n'importe quoi, y compris un identifiant
        # invente. / Only in-scope extractions are attached.
        identifiants_cites &= set(identifiants_du_perimetre)
    if identifiants_cites:
        operation_ecrite.extractions_citees.set(
            ExtractedEntity.objects.filter(pk__in=identifiants_cites)
        )
    return operation_ecrite


def enregistrer_un_tour(wiki, motif, fait_par, bilan, texte_avant,
                        depuis=None, job=None,
                        identifiants_du_perimetre=None):
    """
    Ecrit un tour de wiki et ses operations.
    / Writes a wiki round and its operations.

    LOCALISATION : core/services/historique_de_wiki.py

    FLUX :
    1. compte les nouveautes du perimetre depuis `depuis` — c'est la
       RAISON du tour, et elle n'est plus reproductible apres ;
    2. cree le `TourDeWiki` avec le texte d'avant et celui d'apres ;
    3. cree une `OperationDeWiki` par ligne du bilan, appliquee ou
       rejetee, avec ses extractions citees.

    :param wiki: le `Wiki` concerne / the wiki
    :param motif: une valeur de `MotifDeTourDeWiki`
    :param fait_par: l'humain qui a accepte, ou None pour le moteur
    :param bilan: le dict rendu par `appliquer_les_operations`
    :param texte_avant: le markdown de l'article avant le tour
    :param depuis: la borne basse du comptage des nouveautes. None =
        aucune nouveaute comptee (jamais un compte invente).
    :param job: l'`ExtractionJob` de la proposition, s'il y en a une
    :param identifiants_du_perimetre: les ids proposes au modele ;
        None = on n'attache aucune extraction (chemin sans perimetre,
        comme une reparation de titres).
    :return: le `TourDeWiki` cree / the created round
    """
    from core.services.synthese import notes_du_perimetre_d_un_wiki

    notes = notes_du_perimetre_d_un_wiki(wiki)
    comptes = nouveautes_du_perimetre(notes, depuis)

    tour = TourDeWiki.objects.create(
        wiki=wiki,
        numero_de_tour=wiki.tours_de_mise_a_jour,
        fait_par=fait_par,
        motif=motif,
        depuis=depuis,
        extractions_nouvelles=comptes["extractions"],
        commentaires_nouveaux=comptes["commentaires"],
        job=job,
        texte_avant=texte_avant or "",
        texte_apres=bilan.get("texte_final") or "",
    )

    if depuis is not None:
        # CE QUI a declenche, pas seulement COMBIEN : un compte ne dit
        # pas quelle note lire. / Which notes, not just how many.
        from hypostasis_extractor.models import CommentaireExtraction

        tour.notes_declenchantes.set(
            notes.filter(created_at__gt=depuis)
        )
        tour.commentaires_declenchants.set(
            CommentaireExtraction.objects.filter(
                entity__job__page__in=notes,
                entity__masquee=False,
                created_at__gt=depuis,
            )
        )

    for ligne in bilan.get("operations_appliquees", []):
        _ecrire_une_operation(
            tour, ligne, True, identifiants_du_perimetre,
        )
    for ligne in bilan.get("operations_rejetees", []):
        _ecrire_une_operation(
            tour, ligne, False, identifiants_du_perimetre,
        )

    return tour
