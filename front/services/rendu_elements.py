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
import re

from django.db.models import Exists, OuterRef
from django.utils.html import escape
from django.utils.safestring import mark_safe

from hypostasis_extractor.models import (
    AncrageExtraction,
    CommentaireExtraction,
    EtatAncrage,
)

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
    # `<table>`, et non plus `<pre>` : un `<pre>` ne porte ni ligne ni
    # colonne. Un lecteur d'ecran y lit une bouillie de barres
    # verticales, il ne se replie pas, et celui du PDF etalon mesurait
    # 3 162px. Le markdown « pipe » de Docling est converti par
    # `convertir_un_tableau_markdown`, qui referme les marques d'ancrage
    # a chaque frontiere de cellule.
    # / <pre> carries neither rows nor columns; screen readers read a
    # soup of pipes and it never wraps.
    "table": "table",
    "code": "pre",
    # Ajoutes le 12 aout (ecart n°6 de l'etalon). Ces trois labels
    # tombaient dans le `<p>` par defaut :
    #
    # · une CITATION qui a la forme du texte qui la commente n'est plus
    #   une citation — l'etalon lui donne un filet et l'italique ;
    # · une FORMULE en `<p>` se coupe au milieu et se justifie comme de
    #   la prose ; l'etalon la centre entre deux filets ;
    # · une IMAGE sans `<figure>` perd le lien entre le visuel et sa
    #   legende, y compris pour un lecteur d'ecran.
    # / These three fell into the default <p>: a quote shaped like the
    # prose around it is no quote; a formula breaks mid-line; an image
    # without <figure> loses the tie to its caption.
    "blockquote": "blockquote",
    "formula": "figure",
    "picture": "figure",
}
BALISE_PAR_DEFAUT = "p"


# Une ligne faite de tirets, de deux-points et de barres : c'est la
# CONVENTION d'ecriture du markdown, pas une donnee. Elle ne doit jamais
# devenir une ligne du tableau.
# / The dashes row is markdown syntax, not data.
MOTIF_LIGNE_DE_SEPARATION = re.compile(r"^[\s|:-]+$")

# Une balise ouvrante ou fermante dans le HTML deja rendu. On ne parse
# pas du HTML quelconque : seulement celui que ce module vient de
# produire, dont on connait la forme.
# / Only the HTML this module just produced, whose shape we know.
MOTIF_BALISE = re.compile(r"<(/?)(\w+)([^>]*)>")


def _decouper_en_cellules_en_refermant_les_marques(ligne_html):
    """
    Decoupe une ligne de tableau sur ses barres, en refermant les balises
    ouvertes a chaque frontiere et en les rouvrant apres.
    / Split a table row on its pipes, closing open tags at each boundary
    and reopening them after.

    LOCALISATION : front/services/rendu_elements.py

    POURQUOI CE SOIN

    Le texte arrive DEJA balise : les marques d'ancrage y sont posees aux
    positions des idees. Une idee qui traverse deux cellules laisserait,
    si on decoupait naivement, une balise ouverte dans l'une et fermee
    dans l'autre — du HTML invalide, que chaque navigateur repare a sa
    facon.

    La regle appliquee est celle que le moteur suit deja quand une ancre
    enjambe deux elements : deux `<mark>` plutot qu'une qui traverse. Le
    modele reste coherent d'un bout a l'autre.
    / An idea spanning two cells would leave a tag opened in one and
    closed in the next. Two marks, as across elements.
    """
    cellules = []
    cellule_courante = []
    balises_ouvertes = []
    position = 0

    while position < len(ligne_html):
        if ligne_html[position] == "|":
            # Frontiere : on ferme ce qui est ouvert, du plus interne au
            # plus externe. / Boundary: close what is open, innermost first.
            for nom_de_balise, _attributs in reversed(balises_ouvertes):
                cellule_courante.append(f"</{nom_de_balise}>")
            cellules.append("".join(cellule_courante).strip())
            cellule_courante = []
            # Et on rouvre de l'autre cote, dans l'ordre d'origine.
            # / Reopen on the other side, outermost first.
            for nom_de_balise, attributs in balises_ouvertes:
                cellule_courante.append(f"<{nom_de_balise}{attributs}>")
            position += 1
            continue

        correspondance = MOTIF_BALISE.match(ligne_html, position)
        if correspondance:
            fermante, nom_de_balise, attributs = correspondance.groups()
            if fermante:
                if balises_ouvertes and balises_ouvertes[-1][0] == nom_de_balise:
                    balises_ouvertes.pop()
            else:
                balises_ouvertes.append((nom_de_balise, attributs))
            cellule_courante.append(correspondance.group(0))
            position = correspondance.end()
            continue

        cellule_courante.append(ligne_html[position])
        position += 1

    for nom_de_balise, _attributs in reversed(balises_ouvertes):
        cellule_courante.append(f"</{nom_de_balise}>")
    cellules.append("".join(cellule_courante).strip())

    # Le markdown pipe borde ses lignes : la premiere et la derniere
    # cellule sont vides et ne portent rien.
    # / Pipe markdown borders its rows: first and last cells are empty.
    if cellules and not cellules[0]:
        cellules = cellules[1:]
    if cellules and not cellules[-1]:
        cellules = cellules[:-1]
    return cellules


