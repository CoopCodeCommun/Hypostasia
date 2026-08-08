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
        resultat = convertisseur.convert(chemin_du_fichier)
    except Exception as erreur:
        raise RuntimeError(
            f"Docling n'a pas pu convertir {chemin_du_fichier} : {erreur}"
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

        elements_bruts.append({
            "texte": texte,
            "label": label,
            "reference_docling": str(
                getattr(element_docling, "self_ref", "") or ""
            ),
            "chemin_de_section": list(pile_des_titres),
            "provenance": _provenance_de_l_element(element_docling),
        })

    logger.info(
        "Docling : %s element(s) retenu(s) sur le document.",
        len(elements_bruts),
    )
    return elements_bruts


def _texte_de_l_element(element_docling, document_docling):
    """
    Rend le texte d'un element Docling, tableaux compris.
    / Returns a Docling element's text, tables included.
    """
    texte = getattr(element_docling, "text", "") or ""
    if texte.strip():
        return texte

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
            "coord_origin": str(getattr(boite, "coord_origin", "") or ""),
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
