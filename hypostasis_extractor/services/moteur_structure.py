"""
Scinder, fusionner : faire evoluer la structure sans perdre les ancres.
/ Split, merge: evolve the structure without losing the anchors.

LOCALISATION : hypostasis_extractor/services/moteur_structure.py

Implemente les sections 5.1 et 5.2 de SPEC-ancrage-par-element-v2.md (phase F).

LE PRINCIPE COMMUN AUX DEUX OPERATIONS

Le contenu total ne change jamais. Seule change la facon dont il est
decoupe en elements. Rien n'est ajoute, rien n'est retire — donc chaque
portion d'ancrage qui existait avant existe encore apres, eventuellement
coupee en deux.
/ Total content never changes, only how it is cut into elements.

POURQUOI CES OPERATIONS EXISTENT

Une transcription audio se trompe. Elle colle deux tours de parole en un
seul element, ou attribue le mauvais locuteur au milieu d'un segment. Sans
scission ni fusion, la seule facon de corriger serait de tout re-analyser
et de perdre le debat attache. « Recoller un tour de parole scinde » est
l'operation numero un sur une vraie diarisation.
/ Real diarisation constantly needs splitting and merging turns of speech.

POURQUOI LES CONTRAINTES SONT DEFERRABLE

Ces deux operations passent forcement par des etats temporairement
incoherents : le premier morceau d'une scission reclame l'ordre de
l'element d'origine, qui existe encore. Les contraintes d'unicite sur
(page, ordre) et (extraction, ordre_dans_extraction) sont donc verifiees
au COMMIT, pas ligne a ligne. Sans ca, le pseudo-code de la spec leve une
IntegrityError des la premiere ligne.
/ Both operations pass through temporarily inconsistent states.
"""

import logging

from django.db import transaction
from django.db.models import F

from core.models import (
    ElementDocument,
    ElementOperation,
    TypeOperationElement,
    empreinte_du_texte,
)

from ..models import AncrageExtraction, EtatAncrage
from ..signals import recalculer_etat_de_l_element
from .ancrage import SEPARATEUR_DE_JONCTION
from .garde_edition import (
    verifier_qu_aucune_analyse_ne_tourne,
    verifier_qu_aucune_synthese_ne_cite,
)

logger = logging.getLogger(__name__)