def convertir_un_tableau_markdown(html_du_tableau):
    """
    Rend un tableau markdown « pipe » en vrai `<table>`.
    / Render a pipe-markdown table as a real <table>.

    LOCALISATION : front/services/rendu_elements.py

    POURQUOI PAS UN `<pre>`

    C'est l'ecart n°6 de l'etalon. Un `<pre>` ne porte ni ligne ni
    colonne : un lecteur d'ecran y lit une bouillie de barres verticales,
    et il ne se replie pas — celui du PDF etalon mesurait 3 162px et
    faisait defiler toute la page horizontalement.

    CE QUE CETTE FONCTION NE FAIT PAS

    Elle ne change pas la GRANULARITE DE L'ANCRAGE. Un tableau reste UN
    `ElementDocument` — 4 471 signes pour le premier du PDF etalon — et
    une idee ancree dessus designe toujours tout le tableau. Le decouper
    par ligne est une decision de modele, laissee au mainteneur.
    / It does not change anchoring granularity: a table is still one
    element, and an idea anchored on it still points at the whole.

    :param html_du_tableau: le texte du tableau, DEJA balise de ses marques
    :return: le HTML d'un `<table>`, ou le texte tel quel s'il n'en est pas un
    """
    lignes = [
        ligne for ligne in html_du_tableau.split("\n") if ligne.strip()
    ]
    lignes_de_donnees = [
        ligne for ligne in lignes
        if not MOTIF_LIGNE_DE_SEPARATION.match(ligne)
    ]

    # Un label `table` sur un contenu qui n'en est pas un : mieux vaut
    # rendre le texte qu'une table vide.
    # / A `table` label on non-table content: the text beats an empty table.
    if not lignes_de_donnees or "|" not in html_du_tableau:
        return html_du_tableau

    morceaux = ["<table>"]
    for rang, ligne in enumerate(lignes_de_donnees):
        cellules = _decouper_en_cellules_en_refermant_les_marques(ligne)
        if rang == 0:
            morceaux.append("<thead><tr>")
            morceaux.extend(f"<th>{cellule}</th>" for cellule in cellules)
            morceaux.append("</tr></thead><tbody>")
        else:
            morceaux.append("<tr>")
            morceaux.extend(f"<td>{cellule}</td>" for cellule in cellules)
            morceaux.append("</tr>")
    morceaux.append("</tbody></table>")
    return "".join(morceaux)


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


