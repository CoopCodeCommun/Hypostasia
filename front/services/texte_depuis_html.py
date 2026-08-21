"""
Extraction du texte lisible d'un fragment HTML.
/ Extracting readable text from an HTML fragment.

LOCALISATION : front/services/texte_depuis_html.py

CE QUI RESTE D'UN MODULE DE 504 LIGNES

`front/utils.py` portait le PONT texte<->HTML de l'ancien moteur : il
convertissait les offsets d'une extraction (comptes dans
`text_readability`) en positions dans le HTML, pour y inserer les
surlignages. Tout cela est mort avec l'ancien moteur — le moteur ELEMENT
ancre des portions dans des blocs, il n'a aucun offset a projeter.

Une seule fonction avait une vie propre : celle-ci. Elle derive
`text_readability` depuis `html_readability` a l'ingestion
(`PageCreateSerializer`, conversion de fichiers), ce qui n'a rien a voir
avec l'ancrage. Elle est donc rangee ici, sous un nom qui dit ce qu'elle
fait, avec la seule aide dont elle depend.
/ All that survives of a 504-line module: the one function that had a
life of its own, under a name that says what it does.
"""

import hashlib
import html as html_module
import re

# Regex pour detecter les entites HTML (&amp; &nbsp; &#123; &#x1F; etc.)
# / Regex to detect HTML entities
REGEX_ENTITE_HTML = re.compile(r'&(?:#[xX]?[0-9a-fA-F]+|[a-zA-Z]+);')


def _construire_mapping_text_vers_html(html_brut):
    """
    Parcourt le HTML brut et construit :
    - texte_extrait : le textContent reconstitue (avec whitespace HTML)
    - mapping_debut : dict {text_pos: html_pos} pour chaque position texte

    Logique :
    - Dans un tag <...> : avancer html_pos seulement
    - Dans du texte : avancer les deux compteurs
    - Entites HTML (&amp;, &nbsp;) : un seul char texte = plusieurs chars HTML

    / Walks through raw HTML and builds:
    - texte_extrait: reconstructed textContent (with HTML whitespace)
    - mapping_debut: dict {text_pos: html_pos} for each text position
    """
    texte_extrait = []
    mapping_debut = {}

    html_pos = 0
    text_pos = 0
    longueur_html = len(html_brut)

    while html_pos < longueur_html:
        char_courant = html_brut[html_pos]

        # --- Tag HTML : on avance html_pos sans toucher text_pos ---
        if char_courant == '<':
            fin_tag = html_brut.find('>', html_pos)
            if fin_tag == -1:
                break
            html_pos = fin_tag + 1
            continue

        # --- Entite HTML (&amp; &nbsp; &#123; etc.) ---
        if char_courant == '&':
            match_entite = REGEX_ENTITE_HTML.match(html_brut, html_pos)
            if match_entite:
                entite_brute = match_entite.group(0)
                caractere_decode = html_module.unescape(entite_brute)

                for i, char_decode in enumerate(caractere_decode):
                    mapping_debut[text_pos] = html_pos
                    texte_extrait.append(char_decode)
                    text_pos += 1

                html_pos += len(entite_brute)
                continue

        # --- Caractere texte normal ---
        mapping_debut[text_pos] = html_pos
        texte_extrait.append(char_courant)
        text_pos += 1
        html_pos += 1

    # Position sentinelle pour end_char qui pointe apres le dernier caractere
    # / Sentinel position for end_char pointing past last character
    mapping_debut[text_pos] = html_pos

    return ''.join(texte_extrait), mapping_debut



def extraire_texte_depuis_html(html_brut):
    """
    Extrait le texte lisible depuis du HTML, equivalent a element.textContent.strip().
    Utilise le meme parseur que l'annotation pour garantir la coherence des positions.
    Utilisee par PageCreateSerializer pour deriver text_readability depuis html_readability.
    / Extract readable text from HTML, equivalent to element.textContent.strip().
    Uses the same parser as annotation to guarantee position consistency.
    """
    if not html_brut:
        return ''
    texte_extrait, _ = _construire_mapping_text_vers_html(html_brut)
    return texte_extrait.strip()


def empreinte_d_une_capture(html_readability, text_readability=""):
    """
    L'empreinte de deduplication d'une capture, calculee a un seul
    endroit. / A capture's dedup fingerprint, computed in one place.

    LOCALISATION : front/services/texte_depuis_html.py

    DEUX APPELANTS, UNE SEULE IMPLEMENTATION, ET C'EST LA RAISON D'ETRE
    DE CETTE FONCTION. La vue qui cherche un doublon et le serializer qui
    enregistre doivent obtenir la MEME valeur ; quand ce calcul vivait a
    deux endroits, ils ne s'accordaient pas et le doublon par contenu ne
    se declenchait jamais.
    / Two callers, one implementation: the view that looks for a
    duplicate and the serializer that stores must agree.

    LE HTML SIMPLIFIE FAIT FOI quand il est la : c'est de lui qu'on
    derive `text_readability`, et hacher autre chose que ce qu'on
    enregistre donnerait une empreinte qui ne correspond a rien. Le texte
    soumis ne sert que pour une capture qui n'apporte aucun HTML.
    / The simplified HTML wins when present; the submitted text only
    serves a capture that brings no HTML at all.

    :param html_readability: le HTML simplifie de la capture
    :param text_readability: le texte soumis, utilise a defaut de HTML
    :return: une empreinte SHA256 en hexadecimal (64 caracteres)
    """
    if html_readability:
        texte_de_la_capture = extraire_texte_depuis_html(html_readability)
    else:
        texte_de_la_capture = text_readability or ""
    return hashlib.sha256(texte_de_la_capture.encode("utf-8")).hexdigest()