def scinder_un_element(element, position_de_coupe, utilisateur=None,
                       justification=""):
    """
    Coupe un element en deux, et redistribue les portions d'ancrage.
    / Splits an element in two, redistributing the anchor portions.

    LOCALISATION : hypostasis_extractor/services/moteur_structure.py

    :param element: l'ElementDocument a couper
    :param position_de_coupe: l'indice du caractere ou couper. Le premier
        morceau prend [0:position], le second [position:].
    :param utilisateur: qui fait l'operation (pour le journal)
    :param justification: pourquoi (pour le journal)
    :return: (premier_morceau, second_morceau)

    LES TROIS CAS POUR CHAQUE PORTION QUI TRAVERSAIT L'ELEMENT

    1. La portion finit AVANT la coupe : elle part entiere sur le premier
       morceau, ses offsets ne changent pas.
    2. La portion commence APRES la coupe : elle part entiere sur le
       second morceau, ses offsets reculent de la position de coupe.
    3. La portion CHEVAUCHE la coupe : elle devient DEUX portions, une par
       morceau. C'est exactement le mecanisme qui gerait deja une
       extraction enjambant plusieurs elements — la scission manuelle
       n'est qu'un nouveau cas du meme algorithme, pas un cas special.
    """
    verifier_qu_aucune_analyse_ne_tourne(element.page)
    # Scinder un element cite par une synthese FIGEE couperait sa preuve
    # en deux (SPEC-synthese § 5, phase E). / Splitting a frozen-cited
    # element would cut its evidence in half.
    verifier_qu_aucune_synthese_ne_cite(element)
    _verifier_la_position_de_coupe(element, position_de_coupe)

    texte_original = element.texte
    texte_du_premier = texte_original[:position_de_coupe]
    texte_du_second = texte_original[position_de_coupe:]
    identifiant_stable_d_origine = element.identifiant_stable

    with transaction.atomic():
        # On fait de la place : tous les elements APRES celui-ci reculent
        # d'un cran, puisqu'on va passer de un a deux elements.
        # / Make room: every element after this one shifts by one.
        ElementDocument.objects.filter(
            page=element.page, ordre__gt=element.ordre,
        ).update(ordre=F("ordre") + 1)

        premier_morceau = ElementDocument.objects.create(
            page=element.page,
            ordre=element.ordre,
            label=element.label,
            texte=texte_du_premier,
            empreinte_contenu=empreinte_du_texte(texte_du_premier),
            chemin_de_section=element.chemin_de_section,
            # La provenance physique est recopiee telle quelle. Pour un PDF
            # ou un audio, elle designe desormais une zone plus large que
            # le morceau : a affiner a la main si besoin.
            # / Provenance is copied as is; it now covers a wider area.
            provenance=element.provenance,
            reference_docling=element.reference_docling,
            masque=element.masque,
        )
        second_morceau = ElementDocument.objects.create(
            page=element.page,
            ordre=element.ordre + 1,
            label=element.label,
            texte=texte_du_second,
            empreinte_contenu=empreinte_du_texte(texte_du_second),
            chemin_de_section=element.chemin_de_section,
            provenance=element.provenance,
            reference_docling=element.reference_docling,
            masque=element.masque,
        )

        portions_a_redistribuer = list(
            AncrageExtraction.objects
            .select_for_update()
            .filter(element=element)
        )
        extractions_touchees = set()
        for portion in portions_a_redistribuer:
            _redistribuer_une_portion(
                portion, position_de_coupe, premier_morceau, second_morceau,
            )
            extractions_touchees.add(portion.extraction_id)

        # L'element d'origine ne porte plus aucune portion : le PROTECT ne
        # s'y oppose plus. S'il restait une portion, la suppression
        # echouerait — c'est le garde-fou voulu.
        # / PROTECT would refuse if any portion remained: intended guard.
        element_supprime_id = element.pk
        element.delete()

        # Le journal porte de quoi reconstituer l'operation meme quand les
        # elements auront disparu : qui etait coupe, ou, et ce qui en est
        # sorti. / The journal carries enough to reconstruct the operation.
        ElementOperation.objects.create(
            page=premier_morceau.page,
            element=premier_morceau,
            identifiant_stable_element=identifiant_stable_d_origine,
            type_operation=TypeOperationElement.SCISSION,
            user=utilisateur,
            justification=justification,
            donnees={
                "position_de_coupe": position_de_coupe,
                "element_d_origine": str(identifiant_stable_d_origine),
                "morceaux": [
                    str(premier_morceau.identifiant_stable),
                    str(second_morceau.identifiant_stable),
                ],
                "longueur_du_texte_d_origine": len(texte_original),
            },
        )

        recalculer_etat_de_l_element(premier_morceau.pk)
        recalculer_etat_de_l_element(second_morceau.pk)

    logger.info(
        "Element %s scinde en %s et %s a la position %s (%s extraction(s) "
        "touchee(s)).",
        element_supprime_id, premier_morceau.pk, second_morceau.pk,
        position_de_coupe, len(extractions_touchees),
    )
    return premier_morceau, second_morceau


def _verifier_la_position_de_coupe(element, position_de_coupe):
    """
    Refuse une coupe qui ne couperait rien.
    / Rejects a cut that would not cut anything.

    Couper a 0 ou a la fin du texte produirait un morceau vide : deux
    elements dont l'un ne dit rien, et une operation tracee dans le
    journal pour un resultat nul.
    / Cutting at either end would produce an empty element.
    """
    if position_de_coupe <= 0:
        raise ValueError(
            f"Position de coupe {position_de_coupe} : le premier morceau "
            f"serait vide."
        )
    if position_de_coupe >= len(element.texte):
        raise ValueError(
            f"Position de coupe {position_de_coupe} : le second morceau "
            f"serait vide (le texte fait {len(element.texte)} caracteres)."
        )


