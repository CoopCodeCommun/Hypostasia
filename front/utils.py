"""
Utilitaires pour l'annotation HTML cote serveur.
/ Server-side HTML annotation utilities.

Inspiré de LangExtract : on injecte des <span> ancre directement dans le HTML
en mappant les positions text_readability vers les positions HTML.
/ Inspired by LangExtract: inject anchor <span>s directly into HTML
by mapping text_readability positions to HTML positions.

Principe cle : text_readability = texte_extrait.strip()
Les positions des entites (start_char/end_char) sont relatives a text_readability.
On calcule le leading_offset (whitespace en tete du HTML) pour convertir
positions text_readability → positions texte_extrait → positions HTML.
/ Key principle: text_readability = texte_extrait.strip()
Entity positions are relative to text_readability.
We compute leading_offset to convert positions accordingly.
"""

import html as html_module
import logging
import re

logger = logging.getLogger(__name__)

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


def _calculer_leading_offset(texte_extrait):
    """
    Calcule le nombre de caracteres de whitespace en tete de texte_extrait.
    text_readability = texte_extrait[leading_offset:]  (apres rstrip aussi)
    Donc : position dans text_readability + leading_offset = position dans texte_extrait.
    / Compute leading whitespace char count.
    text_readability position + leading_offset = texte_extrait position.
    """
    for i, char in enumerate(texte_extrait):
        if not char.isspace():
            return i
    return len(texte_extrait)


def _rechercher_texte_dans_contenu(texte_cible, extraction_text, hint_position=None):
    """
    Recherche extraction_text dans texte_cible.
    Essaie : exacte, puis soft (\xa0 → espace), puis debut de texte (30 premiers chars).
    Si hint_position est fourni et qu'il y a plusieurs matchs, prefere le plus proche.
    Retourne la position de debut ou None.
    / Search for extraction_text in texte_cible.
    Tries: exact, then soft (nbsp → space), then prefix search (first 30 chars).
    Returns start position or None.
    """
    if not extraction_text or len(extraction_text) < 3:
        return None

    # --- Strategie 1 : recherche exacte ---
    # / Strategy 1: exact search
    index_exact = texte_cible.find(extraction_text)
    if index_exact != -1:
        return index_exact

    # --- Strategie 2 : remplacer \xa0 par espace dans les deux textes ---
    # C'est la cause #1 de mismatch (guillemets francais « \xa0texte\xa0 »)
    # Le remplacement ne change PAS les longueurs (1 char → 1 char)
    # donc les positions restent valides dans le texte original.
    # / Strategy 2: replace \xa0 with space in both (most common mismatch)
    texte_soft = texte_cible.replace('\xa0', ' ')
    search_soft = extraction_text.replace('\xa0', ' ')
    index_soft = texte_soft.find(search_soft)
    if index_soft != -1:
        return index_soft

    # --- Strategie 3 : recherche du debut (30 chars) ---
    # Pour les cas ou le texte a ete legerement tronque/modifie par le LLM
    # / Strategy 3: search first 30 chars (handles LLM truncation)
    prefixe = search_soft[:30]
    if len(prefixe) >= 10:
        index_prefixe = texte_soft.find(prefixe)
        if index_prefixe != -1:
            return index_prefixe

    logger.debug(
        "_rechercher_texte: aucun match pour '%s'",
        extraction_text[:50],
    )
    return None


