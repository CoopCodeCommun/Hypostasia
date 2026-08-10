"""
Rend le document de lecture a partir des ElementDocument.
/ Renders the reading document from ElementDocument rows.

LOCALISATION : front/services/rendu_elements.py

Implemente la phase I de SPEC-ancrage-par-element-v2.md.

CE QUE CE FICHIER REMPLACE

Jusqu'ici, l'affichage partait de Page.html_readability et y injectait des
balises de surlignage a partir d'offsets plats (front/utils.py). Deux
choses ne marchaient pas :

  - une extraction en plusieurs portions n'avait aucune representation :
    un seul couple debut/fin ne peut pas designer trois paragraphes ;
  - deux extractions qui se chevauchent produisaient du HTML mal
    imbrique, que le navigateur « reparait » a sa facon. Il y a 3 898
    paires de ce genre en base : ce n'est pas un cas d'ecole.

Ici, on part des elements. Chaque element devient un bloc, et son texte
est decoupe en segments selon les portions qui le couvrent.
/ We start from elements, and cut each element's text into segments.

LE DECOUPAGE EN SEGMENTS, ET POURQUOI

Prenons un element ou deux idees se croisent :

    A couvre  0 -> 20
    B couvre 10 -> 30

Aucune imbrication ne peut representer ca : <a><b></a></b> n'est pas du
HTML valide. On collecte donc toutes les bornes — 0, 10, 20, 30 — et on
decoupe le texte entre elles :

    [0-10]  couvert par A
    [10-20] couvert par A et B
    [20-30] couvert par B

Dans chaque segment, l'ensemble des idees qui le couvrent ne change pas.
On peut donc ouvrir et fermer toutes les balises A L'INTERIEUR du segment,
et le HTML reste bien forme quoi qu'il arrive.
/ Within a segment the covering set is constant, so every tag opens and
closes inside it, and the HTML is always well formed.
"""

import logging

from django.utils.html import escape
from django.utils.safestring import mark_safe

from hypostasis_extractor.models import AncrageExtraction, EtatAncrage

logger = logging.getLogger(__name__)

# Au-dela de ce nombre d'idees sur un meme segment, on cesse d'empiler des
# balises : le texte deviendrait illisible et le DOM inutilement profond.
# Une page migree porte un element de 2 469 portions — le garde-fou n'est
# pas theorique. / Beyond this, stacking marks helps no one.
MAXIMUM_D_IDEES_SUPERPOSEES = 4

# Au-dela de ce nombre de MARQUES pour un seul element, on rend le texte
# nu, sans aucun surlignage.
#
# POURQUOI CE SECOND PLAFOND EXISTE
#
# Le premier ne borne que la PROFONDEUR d'imbrication par segment. Il ne
# borne pas le NOMBRE de segments. Mesure sur l'element pathologique issu
# de la bascule (200 954 caracteres, 2 469 portions) : 4 876 segments et
# 8 158 marques, soit 1,4 Mo de HTML en plus a chaque affichage, et autant
# d'arrets de tabulation dans la page.
#
# Passe ce seuil, le surlignage n'aide plus personne : on rend le texte
# lisible, et on le dit dans le bloc plutot que de laisser le navigateur
# s'effondrer en silence.
# / The first cap bounds nesting depth, not the number of segments.
MAXIMUM_DE_MARQUES_PAR_ELEMENT = 400

# Quelle balise pour quel label Docling.
# Un label inconnu retombe sur un paragraphe : jamais de plantage sur une
# forme imprevue. / An unknown label falls back to a paragraph.
BALISE_PAR_LABEL = {
    "title": "h2",
    "section_header": "h3",
    "list_item": "li",
    "table": "pre",
    "code": "pre",
}
BALISE_PAR_DEFAUT = "p"