def _redistribuer_une_portion(portion, position_de_coupe, premier_morceau,
                              second_morceau):
    """
    Applique a une portion l'un des trois cas de la scission.
    / Applies one of the three split cases to a portion.

    LOCALISATION : hypostasis_extractor/services/moteur_structure.py
    """
    # Cas 1 : la portion finit avant la coupe, elle ne bouge pas.
    # / Case 1: the portion ends before the cut, nothing moves.
    if portion.fin_dans_element <= position_de_coupe:
        portion.element = premier_morceau
        portion.save(update_fields=["element"])
        return

    # Cas 2 : la portion commence apres la coupe, ses offsets reculent.
    # / Case 2: the portion starts after the cut, offsets shift back.
    if portion.debut_dans_element >= position_de_coupe:
        portion.element = second_morceau
        portion.debut_dans_element -= position_de_coupe
        portion.fin_dans_element -= position_de_coupe
        portion.save(update_fields=[
            "element", "debut_dans_element", "fin_dans_element",
        ])
        return

    # Cas 3 : la portion chevauche la coupe, elle devient deux portions.
    #
    # On decale d'abord de +1 le numero de toutes les portions suivantes
    # de la MEME extraction, pour liberer le numero de la nouvelle. Ce
    # decalage passe par des numeros temporairement en double : c'est
    # pour cela que la contrainte d'unicite est DEFERRABLE.
    # / Case 3: the portion straddles the cut and becomes two portions.
    AncrageExtraction.objects.filter(
        extraction_id=portion.extraction_id,
        ordre_dans_extraction__gt=portion.ordre_dans_extraction,
    ).update(ordre_dans_extraction=F("ordre_dans_extraction") + 1)

    # Une portion detachee le reste, meme coupee en deux : la scission ne
    # retrouve pas un passage source perdu.
    # / A detached portion stays detached, even when split in two.
    etait_detachee = portion.etat_ancrage == EtatAncrage.DETACHEE
    etat_apres_coupe = (
        EtatAncrage.DETACHEE if etait_detachee else EtatAncrage.ANCREE
    )

    longueur_de_la_seconde_moitie = portion.fin_dans_element - position_de_coupe
    AncrageExtraction.objects.create(
        extraction_id=portion.extraction_id,
        element=second_morceau,
        ordre_dans_extraction=portion.ordre_dans_extraction + 1,
        debut_dans_element=0,
        fin_dans_element=longueur_de_la_seconde_moitie,
        # RETROUVEE et non EXACTE : la position a ete recalculee par une
        # operation de structure, elle n'est plus celle du premier ancrage.
        # / Recomputed by a structural operation, so no longer EXACTE.
        etat_ancrage=etat_apres_coupe,
    )

    portion.element = premier_morceau
    portion.fin_dans_element = position_de_coupe
    portion.etat_ancrage = etat_apres_coupe
    portion.save(update_fields=[
        "element", "fin_dans_element", "etat_ancrage",
    ])


