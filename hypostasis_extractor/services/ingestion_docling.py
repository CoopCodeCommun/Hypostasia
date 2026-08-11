"""
Convertit un document en ElementDocument, via Docling.
/ Converts a document into ElementDocument, via Docling.

LOCALISATION : hypostasis_extractor/services/ingestion_docling.py

Implemente le haut de la section 4 de SPEC-ancrage-par-element-v2.md
(phase D) : fichier source -> DoclingDocument -> N x ElementDocument.

CE QUE DOCLING APPORTE

Il lit un PDF, un fichier Word, un markdown, un HTML, et rend une
structure : des titres, des paragraphes, des items de liste, des
tableaux. Chacun avec son label et, pour un PDF, sa position physique sur
la page.

C'est exactement ce dont l'ancrage par element a besoin : une decoupe du
document qui suit le sens, et pas le nombre de caracteres.
/ Docling returns a structure that follows meaning, not character counts.

CE QU'ON NE GARDE PAS DE DOCLING

Le self_ref ("#/texts/4") est un numero de position. Si le document
change, tous les numeros suivants glissent. On le note pour information,
mais on ne s'en sert JAMAIS comme cle : nos ancres pointent
identifiant_stable, qui ne bouge pas.
/ self_ref is positional and would slide; we never use it as a key.
"""

import logging

from django.db import transaction

from core.models import ElementDocument, empreinte_du_texte

logger = logging.getLogger(__name__)

# Les labels Docling qui ne portent pas de contenu a analyser.
# Un pied de page repete a chaque page n'a pas a etre extrait, ni a
# recevoir des commentaires.
# / Docling labels that carry no analysable content.
LABELS_SANS_CONTENU_UTILE = {
    "page_header",
    "page_footer",
    "footnote",
}

# Les extensions que Docling sait convertir en structure (BR-B).
# Le texte brut (.txt) n'en fait pas partie : il n'a pas de structure a
# decouper, il reste sur l'ancien pipeline. Le .json de transcription a
# son propre pipeline dans la vue d'import.
# / Extensions Docling can convert into structure. Plain text has no
# structure to split; transcription JSON has its own pipeline.
EXTENSIONS_COUVERTES_PAR_DOCLING = {
    ".pdf",
    ".docx",
    ".md",
    ".pptx",
    ".xlsx",
}

# Les gardes-fous de conversion (relecture BR-B) : le serveur a 8 Go,
# partages avec la production. Un PDF-fleuve ou une bombe de
# decompression (un .docx est un zip : la limite d'upload de 50 Mo porte
# sur la taille COMPRESSEE) ne doivent pas pouvoir tout emporter.
# Docling refuse au-dela et la tache finit en erreur propre.
# / Conversion guards: page cap and file-size cap handed to Docling.
LIMITE_DE_PAGES_DOCLING = 200
LIMITE_DE_TAILLE_DOCLING = 50 * 1024 * 1024


def fichier_couvert_par_docling(nom_fichier):
    """
    Dit si un fichier est d'un type que Docling sait convertir.
    / Says whether a file is of a type Docling can convert.

    LOCALISATION : hypostasis_extractor/services/ingestion_docling.py

    Sert a la vue d'import (BR-B) pour decider : type couvert -> lancer
    `ingerer_un_fichier_avec_docling` en plus du pipeline synchrone ;
    type non couvert -> repli sur l'ancien moteur, sans tache.
    / Used by the import view to decide whether to launch ingestion.

    :param nom_fichier: le nom du fichier importe (avec extension)
    :return: True si Docling couvre ce type
    """
    import os

    extension = os.path.splitext(nom_fichier or "")[1].lower()
    return extension in EXTENSIONS_COUVERTES_PAR_DOCLING