def construire_les_segments(longueur_du_texte, portions):
    """
    Decoupe un texte en segments, selon les portions qui le couvrent.
    / Cuts a text into segments, according to the portions covering it.

    LOCALISATION : front/services/rendu_elements.py

    :param longueur_du_texte: la longueur du texte de l'element
    :param portions: les AncrageExtraction posees sur cet element
    :return: liste de (debut, fin, [portions qui couvrent ce segment])

    Les portions rendues pour un segment sont triees de la plus large a la
    plus etroite : la balise la plus englobante est ouverte en premier,
    donc fermee en dernier. L'ordre est ainsi le meme d'un rendu a
    l'autre, ce qui rend le HTML comparable et les tests stables.
    / Widest first, so nesting order is deterministic.
    """
    if longueur_du_texte <= 0:
        return []

    # Les bornes valides, ramenees dans le texte. Une portion dont les
    # offsets debordent — edition non reconciliee, bug ailleurs — est
    # rognee plutot que de faire echouer l'affichage de toute la page.
    # / Out-of-range offsets are clamped, never fatal.
    portions_utilisables = []
    nombre_de_portions_rognees = 0
    nombre_de_portions_jetees = 0
    for portion in portions:
        debut = max(0, min(portion.debut_dans_element, longueur_du_texte))
        fin = max(0, min(portion.fin_dans_element, longueur_du_texte))

        if (debut, fin) != (portion.debut_dans_element, portion.fin_dans_element):
            nombre_de_portions_rognees += 1

        if fin <= debut:
            nombre_de_portions_jetees += 1
            continue
        portions_utilisables.append((debut, fin, portion))

    # Une portion hors bornes signale une incoherence en amont : edition
    # non reconciliee, bug ailleurs. On rogne pour que la page s'affiche
    # quand meme, mais on ne le tait pas.
    # / Clamping keeps the page displayable; staying silent would hide a bug.
    if nombre_de_portions_rognees or nombre_de_portions_jetees:
        logger.warning(
            "Rendu : %s portion(s) rognee(s) et %s jetee(s) sur un texte de "
            "%s caracteres — des offsets sortent du texte de leur element.",
            nombre_de_portions_rognees, nombre_de_portions_jetees,
            longueur_du_texte,
        )

    if not portions_utilisables:
        return [(0, longueur_du_texte, [])]

    points_de_coupe = {0, longueur_du_texte}
    for debut, fin, _portion in portions_utilisables:
        points_de_coupe.add(debut)
        points_de_coupe.add(fin)
    points_de_coupe = sorted(points_de_coupe)

    segments = []
    for numero in range(len(points_de_coupe) - 1):
        debut_du_segment = points_de_coupe[numero]
        fin_du_segment = points_de_coupe[numero + 1]

        portions_couvrantes = [
            portion
            for debut, fin, portion in portions_utilisables
            if debut <= debut_du_segment and fin >= fin_du_segment
        ]
        # La plus large d'abord : elle englobe les autres.
        # / Widest first: it wraps the others.
        # On trie sur les bornes ROGNEES, pas sur celles d'origine : une
        # portion debordante serait sinon classee plus large qu'elle ne
        # l'est reellement dans ce texte.
        # / Sort on clamped bounds, or an overflowing portion looks wider.
        bornes_rognees = {
            portion.pk: (debut, fin)
            for debut, fin, portion in portions_utilisables
        }
        portions_couvrantes.sort(
            key=lambda p: (
                bornes_rognees[p.pk][0] - bornes_rognees[p.pk][1],  # largeur, decroissante
                bornes_rognees[p.pk][0],
                p.pk,
            )
        )
        segments.append((debut_du_segment, fin_du_segment, portions_couvrantes))

    return segments


