"""
Masquer un element sans le supprimer, et pouvoir revenir en arriere.
/ Hide an element without deleting it, and be able to undo.

LOCALISATION : hypostasis_extractor/services/masquage.py

Implemente la section 5.4 de SPEC-ancrage-par-element-v2.md (phase G).

CE QUE MASQUER VEUT DIRE, ET CE QUE CA NE VEUT PAS DIRE

La transcription audio invente parfois du contenu : un bruit de fond
transcrit en mots, une toux, une phrase repetee deux fois. Ce n'est pas
une coquille a corriger — il n'y a rien a corriger VERS, le contenu
n'existe pas. Ce n'est pas non plus une note hors-texte, qui documente une
incertitude, pas une absence.
/ Hiding is neither a correction nor an annotation: the content is not real.

Un element masque :
  - ne part plus dans les chunks envoyes au LLM,
  - reste visible dans le document, barre et grise,
  - voit ses portions d'ancrage passer DETACHEE, jamais supprimees,
  - peut etre demasque, ce qui les remet en place si le texte n'a pas
    change entre-temps.

C'est l'application directe du principe : rien ne disparait en silence.
/ Nothing ever disappears silently.
"""

import hashlib
import logging

from django.db import transaction

from core.models import (
    ElementDocument,
    ElementOperation,
    TypeOperationElement,
)

from ..models import AncrageExtraction, EtatAncrage
from ..signals import recalculer_etat_de_l_element
from .garde_edition import (
    verifier_qu_aucune_analyse_ne_tourne,
    verifier_qu_aucune_synthese_ne_cite,
)

logger = logging.getLogger(__name__)


def hash_du_texte_brut(texte):
    """
    Calcule l'empreinte du texte EXACT, sans aucune normalisation.
    / Computes the fingerprint of the EXACT text, with no normalization.

    LOCALISATION : hypostasis_extractor/services/masquage.py

    POURQUOI PAS empreinte_du_texte() DE core/models.py

    Cette derniere normalise : minuscules, espaces ecrases. C'est ce qu'il
    faut pour reconnaitre un element inchange lors d'une re-ingestion —
    une difference de casse ne fait pas un contenu different.

    Mais ici, on veut savoir si les OFFSETS sont encore valides. Or une
    correction qui ne change que la casse ou les espaces DEPLACE les
    caracteres sans changer l'empreinte normalisee. Corriger une double
    espace en simple espace decale tout ce qui suit d'un caractere : les
    offsets deviennent faux, et l'empreinte normalisee ne le voit pas.
    / Normalized fingerprints hide whitespace and case fixes, which do
    move every offset that follows.

    :param texte: le texte a empreindre
    :return: un SHA256 hexadecimal du texte exact
    """
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def masquer_un_element(element, justification="", utilisateur=None,
                       verifier_les_jobs=True, verifier_les_citations=True):
    """
    Retire un element du contenu utile sans le supprimer.
    / Removes an element from the useful content without deleting it.

    LOCALISATION : hypostasis_extractor/services/masquage.py

    :param element: l'ElementDocument a masquer
    :param justification: pourquoi (trace dans le journal)
    :param utilisateur: qui (trace dans le journal)
    :return: le nombre de portions detachees par ce masquage

    CE QUE LE JOURNAL NOTE, ET POURQUOI

    Deux informations, sans lesquelles le demasquage serait dangereux :

    1. Le hash du texte BRUT. Au demasquage, il faudra savoir si le texte
       a bouge entre-temps. Si c'est exactement le meme texte, les offsets
       des portions sont toujours bons.

    2. Les identifiants des portions detachees PAR CE MASQUAGE. Un element
       peut porter des portions deja detachees avant, par une correction
       de texte par exemple. Celles-la ont des offsets perimes depuis
       longtemps : les rattacher au demasquage les ferait pointer
       n'importe quoi. Seules les portions que ce masquage a detachees
       doivent revenir.
    / Without both, unhiding would resurrect anchors that were already
    stale before the hide.

    :param verifier_les_jobs: mettre a False quand l'appelant a deja
        verifie qu'aucune analyse ne tourne — la re-ingestion le fait une
        fois pour toute la page, plutot qu'une fois par element masque.
        / Set to False when the caller already checked, once for the page.
    :param verifier_les_citations: idem pour la garde § 5 — la
        re-ingestion l'a deja passee au niveau PAGE (sur-ensemble strict
        de la garde element), inutile de la repayer par element.
        / Same for the § 5 guard, already page-checked by re-ingestion.
    """
    if verifier_les_jobs:
        verifier_qu_aucune_analyse_ne_tourne(element.page)
    # Un element deja masque est un no-op : inutile d'opposer la garde
    # citation a un geste qui ne changera rien (relecture E, M9).
    # / An already-hidden element is a no-op: no guard needed.
    if element.masque:
        logger.info("Element %s deja masque, rien a faire.", element.pk)
        return 0
    # Masquer un element cite par une synthese FIGEE ferait disparaitre
    # sa preuve (SPEC-synthese § 5, phase E). / Hiding a frozen-cited
    # element would vanish its evidence.
    if verifier_les_citations:
        verifier_qu_aucune_synthese_ne_cite(element)

    with transaction.atomic():
        element_verrouille = ElementDocument.objects.select_for_update().get(
            pk=element.pk,
        )

        if element_verrouille.masque:
            logger.info("Element %s deja masque, rien a faire.", element.pk)
            return 0

        identifiants_des_portions_detachees = detacher_les_portions_de(
            element_verrouille,
        )

        element_verrouille.masque = True
        element_verrouille.save(update_fields=["masque", "updated_at"])

        ElementOperation.objects.create(
            page=element_verrouille.page,
            element=element_verrouille,
            identifiant_stable_element=element_verrouille.identifiant_stable,
            type_operation=TypeOperationElement.MASQUAGE,
            user=utilisateur,
            justification=justification,
            donnees={
                "hash_du_texte_au_masquage": hash_du_texte_brut(
                    element_verrouille.texte,
                ),
                "portions_detachees": identifiants_des_portions_detachees,
            },
        )

        recalculer_etat_de_l_element(element_verrouille.pk)

    # L'instance de l'appelant doit refleter la base : sans ca, un appel
    # enchaine (scinder, fusionner) relirait masque=False en memoire et
    # perdrait silencieusement le masquage.
    # / Keep the caller's instance in sync, or a chained call loses the hide.
    element.masque = True

    logger.info(
        "Element %s masque, %s portion(s) detachee(s).",
        element.pk, len(identifiants_des_portions_detachees),
    )
    return len(identifiants_des_portions_detachees)