def convertir_un_fichier_avec_docling(chemin_du_fichier):
    """
    Passe un fichier a Docling et rend son document structure.
    / Runs a file through Docling and returns its structured document.

    LOCALISATION : hypostasis_extractor/services/ingestion_docling.py

    :param chemin_du_fichier: chemin du fichier a convertir
    :return: le DoclingDocument
    :raises RuntimeError: si la conversion echoue

    L'import de Docling est fait ICI, dans le corps de la fonction, et pas
    en tete de fichier. Docling charge des modeles lourds au premier
    import : le faire au demarrage de Django ralentirait chaque commande,
    y compris celles qui n'ingerent rien.
    / Docling is imported lazily: it loads heavy models on first import.
    """
    from docling.document_converter import DocumentConverter

    convertisseur = DocumentConverter()
    try:
        resultat = convertisseur.convert(
            chemin_du_fichier,
            max_num_pages=LIMITE_DE_PAGES_DOCLING,
            max_file_size=LIMITE_DE_TAILLE_DOCLING,
        )
    except Exception as erreur:
        raise RuntimeError(
            f"Docling n'a pas pu convertir {chemin_du_fichier} : {erreur}"
        ) from erreur

    return resultat.document


def convertir_du_html_avec_docling(html, nom_source="capture-web.html"):
    """
    Passe du HTML (capture web) a Docling et rend son document.
    / Runs HTML (web capture) through Docling and returns its document.

    LOCALISATION : hypostasis_extractor/services/ingestion_docling.py

    U4 (decision D2, ordre 2) : la capture web n'a pas de fichier sur
    disque — elle a son HTML en base (page.html_original). Docling
    convertit un flux nomme en `.html` exactement comme un fichier ; on
    lui passe donc un DocumentStream plutot qu'un chemin. Memes
    gardes-fous de ressources que la conversion de fichier.
    / Web capture has no file on disk, only HTML in the DB; Docling
    converts a named stream just like a file.

    :param html: le HTML a convertir (str)
    :param nom_source: un nom de flux finissant par .html (le backend
        de Docling se choisit sur l'extension)
    :return: le DoclingDocument
    :raises RuntimeError: si la conversion echoue
    """
    import io

    from docling.datamodel.base_models import DocumentStream
    from docling.document_converter import DocumentConverter

    flux = DocumentStream(
        name=nom_source,
        stream=io.BytesIO((html or "").encode("utf-8")),
    )
    convertisseur = DocumentConverter()
    try:
        resultat = convertisseur.convert(
            flux,
            max_num_pages=LIMITE_DE_PAGES_DOCLING,
            max_file_size=LIMITE_DE_TAILLE_DOCLING,
        )
    except Exception as erreur:
        raise RuntimeError(
            f"Docling n'a pas pu convertir le HTML capturé : {erreur}"
        ) from erreur

    return resultat.document


