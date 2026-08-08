"""
Repositionne les portions d'ancrage apres une correction de texte.
/ Repositions anchor portions after a text correction.

LOCALISATION : hypostasis_extractor/services/reconciliation.py

Implemente les sections 6 et 7 de SPEC-ancrage-par-element-v2.md (phase E).

LE PROBLEME QUE CE FICHIER RESOUT

Quelqu'un corrige une coquille dans un element. Le texte change, donc les
positions glissent. Les portions d'ancrage qui pointaient « du caractere 12
au caractere 30 » ne pointent plus le bon passage.

Trois issues possibles pour chaque portion :

    EXACTE     le passage est toujours au meme endroit -> on ne touche rien
    RETROUVEE  le passage a bouge, mais on le retrouve SANS AMBIGUITE
    DETACHEE   le passage a disparu, OU il apparait plusieurs fois

Le troisieme cas est le plus important : on ne devine pas. Un passage qui
apparait deux fois dans le nouveau texte pourrait etre l'un ou l'autre.
Choisir le premier, c'est ancrer faux sans le dire. On prefere marquer
DETACHEE et laisser un humain trancher.
/ We never guess: an ambiguous match is detached, not arbitrarily picked.
"""

import logging

from django.db import transaction

from core.models import ElementDocument, empreinte_du_texte

from ..models import AncrageExtraction, EtatAncrage
from ..signals import recalculer_etat_de_l_element
from .garde_edition import verifier_qu_aucune_analyse_ne_tourne

logger = logging.getLogger(__name__)


def trouver_toutes_les_occurrences(texte_ou_chercher, texte_cherche):
    """
    Donne toutes les positions ou un texte apparait dans un autre.
    / Returns every position where a text appears within another.

    LOCALISATION : hypostasis_extractor/services/reconciliation.py

    On cherche TOUTES les occurrences, pas seulement la premiere, parce que
    c'est le nombre d'occurrences qui decide : une seule, on repositionne ;
    plusieurs, on refuse de choisir.
    / The COUNT decides: one match repositions, several refuse to choose.

    Les occurrences peuvent se chevaucher : dans "aaaa", chercher "aa"
    donne les positions 0, 1 et 2. C'est voulu — pour compter les
    ambiguites, un chevauchement est une ambiguite comme une autre.
    / Overlapping matches count: for ambiguity, an overlap is an ambiguity.

    :param texte_ou_chercher: le texte dans lequel on cherche
    :param texte_cherche: le texte a trouver
    :return: la liste des positions de debut, dans l'ordre
    """
    # Un texte vide se « trouverait » partout : ca n'a pas de sens, et ca
    # ferait une boucle infinie. / An empty needle matches everywhere.
    if not texte_cherche:
        return []

    positions_trouvees = []
    position_de_depart = 0

    while True:
        position = texte_ou_chercher.find(texte_cherche, position_de_depart)
        if position == -1:
            break
        positions_trouvees.append(position)
        # On repart du caractere SUIVANT le debut trouve, pour attraper
        # aussi les occurrences qui se chevauchent.
        # / Restart one char after, to catch overlapping matches too.
        position_de_depart = position + 1

    return positions_trouvees


