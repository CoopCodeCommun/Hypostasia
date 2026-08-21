"""
Le texte qui ENTOURE une citation, pris dans le document source.
/ The document text SURROUNDING a quote.

LOCALISATION : core/services/contexte_de_citation.py

A QUOI IL SERT. Le panneau de preuve montre la citation exacte. Sortie
de son paragraphe, elle se lit mal — et parfois faux : « ce n'est pas
suffisant » ne veut rien dire sans la phrase d'avant. Ce service rend
ce qu'il faut poser en gris de part et d'autre.

CE QU'IL NE FAIT PAS. Il ne rend JAMAIS la citation elle-meme : le
gabarit l'affiche a part, entre les deux contextes. La rendre ici la
ferait apparaitre deux fois.

TROIS REGLES, chacune posee sur une mesure du 20 aout 2026 (225
citations reelles).
"""

from hypostasis_extractor.models import EtatAncrage

# La borne du contexte, de chaque cote de la citation.
#
# POURQUOI UNE BORNE. Le panneau fait 416px, et le plus long element
# mesure **3 251 caracteres**. Sans borne, le contexte noierait la
# citation qu'il existe pour eclairer.
#
# ET POURQUOI ELLE EST GENEREUSE. Le contexte ne s'affiche plus par
# defaut : la fiche montre la CITATION SEULE, et le passage ne vient
# qu'au clic. Ce qu'on ouvre alors doit valoir le geste — sinon le
# depliant promet un passage et rend trois mots.
# Au-dela, c'est la note qu'il faut ouvrir, et le lien « Voir la
# source » est juste dessous.
# / The context no longer shows by default: the card shows the quote
# alone. What unfolds must be worth the gesture.
SIGNES_DE_CONTEXTE = 700

# En deca de quoi on va chercher l'element VOISIN.
#
# POURQUOI CE REPLI EST INDISPENSABLE, et non un raffinement. Une
# extraction couvre souvent son element entier : **94 citations sur 225
# n'ont aucun caractere avant elles** dans leur propre element, et
# **116 sur 225 aucun apres**. Un contexte pris dans le seul element
# d'ancrage serait donc vide une fois sur deux. Avec le repli, il ne
# reste que **2 citations sans avant et 4 sans apres**.
# / Without the fallback the context is empty for half the quotes.
SIGNES_MINIMAUX_AVANT_DE_PRENDRE_LE_VOISIN = 30


def _couper_par_la_gauche(texte, signes):
    """
    Garde la FIN du texte, sans couper au milieu d'un mot.
    / Keeps the END of the text, never mid-word.
    """
    if len(texte) <= signes:
        return texte
    morceau = texte[-signes:]
    # On repart apres la premiere espace : ce qui suit est un mot entier.
    # / Restart after the first space: what follows is a whole word.
    espace = morceau.find(" ")
    if espace != -1:
        morceau = morceau[espace + 1:]
    return "…" + morceau


def _couper_par_la_droite(texte, signes):
    """
    Garde le DEBUT du texte, sans couper au milieu d'un mot.
    / Keeps the START of the text, never mid-word.
    """
    if len(texte) <= signes:
        return texte
    morceau = texte[:signes]
    espace = morceau.rfind(" ")
    if espace != -1:
        morceau = morceau[:espace]
    return morceau + "…"


def _elements_de_la_page(element, memoire):
    """
    Les elements non masques de la page, tries, lus UNE SEULE FOIS.
    / The page's unhidden elements, ordered, read only once.

    POURQUOI CETTE MEMOIRE EXISTE. La colonne des preuves rend une fiche
    par citation, et chacune cherche son element precedent et son
    element suivant : deux requetes par fiche. Mesure sur l'article de
    demonstration — **65 requetes d'elements** pour 63 citations tirees
    de 6 notes seulement. Avec la memoire, c'est 6.

    Elle appartient a l'APPELANT (un dict qu'il cree et jette), pas au
    module : un cache global survivrait a la requete et rendrait un
    document perime apres une edition.
    / The memo belongs to the caller, not the module: a global cache
    would outlive the request and serve a stale document after an edit.
    """
    from core.models import ElementDocument

    if memoire is None:
        return None
    if element.page_id not in memoire:
        memoire[element.page_id] = list(
            ElementDocument.objects.filter(
                page_id=element.page_id, masque=False,
            ).order_by("ordre")
        )
    return memoire[element.page_id]


def _element_voisin(element, vers_l_avant, memoire_des_elements=None):
    """
    L'element non masque juste avant, ou juste apres, dans la page.
    / The nearest unhidden element before, or after, in the page.

    UN ELEMENT MASQUE N'EST JAMAIS UN CONTEXTE. Il a ete retire du
    contenu utile — cas reel : la transcription invente un segment. Le
    donner pour contexte le remettrait dans la preuve par la bande.
    / A hidden element is not evidence; showing it would smuggle it back.
    """
    from core.models import ElementDocument

    tous = _elements_de_la_page(element, memoire_des_elements)
    if tous is not None:
        if vers_l_avant:
            avant = [autre for autre in tous if autre.ordre < element.ordre]
            return avant[-1] if avant else None
        apres = [autre for autre in tous if autre.ordre > element.ordre]
        return apres[0] if apres else None

    voisins = ElementDocument.objects.filter(
        page_id=element.page_id, masque=False,
    )
    if vers_l_avant:
        return voisins.filter(ordre__lt=element.ordre).order_by("-ordre").first()
    return voisins.filter(ordre__gt=element.ordre).order_by("ordre").first()