def rendre_le_texte_d_un_element(element, portions):
    """
    Rend le texte d'un element en HTML, avec ses surlignages.
    / Renders an element's text as HTML, with its highlights.

    LOCALISATION : front/services/rendu_elements.py

    :param element: l'ElementDocument
    :param portions: les AncrageExtraction posees dessus
    :return: du HTML sur (SafeString)

    L'ECHAPPEMENT EST FAIT SEGMENT PAR SEGMENT, ET C'EST IMPORTANT

    element.texte est du texte brut : il peut contenir < ou &. On echappe
    CHAQUE segment avant de l'entourer de balises.

    On ne peut pas faire autrement :
      - echapper apres avoir insere les balises les echapperait aussi ;
      - echapper le texte entier AVANT de le decouper decalerait toutes
        les positions, puisque & devient &amp; — cinq caracteres la ou il
        y en avait un.
    / Escaping the whole text first would shift every offset.
    """
    texte = element.texte or ""
    segments = construire_les_segments(len(texte), portions)

    if not segments:
        return mark_safe("")

    # Combien de marques ce rendu produirait-il ? On le sait avant de
    # construire quoi que ce soit. / Count before building anything.
    nombre_de_marques_prevu = sum(
        min(len(portions_couvrantes), MAXIMUM_D_IDEES_SUPERPOSEES)
        for _debut, _fin, portions_couvrantes in segments
    )
    if nombre_de_marques_prevu > MAXIMUM_DE_MARQUES_PAR_ELEMENT:
        logger.warning(
            "Element %s : %s marques prevues sur %s segments — au-dela du "
            "plafond de %s. Le texte est rendu SANS surlignage : au-dela de "
            "ce volume, il n'aide plus personne et rend la page inutilisable.",
            element.pk, nombre_de_marques_prevu, len(segments),
            MAXIMUM_DE_MARQUES_PAR_ELEMENT,
        )
        return mark_safe(escape(texte))

    nombre_de_segments_ecretes = 0
    morceaux_de_html = []
    for debut, fin, portions_couvrantes in segments:
        texte_du_segment = escape(texte[debut:fin])

        if not portions_couvrantes:
            morceaux_de_html.append(texte_du_segment)
            continue

        portions_a_baliser = portions_couvrantes[:MAXIMUM_D_IDEES_SUPERPOSEES]
        if len(portions_couvrantes) > MAXIMUM_D_IDEES_SUPERPOSEES:
            nombre_de_segments_ecretes += 1

        balises_ouvrantes = []
        for portion in portions_a_baliser:
            extraction = portion.extraction
            balises_ouvrantes.append(
                '<mark class="portion hl-extraction"'
                f' data-extraction-id="{extraction.pk}"'
                f' data-statut="{escape(extraction.statut_debat)}"'
                # Le nombre REELLEMENT superpose, pas le nombre balise :
                # l'affichage doit pouvoir dire « 7 idees ici » meme s'il
                # n'en dessine que 4.
                # / The real count, not the drawn one.
                f' data-superposition="{len(portions_couvrantes)}"'
                f' data-portion="{portion.ordre_dans_extraction}"'
                ' tabindex="0">'
            )

        morceaux_de_html.append("".join(balises_ouvrantes))
        morceaux_de_html.append(texte_du_segment)
        morceaux_de_html.append("</mark>" * len(portions_a_baliser))

    # Un seul message par element, pas un par segment : sur l'element
    # pathologique, la version precedente ecrivait 77 lignes de log a
    # chaque affichage de la page.
    # / One message per element, not per segment.
    if nombre_de_segments_ecretes:
        logger.info(
            "Element %s : %s passage(s) portent plus de %s idees "
            "superposees ; seules les plus larges y sont balisees.",
            element.pk, nombre_de_segments_ecretes,
            MAXIMUM_D_IDEES_SUPERPOSEES,
        )

    return mark_safe("".join(morceaux_de_html))