def _minutage_lisible(debut_en_secondes):
    """
    Rend un debut de tour de parole sous la forme « 12:05 ».
    / Renders a turn's start as "12:05".

    LOCALISATION : front/services/rendu_elements.py

    L'etalon affiche un minutage court a cote du locuteur. Au-dela de
    l'heure il en faut trois morceaux, sinon deux : « 1:04:12 » ou
    « 04:12 » — jamais « 64:12 », qu'on lirait de travers.
    / Three parts past the hour, two below; never "64:12".
    """
    if debut_en_secondes is None:
        return None
    try:
        total = int(float(debut_en_secondes))
    except (TypeError, ValueError):
        return None
    if total < 0:
        return None

    heures, reste = divmod(total, 3600)
    minutes, secondes = divmod(reste, 60)
    if heures:
        return f"{heures}:{minutes:02d}:{secondes:02d}"
    return f"{minutes:02d}:{secondes:02d}"


def _nombre_de_marques_prevu(segments):
    """
    Combien de <mark> le surlignage produirait, avant de le construire.
    / How many <mark> the highlighting would produce, before building it.

    LOCALISATION : front/services/rendu_elements.py
    """
    return sum(
        min(len(portions_couvrantes), MAXIMUM_D_IDEES_SUPERPOSEES)
        for _debut, _fin, portions_couvrantes in segments
    )


def le_surlignage_depasse_le_plafond(element, portions, segments=None):
    """
    Dit si cet element renoncera au surlignage faute de place.
    / Says whether this element will give up highlighting.

    LOCALISATION : front/services/rendu_elements.py

    :param element: l'ElementDocument a rendre
    :param portions: ses portions non detachees
    :param segments: les segments deja calcules, si l'appelant les a
    :return: True si le texte sera rendu nu

    PASSER LES SEGMENTS QUAND ON LES A DEJA

    `construire_les_segments` coute O(segments x portions). Sur
    l'element pathologique que ce plafond existe pour contenir — 2 469
    portions, 4 876 segments — chaque recalcul se compte en millions
    d'iterations. Le laisser recalculer ici puis dans le rendu puis dans
    la construction des blocs triplerait ce cout, precisement sur les
    pages les plus lourdes.
    / Recomputing would triple the cost on the very pages this cap exists
    to protect.

    POURQUOI L'APPELANT DOIT POUVOIR LE DEMANDER

    Renoncer au surlignage est defendable ; le faire SANS LE DIRE ne
    l'est pas. Constate au navigateur apres la reconversion du 10 aout :
    la page 419 porte 623 ancres et n'affichait pas une seule marque, ni
    le moindre message — le lecteur n'avait aucun moyen de savoir que ces
    idees existaient. Le bloc a besoin de la reponse pour l'annoncer.
    / Giving up is defensible; doing it silently is not.
    """
    if segments is None:
        segments = construire_les_segments(
            len(element.texte or ""), portions,
        )
    if not segments:
        return False
    return (
        _nombre_de_marques_prevu(segments) > MAXIMUM_DE_MARQUES_PAR_ELEMENT
    )