def reconcilier_les_portions_de_l_element(element, nouveau_texte):
    """
    Ecrit le nouveau texte d'un element et repositionne ses portions.
    / Writes an element's new text and repositions its portions.

    LOCALISATION : hypostasis_extractor/services/reconciliation.py

    FLUX D'APPEL :
    1. Une vue recoit une correction de texte (phase H).
    2. Elle appelle CETTE FONCTION, qui fait tout d'un bloc.
    3. La vue journalise l'edition dans PageEdit et rend le HTML.

    :param element: l'ElementDocument a corriger
    :param nouveau_texte: son texte apres correction
    :return: {"ancien_texte": str, "exactes": [pk...], "retrouvees": [pk...],
              "detachees": [pk...]}
        ancien_texte est rendu pour que l'appelant puisse journaliser
        PageEdit.donnees_avant sans avoir a le relire lui-meme AVANT
        l'appel — une relecture hors verrou qui rouvrirait une course sur
        le journal.
        / ancien_texte is returned so the caller can journal PageEdit
        without an unlocked re-read.

    POURQUOI CETTE FONCTION ECRIT AUSSI LE TEXTE (ecart avec la spec)

    La spec section 6 appelle une methode
    portion.texte_de_la_portion_avant_edition() qui n'existe pas, et elle a
    par ailleurs retire le parametre ancien_texte en le declarant inutile.
    Les deux ne peuvent pas etre vrais en meme temps : pour retrouver un
    passage, il FAUT savoir ce qu'on cherche, donc l'ancien texte.

    Trois facons de s'en sortir :
      - passer ancien_texte en parametre (la spec l'a explicitement retire) ;
      - exiger que l'appelant appelle cette fonction AVANT d'ecrire le
        nouveau texte (un ordre d'appel non ecrit dans la signature, donc
        un piege : l'inverser produit des ancres fausses en silence) ;
      - faire porter les deux operations par la meme fonction.

    C'est la troisieme qui est retenue. L'ancien texte est lu en base sous
    verrou, les portions sont repositionnees, puis le nouveau texte est
    ecrit — le tout dans une seule transaction. L'appelant n'a plus deux
    appels a ordonner, donc plus d'ordre a se tromper.

    RISQUE RESIDUEL, a connaitre : ca reduit le piege, ca ne le supprime
    pas. Un appelant qui ecrirait le texte LUI-MEME avant d'appeler
    tomberait sur « ancien_texte == nouveau_texte », donc sur un retour
    immediat : les portions resteraient a leurs anciens offsets, en
    silence. La fonction ne peut pas detecter ce cas de l'interieur. Les
    vues de la phase H ne doivent jamais ecrire element.texte elles-memes.
    / Residual risk: a caller writing the text itself first gets a silent
    no-op. Phase H views must never write element.texte themselves.

    CONCURRENCE (section 7 de la spec)

    select_for_update() serialise les corrections concurrentes sur LE MEME
    element. Deux personnes qui corrigent des elements differents ne se
    bloquent jamais : le verrou est par ligne, pas par page.
    """
    resultat = {
        "ancien_texte": "",
        "exactes": [],
        "retrouvees": [],
        "detachees": [],
    }

    # Une analyse en cours travaille sur le texte actuel : le changer
    # sous ses pieds produirait des ancres fausses, ou ferait tomber le
    # job entier. / An edit under a running analysis breaks the anchoring.
    verifier_qu_aucune_analyse_ne_tourne(element.page)

    with transaction.atomic():
        # On relit l'element SOUS VERROU. Deux corrections simultanees sur
        # le meme element passent l'une apres l'autre, jamais en meme temps.
        # / Re-read under lock: concurrent corrections serialize.
        element_verrouille = ElementDocument.objects.select_for_update().get(
            pk=element.pk,
        )
        ancien_texte = element_verrouille.texte
        resultat["ancien_texte"] = ancien_texte

        # Rien n'a change : inutile de toucher aux portions.
        # / Nothing changed: no need to touch the portions.
        if ancien_texte == nouveau_texte:
            return resultat

        # LES PORTIONS DEJA DETACHEE SONT EXCLUES.
        #
        # Une portion detachee a, par definition, des offsets qui ne
        # veulent plus rien dire : le passage qu'elle designait a disparu.
        # Si on la repositionnait, ancien_texte[debut:fin] decouperait un
        # morceau de texte arbitraire, et les cas 1 et 2 s'appliqueraient
        # comme si c'etait le passage source. Une portion detachee
        # pourrait ainsi repasser EXACTE sur un texte qui n'a aucun
        # rapport avec son extraction — ancrer faux sans le dire, ce que
        # ce module existe justement pour empecher.
        #
        # Un re-attachement volontaire, si on l'ajoute un jour, devra
        # chercher extraction_text, jamais la tranche d'offsets perimee.
        # / Detached portions keep meaningless offsets: repositioning them
        # could resurrect a wrong anchor. Excluded.
        portions = list(
            AncrageExtraction.objects
            .select_for_update()
            .select_related("extraction")
            .filter(element=element_verrouille)
            .exclude(etat_ancrage=EtatAncrage.DETACHEE)
        )

        for portion in portions:
            _repositionner_une_portion(
                portion, ancien_texte, nouveau_texte, resultat,
            )

        # Un seul appel groupe, au lieu d'un save() par portion. La spec
        # signale qu'un save() par portion redeclenchait le signal d'etat a
        # chaque fois — N portions donnaient 2N requetes inutiles.
        # / One grouped call instead of one save() per portion.
        if portions:
            AncrageExtraction.objects.bulk_update(
                portions,
                ["debut_dans_element", "fin_dans_element", "etat_ancrage"],
            )

        # L'EMPREINTE SUIT LE TEXTE, TOUJOURS.
        #
        # Oublier de la recalculer laisserait l'empreinte du texte fautif
        # sur un element corrige. La re-ingestion (section 5.3) compare
        # les empreintes pour reconnaitre un element inchange : avec une
        # empreinte perimee, l'element corrige serait classe « disparu »,
        # masque, ses portions detachees — et un doublon au texte
        # identique serait cree puis re-analyse. On perdrait le debat
        # attache, et on paierait un appel LLM pour rien.
        # / The fingerprint must follow the text, or re-ingestion will
        # mistake a corrected element for a disappeared one.
        element_verrouille.texte = nouveau_texte
        element_verrouille.empreinte_contenu = empreinte_du_texte(nouveau_texte)
        element_verrouille.save(
            update_fields=["texte", "empreinte_contenu", "updated_at"],
        )

        # ATTENTION : bulk_update NE DECLENCHE PAS les signaux post_save.
        # Sans cet appel explicite, un element dont toutes les portions
        # viennent de passer DETACHEE garderait l'etat DEBATTU, et
        # continuerait d'exiger une justification pour rien.
        # / bulk_update fires NO signal: the state must be recomputed here.
        recalculer_etat_de_l_element(element_verrouille.pk)

    nombre_de_detachees = len(resultat["detachees"])
    if nombre_de_detachees:
        logger.info(
            "Reconciliation de l'element %s : %s portion(s) detachee(s) sur "
            "%s. Le passage source a change ou est devenu ambigu.",
            element_verrouille.pk, nombre_de_detachees, len(portions),
        )

    return resultat