def extraire_les_elements_bruts(document_docling):
    """
    Parcourt un DoclingDocument et rend des elements bruts.
    / Walks a DoclingDocument and returns raw elements.

    LOCALISATION : hypostasis_extractor/services/ingestion_docling.py

    :param document_docling: le document rendu par Docling
    :return: liste de dicts prets pour creer_les_elements_d_une_page()

    LE CHEMIN DE SECTION EST CONSTRUIT AU PASSAGE

    On tient a jour la pile des titres rencontres. Chaque element note les
    titres sous lesquels il se trouve, au moment de l'ingestion. C'est un
    instantane : si un titre est corrige plus tard, les elements ne sont
    pas re-derives. La spec (section 2.1) l'assume explicitement.
    / A snapshot of parent titles, not re-derived later.

    LES TABLEAUX SONT SERIALISES EN TEXTE

    Un tableau n'a pas d'attribut .text : son contenu est dans sa
    structure. On le serialise en markdown, qui reste lisible pour un
    humain comme pour un modele. Sans ca, le tableau arriverait vide et
    tout son contenu serait perdu pour l'analyse.
    / Tables have no .text; we serialize them to markdown or lose them.
    """
    elements_bruts = []
    pile_des_titres = []

    for element_docling, _niveau in document_docling.iterate_items():
        label = str(getattr(element_docling, "label", "") or "text")

        if label in LABELS_SANS_CONTENU_UTILE:
            continue

        texte = _texte_de_l_element(element_docling, document_docling)
        if not texte.strip():
            continue

        # Les titres alimentent le chemin de section des elements suivants.
        # / Titles feed the following elements' section path.
        if label in ("title", "section_header"):
            pile_des_titres = _mettre_a_jour_la_pile_des_titres(
                pile_des_titres, texte, label,
            )

        element_brut = {
            "texte": texte,
            "label": label,
            "reference_docling": str(
                getattr(element_docling, "self_ref", "") or ""
            ),
            "chemin_de_section": list(pile_des_titres),
            "provenance": _provenance_de_l_element(element_docling),
        }

        # UN GRAS NE COUPE PAS UNE PHRASE.
        #
        # Docling range les fragments d'une meme ligne dans un GROUPE
        # INLINE : un `<strong>` au milieu d'un paragraphe produit deux
        # items `text` de meme parent. Les garder separes couperait une
        # idee ancree sur cette phrase en deux portions sans raison, et
        # la gouttiere annoncerait deux passages la ou l'auteur en a
        # ecrit un. On recolle DANS un groupe, jamais entre deux — et
        # jamais un titre ni une puce, qui sont de la structure, pas de
        # la mise en forme.
        # / Inline groups are formatting; rejoin them, never lists.
        groupe = _groupe_inline_de_l_element(element_docling, document_docling)
        if (
            groupe is not None
            and label == "text"
            and elements_bruts
            and elements_bruts[-1].get("_groupe_inline") == groupe
            # Le precedent doit etre du TEXTE lui aussi : un titre porte
            # la meme marque de groupe que le paragraphe qui le suit, et
            # sans cette condition le texte se recollait DANS le titre.
            # / A heading shares the group mark; never merge into it.
            and elements_bruts[-1].get("label") == "text"
        ):
            elements_bruts[-1]["texte"] = (
                elements_bruts[-1]["texte"].rstrip() + " " + texte.lstrip()
            )
            continue

        element_brut["_groupe_inline"] = groupe
        elements_bruts.append(element_brut)

    # La marque de regroupement est un outil de travail, pas une donnee
    # du document : elle ne sort pas d'ici.
    # / The grouping mark is scaffolding; it does not leave this function.
    for element_brut in elements_bruts:
        element_brut.pop("_groupe_inline", None)

    logger.info(
        "Docling : %s element(s) retenu(s) sur le document.",
        len(elements_bruts),
    )
    return elements_bruts


def _groupe_inline_de_l_element(element_docling, document_docling):
    """
    Rend la reference du groupe INLINE d'un element, s'il en a un.
    / Returns the element's inline-group reference, if any.

    LOCALISATION : hypostasis_extractor/services/ingestion_docling.py

    Docling distingue trois sortes de groupes : `inline` (une ligne
    coupee par une balise de mise en forme), `list` (une liste) et
    `section`. Seul le premier est de la MISE EN FORME — les deux
    autres sont de la structure, et leurs elements doivent le rester.
    / Only `inline` is formatting; `list` and `section` are structure.
    """
    parent = getattr(element_docling, "parent", None)
    reference = getattr(parent, "cref", None) if parent is not None else None
    if not reference:
        return None

    # Le document de test expose directement la question ; le vrai
    # document Docling demande de retrouver le groupe par sa reference.
    # / The fake document answers directly; the real one needs a lookup.
    repondre = getattr(document_docling, "groupe_est_inline", None)
    if repondre is not None:
        return reference if repondre(reference) else None

    for groupe in getattr(document_docling, "groups", None) or []:
        if str(getattr(groupe, "self_ref", "")) != reference:
            continue
        label = str(getattr(groupe, "label", "") or "")
        return reference if label.endswith("inline") else None
    return None


