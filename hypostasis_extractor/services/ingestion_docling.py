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
import re
from functools import lru_cache

from django.db import transaction

from core.models import ElementDocument, empreinte_du_texte

logger = logging.getLogger(__name__)

# Les labels Docling qui ne portent pas de contenu a analyser.
# Un pied de page repete a chaque page n'a pas a etre extrait, ni a
# recevoir des commentaires.
# / Docling labels that carry no analysable content.
LABELS_SANS_CONTENU_UTILE = {
    # Mise en page d'un document imprime : ce qui se repete a chaque
    # page. / Print layout furniture, repeated on every page.
    "page_header",
    "page_footer",
    "footnote",
    # Chrome d'interface d'une page web. Ces labels-la n'existaient pas
    # dans ce filtre tant qu'il ne servait qu'aux PDF, et la capture web
    # les laissait passer : la page Wikipedia du 21 aout 2026 produisait
    # 13 `checkbox_unselected` — les cases de repli de son sommaire.
    # Treize elements a commenter, a ancrer, et a compter dans la
    # couverture, pour des cases a cocher.
    # / Web UI chrome: these were absent while the filter served PDFs
    # only, so web captures let them through — 13 checkboxes from one
    # collapsible table of contents.
    "checkbox_selected",
    "checkbox_unselected",
    "form",
    "field_heading",
    "field_hint",
    "field_item",
    "field_key",
    "field_region",
    "field_value",
    "key_value_region",
    "document_index",
    "empty_value",
    "marker",
}

# En dessous de ce nombre de caracteres de texte, on ne croit pas que
# Readability ait trouve un article.
# / Below this many characters of text, we do not believe Readability
# found an article.
#
# LE PLANCHER EXISTE POUR NE PAS REMPLACER DU BRUIT PAR DU VIDE.
# Readability est fait pour les ARTICLES. Sur une page d'accueil, un
# forum ou une page de resultats, il rend trois lignes de menu. Ingerer
# ca donnerait une note vide la ou la page brute, elle, portait quelque
# chose — l'utilisateur aurait capture pour rien, sans le savoir.
# / Readability targets ARTICLES; on a home page it returns three lines
# of menu, and ingesting that would give an empty note.
#
# La valeur est un ordre de grandeur assume, pas une mesure : un article
# de moins de deux cents caracteres n'existe pas, une page de navigation
# en fait rarement plus.
# / An assumed order of magnitude, not a measurement.
MINIMUM_DE_TEXTE_LISIBLE = 200


def source_html_d_une_capture(page):
    """
    Choisit le HTML d'une capture web qui part chez Docling.
    / Picks which of a web capture's HTML goes to Docling.

    LOCALISATION : hypostasis_extractor/services/ingestion_docling.py

    L'ARTICLE PROPRE D'ABORD, LA PAGE BRUTE EN SECOURS. L'extension
    fait tourner Readability dans l'onglet et range son resultat dans
    `html_readability` ; `html_original` porte la page ENTIERE, menus,
    bandeaux et pieds de page compris. Ingerer la seconde donnait un
    document dont un tiers etait de la navigation.
    / Clean article first, raw page as backup.

    Mesure du 21 aout 2026, meme pipeline, deux entrees :

    | page        | brut -> elements | propre -> elements | conversion |
    |-------------|------------------|--------------------|------------|
    | Wikipedia   | 248              | 108                | 6,8 s -> 0,2 s |
    | Monde diplo | 150              |  26                | 0,4 s -> 0,1 s |

    `html_original` N'EST PAS TOUCHE et ne doit pas l'etre : c'est
    l'archive immuable de ce qui a ete capture, et c'est elle qui rendra
    possible une re-ingestion le jour ou cette recette s'ameliore.
    / html_original stays untouched: it is the immutable archive that
    makes a future re-ingestion possible.

    :param page: la Page capturee
    :return: le couple (html, origine) ou origine vaut
        "html_readability", "html_original" ou "aucune"
    """
    from front.services.texte_depuis_html import extraire_texte_depuis_html

    article_propre = (page.html_readability or "").strip()
    page_brute = (page.html_original or "").strip()

    if article_propre:
        texte_lisible = extraire_texte_depuis_html(article_propre)
        if len(texte_lisible) >= MINIMUM_DE_TEXTE_LISIBLE:
            return article_propre, "html_readability"
        logger.info(
            "Capture %s : article propre trop court (%s caracteres de "
            "texte, minimum %s) — on repart de la page brute.",
            page.pk, len(texte_lisible), MINIMUM_DE_TEXTE_LISIBLE,
        )

    if page_brute:
        return page_brute, "html_original"

    return "", "aucune"