def demasquer_un_element(element, justification="", utilisateur=None,
                         verifier_les_jobs=True):
    """
    Remet un element dans le contenu utile, et rattache les portions que
    le masquage avait detachees, si le texte n'a pas change.
    / Puts an element back, reattaching the portions this hide detached.

    LOCALISATION : hypostasis_extractor/services/masquage.py

    :param element: l'ElementDocument a demasquer
    :param justification: pourquoi (trace dans le journal)
    :param utilisateur: qui (trace dans le journal)
    :return: {"portions_rattachees": int, "portions_laissees_detachees": int}

    POURQUOI ON NE REUTILISE PAS LA RECONCILIATION

    La reconciliation (services/reconciliation.py) repositionne des
    portions apres un CHANGEMENT de texte, en cherchant le passage a sa
    nouvelle place. Ici, c'est l'inverse : on veut verifier que le texte
    n'a justement PAS change, et la reconciliation rend la main
    immediatement dans ce cas.

    Elle exclut d'ailleurs les portions DETACHEE, a raison : leurs offsets
    ne veulent plus rien dire dans le cas general. Le demasquage est la
    seule exception legitime, parce qu'on sait exactement lesquelles ont
    ete detachees, par quoi, et qu'on peut verifier que rien n'a bouge
    depuis.
    / Unhiding is the one legitimate exception, because we know precisely
    which portions were detached and can verify nothing moved.

    :param verifier_les_jobs: voir masquer_un_element.
    """
    if verifier_les_jobs:
        verifier_qu_aucune_analyse_ne_tourne(element.page)
    # PAS de garde citation ici (relecture E, I1) : le demasquage ne
    # modifie aucun texte — il repasse des ancres de DETACHEE a ANCREE
    # apres avoir verifie que le hash n'a pas bouge. Il rend la preuve
    # PLUS fidele, jamais moins. Le bloquer enfermerait l'utilisateur :
    # un element masque par erreur puis cite (le lien nait DETACHEE)
    # ne serait plus jamais demasquable.
    # / NO citation guard: unhiding restores anchors after a hash check,
    # making the evidence MORE faithful; blocking it would lock users out.

    resultat = {"portions_rattachees": 0, "portions_laissees_detachees": 0}

    with transaction.atomic():
        element_verrouille = ElementDocument.objects.select_for_update().get(
            pk=element.pk,
        )

        if not element_verrouille.masque:
            logger.info("Element %s n'est pas masque, rien a faire.", element.pk)
            return resultat

        contexte_du_masquage = _contexte_du_dernier_masquage(element_verrouille)
        hash_au_masquage = contexte_du_masquage.get("hash_du_texte_au_masquage")
        identifiants_a_rattacher = contexte_du_masquage.get(
            "portions_detachees", [],
        )

        hash_actuel = hash_du_texte_brut(element_verrouille.texte)
        le_texte_est_identique = (
            hash_au_masquage is not None and hash_au_masquage == hash_actuel
        )

        # On ne considere QUE les portions que ce masquage avait
        # detachees, et seulement si elles sont encore detachees.
        # / Only the portions this hide detached, and only if still detached.
        portions_a_rattacher = list(
            AncrageExtraction.objects
            .select_for_update()
            .filter(
                pk__in=identifiants_a_rattacher,
                element=element_verrouille,
                etat_ancrage=EtatAncrage.DETACHEE,
            )
        )

        if le_texte_est_identique:
            for portion in portions_a_rattacher:
                # RETROUVEE et non EXACTE : la position est revenue apres
                # un detour, elle n'est plus celle du premier ancrage.
                # / RETROUVEE, not EXACTE: it came back after a detour.
                portion.etat_ancrage = EtatAncrage.ANCREE
            if portions_a_rattacher:
                AncrageExtraction.objects.bulk_update(
                    portions_a_rattacher, ["etat_ancrage"],
                )
            resultat["portions_rattachees"] = len(portions_a_rattacher)
        else:
            # Le texte a change pendant le masquage : les offsets ne
            # designent plus rien de sur. On ne devine pas.
            # / The text changed while hidden: we do not guess.
            resultat["portions_laissees_detachees"] = len(portions_a_rattacher)

        element_verrouille.masque = False
        element_verrouille.save(update_fields=["masque", "updated_at"])

        ElementOperation.objects.create(
            page=element_verrouille.page,
            element=element_verrouille,
            identifiant_stable_element=element_verrouille.identifiant_stable,
            type_operation=TypeOperationElement.DEMASQUAGE,
            user=utilisateur,
            justification=justification,
            donnees={
                "hash_au_masquage": hash_au_masquage,
                "hash_au_demasquage": hash_actuel,
                "le_texte_a_change": not le_texte_est_identique,
                "portions_rattachees": resultat["portions_rattachees"],
                "portions_laissees_detachees": (
                    resultat["portions_laissees_detachees"]
                ),
            },
        )

        recalculer_etat_de_l_element(element_verrouille.pk)

    element.masque = False

    logger.info(
        "Element %s demasque : %s portion(s) rattachee(s), %s laissee(s) "
        "detachee(s).",
        element.pk, resultat["portions_rattachees"],
        resultat["portions_laissees_detachees"],
    )
    return resultat