def _passage_brut(extraction, memoire_des_elements=None):
    """
    Le texte qui entoure la citation, SANS borne ni marque de coupe.
    / The surrounding text, unbounded and unmarked.

    C'est la partie couteuse — jusqu'a deux requetes pour les elements
    voisins. Elle est separee du decoupage pour que la borne puisse
    changer sans toucher a la lecture du document.
    / Separated from the trimming so the bound can change alone.
    """
    if extraction is None:
        return "", ""

    # `.all()` PUIS UN TRI EN MEMOIRE, jamais `.order_by()`.
    #
    # POURQUOI CE N'EST PAS UN DETAIL. La colonne des preuves prefetch
    # `extraction_source__ancrages__element` pour toutes les citations en
    # une requete. Or `.order_by()` ou `.select_related()` sur un manager
    # lie CONSTRUIT UN NOUVEAU QUERYSET, qui ignore le cache du prefetch
    # et repart en base — une fois par fiche. Mesure sur l'article de
    # demonstration : 64 requetes d'ancrages et 65 d'elements, pour rien.
    # `.all()` est le seul appel qui rende le cache.
    # / order_by()/select_related() on a related manager build a fresh
    # queryset and bypass the prefetch cache: one query per card.
    portions = sorted(
        extraction.ancrages.all(),
        key=lambda portion: portion.ordre_dans_extraction,
    )
    if not portions:
        return "", ""

    # UNE ANCRE DETACHEE PORTE DES POSITIONS PERIMEES : le document a
    # change sous elle. Decouper le texte dessus fabriquerait un contexte
    # faux, donne pour une preuve — dans un panneau dont c'est le propos.
    # / A detached anchor carries stale offsets; slicing on them would
    # fabricate context and present it as evidence.
    detachee = any(
        portion.etat_ancrage == EtatAncrage.DETACHEE for portion in portions
    )
    if detachee:
        return "", ""

    premiere, derniere = portions[0], portions[-1]
    avant = premiere.element.texte[:premiere.debut_dans_element]
    apres = derniere.element.texte[derniere.fin_dans_element:]

    if len(avant.strip()) < SIGNES_MINIMAUX_AVANT_DE_PRENDRE_LE_VOISIN:
        precedent = _element_voisin(
            premiere.element, True, memoire_des_elements,
        )
        if precedent:
            avant = precedent.texte + "\n" + avant
        else:
            avant = avant.strip()

    if len(apres.strip()) < SIGNES_MINIMAUX_AVANT_DE_PRENDRE_LE_VOISIN:
        suivant = _element_voisin(
            derniere.element, False, memoire_des_elements,
        )
        if suivant:
            apres = apres + "\n" + suivant.texte
        else:
            apres = apres.strip()

    return avant, apres


def passage_autour_de_la_citation(extraction, memoire_des_elements=None):
    """
    Le passage du document qui entoure la citation, borne et marque.
    / The bounded, marked passage surrounding the quote.

    LOCALISATION : core/services/contexte_de_citation.py

    IL NE S'AFFICHE PAS PAR DEFAUT. La fiche montre la CITATION SEULE —
    c'est elle la preuve — et le passage ne vient qu'au clic. Une carte
    qui ouvre d'emblee sur trois blocs de texte gris noie ce qu'elle
    existe pour montrer.
    / It does not show by default: the card shows the quote alone.

    :param extraction: une `ExtractedEntity`, ou None.
    :param memoire_des_elements: un dict OPTIONNEL, cree et jete par
        l'appelant, ou le service range les elements deja lus. Il evite
        deux requetes par fiche quand on en rend soixante d'affilee.
        / An optional caller-owned memo, to avoid two queries per card.
    :return: un dict — `avant`, `apres`, et `il_y_a_un_passage` : **faux
             quand le document n'entoure la citation de rien**. Le
             gabarit s'en sert pour ne pas proposer d'ouvrir un
             depliant vide : promettre un passage et n'en montrer aucun
             est pire que de ne rien promettre.
             / False when the document surrounds the quote with nothing:
             promising a passage and showing none is worse than silence.
    """
    avant, apres = _passage_brut(extraction, memoire_des_elements)
    avant = _couper_par_la_gauche(avant, SIGNES_DE_CONTEXTE)
    apres = _couper_par_la_droite(apres, SIGNES_DE_CONTEXTE)
    return {
        "avant": avant,
        "apres": apres,
        "il_y_a_un_passage": bool(avant.strip() or apres.strip()),
    }