# Les labels qu'on accepte de RECOLLER quand ils se suivent dans un meme
# groupe inline de Docling — c'est-a-dire quand ils sont les morceaux
# d'une seule et meme phrase, coupee par une balise de mise en forme.
#
# `text` couvre le gras et l'italique ; `code` couvre les backticks
# simples. Un titre, une puce ou un tableau n'y figurent PAS : ce sont
# des structures, pas de la mise en forme, et les recoller effacerait
# une frontiere que l'auteur a posee.
# / Labels we accept to rejoin inside one Docling inline group: the
# pieces of a single sentence split by formatting. Headings, list items
# and tables are structure, never formatting.
LABELS_RECOLLABLES_EN_LIGNE = {"text", "code"}

# Les extensions que Docling sait convertir en structure (BR-B).
# Le .json de transcription n'y est pas : il a son propre pipeline dans
# la vue d'import, qui sait ce qu'est un tour de parole.
# / Extensions Docling can convert into structure. Transcription JSON
# has its own pipeline, which knows what a speaking turn is.
#
# LE `.txt` EN FAIT PARTIE, ET CE COMMENTAIRE A DIT LE CONTRAIRE.
# Il affirmait que « le texte brut n'a pas de structure a decouper » et
# le laissait sur l'ancien pipeline. Mesure du 21 aout 2026 : Docling
# avale un `.txt` et rend exactement les memes elements que le `.md`
# equivalent — les lignes vides separent les paragraphes, les tirets
# font des puces. Une note `.txt` avait donc ZERO element : lisible,
# mais impossible a analyser (`analyse_par_element` sort aussitot sur
# « aucun element a analyser »), a ancrer ou a citer. Une note morte.
# / The .txt claim was false: Docling yields the same elements as the
# equivalent .md. Text notes had zero elements — readable, but
# impossible to analyse, anchor or cite.
EXTENSIONS_COUVERTES_PAR_DOCLING = {
    ".pdf",
    ".docx",
    ".md",
    ".txt",
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


@lru_cache(maxsize=1)
def _convertisseur_docling():
    """
    Rend LE convertisseur Docling de ce process, construit au besoin.
    / Returns THIS process's Docling converter, built on demand.

    LOCALISATION : hypostasis_extractor/services/ingestion_docling.py

    CE QU'ON MUTUALISE N'EST PAS CE QU'ON CROIT

    `DocumentConverter()` lui-meme est bon marche : son `__init__` ne
    charge aucun modele, il construit une trentaine d'objets d'options
    et un dictionnaire `initialized_pipelines` VIDE. Ce qui coute cher,
    c'est le PIPELINE, bati paresseusement au premier `convert()` et
    range dans ce dictionnaire — un attribut d'INSTANCE. Jeter le
    convertisseur jetait donc le cache de pipelines avec lui, et le
    suivant repayait tout.
    / The converter's __init__ is cheap; the pipeline is not, and it
    lives in a per-INSTANCE dict. Dropping the converter dropped the
    pipeline cache with it.

    C'est donc le cache de pipelines qu'on partage. Mesure du 14 aout
    2026, six conversions du meme PDF dans un process : 9,87 s de
    moyenne (converter neuf) contre 6,70 s (converter partage), RSS
    final 2424 Mo contre 2132 Mo, pic 2928 Mo contre 2288 Mo. Le gain
    depend du format : il est plus net sur les pipelines legers
    (HTML, markdown) que sur un PDF, dont la conversion elle-meme pese.
    / What we share is the pipeline cache. Gain varies by format.

    POURQUOI C'EST SUR AVEC LE POOL PREFORK DE CELERY

    Celery duplique le process du worker au demarrage. Un pipeline
    construit dans le PARENT serait herite par tous les enfants — et le
    pipeline PDF ouvre onnxruntime (RapidOCR) et des pools OpenMP :
    forker un process qui porte des threads vivants de ces
    bibliotheques est un blocage classique, bien plus concret qu'une
    question de copie-sur-ecriture.

    La memoisation est donc PARESSEUSE : rien n'est construit au
    chargement du module, et le fork a lieu bien avant la premiere
    tache. Chaque enfant batit ensuite le sien, dans son propre espace
    memoire. Un test verrouille cet invariant en reproduisant le
    bootstrap complet de Celery, autodiscover compris
    (test_le_bootstrap_celery_n_importe_jamais_docling).
    / Lazy on purpose: the PDF pipeline holds onnxruntime and OpenMP
    threads, and forking a process that carries those is a classic
    hang — nothing exists before the fork, so nothing is inherited.

    UN SEUL APPELANT PAR PROCESS

    `lru_cache` protege son dictionnaire, PAS l'execution de la
    fonction : deux appelants concurrents manqueraient tous deux le
    cache et batiraient chacun un convertisseur. Sans consequence
    aujourd'hui — toutes les conversions passent par des taches Celery
    (`.delay()`), une par process a la fois — mais un appel depuis un
    thread de requete ferait cohabiter deux pipelines de ~2 Go. Docling
    ne promet d'ailleurs pas la conversion concurrente sur une meme
    instance : son propre parallelisme est desactive par defaut, avec
    la mention « Experimental ».
    / lru_cache guards its dict, not the call: concurrent callers would
    each build one. Today every conversion comes from a Celery task.

    `lru_cache` plutot qu'une variable de module : il apporte
    `.cache_clear()`, dont les tests ont besoin pour repartir d'un cache
    froid — sans quoi un convertisseur oublie par un test rendrait muets
    les patches des suivants.
    / lru_cache for the free .cache_clear() the tests need.

    L'import de Docling reste DANS le corps, et pas en tete de fichier :
    il charge des modeles lourds, et le faire au demarrage de Django
    ralentirait chaque commande, y compris celles qui n'ingerent rien.
    / Import stays inside: it loads heavy models.
    """
    from docling.document_converter import DocumentConverter

    return DocumentConverter()


def convertir_un_fichier_avec_docling(chemin_du_fichier):
    """
    Passe un fichier a Docling et rend son document structure.
    / Runs a file through Docling and returns its structured document.

    LOCALISATION : hypostasis_extractor/services/ingestion_docling.py

    :param chemin_du_fichier: chemin du fichier a convertir
    :return: le DoclingDocument
    :raises RuntimeError: si la conversion echoue

    Le convertisseur est celui du process, partage avec la capture web
    (voir `_convertisseur_docling`). / Shared, process-wide converter.
    """
    convertisseur = _convertisseur_docling()
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

    Le convertisseur est celui du process, partage avec la conversion de
    fichier (voir `_convertisseur_docling`) : un DocumentConverter sait
    traiter tous les formats, en poser un par porte d'entree ne
    servirait qu'a payer deux fois la construction.
    / Shared with file conversion: one converter handles every format.
    """
    import io

    from docling.datamodel.base_models import DocumentStream

    flux = DocumentStream(
        name=nom_source,
        stream=io.BytesIO((html or "").encode("utf-8")),
    )
    convertisseur = _convertisseur_docling()
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

        texte = recoller_la_ponctuation_detachee(
            _texte_de_l_element(element_docling, document_docling),
        )
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

        # NI UN GRAS NI UN `code` NE COUPENT UNE PHRASE.
        #
        # Docling range les fragments d'une meme ligne dans un GROUPE
        # INLINE : un `<strong>` au milieu d'un paragraphe produit deux
        # items `text` de meme parent. Les garder separes couperait une
        # idee ancree sur cette phrase en deux portions sans raison, et
        # la gouttiere annoncerait deux passages la ou l'auteur en a
        # ecrit un. On recolle DANS un groupe, jamais entre deux — et
        # jamais un titre ni une puce, qui sont de la structure, pas de
        # la mise en forme.
        #
        # LE `code` INLINE COMPTE PARMI CES FRAGMENTS, et c'est ce qui
        # manquait : un backtick au milieu d'une phrase ne produit pas un
        # item `text` mais un item de label `code`, que la condition
        # `label == "text"` laissait passer. Chaque nom de fichier cite
        # devenait donc un BLOC a lui seul — `BALISE_PAR_LABEL["code"]`
        # vaut `pre` (front/services/rendu_elements.py) — et une phrase
        # de trois citations se lisait en six blocs empiles, chacun avec
        # sa gouttiere et son numero. Mesure du 15 aout sur la note
        # « Presentation Hypostasia V3 » : une phrase etalee sur trois
        # ecrans.
        #
        # DOCLING PORTE LUI-MEME LA DISTINCTION, il n'y a rien a deviner :
        # un `code` inline a pour parent un groupe `inline`, un VRAI bloc
        # de code (triples backticks) a pour parent `#/body` et n'a donc
        # aucun groupe. Aucune heuristique de longueur n'est necessaire.
        # / Inline groups are formatting; rejoin them, never lists. An
        # inline `code` is one of those fragments — Docling itself tells
        # it apart from a real code block by its parent group.
        groupe = _groupe_inline_de_l_element(element_docling, document_docling)
        if (
            groupe is not None
            and label in LABELS_RECOLLABLES_EN_LIGNE
            and elements_bruts
            and elements_bruts[-1].get("_groupe_inline") == groupe
            # Le precedent doit etre recollable lui aussi : un titre porte
            # la meme marque de groupe que le paragraphe qui le suit, et
            # sans cette condition le texte se recollait DANS le titre.
            # / A heading shares the group mark; never merge into it.
            and elements_bruts[-1].get("label") in LABELS_RECOLLABLES_EN_LIGNE
        ):
            elements_bruts[-1]["texte"] = (
                elements_bruts[-1]["texte"].rstrip() + " " + texte.lstrip()
            )
            # LE RESULTAT EST DU TEXTE, meme si le fragment d'ouverture
            # etait du code : une phrase qui COMMENCE par un nom de
            # fichier (« `Page` porte le titre… ») garderait sinon le
            # label `code`, et la phrase entiere partirait en `<pre>`.
            # / The merged result is prose, even when it opens on code.
            elements_bruts[-1]["label"] = "text"
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


# Le point et la virgule, et EUX SEULS. En francais, l'espace avant
# « ? », « ! », « ; » et « : » est correcte : la recoller serait une
# faute de typographie, pas une reparation.
# / Period and comma ONLY: French keeps a space before ? ! ; :
MOTIF_DE_PONCTUATION_DETACHEE = re.compile(r"([\w)\]»%°])[ \t]+([.,])")


def recoller_la_ponctuation_detachee(texte):
    """
    Recolle au mot precedent un point ou une virgule que Docling en a
    separes. / Re-attaches a period or comma Docling detached.

    LOCALISATION : hypostasis_extractor/services/ingestion_docling.py

    POURQUOI CE NETTOYAGE EXISTE. Docling rend regulierement
    « d'un territoire . » ou « par IMS Global , un consortium », la ou
    le fichier d'origine est propre. Un modele qui cite ce passage
    recolle spontanement la ponctuation, comme le ferait un humain — et
    sa citation ne se retrouve alors plus dans la source. Le controle
    verbatim echoue, le lien part en INTROUVABLE, et la chaine de preuve
    est declaree cassee pour un espace que nous avons introduit.

    DEUX GARDES, ET AUCUNE N'EST DECORATIVE :

    1. seuls le POINT et la VIRGULE sont recolles. L'espace avant
       « ? », « ! », « ; » et « : » est la typographie francaise
       normale ;
    2. jamais ENTRE DEUX CHIFFRES : « les niveaux 3 , 5 et 8 » recolle
       donnerait « 3,5 », un decimal que le document n'avance nulle
       part. Vaut pour les dates, les montants, les versions.

    Le motif ne franchit pas non plus de saut de ligne : une ponctuation
    en tete de ligne appartient a la mise en forme — une puce, une
    numerotation — et la recoller souderait deux blocs distincts.

    ET IL N'AGIT QU'APRES UN CARACTERE DE MOT OU UN FERMANT. Coller
    apres n'importe quel non-espace abime la typographie dans l'autre
    sens : dans un tableau, « | « ...avec des chutes » deviendrait
    « | «...avec des chutes », alors que l'espace apres un guillemet
    OUVRANT est correcte. Mesure sur le corpus : 10 recollages fautifs
    de cette famille (guillemets ouvrants de tableaux, chemins de
    fichiers « /carnets/ , /bases/ ») contre ~96 legitimes.
    / It only fires after a word character or a closing mark: gluing
      after any non-space breaks tables and opening quotes.

    CE NETTOYAGE NE TOUCHE QUE LES DOCUMENTS INGERES APRES LUI. Les
    elements deja en base gardent leur texte : le corriger decalerait
    les ancres des extractions, qui portent des positions absolues.
    / Only affects newly ingested documents: rewriting stored text would
    shift the extractions' absolute anchors.
    """
    def recoller(correspondance):
        caractere_precedent, ponctuation = correspondance.groups()
        suite = correspondance.string[correspondance.end():]
        caractere_suivant = suite[:1]
        if caractere_precedent.isdigit() and caractere_suivant.isdigit():
            return correspondance.group(0)
        return caractere_precedent + ponctuation

    return MOTIF_DE_PONCTUATION_DETACHEE.sub(recoller, texte)


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
    elements = creer_les_elements_d_une_page(page, elements_bruts)
    adopter_le_titre_du_document(page, elements_bruts)
    return elements


def adopter_le_titre_du_document(page, elements_bruts):
    """
    Donne a la note le titre lu DANS le document, si elle porte encore
    celui de son fichier.
    / Gives the note the title read INSIDE the document, if it still
    carries its file name.

    LOCALISATION : hypostasis_extractor/services/ingestion_docling.py

    UN TITRE LU DANS LE DOCUMENT VAUT MIEUX QU'UN NOM DE FICHIER. La vue
    d'import n'a que le nom du fichier au moment ou elle cree la note —
    `presentation des open badges.pdf` donne « presentation des open
    badges ». Docling, lui, reconnait le titre du document et le range
    sous le label `title`.
    / A title read inside the document beats a file name.

    ELLE NE TOUCHE PAS A UN TITRE CHOISI PAR QUELQU'UN. Le formulaire
    d'import accepte un titre ; s'il differe du nom du fichier, c'est
    qu'un humain l'a ecrit, et rien ne l'ecrase.
    / It never overwrites a title a human typed.

    :param page: la Page ingeree
    :param elements_bruts: les elements rendus par extraire_les_elements_bruts
    :return: True si le titre a ete remplace
    """
    import os

    from core.models import Page

    if not page.original_filename:
        return False

    titre_par_defaut = os.path.splitext(page.original_filename)[0]
    if (page.title or "").strip() != titre_par_defaut.strip():
        return False

    titre_du_document = next(
        (
            element["texte"].strip()
            for element in elements_bruts
            if element.get("label") == "title" and element.get("texte", "").strip()
        ),
        "",
    )
    if not titre_du_document:
        return False

    # `Page.title` est borne a 500 caracteres : un « titre » reconnu sur
    # un document mal structure peut etre un paragraphe entier.
    # / Page.title is capped at 500 characters.
    titre_du_document = titre_du_document[:500]

    Page.objects.filter(pk=page.pk).update(title=titre_du_document)
    page.title = titre_du_document
    logger.info(
        "Page %s : titre repris du document — %r", page.pk, titre_du_document,
    )
    return True


def ingerer_une_capture_web(page):
    """
    Enchaine conversion Docling du HTML capture et creation des elements.
    / Chains Docling HTML conversion and element creation.

    LOCALISATION : hypostasis_extractor/services/ingestion_docling.py

    U4 : la source n'est pas un fichier mais le HTML capture par
    l'extension. LEQUEL des deux HTML part chez Docling est decide par
    `source_html_d_une_capture` : l'article rendu par Readability quand
    il est credible, la page brute sinon.
    / The source is captured HTML; which one is decided by
    source_html_d_une_capture.

    :param page: la Page a peupler
    :return: la liste des ElementDocument crees
    :raises ValueError: si la page n'a pas de HTML a decouper
    """
    html, origine = source_html_d_une_capture(page)
    if not html:
        raise ValueError(
            f"La page {page.pk} n'a pas de HTML original a decouper."
        )
    logger.info(
        "Capture %s : decoupage depuis %s (%s caracteres de HTML).",
        page.pk, origine, len(html),
    )
    document_docling = convertir_du_html_avec_docling(html)
    elements_bruts = extraire_les_elements_bruts(document_docling)
    return creer_les_elements_d_une_page(page, elements_bruts)