def fusionner_deux_elements(premier, second, utilisateur=None, justification=""):
    """
    Recolle deux elements adjacents en un seul.
    / Merges two adjacent elements into one.

    LOCALISATION : hypostasis_extractor/services/moteur_structure.py

    :param premier: l'element de gauche
    :param second: l'element de droite, qui doit le suivre immediatement
    :param utilisateur: qui fait l'operation (pour le journal)
    :param justification: pourquoi (pour le journal)
    :return: l'element fusionne

    ON NE FUSIONNE QUE DES VOISINS IMMEDIATS

    Fusionner deux elements distants n'aurait pas de sens : que
    deviendrait le texte qui se trouve entre les deux ? La contrainte est
    donc premier.ordre + 1 == second.ordre.
    / Merging distant elements would silently drop what lies between them.

    LES OFFSETS APRES FUSION

    Les portions du premier gardent leurs offsets : leur texte n'a pas
    bouge, il est toujours au debut. Celles du second reculent de la
    longueur du premier, plus celle du separateur qu'on insere entre les
    deux textes.
    / Portions of the second shift by len(first) + len(separator).
    """
    verifier_qu_aucune_analyse_ne_tourne(premier.page)
    # La fusion touche les DEUX elements : chacun doit etre libre de
    # toute citation figee (SPEC-synthese § 5, phase E).
    # / Merging touches BOTH elements: each must be citation-free.
    verifier_qu_aucune_synthese_ne_cite(premier)
    verifier_qu_aucune_synthese_ne_cite(second)

    if premier.page_id != second.page_id:
        raise ValueError(
            "On ne fusionne que deux elements d'une meme page."
        )
    if second.ordre != premier.ordre + 1:
        raise ValueError(
            f"Seuls deux elements adjacents peuvent etre fusionnes : "
            f"le premier est a l'ordre {premier.ordre}, le second a "
            f"{second.ordre} (attendu {premier.ordre + 1})."
        )
    # On ne fusionne pas un element masque avec un element visible.
    #
    # Le resultat ne pourrait etre ni l'un ni l'autre : le laisser visible
    # renverrait au LLM le bruit qu'un humain avait justement retire, sans
    # qu'aucun demasquage soit journalise ; le masquer ferait disparaitre
    # du contenu utile. Il faut demasquer d'abord, en connaissance de
    # cause.
    # / Merging a hidden element with a visible one would either resurface
    # removed noise or hide real content. Unhide first, deliberately.
    if premier.masque != second.masque:
        raise ValueError(
            "On ne fusionne pas un element masque avec un element visible. "
            "Demasquer d'abord celui qui doit revenir dans le contenu utile."
        )

    decalage = len(premier.texte) + len(SEPARATEUR_DE_JONCTION)
    texte_fusionne = premier.texte + SEPARATEUR_DE_JONCTION + second.texte
    identifiant_stable_du_premier = premier.identifiant_stable
    identifiant_stable_du_second = second.identifiant_stable

    with transaction.atomic():
        element_fusionne = ElementDocument.objects.create(
            page=premier.page,
            ordre=premier.ordre,
            label=premier.label,
            texte=texte_fusionne,
            empreinte_contenu=empreinte_du_texte(texte_fusionne),
            chemin_de_section=premier.chemin_de_section,
            provenance=_fusionner_les_provenances(
                premier.provenance, second.provenance,
            ),
            reference_docling=premier.reference_docling,
            # L'element fusionne n'est masque que si les DEUX l'etaient :
            # sinon on ferait disparaitre du contenu visible.
            # / Hidden only if BOTH were hidden.
            masque=premier.masque,  # les deux sont identiques, verifie plus haut
        )

        # UNE PORTION DETACHEE RESTE DETACHEE.
        #
        # Toutes les portions changent d'element — sinon le PROTECT
        # refuserait de supprimer les deux sources. Mais seules celles qui
        # etaient encore attachees passent RETROUVEE. Une portion detachee
        # a perdu son passage source : la promouvoir RETROUVEE la ferait
        # ressusciter sur des offsets que personne n'a jamais valides, et
        # ferait remonter l'etat de l'element sur la foi d'une ancre
        # fantome. Fusionner n'est pas retrouver.
        # / A detached portion stays detached: merging is not finding.
        AncrageExtraction.objects.select_for_update().filter(
            element=premier,
        ).exclude(etat_ancrage=EtatAncrage.DETACHEE).update(
            element=element_fusionne,
            etat_ancrage=EtatAncrage.ANCREE,
        )
        AncrageExtraction.objects.filter(
            element=premier, etat_ancrage=EtatAncrage.DETACHEE,
        ).update(element=element_fusionne)

        for portion in AncrageExtraction.objects.select_for_update().filter(
            element=second,
        ):
            portion.element = element_fusionne
            portion.debut_dans_element += decalage
            portion.fin_dans_element += decalage
            champs_a_sauvegarder = [
                "element", "debut_dans_element", "fin_dans_element",
            ]
            if portion.etat_ancrage != EtatAncrage.DETACHEE:
                portion.etat_ancrage = EtatAncrage.ANCREE
                champs_a_sauvegarder.append("etat_ancrage")
            portion.save(update_fields=champs_a_sauvegarder)

        _coalescer_les_portions_contigues(
            element_fusionne, position_de_la_couture=len(premier.texte),
        )

        premier.delete()
        second.delete()

        # Les elements suivants avancent d'un cran : on est passe de deux
        # elements a un seul. / Following elements shift back by one.
        ElementDocument.objects.filter(
            page=element_fusionne.page, ordre__gt=second.ordre,
        ).update(ordre=F("ordre") - 1)

        ElementOperation.objects.create(
            page=element_fusionne.page,
            element=element_fusionne,
            identifiant_stable_element=element_fusionne.identifiant_stable,
            type_operation=TypeOperationElement.FUSION,
            user=utilisateur,
            justification=justification,
            donnees={
                "elements_fusionnes": [
                    str(identifiant_stable_du_premier),
                    str(identifiant_stable_du_second),
                ],
                "position_de_la_couture": len(premier.texte),
                "resultat": str(element_fusionne.identifiant_stable),
            },
        )

        recalculer_etat_de_l_element(element_fusionne.pk)

    logger.info(
        "Elements fusionnes en %s (texte de %s caracteres).",
        element_fusionne.pk, len(texte_fusionne),
    )
    return element_fusionne