def _contexte_du_dernier_masquage(element):
    """
    Relit dans le journal ce que le dernier masquage avait note.
    / Reads back what the last hide operation recorded.

    LOCALISATION : hypostasis_extractor/services/masquage.py

    Rend un dictionnaire vide si aucun masquage n'est journalise pour cet
    element. Sans contexte de reference, on ne peut rien affirmer sur le
    texte ni sur les portions, donc on ne rattache rien.

    On cherche d'abord par la cle etrangere, puis par identifiant_stable :
    une operation de structure (scission, fusion) peut avoir vide la cle
    etrangere en supprimant l'element d'origine.
    / Falls back to identifiant_stable, since a structural operation may
    have nulled the foreign key.

    :param element: l'ElementDocument concerne
    :return: le dictionnaire donnees du dernier masquage, ou {}
    """
    dernier_masquage = ElementOperation.objects.filter(
        element=element,
        type_operation=TypeOperationElement.MASQUAGE,
    ).order_by("-created_at", "-pk").first()

    if dernier_masquage is None:
        dernier_masquage = ElementOperation.objects.filter(
            identifiant_stable_element=element.identifiant_stable,
            type_operation=TypeOperationElement.MASQUAGE,
        ).order_by("-created_at", "-pk").first()

    if dernier_masquage is None:
        return {}
    return dernier_masquage.donnees or {}


def detacher_les_portions_de(element):
    """
    Marque DETACHEE les portions encore attachees a un element.
    / Marks as DETACHEE the portions still attached to an element.

    LOCALISATION : hypostasis_extractor/services/masquage.py

    Les portions ne sont jamais supprimees : une extraction qu'on ne peut
    plus ancrer reste visible dans la section « detachees » du drawer, ou
    un humain peut decider quoi en faire.
    / Portions are never deleted, only marked.

    Rend la LISTE des identifiants detaches, et pas seulement leur nombre :
    c'est ce qui permet au demasquage de ne rattacher que celles-la, sans
    toucher a celles qui etaient deja detachees avant.
    / Returns the list of PKs, so unhiding can reattach exactly these.

    :param element: l'ElementDocument concerne
    :return: la liste des identifiants des portions detachees
    """
    portions_a_detacher = list(
        AncrageExtraction.objects
        .filter(element=element)
        .exclude(etat_ancrage=EtatAncrage.DETACHEE)
        .values_list("pk", flat=True)
    )

    if portions_a_detacher:
        AncrageExtraction.objects.filter(pk__in=portions_a_detacher).update(
            etat_ancrage=EtatAncrage.DETACHEE,
        )

        # Une ancre detachee detache la citation qui la pointait — meme
        # regle que la reconciliation (SPEC-synthese § 4.2, relecture B N6).
        # Couvre le masquage ET la reingestion, qui passe par ici.
        # / A detached anchor detaches its citation; covers masking AND
        # re-ingestion.
        from core.services.synthese import detacher_les_citations_des_portions
        detacher_les_citations_des_portions(portions_a_detacher)

    return portions_a_detacher
