"""
Transforme un span brut de LangExtract en portions d'ancrage.
/ Turns a raw LangExtract span into anchor portions.

LOCALISATION : hypostasis_extractor/services/ancrage.py

Implemente la section 2.3 de SPEC-ancrage-par-element-v2.md (phase B).

LE PROBLEME QUE CE FICHIER RESOUT

LangExtract nous rend une position dans le texte du CHUNK qu'on lui a envoye.
Un chunk, c'est plusieurs elements colles bout a bout avec un separateur.
Cette position ne veut donc rien dire toute seule : il faut la traduire en
« tel morceau de tel element ».

    chunk envoye au LLM :  "L'IA ne doit pas remplacer :\n\nle jugement"
                            |------- element 12 -------|  |-element 13-|
    span rendu par le LLM :                 (18, 39)
    resultat attendu :  element 12, du caractere 18 au 27
                        element 13, du caractere  0 au  11

Le separateur "\n\n" tombe entre les deux : il n'appartient a aucune portion.
/ The joining separator belongs to no portion.
"""

# Separateur utilise pour coller les elements dans un chunk.
# Doit rester identique a celui du chunking (services/chunking.py).
# / Separator used to join elements in a chunk. Must match chunking.py.
SEPARATEUR_DE_JONCTION = "\n\n"