def construire_les_blocs_de_lecture(page):
    """
    Prepare les blocs a afficher pour une page.
    / Prepares the blocks to display for a page.

    LOCALISATION : front/services/rendu_elements.py

    :param page: la Page a rendre
    :return: liste de dicts, un par bloc, prets pour le template

    DEUX REQUETES, PAS UNE PAR ELEMENT

    Une page peut porter 650 elements. Lire ses portions element par
    element ferait 650 requetes. On charge donc tout en deux fois, et on
    regroupe en memoire.
    / Two queries total, never one per element.

    LES PORTIONS DETACHEES NE SONT PAS RENDUES

    Une portion detachee a perdu son passage source : ses offsets ne
    designent plus rien de sur. La poser quand meme surlignerait un
    passage au hasard. Elle apparait dans le panneau, avec de quoi la
    replacer a la main — pas dans le texte.
    / A detached portion has no reliable position; it is not drawn.
    """
    elements = list(page.elements.all().order_by("ordre"))
    if not elements:
        return []

    portions = (
        AncrageExtraction.objects
        .filter(element__page=page, extraction__masquee=False)
        .exclude(etat_ancrage=EtatAncrage.DETACHEE)
        .select_related("extraction")
        .order_by("debut_dans_element", "pk")
    )

    portions_par_element = {}
    for portion in portions:
        portions_par_element.setdefault(portion.element_id, []).append(portion)

    blocs = []
    for indice, element in enumerate(elements):
        portions_de_l_element = portions_par_element.get(element.pk, [])
        identifiants_des_idees = {
            portion.extraction_id for portion in portions_de_l_element
        }

        # « Recoller avec le suivant » (U1) n'a de sens que si un
        # suivant existe ET qu'il est visible : le service refuse
        # toujours de fusionner un visible avec un masque (relecture
        # U1, defaut M8) — le bouton ne doit donc pas etre propose.
        # / Merge button only when a VISIBLE next element exists: the
        # service always refuses merging into a hidden one.
        element_suivant = (
            elements[indice + 1] if indice + 1 < len(elements) else None
        )
        fusion_possible = (
            element_suivant is not None
            and not element_suivant.masque
            and not element.masque
        )

        blocs.append({
            "element": element,
            "balise": BALISE_PAR_LABEL.get(element.label, BALISE_PAR_DEFAUT),
            "html_du_texte": rendre_le_texte_d_un_element(
                element, portions_de_l_element,
            ),
            "nombre_d_idees": len(identifiants_des_idees),
            "est_masque": element.masque,
            "fusion_possible": fusion_possible,
        })

    return _regrouper_les_items_de_liste(blocs)


def _regrouper_les_items_de_liste(blocs):
    """
    Regroupe les list_item consecutifs, pour un HTML valide.
    / Groups consecutive list_item blocks, for valid HTML.

    LOCALISATION : front/services/rendu_elements.py

    Un <li> hors d'un <ul> n'est pas du HTML valide. Docling rend les
    puces d'une meme liste comme des elements successifs de label
    list_item : on les rassemble donc sous une seule liste.
    / A <li> outside a <ul> is invalid HTML.

    Le regroupement est fait ICI, dans une boucle explicite, et pas dans
    le template : un gabarit Django ne sait pas regarder l'element
    suivant sans devenir illisible.
    / Done here, because a template cannot look ahead readably.
    """
    blocs_regroupes = []
    liste_en_cours = None

    for bloc in blocs:
        c_est_une_puce = bloc["balise"] == "li"

        if c_est_une_puce:
            if liste_en_cours is None:
                liste_en_cours = {"est_une_liste": True, "puces": []}
                blocs_regroupes.append(liste_en_cours)
            liste_en_cours["puces"].append(bloc)
            continue

        liste_en_cours = None
        bloc["est_une_liste"] = False
        blocs_regroupes.append(bloc)

    # Une liste dont TOUTES les puces sont masquees ne doit pas rendre
    # un <ul> vide chez un simple lecteur (relecture U1, defaut B3) —
    # le template a besoin de le savoir sans regarder chaque puce.
    # / Flag fully-hidden lists so the template can skip the empty <ul>.
    for bloc in blocs_regroupes:
        if bloc.get("est_une_liste"):
            bloc["toutes_masquees"] = all(
                puce["est_masque"] for puce in bloc["puces"]
            )

    return blocs_regroupes