def _fusionner_les_provenances(provenance_du_premier, provenance_du_second):
    """
    Combine les provenances physiques de deux elements fusionnes.
    / Combines the physical provenances of two merged elements.

    LOCALISATION : hypostasis_extractor/services/moteur_structure.py

    Trois formes de provenance, selon la source :
      PDF   -> {page_no, boites: [...]}  les boites s'additionnent
      audio -> {start_time, end_time, voice}  l'intervalle s'elargit
      autre -> {}  rien a faire

    On ne perd aucune information : deux boites PDF distinctes restent
    deux boites, exactement comme un paragraphe a cheval sur deux colonnes.
    / No information is lost: two PDF boxes remain two boxes.
    """
    if not provenance_du_premier:
        return dict(provenance_du_second or {})
    if not provenance_du_second:
        return dict(provenance_du_premier or {})

    provenance_fusionnee = dict(provenance_du_premier)

    # Cas PDF : on concatene les listes de boites.
    #
    # Chaque boite emporte son propre numero de page. Sans ca, fusionner
    # deux elements a cheval sur deux pages ferait dessiner les boites de
    # la page 2 sur la page 1 au surlignage : page_no est unique au niveau
    # de la provenance, alors que les boites, elles, sont une liste.
    # / Each box carries its own page number, or boxes from page 2 would
    # be drawn on page 1.
    boites_du_premier = provenance_du_premier.get("boites")
    boites_du_second = provenance_du_second.get("boites")
    if boites_du_premier is not None or boites_du_second is not None:
        provenance_fusionnee["boites"] = (
            _boites_avec_leur_page(
                boites_du_premier, provenance_du_premier.get("page_no"),
            )
            + _boites_avec_leur_page(
                boites_du_second, provenance_du_second.get("page_no"),
            )
        )

    # Cas audio : l'intervalle couvre les deux tours de parole.
    # / Audio case: the interval covers both turns.
    debut_du_premier = provenance_du_premier.get("start_time")
    fin_du_second = provenance_du_second.get("end_time")
    if debut_du_premier is not None:
        provenance_fusionnee["start_time"] = debut_du_premier
    if fin_du_second is not None:
        provenance_fusionnee["end_time"] = fin_du_second

    # Le locuteur n'est conserve que si c'est le meme des deux cotes.
    # Recoller deux locuteurs differents effacerait qui a dit quoi.
    # / The speaker is kept only if both sides agree.
    locuteur_du_premier = provenance_du_premier.get("voice")
    locuteur_du_second = provenance_du_second.get("voice")
    if locuteur_du_premier != locuteur_du_second:
        provenance_fusionnee.pop("voice", None)

    return provenance_fusionnee


def _boites_avec_leur_page(boites, numero_de_page):
    """
    Note sur chaque boite la page dont elle vient.
    / Stamps each box with the page it comes from.

    LOCALISATION : hypostasis_extractor/services/moteur_structure.py

    Une boite qui porte deja un page_no garde le sien : on ne reecrit pas
    une information plus precise par une plus grossiere.
    / A box that already carries a page_no keeps it.
    """
    if not boites:
        return []

    boites_completees = []
    for boite in boites:
        boite_completee = dict(boite)
        if numero_de_page is not None and "page_no" not in boite_completee:
            boite_completee["page_no"] = numero_de_page
        boites_completees.append(boite_completee)
    return boites_completees