def decouper_le_span_en_portions_par_element(
    span_dans_le_chunk,
    elements_du_chunk,
    offsets_des_elements_dans_le_chunk,
    decalages_dans_l_element=None,
):
    """
    Decoupe un span de chunk en portions, une par element traverse.
    / Splits a chunk span into portions, one per crossed element.

    LOCALISATION : hypostasis_extractor/services/ancrage.py

    FLUX D'APPEL :
    1. Le chunking (services/chunking.py) construit un chunk et note, pour
       chaque element, ou il commence et ou il finit DANS CE CHUNK.
    2. LangExtract analyse le texte du chunk et rend un span (debut, fin).
    3. CETTE FONCTION croise les deux et rend une liste de portions.
    4. L'appelant cree une ligne AncrageExtraction par portion.

    LES QUATRE CAS TRAITES :

    1. Le span tient dans un seul element -> UNE portion.
    2. Le span traverse plusieurs elements -> UNE portion par element.
       Les separateurs tombent dans les trous entre deux elements et ne
       sont donc jamais inclus.
    3. Le span commence ou finit au milieu d'un separateur -> il est rogne
       aux bornes de l'element le plus proche. C'est l'intersection qui
       s'en charge toute seule, sans traitement special.
    4. Le span tombe ENTIEREMENT dans un separateur -> aucune portion.
       On rend une liste vide : l'appelant doit decider quoi en faire
       (typiquement, ne pas creer d'ancre du tout).

    :param span_dans_le_chunk: (debut, fin) rendu par LangExtract, en
        offsets dans le texte du chunk. Fin exclue.
    :param elements_du_chunk: les ElementDocument du chunk, DANS L'ORDRE DU
        DOCUMENT. C'est cet ordre qui donne ordre_dans_extraction.
    :param offsets_des_elements_dans_le_chunk: {element.pk: (debut, fin)},
        position de chaque element DANS LE CHUNK. Meme table que celle
        utilisee pour construire le chunk, on ne la recalcule pas.
    :param decalages_dans_l_element: {element.pk: decalage}, position DANS
        LE TEXTE COMPLET DE L'ELEMENT du premier caractere present dans le
        chunk. Vaut 0 quand l'element entier tient dans le chunk, ce qui
        est le cas courant. Ne sert que pour un element trop gros, dont le
        chunk ne porte qu'un morceau (voir la note plus bas). Facultatif.
    :return: liste de dicts {element, ordre_dans_extraction,
        debut_dans_element, fin_dans_element}, prete a creer des
        AncrageExtraction.

    POURQUOI decalages_dans_l_element EXISTE (ecart assume avec la spec)

    La section 2.3 de la spec dit qu'un element trop gros peut produire un
    chunk qui n'est qu'une SOUS-CHAINE de cet element, et que la table
    d'offsets porte alors « les bornes de la portion reellement presente
    dans le chunk ». C'est vrai, mais ca ne suffit pas : ces bornes disent
    ou le morceau se trouve DANS LE CHUNK, pas ou il se trouve DANS
    L'ELEMENT. Sans cette seconde information, une portion d'un element
    coupe serait ancree comme si elle commencait au debut de l'element.

    Exemple : un element de 4000 caracteres, dont le chunk ne porte que les
    caracteres 1500 a 2900. Une portion trouvee au debut du chunk doit etre
    ancree a 1500 dans l'element, pas a 0.
    / Without this parameter, portions of a split element would anchor at 0.
    """
    debut_du_span, fin_du_span = span_dans_le_chunk

    # GARDE 1 : un span a l'envers est un bug de l'appelant, pas un cas
    # metier. Sans cette garde, l'intersection rendrait une liste vide,
    # impossible a distinguer du cas legitime « span dans un separateur ».
    # / An inverted span is a caller bug, not a business case.
    if fin_du_span < debut_du_span:
        raise ValueError(
            f"Span a l'envers : debut={debut_du_span} > fin={fin_du_span}. "
            f"LangExtract rend toujours (debut, fin) avec debut <= fin."
        )

    # GARDE 2 : un offset negatif n'a aucun sens dans un texte.
    # / A negative offset makes no sense in a text.
    if debut_du_span < 0:
        raise ValueError(f"Span negatif : debut={debut_du_span}.")

    if decalages_dans_l_element is None:
        decalages_dans_l_element = {}

    portions = []
    numero_de_la_portion = 0
    fin_de_l_element_precedent = None

    # On parcourt les elements dans l'ordre du document. C'est ce parcours
    # qui donne leur numero aux portions.
    # / We walk elements in document order; that gives portions their number.
    for element in elements_du_chunk:
        bornes_de_l_element = offsets_des_elements_dans_le_chunk.get(element.pk)

        # GARDE 3 : un element sans bornes connues ne peut pas etre croise
        # avec le span. On leve plutot que de le sauter.
        #
        # Pourquoi lever et ne pas sauter ? Parce qu'un saut silencieux
        # produit une ancre INCOMPLETE que rien en aval ne peut detecter :
        # la numerotation se resserre (0, 1 au lieu de 0, 1, 2), la
        # contrainte d'unicite reste satisfaite, et le passage du milieu
        # disparait sans trace. Pour un systeme dont le but est de garantir
        # qu'on remonte a la source, ancrer faux est pire que planter.
        # / A silent skip yields an incomplete anchor nothing downstream can
        # detect. Anchoring wrong is worse than crashing here.
        if bornes_de_l_element is None:
            raise KeyError(
                f"L'element {element.pk} est dans la liste du chunk mais "
                f"absent de la table des offsets. Impossible de l'ancrer "
                f"sans inventer sa position."
            )

        debut_de_l_element, fin_de_l_element = bornes_de_l_element

        # GARDE 4 : les elements doivent arriver dans l'ordre du document,
        # sans se chevaucher. Sinon ordre_dans_extraction serait faux (il
        # doit valoir 0 pour la portion la plus a gauche) et deux portions
        # pourraient se recouvrir.
        # / Elements must arrive in document order, without overlapping.
        if fin_de_l_element_precedent is not None:
            if debut_de_l_element < fin_de_l_element_precedent:
                raise ValueError(
                    f"Les elements du chunk ne sont pas dans l'ordre du "
                    f"document, ou leurs bornes se chevauchent : l'element "
                    f"{element.pk} commence a {debut_de_l_element} alors que "
                    f"le precedent finit a {fin_de_l_element_precedent}."
                )
        fin_de_l_element_precedent = fin_de_l_element

        # Intersection entre le span et l'element, tous deux exprimes en
        # offsets dans le chunk.
        # / Intersection between the span and the element, both in chunk offsets.
        debut_de_l_intersection = max(debut_du_span, debut_de_l_element)
        fin_de_l_intersection = min(fin_du_span, fin_de_l_element)

        # Fin exclue : deux bornes egales veulent dire zero caractere
        # commun, donc pas de portion.
        # / Equal bounds mean zero shared character, so no portion.
        il_y_a_un_vrai_chevauchement = fin_de_l_intersection > debut_de_l_intersection
        if not il_y_a_un_vrai_chevauchement:
            continue

        # On repasse des offsets du chunk aux offsets de l'element, puis on
        # ajoute le decalage si le chunk ne porte qu'un morceau d'element.
        # / Back from chunk offsets to element offsets, plus the split shift.
        decalage_de_l_element = decalages_dans_l_element.get(element.pk, 0)
        debut_dans_l_element = (
            debut_de_l_intersection - debut_de_l_element + decalage_de_l_element
        )
        fin_dans_l_element = (
            fin_de_l_intersection - debut_de_l_element + decalage_de_l_element
        )

        # GARDE 5 : la portion doit tomber dans le texte de l'element. Un
        # decalage faux donnerait des offsets hors du texte, et
        # texte_de_la_portion() rendrait une chaine vide en silence.
        # / A wrong shift would yield out-of-text offsets and a silent empty slice.
        longueur_du_texte = len(element.texte)
        if fin_dans_l_element > longueur_du_texte:
            raise ValueError(
                f"La portion calculee sort du texte de l'element "
                f"{element.pk} : fin={fin_dans_l_element} alors que le texte "
                f"fait {longueur_du_texte} caracteres. Le decalage fourni "
                f"({decalage_de_l_element}) est probablement faux."
            )

        portions.append({
            "element": element,
            "ordre_dans_extraction": numero_de_la_portion,
            "debut_dans_element": debut_dans_l_element,
            "fin_dans_element": fin_dans_l_element,
        })
        numero_de_la_portion += 1

    return portions