def rendre_le_texte_d_un_element(element, portions, segments=None):
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
    if segments is None:
        segments = construire_les_segments(len(texte), portions)

    if not segments:
        return mark_safe("")

    nombre_de_marques_prevu = _nombre_de_marques_prevu(segments)
    if le_surlignage_depasse_le_plafond(element, portions, segments):
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

    # LE MEDIA COMMANDE LA GOUTTIERE.
    #
    # L'etalon n'a pas une gouttiere mais trois : 46px pour un document
    # ecrit, 96px pour un AUDIO — dont la glissiere porte le locuteur et
    # le minutage —, et le label y vaut « utterance » quel que soit
    # l'element (l. 73-78 et 1567-1580).
    # / The mock has three gutters; the medium decides which.
    media = page.source_type or "file"
    c_est_un_audio = media == "audio"

    # UNE COULEUR PAR LOCUTEUR, ATTRIBUEE PAR ORDRE D'APPARITION.
    #
    # Suivre un debat, c'est suivre qui parle : la pastille ne sert que
    # si elle reste LA MEME d'un bout a l'autre pour une meme voix.
    #
    # Par ordre d'apparition, et non par hachage du nom : deux noms
    # quelconques peuvent hacher vers des teintes voisines, alors que
    # l'ordre garantit des couleurs franchement distinctes entre les
    # locuteurs d'un MEME enregistrement — la seule comparaison qu'un
    # lecteur fasse jamais.
    #
    # Palette de WONG, celle des categories du corpus : huit couleurs
    # distinguables par les daltoniens. Celle de l'etalon met un rouge
    # et un vert cote a cote. Et la couleur ne porte jamais seule : le
    # NOM du locuteur est ecrit a cote.
    # / By order of appearance, not by hash; Wong, not the mock's
    # red-next-to-green; and the name is always written.
    couleur_par_locuteur = {}
    if c_est_un_audio:
        from core.models import CategorieDossier

        palette = CategorieDossier.PALETTE_WONG
        for element in elements:
            locuteur = (element.provenance or {}).get("locuteur")
            if locuteur and locuteur not in couleur_par_locuteur:
                couleur_par_locuteur[locuteur] = palette[
                    len(couleur_par_locuteur) % len(palette)
                ]

    portions = (
        AncrageExtraction.objects
        .filter(element__page=page, extraction__masquee=False)
        .exclude(etat_ancrage=EtatAncrage.DETACHEE)
        .select_related("extraction")
        # « Cette idee porte-t-elle un commentaire ? » est demandee DANS
        # la requete des portions : une question de plus, pas une
        # requete de plus. Le rendu tient en deux requetes, quel que
        # soit le nombre d'elements — l'invariant que ce service s'est
        # donne des l'origine.
        # / Asked inside the existing query: still two queries total.
        .annotate(
            idee_commentee=Exists(
                CommentaireExtraction.objects.filter(
                    entity_id=OuterRef("extraction_id"),
                ),
            ),
        )
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

        # « Debattu » au sens de l'etalon (`data-etat="debattu"`, filet
        # d'etat colore) : au moins une idee de ce passage porte un
        # commentaire humain.
        # / "Debated" per the mock: at least one idea here is commented.
        # `ExtractedEntity.statut_debat` est cense repondre a cette
        # question — c'est un champ DERIVE, pose par un signal. En base,
        # il ment : 878 extractions commentees portent un statut herite
        # d'avant A.8 (`discute`, `consensuel`...), 22 seulement disent
        # « commente ». Un critere fonde sur lui passe tous les tests
        # (le signal y tourne) et n'allume RIEN en production.
        # / The derived status lies on 878 rows; ask the comments.
        est_debattu = any(
            portion.idee_commentee for portion in portions_de_l_element
        )

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

        # Les segments servent au rendu ET a la question « ce bloc
        # renonce-t-il au surlignage ? ». Un seul calcul pour les deux.
        # / One computation, two uses.
        segments_de_l_element = construire_les_segments(
            len(element.texte or ""), portions_de_l_element,
        )

        balise_du_bloc = BALISE_PAR_LABEL.get(element.label, BALISE_PAR_DEFAUT)
        html_du_texte = rendre_le_texte_d_un_element(
            element, portions_de_l_element, segments_de_l_element,
        )

        # LA CONVERSION VIENT APRES LE BALISAGE, jamais avant. Les
        # positions d'ancrage sont comptees sur le TEXTE de l'element ;
        # convertir d'abord y injecterait des balises de tableau et
        # decalerait chaque offset. On pose donc les marques sur le texte
        # tel qu'il est, puis on decoupe le HTML obtenu en cellules — en
        # refermant les marques a chaque frontiere.
        # / Conversion comes AFTER marking: offsets are counted on the
        # element's text, so converting first would shift every one.
        if balise_du_bloc == "table":
            html_du_texte = mark_safe(
                convertir_un_tableau_markdown(str(html_du_texte))
            )

        blocs.append({
            "element": element,
            "balise": balise_du_bloc,
            "html_du_texte": html_du_texte,
            "nombre_d_idees": len(identifiants_des_idees),
            # Ce que la GOUTTIERE de l'etalon affiche a cote du bloc.
            # Le numero part de 1 : c'est un repere pour un humain, pas
            # un index. L'empreinte et le label ne se montrent qu'en
            # mode structure ; le compteur d'idees, lui, se voit en
            # lecture. / What the mock's gutter shows beside the block.
            "numero": indice + 1,
            "est_debattu": est_debattu,
            "empreinte_courte": (element.empreinte_contenu or "")[:8],
            # Le numero de page du document source, quand il existe.
            # L'etalon l'affiche dans la gouttiere et masque tout le
            # groupe sans lui (`body[data-docling="non"]`). Une
            # provenance AUDIO ({debut, fin}) n'a pas de page : on rend
            # None plutot que d'ecrire « p. None ».
            # / The source page number, when there is one.
            "numero_de_page": (element.provenance or {}).get("page_no"),
            "media": media,
            # Sur un audio, chaque element est un TOUR DE PAROLE (mesure
            # D3) : l'etalon l'etiquette « utterance » sans regarder le
            # label Docling, qui n'a pas de sens ici.
            # / On audio every element is an utterance.
            "label_affiche": "utterance" if c_est_un_audio else element.label,
            # Ce que la gouttiere d'un AUDIO porte en plus : qui parle,
            # et a quel moment. L'ingestion audio les range dans la
            # provenance, la ou un PDF met sa page et ses boites.
            # / What an audio gutter adds: who speaks, and when.
            "locuteur": (
                (element.provenance or {}).get("locuteur")
                if c_est_un_audio else None
            ),
            "couleur_du_locuteur": couleur_par_locuteur.get(
                (element.provenance or {}).get("locuteur"),
            ),
            "minutage": (
                _minutage_lisible((element.provenance or {}).get("debut"))
                if c_est_un_audio else None
            ),
            # LES MEMES BORNES, BRUTES, POUR LE LECTEUR (ecart n°2).
            #
            # Le minutage ci-dessus est formate parce que la gouttiere
            # l'AFFICHE. Le lecteur, lui, CALCULE avec : la largeur d'un
            # segment de rail vaut `(fin - debut) / duree`, et le tour
            # courant se trouve en comparant l'instant de lecture aux
            # bornes. Reparser « 00:00 » perdrait les decimales — les
            # tours de la note 8 durent 0,4 seconde.
            #
            # None hors audio, et NON 0 : un `debut` a 0 sur un PDF se
            # lirait comme « commence a la seconde zero ».
            # / The formatted timing is for the eye, these are for the
            # maths. None off-audio, never 0.
            "debut": (
                (element.provenance or {}).get("debut")
                if c_est_un_audio else None
            ),
            "fin": (
                (element.provenance or {}).get("fin")
                if c_est_un_audio else None
            ),
            # Combien d'idees ce bloc porte sans pouvoir les montrer.
            # Zero dans l'immense majorite des cas ; le bloc n'en parle
            # que lorsqu'il y renonce vraiment.
            # / How many ideas this block carries without showing them.
            "idees_non_surlignees": (
                len(identifiants_des_idees)
                if le_surlignage_depasse_le_plafond(
                    element, portions_de_l_element, segments_de_l_element,
                )
                else 0
            ),
            "est_masque": element.masque,
            "fusion_possible": fusion_possible,
        })

    # PAS DE REGROUPEMENT DES PUCES.
    #
    # Les `list_item` consecutifs etaient rassembles dans un seul <ul>,
    # hors de la structure `.bloc` : ces passages n'avaient ni
    # gouttiere, ni filet d'etat, ni compteur d'idees, et une idee
    # ancree sur une puce devenait introuvable depuis la gouttiere.
    #
    # L'etalon resout autrement (maquette.html l. 1449) : chaque puce
    # est un bloc a part entiere dont le corps est un <ul> d'un seul
    # <li>. Le HTML reste valide et la puce garde son reperage.
    # / The mock wraps each bullet in its own one-item list.
    return blocs