def _coalescer_les_portions_contigues(element_fusionne, position_de_la_couture):
    """
    Recolle les portions devenues contigues apres une fusion.
    / Merges portions that became contiguous after a merge.

    LOCALISATION : hypostasis_extractor/services/moteur_structure.py

    Si une extraction avait une portion finissant pile a la fin du premier
    element, et une autre commencant pile au debut du second, ces deux
    portions sont maintenant collees dans l'element fusionne. On les
    remplace par une seule.

    ATTENTION : elles ne sont PAS contigues au sens strict. Entre les deux
    se trouve le separateur qu'on vient d'inserer. On les coalesce quand
    meme, parce que le separateur est un artefact de notre collage, pas du
    texte que l'extraction aurait ignore.
    / They are separated by the separator we just inserted, which is an
    artefact of our joining, not content the extraction skipped.

    ON NE RECOLLE QU'A LA COUTURE, ET NULLE PART AILLEURS

    Il ne suffit PAS que deux portions soient distantes de la longueur du
    separateur. Il faut qu'elles se rejoignent exactement au point ou les
    deux textes ont ete colles. Sinon, deux portions separees par deux
    caracteres de VRAI texte — ce que la reconciliation de la phase E peut
    tres bien produire en repositionnant des portions — seraient recollees
    en une seule qui avalerait ces deux caracteres jamais extraits.
    / Merging on distance alone would swallow two characters of real text.

    C'est une optimisation, pas une obligation : le surlignage fonctionne
    identiquement avec deux portions adjacentes ou une seule.
    / An optimisation, not a requirement.

    :param element_fusionne: l'element issu de la fusion
    :param position_de_la_couture: l'indice, dans le texte fusionne, ou
        finit le texte du premier element (donc ou commence le separateur)
    """
    debut_apres_la_couture = position_de_la_couture + len(SEPARATEUR_DE_JONCTION)
    portions_par_extraction = {}
    for portion in AncrageExtraction.objects.filter(
        element=element_fusionne,
    ).order_by("extraction_id", "ordre_dans_extraction"):
        portions_par_extraction.setdefault(
            portion.extraction_id, [],
        ).append(portion)

    for extraction_id, portions in portions_par_extraction.items():
        portions_a_supprimer = []

        # On compare chaque portion a la suivante. Si elles se touchent
        # (a un separateur pres), la premiere absorbe la seconde.
        # / Compare each portion to the next; if they touch, merge them.
        indice = 0
        while indice < len(portions) - 1:
            portion_courante = portions[indice]
            portion_suivante = portions[indice + 1]

            # Les deux portions doivent se rejoindre EXACTEMENT au point
            # de couture : la premiere finit ou finissait le texte du
            # premier element, la seconde commence ou commencait celui du
            # second. Un simple ecart de deux caracteres ne suffit pas.
            # / They must meet exactly at the seam, not merely be 2 apart.
            elles_se_rejoignent_a_la_couture = (
                portion_courante.fin_dans_element == position_de_la_couture
                and portion_suivante.debut_dans_element == debut_apres_la_couture
            )
            if elles_se_rejoignent_a_la_couture:
                portion_courante.fin_dans_element = (
                    portion_suivante.fin_dans_element
                )
                portion_courante.save(update_fields=["fin_dans_element"])
                portions_a_supprimer.append(portion_suivante.pk)
                # La portion absorbee disparait de la liste : la suivante
                # doit etre comparee a la portion courante, pas a elle.
                # / The absorbed portion leaves the list.
                portions.pop(indice + 1)
                continue
            indice += 1

        if portions_a_supprimer:
            AncrageExtraction.objects.filter(
                pk__in=portions_a_supprimer,
            ).delete()
            # Les numeros ont des trous apres les suppressions : on les
            # renumerote de 0 a N pour que l'ordre reste lisible.
            # / Renumber from 0 to N after deletions.
            _renumeroter_les_portions_d_une_extraction(extraction_id)


def _renumeroter_les_portions_d_une_extraction(extraction_id):
    """
    Redonne aux portions d'une extraction les numeros 0, 1, 2...
    / Renumbers an extraction's portions as 0, 1, 2...

    LOCALISATION : hypostasis_extractor/services/moteur_structure.py

    Le passage par des numeros temporairement en double est sans danger :
    la contrainte d'unicite est DEFERRABLE, elle n'est verifiee qu'au
    commit. / Temporarily duplicate numbers are safe: deferred constraint.
    """
    portions = AncrageExtraction.objects.filter(
        extraction_id=extraction_id,
    ).order_by("ordre_dans_extraction", "pk")

    for nouveau_numero, portion in enumerate(portions):
        if portion.ordre_dans_extraction != nouveau_numero:
            portion.ordre_dans_extraction = nouveau_numero
            portion.save(update_fields=["ordre_dans_extraction"])


def renumeroter_les_elements_de_la_page(page):
    """
    Redonne aux elements d'une page les ordres 0, 1, 2...
    / Renumbers a page's elements as 0, 1, 2...

    LOCALISATION : hypostasis_extractor/services/moteur_structure.py

    Utile apres une serie d'operations qui a laisse des trous. Rien ne
    depend de la valeur numerique de l'ordre, seulement de son tri : les
    ancres pointent identifiant_stable, jamais l'ordre.
    / Nothing depends on the numeric value of ordre, only on its sorting.
    """
    with transaction.atomic():
        elements = ElementDocument.objects.select_for_update().filter(
            page=page,
        ).order_by("ordre", "pk")

        for nouvel_ordre, element in enumerate(elements):
            if element.ordre != nouvel_ordre:
                element.ordre = nouvel_ordre
                element.save(update_fields=["ordre"])