def construire_la_table_des_offsets(elements_du_chunk):
    """
    Construit la table des positions des elements dans un chunk.
    / Builds the table of element positions within a chunk.

    LOCALISATION : hypostasis_extractor/services/ancrage.py

    C'est la fonction reciproque du collage : elle dit ou chaque element
    se retrouve une fois les textes colles avec le separateur.

    On la fournit ici pour que le decoupage puisse etre teste seul, sans
    dependre du chunking. Le chunking (phase C) produit la meme table en
    meme temps qu'il colle les textes, et n'a donc pas besoin de rappeler
    cette fonction.
    / Provided so intersection can be tested without the chunker.

    :param elements_du_chunk: les ElementDocument, dans l'ordre du document
    :return: (texte_du_chunk, {element.pk: (debut, fin)})
    """
    morceaux_de_texte = []
    offsets_des_elements = {}
    position_courante = 0

    for numero, element in enumerate(elements_du_chunk):
        # La table est indexee par pk. Un element non sauvegarde a pk=None :
        # deux d'entre eux ecraseraient la meme entree, et la table dirait
        # que le second commence la ou commence le premier.
        # / Unsaved elements share pk=None and would collide in the table.
        if element.pk is None:
            raise ValueError(
                "Un element non sauvegarde (pk=None) ne peut pas entrer dans "
                "un chunk : la table des offsets est indexee par pk, deux "
                "elements sans pk se marcheraient dessus."
            )

        # A partir du deuxieme element, on ajoute le separateur AVANT lui.
        # / From the second element on, the separator comes before it.
        ce_n_est_pas_le_premier = numero > 0
        if ce_n_est_pas_le_premier:
            morceaux_de_texte.append(SEPARATEUR_DE_JONCTION)
            position_courante += len(SEPARATEUR_DE_JONCTION)

        debut_de_l_element = position_courante
        fin_de_l_element = position_courante + len(element.texte)
        offsets_des_elements[element.pk] = (debut_de_l_element, fin_de_l_element)

        morceaux_de_texte.append(element.texte)
        position_courante = fin_de_l_element

    return "".join(morceaux_de_texte), offsets_des_elements