def _texte_de_l_element(element_docling, document_docling):
    """
    Rend le texte d'un element Docling, tableaux compris.
    / Returns a Docling element's text, tables included.

    LOCALISATION : hypostasis_extractor/services/ingestion_docling.py

    UNE IMAGE N'EST PAS UN TABLEAU.

    Ni l'une ni l'autre n'a de `.text`, mais seul le tableau gagne a
    etre serialise en markdown. Pour une image, `export_to_markdown`
    rend un message destine au developpeur — « Image not available.
    Please use `PdfPipelineOptions`… » — qui atterrissait tel quel dans
    le document que l'utilisateur lit (constate sur la capture
    `sample/capture-web-badgeons-la-normandie.html`).

    Une image porte donc sa LEGENDE si elle en a une (c'est du texte
    d'auteur, citable), et rien sinon.
    / An image is not a table: its markdown is a developer message.
    """
    texte = getattr(element_docling, "text", "") or ""
    if texte.strip():
        return texte

    if str(getattr(element_docling, "label", "")).endswith("picture"):
        return _legende_de_l_image(element_docling, document_docling)

    # Un tableau n'a pas de .text : on le serialise.
    # / A table has no .text: serialize it.
    exporter_en_markdown = getattr(element_docling, "export_to_markdown", None)
    if exporter_en_markdown is not None:
        try:
            return exporter_en_markdown(doc=document_docling) or ""
        except TypeError:
            # Selon la version de Docling, la signature attend ou non le
            # document. / Signature varies across Docling versions.
            try:
                return exporter_en_markdown() or ""
            except Exception as erreur:
                logger.warning(
                    "Tableau non serialisable, ignore : %s", erreur,
                )
                return ""
        except Exception as erreur:
            logger.warning("Tableau non serialisable, ignore : %s", erreur)
            return ""

    return ""


def _legende_de_l_image(element_docling, document_docling):
    """
    Rend la legende d'une image, ou une chaine vide.
    / Returns an image's caption, or an empty string.

    LOCALISATION : hypostasis_extractor/services/ingestion_docling.py

    Une image sans legende ne donne AUCUN bloc : un bloc qui n'affiche
    rien encombre la lecture et fausse le compte de la gouttiere.
    / No caption, no block.
    """
    for legende in getattr(element_docling, "captions", None) or []:
        resoudre = getattr(legende, "resolve", None)
        objet = legende
        if resoudre is not None:
            try:
                objet = resoudre(document_docling) or legende
            except Exception:  # noqa: BLE001 — une legende n'est pas critique
                objet = legende
        texte = (getattr(objet, "text", "") or "").strip()
        if texte:
            return texte
    return ""


def _mettre_a_jour_la_pile_des_titres(pile_des_titres, texte_du_titre, label):
    """
    Tient a jour la pile des titres parents.
    / Keeps the stack of parent titles up to date.

    Un titre de document (title) remet la pile a zero : c'est le sommet.
    Un sous-titre (section_header) remplace le dernier sous-titre au meme
    niveau. Docling ne donnant pas toujours un niveau fiable, on reste
    simple : un seul niveau de sous-titre a la fois.
    / Kept deliberately simple: one section level at a time.
    """
    if label == "title":
        return [texte_du_titre]

    if pile_des_titres:
        return pile_des_titres[:1] + [texte_du_titre]
    return [texte_du_titre]


def _coord_origin_en_chaine(coord_origin):
    """
    Rend "BOTTOMLEFT", jamais "CoordOrigin.BOTTOMLEFT".
    / Returns "BOTTOMLEFT", never "CoordOrigin.BOTTOMLEFT".

    LOCALISATION : hypostasis_extractor/services/ingestion_docling.py

    `coord_origin` est un membre de l'enumeration CoordOrigin de
    docling-core. str() d'un membre d'enum rend "NomDeClasse.MEMBRE" — le
    prefixe de classe compris — ce qu'un visualiseur PDF ne sait pas
    interpreter : c'est `.value` qu'il faut, pas `str()`. Le systeme de
    coordonnees n'est pas cosmetique : BOTTOMLEFT dit que `t` se mesure
    depuis le bas de la page, et se tromper dessine les surlignages a
    l'envers.
    / `.value` on purpose, never `str()`: str() leaks "ClassName.MEMBER",
    and the origin decides which way highlights get drawn.

    :param coord_origin: un membre d'enum, une chaine deja propre, ou
        absent (None) selon la source Docling.
    """
    if coord_origin is None:
        return ""
    valeur = getattr(coord_origin, "value", coord_origin)
    return str(valeur)