def _repositionner_une_portion(portion, ancien_texte, nouveau_texte, resultat):
    """
    Decide du sort d'une portion apres la correction, et la modifie sur place.
    / Decides one portion's fate after the correction, modifying it in place.

    LOCALISATION : hypostasis_extractor/services/reconciliation.py

    La portion n'est pas sauvegardee ici : l'appelant fait un bulk_update
    groupe. / The portion is not saved here; the caller bulk-updates.

    LES PORTIONS DES EXTRACTIONS MASQUEES SONT TRAITEES AUSSI (ecart assume)

    La spec section 6 dit de les ignorer — « pas de travail sur ce que
    personne ne voit ». On les traite quand meme, pour une raison simple :
    une portion laissee avec ses anciens offsets sur un texte qui a change
    pointe desormais n'importe quoi. Le jour ou l'extraction est
    demasquee, elle ressort avec une ancre fausse, sans que rien ne l'ait
    signale. C'est exactement ce que le principe « rien ne disparait en
    silence » interdit.

    Le cout evite est negligeable (quelques comparaisons de chaines), le
    bug evite est silencieux et durable. Les portions masquees ne sont en
    revanche pas comptees dans le resultat rendu a l'utilisateur : elles
    n'ont pas a apparaitre dans « 3 extractions repositionnees ».
    / Hidden portions are repositioned too, but not reported.
    """
    texte_recherche = ancien_texte[
        portion.debut_dans_element:portion.fin_dans_element
    ]
    portion_visible = not portion.extraction.masquee

    # Cas 1 : le passage est toujours exactement a la meme place.
    # / Case 1: the passage is still exactly where it was.
    texte_a_la_position_actuelle = nouveau_texte[
        portion.debut_dans_element:portion.fin_dans_element
    ]
    if texte_a_la_position_actuelle == texte_recherche:
        portion.etat_ancrage = EtatAncrage.ANCREE
        if portion_visible:
            resultat["exactes"].append(portion.pk)
        return

    # Cas 2 : le passage a bouge, mais il n'apparait qu'UNE fois.
    # / Case 2: the passage moved, but appears only ONCE.
    occurrences = trouver_toutes_les_occurrences(nouveau_texte, texte_recherche)
    il_n_y_a_qu_une_occurrence = len(occurrences) == 1
    if il_n_y_a_qu_une_occurrence:
        nouvelle_position = occurrences[0]
        portion.debut_dans_element = nouvelle_position
        portion.fin_dans_element = nouvelle_position + len(texte_recherche)
        portion.etat_ancrage = EtatAncrage.ANCREE
        if portion_visible:
            resultat["retrouvees"].append(portion.pk)
        return

    # Cas 3 : zero occurrence (le passage a disparu), OU plusieurs
    # occurrences (on ne saurait pas laquelle choisir). Dans les deux cas,
    # on ne devine pas.
    # / Case 3: zero or several matches. We do not guess.
    portion.etat_ancrage = EtatAncrage.DETACHEE
    if portion_visible:
        resultat["detachees"].append(portion.pk)