def annoter_html_avec_ancres(html_brut, text_readability, entites, ids_entites_commentees=None):
    """
    Injecte des ancres <span class="extraction-ancre" data-extraction-id="N"></span>
    dans html_brut pour chaque entite.

    Les positions des entites (start_char/end_char) sont relatives a text_readability.
    text_readability = texte_extrait.strip(), donc on ajoute leading_offset
    pour convertir les positions text_readability → texte_extrait → html_pos.

    Si les positions sont invalides (0-0) ou incoherentes, fallback sur recherche textuelle.
    / Inject anchor spans into html_brut for each entity.
    Entity positions are in text_readability space.
    We add leading_offset to convert to texte_extrait space, then look up html_pos.
    """
    if not html_brut or not entites:
        return html_brut

    # 1. Construire le mapping texte_extrait_pos → html_pos
    texte_extrait, mapping_debut = _construire_mapping_text_vers_html(html_brut)

    # 2. Calculer le decalage entre text_readability et texte_extrait
    # text_readability = texte_extrait.strip()
    # Donc pos_dans_texte_extrait = pos_dans_text_readability + leading_offset
    # / Calculate offset: text_readability = texte_extrait.strip()
    leading_offset = _calculer_leading_offset(texte_extrait)

    # 3. Pour chaque entite, determiner la position d'insertion de l'ancre
    # / For each entity, determine anchor insertion position
    insertions = []

    for entite in entites:
        entite_pk = entite.pk
        start_char = entite.start_char
        end_char = entite.end_char
        extraction_text = entite.extraction_text or ''

        positions_valides = (start_char > 0 or end_char > 0) and end_char > start_char
        position_trouvee = False

        if positions_valides:
            # Convertir position text_readability → position texte_extrait
            # / Convert text_readability position → texte_extrait position
            pos_extrait = start_char + leading_offset

            # Verifier la coherence : le texte a cette position doit correspondre
            # / Sanity check: text at this position should match
            if extraction_text and len(extraction_text) > 5:
                texte_a_position = texte_extrait[pos_extrait:pos_extrait + 30]
                debut_attendu = extraction_text[:30].replace('\xa0', ' ')
                debut_trouve = texte_a_position[:30].replace('\xa0', ' ')
                if debut_attendu[:15] and debut_attendu[:15] not in debut_trouve:
                    # Le leading_offset ne suffit pas (donnees pre-existantes incoherentes)
                    # On fallback sur la recherche textuelle
                    # / leading_offset mismatch (legacy inconsistent data), fallback to text search
                    positions_valides = False

            if positions_valides and pos_extrait in mapping_debut:
                html_pos_insertion = mapping_debut[pos_extrait]
                insertions.append((html_pos_insertion, entite_pk))
                position_trouvee = True

        if not position_trouvee:
            # Fallback : recherche textuelle dans texte_extrait
            # / Fallback: text search in texte_extrait
            pos_trouvee = _rechercher_texte_dans_contenu(
                texte_extrait, extraction_text,
                hint_position=start_char + leading_offset if positions_valides else None,
            )
            if pos_trouvee is not None and pos_trouvee in mapping_debut:
                html_pos_insertion = mapping_debut[pos_trouvee]
                insertions.append((html_pos_insertion, entite_pk))
            elif pos_trouvee is not None:
                # Position trouvee mais pas exactement dans le mapping
                # Prendre la position mappee la plus proche (inferieure)
                # / Found position not in mapping, take closest lower mapped position
                positions_inferieures = [p for p in mapping_debut if p <= pos_trouvee]
                if positions_inferieures:
                    pos_proche = max(positions_inferieures)
                    html_pos_insertion = mapping_debut[pos_proche]
                    insertions.append((html_pos_insertion, entite_pk))
                else:
                    logger.warning(
                        "annoter_html: ancre impossible pour entite pk=%s",
                        entite_pk,
                    )
            else:
                logger.warning(
                    "annoter_html: texte introuvable pour entite pk=%s — '%s'",
                    entite_pk, extraction_text[:60],
                )

    if not insertions:
        return html_brut

    # 4. Trier par html_pos decroissant pour inserer de la fin vers le debut
    # / Sort by html_pos descending to insert from end to start
    insertions.sort(key=lambda t: t[0], reverse=True)

    # 5. Inserer les ancres dans le HTML
    html_modifie = html_brut
    # Set des IDs d'entites ayant des commentaires (pour colorer la pastille)
    # / Set of entity IDs that have comments (to color the dot)
    ids_commentees = ids_entites_commentees or set()

    for html_pos_insertion, entite_pk in insertions:
        # Ajouter la classe "ancre-commentee" si l'entite a des commentaires
        # / Add "ancre-commentee" class if entity has comments
        classe_extra = " ancre-commentee" if entite_pk in ids_commentees else ""
        balise_ancre = (
            f'<span class="extraction-ancre{classe_extra}" data-extraction-id="{entite_pk}"></span>'
        )
        html_modifie = (
            html_modifie[:html_pos_insertion]
            + balise_ancre
            + html_modifie[html_pos_insertion:]
        )

    return html_modifie