def _provenance_de_l_element(element_docling):
    """
    Rend la provenance physique d'un element : page et boites.
    / Returns an element's physical provenance: page and boxes.

    LOCALISATION : hypostasis_extractor/services/ingestion_docling.py

    Pour un PDF, Docling donne une LISTE de provenances : un paragraphe a
    cheval sur deux colonnes ou deux pages en a plusieurs. On les garde
    toutes, chacune avec son numero de page — sinon le surlignage
    dessinerait les boites de la page 2 sur la page 1.
    / A paragraph spanning two columns has several boxes; each keeps its page.

    Pour un markdown ou un texte brut, il n'y a pas de provenance
    physique : on rend un dictionnaire vide, ce que la spec prevoit.
    / Markdown has no physical provenance: empty dict, as the spec says.
    """
    provenances = getattr(element_docling, "prov", None)
    if not provenances:
        return {}

    boites = []
    numero_de_page_principal = None
    for provenance in provenances:
        numero_de_page = getattr(provenance, "page_no", None)
        if numero_de_page_principal is None:
            numero_de_page_principal = numero_de_page

        boite = getattr(provenance, "bbox", None)
        if boite is None:
            continue

        boites.append({
            "l": getattr(boite, "l", None),
            "t": getattr(boite, "t", None),
            "r": getattr(boite, "r", None),
            "b": getattr(boite, "b", None),
            "coord_origin": _coord_origin_en_chaine(
                getattr(boite, "coord_origin", None),
            ),
            "page_no": numero_de_page,
        })

    if not boites:
        return {}

    return {"page_no": numero_de_page_principal, "boites": boites}


def creer_les_elements_d_une_page(page, elements_bruts):
    """
    Cree les ElementDocument d'une page a partir d'elements bruts.
    / Creates a page's ElementDocument rows from raw elements.

    LOCALISATION : hypostasis_extractor/services/ingestion_docling.py

    :param page: la Page a peupler
    :param elements_bruts: la liste rendue par extraire_les_elements_bruts
    :return: la liste des ElementDocument crees

    CETTE FONCTION NE SERT QU'A LA PREMIERE INGESTION

    Pour un document deja ingere qui a change, il faut passer par
    services/reingestion.py : lui reconnait les elements inchanges par
    leur empreinte et leur garde leurs ancres. Celle-ci part d'une page
    vide.
    / For an already-ingested page, use reingestion.py instead.
    """
    if page.elements.exists():
        raise ValueError(
            f"La page {page.pk} a deja des elements. Utiliser "
            f"services/reingestion.py pour la mettre a jour sans perdre "
            f"les ancres existantes."
        )


    elements_crees = []
    with transaction.atomic():
        for position, element_brut in enumerate(elements_bruts):
            elements_crees.append(ElementDocument.objects.create(
                page=page,
                ordre=position,
                label=element_brut.get("label", "text"),
                texte=element_brut["texte"],
                empreinte_contenu=empreinte_du_texte(element_brut["texte"]),
                reference_docling=element_brut.get("reference_docling", ""),
                chemin_de_section=element_brut.get("chemin_de_section") or [],
                provenance=element_brut.get("provenance") or {},
            ))


    logger.info(
        "Page %s : %s element(s) cree(s) depuis Docling.",
        page.pk, len(elements_crees),
    )

    return elements_crees


def ingerer_un_fichier(page, chemin_du_fichier):
    """
    Enchaine conversion Docling et creation des elements.
    / Chains Docling conversion and element creation.

    LOCALISATION : hypostasis_extractor/services/ingestion_docling.py

    :param page: la Page a peupler
    :param chemin_du_fichier: le fichier source
    :return: la liste des ElementDocument crees
    """
    document_docling = convertir_un_fichier_avec_docling(chemin_du_fichier)
    elements_bruts = extraire_les_elements_bruts(document_docling)
    return creer_les_elements_d_une_page(page, elements_bruts)


def ingerer_une_capture_web(page):
    """
    Enchaine conversion Docling du HTML capture et creation des elements.
    / Chains Docling HTML conversion and element creation.

    LOCALISATION : hypostasis_extractor/services/ingestion_docling.py

    U4 : la source est page.html_original (le HTML brut capture par
    l'extension), pas un fichier. / The source is the captured HTML.

    :param page: la Page a peupler
    :return: la liste des ElementDocument crees
    :raises ValueError: si la page n'a pas de HTML a decouper
    """
    html = page.html_original or ""
    if not html.strip():
        raise ValueError(
            f"La page {page.pk} n'a pas de HTML original a decouper."
        )
    document_docling = convertir_du_html_avec_docling(html)
    elements_bruts = extraire_les_elements_bruts(document_docling)
    return creer_les_elements_d_une_page(page, elements_bruts)
